# -*- coding: utf-8 -*-
"""Сухий прогон кнопки «Гнучкий між конекторами» на заглушках API Revit (без Revit).

Запуск з кореня репозиторію:   python3 -m unittest discover -s pyrevit/tests -v
Заглушки повторюють лише ті виклики API, що використовує скрипт; це не заміна перевірці в Revit 2026,
але ловить помилки в логіці (вибір конектора, система, дотичні, з'єднання, цикл, скасування).
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


class FakeDuct(object):          # має ConnectorManager (як Duct/FlexDuct)
    def __init__(self, ident, conns=(), level=None):
        self.Id = EId(ident)
        self.LevelId = level if level is not None else EId(-1)
        self.ConnectorManager = types.SimpleNamespace(Connectors=ConnSet())
        for c in conns:
            c.Owner = self
            self.ConnectorManager.Connectors.append(c)


class FakeInstance(object):      # сімейство: конектори через MEPModel
    def __init__(self, ident, conns=(), level=None):
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
        self.picks = []          # сценарій кліків: (element, point) або Cancelled
        self.alerts, self.answers = [], {}
        self.tx = []


def run_button(world, answers=None):
    DB = types.SimpleNamespace()
    DB.ElementId = EId
    DB.XYZ = XYZ
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
            el, pt = nxt
            assert flt.AllowElement(el) or True
            return types.SimpleNamespace(ElementId=el.Id, GlobalPoint=pt)

    UI = types.SimpleNamespace(Selection=types.SimpleNamespace(
        ISelectionFilter=object, ObjectType=types.SimpleNamespace(PointOnElement='pt')))
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

    forms = types.SimpleNamespace(alert=alert, SelectFromList=SelectFromList)

    class Output(object):
        def print_md(self, t):
            world.log.append(('md', t))

    cfg_store = answers.get('_config', {})

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
        runpy.run_path(SCRIPT, run_name='__main__')
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
        w.picks = [(w.a, XYZ(0, 0, 0.1)), (w.b, XYZ(3, 0, 1.1)), Cancelled]
        run_button(w)
        self.assertEqual(len(w.created), 1)
        f = w.created[0]
        self.assertEqual(f.created_with['points'], [(0, 0, 0), (3, 0, 1)])
        self.assertEqual(f.created_with['tangents'][0].t(), (0, 0, 1))        # вихід із першого по його нормалі
        self.assertEqual(f.created_with['tangents'][1].t(), (1, 0, 0))        # вхід у другий проти його нормалі
        self.assertEqual(w.tx, ['start', 'commit'])

    def test_type_system_and_level(self):
        w = scenario()
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w, {u'Тип гнучкого': 'Flex Alu'})
        f = w.created[0].created_with
        self.assertEqual((f['type'], f['system'], f['level']), (2, 10, 100))   # система — з MEPSystem першого конектора

    def test_picks_nearest_free_connector_and_ignores_connected(self):
        w = scenario()
        # клік біля зайнятого конектора (9,9,9) має дати єдиний вільний конектор елемента b
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(9, 9, 9)), Cancelled]
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'][1], (3, 0, 1))

    def test_flex_ends_are_connected_to_both_connectors(self):
        w = scenario()
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w)
        f = w.created[0]
        ends = list(f.ConnectorManager.Connectors)
        self.assertEqual(sum(len(e.connected_to) for e in ends), 2)
        targets = [t for e in ends for t in e.connected_to]
        self.assertIn(w.a.MEPModel.ConnectorManager.Connectors[0], targets)
        self.assertIn(w.b.ConnectorManager.Connectors[0], targets)

    def test_size_is_copied_from_first_connector(self):
        w = scenario()
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w)
        self.assertAlmostEqual(w.created[0].params['diam'].value, 0.4)        # радіус 0.2 → діаметр 0.4

    def test_fallback_for_old_api_without_tangents(self):
        w = scenario(tangent_api=False)
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w)
        cw = w.created[0].created_with
        self.assertIsNone(cw['tangents'])
        pts = cw['points']
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts[0], (0, 0, 0))
        self.assertEqual(pts[3], (3, 0, 1))
        self.assertGreater(pts[1][2], 0)             # друга точка — вгору від першого конектора (його нормаль +Z)
        self.assertLess(pts[2][0], 3)                # передостання — «перед» кінцем (нормаль другого конектора −X)

    def test_loop_creates_several_until_escape(self):
        w = scenario()
        c = FakeInstance(3, [Connector(None, XYZ(0, 5, 0), XYZ(0, 0, 1))], level=EId(100))
        d = FakeDuct(4, [Connector(None, XYZ(3, 5, 1), XYZ(-1, 0, 0))], level=EId(100))
        w.elements.update({3: c, 4: d})
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), (c, XYZ(0, 5, 0)), (d, XYZ(3, 5, 1)), Cancelled]
        run_button(w)
        self.assertEqual(len(w.created), 2)
        self.assertEqual([f.created_with['points'][0] for f in w.created], [(0, 0, 0), (0, 5, 0)])
        self.assertEqual(w.tx, ['start', 'commit', 'start', 'commit'])

    def test_nearest_of_several_free_connectors_is_chosen(self):
        w = scenario()
        two_ends = FakeDuct(5, [Connector(None, XYZ(0, 20, 0), XYZ(-1, 0, 0)), Connector(None, XYZ(10, 20, 0), XYZ(1, 0, 0))],
                            level=EId(100))
        w.elements[5] = two_ends
        w.picks = [(w.a, XYZ(0, 0, 0)), (two_ends, XYZ(9.5, 20, 0)), Cancelled]       # клік біля другого кінця
        run_button(w)
        self.assertEqual(w.created[0].created_with['points'][1], (10, 20, 0))

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
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(0, 0, 0.001)), Cancelled]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'надто близько' in a for a in w.alerts))
        self.assertEqual(w.tx, ['start', 'rollback'])

    def test_same_connector_twice_is_rejected(self):
        w = scenario()
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.a, XYZ(0, 0, 0)), Cancelled]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'той самий' in a for a in w.alerts))

    def test_system_chosen_by_user_when_connectors_have_none(self):
        w = scenario()
        w.a.MEPModel.ConnectorManager.Connectors[0].MEPSystem = None
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w, {u'Тип системи': 'Return Air'})
        self.assertEqual(w.created[0].created_with['system'], 11)

    def test_level_fallback_to_nearest_by_elevation(self):
        w = scenario()
        w.a.LevelId = EId(-1)
        w.a.MEPModel.ConnectorManager.Connectors[0].Origin = XYZ(0, 0, 9.5)
        w.picks = [(w.a, XYZ(0, 0, 9.5)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w)
        self.assertEqual(w.created[0].created_with['level'], 101)            # найближчий за висотою — L2

    def test_remembers_last_choice(self):
        w = scenario()
        cfg = {}
        w.picks = [(w.a, XYZ(0, 0, 0)), (w.b, XYZ(3, 0, 1)), Cancelled]
        run_button(w, {u'Тип гнучкого': 'Flex Alu', '_config': cfg})
        self.assertEqual(cfg.get('flex_type'), 'Flex Alu')
        w2 = scenario()
        w2.picks = [Cancelled]
        run_button(w2, {'_config': cfg})
        shown = [l for l in w2.log if l[0] == 'select'][0]
        self.assertEqual(shown[2][0], 'Flex Alu')                           # останній обраний — першим у списку

    def test_no_fstrings_for_ironpython34(self):
        with io.open(SCRIPT, encoding='utf-8') as f:
            text = f.read()
        self.assertIsNone(re.search(r"""(?<![A-Za-z0-9_])[fF][rR]?['"]""", text))


if __name__ == '__main__':
    unittest.main()
