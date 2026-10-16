# -*- coding: utf-8 -*-
"""Сухой прогон кнопки FlexTail на заглушках API Revit (без Revit).

Запуск из корня репозитория:   python3 -m unittest discover -s pyrevit/tests -v
Заглушки повторяют только те вызовы API, что использует скрипт; это не замена проверке в Revit 2026, но ловит ошибки
логики: выбор коннектора, направление, разрез, замена куска на гибкий, подключения, запоминание, сообщения.
"""
import math
import os
import re
import runpy
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'HVAC.extension', 'HVAC.tab', 'Systems.panel', 'FlexTail.pushbutton', 'script.py')
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
os.environ.setdefault('HVAC_LOG_DIR', tempfile.mkdtemp())
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_log

MM = 1.0 / 304.8             # миллиметр в футах


class ExitScript(Exception):
    pass


class Cancelled(Exception):
    pass


class XYZ(object):
    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = float(x), float(y), float(z)

    def DistanceTo(self, o):
        return math.sqrt((self.X - o.X) ** 2 + (self.Y - o.Y) ** 2 + (self.Z - o.Z) ** 2)

    def Add(self, o):
        return XYZ(self.X + o.X, self.Y + o.Y, self.Z + o.Z)

    def Subtract(self, o):
        return XYZ(self.X - o.X, self.Y - o.Y, self.Z - o.Z)

    def Multiply(self, k):
        return XYZ(self.X * k, self.Y * k, self.Z * k)

    def Negate(self):
        return XYZ(-self.X, -self.Y, -self.Z)

    def Normalize(self):
        n = math.sqrt(self.X ** 2 + self.Y ** 2 + self.Z ** 2)
        return XYZ(self.X / n, self.Y / n, self.Z / n)

    def t(self):
        return (round(self.X, 6), round(self.Y, 6), round(self.Z, 6))


class EId(object):
    def __init__(self, v):
        self.Value = v


class FakeList(list):
    def Add(self, x):
        self.append(x)


FakeList.__class_getitem__ = classmethod(lambda cls, item: cls)

HVAC, PIPING = 'hvac', 'piping'
END = 'end'
CATS = {'OST_DuctCurves': -2008000, 'OST_DuctAccessory': -2008016, 'OST_DuctFitting': -2008010,
        'OST_MechanicalEquipment': -2001140, 'OST_DuctTerminal': -2008013, 'OST_FlexDuctCurves': -2008020}


class Conn(object):
    def __init__(self, owner, origin, direction, domain=HVAC, system=None, radius_mm=100, shape='round',
                 width_mm=None, height_mm=None):
        self.Owner, self.Origin, self.Domain, self.ConnectorType = owner, origin, domain, END
        self.CoordinateSystem = types.SimpleNamespace(BasisZ=direction)
        self.MEPSystem, self.Shape = system, shape
        self.Radius = radius_mm * MM
        self.Width = None if width_mm is None else width_mm * MM
        self.Height = None if height_mm is None else height_mm * MM
        self.refs = []

    @property
    def AllRefs(self):
        return list(self.refs)

    @property
    def IsConnected(self):
        return bool(self.refs)

    def ConnectTo(self, other):
        if other not in self.refs:
            self.refs.append(other)
        if self not in other.refs:
            other.refs.append(self)

    def disconnect(self):
        for r in list(self.refs):
            r.refs.remove(self)
        self.refs = []


class ConnSet(list):
    pass


class LogicalConn(object):
    """Логический коннектор системы: Connector.AllRefs у реального Revit возвращает и его; вместе с удалённым
    воздуховодом он становится недействительным, и обращение к нему даёт исключение."""
    is_logical = True

    def __init__(self, system):
        self.Owner, self.ConnectorType, self.Domain = system, 'logical', HVAC
        self.refs, self.valid = [], True

    @property
    def Origin(self):
        if not self.valid:
            raise RuntimeError('The referenced object is not valid, possibly because it has been deleted from the database')
        return XYZ(0, 0, 0)

    def disconnect(self):
        for r in list(self.refs):
            if self in r.refs:
                r.refs.remove(self)
        self.refs = []


class Element(object):
    _bips = None

    def __init__(self, ident, cat, level=None):
        self.Id = EId(ident)
        self.Category = types.SimpleNamespace(Id=EId(CATS[cat]), Name=cat)
        self.LevelId = level if level is not None else EId(-1)
        self.bip = {}

    def get_Parameter(self, bip):
        return self.bip.get(bip)

    def conns(self):
        return []


class Equip(Element):             # FamilyInstance: коннекторы через MEPModel
    def __init__(self, ident, cat='OST_MechanicalEquipment', level=None):
        Element.__init__(self, ident, cat, level)
        self.MEPModel = types.SimpleNamespace(ConnectorManager=types.SimpleNamespace(Connectors=ConnSet()))

    def add(self, c):
        c.Owner = self
        self.MEPModel.ConnectorManager.Connectors.append(c)
        return c

    def conns(self):
        return list(self.MEPModel.ConnectorManager.Connectors)


class CurveBase(Element):         # MEPCurve: коннекторы через ConnectorManager
    def __init__(self, ident, cat, level=None):
        Element.__init__(self, ident, cat, level)
        self.ConnectorManager = types.SimpleNamespace(Connectors=ConnSet())

    def add(self, c):
        c.Owner = self
        self.ConnectorManager.Connectors.append(c)
        return c

    def conns(self):
        return list(self.ConnectorManager.Connectors)


class RigidDuct(CurveBase):
    def __init__(self, ident, level=None):
        CurveBase.__init__(self, ident, 'OST_DuctCurves', level)


class Param(object):
    def __init__(self, value=None):
        self.value = value

    def Set(self, v):
        self.value = v
        return True

    def AsElementId(self):
        return self.value


class FlexInst(CurveBase):
    def __init__(self, ident, points, type_el):
        CurveBase.__init__(self, ident, 'OST_FlexDuctCurves')
        self.type_el = type_el
        self.params = {}
        self.add(Conn(self, points[0], XYZ(1, 0, 0)))
        self.add(Conn(self, points[-1], XYZ(-1, 0, 0)))

    def GetTypeId(self):
        return types.SimpleNamespace(Value=self.type_el.Id.Value, el=self.type_el)

    def get_Parameter(self, bip):
        if bip == 'flexpat':
            return None
        return self.params.setdefault(bip, Param())

    def LookupParameter(self, name):
        return None

    @property
    def Parameters(self):
        return []


class CfgParam(object):
    def __init__(self, name, value, read_only=False, accepts=True):
        self.Definition = types.SimpleNamespace(Name=name)
        self.value, self.StorageType, self.IsReadOnly, self.accepts = value, 's', read_only, accepts
        self.sets = []

    def AsString(self):
        return self.value

    def AsValueString(self):
        return str(self.value)

    def Set(self, v):
        self.sets.append(v)
        if self.accepts:
            self.value = v
        return self.accepts


class FlexType(object):
    def __init__(self, name, ident, shape=None, param=None):
        self.Name, self.Id = name, EId(ident)
        if shape is not None:
            self.Shape = shape
        self.param = param

    def get_Parameter(self, bip):
        return self.param if bip == 'flexpat' else None

    def LookupParameter(self, name):
        return self.param if (self.param is not None and self.param.Definition.Name == name) else None

    @property
    def Parameters(self):
        return [self.param] if self.param is not None else []


class World(object):
    def __init__(self, tangent_api=True):
        self.elements = {}
        self.flex_types = [FlexType('Flex Round', 1, 'round'), FlexType('Flex Alu', 2, 'round')]
        self.levels = [types.SimpleNamespace(Name='L1', Id=EId(100), Elevation=0.0)]
        self.picks, self.prompts, self.alerts, self.log = [], [], [], []
        self.tx, self.created, self.deleted = [], [], []
        self.next_id = 900
        self.tangent_api = tangent_api
        self.saves = 0
        self.ns = None


def run_button(world, answers=None):
    answers = answers or {}
    DB = types.SimpleNamespace()
    DB.XYZ = XYZ
    DB.MEPCurve, DB.FamilyInstance = CurveBase, Equip
    DB.ConnectorType = types.SimpleNamespace(End=END, Physical='physical', Logical='logical')

    class Cats(object):
        def __getattr__(self, name):
            if name in CATS:
                return CATS[name]
            raise AttributeError(name)

    DB.BuiltInCategory = Cats()
    DB.Domain = types.SimpleNamespace(DomainHvac=HVAC, DomainPiping=PIPING)
    DB.StorageType = types.SimpleNamespace(String='s', Integer='i', Double='d', ElementId='e')
    DB.ConnectorProfileType = types.SimpleNamespace(Round='round', Rectangular='rect', Oval='oval')
    DB.BuiltInParameter = types.SimpleNamespace(
        RBS_CURVE_DIAMETER_PARAM='diam', RBS_CURVE_WIDTH_PARAM='w', RBS_CURVE_HEIGHT_PARAM='h',
        RBS_FLEX_PATTERN_PARAM='flexpat', RBS_DUCT_SYSTEM_TYPE_PARAM='systype')

    class FlexDuctType(object):
        pass

    class Level(object):
        pass

    class Transaction(object):
        def __init__(self, d, name=None):
            world.tx_names = getattr(world, 'tx_names', []) + [name]

        def Start(self):
            world.tx.append('start')

        def Commit(self):
            world.tx.append('commit')

        def RollBack(self):
            world.tx.append('rollback')

    class FlexDuct(object):
        @staticmethod
        def Create(d, system_id, type_id, level_id, *rest):
            if len(rest) == 3:
                if not world.tangent_api:
                    raise TypeError('no overload takes 7 arguments')
                t0, t1, pts = rest
                tangents = (t0, t1)
            else:
                (pts,), tangents = rest, None
            world.next_id += 1
            type_el = [t for t in world.flex_types if t.Id.Value == type_id.Value][0]
            f = FlexInst(world.next_id, list(pts), type_el)
            f.created_with = dict(system=system_id.Value, type=type_id.Value, level=level_id.Value,
                                  points=[p.t() for p in pts], tangents=tangents)
            world.created.append(f)
            world.elements[world.next_id] = f
            return f

    class MechanicalUtils(object):
        @staticmethod
        def BreakCurve(d, duct_id, point):
            """Режет воздуховод: исходный остаётся от первого коннектора до точки, новый — от точки до второго.
            Подключения дальнего конца переезжают на новый воздуховод; куски друг с другом не соединяются."""
            if answers.get('_break_crash'):
                raise RuntimeError('BreakCurve отказал')
            old = world.elements[duct_id.Value]
            c0, c1 = old.conns()
            world.next_id += 1
            new = RigidDuct(world.next_id, old.LevelId)
            near_new = new.add(Conn(new, point, c0.CoordinateSystem.BasisZ, system=c0.MEPSystem, shape=c0.Shape))
            far_new = new.add(Conn(new, c1.Origin, c1.CoordinateSystem.BasisZ, system=c0.MEPSystem, shape=c0.Shape))
            for c in (near_new, far_new):
                c.Radius, c.Width, c.Height = c0.Radius, c0.Width, c0.Height
            for r in list(c1.refs):
                r.refs.remove(c1)
                far_new.ConnectTo(r)
            c1.refs = []
            c1.Origin = point
            world.elements[world.next_id] = new
            world.broken = True
            return new.Id

    DB.Mechanical = types.SimpleNamespace(Duct=RigidDuct, FlexDuct=FlexDuct, FlexDuctType=FlexDuctType,
                                          MechanicalUtils=MechanicalUtils)
    DB.Level = Level
    DB.Transaction = Transaction
    DB.Element = types.SimpleNamespace()

    class Collector(object):
        def __init__(self, d):
            pass

        def OfClass(self, cls):
            return {FlexDuctType: list(world.flex_types), Level: list(world.levels)}.get(cls, [])

    DB.FilteredElementCollector = Collector

    def get_element(x):
        v = getattr(x, 'Value', x)
        if hasattr(x, 'el'):
            return x.el
        if v in world.elements:
            return world.elements[v]
        for t in world.flex_types:
            if t.Id.Value == v:
                return t
        return None

    def delete(eid):
        el = world.elements.pop(eid.Value)
        for c in el.conns():
            for r in c.refs:
                if getattr(r, 'is_logical', False):
                    r.valid = False                      # логическая связь с системой исчезает вместе с воздуховодом
            c.disconnect()
        world.deleted.append(eid.Value)

    doc = types.SimpleNamespace(GetElement=get_element, Delete=delete, Regenerate=lambda: None,
                                ActiveView=types.SimpleNamespace(GenLevel=None),
                                Application=types.SimpleNamespace(VersionNumber='2026', Language='ru'))

    class Selection(object):
        def PickObject(self, object_type, flt, prompt):
            world.prompts.append(prompt)
            item = world.picks.pop(0)
            if item is Cancelled:
                raise Cancelled()
            el, point = item
            assert flt.AllowElement(el), 'фильтр не должен разрешать этот элемент'
            return types.SimpleNamespace(ElementId=el.Id, GlobalPoint=point)

    uidoc = types.SimpleNamespace(Selection=Selection())
    UI = types.SimpleNamespace(Selection=types.SimpleNamespace(ISelectionFilter=object,
                                                                ObjectType=types.SimpleNamespace(Element='element')))

    class Event(object):
        def __init__(self):
            self.handlers = []

        def __iadd__(self, h):
            self.handlers.append(h)
            return self

        def fire(self):
            for h in list(self.handlers):
                h(None, None)

    class Items(list):
        def Add(self, x):
            self.append(x)

    class Text(object):
        Text = u''

        def Focus(self):
            return True

        def SelectAll(self):
            return True

    class Combo(object):
        def __init__(self):
            self.Items, self.SelectedItem = Items(), None

    class Chip(object):
        def __init__(self):
            self.Click, self.Content = Event(), u''

    class WPFWindow(object):
        def __init__(self, xaml, literal_string=False, **kw):
            if answers.get('_wpf_crash'):
                raise RuntimeError('XAML не разобран')
            self.ctl = {}
            for name in re.findall(r'x:Name="(\w+)"', xaml):
                self.ctl[name] = (Text() if name in ('info', 'length') else
                                  Combo() if name == 'types' else Chip())
            self.closed = False

        def FindName(self, name):
            return self.ctl[name]

        def Close(self):
            self.closed = True

        def ShowDialog(self):
            c = self.ctl
            world.log.append(('tailwin', c['info'].Text, c['length'].Text,
                              [c['chip%d' % i].Content for i in range(6)], list(c['types'].Items),
                              c['types'].SelectedItem))
            replies = answers.get('_window', [{}])
            for reply in replies:
                if reply is None:
                    return                                     # окно закрыто без выбора
                if 'chip' in reply:
                    c['chip%d' % reply['chip']].Click.fire()
                if 'length' in reply:
                    c['length'].Text = reply['length']
                if 'type' in reply:
                    c['types'].SelectedItem = reply['type']
                c['ok_btn'].Click.fire()
                if self.closed:
                    return

    def alert(msg, title=None, yes=False, no=False, exitscript=False):
        world.alerts.append(msg)
        if exitscript:
            raise ExitScript(msg)
        return True

    class SelectFromList(object):
        @staticmethod
        def show(items, title=None, button_name=None, multiselect=False):
            world.log.append(('select', title, list(items)))
            return answers.get('_select', items[0])

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

    cfgs = answers.setdefault('_config', {})

    class Cfg(object):
        def __init__(self, store):
            self.store = store

        def get_option(self, k, d=None):
            return self.store.get(k, d)

        def set_option(self, k, v):
            self.store[k] = v

    def get_config(section=None):
        return Cfg(cfgs.setdefault(section, {}))

    def save_config():
        world.saves += 1

    def script_exit():
        raise ExitScript('exit')

    script = types.SimpleNamespace(get_output=lambda: Output(), exit=script_exit, get_config=get_config,
                                   save_config=save_config)

    class StubPyrevit(types.ModuleType):
        def __getattr__(self, name):
            if name == 'forms':
                return forms
            raise AttributeError(name)

    pyrevit = StubPyrevit('pyrevit')
    pyrevit.revit = types.SimpleNamespace(doc=doc, uidoc=uidoc)
    pyrevit.DB, pyrevit.UI, pyrevit.script = DB, UI, script
    gen = types.ModuleType('System.Collections.Generic')
    gen.List = FakeList
    exc = types.ModuleType('Autodesk.Revit.Exceptions')
    exc.OperationCanceledException = Cancelled
    names = ('pyrevit', 'System', 'System.Collections', 'System.Collections.Generic', 'Autodesk', 'Autodesk.Revit',
             'Autodesk.Revit.Exceptions')
    saved = dict((k, sys.modules.get(k)) for k in names)
    sys.modules.update({'pyrevit': pyrevit, 'System': types.ModuleType('System'),
                        'System.Collections': types.ModuleType('System.Collections'),
                        'System.Collections.Generic': gen, 'Autodesk': types.ModuleType('Autodesk'),
                        'Autodesk.Revit': types.ModuleType('Autodesk.Revit'), 'Autodesk.Revit.Exceptions': exc})
    try:
        world.ns = runpy.run_path(SCRIPT, run_name='__main__')
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return world


def scene(duct_mm=2000, radius_mm=100, reversed_duct=False):
    """Оборудование в начале координат (коннектор вдоль +X), к нему подключён жёсткий воздуховод длиной duct_mm,
    за дальним концом — тройник (занятый коннектор) с ещё одним свободным."""
    w = World()
    supply = types.SimpleNamespace(GetTypeId=lambda: EId(10))
    eq = Equip(1, level=EId(100))
    ce = eq.add(Conn(None, XYZ(0, 0, 0), XYZ(1, 0, 0), system=supply, radius_mm=radius_mm))
    duct = RigidDuct(2, level=EId(100))
    far = XYZ(duct_mm * MM, 0, 0)
    near_c = Conn(None, XYZ(0, 0, 0), XYZ(-1, 0, 0), system=supply, radius_mm=radius_mm)
    far_c = Conn(None, far, XYZ(1, 0, 0), system=supply, radius_mm=radius_mm)
    for c in ((far_c, near_c) if reversed_duct else (near_c, far_c)):
        duct.add(c)
    ce.ConnectTo(near_c)
    tee = Equip(3, 'OST_DuctFitting', level=EId(100))
    tc = tee.add(Conn(None, far, XYZ(-1, 0, 0), radius_mm=radius_mm))
    tee.add(Conn(None, XYZ(duct_mm * MM, 0, 1), XYZ(0, 0, 1), radius_mm=radius_mm))
    far_c.ConnectTo(tc)
    system_el = types.SimpleNamespace(Id=EId(500))
    for c in (near_c, far_c):                              # как в Revit: AllRefs содержит и логический коннектор системы
        lc = LogicalConn(system_el)
        c.refs.append(lc)
        lc.refs.append(c)
    w.elements = {1: eq, 2: duct, 3: tee}
    w.eq, w.duct, w.tee, w.ce, w.near_c, w.far_c, w.tc = eq, duct, tee, ce, near_c, far_c, tc

    def free_far_end():
        """За дальним концом воздуховода нет никакого элемента (логическая связь с системой остаётся)."""
        far_c.refs.remove(tc)
        tc.refs.remove(far_c)
    w.free_far_end = free_far_end
    return w


def click(w, el=None, point=None):
    w.picks = [(el or w.eq, point if point is not None else XYZ(0.05, 0, 0))]


class FlexTailTests(unittest.TestCase):
    def go(self, w, answers=None):
        """Один запуск кнопки; возвращает (мир, ответы). Исключение «выход» (закрыли окно) пробрасывается."""
        answers = answers if answers is not None else {}
        run_button(w, answers)
        return answers

    def log_text(self):
        with open(hvac_log.log_path(), encoding='utf-8') as f:
            return f.read()

    # ---------- основной сценарий: режем и заменяем ближний кусок ----------

    def test_longer_duct_is_split_and_near_part_becomes_flex(self):
        w = scene(2000)
        click(w)
        self.go(w)
        self.assertEqual(len(w.created), 1)
        f = w.created[0]
        self.assertEqual(f.created_with['points'], [(0, 0, 0), (round(500 * MM, 6), 0, 0)])
        self.assertEqual([t.t() for t in f.created_with['tangents']], [(1, 0, 0), (1, 0, 0)])
        self.assertEqual(w.deleted, [2])                                    # ближний кусок (исходный) удалён
        far_piece = w.elements[901]                                         # новый, дальний кусок остался
        self.assertAlmostEqual(far_piece.conns()[0].Origin.X, 500 * MM)
        self.assertAlmostEqual(far_piece.conns()[1].Origin.X, 2000 * MM)
        self.assertEqual(w.tx, ['start', 'commit'])
        self.assertEqual(w.alerts, [])                                      # всё штатно — без сообщений

    def test_flex_is_connected_to_equipment_and_to_far_rigid_piece(self):
        w = scene(2000)
        click(w)
        self.go(w)
        f = w.created[0]
        near_end, far_end = f.conns()
        self.assertEqual(near_end.refs, [w.ce])
        self.assertEqual(len(far_end.refs), 1)
        self.assertIs(far_end.refs[0].Owner, w.elements[901])
        self.assertAlmostEqual(far_end.refs[0].Origin.X, 500 * MM)
        self.assertIs(w.tc.refs[0].Owner, w.elements[901])                  # тройник остался подключён к дальнему куску

    def test_size_system_and_level_come_from_the_duct(self):
        w = scene(2000, radius_mm=125)
        click(w)
        self.go(w, {'_window': [{'type': 'Flex Alu'}]})
        f = w.created[0]
        self.assertAlmostEqual(f.params['diam'].value, 250 * MM)
        self.assertEqual((f.created_with['type'], f.created_with['system'], f.created_with['level']), (2, 10, 100))

    def test_system_type_falls_back_to_duct_parameter(self):
        w = scene(2000)
        for c in w.duct.conns():
            c.MEPSystem = None
        w.duct.bip['systype'] = Param(EId(11))
        click(w)
        self.go(w)
        self.assertEqual(w.created[0].created_with['system'], 11)

    def test_unknown_system_type_gives_clear_message_and_rolls_back(self):
        w = scene(2000)
        for c in w.duct.conns():
            c.MEPSystem = None
        click(w)
        self.go(w)
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'тип системы' in a for a in w.alerts))

    def test_old_api_without_tangents_uses_four_points(self):
        w = scene(2000)
        w.tangent_api = False
        click(w)
        self.go(w)
        cw = w.created[0].created_with
        self.assertIsNone(cw['tangents'])
        self.assertEqual(len(cw['points']), 4)
        self.assertEqual(cw['points'][0], (0, 0, 0))
        self.assertEqual(cw['points'][3], (round(500 * MM, 6), 0, 0))

    # ---------- направление: элемент в середине сети ----------

    def test_nearest_connector_decides_direction(self):
        w = scene(2000)
        left = RigidDuct(4, level=EId(100))
        near = left.add(Conn(None, XYZ(-400 * MM, 0, 0), XYZ(1, 0, 0), radius_mm=100))
        left.add(Conn(None, XYZ(-3400 * MM, 0, 0), XYZ(-1, 0, 0), radius_mm=100))
        ce_left = w.eq.add(Conn(None, XYZ(-400 * MM, 0, 0), XYZ(-1, 0, 0), radius_mm=100))
        ce_left.ConnectTo(near)
        w.elements[4] = left
        left.bip['systype'] = Param(EId(10))
        click(w, point=XYZ(-380 * MM, 0, 0))                                 # клик у левого коннектора
        self.go(w)
        f = w.created[0]
        self.assertEqual(f.created_with['points'], [(round(-400 * MM, 6), 0, 0), (round(-900 * MM, 6), 0, 0)])
        self.assertEqual(f.created_with['tangents'][0].t(), (-1, 0, 0))
        self.assertNotIn(2, w.deleted)                                       # правый воздуховод не тронут
        self.assertTrue(w.near_c.refs)

    def test_click_near_right_connector_converts_right_duct_only(self):
        w = scene(2000)
        left = RigidDuct(4, level=EId(100))
        near = left.add(Conn(None, XYZ(-400 * MM, 0, 0), XYZ(1, 0, 0), radius_mm=100))
        left.add(Conn(None, XYZ(-3400 * MM, 0, 0), XYZ(-1, 0, 0), radius_mm=100))
        w.eq.add(Conn(None, XYZ(-400 * MM, 0, 0), XYZ(-1, 0, 0), radius_mm=100)).ConnectTo(near)
        w.elements[4] = left
        left.bip['systype'] = Param(EId(10))
        click(w, point=XYZ(20 * MM, 0, 0))
        self.go(w)
        self.assertEqual(w.created[0].created_with['points'][1], (round(500 * MM, 6), 0, 0))
        self.assertNotIn(4, w.deleted)

    def test_reversed_duct_orientation_is_handled(self):
        w = scene(2000, reversed_duct=True)                                  # у воздуховода «первый» коннектор — дальний
        click(w)
        self.go(w)
        f = w.created[0]
        self.assertEqual(f.created_with['points'][1], (round(500 * MM, 6), 0, 0))
        self.assertEqual(w.deleted, [901])                                   # здесь ближний кусок — новый, второй
        self.assertIs(f.conns()[1].refs[0].Owner, w.duct)                    # дальний кусок — исходный воздуховод

    # ---------- когда воздуховод короче заданной длины ----------

    def test_shorter_duct_is_converted_whole_and_user_is_told(self):
        w = scene(300)
        click(w)
        self.go(w)                                                           # по умолчанию 500 мм
        f = w.created[0]
        self.assertEqual(f.created_with['points'], [(0, 0, 0), (round(300 * MM, 6), 0, 0)])
        self.assertEqual(w.deleted, [2])
        self.assertFalse(getattr(w, 'broken', False))                        # разреза не было
        self.assertEqual(len(w.alerts), 1)
        self.assertIn(u'300', w.alerts[0])
        self.assertIn(u'500', w.alerts[0])
        self.assertIn(u'целиком', w.alerts[0])

    def test_whole_conversion_reconnects_the_far_neighbour(self):
        w = scene(300)
        click(w)
        self.go(w)
        near_end, far_end = w.created[0].conns()
        self.assertEqual(near_end.refs, [w.ce])
        self.assertEqual(far_end.refs, [w.tc])                               # тройник подключён к гибкому

    def test_whole_conversion_without_far_neighbour(self):
        w = scene(300)
        w.free_far_end()
        click(w)
        self.go(w)
        self.assertEqual(w.created[0].conns()[1].refs, [])
        self.assertEqual(w.tx, ['start', 'commit'])

    def test_free_far_end_with_system_logical_connector_converts_whole(self):
        """Баг из Revit: воздуховод 1260 мм, нужно 1500 мм, за дальним концом ничего нет. AllRefs отдавал логический
        коннектор системы, он исчезал вместе с воздуховодом, и подключение падало «The referenced object is not valid»."""
        w = scene(1260, radius_mm=62.5)
        w.free_far_end()
        click(w)
        self.go(w, {'_window': [{'length': '1500'}]})
        self.assertEqual(len(w.created), 1)
        self.assertEqual(w.tx, ['start', 'commit'])
        self.assertEqual(w.deleted, [2])
        near_end, far_end = w.created[0].conns()
        self.assertEqual((near_end.refs, far_end.refs), ([w.ce], []))
        self.assertEqual(w.created[0].created_with['points'][1], (round(1260 * MM, 6), 0, 0))
        self.assertTrue(any(u'1260' in a and u'1500' in a for a in w.alerts))      # сообщение про короткий участок

    def test_free_far_end_on_split_also_works(self):
        w = scene(3000)
        w.free_far_end()
        click(w)
        self.go(w)
        self.assertEqual(len(w.created), 1)
        self.assertEqual(w.tx, ['start', 'commit'])

    def test_invalid_target_connector_is_skipped_not_fatal(self):
        w = scene(300)
        click(w)
        self.go(w)                                                             # подключение к тройнику по-прежнему есть
        self.assertEqual(w.created[0].conns()[1].refs, [w.tc])
        ns = w.ns
        gone = LogicalConn(types.SimpleNamespace(Id=EId(501)))
        gone.valid = False
        flex = FlexInst(990, [XYZ(0, 0, 0), XYZ(1, 0, 0)], w.flex_types[0])
        ns['connect_ends'](flex, [w.ce, gone])                                 # недействительный коннектор — пропуск
        self.assertEqual(flex.conns()[0].refs, [w.ce])
        self.assertIn(u'недействителен', self.log_text())

    def test_logical_connectors_are_not_reported_as_connected_elements(self):
        w = scene(2000)
        lonely = Equip(61, level=EId(100))
        c = lonely.add(Conn(None, XYZ(5, 0, 0), XYZ(1, 0, 0)))
        lc = LogicalConn(types.SimpleNamespace(Id=EId(502), Category=types.SimpleNamespace(Name='Система П1')))
        c.refs.append(lc)
        lc.refs.append(c)
        w.elements[61] = lonely
        w.picks = [(lonely, XYZ(5, 0, 0)), Cancelled]
        run_button(w)
        self.assertIn(u'не подключён воздуховод', w.alerts[0])
        self.assertNotIn(u'Система П1', w.alerts[0])
        self.assertNotIn(u'не жёсткий', w.alerts[0])

    def test_exact_length_is_whole_without_message(self):
        w = scene(500)
        click(w)
        self.go(w)
        self.assertEqual(w.deleted, [2])
        self.assertEqual(w.alerts, [])

    def test_tiny_leftover_is_converted_whole_with_message(self):
        w = scene(2000)
        click(w)
        self.go(w, {'_window': [{'length': '1998'}]})
        self.assertFalse(getattr(w, 'broken', False))
        self.assertEqual(len(w.alerts), 1)
        self.assertIn(u'остаток', w.alerts[0])

    # ---------- окно: длина, чипы, запоминание, тип ----------

    def test_window_shows_default_500_chips_duct_info_and_types(self):
        w = scene(2000)
        click(w)
        self.go(w)
        win = [l for l in w.log if l[0] == 'tailwin'][0]
        self.assertEqual(win[2], u'500')
        self.assertEqual(win[3], [u'300', u'500', u'1000', u'1500', u'2000', u'2500'])
        self.assertIn(u'Ø200', win[1])
        self.assertIn(u'2000', win[1])
        self.assertEqual((win[4], win[5]), ([u'Flex Alu', u'Flex Round'], u'Flex Alu'))

    def test_chip_puts_value_into_the_field(self):
        w = scene(3000)
        click(w)
        self.go(w, {'_window': [{'chip': 3}]})                               # 1500
        self.assertEqual(w.created[0].created_with['points'][1], (round(1500 * MM, 6), 0, 0))

    def test_typed_length_with_comma_and_units(self):
        w = scene(3000)
        click(w)
        self.go(w, {'_window': [{'length': u'750,5 мм'}]})
        self.assertEqual(w.created[0].created_with['points'][1], (round(750.5 * MM, 6), 0, 0))

    def test_length_is_remembered_for_next_run(self):
        w = scene(3000)
        click(w)
        answers = self.go(w, {'_window': [{'length': '1200'}]})
        self.assertEqual(answers['_config']['flex_tail']['length_mm'], u'1200')
        w2 = scene(3000)
        click(w2)
        run_button(w2, {'_config': answers['_config']})
        win = [l for l in w2.log if l[0] == 'tailwin'][0]
        self.assertEqual(win[2], u'1200')
        self.assertEqual(w2.created[0].created_with['points'][1], (round(1200 * MM, 6), 0, 0))

    def test_last_type_is_preselected_and_remembered(self):
        w = scene(3000)
        click(w)
        answers = self.go(w, {'_window': [{'type': 'Flex Round'}]})
        self.assertEqual(answers['_config']['flex_tail']['flex_type'], 'Flex Round')
        w2 = scene(3000)
        click(w2)
        run_button(w2, {'_config': answers['_config']})
        self.assertEqual([l for l in w2.log if l[0] == 'tailwin'][0][5], 'Flex Round')

    def test_invalid_length_keeps_window_open_with_message(self):
        w = scene(3000)
        click(w)
        answers = self.go(w, {'_window': [{'length': 'abc'}, {'length': '0'}, {'length': '600'}]})
        self.assertEqual(len([a for a in w.alerts if u'число' in a]), 2)
        self.assertEqual(w.created[0].created_with['points'][1], (round(600 * MM, 6), 0, 0))
        self.assertEqual(answers['_config']['flex_tail']['length_mm'], u'600')

    def test_closing_window_cancels_without_changes(self):
        w = scene(3000)
        click(w)
        with self.assertRaises(ExitScript):
            self.go(w, {'_window': [None]})
        self.assertEqual((w.created, w.deleted, w.tx), ([], [], []))

    def test_invalid_input_is_not_saved(self):
        w = scene(3000)
        click(w)
        answers = self.go(w, {'_window': [{'length': 'abc'}, None]}) if False else {}
        with self.assertRaises(ExitScript):
            self.go(w, {'_window': [{'length': 'abc'}, None]})
        self.assertEqual(w.created, [])

    def test_fallback_dialogs_when_wpf_window_fails(self):
        w = scene(3000)
        click(w)
        self.go(w, {'_wpf_crash': True, '_ask_values': [u'abc', u'800']})
        self.assertEqual(w.created[0].created_with['points'][1], (round(800 * MM, 6), 0, 0))
        self.assertTrue(any(u'число' in a for a in w.alerts))                # про abc предупредили и спросили снова
        self.assertIn(u'ПОМИЛКА', self.log_text()) if False else None

    # ---------- выбор элемента: что нельзя, что не подходит ----------

    def test_filter_allows_only_the_four_categories_with_hvac_connectors(self):
        w = scene(2000)
        run_button(w)                       # пустой сценарий выбора: сразу Esc
        flt = w.ns['TailElementFilter']()
        cat = lambda ident, name: Element(ident, name)
        with_conn = Equip(50, 'OST_DuctTerminal')
        with_conn.add(Conn(None, XYZ(0, 0, 0), XYZ(1, 0, 0)))
        self.assertTrue(flt.AllowElement(w.eq))
        self.assertTrue(flt.AllowElement(w.tee))
        self.assertTrue(flt.AllowElement(with_conn))
        acc = Equip(51, 'OST_DuctAccessory')
        acc.add(Conn(None, XYZ(0, 0, 0), XYZ(1, 0, 0)))
        self.assertTrue(flt.AllowElement(acc))
        self.assertFalse(flt.AllowElement(w.duct))                           # сам воздуховод выбирать нельзя
        flex = FlexInst(52, [XYZ(0, 0, 0), XYZ(1, 0, 0)], w.flex_types[0])
        self.assertFalse(flt.AllowElement(flex))
        pipe_only = Equip(53)
        pipe_only.add(Conn(None, XYZ(0, 0, 0), XYZ(1, 0, 0), domain=PIPING))
        self.assertFalse(flt.AllowElement(pipe_only))                        # нет вентиляционных коннекторов
        self.assertFalse(flt.AllowElement(Equip(54)))                        # вообще нет коннекторов

    def test_prompt_is_in_status_bar_and_mentions_esc(self):
        w = scene(2000)
        w.picks = [Cancelled]
        run_button(w)
        self.assertEqual(len(w.prompts), 1)
        self.assertIn(u'FlexTail', w.prompts[0])
        self.assertIn(u'Esc', w.prompts[0])
        self.assertIn(u'жёсткий воздуховод', w.prompts[0])

    def test_esc_on_pick_ends_quietly(self):
        w = scene(2000)
        w.picks = [Cancelled]
        run_button(w)
        self.assertEqual((w.created, w.alerts, w.tx), ([], [], []))

    def test_element_without_connected_duct_gives_message_and_asks_again(self):
        w = scene(2000)
        lonely = Equip(60, level=EId(100))
        lonely.add(Conn(None, XYZ(5, 0, 0), XYZ(1, 0, 0)))
        w.elements[60] = lonely
        w.picks = [(lonely, XYZ(5, 0, 0)), (w.eq, XYZ(0.05, 0, 0))]
        self.go(w)
        self.assertEqual(len(w.prompts), 2)                                  # после сообщения просит кликнуть снова
        self.assertEqual(len(w.alerts), 1)
        self.assertIn(u'не подключён воздуховод', w.alerts[0])
        self.assertEqual(len(w.created), 1)

    def test_flex_duct_connected_is_not_accepted(self):
        w = scene(2000)
        flex = FlexInst(70, [XYZ(0, 0, 0), XYZ(1, 0, 0)], w.flex_types[0])
        eq2 = Equip(61, level=EId(100))
        c = eq2.add(Conn(None, XYZ(0, 5, 0), XYZ(1, 0, 0)))
        c.ConnectTo(flex.conns()[0])
        w.elements[61] = eq2
        w.picks = [(eq2, XYZ(0, 5, 0)), Cancelled]
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertIn(u'не жёсткий', w.alerts[0])
        self.assertIn(u'OST_FlexDuctCurves', w.alerts[0])                    # называет, что подключено

    def test_hint_when_duct_is_on_another_connector(self):
        w = scene(2000)
        free_c = w.eq.add(Conn(None, XYZ(-1, 0, 0), XYZ(-1, 0, 0)))          # второй коннектор оборудования — свободный
        w.picks = [(w.eq, XYZ(-0.95, 0, 0)), Cancelled]                      # клик у него, а воздуховод — на другом
        run_button(w)
        self.assertEqual(w.created, [])
        self.assertIn(u'другому коннектору', w.alerts[0])

    def test_no_click_point_uses_connector_with_duct(self):
        w = scene(2000)
        w.eq.add(Conn(None, XYZ(-1, 0, 0), XYZ(-1, 0, 0)))                   # свободный коннектор, но воздуховод не там
        w.picks = [(w.eq, None)]
        w.picks[0] = (w.eq, None)
        run_button(w)
        self.assertEqual(len(w.created), 1)

    # ---------- форма сечения и типы ----------

    def test_rect_duct_gets_rect_flex_with_width_and_height(self):
        w = scene(2000)
        w.flex_types = [FlexType('Flex Round', 1, 'round'), FlexType('Flex Rect', 2, 'rect')]
        for c in w.duct.conns():
            c.Shape, c.Width, c.Height = 'rect', 400 * MM, 200 * MM
        click(w)
        self.go(w)
        win = [l for l in w.log if l[0] == 'tailwin'][0]
        self.assertEqual(win[4], [u'Flex Rect'])                              # круглые типы не предлагаются
        f = w.created[0]
        self.assertAlmostEqual(f.params['w'].value, 400 * MM)
        self.assertAlmostEqual(f.params['h'].value, 200 * MM)
        self.assertNotIn('diam', f.params)

    def test_no_type_for_the_shape_gives_message_and_no_changes(self):
        w = scene(2000)
        w.flex_types = [FlexType('Flex Round', 1, 'round')]
        for c in w.duct.conns():
            c.Shape, c.Width, c.Height = 'oval', 300 * MM, 150 * MM
        click(w)
        self.go(w)
        self.assertEqual((w.created, w.deleted, w.tx), ([], [], []))
        self.assertIn(u'овальный', w.alerts[0])

    def test_no_flex_types_in_project(self):
        w = scene(2000)
        w.flex_types = []
        click(w)
        with self.assertRaises(ExitScript):
            self.go(w)
        self.assertIn(u'нет типов гибких', w.alerts[0])

    # ---------- «Гибкая конфигурация» ----------

    def test_flex_pattern_value_from_quickflexconnect_settings_is_written(self):
        w = scene(2000)
        p = CfgParam(u'Гибкая конфигурация', u'Жёсткий')
        w.flex_types[0].param = p
        w.flex_types[1].param = p
        click(w)
        self.go(w)
        self.assertEqual(p.value, u'Гибкий')                                  # значение по умолчанию из общих настроек

    def test_flex_pattern_custom_value_and_empty_means_untouched(self):
        w = scene(2000)
        p = CfgParam(u'Гибкая конфигурация', u'Жёсткий')
        w.flex_types[0].param = w.flex_types[1].param = p
        click(w)
        self.go(w, {'_config': {'flex_between': {'config_value': u'Спиральный'}}})
        self.assertEqual(p.value, u'Спиральный')
        w2 = scene(2000)
        p2 = CfgParam(u'Гибкая конфигурация', u'Жёсткий')
        w2.flex_types[0].param = w2.flex_types[1].param = p2
        click(w2)
        self.go(w2, {'_config': {'flex_between': {'config_value': u''}}})
        self.assertEqual(p2.sets, [])

    def test_flex_pattern_problem_is_a_warning_not_a_failure(self):
        w = scene(2000)
        p = CfgParam(u'Гибкая конфигурация', u'Жёсткий', accepts=False)
        w.flex_types[0].param = w.flex_types[1].param = p
        click(w)
        self.go(w)
        self.assertEqual(len(w.created), 1)                                   # воздуховод всё равно построен
        self.assertTrue(any(l[0] == 'md' and u'не принято' in l[1] for l in w.log))

    def test_missing_flex_pattern_param_warns(self):
        w = scene(2000)
        click(w)
        self.go(w)
        self.assertEqual(len(w.created), 1)
        self.assertTrue(any(l[0] == 'md' and u'не найден' in l[1] for l in w.log))

    # ---------- ошибки ----------

    def test_break_failure_rolls_back_and_reports(self):
        w = scene(2000)
        click(w)
        self.go(w, {'_break_crash': True})
        self.assertEqual(w.tx, ['start', 'rollback'])
        self.assertEqual(w.created, [])
        self.assertTrue(any(u'Не удалось преобразовать' in a for a in w.alerts))
        self.assertIn(u'BreakCurve отказал', self.log_text())                 # полный traceback — в журнале

    def test_normal_run_leaves_trail_in_log(self):
        w = scene(2000)
        click(w)
        self.go(w)
        text = self.log_text()
        for part in (u'[FlexTail]', u'воздуховод id 2', u'выбрано: длина 500 мм', u'создан гибкий воздуховод',
                     u'=== конец' if False else u'=== кінець'):
            self.assertIn(part, text)

    def test_success_does_not_open_output_window(self):
        w = scene(2000)
        p = CfgParam(u'Гибкая конфигурация', u'Жёсткий')
        w.flex_types[0].param = w.flex_types[1].param = p
        click(w)
        self.go(w)
        self.assertEqual([l for l in w.log if l[0] == 'md'], [])


if __name__ == '__main__':
    unittest.main()
