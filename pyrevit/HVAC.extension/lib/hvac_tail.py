# -*- coding: utf-8 -*-
"""FlexTail: длина гибкого участка — ввод, запоминание, план разреза воздуховода. Без зависимости от Revit.

Длины в окне — в миллиметрах, внутри Revit — в футах. Совместимо с IronPython 3.4 и CPython (без f-строк)."""

FT_TO_MM = 304.8
MIN_LEN_FT = 1.0 / 10.0 / 12.0       # Revit не строит MEP-кривые короче 1/10 дюйма
TOLERANCE_FT = 1.0 / FT_TO_MM        # 1 мм: разницу меньше миллиметра считаем равенством

DEFAULT_LENGTH_MM = 500
CHIPS_MM = (300, 500, 1000, 1500, 2000, 2500)      # быстрые значения в окне
MIN_LENGTH_MM = 5.0                                # короче не принимаем (Revit не построит и 2,5 мм)
MAX_LENGTH_MM = 50000.0

LENGTH_KEY = 'length_mm'


def mm_to_ft(mm):
    return mm / FT_TO_MM


def ft_to_mm(ft):
    return ft * FT_TO_MM


def format_mm(value):
    """Миллиметры без лишних нулей: 500 → «500», 1234.5 → «1234.5»."""
    text = '{0:.1f}'.format(float(value))
    return text[:-2] if text.endswith('.0') else text


def parse_length_mm(text):
    """Длина из текста окна («500», «1 250,5», «750 мм»). Возвращает миллиметры или None, если ввод не подходит
    (пусто, не число, меньше MIN_LENGTH_MM, больше MAX_LENGTH_MM)."""
    try:
        cleaned = str(text).strip().lower()
        for junk in (u'мм', u'mm', u' ', u' '):
            cleaned = cleaned.replace(junk, u'')
        value = float(cleaned.replace(u',', u'.'))
    except (ValueError, TypeError):
        return None
    if value != value or value < MIN_LENGTH_MM or value > MAX_LENGTH_MM:       # value != value: NaN
        return None
    return value


def get_last_length(cfg):
    """Последняя введённая длина (мм); нет сохранённой или она испорчена — DEFAULT_LENGTH_MM."""
    try:
        value = parse_length_mm(cfg.get_option(LENGTH_KEY, u''))
    except Exception:
        value = None
    return DEFAULT_LENGTH_MM if value is None else value


def set_last_length(cfg, mm):
    cfg.set_option(LENGTH_KEY, format_mm(mm))


def plan_tail(length_ft, duct_ft, min_ft=MIN_LEN_FT):
    """Как поступить с жёстким воздуховодом длиной duct_ft, если гибким нужно сделать length_ft от элемента.

    Возвращает {'mode': 'split' | 'whole', 'distance': футы от элемента до места разреза (для 'whole' — вся длина),
    'note': None | 'short' | 'leftover'}:
      * 'split'  — режем на расстоянии length_ft, ближний кусок становится гибким;
      * 'whole'  — гибким становится весь воздуховод; 'short' — он короче заданной длины, 'leftover' — разрез
        оставил бы жёсткий кусок короче минимума, который Revit может построить."""
    if length_ft >= duct_ft - TOLERANCE_FT:
        return {'mode': 'whole', 'distance': duct_ft, 'note': 'short' if length_ft > duct_ft + TOLERANCE_FT else None}
    if duct_ft - length_ft < min_ft:
        return {'mode': 'whole', 'distance': duct_ft, 'note': 'leftover'}
    return {'mode': 'split', 'distance': length_ft, 'note': None}


def note_text(note, length_mm, duct_mm):
    """Текст сообщения пользователю для plan_tail()['note']; для None — пустая строка."""
    if note == 'short':
        return (u'Жёсткий участок короче заданной длины: он {0} мм, а нужно {1} мм.\n'
                u'Он преобразован в гибкий воздуховод целиком ({0} мм).'.format(format_mm(duct_mm), format_mm(length_mm)))
    if note == 'leftover':
        return (u'Если отрезать {1} мм, жёсткий остаток был бы короче {2} мм — Revit такой воздуховод не строит.\n'
                u'Участок ({0} мм) преобразован в гибкий воздуховод целиком.'.format(
                    format_mm(duct_mm), format_mm(length_mm), format_mm(ft_to_mm(MIN_LEN_FT))))
    return u''
