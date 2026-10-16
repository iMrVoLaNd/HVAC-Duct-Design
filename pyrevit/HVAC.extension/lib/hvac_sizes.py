# -*- coding: utf-8 -*-
"""Розміри перерізу конекторів/повітроводів без залежності від Revit: порівняння, підписи, вибір типів за формою.

Розмір — словник:  {'shape': 'round', 'd': діаметр}  або  {'shape': 'rect'|'oval', 'w': ширина, 'h': висота};
довжини — у внутрішніх одиницях Revit (футах). Невідома форма: {'shape': None}.
Сумісно з IronPython 3.4 і CPython (без f-рядків)."""

FT_TO_MM = 304.8
TOLERANCE_MM = 0.5          # різниця менша за пів міліметра — розміри однакові
SHAPE_NAMES = {'round': u'круглый', 'rect': u'прямоугольный', 'oval': u'овальный'}


def round_size(diameter):
    return {'shape': 'round', 'd': float(diameter)}


def box_size(shape, width, height):
    return {'shape': shape, 'w': float(width), 'h': float(height)}


def unknown_size():
    return {'shape': None}


def mm(feet):
    return feet * FT_TO_MM


def _fmt(value_mm):
    text = '{0:.1f}'.format(value_mm)
    return text[:-2] if text.endswith('.0') else text


def label(size):
    """Короткий підпис: «Ø200», «400×200», «овал 400×200»; невідомий переріз — «?»."""
    shape = size.get('shape')
    if shape == 'round':
        return u'Ø' + _fmt(mm(size['d']))
    if shape == 'rect':
        return u'{0}×{1}'.format(_fmt(mm(size['w'])), _fmt(mm(size['h'])))
    if shape == 'oval':
        return u'овал {0}×{1}'.format(_fmt(mm(size['w'])), _fmt(mm(size['h'])))
    return u'?'


def same_size(a, b, tol_mm=TOLERANCE_MM):
    """Однакова форма й розміри (з допуском)."""
    if a.get('shape') != b.get('shape'):
        return False
    shape = a.get('shape')
    if shape is None:
        return True                      # нічого порівнювати: не питаємо
    keys = ('d',) if shape == 'round' else ('w', 'h')
    return all(abs(mm(a[k]) - mm(b[k])) <= tol_mm for k in keys)


def types_for_shape(entries, shape):
    """Фільтр типів за формою. entries — [(ім'я, форма або None)]. Типи з невідомою формою залишаємо (не вгадуємо);
    якщо не лишилось жодного — повертаємо порожній список (виклик покаже зрозуміле повідомлення)."""
    if shape is None:
        return [name for name, _s in entries]
    return [name for name, s in entries if s is None or s == shape]


def dedupe_sizes(sizes, tol_mm=TOLERANCE_MM):
    """Прибрати повтори зі списку розмірів, зберігаючи порядок."""
    result = []
    for s in sizes:
        if not any(same_size(s, r, tol_mm) for r in result):
            result.append(s)
    return result
