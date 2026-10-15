# -*- coding: utf-8 -*-
__title__ = u'Гнучкий\nміж конекторами'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'Обираєте два елементи (повітровод, арматуру, фасонну частину, обладнання) — між їхніми найближчими вільними '
           u'конекторами будується гнучкий повітровод '
           u'обраного типу (тип обирається після натискання кнопки), кінці з\'єднуються з конекторами. '
           u'Shift+клік — вікно налаштувань: параметр «Гибкая конфигурация» (за замовчуванням «Гибкий») '
           u'і галочка «Цикл» (за замовчуванням вимкнено).')

# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
import uuid

import os
import sys

# Папка lib розширення (HVAC.extension/lib). Зазвичай pyRevit додає її сам; додаємо явно про всяк випадок.
try:
    _LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
except Exception:
    _LIB = u'?'
try:
    import hvac_log
except ImportError:
    from pyrevit import forms
    forms.alert(u'Не знайдено файл lib\\hvac_log.py.\nСкопіюйте в розширення ВСЮ папку HVAC.extension разом із lib '
                u'(усі файли) і перезавантажте pyRevit.\n\nШукав тут: {0}'.format(_LIB),
                title=u'HVAC', exitscript=True)
TOOL = 'flex_between'

try:
    from pyrevit import revit, DB, UI, forms, script
    from System.Collections.Generic import List
    from Autodesk.Revit.Exceptions import OperationCanceledException

    import hvac_flex_settings
    import hvac_revit
except Exception:
    hvac_log.log_exception(TOOL, u'імпорт модулів')
    raise

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

MIN_LEN_FT = 1.0 / 10.0 / 12.0       # Revit не будує MEP-криві коротші за 1/10 дюйма
BEND_FACTOR = 0.3                    # «виліт» кривої від конектора (частка відстані) у запасному варіанті
BEND_MIN_FT = 0.3
CONFIG_SECTION = 'flex_between'

# Які елементи можна вибирати (назви BuiltInCategory). Потрібне додайте, зайве приберіть.
ALLOWED_CATEGORIES = [
    u'OST_DuctCurves',            # повітроводи
    u'OST_DuctAccessory',         # арматура повітроводів
    u'OST_DuctFitting',           # фасонні частини повітроводів
    u'OST_MechanicalEquipment',   # обладнання
    # u'OST_DuctTerminal',        # повітророзподільники — розкоментуйте, якщо потрібні
]


def eid_int(eid):
    """Числове значення ElementId (у нових версіях Revit — .Value, у старих — .IntegerValue)."""
    try:
        return eid.Value
    except AttributeError:
        return eid.IntegerValue


def type_name(t):
    return hvac_revit.element_name(DB, t)


def category_name(el):
    try:
        return el.Category.Name
    except Exception:
        return u'?'


def type_label(el):
    try:
        return type_name(doc.GetElement(el.GetTypeId()))
    except Exception:
        return u'?'


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


def allowed_category_values():
    values = set()
    for name in ALLOWED_CATEGORIES:
        if hasattr(DB.BuiltInCategory, name):
            values.add(int(getattr(DB.BuiltInCategory, name)))
    return values


def is_allowed_category(el):
    try:
        cat = el.Category
        return cat is not None and eid_int(cat.Id) in allowed_category_values()
    except Exception:
        return False


class DuctElementFilter(UI.Selection.ISelectionFilter):
    """Дозволяє вибрати лише повітроводи, арматуру, фасонні частини й обладнання з вільним вентиляційним конектором."""

    # CPython-рушій pyRevit (pythonnet 3): клас, що реалізує .NET-інтерфейс, потребує __namespace__,
    # причому щоразу нового (інакше «Duplicate type name» при повторному запуску). У IronPython це просто атрибут.
    __namespace__ = 'HvacFlex_' + uuid.uuid4().hex

    def AllowElement(self, e):
        try:
            return is_allowed_category(e) and len(free_connectors(e)) > 0
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


def pick_element(prompt):
    """Вибір цілого елемента (клік будь-де на ньому)."""
    ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, DuctElementFilter(), prompt)
    return doc.GetElement(ref.ElementId)


def closest_pair(el0, el1):
    """Пара вільних конекторів (з першого й другого елемента) з найменшою відстанню між ними."""
    free0, free1 = free_connectors(el0), free_connectors(el1)
    if not free0 or not free1:
        return None
    return min(((a, b) for a in free0 for b in free1), key=lambda p: p[0].Origin.DistanceTo(p[1].Origin))


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
        flex = DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, z0, z1.Negate(), pts)
        hvac_log.log(TOOL, u'FlexDuct.Create: варіант з дотичними')
        return flex
    except TypeError as ex:
        hvac_log.log(TOOL, u'FlexDuct.Create з дотичними недоступний ({0}), пробую 4 точки'.format(ex))
    # Запасний варіант: проміжні точки задають вихід по нормалі з обох конекторів.
    k = max(dist * BEND_FACTOR, BEND_MIN_FT)
    pts = List[DB.XYZ]()
    pts.Add(p0)
    pts.Add(p0.Add(z0.Multiply(k)))
    pts.Add(p1.Add(z1.Multiply(k)))
    pts.Add(p1)
    flex = DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, pts)
    hvac_log.log(TOOL, u'FlexDuct.Create: варіант з 4 точками')
    return flex


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


def param_text(p):
    """Поточне значення параметра текстом (для порівняння й журналу)."""
    try:
        if p.StorageType == DB.StorageType.String:
            return p.AsString() or u''
        return p.AsValueString() or u''
    except Exception:
        return u''


def set_param_text(p, value):
    """Записати значення з тексту; повертає True, якщо вдалося."""
    st = p.StorageType
    if st == DB.StorageType.String:
        return bool(p.Set(value))
    if st == DB.StorageType.Integer:
        try:
            return bool(p.Set(int(value)))
        except ValueError:
            return bool(p.SetValueString(value))
    if st == DB.StorageType.Double:
        return bool(p.SetValueString(value))
    return False            # ElementId та інше — не підтримуємо


def dump_parameter_names(flex, type_el):
    """У журнал: які параметри є в екземплярі й типі — щоб було видно, як насправді називається потрібний."""
    for label, el in ((u'екземпляр', flex), (u'тип', type_el)):
        try:
            names = sorted(p.Definition.Name for p in el.Parameters)
            hvac_log.log(TOOL, u'параметри ({0}): {1}'.format(label, u'; '.join(names)))
        except Exception as ex:
            hvac_log.log(TOOL, u'параметри ({0}) не прочитано: {1}'.format(label, ex))


def apply_config_param(flex, state):
    """Записати «Гибкая конфигурация» у щойно створений гнучкий повітровод. Ніколи не ламає побудову."""
    name, value = state['param'], state['value']
    if not value:
        return
    try:
        type_el = doc.GetElement(flex.GetTypeId())
        for label, el in ((u'екземпляр', flex), (u'тип', type_el)):
            p = el.LookupParameter(name)
            if p is None:
                continue
            if p.IsReadOnly:
                hvac_log.log(TOOL, u'параметр «{0}» ({1}) тільки для читання — пропущено'.format(name, label))
                state['warnings'].append(u'Параметр «{0}» тільки для читання.'.format(name))
                return
            before = param_text(p)
            if before == value:
                hvac_log.log(TOOL, u'«{0}» ({1}) вже = «{2}»'.format(name, label, value))
                return
            if set_param_text(p, value):
                hvac_log.log(TOOL, u'«{0}» ({1}): «{2}» → «{3}»'.format(name, label, before, value))
            else:
                hvac_log.log(TOOL, u'«{0}» ({1}): значення «{2}» не прийнято'.format(name, label, value))
                state['warnings'].append(u'Параметр «{0}»: значення «{1}» не прийнято.'.format(name, value))
            return
        hvac_log.log(TOOL, u'параметра «{0}» немає ні в екземплярі, ні в типі'.format(name))
        state['warnings'].append(u'Параметра «{0}» не знайдено (перевірте назву у вікні налаштувань; '
                                 u'список параметрів — у журналі).'.format(name))
        if not state['dumped']:
            state['dumped'] = True
            dump_parameter_names(flex, type_el)
    except Exception as ex:
        hvac_log.log_exception(TOOL, u'запис параметра «{0}»'.format(name))
        state['warnings'].append(u'Не вдалося записати параметр «{0}»: {1}'.format(name, ex))


def build_one(c0, c1, flex_type, system_state):
    system_id = system_type_id_from(c0) or system_type_id_from(c1) or system_state.get('id')
    if system_id is None:
        system_id = pick_system_type_id()
        system_state['id'] = system_id
    level_id = level_id_for(c0)
    if level_id is None:
        raise ValueError(u'У проєкті немає рівнів.')
    hvac_log.log(TOOL, u'побудова: тип {0}, система {1}, рівень {2}, довжина {3:.3f} ft'.format(
        type_name(flex_type), eid_int(system_id), eid_int(level_id), c0.Origin.DistanceTo(c1.Origin)))
    t = DB.Transaction(doc, u'Гнучкий повітровод між конекторами')
    t.Start()
    try:
        flex = create_flex(c0, c1, flex_type.Id, system_id, level_id)
        apply_size(flex, c0)
        apply_config_param(flex, system_state)
        connect_ends(flex, c0, c1)
        t.Commit()
        hvac_log.log(TOOL, u'створено, id {0}'.format(eid_int(flex.Id)))
    except Exception:
        t.RollBack()
        hvac_log.log_exception(TOOL, u'побудова (транзакцію відкотено)')
        raise
    return flex


def main():
    types = flex_types()
    if not types:
        forms.alert(u'У проєкті немає типів гнучких повітроводів.', title=u'Гнучкий повітровод', exitscript=True)
    cfg = script.get_config(CONFIG_SECTION)
    # Тип гнучкого повітровода — вибір після натискання кнопки (останній обраний стоїть першим; один тип — без питання).
    flex_type = choose_from(types, [type_name(t) for t in types], u'Тип гнучкого повітровода:', 'flex_type')
    config_param = hvac_flex_settings.get_config_param(cfg)
    config_value = hvac_flex_settings.get_config_value(cfg)
    # Режим циклу — галочка у вікні налаштувань (Shift+клік), за замовчуванням вимкнено.
    loop = hvac_flex_settings.is_loop(cfg)
    hvac_log.log(TOOL, u'тип «{0}», «{1}» = «{2}», цикл {3}, журнал {4}'.format(
        type_name(flex_type), config_param, config_value, loop, hvac_log.log_path()))
    tail = u'Esc — завершити' if loop else u'Esc — скасувати'
    system_state = {'id': None, 'param': config_param, 'value': config_value, 'warnings': [], 'dumped': False}
    made = 0
    while True:
        try:
            e0 = pick_element(u'Перший елемент: повітровод, арматура, фасонна частина або обладнання ({0})'.format(tail))
            e1 = pick_element(u'Другий елемент ({0})'.format(tail))
        except OperationCanceledException:
            hvac_log.log(TOOL, u'вибір скасовано (Esc)')
            break
        hvac_log.log(TOOL, u'вибрано: {0} «{1}» id {2} і {3} «{4}» id {5}'.format(
            category_name(e0), type_label(e0), eid_int(e0.Id), category_name(e1), type_label(e1), eid_int(e1.Id)))
        if eid_int(e0.Id) == eid_int(e1.Id):
            forms.alert(u'Це той самий елемент. Оберіть два різні.', title=u'Гнучкий повітровод')
            if loop:
                continue
            break
        pair = closest_pair(e0, e1)
        if pair is not None:
            hvac_log.log(TOOL, u'пара конекторів: ({0:.2f}, {1:.2f}, {2:.2f}) → ({3:.2f}, {4:.2f}, {5:.2f})'.format(
                pair[0].Origin.X, pair[0].Origin.Y, pair[0].Origin.Z,
                pair[1].Origin.X, pair[1].Origin.Y, pair[1].Origin.Z))
        if pair is None:
            forms.alert(u'На одному з елементів немає вільних конекторів.', title=u'Гнучкий повітровод')
            if loop:
                continue
            break
        try:
            build_one(pair[0], pair[1], flex_type, system_state)
            made += 1
        except Exception as ex:
            hvac_log.log(TOOL, u'побудова не вдалася: {0}'.format(ex))
            forms.alert(u'Не вдалося побудувати гнучкий повітровод:\n{0}\n\nЖурнал: {1}'.format(ex, hvac_log.log_path()),
                        title=u'Гнучкий повітровод')
        if not loop:
            break
    for w in sorted(set(system_state['warnings'])):
        output.print_md(u'* **Увага:** {0}'.format(w))
    if made:
        output.print_md(u'**Гнучких повітроводів створено: {0}** (тип «{1}»)'.format(made, type_name(flex_type)))


hvac_log.run(TOOL, main, doc)
