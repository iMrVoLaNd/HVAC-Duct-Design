# -*- coding: utf-8 -*-
"""Личный файл настроек кнопки (hvac_settings): чтение, запись, перенос из старой конфигурации pyRevit."""
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_settings as hs


def read(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


def no_env_override(test):
    """Другие тесты задают HVAC_SETTINGS_DIR; здесь проверяем настоящее расположение файла — в папке кнопки."""
    old = os.environ.pop(hs.ENV_DIR, None)
    if old is not None:
        test.addCleanup(os.environ.__setitem__, hs.ENV_DIR, old)


class Legacy(object):
    def __init__(self, **kw):
        self.d = dict(kw)

    def get_option(self, k, default=None):
        return self.d.get(k, default)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        no_env_override(self)
        self.root = tempfile.mkdtemp()
        self.folder = os.path.join(self.root, 'MyTool.pushbutton')
        os.makedirs(self.folder)

    def test_missing_file_gives_defaults(self):
        cfg = hs.load(self.folder)
        self.assertEqual((cfg.get_option('a', u'x'), cfg.get_option('a')), (u'x', None))

    def test_roundtrip_with_unicode(self):
        cfg = hs.load(self.folder)
        cfg.set_option('config_value', u'Гибкий')
        cfg.set_option('loop', 'true')
        cfg.set_option('number', 3)
        self.assertTrue(cfg.save())
        again = hs.load(self.folder)
        self.assertEqual((again.get_option('config_value'), again.get_option('loop'), again.get_option('number')),
                         (u'Гибкий', u'true', u'3'))

    def test_file_lives_in_the_plugin_folder_and_is_readable(self):
        cfg = hs.load(self.folder)
        cfg.set_option('b', u'2')
        cfg.set_option('a', u'1')
        cfg.save()
        path = os.path.join(self.folder, 'settings.ini')
        text = read(path)
        self.assertIn(u'[settings]', text)
        self.assertLess(text.index(u'a = 1'), text.index(u'b = 2'))            # ключи по алфавиту
        self.assertIn(u'MyTool', text.splitlines()[0])                         # в шапке имя кнопки
        self.assertFalse(os.path.exists(path + '.tmp'))

    def test_two_plugins_do_not_share_files(self):
        other = os.path.join(self.root, 'Other.pushbutton')
        os.makedirs(other)
        a, b = hs.load(self.folder), hs.load(other)
        a.set_option('k', u'A')
        a.save()
        self.assertIsNone(hs.load(other).get_option('k'))
        b.set_option('k', u'B')
        b.save()
        self.assertEqual((hs.load(self.folder).get_option('k'), hs.load(other).get_option('k')), (u'A', u'B'))

    def test_hand_edited_file_is_understood(self):
        with io.open(os.path.join(self.folder, 'settings.ini'), 'w', encoding='utf-8') as f:
            f.write(u'﻿# коммент\n; ещё\n[settings]\n\nlength_mm = 750\n  loop=true  \nмусорная строка\nvalue = a = b\n')
        cfg = hs.load(self.folder)
        self.assertEqual((cfg.get_option('length_mm'), cfg.get_option('loop'), cfg.get_option('value')),
                         (u'750', u'true', u'a = b'))

    def test_values_with_newlines_are_flattened(self):
        cfg = hs.load(self.folder)
        cfg.set_option('k', u'строка 1\nстрока 2')
        cfg.save()
        self.assertEqual(hs.load(self.folder).get_option('k'), u'строка 1 строка 2')

    def test_empty_value_is_kept_as_empty_not_missing(self):
        cfg = hs.load(self.folder)
        cfg.set_option('config_value', u'')                                     # «не менять параметр»
        cfg.save()
        self.assertEqual(hs.load(self.folder).get_option('config_value', u'Гибкий'), u'')

    def test_unwritable_folder_save_returns_false(self):
        blocker = os.path.join(self.root, 'file')
        with io.open(blocker, 'w') as f:
            f.write(u'x')
        cfg = hs.load(os.path.join(blocker, 'sub'))
        cfg.set_option('k', u'v')
        self.assertFalse(cfg.save())

    def test_unreadable_file_means_empty(self):
        with io.open(os.path.join(self.folder, 'settings.ini'), 'wb') as f:
            f.write(b'\xff\xfe\x00bad')
        self.assertEqual(hs.load(self.folder).keys(), [])

    def test_overwrite_replaces_old_content(self):
        cfg = hs.load(self.folder)
        cfg.set_option('a', u'1')
        cfg.save()
        cfg.set_option('a', u'2')
        cfg.save()
        self.assertEqual(hs.load(self.folder).get_option('a'), u'2')


class MigrationTests(unittest.TestCase):
    def setUp(self):
        no_env_override(self)
        self.folder = tempfile.mkdtemp()

    def test_values_move_from_legacy_config_once(self):
        legacy = Legacy(loop='true', config_value=u'Гибкий', other=u'не переносить')
        cfg = hs.load(self.folder, legacy=lambda: legacy, legacy_keys=('loop', 'config_value', 'missing'))
        self.assertEqual((cfg.get_option('loop'), cfg.get_option('config_value'), cfg.get_option('other')),
                         (u'true', u'Гибкий', None))
        self.assertTrue(os.path.isfile(os.path.join(self.folder, 'settings.ini')))
        later = hs.load(self.folder, legacy=lambda: Legacy(loop='false'), legacy_keys=('loop',))
        self.assertEqual(later.get_option('loop'), u'true')                     # файл уже есть — старое не трогаем

    def test_legacy_not_called_when_file_exists(self):
        hs.load(self.folder).save()
        calls = []
        hs.load(self.folder, legacy=lambda: calls.append(1), legacy_keys=('a',))
        self.assertEqual(calls, [])

    def test_empty_legacy_creates_no_file(self):
        cfg = hs.load(self.folder, legacy=lambda: Legacy(), legacy_keys=('loop',))
        self.assertEqual(cfg.keys(), [])
        self.assertFalse(os.path.isfile(os.path.join(self.folder, 'settings.ini')))

    def test_broken_legacy_is_not_fatal(self):
        def boom():
            raise RuntimeError('нет pyRevit')
        self.assertEqual(hs.load(self.folder, legacy=boom, legacy_keys=('a',)).keys(), [])


if __name__ == '__main__':
    unittest.main()
