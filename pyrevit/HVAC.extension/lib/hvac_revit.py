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


def find_param(DB, el, builtin_name, fallback_name):
    """Параметр елемента: спершу вбудований (BuiltInParameter, не залежить від мови Revit), потім за назвою."""
    bip = getattr(DB.BuiltInParameter, builtin_name, None)
    if bip is not None:
        p = el.get_Parameter(bip)
        if p is not None:
            return p
    return el.LookupParameter(fallback_name)


def enum_options(p, limit=32, refresh=None, max_misses=4):
    """Варіанти параметра-списку (ціле число, а на екрані текст): [(число, текст), ...].

    Перебираємо числа 0..limit-1, записуємо кожне й читаємо текст (AsValueString); порожні й повторні тексти —
    «промахи», після max_misses поспіль зупиняємось. Значення, що було, повертаємо назад.
    Викликати треба всередині транзакції (її потім відкочують, якщо значення не мають залишитись)."""
    try:
        original = p.AsInteger()
    except Exception:
        original = None
    found, seen, misses = [], set(), 0
    for i in range(limit):
        text = u''
        try:
            if p.Set(i):
                if refresh is not None:
                    refresh()
                text = (p.AsValueString() or u'').strip()
        except Exception:
            text = u''
        if not text or text in seen:
            misses += 1
            if misses >= max_misses:
                break
            continue
        misses = 0
        seen.add(text)
        found.append((i, text))
    if original is not None:
        try:
            p.Set(original)
        except Exception:
            pass
    return found


def set_enum_by_text(p, text, refresh=None):
    """Записати в параметр-список варіант за його текстом («Гибкий»); True, якщо такий варіант знайдено."""
    wanted = text.strip().lower()
    for number, label in enum_options(p, refresh=refresh):
        if label.lower() == wanted:
            return bool(p.Set(number))
    return False
