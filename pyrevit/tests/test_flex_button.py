# -*- coding: utf-8 -*-
"""Сухий прогон кнопки «Гнучкий між конекторами» на заглушках API Revit (без Revit).

Запуск з кореня репозиторію:   python3 -m unittest discover -s pyrevit/tests -v
Заглушки повторюють лише ті виклики API, що використовує скрипт; це не заміна перевірці в Revit 2026,
але ловить помилки в логіці (вибір елементів і конекторів, система, дотичні, з'єднання, цикл, скасування).
"""
import io
import math
import os
import re
import runpy
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'HVAC.extension', 'HVAC.tab', 'Systems.panel', 'FlexBetween.pushbutton', 'script.py')
CONFIG = os.path.join(HERE, '..', 'HVAC.extension', 'HVAC.tab', 'Systems.panel', 'FlexBetween.pushbutton', 'config.py')
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_flex_settings


class XYZ(object):
    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = float(x), float(y), float(z)

    def DistanceTo(self, o):
        return math.sqrt((self.X - o.X) ** 2 + (self.Y - o.Y) ** 2 + (self.Z - o.Z) ** 2)

    def Add(self, o):
        return XYZ(self.X + o.X, self.Y + o.Y, self.Z + o.Z)

    def Multiply(self, k):
        return XYZ(self.X * k, self.Y * k, self.Z * k)

    def Negate(self):
        return XYZ(-self.X, -self.Y, -self.Z)

    def t(self):
        return (round(self.X, 6), round(self.Y, 6), round(self.Z, 6))


class EId(object):
    def __init__(self, v):
        self.Value = v


class FakeList(list):
    def Add(self, x):
        self.append(x)


FakeList.__class_getitem__ = classmethod(lambda cls, item: cls)


class Domain(object):
    DomainHvac = 'hvac'
    DomainPiping = 'piping'


class CType(object):
    End = 'end'
    Physical = 'physical'
    Logical = 'logical'


class Connector(object):
    _n = 0

    def __init__(self, owner, origin, direction, domain=Domain.DomainHvac, connected=False, ctype=CType.End,
                 system=None, radius=0.25):
        Connector._n += 1
        self.Id = Connector._n
        self.Owner, self.Origin, self.Domain, self.IsConnected, self.ConnectorType = owner, origin, domain, connected, ctype
        self.CoordinateSystem = types.SimpleNamespace(BasisZ=direction)
        self.MEPSystem, self.Shape, self.Radius = system, 'round', radius
        self.connected_to = []

    def ConnectTo(self, other):
        self.connected_to.append(other)
        self.IsConnected = True
        other.IsConnected = True


class ConnSet(list):
    pass


CATS = {'OST_DuctCurves': -2008000, 'OST_DuctAccessory': -2008016, 'OST_DuctFitting': -2008010,
        'OST_MechanicalEquipment': -2001140, 'OST_DuctTerminal': -2008013, 'OST_FlexDuctCurves': -2008020,
        'OST_PipeCurves': -2008044}


def category(name):
    return types.SimpleNamespace(Id=EId(CATS[name]))


class FakeDuct(object):          # має ConnectorManager (як Duct/FlexDuct)
    def __init__(self, ident, conns=(), level=None, cat='OST_DuctCurves'):
        self.Category = category(cat)
        self.Id = EId(ident)
        self.LevelId = level if level is not None else EId(-1)
        self.ConnectorManager = types.SimpleNamespace(Connectors=ConnSet())
        for c in conns:
            c.Owner = self
            self.ConnectorManager.Connectors.append(c)


class FakeInstance(object):      # сімейство: конектори через MEPModel
    def __init__(self, ident, conns=(), level=None, cat='OST_DuctAccessory'):
        self.Category = category(cat)
        self.Id = EId(ident)
        self.LevelId = level if level is not None else EId(-1)
        self.MEPModel = types.SimpleNamespace(ConnectorManager=types.SimpleNamespace(Connectors=ConnSet()))
        for c in conns:
            c.Owner = self
            self.MEPModel.ConnectorManager.Connectors.append(c)


class ExitScript(Exception):
    pass


class Cancelled(Exception):
    pass


class Param(object):
    def __init__(self):
        self.value = None

    def Set(self, v):
        self.value = v


class FakeFlex(object):
    def __init__(self, points, ident):
        self.Id = EId(ident)
        self.params = {}
        self.ConnectorManager = types.SimpleNamespace(Connectors=ConnSet([
            Connector(self, points[0], XYZ(1, 0, 0)), Connector(self, points[-1], XYZ(-1, 0, 0))]))

    def get_Parameter(self, bip):
        return self.params.setdefault(bip, Param())


class World(object):
    """Умовний проєкт: елементи за id, типи, рівні, журнал викликів."""

    def __init__(self, tangent_api=True):
        self.elements = {}
        self.flex_types = [types.SimpleNamespace(Name='Flex Round', Id=EId(1)), types.SimpleNamespace(Name='Flex Alu', Id=EId(2))]
        self.system_types = [types.SimpleNamespace(Name='Supply Air', Id=EId(10)), types.SimpleNamespace(Name='Return Air', Id=EId(11))]
        self.levels = [types.SimpleNamespace(Name='L1', Id=EId(100), Elevation=0.0), types.SimpleNamespace(Name='L2', Id=EId(101), Elevation=10.0)]
        self.created, self.log, self.tangent_api, self.next_id = [], [], tangent_api, 900
        self.picks = []          # сценарій вибору: елемент або Cancelled
        self.alerts, self.answers = [], {}
        self.tx = []


def run_button(world, answers=None, loop=False, path=None):
    DB = types.SimpleNamespace()
    DB.ElementId = EId
    DB.XYZ = XYZ
    DB.BuiltInCategory = types.SimpleNamespace(**CATS)
    DB.Domain, DB.ConnectorType = Domain, CType
    DB.ConnectorProfileType = types.SimpleNamespace(Round='round', Rectangular='rect')
    DB.BuiltInParameter = types.SimpleNamespace(RBS_CURVE_DIAMETER_PARAM='diam', RBS_CURVE_WIDTH_PARAM='w', RBS_CURVE_HEIGHT_PARAM='h')

    class FlexDuctType(object):
        pass

    class MechanicalSystemType(object):
        pass

    class Level(object):
        pass

    class FlexDuct(object):
        @staticmethod
        def Create(doc, system_id, type_id, level_id, *rest):
            if len(rest) == 3:                       # (startTangent, endTangent, points)
                if not world.tangent_api:
                    raise TypeError('no overload takes 7 arguments')
                t0, t1, pts = rest
                tangents = (t0, t1)
            else:
                (pts,), tangents = rest, None
            world.next_id += 1
            f = FakeFlex(list(pts), world.next_id)
            f.created_with = dict(system=system_id.Value, type=type_id.Value, level=level_id.Value,
                                  points=[p.t() for p in pts], tangents=tangents)
            world.created.append(f)
            world.elements[world.next_id] = f
            return f

    DB.Mechanical = types.SimpleNamespace(FlexDuct=FlexDuct, FlexDuctType=FlexDuctType, MechanicalSystemType=MechanicalSystemType)
    DB.Level = Level
    DB.Element = types.SimpleNamespace(Name=types.SimpleNamespace(GetValue=lambda t: t.Name))

    class Collector(object):
        def __init__(self, d):
            pass

        def OfClass(self, cls):
            return {FlexDuctType: list(world.flex_types), MechanicalSystemType: list(world.system_types),
                    Level: list(world.levels)}.get(cls, [])

    DB.FilteredElementCollector = Collector

    class Transaction(object):
        def __init__(self, d, name):
            pass

        def Start(self):
            world.tx.append('start')

        def Commit(self):
            world.tx.append('commit')

        def RollBack(self):
            world.tx.append('rollback')

    DB.Transaction = Transaction

    class Doc(object):
        ActiveView = types.SimpleNamespace(GenLevel=None)

        def GetElement(self, eid):
            return world.elements[eid.Value if hasattr(eid, 'Value') else eid]

    doc = Doc()

    class Selection(object):
        def PickObject(self, otype, flt, prompt):
            if not world.picks:
                raise Cancelled()
            nxt = world.picks.pop(0)
            if nxt is Cancelled:
                raise Cancelled()
            el = nxt
            world.log.append(('pick', otype, flt.AllowElement(el), prompt, getattr(type(flt), '__namespace__', None)))
            return types.SimpleNamespace(ElementId=el.Id)

    UI = types.SimpleNamespace(Selection=types.SimpleNamespace(
        ISelectionFilter=object, ObjectType=types.SimpleNamespace(Element='element', PointOnElement='pt')))
    uidoc = types.SimpleNamespace(Selection=Selection())

    answers = answers or {}

    def alert(msg, title=None, yes=False, no=False, exitscript=False):
        world.alerts.append(msg)
        if exitscript:
            raise ExitScript(msg)
        return True

    class SelectFromList(object):
        @staticmethod
        def show(items, title=None, button_name=None, multiselect=False):
            world.log.append(('select', title, list(items)))
            for key, val in answers.items():
                if key in title:
                    return val
            return items[0]

    class Comp(object):
        def __init__(self, kind, name=None, **kw):
            self.kind, self.name, self.kw = kind, name, kw

    class FlexForm(object):
        def __init__(self, title, components):
            self.title, self.components, self.values = title, components, {}

        def show(self):
            world.form = self
            reply = answers.get('_form')                  # None — вікно закрито хрестиком
            if reply is not None:
                self.values = dict(reply)

    forms = types.SimpleNamespace(
        alert=alert, SelectFromList=SelectFromList, FlexForm=FlexForm,
        Label=lambda text: Comp('label', text=text),
        ComboBox=lambda name, options, **kw: Comp('combo', name, options=list(options), **kw),
        CheckBox=lambda name, text, **kw: Comp('check', name, text=text, **kw),
        Separator=lambda: Comp('sep'), Button=lambda text, **kw: Comp('button', text=text))

    class Output(object):
        def print_md(self, t):
            world.log.append(('md', t))

    cfg_store = answers.get('_config', {})
    if loop:
        cfg_store['loop'] = 'true'

    class Cfg(object):
        def get_option(self, k, d=None):
            return cfg_store.get(k, d)

        def set_option(self, k, v):
            cfg_store[k] = v

    def script_exit():
        raise ExitScript('exit')

    script = types.SimpleNamespace(get_output=lambda: Output(), exit=script_exit,
                                   get_config=lambda section=None: Cfg(), save_config=lambda: None)
    revit = types.SimpleNamespace(doc=doc, uidoc=uidoc)
    pyrevit = types.ModuleType('pyrevit')
    pyrevit.revit, pyrevit.DB, pyrevit.UI, pyrevit.forms, pyrevit.script = revit, DB, UI, forms, script
    gen = types.ModuleType('System.Collections.Generic')
    gen.List = FakeList
    exc = types.ModuleType('Autodesk.Revit.Exceptions')
    exc.OperationCanceledException = Cancelled
    names = ('pyrevit', 'System', 'System.Collections', 'System.Collections.Generic', 'Autodesk', 'Autodesk.Revit',
             'Autodesk.Revit.Exceptions')
    saved = dict((k, sys.modules.get(k)) for k in names)
    sys.modules.update({'pyrevit': pyrevit, 'System': types.ModuleType('System'),
                        'System.Collections': types.ModuleType('System.Collections'), 'System.Collections.Generic': gen,
                        'Autodesk': types.ModuleType('Autodesk'), 'Autodesk.Revit': types.ModuleType('Autodesk.Revit'),
                        'Autodesk.Revit.Exceptions': exc})
    try:
        runpy.run_path(path or SCRIPT, run_name='__main__')
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return world


def scenario(tangent_api=True):
    """Два елементи з вільними конекторами: повітророзподільник і трійник."""
    w = World(tangent_api)
    supply = types.SimpleNamespace(GetTypeId=lambda: EId(10))
    a = FakeInstance(1, [Connector(None, XYZ(0, 0, 0), XYZ(0, 0, 1), system=supply, radius=0.2)], level=EId(100))
    b = FakeDuct(2, [Connector(None, XYZ(3, 0, 1), XYZ(-1, 0, 0), radius=0.2),
                     Connector(None, XYZ(9, 9, 9), XYZ(1, 0, 0), connected=True)], level=EId(100))
    w.elements = {1: a, 2: b}
    w.a, w.b = a, b
    return w


class FlexButtonTests(unittest.TestCase):
    def test_builds_flex_between_two_connectors_with_tangents(self):
        w = scenario()
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        self.assertEqual(len(w.created), 1)
        f = w.created[0]
        self.assertEqual(f.created_with['points'], [(0, 0, 0), (3, 0, 1)])
        self.assertEqual(f.created_with['tangents'][0].t(), (0, 0, 1))        # вихід із першого по його нормалі
        self.assertEqual(f.created_with['tangents'][1].t(), (1, 0, 0))        # вхід у другий проти його нормалі
        self.assertEqual(w.tx, ['start', 'commit'])

    def test_type_system_and_level(self):
        w = scenario()
        w.picks = [w.a, w.b, Cancelled]
        run_button(w, {u'Тип гнучкого': 'Flex Alu'})
        f = w.created[0].created_with
        self.assertEqual((f['type'], f['system'], f['level']), (2, 10, 100))   # система — з MEPSystem першого конектора

    def test_picks_nearest_free_connector_and_ignores_connected(self):
        w = scenario()
        # клік біля зайнятого конектора (9,9,9) має дати єдиний вільний конектор елемента b
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'][1], (3, 0, 1))

    def test_flex_ends_are_connected_to_both_connectors(self):
        w = scenario()
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        f = w.created[0]
        ends = list(f.ConnectorManager.Connectors)
        self.assertEqual(sum(len(e.connected_to) for e in ends), 2)
        targets = [t for e in ends for t in e.connected_to]
        self.assertIn(w.a.MEPModel.ConnectorManager.Connectors[0], targets)
        self.assertIn(w.b.ConnectorManager.Connectors[0], targets)

    def test_size_is_copied_from_first_connector(self):
        w = scenario()
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        self.assertAlmostEqual(w.created[0].params['diam'].value, 0.4)        # радіус 0.2 → діаметр 0.4

    def test_fallback_for_old_api_without_tangents(self):
        w = scenario(tangent_api=False)
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        cw = w.created[0].created_with
        self.assertIsNone(cw['tangents'])
        pts = cw['points']
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts[0], (0, 0, 0))
        self.assertEqual(pts[3], (3, 0, 1))
        self.assertGreater(pts[1][2], 0)             # друга точка — вгору від першого конектора (його нормаль +Z)
        self.assertLess(pts[2][0], 3)                # передостання — «перед» кінцем (нормаль другого конектора −X)

    def test_loop_on_creates_several_until_escape(self):
        w = scenario()
        c = FakeInstance(3, [Connector(None, XYZ(0, 5, 0), XYZ(0, 0, 1))], level=EId(100))
        d = FakeDuct(4, [Connector(None, XYZ(3, 5, 1), XYZ(-1, 0, 0))], level=EId(100))
        w.elements.update({3: c, 4: d})
        w.picks = [w.a, w.b, c, d, Cancelled]
        run_button(w, loop=True)
        self.assertEqual(len(w.created), 2)
        self.assertEqual([f.created_with['points'][0] for f in w.created], [(0, 0, 0), (0, 5, 0)])
        self.assertEqual(w.tx, ['start', 'commit', 'start', 'commit'])

    def test_closest_pair_of_free_connectors_is_chosen(self):
        w = scenario()
        two_ends = FakeDuct(5, [Connector(None, XYZ(0, 20, 0), XYZ(-1, 0, 0)), Connector(None, XYZ(10, 20, 0), XYZ(1, 0, 0))],
                            level=EId(100))
        w.elements[5] = two_ends
        w.picks = [w.a, two_ends]
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'], [(0, 0, 0), (0, 20, 0)])     # найближчий кінець воздуховода

    def test_closest_pair_when_both_elements_have_several_free_ends(self):
        w = scenario()
        d1 = FakeDuct(5, [Connector(None, XYZ(0, 0, 0), XYZ(-1, 0, 0)), Connector(None, XYZ(10, 0, 0), XYZ(1, 0, 0))])
        d2 = FakeDuct(6, [Connector(None, XYZ(11, 0, 0), XYZ(-1, 0, 0)), Connector(None, XYZ(30, 0, 0), XYZ(1, 0, 0))])
        w.elements.update({5: d1, 6: d2})
        w.picks = [d1, d2]
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'], [(10, 0, 0), (11, 0, 0)])

    def test_filter_class_has_unique_namespace_for_cpython_engine(self):
        spaces = []
        for _ in range(2):                                   # два запуски кнопки = два створення класу
            w = scenario()
            w.picks = [w.a, w.b]
            run_button(w)
            spaces.append([l[4] for l in w.log if l[0] == 'pick'][0])
        self.assertTrue(all(spaces) and spaces[0] != spaces[1], spaces)

    def test_selection_is_whole_element_not_a_point(self):
        w = scenario()
        w.picks = [w.a, w.b]
        run_button(w)
        picks = [l for l in w.log if l[0] == 'pick']
        self.assertEqual([p[1] for p in picks], ['element', 'element'])

    def test_selection_filter_allows_only_duct_categories(self):
        allowed = ('OST_DuctCurves', 'OST_DuctAccessory', 'OST_DuctFitting', 'OST_MechanicalEquipment')
        denied = ('OST_FlexDuctCurves', 'OST_PipeCurves', 'OST_DuctTerminal')
        result = {}
        for name in allowed + denied:
            w1 = scenario()
            el = FakeDuct(50, [Connector(None, XYZ(1, 50, 0), XYZ(1, 0, 0))], cat=name)
            w1.elements[50] = el
            w1.picks = [el, w1.b]
            run_button(w1)
            result[name] = [l for l in w1.log if l[0] == 'pick'][0][2]
        self.assertEqual(result, dict([(n, True) for n in allowed] + [(n, False) for n in denied]))

    def test_filter_rejects_element_without_free_connectors(self):
        w = scenario()
        busy = FakeDuct(60, [Connector(None, XYZ(1, 1, 1), XYZ(1, 0, 0), connected=True)])
        w.elements[60] = busy
        w.picks = [busy, w.b]
        run_button(w)
        self.assertFalse([l for l in w.log if l[0] == 'pick'][0][2])

    def test_connectors_follow_pick_order_for_size_and_system(self):
        w = scenario()
        w.picks = [w.b, w.a]                               # спочатку воздуховод, потім розподільник
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'], [(3, 0, 1), (0, 0, 0)])

    def test_cancel_on_first_pick_creates_nothing(self):
        w = scenario()
        w.picks = [Cancelled]
        run_button(w)
        self.assertEqual((w.created, w.tx), ([], []))

    def test_no_flex_types_aborts(self):
        w = scenario()
        w.flex_types = []
        with self.assertRaises(ExitScript):
            run_button(w)

    def test_too_short_distance_is_reported_and_rolled_back(self):
        w = scenario()
        w.b.ConnectorManager.Connectors[0].Origin = XYZ(0, 0, 0.001)        # менше 1/10 дюйма
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'надто близько' in a for a in w.alerts))
        self.assertEqual(w.tx, ['start', 'rollback'])

    def test_same_connector_twice_is_rejected(self):
        w = scenario()
        w.picks = [w.a, w.a, Cancelled]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'той самий' in a for a in w.alerts))

    def test_system_chosen_by_user_when_connectors_have_none(self):
        w = scenario()
        w.a.MEPModel.ConnectorManager.Connectors[0].MEPSystem = None
        w.picks = [w.a, w.b, Cancelled]
        run_button(w, {u'Тип системи': 'Return Air'})
        self.assertEqual(w.created[0].created_with['system'], 11)

    def test_level_fallback_to_nearest_by_elevation(self):
        w = scenario()
        w.a.LevelId = EId(-1)
        w.a.MEPModel.ConnectorManager.Connectors[0].Origin = XYZ(0, 0, 9.5)
        w.picks = [w.a, w.b, Cancelled]
        run_button(w)
        self.assertEqual(w.created[0].created_with['level'], 101)            # найближчий за висотою — L2

    def test_remembers_last_choice(self):
        w = scenario()
        cfg = {}
        w.picks = [w.a, w.b, Cancelled]
        run_button(w, {u'Тип гнучкого': 'Flex Alu', '_config': cfg})
        self.assertEqual(cfg.get('flex_type'), 'Flex Alu')
        w2 = scenario()
        w2.picks = [w2.a, w2.b, Cancelled]
        run_button(w2, {'_config': cfg})
        self.assertEqual([l for l in w2.log if l[0] == 'select' and u'Тип гнучкого' in l[1]], [])     # вже запам'ятано
        self.assertEqual(w2.created[0].created_with['type'], 2)

    # ---------- режим циклу: за замовчуванням вимкнено ----------

    def _two_pairs(self):
        w = scenario()
        c = FakeInstance(3, [Connector(None, XYZ(0, 5, 0), XYZ(0, 0, 1))], level=EId(100))
        d = FakeDuct(4, [Connector(None, XYZ(3, 5, 1), XYZ(-1, 0, 0))], level=EId(100))
        w.elements.update({3: c, 4: d})
        w.picks = [w.a, w.b, c, d, Cancelled]
        return w

    def test_loop_off_by_default_builds_one_pair_and_stops(self):
        w = self._two_pairs()
        run_button(w)
        self.assertEqual(len(w.created), 1)
        self.assertEqual(len(w.picks), 3)                # друга пара навіть не запитувалась

    def test_loop_off_stops_after_error(self):
        w = scenario()
        w.b.ConnectorManager.Connectors[0].Origin = XYZ(0, 0, 0.001)
        w.picks = [w.a, w.b, w.a, w.b]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertEqual(len(w.picks), 2)                # без циклу — одна спроба

    def test_loop_off_stops_after_same_connector(self):
        w = scenario()
        w.picks = [w.a, w.a, w.a, w.b]
        run_button(w)
        self.assertEqual((w.created, len(w.picks)), ([], 2))

    def test_loop_on_continues_after_same_connector(self):
        w = scenario()
        w.picks = [w.a, w.a, w.a, w.b, Cancelled]
        run_button(w, loop=True)
        self.assertEqual(len(w.created), 1)

    # ---------- тип гнучкого повітровода з налаштувань ----------

    def test_default_type_is_gibkiy_without_asking(self):
        w = scenario()
        w.flex_types.append(types.SimpleNamespace(Name=u'Гибкий', Id=EId(3)))
        w.picks = [w.a, w.b]
        run_button(w)
        self.assertEqual(w.created[0].created_with['type'], 3)
        self.assertEqual([l for l in w.log if l[0] == 'select'], [])

    def test_type_from_settings_wins_over_default(self):
        w = scenario()
        w.flex_types.append(types.SimpleNamespace(Name=u'Гибкий', Id=EId(3)))
        w.picks = [w.a, w.b]
        run_button(w, {'_config': {'flex_type': 'Flex Alu'}})
        self.assertEqual(w.created[0].created_with['type'], 2)

    def test_type_match_ignores_case(self):
        w = scenario()
        w.flex_types.append(types.SimpleNamespace(Name=u'ГИБКИЙ', Id=EId(3)))
        w.picks = [w.a, w.b]
        run_button(w)
        self.assertEqual(w.created[0].created_with['type'], 3)

    def test_asks_list_when_configured_type_missing(self):
        w = scenario()                                      # типів «Гибкий» немає
        w.picks = [w.a, w.b]
        run_button(w, {'_config': {'flex_type': u'Немає такого'}})
        self.assertEqual(len([l for l in w.log if l[0] == 'select']), 1)

    def _comp(self, w, name):
        return [c for c in w.form.components if c.name == name][0]

    def test_config_window_defaults_are_gibkiy_and_loop_off(self):
        w = scenario()
        w.flex_types.append(types.SimpleNamespace(Name=u'Гибкий', Id=EId(3)))
        run_button(w, {'_form': {'flex_type': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(self._comp(w, 'flex_type').kw['default'], u'Гибкий')
        self.assertIn(u'Гибкий', self._comp(w, 'flex_type').kw['options'])
        self.assertFalse(self._comp(w, 'loop').kw['default'])

    def test_config_window_saves_type_and_loop(self):
        w = scenario()
        cfg = {}
        run_button(w, {'_form': {'flex_type': 'Flex Alu', 'loop': True}, '_config': cfg}, path=CONFIG)
        self.assertEqual((cfg['flex_type'], cfg['loop']), ('Flex Alu', 'true'))
        w2 = scenario()                                    # основна кнопка бере збережене: тип Alu, цикл увімкнено
        c = FakeInstance(3, [Connector(None, XYZ(0, 5, 0), XYZ(0, 0, 1))], level=EId(100))
        d = FakeDuct(4, [Connector(None, XYZ(3, 5, 1), XYZ(-1, 0, 0))], level=EId(100))
        w2.elements.update({3: c, 4: d})
        w2.picks = [w2.a, w2.b, c, d, Cancelled]
        run_button(w2, {'_config': cfg})
        self.assertEqual([f.created_with['type'] for f in w2.created], [2, 2])

    def test_config_window_turns_loop_off_again(self):
        w = scenario()
        cfg = {'loop': 'true'}
        run_button(w, {'_form': {'flex_type': 'Flex Round', 'loop': False}, '_config': cfg}, path=CONFIG)
        self.assertEqual(cfg['loop'], 'false')
        self.assertTrue(self._comp(w, 'loop').kw['default'])        # стан у вікні відображає збережений
    def test_config_window_closed_changes_nothing(self):
        w = scenario()
        cfg = {'flex_type': 'Flex Round'}
        with self.assertRaises(ExitScript):
            run_button(w, {'_config': cfg}, path=CONFIG)
        self.assertEqual(cfg, {'flex_type': 'Flex Round'})

    def test_config_button_without_types_aborts(self):
        w = scenario()
        w.flex_types = []
        with self.assertRaises(ExitScript):
            run_button(w, path=CONFIG)


class SettingsModuleTests(unittest.TestCase):
    class Cfg(object):
        def __init__(self, **kw):
            self.d = dict(kw)

        def get_option(self, k, d=None):
            return self.d.get(k, d)

        def set_option(self, k, v):
            self.d[k] = v

    class Broken(object):
        def get_option(self, k, d=None):
            raise RuntimeError('boom')

    def test_loop_is_off_by_default(self):
        self.assertFalse(hvac_flex_settings.is_loop(self.Cfg()))

    def test_loop_truthy_values(self):
        for v in ('true', 'True', ' 1 ', 'yes', 'on'):
            self.assertTrue(hvac_flex_settings.is_loop(self.Cfg(loop=v)), v)
        for v in ('false', '', '0', 'no', 'maybe'):
            self.assertFalse(hvac_flex_settings.is_loop(self.Cfg(loop=v)), v)

    def test_loop_read_error_means_off(self):
        self.assertFalse(hvac_flex_settings.is_loop(self.Broken()))

    def test_set_loop_roundtrip(self):
        c = self.Cfg()
        hvac_flex_settings.set_loop(c, True)
        self.assertTrue(hvac_flex_settings.is_loop(c))
        hvac_flex_settings.set_loop(c, False)
        self.assertFalse(hvac_flex_settings.is_loop(c))

    def test_flex_type_default_and_roundtrip(self):
        c = self.Cfg()
        self.assertEqual(hvac_flex_settings.get_flex_type(c), u'Гибкий')
        hvac_flex_settings.set_flex_type(c, u'Alu')
        self.assertEqual(hvac_flex_settings.get_flex_type(c), u'Alu')
        self.assertEqual(hvac_flex_settings.get_flex_type(self.Broken()), u'Гибкий')

    def test_find_type_index(self):
        f = hvac_flex_settings.find_type_index
        names = [u'Alu', u'гибкий', u'Гибкий воздуховод', u'Гибкий']
        self.assertEqual(f(names, u'Гибкий'), 3)                 # точний збіг важливіший
        self.assertEqual(f([u'ГИБКИЙ', u'Alu'], u'Гибкий'), 0)   # без регістру
        self.assertEqual(f([u'Alu', u'Гибкий воздуховод'], u'Гибкий'), 1)    # за початком назви
        self.assertIsNone(f([u'Alu'], u'Гибкий'))
        self.assertIsNone(f([u'Alu'], u''))


class FlexButtonSourceTests(unittest.TestCase):
    def test_no_fstrings_for_ironpython34(self):
        for path in (SCRIPT, CONFIG, os.path.join(LIB, 'hvac_flex_settings.py')):
            with io.open(path, encoding='utf-8') as f:
                text = f.read()
            self.assertIsNone(re.search(r"""(?<![A-Za-z0-9_])[fF][rR]?['"]""", text), path)


if __name__ == '__main__':
    unittest.main()
