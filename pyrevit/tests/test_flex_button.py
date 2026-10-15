# -*- coding: utf-8 -*-
"""Сухий прогон кнопки «Гнучкий між конекторами» на заглушках API Revit (без Revit).

Запуск з кореня репозиторію:   python3 -m unittest discover -s pyrevit/tests -v
Заглушки повторюють лише ті виклики API, що використовує скрипт; це не заміна перевірці в Revit 2026,
але ловить помилки в логіці (вибір елементів і конекторів, система, дотичні, з'єднання, цикл, скасування).
"""
import io
import shutil
import math
import os
import re
import runpy
import sys
import types
import tempfile
import unittest

NO = u'(не змінювати параметр)'          # пункт «не чіпати параметр» у списку налаштувань
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'HVAC.extension', 'HVAC.tab', 'Systems.panel', 'FlexBetween.pushbutton', 'script.py')
CONFIG = os.path.join(HERE, '..', 'HVAC.extension', 'HVAC.tab', 'Systems.panel', 'FlexBetween.pushbutton', 'config.py')
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
os.environ['HVAC_LOG_DIR'] = tempfile.mkdtemp()      # журнал тестів — не в реальний %APPDATA%
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_flex_settings
import hvac_log


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


class CfgParam(object):
    """Параметр з іменем («Гибкая конфигурация»): значення, тип зберігання, прапорець «лише читання»."""

    def __init__(self, name, value, storage='s', read_only=False, accepts=True):
        self.Definition = types.SimpleNamespace(Name=name)
        self.value, self.StorageType, self.IsReadOnly, self.accepts = value, storage, read_only, accepts
        self.sets = []

    def AsString(self):
        return self.value

    def AsInteger(self):
        return self.value

    def AsValueString(self):
        return str(self.value)

    def Set(self, v):
        self.sets.append(('Set', v))
        if self.accepts:
            self.value = v
        return self.accepts

    def SetValueString(self, v):
        self.sets.append(('SetValueString', v))
        if self.accepts:
            self.value = v
        return self.accepts


class EnumParam(CfgParam):
    """Параметр-список: ціле число, на екрані — текст. lenient=True: Set приймає будь-яке число (як може бути в Revit),
    а текст для зайвих чисел порожній."""

    def __init__(self, name, options, value=0, lenient=False, read_only=False, clamp=False):
        CfgParam.__init__(self, name, value, storage='i', read_only=read_only)
        self.options, self.lenient, self.clamp = list(options), lenient or clamp, clamp

    def AsInteger(self):
        return self.value

    def AsValueString(self):
        if self.clamp:                      # Revit може «притискати» зайве число до останнього варіанта
            return self.options[min(self.value, len(self.options) - 1)]
        return self.options[self.value] if 0 <= self.value < len(self.options) else u''

    def Set(self, v):
        self.sets.append(('Set', v))
        if not isinstance(v, int) or (v >= len(self.options) and not self.lenient):
            return False
        self.value = v
        return True


class HasParams(object):
    def __init__(self, *params):
        self.cfg_params, self.bip_params = {}, {}
        for p in params:
            self.add(p)

    def add(self, p, bip=None):
        """Додати параметр: за назвою й (якщо вказано) за BuiltInParameter."""
        self.cfg_params[p.Definition.Name] = p
        if bip is not None:
            self.bip_params[bip] = p
        return p

    def get_Parameter(self, bip):
        return self.bip_params.get(bip)

    def LookupParameter(self, name):
        return self.cfg_params.get(name)

    @property
    def Parameters(self):
        return list(self.cfg_params.values())


class FlexTypeEl(HasParams):
    def __init__(self, name, ident, *params):
        HasParams.__init__(self, *params)
        self.Name, self.Id = name, EId(ident)


class TypeRef(EId):
    """ElementId типу, який «знає» свій елемент (щоб doc.GetElement(flex.GetTypeId()) працював у заглушці)."""

    def __init__(self, el):
        EId.__init__(self, el.Id.Value)
        self.el = el


class FakeFlex(HasParams):
    def __init__(self, points, ident):
        HasParams.__init__(self)
        self.Id = EId(ident)
        self.params = {}
        self.ConnectorManager = types.SimpleNamespace(Connectors=ConnSet([
            Connector(self, points[0], XYZ(1, 0, 0)), Connector(self, points[-1], XYZ(-1, 0, 0))]))

    def get_Parameter(self, bip):
        if bip in self.bip_params:
            return self.bip_params[bip]
        if bip == 'flexpat':
            return None
        return self.params.setdefault(bip, Param())


class World(object):
    """Умовний проєкт: елементи за id, типи, рівні, журнал викликів."""

    def __init__(self, tangent_api=True):
        self.elements = {}
        self.flex_types = [FlexTypeEl('Flex Round', 1), FlexTypeEl('Flex Alu', 2)]
        self.system_types = [types.SimpleNamespace(Name='Supply Air', Id=EId(10)), types.SimpleNamespace(Name='Return Air', Id=EId(11))]
        self.levels = [types.SimpleNamespace(Name='L1', Id=EId(100), Elevation=0.0), types.SimpleNamespace(Name='L2', Id=EId(101), Elevation=10.0)]
        self.created, self.log, self.tangent_api, self.next_id = [], [], tangent_api, 900
        self.picks = []          # сценарій вибору: елемент або Cancelled
        self.alerts, self.answers = [], {}
        self.tx = []
        self.flex_instances = []


def run_button(world, answers=None, loop=False, path=None):
    DB = types.SimpleNamespace()
    DB.ElementId = EId
    DB.XYZ = XYZ
    DB.BuiltInCategory = types.SimpleNamespace(**CATS)
    DB.Domain, DB.ConnectorType = Domain, CType
    DB.StorageType = types.SimpleNamespace(String='s', Integer='i', Double='d', ElementId='e')
    DB.ConnectorProfileType = types.SimpleNamespace(Round='round', Rectangular='rect')
    DB.BuiltInParameter = types.SimpleNamespace(RBS_CURVE_DIAMETER_PARAM='diam', RBS_CURVE_WIDTH_PARAM='w', RBS_CURVE_HEIGHT_PARAM='h', RBS_FLEX_PATTERN_PARAM='flexpat')

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
            f.GetTypeId = lambda: TypeRef([t for t in world.flex_types if t.Id.Value == type_id.Value][0])
            f.created_with = dict(system=system_id.Value, type=type_id.Value, level=level_id.Value,
                                  points=[p.t() for p in pts], tangents=tangents)
            world.created.append(f)
            world.elements[world.next_id] = f
            return f

    DB.Mechanical = types.SimpleNamespace(FlexDuct=FlexDuct, FlexDuctType=FlexDuctType, MechanicalSystemType=MechanicalSystemType)
    DB.Level = Level
    class NameDescriptor(object):
        """Як у IronPython 3: DB.Element.Name — getset_descriptor, БЕЗ методу GetValue."""

        def __get__(self, obj, objtype=None):
            return obj.Name

    DB.Element = types.SimpleNamespace(Name=NameDescriptor())

    class Collector(object):
        def __init__(self, d):
            pass

        def OfClass(self, cls):
            return {FlexDuctType: list(world.flex_types), MechanicalSystemType: list(world.system_types),
                    Level: list(world.levels), FlexDuct: list(world.flex_instances)}.get(cls, [])

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

        def Regenerate(self):
            world.log.append(('regenerate',))

        def GetElement(self, eid):
            if hasattr(eid, 'el'):
                return eid.el
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
        return answers.get('_alert_result', True)

    class SelectFromList(object):
        @staticmethod
        def show(items, title=None, button_name=None, multiselect=False):
            world.log.append(('select', title, list(items)))
            for key, val in answers.items():
                if key in title:
                    return val
            return items[0]

    class ItemsList(list):
        def Add(self, x):
            self.append(x)

    class Event(object):
        def __init__(self):
            self.handlers = []

        def __iadd__(self, h):                    # button.Click += handler
            self.handlers.append(h)
            return self

    class Combo(object):
        def __init__(self):
            self.Items, self.SelectedItem = ItemsList(), None

    class Check(object):
        IsChecked = False

    class Button(object):
        def __init__(self):
            self.Click = Event()

    class WPFWindow(object):
        """Заглушка pyrevit.forms.WPFWindow: XAML-елементи за x:Name, ShowDialog імітує вибір користувача."""

        def __init__(self, xaml, literal_string=False, **kw):
            if answers.get('_wpf_crash'):
                raise RuntimeError('XAML не розібрано')
            for name in ('param_value', 'loop', 'save_btn', 'cancel_btn'):
                assert 'x:Name="%s"' % name in xaml, name
            assert literal_string
            assert 'IsEditable="False"' in xaml                # лише вибір зі списку, вводити своє не можна
            self.ctl = {'param_value': Combo(), 'loop': Check(), 'save_btn': Button(), 'cancel_btn': Button()}
            self.closed = False

        def FindName(self, name):
            return self.ctl[name]

        def Close(self):
            self.closed = True

        def ShowDialog(self):
            c = self.ctl
            world.form = types.SimpleNamespace(value=c['param_value'].SelectedItem,
                                               options=list(c['param_value'].Items), loop=c['loop'].IsChecked)
            reply = answers.get('_form')              # None — вікно закрито без збереження
            if reply is not None:
                c['param_value'].SelectedItem = reply['value']
                c['loop'].IsChecked = reply['loop']
                for h in c['save_btn'].Click.handlers:
                    h(None, None)

    def ask_for_string(default=None, prompt=None, title=None):
        world.log.append(('ask', prompt, default))
        vals = answers.get('_ask_values')
        return vals.pop(0) if vals is not None else default

    forms = types.SimpleNamespace(alert=alert, SelectFromList=SelectFromList, ask_for_string=ask_for_string)
    if not answers.get('_no_wpf'):
        forms.WPFWindow = WPFWindow

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

    # ---------- ім'я елемента (IronPython 3: Element.Name без GetValue) ----------

    def test_type_names_work_when_element_name_has_no_getvalue(self):
        w = scenario()
        w.picks = [w.a, w.b]
        run_button(w)                                        # раніше: AttributeError 'getset_descriptor'…'GetValue'
        self.assertEqual(len(w.created), 1)
        self.assertNotIn(u'GetValue', self._log_text())

    # ---------- параметр «Гибкая конфигурация» ----------

    def _built(self, w, answers=None, **kw):
        w.picks = [w.a, w.b]
        run_button(w, answers, **kw)
        return w.created[0]

    def test_type_is_chosen_after_button_press_every_time(self):
        w = scenario()
        self._built(w, {u'Тип гнучкого': 'Flex Alu'})
        self.assertEqual([l[1] for l in w.log if l[0] == 'select'], [u'Тип гнучкого повітровода:'])
        self.assertEqual(w.created[0].created_with['type'], 2)

    def test_single_flex_type_is_not_asked(self):
        w = scenario()
        w.flex_types = [FlexTypeEl('Only', 7)]
        self._built(w)
        self.assertEqual([l for l in w.log if l[0] == 'select'], [])

    def test_default_parameter_is_set_on_type_to_gibkiy(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Жорсткий')
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.value, u'Гибкий')
        self.assertEqual(p.sets, [('Set', u'Гибкий')])

    def test_instance_parameter_wins_over_type_parameter(self):
        w = scenario()
        inst, typ = CfgParam(u'Гибкая конфигурация', u'старе'), CfgParam(u'Гибкая конфигурация', u'старе')
        w.flex_types[0].add(typ, 'flexpat')
        # екземпляр створюється самою заглушкою; додаємо параметр екземпляру через підміну конструктора FakeFlex
        FakeFlex_init = FakeFlex.__init__

        def init(self, points, ident):
            FakeFlex_init(self, points, ident)
            self.add(inst, 'flexpat')
        FakeFlex.__init__ = init
        try:
            self._built(w, {u'Тип гнучкого': 'Flex Round'})
        finally:
            FakeFlex.__init__ = FakeFlex_init
        self.assertEqual((inst.value, typ.value), (u'Гибкий', u'старе'))

    def test_empty_value_means_do_not_touch_parameter(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Жорсткий')
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round', '_config': {'config_value': ''}})
        self.assertEqual((p.value, p.sets), (u'Жорсткий', []))

    def test_value_already_equal_is_not_rewritten(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Гибкий')
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.sets, [])

    def test_missing_parameter_does_not_block_building_and_lists_names(self):
        w = scenario()
        other = CfgParam(u'Інший параметр', u'1')
        w.flex_types[0].add(other)                     # інша назва й не вбудований параметр — «Гибкая конфигурация» не знайти
        f = self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(w.tx, ['start', 'commit'])
        text = self._log_text()
        self.assertIn(u'параметра «Гибкая конфигурация» (RBS_FLEX_PATTERN_PARAM) немає', text)
        self.assertIn(u'Інший параметр', text)                                    # перелік параметрів для діагностики
        self.assertTrue(any(l[0] == 'md' and u'Параметра «Гибкая конфигурация» не знайдено' in l[1] for l in w.log))

    def test_read_only_parameter_is_skipped_with_warning(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Жорсткий', read_only=True)
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.sets, [])
        self.assertTrue(any(l[0] == 'md' and u'тільки для читання' in l[1] for l in w.log))

    def test_integer_parameter_uses_int_or_value_string(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', 0, storage='i')
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round', '_config': {'config_value': '3'}})
        self.assertEqual(p.sets, [('Set', 3)])
        w2 = scenario()
        p2 = CfgParam(u'Гибкая конфигурация', 0, storage='i')
        w2.flex_types[0].add(p2, 'flexpat')
        self._built(w2, {u'Тип гнучкого': 'Flex Round'})                          # «Гибкий» — не число й не варіант
        self.assertEqual(p2.value, 0)                                              # значення відновлено
        self.assertTrue(any(l[0] == 'md' and u'не прийнято' in l[1] for l in w2.log))

    def test_parameter_not_accepted_gives_warning_but_still_builds(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Ж', accepts=False)
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(len(w.created), 1)
        self.assertTrue(any(l[0] == 'md' and u'не прийнято' in l[1] for l in w.log))

    def test_parameter_exception_never_blocks_building(self):
        class Boom(CfgParam):
            def Set(self, v):
                raise RuntimeError('параметр-збій-5150')
        w = scenario()
        p = Boom(u'Гибкая конфигурация', u'Ж')
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual((len(w.created), w.tx), (1, ['start', 'commit']))
        self.assertIn(u'параметр-збій-5150', self._log_text())

    # ---------- «Гибкая конфигурация» = RBS_FLEX_PATTERN_PARAM: пошук і значення-список ----------

    def test_builtin_parameter_is_found_even_if_its_name_is_localized_differently(self):
        w = scenario()
        p = CfgParam(u'Flex pattern', u'Rigid')                       # назва іншою мовою, але це той самий BuiltInParameter
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.value, u'Гибкий')

    def test_parameter_found_by_name_when_builtin_missing(self):
        w = scenario()
        p = CfgParam(u'Гибкая конфигурация', u'Жорсткий')
        w.flex_types[0].add(p)                                        # без BuiltInParameter — лише за назвою
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.value, u'Гибкий')

    def test_enum_parameter_text_is_mapped_to_number(self):
        w = scenario()
        p = EnumParam(u'Гибкая конфигурация', [u'Жорсткий', u'Гибкий', u'Спіральний'], value=0)
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual((p.value, p.AsValueString()), (1, u'Гибкий'))

    def test_enum_parameter_lenient_set_still_maps_text(self):
        w = scenario()
        p = EnumParam(u'Гибкая конфигурация', [u'Жорсткий', u'Гибкий'], value=0, lenient=True)
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.value, 1)
        self.assertEqual(len(p.sets) < 20, True)                       # зупинились після кількох промахів, а не на 32

    def test_enum_text_not_among_options_leaves_old_value_and_warns(self):
        w = scenario()
        p = EnumParam(u'Гибкая конфигурация', [u'Жорсткий', u'Спіральний'], value=1)
        w.flex_types[0].add(p, 'flexpat')
        self._built(w, {u'Тип гнучкого': 'Flex Round'})
        self.assertEqual(p.value, 1)                                  # як було
        self.assertEqual(len(w.created), 1)
        self.assertTrue(any(l[0] == 'md' and u'не прийнято' in l[1] for l in w.log))

    # ---------- вікно налаштувань ----------

    def _project_with_enum(self, w, options=(u'Жорсткий', u'Гибкий', u'Спіральний'), on_instance=True, **kw):
        p = EnumParam(u'Гибкая конфигурация', list(options), value=2, **kw)
        if on_instance:
            inst = FakeFlex([XYZ(0, 0, 0), XYZ(1, 0, 0)], 777)
            inst.add(p, 'flexpat')
            w.flex_instances.append(inst)
        else:
            w.flex_types[0].add(p, 'flexpat')
        return p

    def test_options_without_duplicates_when_out_of_range_numbers_repeat_last_text(self):
        w = scenario()
        self._project_with_enum(w, clamp=True)
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(w.form.options, [NO, u'Жорсткий', u'Гибкий', u'Спіральний'])

    def test_config_window_lists_parameter_options_and_defaults_to_gibkiy(self):
        w = scenario()
        self._project_with_enum(w)
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(w.form.options, [NO, u'Жорсткий', u'Гибкий', u'Спіральний'])
        self.assertEqual((w.form.value, w.form.loop), (u'Гибкий', False))

    def test_reading_options_does_not_change_the_project(self):
        w = scenario()
        p = self._project_with_enum(w)
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(p.value, 2)                                  # значення відновлено
        self.assertEqual(w.tx, ['start', 'rollback'])                 # транзакцію відкотено, не закомічено

    def test_options_are_read_from_flex_type_when_no_instances(self):
        w = scenario()
        self._project_with_enum(w, on_instance=False)
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(w.form.options, [NO, u'Жорсткий', u'Гибкий', u'Спіральний'])

    def test_no_options_available_window_still_opens_with_default_text(self):
        w = scenario()                                                # у проєкті немає параметра
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual((w.form.options, w.form.value), ([NO, u'Гибкий'], u'Гибкий'))        # своє вводити не можна
        self.assertEqual(w.tx, [])

    def test_option_reading_failure_is_not_critical(self):
        class Boom(EnumParam):
            def AsInteger(self):
                raise RuntimeError('збій-читання-8812')

            def Set(self, v):
                raise RuntimeError('збій-запису-8812')
        w = scenario()
        inst = FakeFlex([XYZ(0, 0, 0), XYZ(1, 0, 0)], 777)
        inst.add(Boom(u'Гибкая конфигурация', [u'a']), 'flexpat')
        w.flex_instances.append(inst)
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual(w.form.options, [NO, u'Гибкий'])             # вікно все одно відкрилось

    def test_config_window_default_value_is_gibkiy_and_loop_off(self):
        w = scenario()
        run_button(w, {'_form': {'value': u'Гибкий', 'loop': False}}, path=CONFIG)
        self.assertEqual((w.form.value, w.form.loop), (u'Гибкий', False))

    def test_config_window_saves_value_and_loop(self):
        w = scenario()
        cfg = {}
        run_button(w, {'_form': {'value': u' Спіральний ', 'loop': True}, '_config': cfg}, path=CONFIG)
        self.assertEqual((cfg['config_value'], cfg['loop']), (u'Спіральний', 'true'))

    def test_config_window_reflects_saved_values_and_can_turn_loop_off(self):
        w = scenario()
        cfg = {'loop': 'true', 'config_value': u'З'}
        run_button(w, {'_form': {'value': u'З', 'loop': False}, '_config': cfg}, path=CONFIG)
        self.assertEqual((w.form.value, w.form.loop), (u'З', True))
        self.assertEqual(cfg['loop'], 'false')

    def test_config_window_closed_changes_nothing(self):
        w = scenario()
        cfg = {'config_value': u'З'}
        with self.assertRaises(ExitScript):
            run_button(w, {'_config': cfg}, path=CONFIG)
        self.assertEqual(cfg, {'config_value': u'З'})

    def test_config_window_wpf_failure_falls_back_to_options_list(self):
        w = scenario()
        self._project_with_enum(w)
        cfg = {}
        run_button(w, {'_wpf_crash': True, u'Гибкая конфигурация': u'Спіральний', '_alert_result': True, '_config': cfg},
                   path=CONFIG)
        self.assertEqual((cfg['config_value'], cfg['loop']), (u'Спіральний', 'true'))
        self.assertEqual([l[2] for l in w.log if l[0] == 'select'][0][0], u'Гибкий')   # поточне — першим
        self.assertIn(u'XAML не розібрано', self._log_text())

    def test_config_dialogs_without_options_offer_saved_value_only(self):
        w = scenario()
        cfg = {}
        run_button(w, {'_no_wpf': True, '_alert_result': False, '_config': cfg}, path=CONFIG)
        self.assertEqual([l[2] for l in w.log if l[0] == 'select'][0], [u'Гибкий', NO])
        self.assertEqual((cfg['config_value'], cfg['loop']), (u'Гибкий', 'false'))

    def test_config_dialogs_cancel_changes_nothing(self):
        w = scenario()
        cfg = {}
        with self.assertRaises(ExitScript):
            run_button(w, {'_no_wpf': True, u'Гибкая конфигурация': None, '_config': cfg}, path=CONFIG)
        self.assertEqual(cfg, {})

    def test_config_dialogs_no_change_item_saves_empty_value(self):
        w = scenario()
        cfg = {}
        run_button(w, {'_no_wpf': True, u'Гибкая конфигурация': NO, '_alert_result': False, '_config': cfg}, path=CONFIG)
        self.assertEqual(cfg['config_value'], u'')

    def test_window_cannot_take_free_text(self):
        with io.open(CONFIG, encoding='utf-8') as f:
            text = f.read()
        self.assertIn('IsEditable="False"', text)
        self.assertNotIn('.Text', text.split('def main')[0].split('def ask_with_window')[1])   # значення — SelectedItem, не Text

    def test_window_no_change_item_saves_empty_value(self):
        w = scenario()
        cfg = {'config_value': u'Гибкий'}
        run_button(w, {'_form': {'value': NO, 'loop': False}, '_config': cfg}, path=CONFIG)
        self.assertEqual(cfg['config_value'], u'')

    def test_window_selects_saved_option_empty_means_no_change_and_stale_falls_back_to_gibkiy(self):
        for saved, shown in ((u'Спіральний', u'Спіральний'), (u'', NO), (u'Немає такого', u'Гибкий')):
            w = scenario()
            self._project_with_enum(w)
            run_button(w, {'_form': {'value': shown, 'loop': False}, '_config': {'config_value': saved}}, path=CONFIG)
            self.assertEqual(w.form.value, shown, saved)

    # ---------- установка: папка lib ----------

    def _isolated_imports(self):
        """Прибрати lib зі sys.path і наші модулі з кешу (як чистий запуск у pyRevit); повертає функцію відновлення."""
        saved_path = list(sys.path)
        saved_mods = dict((k, v) for k, v in sys.modules.items() if k.startswith('hvac_'))
        sys.path[:] = [p for p in sys.path if os.path.abspath(p) != os.path.abspath(LIB)]
        for k in saved_mods:
            del sys.modules[k]

        def restore():
            sys.path[:] = saved_path
            for k in [k for k in sys.modules if k.startswith('hvac_')]:
                del sys.modules[k]
            sys.modules.update(saved_mods)
        return restore

    def test_works_even_if_pyrevit_did_not_put_lib_on_sys_path(self):
        restore = self._isolated_imports()
        try:
            w = scenario()
            w.picks = [w.a, w.b]
            run_button(w)                                    # lib знаходиться за розташуванням самого script.py
            self.assertEqual(len(w.created), 1)
        finally:
            restore()

    def test_missing_lib_file_gives_clear_message_with_path(self):
        ext = os.path.abspath(os.path.join(HERE, '..', 'HVAC.extension'))
        tmp = tempfile.mkdtemp()
        copy = os.path.join(tmp, 'HVAC.extension')
        shutil.copytree(ext, copy)
        os.remove(os.path.join(copy, 'lib', 'hvac_log.py'))             # «не докопіювали» файл
        script_copy = os.path.join(copy, 'HVAC.tab', 'Systems.panel', 'FlexBetween.pushbutton', 'script.py')
        restore = self._isolated_imports()
        try:
            w = scenario()
            with self.assertRaises(ExitScript):
                run_button(w, path=script_copy)
        finally:
            restore()
        self.assertEqual(len(w.alerts), 1)
        self.assertIn('hvac_log.py', w.alerts[0])
        self.assertIn(os.path.join(copy, 'lib'), w.alerts[0])           # показано, де шукав

    # ---------- журнал ----------

    def _log_text(self):
        with io.open(hvac_log.log_path(), encoding='utf-8') as f:
            return f.read()

    def test_normal_run_leaves_trail_in_log(self):
        w = scenario()
        w.picks = [w.a, w.b]
        run_button(w)
        text = self._log_text()
        self.assertIn(u'[flex_between] === запуск', text)
        self.assertIn(u'вибрано:', text)
        self.assertIn(u'пара конекторів:', text)
        self.assertIn(u'FlexDuct.Create: варіант з дотичними', text)
        self.assertIn(u'створено, id', text)

    def test_old_api_fallback_is_logged(self):
        w = scenario(tangent_api=False)
        w.picks = [w.a, w.b]
        run_button(w)
        text = self._log_text()
        self.assertIn(u'недоступний', text)
        self.assertIn(u'варіант з 4 точками', text)

    def test_build_error_is_logged_with_traceback(self):
        w = scenario()
        w.b.ConnectorManager.Connectors[0].Origin = XYZ(0, 0, 0.0012)
        w.picks = [w.a, w.b]
        run_button(w)
        text = self._log_text()
        self.assertIn(u'транзакцію відкотено', text)
        self.assertIn(u'надто близько', text)
        self.assertTrue(any(hvac_log.log_path() in a for a in w.alerts))      # шлях до журналу в повідомленні

    def test_unexpected_error_is_logged_and_reported_instead_of_bare_crash(self):
        class BadType(object):
            Id = EId(7)

            @property
            def Name(self):
                raise RuntimeError('несподіванка-9001')

        w = scenario()
        w.flex_types = [BadType()]
        run_button(w)                                        # не кидає: помилку обробив журнал
        self.assertIn(u'RuntimeError: несподіванка-9001', self._log_text())
        self.assertTrue(any(hvac_log.log_path() in a for a in w.alerts))
        self.assertTrue(any(l[0] == 'md' and 'несподіванка-9001' in l[1] for l in w.log))

    def test_cancel_by_esc_is_logged_without_error(self):
        w = scenario()
        w.picks = [Cancelled]
        run_button(w)
        self.assertIn(u'вибір скасовано (Esc)', self._log_text())

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
        shown = [l for l in w2.log if l[0] == 'select' and u'Тип гнучкого' in l[1]]
        self.assertEqual(len(shown), 1)                                      # тип обирається при кожному запуску
        self.assertEqual(shown[0][2][0], 'Flex Alu')                         # останній обраний — першим у списку
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


class ConfigSettingsTests(unittest.TestCase):
    def test_defaults(self):
        c = SettingsModuleTests.Cfg()
        self.assertEqual(hvac_flex_settings.get_config_value(c), u'Гибкий')
        self.assertEqual(hvac_flex_settings.BUILTIN_PARAM, 'RBS_FLEX_PATTERN_PARAM')

    def test_roundtrip_strips_spaces_and_keeps_empty(self):
        c = SettingsModuleTests.Cfg()
        hvac_flex_settings.set_config_value(c, u' Знач ')
        self.assertEqual(hvac_flex_settings.get_config_value(c), u'Знач')
        hvac_flex_settings.set_config_value(c, u'')
        self.assertEqual(hvac_flex_settings.get_config_value(c), u'')

    def test_read_error_gives_default(self):
        self.assertEqual(hvac_flex_settings.get_config_value(SettingsModuleTests.Broken()), u'Гибкий')


class FlexButtonSourceTests(unittest.TestCase):
    def test_no_fstrings_for_ironpython34(self):
        for path in (SCRIPT, CONFIG, os.path.join(LIB, 'hvac_flex_settings.py')):
            with io.open(path, encoding='utf-8') as f:
                text = f.read()
            self.assertIsNone(re.search(r"""(?<![A-Za-z0-9_])[fF][rR]?['"]""", text), path)


if __name__ == '__main__':
    unittest.main()
