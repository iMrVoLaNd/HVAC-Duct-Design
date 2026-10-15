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


# ---------- параметр «Гибкая конфигурация» ----------
# Після побудови гнучкого повітровода кнопка записує значення в цей параметр (спершу шукає його в екземплярі,
# потім у типі). Порожнє значення — параметр не чіпати. Тип гнучкого повітровода обирається при кожному запуску кнопки.

CONFIG_PARAM_KEY = 'config_param'
CONFIG_VALUE_KEY = 'config_value'
DEFAULT_CONFIG_PARAM = u'Гибкая конфигурация'
DEFAULT_CONFIG_VALUE = u'Гибкий'


def _text_option(cfg, key, default):
    try:
        value = cfg.get_option(key, None)
    except Exception:
        value = None
    return default if value is None else value


def get_config_param(cfg):
    """Ім'я параметра; порожнє в налаштуваннях = значення за замовчуванням."""
    return _text_option(cfg, CONFIG_PARAM_KEY, DEFAULT_CONFIG_PARAM).strip() or DEFAULT_CONFIG_PARAM


def get_config_value(cfg):
    """Значення параметра; НЕ підставляємо default для порожнього (порожнє = «не чіпати параметр»)."""
    return _text_option(cfg, CONFIG_VALUE_KEY, DEFAULT_CONFIG_VALUE).strip()


def set_config(cfg, name, value):
    cfg.set_option(CONFIG_PARAM_KEY, name.strip())
    cfg.set_option(CONFIG_VALUE_KEY, value.strip())
