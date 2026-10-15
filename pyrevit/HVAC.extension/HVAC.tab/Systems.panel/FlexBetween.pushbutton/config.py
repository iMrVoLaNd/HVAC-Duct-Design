# -*- coding: utf-8 -*-
"""Вікно налаштувань кнопки «Гнучкий між конекторами» (відкривається Shift+кліком по кнопці):
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
    forms.alert(u'Не знайдено файл lib\\hvac_log.py.\nСкопіюйте в розширення ВСЮ папку HVAC.extension разом із lib '
                u'(усі файли) і перезавантажте pyRevit.\n\nШукав тут: {0}'.format(_LIB),
                title=u'HVAC', exitscript=True)
TOOL = 'flex_between_config'

try:
    from pyrevit import revit, DB, forms, script

    import hvac_flex_settings
    import hvac_revit
except Exception:
    hvac_log.log_exception(TOOL, u'імпорт модулів')
    raise

doc = revit.doc
CONFIG_SECTION = hvac_flex_settings.SECTION
TITLE = u'Гнучкий повітровод — налаштування'
NO_CHANGE = u'(не змінювати параметр)'      # пункт списку: значення порожнє — параметр не чіпати


XAML = u"""
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Гнучкий повітровод — налаштування" Width="440" SizeToContent="Height"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize" ShowInTaskbar="False">
  <StackPanel Margin="16">
    <TextBlock Text="Параметр «Гибкая конфигурация» (RBS_FLEX_PATTERN_PARAM) — значення:" Margin="0,0,0,4"/>
    <TextBlock Text="(можна лише обрати зі списку)" Margin="0,0,0,4" Opacity="0.6"/>
    <ComboBox x:Name="param_value" IsEditable="False" Margin="0,0,0,14"/>
    <CheckBox x:Name="loop" Content="Цикл: будувати пари поспіль, поки не натиснуто Esc" Margin="0,0,0,16"/>
    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
      <Button x:Name="save_btn" Content="Зберегти" Width="100" Margin="0,0,8,0" IsDefault="True"/>
      <Button x:Name="cancel_btn" Content="Скасувати" Width="100" IsCancel="True"/>
    </StackPanel>
  </StackPanel>
</Window>
"""


def read_options():
    """Варіанти параметра «Гибкая конфигурация» з проєкту: перебір значень у транзакції, яку відкочуємо.
    Береться перший гнучкий повітровод (або тип) із цим параметром. Немає такого — порожній список."""
    try:
        for cls in (DB.Mechanical.FlexDuct, DB.Mechanical.FlexDuctType):
            for el in DB.FilteredElementCollector(doc).OfClass(cls):
                p = hvac_revit.find_param(DB, el, hvac_flex_settings.BUILTIN_PARAM,
                                          hvac_flex_settings.FALLBACK_PARAM_NAME)
                if p is None or p.StorageType != DB.StorageType.Integer:
                    continue
                t = DB.Transaction(doc, u'Варіанти параметра (відкат)')
                t.Start()
                try:
                    options = [text for _num, text in hvac_revit.enum_options(p, refresh=doc.Regenerate)]
                finally:
                    t.RollBack()
                hvac_log.log(TOOL, u'варіанти параметра: {0}'.format(u'; '.join(options) or u'(не знайдено)'))
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


def ask_with_window(value, loop, options):
    """Власне WPF-вікно: значення параметра, галочка «Цикл», кнопки «Зберегти» / «Скасувати».
    Повертає (значення, цикл) або None, якщо вікно закрито без збереження."""

    class SettingsWindow(forms.WPFWindow):
        def __init__(self):
            forms.WPFWindow.__init__(self, XAML, literal_string=True)
            self.result = None
            combo = self.FindName('param_value')
            items = choices_for(value, options)
            for item in items:
                combo.Items.Add(item)
            combo.SelectedItem = selected_for(value, items)
            self.FindName('loop').IsChecked = bool(loop)
            self.FindName('save_btn').Click += self.on_save

        def on_save(self, sender, args):
            chosen = self.FindName('param_value').SelectedItem
            self.result = (u'' if chosen in (None, NO_CHANGE) else chosen, bool(self.FindName('loop').IsChecked))
            self.Close()

    win = SettingsWindow()
    win.ShowDialog()
    return win.result


def ask_with_dialogs(value, loop, options):
    """Запасний варіант на стандартних діалогах pyRevit — якщо власне вікно не вдалося створити."""
    items = choices_for(value, options)
    current = selected_for(value, items)
    ordered = [current] + [i for i in items if i != current]
    picked = forms.SelectFromList.show(ordered, title=u'«Гибкая конфигурация» (зараз: «{0}»)'.format(current),
                                       button_name=u'Далі', multiselect=False)
    if not picked:
        return None
    loop_on = forms.alert(u'Режим «Цикл» (пари поспіль, поки не натиснуто Esc).\nЗараз: {0}.\n\nУвімкнути?'
                          .format(u'увімкнено' if loop else u'вимкнено'), title=TITLE, yes=True, no=True)
    return (u'' if picked == NO_CHANGE else picked), bool(loop_on)


def main():
    cfg = script.get_config(CONFIG_SECTION)
    value = hvac_flex_settings.get_config_value(cfg)
    loop = hvac_flex_settings.is_loop(cfg)

    options = read_options()
    try:
        result = ask_with_window(value, loop, options)
    except Exception:
        hvac_log.log_exception(TOOL, u'вікно налаштувань (WPF) не вдалося, беру стандартні діалоги')
        result = ask_with_dialogs(value, loop, options)
    if result is None:                        # вікно закрито без збереження — нічого не змінюємо
        hvac_log.log(TOOL, u'налаштування не змінено')
        script.exit()
    hvac_flex_settings.set_config_value(cfg, result[0])
    hvac_flex_settings.set_loop(cfg, result[1])
    script.save_config()
    hvac_log.log(TOOL, u'збережено: «Гибкая конфигурация» = «{0}», цикл {1}'.format(result[0], result[1]))


hvac_log.run(TOOL, main, doc)
