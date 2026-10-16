# -*- coding: utf-8 -*-
"""Архив для скачивания (dist/HVAC.extension.zip): свежий, полный и без лишнего."""
import importlib.util
import io
import os
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
spec = importlib.util.spec_from_file_location('build_plugin_zip', os.path.join(ROOT, 'tools', 'build_plugin_zip.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ZipTests(unittest.TestCase):
    def test_archive_in_repo_is_up_to_date(self):
        with open(builder.TARGET, 'rb') as f:
            self.assertEqual(f.read(), builder.build_bytes(),
                             'код изменился, а архив нет: python3 tools/build_plugin_zip.py')

    def names(self):
        with zipfile.ZipFile(io.BytesIO(builder.build_bytes())) as z:
            self.assertIsNone(z.testzip())
            return z.namelist()

    def test_contains_both_buttons_and_whole_lib(self):
        names = self.names()
        for part in ('HVAC.extension/HVAC.tab/Systems.panel/101_QuickFlexConnect.pushbutton/script.py',
                     'HVAC.extension/HVAC.tab/Systems.panel/102_FlexTail.pushbutton/script.py',
                     'HVAC.extension/HVAC.tab/Systems.panel/102_FlexTail.pushbutton/config.py',
                     'HVAC.extension/lib/hvac_ui.py', 'HVAC.extension/lib/hvac_settings.py',
                     'HVAC.extension/lib/hvac_log.py', 'HVAC.extension/lib/hvac_tail.py', builder.README_NAME):
            self.assertIn(part, names)
        lib = set(os.listdir(os.path.join(builder.SOURCE, 'lib')))
        lib.discard('__pycache__')
        self.assertEqual(set(n.split('/')[-1] for n in names if n.startswith('HVAC.extension/lib/')), lib)

    def test_no_logs_personal_settings_or_cache(self):
        for name in self.names():
            low = name.lower()
            self.assertFalse(low.endswith(('.pyc', '.log', '.log.1', '/settings.ini')), name)
            self.assertNotIn('__pycache__', low)
            self.assertNotIn('/tests/', low)

    def test_build_is_deterministic(self):
        self.assertEqual(builder.build_bytes(), builder.build_bytes())

    def test_readme_in_archive_explains_install(self):
        with zipfile.ZipFile(io.BytesIO(builder.build_bytes())) as z:
            text = z.read(builder.README_NAME).decode('utf-8')
        for part in (u'Custom Extension Directories', u'HVAC.extension', u'settings.ini'):
            self.assertIn(part, text)


if __name__ == '__main__':
    unittest.main()
