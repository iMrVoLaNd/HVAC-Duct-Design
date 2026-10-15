# -*- coding: utf-8 -*-
__title__ = u'QuickFlex\nConnect'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'QuickFlexConnect: обираєте два елементи (повітровод, арматуру, фасонну частину, обладнання, повітророзподільник) — між їхніми найближчими вільними '
           u'конекторами будується гнучкий повітровод '
           u'обраного типу (тип обирається після натискання кнопки), кінці з\'єднуються з конекторами. '
           u'Shift+клік — вікно налаштувань: параметр «Гибкая конфигурация» (за замовчуванням «Гибкий») '
           u'і галочка «Цикл» (за замовчуванням вимкнено).')

# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
import os
import sys
import time

_T0 = time.time()        # початок запуску скрипта: щоб у журналі було видно, скільки йде підготовка до першого вибору

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
TOOL = 'QuickFlexConnect'

try:
    from pyrevit import revit, DB, UI, script
    from System.Collections.Generic import List
    from Autodesk.Revit.Exceptions import OperationCanceledException

    import hvac_flex_settings
    import hvac_revit
    import hvac_sizes
except Exception:
    hvac_log.log_exception(TOOL, u'імпорт модулів')
    raise

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()


class _LazyForms(object):
    """pyrevit.forms тягне WPF і коштує десятки-сотні мс; на швидкому шляху (без жодного вікна) він не потрібен —
    вантажимо його лише при першому зверненні."""

    def __getattr__(self, name):
        from pyrevit import forms as real_forms
        return getattr(real_forms, name)


forms = _LazyForms()


def _unique_namespace(prefix):
    """Унікальне __namespace__ для класів, що реалізують .NET-інтерфейс (потрібне CPython-рушію pyRevit). Без модуля
    uuid: його імпорт у IronPython помітно повільний."""
    return u'{0}{1:x}{2:x}'.format(prefix, int(time.time() * 1000000), int.from_bytes(os.urandom(6), 'big'))

MIN_LEN_FT = 1.0 / 10.0 / 12.0       # Revit не будує MEP-криві коротші за 1/10 дюйма
BEND_FACTOR = 0.3                    # «виліт» кривої від конектора (частка відстані) у запасному варіанті
BEND_MIN_FT = 0.3
CONFIG_SECTION = 'flex_between'       # ім'я секції конфігурації лишилось старим, щоб не втратити збережені налаштування

# Які елементи можна вибирати (назви BuiltInCategory). Потрібне додайте, зайве приберіть.
ALLOWED_CATEGORIES = [
    u'OST_DuctCurves',            # повітроводи
    u'OST_DuctAccessory',         # арматура повітроводів
    u'OST_DuctFitting',           # фасонні частини повітроводів
    u'OST_MechanicalEquipment',   # обладнання
    u'OST_DuctTerminal',          # повітророзподільники
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
    """Усі конектори елемента: повітровод (ConnectorManager) або сімейство (MEPModel). Тип визначаємо за класом, а не
    через AttributeError — винятки в IronPython дорогі, а ця функція викликається при кожному русі курсора."""
    mgr = None
    curve_cls = getattr(DB, 'MEPCurve', None)
    family_cls = getattr(DB, 'FamilyInstance', None)
    if curve_cls is not None and isinstance(el, curve_cls):
        mgr = el.ConnectorManager
    elif family_cls is not None and isinstance(el, family_cls):
        mep = el.MEPModel
        mgr = mep.ConnectorManager if mep is not None else None
    else:                                   # невідомий клас (або заглушка): запасний шлях через винятки
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


def hvac_connectors(el):
    """Усі вентиляційні конектори елемента (вільні й зайняті)."""
    result = []
    for c in element_connectors(el):
        try:
            if c.Domain == DB.Domain.DomainHvac:
                result.append(c)
        except Exception:
            pass
    return result


def connector_text(c):
    """Короткий опис конектора для журналу: тип, домен, чи підключений, координати."""
    try:
        o = c.Origin
        return u'{0}/{1}/{2}@({3:.2f}, {4:.2f}, {5:.2f})'.format(
            c.ConnectorType, c.Domain, u'підключений' if c.IsConnected else u'вільний', o.X, o.Y, o.Z)
    except Exception:
        return u'?'


_REJECTED = set()


def note_rejected(e):
    """Елемент дозволеної категорії без вентиляційних конекторів не вибирається: пишемо в журнал (раз на елемент)."""
    try:
        key = eid_int(e.Id)
        if key in _REJECTED or len(_REJECTED) >= 30:
            return
        _REJECTED.add(key)
        hvac_log.log(TOOL, u'елемент відхилено фільтром: {0} id {1}; конектори: {2}'.format(
            category_name(e), key, u'; '.join(connector_text(c) for c in element_connectors(e)) or u'немає'))
    except Exception:
        pass


_ALLOWED_CACHE = []
_ALLOW_CACHE = {}        # id елемента → чи дозволений фільтром вибору


def allowed_category_values():
    """Числові id дозволених категорій; рахуємо один раз (фільтр викликається при кожному русі курсора)."""
    if not _ALLOWED_CACHE:
        values = set()
        for name in ALLOWED_CATEGORIES:
            if hasattr(DB.BuiltInCategory, name):
                values.add(int(getattr(DB.BuiltInCategory, name)))
        _ALLOWED_CACHE.append(values)
    return _ALLOWED_CACHE[0]


def is_allowed_category(el):
    try:
        cat = el.Category
        return cat is not None and eid_int(cat.Id) in allowed_category_values()
    except Exception:
        return False


class DuctElementFilter(UI.Selection.ISelectionFilter):
    """Дозволяє вибрати лише повітроводи, арматуру, фасонні частини, обладнання й повітророзподільники, у яких є
    вентиляційні конектори. Чи вільні вони, перевіряємо вже після кліку — щоб пояснити, а не мовчки не реагувати."""

    # CPython-рушій pyRevit (pythonnet 3): клас, що реалізує .NET-інтерфейс, потребує __namespace__,
    # причому щоразу нового (інакше «Duplicate type name» при повторному запуску). У IronPython це просто атрибут.
    __namespace__ = _unique_namespace('HvacFlex_')

    def AllowElement(self, e):
        # Викликається Revit-ом при кожному русі курсора над елементом: результат кешуємо за id (він не залежить від
        # того, вільні конектори чи ні, тому за час запуску не застаріває).
        try:
            key = eid_int(e.Id)
            cached = _ALLOW_CACHE.get(key)
            if cached is not None:
                return cached
            allowed = False
            if is_allowed_category(e):
                if hvac_connectors(e):
                    allowed = True
                else:
                    note_rejected(e)
            _ALLOW_CACHE[key] = allowed
            return allowed
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


class FlexSampleFilter(UI.Selection.ISelectionFilter):
    """Дозволяє клацнути лише на гнучкий повітровод — з нього беремо тип."""

    __namespace__ = _unique_namespace('HvacFlexSample_')          # див. примітку в DuctElementFilter

    def AllowElement(self, e):
        try:
            cat = e.Category
            return cat is not None and eid_int(cat.Id) == int(DB.BuiltInCategory.OST_FlexDuctCurves)
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


def pick_sample_type(by_name):
    """Клік на гнучкий повітровод у моделі → його тип (елемент з by_name). Esc — None (тоді питаємо зі списку)."""
    try:
        ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, FlexSampleFilter(),
                                         u'QuickFlexConnect · 3/3 — клацніть на гнучкому повітроводі, з якого взяти тип (Esc — обрати зі списку)')
    except OperationCanceledException:
        hvac_log.log(TOOL, u'зразок типу не вибрано (Esc) — вибір зі списку')
        return None
    flex = doc.GetElement(ref.ElementId)
    name = type_name(doc.GetElement(flex.GetTypeId()))
    hvac_log.log(TOOL, u'тип зі зразка в моделі: «{0}»'.format(name))
    if name not in by_name:
        forms.alert(u'Тип «{0}» не знайдено серед типів гнучких повітроводів. Оберіть зі списку.'.format(name),
                    title=u'QuickFlexConnect')
        return None
    return by_name[name]


def pick_element(prompt):
    """Вибір цілого елемента (без точки на ньому — підсвічується весь елемент). Повертає (елемент, точка кліку):
    точку Revit зазвичай віддає в Reference.GlobalPoint і для вибору елемента; якщо ні — None, і конектори
    підбираються як найближча пара."""
    ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, DuctElementFilter(), prompt)
    point = None
    try:
        point = ref.GlobalPoint
    except Exception:
        point = None
    if point is None:
        hvac_log.log(TOOL, u'точка кліку недоступна — конектор підбиратиметься як найближча пара')
    else:
        hvac_log.log(TOOL, u'точка кліку: ({0:.2f}, {1:.2f}, {2:.2f})'.format(point.X, point.Y, point.Z))
    return doc.GetElement(ref.ElementId), point


def nearest_free(el, point):
    """Вільний конектор елемента, найближчий до точки кліку; None — вільних немає."""
    free = free_connectors(el)
    if not free:
        return None
    return min(free, key=lambda c: c.Origin.DistanceTo(point))


def closest_pair(el0, el1):
    """Пара вільних конекторів (з першого й другого елемента) з найменшою відстанню між ними."""
    free0, free1 = free_connectors(el0), free_connectors(el1)
    if not free0 or not free1:
        return None
    return min(((a, b) for a in free0 for b in free1), key=lambda p: p[0].Origin.DistanceTo(p[1].Origin))


def choose_pair(e0, p0, e1, p1):
    """Пара конекторів: кожен — найближчий до місця кліку на своєму елементі. Немає точок кліку — найближча пара."""
    if p0 is None or p1 is None:
        return closest_pair(e0, e1)
    c0, c1 = nearest_free(e0, p0), nearest_free(e1, p1)
    if c0 is None or c1 is None:
        return None
    return c0, c1


def describe_pick(el, point):
    """Для підказки в рядку стану: що вже обрано — категорія й переріз найближчого до кліку конектора."""
    try:
        c = nearest_free(el, point) if point is not None else None
        size = hvac_sizes.label(connector_size(c)) if c is not None else u''
        return (u'{0} {1}'.format(category_name(el), size)).strip()
    except Exception:
        return category_name(el)


def explain_no_free(e0, e1):
    """Чому пару не знайдено: який елемент без вільних конекторів і що з його конекторами (у журнал і в діалог)."""
    lines = []
    for e in (e0, e1):
        if not free_connectors(e):
            conns = element_connectors(e)
            hvac_log.log(TOOL, u'немає вільних конекторів: {0} id {1}; конектори: {2}'.format(
                category_name(e), eid_int(e.Id), u'; '.join(connector_text(c) for c in conns) or u'немає'))
            lines.append(u'«{0}» (id {1}): усього конекторів {2}, вільних 0'.format(
                category_name(e), eid_int(e.Id), len(conns)))
    return u'\n'.join(lines)


# ---------- типи, система, рівень ----------

def flex_types():
    return sorted(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType), key=type_name)


_CFG = []


def get_cfg():
    """Об'єкт конфігурації pyRevit — читаємо файл налаштувань один раз за запуск, а не при кожному зверненні."""
    if not _CFG:
        _CFG.append(script.get_config(CONFIG_SECTION))
    return _CFG[0]


def load_last(key):
    try:
        return get_cfg().get_option(key, u'')
    except Exception:
        return u''


def save_last(key, value):
    try:
        get_cfg().set_option(key, value)
        script.save_config()
    except Exception:
        pass


PICK_XAML = u"""
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="340" SizeToContent="Height" WindowStartupLocation="CenterScreen"
        ResizeMode="NoResize" ShowInTaskbar="False" Topmost="True">
  <StackPanel Margin="12">
    <ComboBox x:Name="choices" Margin="0,0,0,10"/>
    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
      <Button x:Name="ok_btn" Content="OK" Width="80" Margin="0,0,8,0" IsDefault="True"/>
      <Button x:Name="cancel_btn" Content="Скасувати" Width="80" IsCancel="True"/>
    </StackPanel>
  </StackPanel>
</Window>
"""


def pick_in_small_window(names, last, title):
    """Компактне вікно: один випадаючий список, остання вибрана позиція вже підставлена; Enter — OK, Esc — скасувати.
    Повертає вибране ім'я або None."""

    class PickWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, PICK_XAML, literal_string=True)
            self.Title = title
            self.result = None
            combo = self.FindName('choices')
            for n in names:
                combo.Items.Add(n)
            combo.SelectedItem = last if last in names else names[0]
            self.FindName('ok_btn').Click += self.on_ok
            combo.Focus()

        def on_ok(self, sender, args):
            self.result = self.FindName('choices').SelectedItem
            self.Close()

    win = PickWindow()
    win.ShowDialog()
    return win.result


def choose_from(items, names, title, last_key):
    """Вибір зі списку з пам'яттю останнього (він підставляється одразу, Enter — підтвердити). Один елемент — без запиту.
    Не вдалося створити своє вікно — стандартний список pyRevit."""
    if len(items) == 1:
        return items[0]
    last = load_last(last_key)
    ordered = sorted(names)
    try:
        picked = pick_in_small_window(ordered, last, title)
    except Exception:
        hvac_log.log_exception(TOOL, u'компактне вікно вибору не вдалося, беру стандартний список')
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
        forms.alert(u'У проєкті немає типів механічних систем.', title=u'QuickFlexConnect', exitscript=True)
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


def connector_size(c):
    """Переріз конектора: круглий / прямокутний / овальний (або невідомий)."""
    try:
        shape = c.Shape
        if shape == DB.ConnectorProfileType.Round:
            return hvac_sizes.round_size(c.Radius * 2.0)
        if shape == DB.ConnectorProfileType.Rectangular:
            return hvac_sizes.box_size('rect', c.Width, c.Height)
        if shape == DB.ConnectorProfileType.Oval:
            return hvac_sizes.box_size('oval', c.Width, c.Height)
    except Exception:
        hvac_log.log_exception(TOOL, u'переріз конектора не прочитано')
    return hvac_sizes.unknown_size()


def type_shape(t):
    """Форма типу гнучкого повітровода (MEPCurveType.Shape): 'round' / 'rect' / 'oval' або None, якщо не визначити."""
    try:
        shape = t.Shape
        if shape == DB.ConnectorProfileType.Round:
            return 'round'
        if shape == DB.ConnectorProfileType.Rectangular:
            return 'rect'
        if shape == DB.ConnectorProfileType.Oval:
            return 'oval'
    except Exception:
        pass
    return None


def standard_sizes(shape):
    """Стандартні круглі діаметри з налаштувань механіки проєкту (для вибору «свого» розміру). Прямокутні й овальні
    списком не пропонуємо — їх можна взяти лише з конекторів. Не вдалося прочитати — порожній список."""
    if shape != 'round':
        return []
    try:
        settings = DB.Mechanical.DuctSizeSettings.GetDuctSizeSettings(doc)
        for pair in settings:
            if pair.Key == DB.Mechanical.DuctShape.Round:
                found = [hvac_sizes.round_size(m.NominalDiameter) for m in pair.Value
                         if getattr(m, 'UsedInSizeLists', True)]
                return sorted(found, key=lambda x: x['d'])
    except Exception:
        hvac_log.log_exception(TOOL, u'стандартні розміри не прочитано (не критично)')
    return []


def apply_size(flex, size):
    """Задати розмір гнучкого повітровода: діаметр для круглого, ширина й висота для прямокутного та овального."""
    try:
        shape = size.get('shape')
        if shape == 'round':
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_DIAMETER_PARAM).Set(size['d'])
        elif shape in ('rect', 'oval'):
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_WIDTH_PARAM).Set(size['w'])
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_HEIGHT_PARAM).Set(size['h'])
    except Exception:
        hvac_log.log_exception(TOOL, u'розмір не задано — лишається розмір типу (не критично)')


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


def set_param_text(p, value, hint=None, trust=False):
    """Записати значення з тексту. Повертає (вдалося, число-варіант або None); число — для параметрів-списків."""
    st = p.StorageType
    if st == DB.StorageType.String:
        return bool(p.Set(value)), None
    if st == DB.StorageType.Integer:
        try:
            return bool(p.Set(int(value))), None
        except ValueError:
            number = hvac_revit.set_enum_by_text(p, value, refresh=doc.Regenerate, hint=hint, trust_hint=trust)
            return number is not None, number
    if st == DB.StorageType.Double:
        return bool(p.SetValueString(value)), None
    return False, None            # ElementId та інше — не підтримуємо


def find_config_param(el):
    """Параметр «Гибкая конфигурация»: вбудований RBS_FLEX_PATTERN_PARAM, а якщо його немає — за назвою."""
    return hvac_revit.find_param(DB, el, hvac_flex_settings.BUILTIN_PARAM, hvac_flex_settings.FALLBACK_PARAM_NAME)


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
    value = state['value']
    name = hvac_flex_settings.FALLBACK_PARAM_NAME
    if not value:
        return
    try:
        type_el = doc.GetElement(flex.GetTypeId())
        for label, el in ((u'екземпляр', flex), (u'тип', type_el)):
            p = find_config_param(el)
            if p is None:
                continue
            if p.IsReadOnly:
                hvac_log.log(TOOL, u'параметр «{0}» ({1}) тільки для читання — пропущено'.format(name, label))
                state['warnings'].append(u'Параметр «{0}» тільки для читання.'.format(name))
                return
            before = param_text(p)
            if before.strip().lower() == value.lower():
                hvac_log.log(TOOL, u'«{0}» ({1}) вже = «{2}»'.format(name, label, value))
                return
            hint = state.get('number')
            ok, number = set_param_text(p, value, hint, trust=hint is not None)
            if number is not None:
                state['trusted'] = hint is not None and number == hint           # записали за довіреним числом
                state['number'] = state['learned'] = number
            if ok:
                hvac_log.log(TOOL, u'«{0}» ({1}): «{2}» → «{3}»'.format(name, label, before, value))
            else:
                hvac_log.log(TOOL, u'«{0}» ({1}): значення «{2}» не прийнято (було «{3}»)'.format(name, label, value, before))
                state['warnings'].append(u'Параметр «{0}»: значення «{1}» не прийнято.'.format(name, value))
            return
        hvac_log.log(TOOL, u'параметра «{0}» (RBS_FLEX_PATTERN_PARAM) немає ні в екземплярі, ні в типі'.format(name))
        state['warnings'].append(u'Параметра «{0}» не знайдено (список параметрів — у журналі).'.format(name))
        if not state['dumped']:
            state['dumped'] = True
            dump_parameter_names(flex, type_el)
    except Exception as ex:
        hvac_log.log_exception(TOOL, u'запис параметра «{0}»'.format(name))
        state['warnings'].append(u'Не вдалося записати параметр «{0}»: {1}'.format(name, ex))


BUILD_XAML = u"""
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="QuickFlexConnect" Width="400" SizeToContent="Height" WindowStartupLocation="CenterScreen"
        ResizeMode="NoResize" ShowInTaskbar="False" Topmost="True">
  <StackPanel Margin="12">
    <TextBlock Text="Розміри елементів різні. Розмір гнучкого повітровода:" Margin="0,0,0,6"/>
    <StackPanel Orientation="Horizontal" Margin="0,0,0,6">
      <ToggleButton x:Name="chip0" MinWidth="120" Padding="12,5" Margin="0,0,8,0"/>
      <ToggleButton x:Name="chip1" MinWidth="120" Padding="12,5"/>
    </StackPanel>
    <ComboBox x:Name="custom_size" Margin="0,0,0,12"/>
    <TextBlock Text="Тип гнучкого повітровода:" Margin="0,0,0,4"/>
    <ComboBox x:Name="types" Margin="0,0,0,12"/>
    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
      <Button x:Name="ok_btn" Content="OK" Width="80" Margin="0,0,8,0" IsDefault="True"/>
      <Button x:Name="cancel_btn" Content="Скасувати" Width="80" IsCancel="True"/>
    </StackPanel>
  </StackPanel>
</Window>
"""

CUSTOM_PLACEHOLDER = u'Інший розмір…'
NO_CUSTOM_SIZES = u'(інших стандартних розмірів немає)'


def ask_size_and_type_window(sizes, custom_sizes, entries, last):
    """Одне вікно, коли розміри елементів різні: два «чипи» з розмірами обох конекторів (клік — вибрано, за
    замовчуванням перший), нижче випадаючий список «інший розмір», ще нижче тип. Список типів підлаштовується під
    форму вибраного розміру. Повертає (розмір, ім'я типу) або None, якщо вікно закрито."""

    class BuildWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, BUILD_XAML, literal_string=True)
            self.result = None
            self.size = sizes[0]
            self.chips = [self.FindName('chip0'), self.FindName('chip1')]
            self.custom = self.FindName('custom_size')
            self.types = self.FindName('types')
            for i, chip in enumerate(self.chips):
                chip.Content = u'{0}-й: {1}'.format(i + 1, hvac_sizes.label(sizes[i]))
            chip_handlers = (self.on_chip0, self.on_chip1)
            for chip, handler in zip(self.chips, chip_handlers):
                chip.Click += handler
            self.custom.Items.Add(CUSTOM_PLACEHOLDER if custom_sizes else NO_CUSTOM_SIZES)
            for c in custom_sizes:
                self.custom.Items.Add(hvac_sizes.label(c))
            self.custom.SelectedIndex = 0
            self.custom.IsEnabled = bool(custom_sizes)
            self.custom.SelectionChanged += self.on_custom
            self.FindName('ok_btn').Click += self.on_ok
            self.select_chip(0)
            self.types.Focus()

        def refill_types(self):
            names = hvac_sizes.types_for_shape(entries, self.size.get('shape'))
            keep = self.types.SelectedItem
            self.types.Items.Clear()
            for n in names:
                self.types.Items.Add(n)
            self.types.SelectedItem = keep if keep in names else (last if last in names else (names[0] if names else None))

        def select_chip(self, index):
            self.size = sizes[index]
            for i, chip in enumerate(self.chips):
                chip.IsChecked = (i == index)
            self.custom.SelectedIndex = 0
            self.refill_types()

        def on_chip0(self, sender, args):
            self.select_chip(0)

        def on_chip1(self, sender, args):
            self.select_chip(1)

        def on_custom(self, sender, args):
            index = self.custom.SelectedIndex
            if index is None or index < 1:
                return
            self.size = custom_sizes[index - 1]
            for chip in self.chips:
                chip.IsChecked = False
            self.refill_types()

        def on_ok(self, sender, args):
            chosen = self.types.SelectedItem
            if chosen is not None:
                self.result = (self.size, chosen)
                self.Close()

    win = BuildWindow()
    win.ShowDialog()
    return win.result


def ask_size_and_type_dialogs(sizes, custom_sizes, entries, last):
    """Запасний варіант на стандартних списках pyRevit: розмір, потім тип."""
    labels = [u'{0}-й: {1}'.format(i + 1, hvac_sizes.label(sz)) for i, sz in enumerate(sizes)]
    labels += [hvac_sizes.label(c) for c in custom_sizes]
    everything = list(sizes) + list(custom_sizes)
    picked = forms.SelectFromList.show(labels, title=u'Розмір гнучкого повітровода', button_name=u'Далі',
                                       multiselect=False)
    if not picked:
        return None
    size = everything[labels.index(picked)]
    names = hvac_sizes.types_for_shape(entries, size.get('shape'))
    if not names:
        return size, None
    if len(names) == 1:
        return size, names[0]
    name = forms.SelectFromList.show(names, title=u'Тип гнучкого повітровода:', button_name=u'Обрати',
                                     multiselect=False)
    return (size, name) if name else None


def choose_options(s0, s1, entries, state):
    """Після вибору двох елементів: який розмір і тип гнучкого. Повертає (тип-елемент, розмір).
    Однакові розміри — розмір один, питаємо лише тип (а в циклі й того, якщо тип уже обрано й підходить);
    тут можливий клік на зразок у моделі. Різні — одразу одне вікно з чипами розмірів і типом, без кліку на зразок.
    Закрили вікно — script.exit()."""
    by_name = dict((name, el) for name, _shape, el in entries)
    entry_pairs = [(name, shape) for name, shape, _el in entries]
    last = load_last('flex_type')
    sample = None
    same = hvac_sizes.same_size(s0, s1)
    # Тип кліком на гнучкий повітровод — лише коли розміри однакові. Різні розміри: одразу вікно з чипами й типом
    # (воно саме по собі вибір), навіть якщо увімкнено «тип з моделі».
    if same and state.get('from_model') and state.get('type') is None:
        sample = pick_sample_type(by_name)
    if same:
        size = s0
        names = hvac_sizes.types_for_shape(entry_pairs, size.get('shape'))
        if not names:
            raise ValueError(u'Немає типів гнучкого повітровода для форми «{0}».'.format(
                hvac_sizes.SHAPE_NAMES.get(size.get('shape'), u'?')))
        cur = state.get('type')
        if cur is not None and type_name(cur) in names:
            return cur, size
        if sample is not None:
            if type_name(sample) in names:
                state['type'] = sample
                save_last('flex_type', type_name(sample))
                return sample, size
            forms.alert(u'Тип «{0}» не підходить за формою («{1}»). Оберіть інший зі списку.'.format(
                type_name(sample), hvac_sizes.SHAPE_NAMES.get(size.get('shape'), u'?')), title=u'QuickFlexConnect')
        chosen = choose_from([by_name[n] for n in names], names, u'Тип гнучкого повітровода:', 'flex_type')
        state['type'] = chosen
        return chosen, size
    sizes = [s0, s1]
    shapes = [x.get('shape') for x in sizes]
    custom = hvac_sizes.dedupe_sizes(sizes + standard_sizes('round' if 'round' in shapes else None))[2:]
    hvac_log.log(TOOL, u'розміри різні: {0} / {1}; власних розмірів у списку: {2}'.format(
        hvac_sizes.label(s0), hvac_sizes.label(s1), len(custom)))
    try:
        result = ask_size_and_type_window(sizes, custom, entry_pairs, last)
    except Exception:
        hvac_log.log_exception(TOOL, u'вікно розміру й типу не вдалося, беру стандартні списки')
        result = ask_size_and_type_dialogs(sizes, custom, entry_pairs, last)
    if result is None:
        script.exit()
    size, name = result
    if name is None:
        raise ValueError(u'Немає типів гнучкого повітровода для форми «{0}».'.format(
            hvac_sizes.SHAPE_NAMES.get(size.get('shape'), u'?')))
    save_last('flex_type', name)
    state['type'] = by_name[name]
    return by_name[name], size


def verify_config_param(flex_id, state):
    """Після коміту (модель уже перерахована Revit-ом) перевіряємо значення, записане за запам'ятованим числом, —
    дешеве читання без жодного перерахунку. Не збіглось (число застаріло) — одноразово виправляємо перебором."""
    try:
        flex = doc.GetElement(flex_id)
        for el in (flex, doc.GetElement(flex.GetTypeId())):
            p = find_config_param(el)
            if p is not None:
                if param_text(p).strip().lower() == state['value'].lower():
                    return
                break
        hvac_log.log(TOOL, u'запам\'ятоване число {0} дало інше значення — визначаю заново'.format(state.get('number')))
        state['number'] = None
        t = DB.Transaction(doc, u'QuickFlexConnect: виправлення параметра')
        t.Start()
        try:
            apply_config_param(doc.GetElement(flex_id), state)
            t.Commit()
        except Exception:
            t.RollBack()
            raise
    except Exception:
        hvac_log.log_exception(TOOL, u'перевірка параметра після побудови')


def build_one(c0, c1, flex_type, size, system_state):
    system_id = system_type_id_from(c0) or system_type_id_from(c1) or system_state.get('id')
    if system_id is None:
        system_id = pick_system_type_id()
        system_state['id'] = system_id
    level_id = level_id_for(c0)
    if level_id is None:
        raise ValueError(u'У проєкті немає рівнів.')
    hvac_log.log(TOOL, u'побудова: тип {0}, розмір {1}, система {2}, рівень {3}, довжина {4:.3f} ft'.format(
        type_name(flex_type), hvac_sizes.label(size), eid_int(system_id), eid_int(level_id),
        c0.Origin.DistanceTo(c1.Origin)))
    started = time.time()
    t = DB.Transaction(doc, u'QuickFlexConnect: гнучкий повітровод між конекторами')
    t.Start()
    try:
        flex = create_flex(c0, c1, flex_type.Id, system_id, level_id)
        apply_size(flex, size)
        system_state['trusted'] = False
        apply_config_param(flex, system_state)
        connect_ends(flex, c0, c1)
        t.Commit()
        hvac_log.log(TOOL, u'створено, id {0}, {1} мс'.format(eid_int(flex.Id), hvac_log.elapsed_ms(started)))
    except Exception:
        t.RollBack()
        hvac_log.log_exception(TOOL, u'побудова (транзакцію відкотено)')
        raise
    if system_state.get('trusted'):
        verify_config_param(flex.Id, system_state)
    return flex


def main():
    types = flex_types()
    if not types:
        forms.alert(u'У проєкті немає типів гнучких повітроводів.', title=u'QuickFlexConnect', exitscript=True)
    entries = [(type_name(t), type_shape(t), t) for t in types]
    cfg = get_cfg()
    ctx = hvac_revit.app_context(doc)
    config_value = hvac_flex_settings.get_config_value(cfg)
    # Режим циклу — галочка у вікні налаштувань (Shift+клік), за замовчуванням вимкнено.
    loop = hvac_flex_settings.is_loop(cfg)
    hvac_log.log(TOOL, u'типів гнучких: {0} ({1}); «Гибкая конфигурация» = «{2}», цикл {3}, тип з моделі {4}, журнал {5}'.format(
        len(types), u', '.join(u'{0}[{1}]'.format(n, sh) for n, sh, _t in entries), config_value, loop,
        hvac_flex_settings.is_type_from_model(cfg), hvac_log.log_path()))
    tail = u'Esc — завершити' if loop else u'Esc — скасувати'
    hvac_log.log(TOOL, u'підготовка до першого вибору (імпорти, типи, налаштування): {0} мс'.format(hvac_log.elapsed_ms(_T0)))
    system_state = {'id': None, 'type': None, 'from_model': hvac_flex_settings.is_type_from_model(cfg),
                    'value': config_value,
                    'number': hvac_flex_settings.get_config_number(cfg, ctx), 'learned': None, 'trusted': False,
                    'warnings': [], 'dumped': False}
    made = 0
    while True:
        try:
            # Підказки йдуть у рядок стану Revit (це текст запиту PickObject): що робити зараз і що вже обрано.
            pair_no = u'пара {0}: '.format(made + 1) if loop else u''
            e0, p0 = pick_element(u'QuickFlexConnect · {0}1/2 — клацніть на першому елементі, конектор буде найближчий '
                                  u'до кліку ({1})'.format(pair_no, tail))
            first = describe_pick(e0, p0)
            e1, p1 = pick_element(u'QuickFlexConnect · {0}2/2 — перший: {1}. Клацніть на другому елементі, конектор буде '
                                  u'найближчий до кліку ({2})'.format(pair_no, first, tail))
        except OperationCanceledException:
            hvac_log.log(TOOL, u'вибір скасовано (Esc)')
            break
        hvac_log.log(TOOL, u'вибрано: {0} «{1}» id {2} і {3} «{4}» id {5}'.format(
            category_name(e0), type_label(e0), eid_int(e0.Id), category_name(e1), type_label(e1), eid_int(e1.Id)))
        if eid_int(e0.Id) == eid_int(e1.Id):
            forms.alert(u'Це той самий елемент. Оберіть два різні.', title=u'QuickFlexConnect')
            if loop:
                continue
            break
        pair = choose_pair(e0, p0, e1, p1)
        if pair is None:
            forms.alert(u'На одному з елементів немає вільних конекторів:\n{0}\n\nЖурнал: {1}'.format(
                explain_no_free(e0, e1), hvac_log.log_path()), title=u'QuickFlexConnect')
            if loop:
                continue
            break
        hvac_log.log(TOOL, u'пара конекторів: ({0:.2f}, {1:.2f}, {2:.2f}) → ({3:.2f}, {4:.2f}, {5:.2f})'.format(
            pair[0].Origin.X, pair[0].Origin.Y, pair[0].Origin.Z,
            pair[1].Origin.X, pair[1].Origin.Y, pair[1].Origin.Z))
        s0, s1 = connector_size(pair[0]), connector_size(pair[1])
        hvac_log.log(TOOL, u'розміри конекторів: {0} / {1}'.format(hvac_sizes.label(s0), hvac_sizes.label(s1)))
        try:
            flex_type, size = choose_options(s0, s1, entries, system_state)
            build_one(pair[0], pair[1], flex_type, size, system_state)
            made += 1
        except Exception as ex:
            if hvac_log.is_not_error(ex):
                raise                                       # Esc / закрите вікно вибору
            hvac_log.log(TOOL, u'побудова не вдалася: {0}'.format(ex))
            forms.alert(u'Не вдалося побудувати гнучкий повітровод:\n{0}\n\nЖурнал: {1}'.format(ex, hvac_log.log_path()),
                        title=u'QuickFlexConnect')
        if not loop:
            break
    for w in sorted(set(system_state['warnings'])):
        output.print_md(u'* **Увага:** {0}'.format(w))
    if system_state['learned'] is not None and system_state['learned'] != hvac_flex_settings.get_config_number(cfg, ctx):
        hvac_flex_settings.set_config_number(cfg, system_state['learned'], ctx)      # наступного разу — без перебору
        script.save_config()
    hvac_log.log(TOOL, u'створено гнучких повітроводів: {0}'.format(made))      # вікно виводу на успіх не відкриваємо


hvac_log.run(TOOL, main, doc)
