# -*- coding: utf-8 -*-
__title__ = u'Гнучкий\nміж конекторами'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'Обираєте два вільні конектори (клік на елементі біля конектора) — між ними будується гнучкий повітровод '
           u'типу з налаштувань (Shift+клік; за замовчуванням «Гибкий»), кінці з\'єднуються з конекторами. '
           u'За замовчуванням будується один повітровод; серія до Esc — кнопка «Цикл».')

# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
from pyrevit import revit, DB, UI, forms, script
from System.Collections.Generic import List
from Autodesk.Revit.Exceptions import OperationCanceledException

import hvac_flex_settings

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

MIN_LEN_FT = 1.0 / 10.0 / 12.0       # Revit не будує MEP-криві коротші за 1/10 дюйма
BEND_FACTOR = 0.3                    # «виліт» кривої від конектора (частка відстані) у запасному варіанті
BEND_MIN_FT = 0.3
CONFIG_SECTION = 'flex_between'


def eid_int(eid):
    """Числове значення ElementId (у нових версіях Revit — .Value, у старих — .IntegerValue)."""
    try:
        return eid.Value
    except AttributeError:
        return eid.IntegerValue


def type_name(t):
    return DB.Element.Name.GetValue(t)


# ---------- конектори ----------

def element_connectors(el):
    """Усі конектори елемента: повітровод/гнучкий (ConnectorManager) або сімейство (MEPModel)."""
    mgr = None
    try:
        mgr = el.ConnectorManager
    except AttributeError:
        mgr = None
    if mgr is None:
        try:
            mep = el.MEPModel
            mgr = mep.ConnectorManager if mep is not None else None
        except AttributeError:
            mgr = None
    return list(mgr.Connectors) if mgr is not None else []


def is_free_hvac(c):
    try:
        return (c.Domain == DB.Domain.DomainHvac and not c.IsConnected
                and c.ConnectorType in (DB.ConnectorType.End, DB.ConnectorType.Physical))
    except Exception:
        return False


def free_connectors(el):
    return [c for c in element_connectors(el) if is_free_hvac(c)]


class FreeHvacConnectorFilter(UI.Selection.ISelectionFilter):
    """Дозволяє клікати лише на елементи, де є вільний вентиляційний конектор."""

    def AllowElement(self, e):
        try:
            return len(free_connectors(e)) > 0
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


def pick_connector(prompt):
    """Клік на елементі → найближчий до точки кліку вільний конектор."""
    ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.PointOnElement, FreeHvacConnectorFilter(), prompt)
    el = doc.GetElement(ref.ElementId)
    pt = ref.GlobalPoint
    free = free_connectors(el)
    if not free:
        return None
    return min(free, key=lambda c: c.Origin.DistanceTo(pt))


# ---------- типи, система, рівень ----------

def flex_types():
    return sorted(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType), key=type_name)


def load_last(key):
    try:
        return script.get_config(CONFIG_SECTION).get_option(key, u'')
    except Exception:
        return u''


def save_last(key, value):
    try:
        cfg = script.get_config(CONFIG_SECTION)
        cfg.set_option(key, value)
        script.save_config()
    except Exception:
        pass


def choose_from(items, names, title, last_key):
    """Список з пам'яттю останнього вибору (останній — зверху). Один елемент — без запиту."""
    if len(items) == 1:
        return items[0]
    last = load_last(last_key)
    order = sorted(range(len(items)), key=lambda i: (names[i] != last, names[i]))
    picked = forms.SelectFromList.show([names[i] for i in order], title=title, button_name=u'Обрати',
                                       multiselect=False)
    if not picked:
        script.exit()
    save_last(last_key, picked)
    return items[names.index(picked)]


def system_type_id_from(connector):
    """Тип системи з системи, до якої вже належить конектор."""
    try:
        sysobj = connector.MEPSystem
    except Exception:
        return None
    if sysobj is None:
        return None
    try:
        return sysobj.GetTypeId()
    except Exception:
        return None


def pick_system_type_id():
    types = sorted(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.MechanicalSystemType), key=type_name)
    if not types:
        forms.alert(u'У проєкті немає типів механічних систем.', title=u'Гнучкий повітровод', exitscript=True)
    names = [type_name(t) for t in types]
    return choose_from(types, names, u'Тип системи для нового гнучкого повітровода:', 'system_type').Id


def level_id_for(connector):
    """Рівень: з елемента-власника конектора, інакше рівень активного виду, інакше найближчий за висотою."""
    owner = connector.Owner
    lid = getattr(owner, 'LevelId', None)
    if lid is not None and eid_int(lid) != -1:
        return lid
    try:
        gl = doc.ActiveView.GenLevel
        if gl is not None:
            return gl.Id
    except Exception:
        pass
    levels = list(DB.FilteredElementCollector(doc).OfClass(DB.Level))
    if not levels:
        return None
    z = connector.Origin.Z
    return min(levels, key=lambda l: abs(l.Elevation - z)).Id


# ---------- побудова ----------

def create_flex(c0, c1, type_id, system_id, level_id):
    p0, p1 = c0.Origin, c1.Origin
    dist = p0.DistanceTo(p1)
    if dist < MIN_LEN_FT:
        raise ValueError(u'Конектори надто близько один до одного (менше 1/10 дюйма).')
    z0 = c0.CoordinateSystem.BasisZ         # напрям виходу з першого конектора
    z1 = c1.CoordinateSystem.BasisZ         # напрям виходу з другого конектора
    # Основний варіант (Revit 2025+): дві точки + дотичні на кінцях.
    pts = List[DB.XYZ]()
    pts.Add(p0)
    pts.Add(p1)
    try:
        return DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, z0, z1.Negate(), pts)
    except TypeError:
        pass            # старіший API без дотичних
    # Запасний варіант: проміжні точки задають вихід по нормалі з обох конекторів.
    k = max(dist * BEND_FACTOR, BEND_MIN_FT)
    pts = List[DB.XYZ]()
    pts.Add(p0)
    pts.Add(p0.Add(z0.Multiply(k)))
    pts.Add(p1.Add(z1.Multiply(k)))
    pts.Add(p1)
    return DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, pts)


def apply_size(flex, connector):
    """Розмір гнучкого повітровода — як у конектора, від якого починаємо."""
    try:
        if connector.Shape == DB.ConnectorProfileType.Round:
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_DIAMETER_PARAM).Set(connector.Radius * 2.0)
        elif connector.Shape == DB.ConnectorProfileType.Rectangular:
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_WIDTH_PARAM).Set(connector.Width)
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_HEIGHT_PARAM).Set(connector.Height)
    except Exception:
        pass            # розмір залишиться за замовчуванням типу — не критично


def connect_ends(flex, c0, c1):
    """З'єднати кінці гнучкого повітровода з конекторами (кожен кінець — з найближчим)."""
    ends = list(flex.ConnectorManager.Connectors)
    for target in (c0, c1):
        mine = min(ends, key=lambda e: e.Origin.DistanceTo(target.Origin))
        mine.ConnectTo(target)
        ends = [e for e in ends if e is not mine]


def build_one(c0, c1, flex_type, system_state):
    system_id = system_type_id_from(c0) or system_type_id_from(c1) or system_state.get('id')
    if system_id is None:
        system_id = pick_system_type_id()
        system_state['id'] = system_id
    level_id = level_id_for(c0)
    if level_id is None:
        raise ValueError(u'У проєкті немає рівнів.')
    t = DB.Transaction(doc, u'Гнучкий повітровод між конекторами')
    t.Start()
    try:
        flex = create_flex(c0, c1, flex_type.Id, system_id, level_id)
        apply_size(flex, c0)
        connect_ends(flex, c0, c1)
        t.Commit()
    except Exception:
        t.RollBack()
        raise
    return flex


def main():
    types = flex_types()
    if not types:
        forms.alert(u'У проєкті немає типів гнучких повітроводів.', title=u'Гнучкий повітровод', exitscript=True)
    cfg = script.get_config(CONFIG_SECTION)
    names = [type_name(t) for t in types]
    # Тип — з налаштувань (Shift+клік по кнопці), за замовчуванням «Гибкий»; немає такого — питаємо зі списку.
    idx = hvac_flex_settings.find_type_index(names, hvac_flex_settings.get_flex_type(cfg))
    if idx is not None:
        flex_type = types[idx]
    else:
        flex_type = choose_from(types, names, u'Тип гнучкого повітровода:', hvac_flex_settings.FLEX_TYPE_KEY)
    # Режим циклу вмикається окремою кнопкою «Цикл» (за замовчуванням вимкнений).
    loop = hvac_flex_settings.is_loop(cfg)
    tail = u'Esc — завершити' if loop else u'Esc — скасувати'
    system_state = {'id': None}
    made = 0
    while True:
        try:
            c0 = pick_connector(u'Перший конектор: клацніть на елементі біля вільного конектора ({0})'.format(tail))
            if c0 is None:
                forms.alert(u'На цьому елементі немає вільних конекторів.', title=u'Гнучкий повітровод')
                if loop:
                    continue
                break
            c1 = pick_connector(u'Другий конектор: клацніть на елементі біля вільного конектора ({0})'.format(tail))
            if c1 is None:
                forms.alert(u'На цьому елементі немає вільних конекторів.', title=u'Гнучкий повітровод')
                if loop:
                    continue
                break
        except OperationCanceledException:
            break
        if eid_int(c0.Owner.Id) == eid_int(c1.Owner.Id) and c0.Id == c1.Id:
            forms.alert(u'Це той самий конектор. Оберіть два різні.', title=u'Гнучкий повітровод')
            if loop:
                continue
            break
        try:
            build_one(c0, c1, flex_type, system_state)
            made += 1
        except Exception as ex:
            forms.alert(u'Не вдалося побудувати гнучкий повітровод:\n{0}'.format(ex), title=u'Гнучкий повітровод')
        if not loop:
            break
    if made:
        output.print_md(u'**Гнучких повітроводів створено: {0}** (тип «{1}»)'.format(made, type_name(flex_type)))


main()
