# -*- coding: utf-8 -*-
"""Журнал кнопок HVAC: пише кроки роботи й повні помилки у файл, щоб було видно, на чому падаємо.

Файл:  %APPDATA%\\HVAC-Duct-Design\\hvac-tools.log   (або папка з змінної середовища HVAC_LOG_DIR,
       якщо APPDATA немає — тимчасова папка). Старий журнал (понад 512 КБ) переїжджає в hvac-tools.log.1.

Модуль не залежить від Revit; будь-яка помилка самого журналу ігнорується (журнал не має ламати кнопку).
Сумісний з IronPython 3.4 і CPython (без f-рядків).
"""
import io
import os
import sys
import tempfile
import time
import traceback

LOG_NAME = 'hvac-tools.log'
MAX_BYTES = 512 * 1024
# Ці винятки — не помилки: користувач натиснув Esc або скрипт сам завершився (script.exit()).
_NOT_ERRORS = ('Exit', 'Cancel')


def log_dir():
    base = os.environ.get('HVAC_LOG_DIR')
    if not base:
        appdata = os.environ.get('APPDATA')
        base = os.path.join(appdata, 'HVAC-Duct-Design') if appdata else os.path.join(tempfile.gettempdir(),
                                                                                    'HVAC-Duct-Design')
    return base


def log_path():
    return os.path.join(log_dir(), LOG_NAME)


def _to_text(value):
    try:
        return value if isinstance(value, type(u'')) else str(value)
    except Exception:
        try:
            return repr(value)
        except Exception:
            return u'<?>'


def _write(text):
    try:
        folder = log_dir()
        if not os.path.isdir(folder):
            os.makedirs(folder)
        path = log_path()
        if os.path.isfile(path) and os.path.getsize(path) > MAX_BYTES:
            old = path + '.1'
            if os.path.isfile(old):
                os.remove(old)
            os.rename(path, old)
        with io.open(path, 'a', encoding='utf-8') as f:
            f.write(text + u'\n')
    except Exception:
        pass


def log(tool, message):
    """Один рядок журналу: час, кнопка, повідомлення."""
    _write(u'{0} [{1}] {2}'.format(time.strftime('%Y-%m-%d %H:%M:%S'), tool, _to_text(message)))


def engine_name():
    """Назва рушія. IronPython 3.4 теж каже «3.4.x», тому дивимось на sys.implementation, а не лише на версію."""
    version = sys.version.split()[0]
    impl = getattr(getattr(sys, 'implementation', None), 'name', u'') or u''
    if 'ironpython' in impl.lower() or sys.platform == 'cli' or 'IronPython' in sys.version:
        return u'IronPython ' + version
    return u'CPython ' + version


def log_start(tool, doc=None):
    """Початок запуску: рушій Python і версія Revit — перше, що треба знати при помилці."""
    revit_ver = u'?'
    try:
        revit_ver = _to_text(doc.Application.VersionNumber)
    except Exception:
        pass
    log(tool, u'=== запуск | {0} | Revit {1} | {2}'.format(engine_name(), revit_ver, sys.platform))


def log_exception(tool, where=u''):
    """Повний traceback поточного винятку; повертає його текст."""
    text = traceback.format_exc()
    log(tool, u'ПОМИЛКА {0}\n{1}'.format(where, text))
    return text


def is_not_error(exc):
    """Esc користувача й script.exit() — не помилки (за назвою класу, бо типи залежать від рушія)."""
    name = type(exc).__name__
    return any(part in name for part in _NOT_ERRORS)


def run(tool, func, doc=None):
    """Запустити func() із журналом. Помилку — у файл, у вікно виводу й діалог, без білого вікна без пояснень.

    Esc і script.exit() пропускаємо далі як є."""
    log_start(tool, doc)
    try:
        func()
    except Exception as ex:
        if is_not_error(ex):
            log(tool, u'завершено ({0})'.format(type(ex).__name__))
            raise
        text = log_exception(tool)
        _report(tool, text)
    else:
        log(tool, u'=== кінець')


def _report(tool, text):
    path = log_path()
    try:
        from pyrevit import script
        out = script.get_output()
        out.print_md(u'## Помилка в кнопці «{0}»'.format(tool))
        out.print_md(u'Журнал: `{0}`'.format(path))
        out.print_md(u'```\n{0}\n```'.format(text))
    except Exception:
        pass
    try:
        from pyrevit import forms
        forms.alert(u'Помилка в кнопці «{0}».\nЖурнал: {1}'.format(tool, path), title=u'HVAC')
    except Exception:
        pass
