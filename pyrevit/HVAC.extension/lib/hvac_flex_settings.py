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


# ---------- параметр «Гибкая конфигурация» (BuiltInParameter.RBS_FLEX_PATTERN_PARAM) ----------
# Після побудови гнучкого повітровода кнопка записує це значення в параметр (спершу шукає його в екземплярі, потім
# у типі). Порожнє значення — параметр не чіпати. Тип гнучкого повітровода обирається при кожному запуску кнопки.

CONFIG_VALUE_KEY = 'config_value'
DEFAULT_CONFIG_VALUE = u'Гибкий'
BUILTIN_PARAM = 'RBS_FLEX_PATTERN_PARAM'       # BuiltInParameter, не залежить від мови Revit
FALLBACK_PARAM_NAME = u'Гибкая конфигурация'   # якщо вбудованого параметра не знайдено — шукаємо за назвою


def get_config_value(cfg):
    """Значення параметра; порожнє зберігається порожнім (= «не чіпати параметр»)."""
    try:
        value = cfg.get_option(CONFIG_VALUE_KEY, None)
    except Exception:
        value = None
    return DEFAULT_CONFIG_VALUE if value is None else value.strip()


CONFIG_NUMBER_KEY = 'config_value_num'


def get_config_number(cfg):
    """Число, що відповідає збереженому значенню-тексту (щоб не перебирати варіанти щоразу); None — невідомо."""
    try:
        raw = cfg.get_option(CONFIG_NUMBER_KEY, '')
        return int(str(raw).strip()) if str(raw).strip() != '' else None
    except Exception:
        return None


def set_config_value(cfg, value, number=None):
    """Зберегти значення (текст) і, якщо відоме, відповідне число; без числа старе число стирається."""
    cfg.set_option(CONFIG_VALUE_KEY, value.strip())
    cfg.set_option(CONFIG_NUMBER_KEY, '' if number is None else str(int(number)))


def set_config_number(cfg, number):
    """Запам'ятати число для вже збереженого значення (кнопка сама дізналась його при першому запису)."""
    cfg.set_option(CONFIG_NUMBER_KEY, str(int(number)))
