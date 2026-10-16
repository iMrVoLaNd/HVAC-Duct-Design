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

LENGTH_KEY = 'length_mm'                  # последняя введённая длина
DEFAULT_LENGTH_KEY = 'default_length_mm'  # «длина по умолчанию» из окна настроек
REMEMBER_KEY = 'remember_length'          # запоминать ли последнюю длину (по умолчанию да)

SECTION = 'flex_tail'                     # собственная секция конфигурации кнопки FlexTail (не общая с другими кнопками)


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


MAX_EPS_MM = 0.05          # в окне длина показывается с точностью 0,1 мм: разницу меньше 0,05 мм считаем равенством


def fit_length(mm, max_mm):
    """Вписать введённую длину в длину найденного воздуховода max_mm (None — без ограничения).

    Возвращает (длина, подставлена_ли_максимальная): длиннее максимума — берём максимум и сообщаем об этом (True);
    равна максимуму с точностью до MAX_EPS_MM — берём максимум точно (воздуховод преобразуется целиком, без замечаний)."""
    if max_mm is None:
        return mm, False
    if mm > max_mm + MAX_EPS_MM:
        return max_mm, True
    if abs(mm - max_mm) <= MAX_EPS_MM:
        return max_mm, False
    return mm, False


def too_long_text(max_mm):
    return (u'Максимально возможная длина — {0} мм (длина найденного воздуховода).\n'
            u'Подставлена максимальная длина.'.format(format_mm(max_mm)))


def _read_length(cfg, key):
    try:
        return parse_length_mm(cfg.get_option(key, u''))
    except Exception:
        return None


def get_default_length(cfg):
    """Длина по умолчанию из настроек; нет или испорчена — DEFAULT_LENGTH_MM."""
    value = _read_length(cfg, DEFAULT_LENGTH_KEY)
    return DEFAULT_LENGTH_MM if value is None else value


def set_default_length(cfg, mm):
    cfg.set_option(DEFAULT_LENGTH_KEY, format_mm(mm))


def is_remember(cfg):
    """Запоминать последнюю длину? Любая ошибка чтения = да (так задумано по умолчанию)."""
    try:
        return str(cfg.get_option(REMEMBER_KEY, u'true')).strip().lower() in (u'1', u'true', u'yes', u'on')
    except Exception:
        return True


def set_remember(cfg, value):
    cfg.set_option(REMEMBER_KEY, u'true' if value else u'false')


def get_last_length(cfg):
    """Последняя введённая длина (мм); нет сохранённой или она испорчена — длина по умолчанию."""
    value = _read_length(cfg, LENGTH_KEY)
    return get_default_length(cfg) if value is None else value


def set_last_length(cfg, mm):
    cfg.set_option(LENGTH_KEY, format_mm(mm))


def start_length(cfg):
    """Какую длину показать в окне: последнюю введённую (если запоминание включено) или длину по умолчанию."""
    return get_last_length(cfg) if is_remember(cfg) else get_default_length(cfg)


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


def preview_text(size_text, length_mm, duct_mm=None):
    """Что получится: «Будет создан гибкий воздуховод Ø200 мм длиной 500 мм. Останется воздуховод длиной 1500 мм.»
    length_mm None — длина не введена (подсказка)."""
    if length_mm is None:
        return u'Введите длину числом, мм (от {0} до {1}).'.format(format_mm(MIN_LENGTH_MM), format_mm(MAX_LENGTH_MM))
    made = length_mm
    tail = u''
    if duct_mm is not None:
        plan = plan_tail(mm_to_ft(length_mm), mm_to_ft(duct_mm))
        if plan['mode'] == 'whole':
            made = duct_mm
            tail = u' Воздуховод преобразуется целиком.'
        else:
            tail = u' Останется воздуховод длиной {0} мм.'.format(format_mm(duct_mm - length_mm))
    size = (size_text + u' ') if size_text else u''
    return u'Будет создан гибкий воздуховод {0}длиной {1} мм.{2}'.format(size, format_mm(made), tail)


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
