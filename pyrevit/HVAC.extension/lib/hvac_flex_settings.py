# -*- coding: utf-8 -*-
"""Налаштування кнопок «Гнучкий між конекторами»: режим циклу (за замовчуванням ВИМКНЕНО).

Не залежить від Revit: працює з об'єктом конфігурації pyRevit (script.get_config(...)) і лише
читає/пише параметр 'loop' текстом 'true'/'false'. Сумісно з IronPython 3.4 і CPython.
"""

SECTION = 'flex_between'
LOOP_KEY = 'loop'


def _truthy(value):
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def is_loop(cfg):
    """Чи ввімкнено цикл. Будь-яка помилка читання = вимкнено (безпечне значення за замовчуванням)."""
    try:
        return _truthy(cfg.get_option(LOOP_KEY, 'false'))
    except Exception:
        return False


def set_loop(cfg, value):
    cfg.set_option(LOOP_KEY, 'true' if value else 'false')


# ---------- тип гнучкого повітровода ----------

FLEX_TYPE_KEY = 'flex_type'
DEFAULT_FLEX_TYPE = u'Гибкий'         # назва типу за замовчуванням (як у шаблоні проєкту)


def get_flex_type(cfg):
    """Назва типу з налаштувань; якщо нічого не збережено — DEFAULT_FLEX_TYPE."""
    try:
        value = cfg.get_option(FLEX_TYPE_KEY, u'')
    except Exception:
        value = u''
    return value if value else DEFAULT_FLEX_TYPE


def set_flex_type(cfg, name):
    cfg.set_option(FLEX_TYPE_KEY, name)


def find_type_index(names, wanted):
    """Індекс типу за назвою: точний збіг, потім без урахування регістру, потім за початком назви.
    Не знайдено — None (тоді кнопка покаже список)."""
    if not wanted:
        return None
    for i, n in enumerate(names):
        if n == wanted:
            return i
    low = wanted.strip().lower()
    for i, n in enumerate(names):
        if n.strip().lower() == low:
            return i
    for i, n in enumerate(names):
        if n.strip().lower().startswith(low):
            return i
    return None
