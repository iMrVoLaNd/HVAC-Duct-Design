# -*- coding: utf-8 -*-
"""Вікно налаштувань кнопки QuickFlexConnect (відкривається Shift+кліком по кнопці):
параметр «Гибкая конфигурация» (RBS_FLEX_PATTERN_PARAM; за замовчуванням значення «Гибкий») і перемикач «Цикл» (за замовчуванням вимкнено).
Тип гнучкого повітровода тут не налаштовується: його обирають після натискання кнопки."""
# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
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
    forms.alert(u'Не найден файл lib\\hvac_log.py.\nСкопируйте в расширение ВСЮ папку HVAC.extension вместе с lib '
                u'(все файлы) и перезагрузите pyRevit.\n\nИскал здесь: {0}'.format(_LIB),
                title=u'HVAC', exitscript=True)
TOOL = 'QuickFlexConnect_config'

try:
    from pyrevit import revit, DB, script

    import hvac_flex_settings
    import hvac_revit
    import hvac_ui
except Exception:
    hvac_log.log_exception(TOOL, u'імпорт модулів')
    raise

doc = revit.doc


class _LazyForms(object):
    """pyrevit.forms вантажимо лише при першому зверненні (див. script.py)."""

    def __getattr__(self, name):
        from pyrevit import forms as real_forms
        return getattr(real_forms, name)


forms = _LazyForms()
CONFIG_SECTION = hvac_flex_settings.SECTION
TITLE = u'QuickFlexConnect — настройки'
NO_CHANGE = u'(не менять параметр)'      # пункт списку: значення порожнє — параметр не чіпати


def settings_xaml():
    """XAML окна настроек в общем виде кнопок HVAC (hvac_ui)."""
    body = u'\n'.join((
        hvac_ui.label(u'Параметр гибкого воздуховода «Гибкая конфигурация»:'),
        u'      <TextBlock Style="{StaticResource Muted}" Text="(можно только выбрать из списка)" Margin="0,0,0,6"/>',
        u'      <ComboBox x:Name="param_value" IsEditable="False" Margin="0,0,0,14"/>',
        u'      <CheckBox x:Name="pick_type" Content="Тип с образца" Margin="0,0,0,8"',
        u'                ToolTip="Вместо выбора типа из списка: клик по гибкому воздуховоду в модели, тип берётся с него"/>',
        u'      <CheckBox x:Name="loop" Content="Цикл" Margin="0,0,0,16"',
        u'                ToolTip="Строить пары подряд, пока не нажат Esc"/>',
        hvac_ui.buttons(u'save_btn', u'Сохранить')))
    return hvac_ui.window_xaml(TITLE, 460, body)


def read_options():
    """Варіанти параметра «Гибкая конфигурация» з проєкту: [(число, текст), ...]. Перебір значень у транзакції,
    яку відкочуємо. Береться перший гнучкий повітровод (або тип) із цим параметром. Немає такого — порожній список."""
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
                hvac_log.log(TOOL, u'варіанти параметра: {0}'.format(
                    u'; '.join(u'{0}={1}'.format(n, text) for n, text in options) or u'(не найдено)'))
                return options
    except Exception:
        hvac_log.log_exception(TOOL, u'читання варіантів параметра (не критично)')
    return []


def choices_for(value, options):
    """Пункти списку: «не змінювати» + варіанти параметра з проєкту. Своє значення вводити не можна: якщо варіантів
    прочитати не вдалося, у списку лишається збережене значення (за замовчуванням «Гибкий»)."""
    items = [NO_CHANGE] + list(options)
    if not options and value:
        items.append(value)
    return items


def selected_for(value, items):
    """Що показати вибраним: збережене значення, інакше «Гибкий», інакше «не змінювати»."""
    if not value:
        return NO_CHANGE
    if value in items:
        return value
    if hvac_flex_settings.DEFAULT_CONFIG_VALUE in items:
        return hvac_flex_settings.DEFAULT_CONFIG_VALUE
    return NO_CHANGE


def ask_with_window(value, loop, options, pick_type):
    """Власне WPF-вікно: значення параметра, галочка «Цикл», кнопки «Зберегти» / «Скасувати».
    Повертає (значення, цикл, тип з моделі) або None, якщо вікно закрито без збереження."""

    class SettingsWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, settings_xaml(), literal_string=True)
            self.result = None
            combo = self.FindName('param_value')
            items = choices_for(value, options)
            for item in items:
                combo.Items.Add(item)
            combo.SelectedItem = selected_for(value, items)
            self.FindName('loop').IsChecked = bool(loop)
            self.FindName('pick_type').IsChecked = bool(pick_type)
            self.FindName('save_btn').Click += self.on_save

        def on_save(self, sender, args):
            chosen = self.FindName('param_value').SelectedItem
            self.result = (u'' if chosen in (None, NO_CHANGE) else chosen, bool(self.FindName('loop').IsChecked),
                           bool(self.FindName('pick_type').IsChecked))
            self.Close()

    win = SettingsWindow()
    win.ShowDialog()
    return win.result


def ask_with_dialogs(value, loop, options, pick_type):
    """Запасний варіант на стандартних діалогах pyRevit — якщо власне вікно не вдалося створити."""
    items = choices_for(value, options)
    current = selected_for(value, items)
    ordered = [current] + [i for i in items if i != current]
    picked = forms.SelectFromList.show(ordered, title=u'«Гибкая конфигурация» (сейчас: «{0}»)'.format(current),
                                       button_name=u'Далее', multiselect=False)
    if not picked:
        return None
    loop_on = forms.alert(u'Режим «Цикл» (пары подряд, пока не нажат Esc).\nСейчас: {0}.\n\nВключить?'
                          .format(u'включён' if loop else u'выключен'), title=TITLE, yes=True, no=True)
    from_model = forms.alert(u'Брать тип гибкого воздуховода с гибкого воздуховода в модели (клик) вместо списка?\n'
                             u'Сейчас: {0}.'.format(u'да' if pick_type else u'нет'), title=TITLE, yes=True, no=True)
    return (u'' if picked == NO_CHANGE else picked), bool(loop_on), bool(from_model)


def main():
    cfg = script.get_config(CONFIG_SECTION)
    value = hvac_flex_settings.get_config_value(cfg)
    loop = hvac_flex_settings.is_loop(cfg)
    pick_type = hvac_flex_settings.is_type_from_model(cfg)

    pairs = read_options()
    options = [text for _num, text in pairs]
    try:
        result = ask_with_window(value, loop, options, pick_type)
    except Exception:
        hvac_log.log_exception(TOOL, u'вікно налаштувань (WPF) не вдалося, беру стандартні діалоги')
        result = ask_with_dialogs(value, loop, options, pick_type)
    if result is None:                        # вікно закрито без збереження — нічого не змінюємо
        hvac_log.log(TOOL, u'налаштування не змінено')
        script.exit()
    number = dict((text, num) for num, text in pairs).get(result[0])      # число варіанта — щоб кнопка не перебирала його щоразу
    hvac_flex_settings.set_config_value(cfg, result[0], number, hvac_revit.app_context(doc))
    hvac_flex_settings.set_loop(cfg, result[1])
    hvac_flex_settings.set_type_from_model(cfg, result[2])
    script.save_config()
    hvac_log.log(TOOL, u'збережено: «Гибкая конфигурация» = «{0}» (число {1}), цикл {2}, тип з моделі {3}'.format(
        result[0], number, result[1], result[2]))


hvac_log.run(TOOL, main, doc)
