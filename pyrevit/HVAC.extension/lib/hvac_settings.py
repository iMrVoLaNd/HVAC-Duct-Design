# -*- coding: utf-8 -*-
"""Личный файл настроек кнопки: <папка кнопки>\\settings.ini — у каждой кнопки свой.

Формат простой и читаемый (можно править в блокноте):

    # комментарий
    [settings]
    ключ = значение

Объект настроек имитирует конфигурацию pyRevit: get_option(ключ, по_умолчанию) / set_option(ключ, значение),
плюс save(). Значения хранятся текстом. Модуль не зависит от Revit; любая ошибка чтения/записи не ломает кнопку
(читаем — значит, пусто; пишем — save() вернёт False). Совместимо с IronPython 3.4 и CPython (без f-строк)."""
import io
import os

FILE_NAME = 'settings.ini'
ENV_DIR = 'HVAC_SETTINGS_DIR'      # для тестов: хранить файлы настроек не в папках кнопок, а здесь (по подпапке на кнопку)
HEADER = u'# Настройки кнопки {0}. Файл можно править вручную; удалите его — вернутся значения по умолчанию.'


def _to_text(value):
    if value is None:
        return u''
    text = value if isinstance(value, type(u'')) else str(value)
    return text.replace(u'\r', u' ').replace(u'\n', u' ').strip()


class FileConfig(object):
    def __init__(self, path, values=None, title=u''):
        self.path = path
        self.title = title
        self._values = dict(values or {})

    def get_option(self, key, default=None):
        return self._values.get(key, default)

    def set_option(self, key, value):
        self._values[key] = _to_text(value)

    def keys(self):
        return sorted(self._values)

    def save(self):
        """Записать файл целиком (сначала во временный, затем подменой). Возвращает True/False."""
        try:
            folder = os.path.dirname(self.path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            lines = [HEADER.format(self.title or os.path.basename(folder)), u'[settings]']
            for key in sorted(self._values):
                lines.append(u'{0} = {1}'.format(key, self._values[key]))
            tmp = self.path + '.tmp'
            with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
                f.write(u'\r\n'.join(lines) + u'\r\n')
            if os.path.isfile(self.path):
                os.remove(self.path)
            os.rename(tmp, self.path)
            return True
        except Exception:
            return False


def parse(text):
    """Словарь из текста файла: пустые строки, комментарии (# и ;) и заголовки [раздел] пропускаются."""
    values = {}
    for raw in text.splitlines():
        line = raw.strip().lstrip(u'﻿')
        if not line or line[0] in u'#;[':
            continue
        if u'=' not in line:
            continue
        key, _sep, value = line.partition(u'=')
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def read_file(path):
    try:
        with io.open(path, encoding='utf-8') as f:
            return parse(f.read())
    except Exception:
        return {}


def load(folder, legacy=None, legacy_keys=(), name=FILE_NAME):
    """Настройки кнопки из <folder>\\settings.ini.

    Файла ещё нет, а legacy (функция без аргументов, возвращает старую конфигурацию pyRevit) задана — переносим из неё
    значения legacy_keys в новый файл, чтобы прежние настройки не потерялись."""
    title = os.path.basename(folder.rstrip(u'\\/'))
    if title.lower().endswith(u'.pushbutton'):
        title = title[:-len(u'.pushbutton')]
    head, sep, rest = title.partition(u'_')
    if sep and head.isdigit():            # «102_FlexTail» -> «FlexTail»: номер в имени папки задаёт только порядок на ленте
        title = rest
    override = os.environ.get(ENV_DIR)
    if override:
        folder = os.path.join(override, title)
    path = os.path.join(folder, name)
    cfg = FileConfig(path, read_file(path), title)
    if legacy is not None and not os.path.isfile(path):
        try:
            old = legacy()
            moved = 0
            for key in legacy_keys:
                value = old.get_option(key, None)
                if value is not None and str(value).strip() != u'':
                    cfg.set_option(key, value)
                    moved += 1
            if moved:
                cfg.save()
        except Exception:
            pass
    return cfg
