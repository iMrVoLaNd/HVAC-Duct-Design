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
    import hvac_sizes
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


_ALLOWED_CACHE = []


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


class FlexSampleFilter(UI.Selection.ISelectionFilter):
    """Дозволяє клацнути лише на гнучкий повітровод — з нього беремо тип."""

    __namespace__ = 'HvacFlexSample_' + uuid.uuid4().hex          # див. примітку в DuctElementFilter

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
                                         u'Клацніть на гнучкий повітровод, з якого взяти тип (Esc — обрати зі списку)')
    except OperationCanceledException:
        hvac_log.log(TOOL, u'зразок типу не вибрано (Esc) — вибір зі списку')
        return None
    flex = doc.GetElement(ref.ElementId)
    name = type_name(doc.GetElement(flex.GetTypeId()))
    hvac_log.log(TOOL, u'тип зі зразка в моделі: «{0}»'.format(name))
    if name not in by_name:
        forms.alert(u'Тип «{0}» не знайдено серед типів гнучких повітроводів. Оберіть зі списку.'.format(name),
                    title=u'Гнучкий повітровод')
        return None
    return by_name[name]


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


def set_param_text(p, value, hint=None):
    """Записати значення з тексту. Повертає (вдалося, число-варіант або None); число — для параметрів-списків."""
    st = p.StorageType
    if st == DB.StorageType.String:
        return bool(p.Set(value)), None
    if st == DB.StorageType.Integer:
        try:
            return bool(p.Set(int(value))), None
        except ValueError:
            number = hvac_revit.set_enum_by_text(p, value, refresh=doc.Regenerate, hint=hint)
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
            ok, number = set_param_text(p, value, state.get('number'))
            if number is not None:
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
        Title="Гнучкий повітровод" Width="400" SizeToContent="Height" WindowStartupLocation="CenterScreen"
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
                type_name(sample), hvac_sizes.SHAPE_NAMES.get(size.get('shape'), u'?')), title=u'Гнучкий повітровод')
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
    t = DB.Transaction(doc, u'Гнучкий повітровод між конекторами')
    t.Start()
    try:
        flex = create_flex(c0, c1, flex_type.Id, system_id, level_id)
        apply_size(flex, size)
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
    entries = [(type_name(t), type_shape(t), t) for t in types]
    cfg = script.get_config(CONFIG_SECTION)
    config_value = hvac_flex_settings.get_config_value(cfg)
    # Режим циклу — галочка у вікні налаштувань (Shift+клік), за замовчуванням вимкнено.
    loop = hvac_flex_settings.is_loop(cfg)
    hvac_log.log(TOOL, u'типів гнучких: {0} ({1}); «Гибкая конфигурация» = «{2}», цикл {3}, тип з моделі {4}, журнал {5}'.format(
        len(types), u', '.join(u'{0}[{1}]'.format(n, sh) for n, sh, _t in entries), config_value, loop,
        hvac_flex_settings.is_type_from_model(cfg), hvac_log.log_path()))
    tail = u'Esc — завершити' if loop else u'Esc — скасувати'
    system_state = {'id': None, 'type': None, 'from_model': hvac_flex_settings.is_type_from_model(cfg),
                    'value': config_value,
                    'number': hvac_flex_settings.get_config_number(cfg), 'learned': None,
                    'warnings': [], 'dumped': False}
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
        if pair is None:
            forms.alert(u'На одному з елементів немає вільних конекторів.', title=u'Гнучкий повітровод')
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
                        title=u'Гнучкий повітровод')
        if not loop:
            break
    for w in sorted(set(system_state['warnings'])):
        output.print_md(u'* **Увага:** {0}'.format(w))
    if system_state['learned'] is not None and system_state['learned'] != hvac_flex_settings.get_config_number(cfg):
        hvac_flex_settings.set_config_number(cfg, system_state['learned'])      # наступного разу — без перебору
        script.save_config()
    hvac_log.log(TOOL, u'створено гнучких повітроводів: {0}'.format(made))      # вікно виводу на успіх не відкриваємо


hvac_log.run(TOOL, main, doc)
