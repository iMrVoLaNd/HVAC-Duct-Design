# -*- coding: utf-8 -*-
"""Тести журналу hvac_log (без Revit)."""
import io
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_log  # noqa: E402


def read(path):
    with io.open(path, encoding='utf-8') as f:
        return f.read()


class LogTests(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.get('HVAC_LOG_DIR')
        self.dir = tempfile.mkdtemp()
        os.environ['HVAC_LOG_DIR'] = self.dir

    def tearDown(self):
        if self.old is None:
            os.environ.pop('HVAC_LOG_DIR', None)
        else:
            os.environ['HVAC_LOG_DIR'] = self.old

    def test_log_line_has_time_tool_and_message(self):
        hvac_log.log('tool1', u'привіт')
        text = read(hvac_log.log_path())
        self.assertIn(u'[tool1] привіт', text)
        self.assertRegex(text, r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[tool1\]')

    def test_log_dir_comes_from_env(self):
        self.assertEqual(os.path.dirname(hvac_log.log_path()), self.dir)

    def test_unwritable_dir_never_raises(self):
        blocker = os.path.join(self.dir, 'file')
        with io.open(blocker, 'w') as f:
            f.write(u'x')
        os.environ['HVAC_LOG_DIR'] = os.path.join(blocker, 'sub')      # папку створити неможливо
        hvac_log.log('t', u'не впаде')

    def test_rotation_when_file_too_big(self):
        path = hvac_log.log_path()
        with io.open(path, 'w', encoding='utf-8') as f:
            f.write(u'x' * (hvac_log.MAX_BYTES + 1))
        hvac_log.log('t', u'після ротації')
        self.assertTrue(os.path.isfile(path + '.1'))
        self.assertLess(os.path.getsize(path), 1000)

    def test_run_success_logs_start_engine_and_end(self):
        hvac_log.run('okbtn', lambda: None)
        text = read(hvac_log.log_path())
        self.assertIn(u'=== запуск', text)
        self.assertRegex(text, r'(CPython|IronPython) \d')
        self.assertIn(u'=== кінець', text)

    def test_run_logs_full_traceback_and_swallows_error(self):
        def boom():
            raise RuntimeError('помилка-4242')

        hvac_log.run('failbtn', boom)                       # не кидає далі
        text = read(hvac_log.log_path())
        self.assertIn(u'ПОМИЛКА', text)
        self.assertIn(u'Traceback', text)
        self.assertIn(u'RuntimeError: помилка-4242', text)
        self.assertNotIn(u'=== кінець', text)

    def test_exit_and_cancel_are_not_errors_and_propagate(self):
        class ExitScript(Exception):
            pass

        class OperationCanceledException(Exception):
            pass

        for exc in (ExitScript, OperationCanceledException):
            def f():
                raise exc()
            with self.assertRaises(exc):
                hvac_log.run('t', f)
        self.assertNotIn(u'ПОМИЛКА', read(hvac_log.log_path()))

    def test_error_is_reported_to_output_window_and_dialog(self):
        out, alerts = [], []
        pyrevit = types.ModuleType('pyrevit')
        pyrevit.script = types.SimpleNamespace(get_output=lambda: types.SimpleNamespace(print_md=out.append))
        pyrevit.forms = types.SimpleNamespace(alert=lambda msg, **k: alerts.append(msg))
        saved = sys.modules.get('pyrevit')
        sys.modules['pyrevit'] = pyrevit
        try:
            def boom():
                raise ValueError('видно-у-вікні')
            hvac_log.run('btn', boom)
        finally:
            if saved is None:
                sys.modules.pop('pyrevit', None)
            else:
                sys.modules['pyrevit'] = saved
        self.assertTrue(any('видно-у-вікні' in m for m in out))
        self.assertTrue(any(hvac_log.log_path() in m for m in out))
        self.assertEqual(len(alerts), 1)
        self.assertIn(hvac_log.log_path(), alerts[0])

    def test_log_start_reads_revit_version_if_available(self):
        doc = types.SimpleNamespace(Application=types.SimpleNamespace(VersionNumber='2026'))
        hvac_log.log_start('t', doc)
        self.assertIn(u'Revit 2026', read(hvac_log.log_path()))

    def test_no_fstrings_for_ironpython34(self):
        import re
        text = read(os.path.join(LIB, 'hvac_log.py'))
        self.assertIsNone(re.search(r"""(?<![A-Za-z0-9_])[fF][rR]?['"]""", text))


if __name__ == '__main__':
    unittest.main()
