# -*- coding: utf-8 -*-
"""Налаштування кнопки QuickFlexConnect: режим циклу (за замовчуванням ВИМКНЕНО).

Не залежить від Revit: працює з об'єктом налаштувань кнопки (hvac_settings.load(...) або script.get_config(...)) і лише
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


# ---------- звідки брати тип гнучкого повітровода ----------
# За замовчуванням тип обирається у вікні зі списку. Якщо ввімкнено — після вибору двох елементів кнопка просить
# клацнути на будь-який гнучкий повітровод у моделі й бере тип з нього.

TYPE_FROM_MODEL_KEY = 'type_from_model'


def is_type_from_model(cfg):
    try:
        return _truthy(cfg.get_option(TYPE_FROM_MODEL_KEY, 'false'))
    except Exception:
        return False


def set_type_from_model(cfg, value):
    cfg.set_option(TYPE_FROM_MODEL_KEY, 'true' if value else 'false')


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
CONFIG_CTX_KEY = 'config_value_ctx'


def get_config_number(cfg, ctx=None):
    """Число, що відповідає збереженому значенню-тексту (щоб не перебирати варіанти щоразу); None — невідомо.

    ctx — «відбиток» середовища (версія Revit і мова): число діє лише в тому середовищі, де його дізнались, інакше
    None і кнопка знову визначить його перебором. ctx=None — без перевірки."""
    try:
        raw = cfg.get_option(CONFIG_NUMBER_KEY, '')
        if str(raw).strip() == '':
            return None
        if ctx is not None and str(cfg.get_option(CONFIG_CTX_KEY, '')) != ctx:
            return None
        return int(str(raw).strip())
    except Exception:
        return None


def set_config_value(cfg, value, number=None, ctx=None):
    """Зберегти значення (текст) і, якщо відоме, відповідне число; без числа старе число стирається."""
    cfg.set_option(CONFIG_VALUE_KEY, value.strip())
    cfg.set_option(CONFIG_NUMBER_KEY, '' if number is None else str(int(number)))
    cfg.set_option(CONFIG_CTX_KEY, '' if ctx is None else ctx)


def set_config_number(cfg, number, ctx=None):
    """Запам'ятати число для вже збереженого значення (кнопка сама дізналась його при першому запису)."""
    cfg.set_option(CONFIG_NUMBER_KEY, str(int(number)))
    cfg.set_option(CONFIG_CTX_KEY, '' if ctx is None else ctx)
