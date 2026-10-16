# -*- coding: utf-8 -*-
__title__ = u'Flex\nTail'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'FlexTail: кликаете по оборудованию, арматуре, соединительной детали или воздухораспределителю, к которому '
           u'подключён жёсткий воздуховод. В окне задаёте длину и тип гибкого воздуховода — и участок жёсткого '
           u'воздуховода от этого элемента заданной длины заменяется гибким. Длина запоминается. Если жёсткий участок '
           u'короче заданной длины, он преобразуется целиком и кнопка об этом сообщит.')

# Совместимо с IronPython 3.4 (pyRevit) и CPython: без f-строк и современного синтаксиса.
import os
import sys
import time

_T0 = time.time()

# Папка lib расширения (HVAC.extension/lib). Обычно pyRevit добавляет её сам; добавляем явно на всякий случай.
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
    forms.alert(u'Не найден файл lib\\hvac_log.py.\nСкопируйте в расширение ВСЮ папку HVAC.extension вместе с lib '
                u'(все файлы) и перезагрузите pyRevit.\n\nИскал здесь: {0}'.format(_LIB),
                title=u'HVAC', exitscript=True)
TOOL = 'FlexTail'

try:
    from pyrevit import revit, DB, UI, script
    from System.Collections.Generic import List
    from Autodesk.Revit.Exceptions import OperationCanceledException

    import hvac_flex_settings
    import hvac_revit
    import hvac_sizes
    import hvac_tail
except Exception:
    hvac_log.log_exception(TOOL, u'импорт модулей')
    raise

doc = revit.doc
uidoc = revit.uidoc

TAIL_SECTION = 'flex_tail'                      # длина и последний тип этой кнопки
FLEX_SECTION = hvac_flex_settings.SECTION       # «Гибкая конфигурация» — общая с QuickFlexConnect
BEND_FACTOR = 0.3                               # запасной вариант FlexDuct.Create: «вылет» от конца (доля длины)
BEND_MIN_FT = 0.3

# Какие элементы можно выбирать (имена BuiltInCategory). Сам воздуховод выбирать не нужно: он берётся от элемента.
ALLOWED_CATEGORIES = [
    u'OST_DuctAccessory',         # арматура воздуховодов
    u'OST_DuctFitting',           # соединительные детали воздуховодов
    u'OST_MechanicalEquipment',   # оборудование
    u'OST_DuctTerminal',          # воздухораспределители
]


class _LazyForms(object):
    """pyrevit.forms тянет WPF и стоит десятки-сотни мс; грузим его только при первом обращении."""

    def __getattr__(self, name):
        from pyrevit import forms as real_forms
        return getattr(real_forms, name)


forms = _LazyForms()


def _unique_namespace(prefix):
    """Уникальное __namespace__ для классов, реализующих .NET-интерфейс (нужно CPython-движку pyRevit)."""
    return u'{0}{1:x}{2:x}'.format(prefix, int(time.time() * 1000000), int.from_bytes(os.urandom(6), 'big'))


def eid_int(eid):
    """Числовое значение ElementId (в новых версиях Revit — .Value, в старых — .IntegerValue)."""
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


# ---------- коннекторы ----------

def element_connectors(el):
    """Все коннекторы элемента: воздуховод (ConnectorManager) или семейство (MEPModel). Тип определяем по классу, а не
    через AttributeError — исключения в IronPython дороги, а функция вызывается при каждом движении курсора."""
    mgr = None
    curve_cls = getattr(DB, 'MEPCurve', None)
    family_cls = getattr(DB, 'FamilyInstance', None)
    if curve_cls is not None and isinstance(el, curve_cls):
        mgr = el.ConnectorManager
    elif family_cls is not None and isinstance(el, family_cls):
        mep = el.MEPModel
        mgr = mep.ConnectorManager if mep is not None else None
    else:                                   # неизвестный класс (или заглушка): запасной путь через исключения
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


def hvac_connectors(el):
    """Все вентиляционные коннекторы элемента (свободные и занятые)."""
    result = []
    for c in element_connectors(el):
        try:
            if c.Domain == DB.Domain.DomainHvac:
                result.append(c)
        except Exception:
            pass
    return result


def connector_size(c):
    """Сечение коннектора: круглое / прямоугольное / овальное (или неизвестное)."""
    try:
        shape = c.Shape
        if shape == DB.ConnectorProfileType.Round:
            return hvac_sizes.round_size(c.Radius * 2.0)
        if shape == DB.ConnectorProfileType.Rectangular:
            return hvac_sizes.box_size('rect', c.Width, c.Height)
        if shape == DB.ConnectorProfileType.Oval:
            return hvac_sizes.box_size('oval', c.Width, c.Height)
    except Exception:
        hvac_log.log_exception(TOOL, u'сечение коннектора не прочитано')
    return hvac_sizes.unknown_size()


def type_shape(t):
    """Форма типа гибкого воздуховода: 'round' / 'rect' / 'oval' или None, если определить нельзя."""
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


def apply_size(flex, size):
    """Задать размер гибкого воздуховода: диаметр для круглого, ширина и высота для прямоугольного и овального."""
    try:
        shape = size.get('shape')
        if shape == 'round':
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_DIAMETER_PARAM).Set(size['d'])
        elif shape in ('rect', 'oval'):
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_WIDTH_PARAM).Set(size['w'])
            flex.get_Parameter(DB.BuiltInParameter.RBS_CURVE_HEIGHT_PARAM).Set(size['h'])
    except Exception:
        hvac_log.log_exception(TOOL, u'размер не задан — остаётся размер типа (не критично)')


# ---------- выбор элемента ----------

_ALLOWED_CACHE = []
_ALLOW_CACHE = {}


def allowed_category_values():
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


class TailElementFilter(UI.Selection.ISelectionFilter):
    """Разрешает выбрать оборудование, арматуру, соединительные детали и воздухораспределители с вентиляционными
    коннекторами. Есть ли к нужному коннектору жёсткий воздуховод, проверяем после клика — чтобы объяснить причину
    сообщением, а не молча не реагировать."""

    __namespace__ = _unique_namespace('HvacTail_')        # CPython-движок pyRevit: см. QuickFlexConnect

    def AllowElement(self, e):
        try:
            key = eid_int(e.Id)
            cached = _ALLOW_CACHE.get(key)
            if cached is not None:
                return cached
            allowed = bool(is_allowed_category(e) and hvac_connectors(e))
            _ALLOW_CACHE[key] = allowed
            return allowed
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


def pick_element(prompt):
    """Выбор целого элемента. Возвращает (элемент, точка клика); точку Revit отдаёт в Reference.GlobalPoint."""
    ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, TailElementFilter(), prompt)
    point = None
    try:
        point = ref.GlobalPoint
    except Exception:
        point = None
    if point is None:
        hvac_log.log(TOOL, u'точка клика недоступна — берётся коннектор с подключённым воздуховодом')
    else:
        hvac_log.log(TOOL, u'точка клика: ({0:.2f}, {1:.2f}, {2:.2f})'.format(point.X, point.Y, point.Z))
    return doc.GetElement(ref.ElementId), point


def is_physical(c):
    """Настоящее соединение (конец воздуховода / патрубок), а не логическая связь с системой: Connector.AllRefs
    возвращает и логические коннекторы системы — они исчезают вместе с воздуховодом, и обращаться к ним нельзя."""
    try:
        return c.ConnectorType in (DB.ConnectorType.End, DB.ConnectorType.Physical)
    except Exception:
        return False


def physical_refs(c):
    """Коннекторы, физически подключённые к c."""
    try:
        return [r for r in list(c.AllRefs) if is_physical(r)]
    except Exception:
        return []


def connected_ducts(c, owner_id):
    """Жёсткие воздуховоды, подключённые к коннектору c: [(воздуховод, его коннектор в этом соединении)]."""
    result = []
    for r in physical_refs(c):
        try:
            owner = r.Owner
            if owner is None or eid_int(owner.Id) == owner_id:
                continue
            if isinstance(owner, DB.Mechanical.Duct):
                result.append((owner, r))
        except Exception:
            continue
    return result


def other_connected(c, owner_id):
    """Что подключено к коннектору c, кроме его владельца: [(элемент, коннектор)] (для сообщения об ошибке)."""
    result = []
    for r in physical_refs(c):
        try:
            owner = r.Owner
            if owner is not None and eid_int(owner.Id) != owner_id:
                result.append((owner, r))
        except Exception:
            continue
    return result


def resolve_start(el, point):
    """По элементу и точке клика: (коннектор элемента, жёсткий воздуховод, коннектор воздуховода у элемента, None)
    либо (None, None, None, причина-текст). Берётся коннектор, ближайший к клику, и именно к нему должен быть
    подключён жёсткий воздуховод."""
    conns = hvac_connectors(el)
    if not conns:
        return None, None, None, u'У элемента «{0}» нет вентиляционных коннекторов.'.format(category_name(el))
    owner_id = eid_int(el.Id)
    if point is not None:
        c = min(conns, key=lambda x: x.Origin.DistanceTo(point))
    else:
        with_duct = [x for x in conns if connected_ducts(x, owner_id)]
        c = with_duct[0] if with_duct else conns[0]
    ducts = connected_ducts(c, owner_id)
    if ducts:
        duct, dc = ducts[0]
        return c, duct, dc, None
    others = other_connected(c, owner_id)
    if others:
        names = u', '.join(sorted(set(category_name(o) for o, _r in others)))
        reason = u'К ближайшему к клику коннектору подключён не жёсткий воздуховод, а: {0}.'.format(names)
    else:
        reason = u'К ближайшему к клику коннектору элемента «{0}» не подключён воздуховод.'.format(category_name(el))
    if any(connected_ducts(x, owner_id) for x in conns if x is not c):
        reason += u'\nУ этого элемента воздуховод подключён к другому коннектору — кликните ближе к нему.'
    return None, None, None, reason


# ---------- типы, система, уровень ----------

def flex_types():
    return sorted(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType), key=type_name)


_CFGS = {}


def get_cfg(section):
    """Объект конфигурации pyRevit; читаем файл настроек один раз за запуск."""
    if section not in _CFGS:
        _CFGS[section] = script.get_config(section)
    return _CFGS[section]


def load_last(key):
    try:
        return get_cfg(TAIL_SECTION).get_option(key, u'')
    except Exception:
        return u''


def save_last(key, value):
    try:
        get_cfg(TAIL_SECTION).set_option(key, value)
        script.save_config()
    except Exception:
        pass


def system_type_id_from(connector):
    """Тип системы из системы, к которой уже относится коннектор воздуховода."""
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


def system_type_id_for(duct, connector):
    """Тип системы воздуховода: из системы коннектора, иначе из параметра воздуховода."""
    sid = system_type_id_from(connector)
    if sid is not None:
        return sid
    try:
        p = duct.get_Parameter(DB.BuiltInParameter.RBS_DUCT_SYSTEM_TYPE_PARAM)
        if p is not None:
            eid = p.AsElementId()
            if eid is not None and eid_int(eid) != -1:
                return eid
    except Exception:
        pass
    return None


def level_id_for(duct, point):
    """Уровень: у воздуховода, иначе уровень активного вида, иначе ближайший по высоте."""
    lid = getattr(duct, 'LevelId', None)
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
    return min(levels, key=lambda l: abs(l.Elevation - point.Z)).Id


# ---------- окно: длина и тип ----------

TAIL_XAML = u"""
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="FlexTail" Width="420" SizeToContent="Height"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize" ShowInTaskbar="False" Topmost="True">
  <StackPanel Margin="12">
    <TextBlock x:Name="info" TextWrapping="Wrap" Margin="0,0,0,10" Opacity="0.7"/>
    <TextBlock Text="Длина гибкого участка, мм:" Margin="0,0,0,4"/>
    <TextBox x:Name="length" Margin="0,0,0,6"/>
    <WrapPanel Margin="0,0,0,12">
      <Button x:Name="chip0" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
      <Button x:Name="chip1" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
      <Button x:Name="chip2" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
      <Button x:Name="chip3" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
      <Button x:Name="chip4" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
      <Button x:Name="chip5" MinWidth="58" Padding="6,4" Margin="0,0,6,6"/>
    </WrapPanel>
    <TextBlock Text="Тип гибкого воздуховода:" Margin="0,0,0,4"/>
    <ComboBox x:Name="types" Margin="0,0,0,12"/>
    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
      <Button x:Name="ok_btn" Content="OK" Width="80" Margin="0,0,8,0" IsDefault="True"/>
      <Button x:Name="cancel_btn" Content="Отмена" Width="80" IsCancel="True"/>
    </StackPanel>
  </StackPanel>
</Window>
"""

BAD_LENGTH = u'Введите длину в миллиметрах: число от {0} до {1}.'.format(
    hvac_tail.format_mm(hvac_tail.MIN_LENGTH_MM), hvac_tail.format_mm(hvac_tail.MAX_LENGTH_MM))


def ask_length_and_type_window(names, last_type, last_length, info_text):
    """Окно: длина (поле + быстрые значения) и тип. Возвращает (длина мм, имя типа) или None, если окно закрыто."""

    class TailWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, TAIL_XAML, literal_string=True)
            self.result = None
            self.FindName('info').Text = info_text
            self.length = self.FindName('length')
            self.length.Text = hvac_tail.format_mm(last_length)
            self.types = self.FindName('types')
            for i, mm in enumerate(hvac_tail.CHIPS_MM):
                chip = self.FindName('chip%d' % i)
                chip.Content = hvac_tail.format_mm(mm)
                chip.Click += self.chip_handler(mm)
            for n in names:
                self.types.Items.Add(n)
            self.types.SelectedItem = last_type if last_type in names else names[0]
            self.FindName('ok_btn').Click += self.on_ok
            try:
                self.length.Focus()
                self.length.SelectAll()
            except Exception:
                pass

        def chip_handler(self, mm):
            def handler(sender, args):
                self.length.Text = hvac_tail.format_mm(mm)
            return handler

        def on_ok(self, sender, args):
            mm = hvac_tail.parse_length_mm(self.length.Text)
            if mm is None:
                forms.alert(BAD_LENGTH, title=u'FlexTail')
                return                                     # окно остаётся открытым
            chosen = self.types.SelectedItem
            if chosen is not None:
                self.result = (mm, chosen)
                self.Close()

    win = TailWindow()
    win.ShowDialog()
    return win.result


def ask_length_and_type_dialogs(names, last_type, last_length, info_text):
    """Запасной вариант на стандартных диалогах pyRevit: длина, затем тип."""
    while True:
        text = forms.ask_for_string(default=hvac_tail.format_mm(last_length),
                                    prompt=u'{0}\nДлина гибкого участка, мм:'.format(info_text),
                                    title=u'FlexTail')
        if text is None:
            return None
        mm = hvac_tail.parse_length_mm(text)
        if mm is not None:
            break
        forms.alert(BAD_LENGTH, title=u'FlexTail')
    ordered = [last_type] + [n for n in names if n != last_type] if last_type in names else list(names)
    name = ordered[0] if len(ordered) == 1 else forms.SelectFromList.show(
        ordered, title=u'Тип гибкого воздуховода', button_name=u'Выбрать', multiselect=False)
    return (mm, name) if name else None


# ---------- параметр «Гибкая конфигурация» ----------

def param_text(p):
    try:
        if p.StorageType == DB.StorageType.String:
            return p.AsString() or u''
        return p.AsValueString() or u''
    except Exception:
        return u''


def set_param_text(p, value, hint=None):
    """Записать значение из текста. Возвращает (удалось, число-вариант или None); число — для параметров-списков."""
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
    return False, None


def find_config_param(el):
    return hvac_revit.find_param(DB, el, hvac_flex_settings.BUILTIN_PARAM, hvac_flex_settings.FALLBACK_PARAM_NAME)


def apply_config_param(flex, state):
    """Записать «Гибкая конфигурация» (значение — из настроек QuickFlexConnect) в созданный гибкий воздуховод.
    Никогда не ломает построение: проблемы уходят в state['warnings']."""
    value = state['value']
    name = hvac_flex_settings.FALLBACK_PARAM_NAME
    if not value:
        return
    try:
        type_el = doc.GetElement(flex.GetTypeId())
        for label, el in ((u'экземпляр', flex), (u'тип', type_el)):
            p = find_config_param(el)
            if p is None:
                continue
            if p.IsReadOnly:
                hvac_log.log(TOOL, u'параметр «{0}» ({1}) только для чтения — пропущено'.format(name, label))
                state['warnings'].append(u'Параметр «{0}» только для чтения.'.format(name))
                return
            before = param_text(p)
            if before.strip().lower() == value.lower():
                hvac_log.log(TOOL, u'«{0}» ({1}) уже = «{2}»'.format(name, label, value))
                return
            ok, number = set_param_text(p, value, state.get('number'))
            if number is not None:
                state['number'] = state['learned'] = number
            if ok:
                hvac_log.log(TOOL, u'«{0}» ({1}): «{2}» → «{3}»'.format(name, label, before, value))
            else:
                hvac_log.log(TOOL, u'«{0}» ({1}): значение «{2}» не принято (было «{3}»)'.format(name, label, value, before))
                state['warnings'].append(u'Параметр «{0}»: значение «{1}» не принято.'.format(name, value))
            return
        hvac_log.log(TOOL, u'параметра «{0}» (RBS_FLEX_PATTERN_PARAM) нет ни в экземпляре, ни в типе'.format(name))
        state['warnings'].append(u'Параметр «{0}» не найден.'.format(name))
    except Exception as ex:
        hvac_log.log_exception(TOOL, u'запись параметра «{0}»'.format(name))
        state['warnings'].append(u'Не удалось записать параметр «{0}»: {1}'.format(name, ex))


# ---------- построение ----------

def create_flex(p0, p1, direction, type_id, system_id, level_id):
    """Прямой гибкий воздуховод от p0 до p1 вдоль direction. Основной вариант (Revit 2025+) — две точки и касательные
    на концах; запасной — четыре точки."""
    dist = p0.DistanceTo(p1)
    if dist < hvac_tail.MIN_LEN_FT:
        raise ValueError(u'Гибкий участок получился короче 1/10 дюйма — Revit его не построит.')
    pts = List[DB.XYZ]()
    pts.Add(p0)
    pts.Add(p1)
    try:
        flex = DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, direction, direction, pts)
        hvac_log.log(TOOL, u'FlexDuct.Create: вариант с касательными')
        return flex
    except TypeError as ex:
        hvac_log.log(TOOL, u'FlexDuct.Create с касательными недоступен ({0}), пробую 4 точки'.format(ex))
    k = max(dist * BEND_FACTOR, BEND_MIN_FT)
    pts = List[DB.XYZ]()
    pts.Add(p0)
    pts.Add(p0.Add(direction.Multiply(k)))
    pts.Add(p1.Subtract(direction.Multiply(k)))
    pts.Add(p1)
    flex = DB.Mechanical.FlexDuct.Create(doc, system_id, type_id, level_id, pts)
    hvac_log.log(TOOL, u'FlexDuct.Create: вариант с 4 точками')
    return flex


def connect_ends(flex, targets):
    """Соединить концы гибкого воздуховода с коннекторами: каждый конец — с ближайшим к нему из targets."""
    ends = list(flex.ConnectorManager.Connectors)
    for target in targets:
        if target is None or not ends:
            continue
        try:
            where = target.Origin
        except Exception as ex:                       # коннектор исчез вместе с удалённым воздуховодом — не подключаем
            hvac_log.log(TOOL, u'коннектор для подключения недействителен, пропущен: {0}'.format(ex))
            continue
        mine = min(ends, key=lambda e: e.Origin.DistanceTo(where))
        mine.ConnectTo(target)
        ends = [e for e in ends if e is not mine]


def duct_ends(duct, c_elem):
    """Концы воздуховода: (конец у элемента, дальний конец)."""
    conns = [x for x in element_connectors(duct) if x.Domain == DB.Domain.DomainHvac]
    if len(conns) < 2:
        raise ValueError(u'У воздуховода меньше двух коннекторов.')
    conns.sort(key=lambda x: x.Origin.DistanceTo(c_elem.Origin))
    return conns[0], conns[1]


def neighbor_of(far_end, duct_id):
    """Коннектор, подключённый к дальнему концу воздуховода (кроме него самого), или None."""
    for owner, r in other_connected(far_end, duct_id):
        return r
    return None


def convert_to_flex(c_elem, duct, near_end, far_end, plan, flex_type, size, state):
    """Одна транзакция: жёсткий воздуховод (целиком или его ближняя часть) заменяется гибким."""
    p_a, p_b = near_end.Origin, far_end.Origin
    direction = p_b.Subtract(p_a).Normalize()
    system_id = system_type_id_for(duct, near_end)
    if system_id is None:
        raise ValueError(u'Не удалось определить тип системы воздуховода.')
    level_id = level_id_for(duct, p_a)
    if level_id is None:
        raise ValueError(u'В проекте нет уровней.')
    duct_id = duct.Id
    duct_key = eid_int(duct_id)
    hvac_log.log(TOOL, u'преобразование: тип {0}, размер {1}, режим {2}, расстояние {3:.0f} мм из {4:.0f} мм'.format(
        type_name(flex_type), hvac_sizes.label(size), plan['mode'], hvac_tail.ft_to_mm(plan['distance']),
        hvac_tail.ft_to_mm(p_a.DistanceTo(p_b))))
    started = time.time()
    t = DB.Transaction(doc, u'FlexTail: жёсткий воздуховод в гибкий')
    t.Start()
    try:
        if plan['mode'] == 'whole':
            neighbor = neighbor_of(far_end, duct_key)          # что было подключено к дальнему концу
            end_point = p_b
            doc.Delete(duct_id)
            far_target = neighbor
        else:
            end_point = p_a.Add(direction.Multiply(plan['distance']))
            new_id = DB.Mechanical.MechanicalUtils.BreakCurve(doc, duct_id, end_point)
            pieces = [doc.GetElement(duct_id), doc.GetElement(new_id)]
            pieces.sort(key=lambda d: min(x.Origin.DistanceTo(p_a) for x in element_connectors(d)))
            near_piece, far_piece = pieces[0], pieces[1]       # ближняя — та, чей конец лежит у элемента
            far_target = min(element_connectors(far_piece), key=lambda x: x.Origin.DistanceTo(end_point))
            doc.Delete(near_piece.Id)
        flex = create_flex(p_a, end_point, direction, flex_type.Id, system_id, level_id)
        apply_size(flex, size)
        apply_config_param(flex, state)
        connect_ends(flex, [c_elem, far_target])
        t.Commit()
        hvac_log.log(TOOL, u'создан гибкий воздуховод id {0}, {1} мс'.format(eid_int(flex.Id), hvac_log.elapsed_ms(started)))
    except Exception:
        t.RollBack()
        hvac_log.log_exception(TOOL, u'преобразование (транзакция откатана)')
        raise
    return flex


def main():
    types = flex_types()
    if not types:
        forms.alert(u'В проекте нет типов гибких воздуховодов.', title=u'FlexTail', exitscript=True)
    entries = [(type_name(t), type_shape(t), t) for t in types]
    by_name = dict((n, t) for n, _s, t in entries)
    entry_pairs = [(n, s) for n, s, _t in entries]
    cfg_flex = get_cfg(FLEX_SECTION)
    ctx = hvac_revit.app_context(doc)
    state = {'value': hvac_flex_settings.get_config_value(cfg_flex),
             'number': hvac_flex_settings.get_config_number(cfg_flex, ctx), 'learned': None, 'warnings': []}
    last_length = hvac_tail.get_last_length(get_cfg(TAIL_SECTION))
    last_type = load_last('flex_type')
    hvac_log.log(TOOL, u'типов гибких: {0}; «Гибкая конфигурация» = «{1}»; последняя длина {2} мм; журнал {3}'.format(
        len(types), state['value'], hvac_tail.format_mm(last_length), hvac_log.log_path()))

    prompt = (u'FlexTail · кликните по элементу, к которому подключён жёсткий воздуховод '
              u'(оборудование, арматура, соединительная деталь, воздухораспределитель); '
              u'будет взят коннектор, ближайший к клику (Esc — отменить)')
    while True:
        try:
            el, point = pick_element(prompt)
        except OperationCanceledException:
            hvac_log.log(TOOL, u'выбор отменён (Esc)')
            return
        c_elem, duct, dc, reason = resolve_start(el, point)
        if reason is not None:
            hvac_log.log(TOOL, u'элемент не подошёл: {0} id {1}: {2}'.format(
                category_name(el), eid_int(el.Id), reason.replace(u'\n', u' ')))
            forms.alert(reason, title=u'FlexTail')
            continue                                            # снова просим кликнуть; Esc — выход
        break

    near_end, far_end = duct_ends(duct, c_elem)
    size = connector_size(near_end)
    duct_ft = near_end.Origin.DistanceTo(far_end.Origin)
    duct_mm = hvac_tail.ft_to_mm(duct_ft)
    hvac_log.log(TOOL, u'воздуховод id {0}: {1}, длина {2:.0f} мм; от элемента {3} id {4}'.format(
        eid_int(duct.Id), hvac_sizes.label(size), duct_mm, category_name(el), eid_int(el.Id)))

    names = hvac_sizes.types_for_shape(entry_pairs, size.get('shape'))
    if not names:
        forms.alert(u'Нет типов гибкого воздуховода для формы «{0}».'.format(
            hvac_sizes.SHAPE_NAMES.get(size.get('shape'), u'?')), title=u'FlexTail')
        return
    info = u'Жёсткий воздуховод: {0}, длина {1} мм'.format(hvac_sizes.label(size), hvac_tail.format_mm(duct_mm))
    try:
        result = ask_length_and_type_window(sorted(names), last_type, last_length, info)
    except Exception:
        hvac_log.log_exception(TOOL, u'окно длины и типа не удалось, беру стандартные диалоги')
        result = ask_length_and_type_dialogs(sorted(names), last_type, last_length, info)
    if result is None:
        script.exit()
    length_mm, chosen = result
    hvac_tail.set_last_length(get_cfg(TAIL_SECTION), length_mm)
    save_last('flex_type', chosen)
    hvac_log.log(TOOL, u'выбрано: длина {0} мм, тип «{1}»'.format(hvac_tail.format_mm(length_mm), chosen))

    plan = hvac_tail.plan_tail(hvac_tail.mm_to_ft(length_mm), duct_ft)
    try:
        convert_to_flex(c_elem, duct, near_end, far_end, plan, by_name[chosen], size, state)
    except Exception as ex:
        if hvac_log.is_not_error(ex):
            raise
        hvac_log.log(TOOL, u'преобразование не удалось: {0}'.format(ex))
        forms.alert(u'Не удалось преобразовать воздуховод:\n{0}\n\nЖурнал: {1}'.format(ex, hvac_log.log_path()),
                    title=u'FlexTail')
        return
    note = hvac_tail.note_text(plan['note'], length_mm, duct_mm)
    if note:
        hvac_log.log(TOOL, u'сообщение пользователю: {0}'.format(note.replace(u'\n', u' ')))
        forms.alert(note, title=u'FlexTail')
    for w in sorted(set(state['warnings'])):
        script.get_output().print_md(u'* **Внимание:** {0}'.format(w))       # окно вывода — только когда есть что показать
    if state['learned'] is not None and state['learned'] != hvac_flex_settings.get_config_number(cfg_flex, ctx):
        hvac_flex_settings.set_config_number(cfg_flex, state['learned'], ctx)       # в следующий раз — без перебора
        script.save_config()


hvac_log.run(TOOL, main, doc)
