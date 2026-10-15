# -*- coding: utf-8 -*-
"""Вікно налаштувань кнопки «Гнучкий між конекторами» (відкривається Shift+кліком по кнопці):
тип гнучкого повітровода (за замовчуванням «Гибкий») і перемикач «Цикл» (за замовчуванням вимкнено)."""
# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
from pyrevit import revit, DB, forms, script

import hvac_flex_settings

doc = revit.doc
CONFIG_SECTION = hvac_flex_settings.SECTION
TITLE = u'Гнучкий повітровод — налаштування'


def type_name(t):
    return DB.Element.Name.GetValue(t)


def main():
    cfg = script.get_config(CONFIG_SECTION)
    names = sorted(type_name(t) for t in DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType))
    if not names:
        forms.alert(u'У проєкті немає типів гнучких повітроводів.', title=TITLE, exitscript=True)
    current = hvac_flex_settings.get_flex_type(cfg)
    idx = hvac_flex_settings.find_type_index(names, current)
    default = names[idx if idx is not None else 0]

    components = [
        forms.Label(u'Тип гнучкого повітровода:'),
        forms.ComboBox('flex_type', names, default=default),
        forms.Separator(),
        forms.CheckBox('loop', u'Цикл: будувати пари поспіль, поки не натиснуто Esc',
                       default=hvac_flex_settings.is_loop(cfg)),
        forms.Separator(),
        forms.Button(u'Зберегти'),
    ]
    form = forms.FlexForm(TITLE, components)
    form.show()
    values = form.values
    if not values:                            # вікно закрито хрестиком — нічого не змінюємо
        script.exit()
    hvac_flex_settings.set_flex_type(cfg, values['flex_type'])
    hvac_flex_settings.set_loop(cfg, bool(values['loop']))
    script.save_config()


main()
