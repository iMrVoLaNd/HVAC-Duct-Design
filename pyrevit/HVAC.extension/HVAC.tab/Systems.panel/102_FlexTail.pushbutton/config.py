# -*- coding: utf-8 -*-
"""Окно настроек кнопки FlexTail (открывается Shift+кликом по кнопке). Настройки у кнопки свои и хранятся в её
собственной секции конфигурации (flex_tail), независимо от других кнопок:
  * параметр «Гибкая конфигурация» (RBS_FLEX_PATTERN_PARAM; по умолчанию «Гибкий») — значение для созданного гибкого;
  * длина гибкого участка по умолчанию (мм; по умолчанию 500);
  * запоминать ли последнюю введённую длину (по умолчанию да).
Тип гибкого воздуховода здесь не настраивается: его выбирают при каждом запуске."""
# Совместимо с IronPython 3.4 (pyRevit) и CPython: без f-строк и современного синтаксиса.
import os
import sys

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
TOOL = 'FlexTail_config'
hvac_log.configure(os.path.dirname(os.path.abspath(__file__)), 'FlexTail')       # журнал — в папке этой кнопки

try:
    from pyrevit import revit, DB, script

    import hvac_flex_settings
    import hvac_revit
    import hvac_settings
    import hvac_tail
    import hvac_ui
except Exception:
    hvac_log.log_exception(TOOL, u'импорт модулей')
    raise

doc = revit.doc


class _LazyForms(object):
    """pyrevit.forms грузим только при первом обращении (см. script.py)."""

    def __getattr__(self, name):
        from pyrevit import forms as real_forms
        return getattr(real_forms, name)


forms = _LazyForms()
CONFIG_SECTION = hvac_tail.SECTION      # старая секция pyRevit: из неё один раз переносим настройки в settings.ini
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_KEYS = ('config_value', 'config_value_num', 'config_value_ctx', 'length_mm', 'default_length_mm',
               'remember_length', 'flex_type')
TITLE = u'FlexTail — настройки'
NO_CHANGE = u'(не менять параметр)'      # пункт списка: значение пустое — параметр не трогать
BAD_LENGTH = u'Введите длину в миллиметрах: число от {0} до {1}.'.format(
    hvac_tail.format_mm(hvac_tail.MIN_LENGTH_MM), hvac_tail.format_mm(hvac_tail.MAX_LENGTH_MM))


def settings_xaml():
    body = u'\n'.join((
        hvac_ui.label(u'Параметр гибкого воздуховода «Гибкая конфигурация»:'),
        u'      <TextBlock Style="{StaticResource Muted}" Text="(можно только выбрать из списка)" Margin="0,0,0,6"/>',
        u'      <ComboBox x:Name="param_value" IsEditable="False" Margin="0,0,0,14"/>',
        hvac_ui.label(u'Длина гибкого участка по умолчанию, мм:'),
        u'      <TextBox x:Name="default_length" Margin="0,0,0,14"/>',
        u'      <CheckBox x:Name="remember" Content="Запоминать последнюю введённую длину" Margin="0,0,0,16"',
        u'                ToolTip="Включено: в окне подставляется последняя длина. Выключено: всегда длина по умолчанию."/>',
        hvac_ui.buttons(u'save_btn', u'Сохранить')))
    return hvac_ui.window_xaml(TITLE, 460, body)


def read_options():
    """Варианты параметра «Гибкая конфигурация» из проекта: [(число, текст), ...]. Перебор значений в транзакции,
    которую откатываем. Берётся первый гибкий воздуховод (или тип) с этим параметром. Нет такого — пустой список."""
    try:
        for cls in (DB.Mechanical.FlexDuct, DB.Mechanical.FlexDuctType):
            for el in DB.FilteredElementCollector(doc).OfClass(cls):
                p = hvac_revit.find_param(DB, el, hvac_flex_settings.BUILTIN_PARAM,
                                          hvac_flex_settings.FALLBACK_PARAM_NAME)
                if p is None or p.StorageType != DB.StorageType.Integer:
                    continue
                t = DB.Transaction(doc, u'Варианты параметра (откат)')
                t.Start()
                try:
                    options = hvac_revit.enum_options(p, refresh=doc.Regenerate)
                finally:
                    t.RollBack()
                hvac_log.log(TOOL, u'варианты параметра: {0}'.format(
                    u'; '.join(u'{0}={1}'.format(n, text) for n, text in options) or u'(не найдено)'))
                return options
    except Exception:
        hvac_log.log_exception(TOOL, u'чтение вариантов параметра (не критично)')
    return []


def choices_for(value, options):
    """Пункты списка: «не менять» + варианты параметра из проекта. Своё значение вводить нельзя: если варианты
    прочитать не удалось, в списке остаётся сохранённое значение (по умолчанию «Гибкий»)."""
    items = [NO_CHANGE] + list(options)
    if not options and value:
        items.append(value)
    return items


def selected_for(value, items):
    """Что показать выбранным: сохранённое значение, иначе «Гибкий», иначе «не менять»."""
    if not value:
        return NO_CHANGE
    if value in items:
        return value
    if hvac_flex_settings.DEFAULT_CONFIG_VALUE in items:
        return hvac_flex_settings.DEFAULT_CONFIG_VALUE
    return NO_CHANGE


def ask_with_window(value, default_length, remember, options):
    """Своё WPF-окно. Возвращает (значение, длина по умолчанию мм, запоминать) или None, если закрыто без сохранения.
    Неверная длина — сообщение, окно остаётся открытым."""

    class SettingsWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, settings_xaml(), literal_string=True)
            hvac_ui.enable_drag(self)
            self.result = None
            combo = self.FindName('param_value')
            items = choices_for(value, options)
            for item in items:
                combo.Items.Add(item)
            combo.SelectedItem = selected_for(value, items)
            self.FindName('default_length').Text = hvac_tail.format_mm(default_length)
            self.FindName('remember').IsChecked = bool(remember)
            self.FindName('save_btn').Click += self.on_save

        def on_save(self, sender, args):
            mm = hvac_tail.parse_length_mm(self.FindName('default_length').Text)
            if mm is None:
                forms.alert(BAD_LENGTH, title=TITLE)
                return                                     # окно остаётся открытым
            chosen = self.FindName('param_value').SelectedItem
            self.result = (u'' if chosen in (None, NO_CHANGE) else chosen, mm,
                           bool(self.FindName('remember').IsChecked))
            self.Close()

    win = SettingsWindow()
    win.ShowDialog()
    return win.result


def ask_with_dialogs(value, default_length, remember, options):
    """Запасной вариант на стандартных диалогах pyRevit — если своё окно создать не удалось."""
    items = choices_for(value, options)
    current = selected_for(value, items)
    ordered = [current] + [i for i in items if i != current]
    picked = forms.SelectFromList.show(ordered, title=u'«Гибкая конфигурация» (сейчас: «{0}»)'.format(current),
                                       button_name=u'Далее', multiselect=False)
    if not picked:
        return None
    mm = None
    while mm is None:
        text = forms.ask_for_string(default=hvac_tail.format_mm(default_length),
                                    prompt=u'Длина гибкого участка по умолчанию, мм:', title=TITLE)
        if text is None:
            return None
        mm = hvac_tail.parse_length_mm(text)
        if mm is None:
            forms.alert(BAD_LENGTH, title=TITLE)
    keep = forms.alert(u'Запоминать последнюю введённую длину?\nСейчас: {0}.'.format(u'да' if remember else u'нет'),
                       title=TITLE, yes=True, no=True)
    return (u'' if picked == NO_CHANGE else picked), mm, bool(keep)


def main():
    cfg = hvac_settings.load(PLUGIN_DIR, legacy=lambda: script.get_config(CONFIG_SECTION), legacy_keys=LEGACY_KEYS)
    value = hvac_flex_settings.get_config_value(cfg)
    default_length = hvac_tail.get_default_length(cfg)
    remember = hvac_tail.is_remember(cfg)

    pairs = read_options()
    options = [text for _num, text in pairs]
    try:
        result = ask_with_window(value, default_length, remember, options)
    except Exception:
        hvac_log.log_exception(TOOL, u'окно настроек (WPF) не удалось, беру стандартные диалоги')
        result = ask_with_dialogs(value, default_length, remember, options)
    if result is None:                        # окно закрыто без сохранения — ничего не меняем
        hvac_log.log(TOOL, u'настройки не изменены')
        script.exit()
    number = dict((text, num) for num, text in pairs).get(result[0])      # число варианта — чтобы кнопка не перебирала его
    hvac_flex_settings.set_config_value(cfg, result[0], number, hvac_revit.app_context(doc))
    hvac_tail.set_default_length(cfg, result[1])
    hvac_tail.set_remember(cfg, result[2])
    if not cfg.save():
        forms.alert(u'Не удалось записать файл настроек:\n{0}'.format(cfg.path), title=TITLE)
    hvac_log.log(TOOL, u'сохранено: «Гибкая конфигурация» = «{0}» (число {1}), длина по умолчанию {2} мм, запоминать {3}'.format(
        result[0], number, hvac_tail.format_mm(result[1]), result[2]))


hvac_log.run(TOOL, main, doc)
