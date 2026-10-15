# -*- coding: utf-8 -*-
"""Дрібні допоміжні функції для Revit API, однакові в усіх кнопках.

Сумісно з IronPython 3.4 і CPython (без f-рядків)."""


def element_name(DB, el):
    """Ім'я елемента/типу (Element.Name).

    У IronPython 3 старий прийом DB.Element.Name.GetValue(el) не працює (Name — getset_descriptor без GetValue),
    а у IronPython 2 для типів інколи треба саме його. Тому пробуємо по черзі; якщо жоден спосіб не вдався —
    піднімаємо першу (найінформативнішу) помилку."""
    first = None
    try:
        return el.Name
    except Exception as ex:
        first = ex
    prop = DB.Element.Name
    for attempt in (lambda: prop.__get__(el, type(el)), lambda: prop.GetValue(el)):
        try:
            return attempt()
        except Exception:
            pass
    raise first
