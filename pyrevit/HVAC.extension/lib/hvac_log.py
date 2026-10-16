# -*- coding: utf-8 -*-
"""Журнал кнопок HVAC: пише кроки роботи й повні помилки у файл, щоб було видно, на чому падаємо.

Файл у папці кнопки: <папка кнопки>\\<ім'я кнопки>.log — у кожної кнопки свій журнал (див. configure()).
Не вдалося писати в папку кнопки — резервний файл %APPDATA%\\HVAC-Duct-Design\\<ім'я>.log (або тимчасова папка).
Змінна середовища HVAC_LOG_DIR переважає все (для тестів). Старий журнал (понад 512 КБ) переїжджає в <ім'я>.log.1.

Модуль не залежить від Revit; будь-яка помилка самого журналу ігнорується (журнал не має ламати кнопку).
Сумісний з IronPython 3.4 і CPython (без f-рядків).
"""
import io
import os
import sys
import time

LOG_NAME = 'hvac-tools.log'
MAX_BYTES = 512 * 1024
# Ці винятки — не помилки: користувач натиснув Esc або скрипт сам завершився (script.exit()).
_NOT_ERRORS = ('Exit', 'Cancel')


_CONFIG = {'folder': None, 'name': None}


def configure(folder, name):
    """Журнал цієї кнопки пишеться в її папку: <folder>/<name>.log. Викликати відразу після імпорту hvac_log."""
    _CONFIG['folder'] = folder
    _CONFIG['name'] = name


def default_dir():
    """Резервна папка журналу: %APPDATA%\\HVAC-Duct-Design (або тимчасова папка)."""
    appdata = os.environ.get('APPDATA')
    if appdata:
        return os.path.join(appdata, 'HVAC-Duct-Design')
    import tempfile                              # важкий імпорт — лише коли справді потрібен
    return os.path.join(tempfile.gettempdir(), 'HVAC-Duct-Design')


def log_dir():
    return os.environ.get('HVAC_LOG_DIR') or _CONFIG['folder'] or default_dir()


def log_name():
    return (_CONFIG['name'] + '.log') if _CONFIG['name'] else LOG_NAME


def log_path():
    return os.path.join(log_dir(), log_name())


def _to_text(value):
    try:
        return value if isinstance(value, type(u'')) else str(value)
    except Exception:
        try:
            return repr(value)
        except Exception:
            return u'<?>'


_BUFFER = []           # рядки, накопичені під час run(): пишемо одним відкриттям файлу, а не по одному на рядок
_BUFFERING = [False]


def _write(text):
    """Додати рядок: під час run() — у пам'ять (flush() запише все одним махом), поза ним — одразу у файл."""
    if _BUFFERING[0]:
        _BUFFER.append(text)
        return
    _write_now(text)


def flush():
    """Записати накопичені рядки у файл (один раз відкриваємо файл)."""
    if not _BUFFER:
        return
    text = u'\n'.join(_BUFFER)
    del _BUFFER[:]
    _write_now(text)


def _append(folder, text):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    path = os.path.join(folder, log_name())
    if os.path.isfile(path) and os.path.getsize(path) > MAX_BYTES:
        old = path + '.1'
        if os.path.isfile(old):
            os.remove(old)
        os.rename(path, old)
    with io.open(path, 'a', encoding='utf-8') as f:
        f.write(text + u'\n')


def _write_now(text):
    try:
        _append(log_dir(), text)
        return
    except Exception:
        pass
    if os.environ.get('HVAC_LOG_DIR'):               # явно заданную папку не подменяем
        return
    try:
        _append(default_dir(), text)                 # папку кнопки писать нельзя — резервная
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
    """Повний traceback поточного винятку; повертає його текст. Пишемо одразу: за помилки буфер не чекає кінця."""
    import traceback                             # лише за помилки: на звичайному запуску модуль не вантажимо
    text = traceback.format_exc()
    log(tool, u'ПОМИЛКА {0}\n{1}'.format(where, text))
    flush()
    return text


def is_not_error(exc):
    """Esc користувача й script.exit() — не помилки (за назвою класу, бо типи залежать від рушія)."""
    name = type(exc).__name__
    return any(part in name for part in _NOT_ERRORS)


def run(tool, func, doc=None):
    """Запустити func() із журналом. Помилку — у файл, у вікно виводу й діалог, без білого вікна без пояснень.

    Esc і script.exit() пропускаємо далі як є. Рядки журналу збираються в пам'яті й записуються в кінці одним
    махом (а також одразу при помилці); у кінці пишеться тривалість запуску."""
    started = time.time()
    _BUFFERING[0] = True
    try:
        log_start(tool, doc)
        try:
            func()
        except Exception as ex:
            if is_not_error(ex):
                log(tool, u'завершено ({0}), {1} мс'.format(type(ex).__name__, elapsed_ms(started)))
                raise
            text = log_exception(tool)
            _report(tool, text)
        else:
            log(tool, u'=== кінець, {0} мс'.format(elapsed_ms(started)))
    finally:
        _BUFFERING[0] = False
        flush()


def elapsed_ms(started):
    """Скільки мілісекунд минуло від started (time.time())."""
    return int((time.time() - started) * 1000)


def _report(tool, text):
    path = log_path()
    try:
        from pyrevit import script
        out = script.get_output()
        out.print_md(u'## Ошибка в кнопке «{0}»'.format(tool))
        out.print_md(u'Журнал: `{0}`'.format(path))
        out.print_md(u'```\n{0}\n```'.format(text))
    except Exception:
        pass
    try:
        from pyrevit import forms
        forms.alert(u'Ошибка в кнопке «{0}».\nЖурнал: {1}'.format(tool, path), title=u'HVAC')
    except Exception:
        pass
