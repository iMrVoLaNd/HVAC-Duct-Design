# -*- coding: utf-8 -*-
"""Палітра систем вентиляції для кнопок pyRevit.

Модуль не залежить від Revit: лише читає palette.json (його генерує tools/export-palette-json.js
з js/palette.js сайту) і віддає списки систем та кольори. Завдяки цьому його можна перевірити звичайним Python.
Сумісний з IronPython 3.4 і CPython (без f-рядків).
"""
import io
import json
import os

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'palette.json')

# Префікс імені фільтра у Revit: «ОВ_П1», «ОВ_В12»...
FILTER_PREFIX = u'ОВ_'


def load(path=None):
    """Прочитати palette.json."""
    with io.open(path or _DEFAULT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def systems(palette, kinds):
    """Системи вказаних груп ('supply' — припливні П, 'exhaust' — витяжні В) у порядку номерів."""
    return [s for s in palette['systems'] if s['kind'] in kinds]


def find(items, item_id, key='id'):
    """Знайти елемент списку словників за ключем (для варіантів стінок і товщини)."""
    for item in items:
        if item[key] == item_id:
            return item
    raise KeyError(item_id)


def find_by_label(items, label):
    """Те саме, але за підписом із діалогу."""
    for item in items:
        if item['label'] == label:
            return item
    raise KeyError(label)


def filter_name(system_name, prefix=FILTER_PREFIX):
    """Ім'я фільтра для системи: П1 -> ОВ_П1."""
    return prefix + system_name


def wall_rgb(preset, kind):
    """Колір бічних стінок (лінії) для групи системи."""
    return tuple(preset[kind])
