# -*- coding: utf-8 -*-
"""Собирает архив расширения для скачивания: dist/HVAC.extension.zip.

    python3 tools/build_plugin_zip.py          # пересобрать архив
    python3 tools/build_plugin_zip.py --check  # только проверить, что архив в репозитории свежий (код возврата 0/1)

Архив детерминированный (одинаковые файлы дают одинаковые байты), поэтому его можно хранить в git и сравнивать.
Внутри — папка HVAC.extension целиком (кнопки + lib) и короткая инструкция. Журналы, личные settings.ini
и кэш Python в архив не попадают."""
import io
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SOURCE = os.path.join(ROOT, 'pyrevit', 'HVAC.extension')
TARGET = os.path.join(ROOT, 'dist', 'HVAC.extension.zip')
FOLDER = 'HVAC.extension'
STAMP = (2026, 1, 1, 0, 0, 0)            # фиксированная дата в архиве — иначе байты меняются при каждой сборке

README_NAME = u'УСТАНОВКА.txt'
README = (u'HVAC — кнопки для Revit (pyRevit): QuickFlexConnect и FlexTail\r\n'
          u'\r\n'
          u'1. Распакуйте архив в постоянную папку, например C:\\pyRevit\\HVAC (папка HVAC.extension должна лежать внутри).\r\n'
          u'2. pyRevit -> Settings -> Custom Extension Directories -> Add -> выберите папку, В КОТОРОЙ лежит HVAC.extension\r\n'
          u'   (то есть C:\\pyRevit\\HVAC, а не саму HVAC.extension) -> Save Settings and Reload.\r\n'
          u'3. На ленте появится вкладка HVAC.\r\n'
          u'\r\n'
          u'Копируйте HVAC.extension целиком: кнопки используют общую папку lib.\r\n'
          u'Журнал и настройки каждой кнопки лежат в её собственной папке (HVAC.tab\\Systems.panel\\<кнопка>.pushbutton):\r\n'
          u'<кнопка>.log и settings.ini. При обновлении плагина эти два файла можно оставить — настройки сохранятся.\r\n')


def skipped(name):
    low = name.lower()
    return (low.endswith('.pyc') or low.endswith('.log') or low.endswith('.log.1') or low.endswith('.tmp')
            or low == 'settings.ini' or low == '.ds_store' or low == 'thumbs.db')


def files():
    """Список (путь в архиве, путь на диске) в стабильном порядке."""
    found = []
    for folder, dirs, names in os.walk(SOURCE):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(names):
            if skipped(name):
                continue
            disk = os.path.join(folder, name)
            rel = os.path.relpath(disk, SOURCE).replace(os.sep, '/')
            found.append((FOLDER + '/' + rel, disk))
    return sorted(found)


def _add(archive, name, data):
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    archive.writestr(info, data)


def build_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
        _add(archive, README_NAME, README.encode('utf-8'))
        for name, disk in files():
            with open(disk, 'rb') as f:
                _add(archive, name, f.read())
    return buf.getvalue()


def main(argv):
    data = build_bytes()
    if '--check' in argv:
        current = open(TARGET, 'rb').read() if os.path.isfile(TARGET) else None
        if current == data:
            print('dist/HVAC.extension.zip актуален')
            return 0
        print('dist/HVAC.extension.zip устарел: запустите python3 tools/build_plugin_zip.py')
        return 1
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, 'wb') as f:
        f.write(data)
    print('записано: {0} ({1} файлов, {2} байт)'.format(TARGET, len(files()) + 1, len(data)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
