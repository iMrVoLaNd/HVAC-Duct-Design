# -*- coding: utf-8 -*-
"""Налаштування кнопки «Гнучкий між конекторами» (відкривається Shift+кліком по кнопці)."""
# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
from pyrevit import revit, DB, forms, script

import hvac_flex_settings

doc = revit.doc
CONFIG_SECTION = hvac_flex_settings.SECTION


def type_name(t):
    return DB.Element.Name.GetValue(t)


def main():
    cfg = script.get_config(CONFIG_SECTION)
    names = sorted(type_name(t) for t in DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType))
    if not names:
        forms.alert(u'У проєкті немає типів гнучких повітроводів.', title=u'Налаштування: гнучкий повітровод',
                    exitscript=True)
    current = hvac_flex_settings.get_flex_type(cfg)
    idx = hvac_flex_settings.find_type_index(names, current)
    if idx is not None:                       # поточний тип — першим у списку
        names.insert(0, names.pop(idx))
    picked = forms.SelectFromList.show(
        names, title=u'Тип гнучкого повітровода (зараз: «{0}»)'.format(current),
        button_name=u'Зберегти', multiselect=False)
    if not picked:
        script.exit()
    hvac_flex_settings.set_flex_type(cfg, picked)
    script.save_config()
    forms.alert(u'Збережено: «{0}».\nКнопка «Гнучкий між конекторами» тепер будує цим типом без запитань.'
                .format(picked), title=u'Налаштування: гнучкий повітровод')


main()
