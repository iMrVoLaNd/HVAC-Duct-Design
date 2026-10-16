# -*- coding: utf-8 -*-
"""Окна сообщений (hvac_dialog): XAML, тексты, ссылки на элементы, копирование, журнал, запасной диалог."""
import os
import sys
import types
import unittest
import xml.dom.minidom

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_dialog as dlg
import hvac_revit
import hvac_ui


class Event(object):
    def __init__(self):
        self.handlers = []

    def __iadd__(self, h):
        self.handlers.append(h)
        return self

    def fire(self):
        for h in list(self.handlers):
            h(None, None)


class Control(object):
    def __init__(self):
        self.Text, self.Content, self.ToolTip = u'', u'', u''
        self.Click = Event()


def make_forms(crash=False, clicks=None, alerts=None):
    """Заглушка pyrevit.forms. clicks(window) — что «нажал» пользователь, пока окно открыто."""
    import re
    state = types.SimpleNamespace(windows=[])

    class WPFWindow(object):
        def __init__(self, xaml, literal_string=False, **kw):
            if crash:
                raise RuntimeError('XAML не разобран')
            xml.dom.minidom.parseString(xaml.encode('utf-8'))
            self.ctl = dict((n, Control()) for n in re.findall(r'x:Name="(\w+)"', xaml))
            self.MouseLeftButtonDown = Event()
            self.Title = u''
            self.closed = False
            state.windows.append(self)

        def FindName(self, name):
            return self.ctl[name]

        def DragMove(self):
            pass

        def Close(self):
            self.closed = True

        def ShowDialog(self):
            if clicks:
                clicks(self)

    def alert(text, title=None, yes=False, no=False):
        (alerts if alerts is not None else []).append((text, title, yes, no))
        return True

    return types.SimpleNamespace(WPFWindow=WPFWindow, alert=alert), state


class Base(unittest.TestCase):
    def setUp(self):
        self.selected, self.copied, self.opened = [], [], []
        self.real = (dlg.copy_to_clipboard, dlg.open_path)
        dlg.copy_to_clipboard = lambda text: (self.copied.append(text) or True)
        dlg.open_path = lambda path: (self.opened.append(path) or True)
        dlg.configure(select=lambda i: self.selected.append(i), log_path=lambda: u'C:\\x\\btn.log', strings=dlg.RU)

    def tearDown(self):
        dlg.copy_to_clipboard, dlg.open_path = self.real

    def run_dialog(self, call, clicks=None, crash=False, alerts=None):
        forms, state = make_forms(crash=crash, clicks=clicks, alerts=alerts)
        dlg.configure(forms=forms)
        return call(), state


class TextTests(unittest.TestCase):
    def test_log_line_becomes_path(self):
        text, log = dlg.split_log(u'Ошибка\nописание\n\nЖурнал: C:\\a\\b.log')
        self.assertEqual((text, log), (u'Ошибка\nописание', u'C:\\a\\b.log'))
        self.assertEqual(dlg.split_log(u'без журнала'), (u'без журнала', u''))

    def test_first_line_is_heading(self):
        self.assertEqual(dlg.split_text(u'Заголовок\nстрока 1\nстрока 2'), (u'Заголовок', u'строка 1\nстрока 2'))
        self.assertEqual(dlg.split_text(u'Одна строка'), (u'Одна строка', u''))

    def test_make_message_from_plain_text_keeps_old_calls_working(self):
        m = dlg.make_message(dlg.WARNING, u'Это один и тот же элемент.\nВыберите два разных.', u'T')
        self.assertEqual((m.heading, m.body, m.log, m.kind_label), (u'Это один и тот же элемент.', u'Выберите два разных.', u'', u'Внимание'))

    def test_explicit_heading_and_body_win(self):
        m = dlg.make_message(dlg.ERROR, u'', u'T', heading=u'H', body=u'B', details=u'tb')
        self.assertEqual((m.heading, m.body, m.details), (u'H', u'B', u'tb'))

    def test_plain_text_contains_everything_for_clipboard(self):
        m = dlg.Message(dlg.ERROR, u'Кнопка', u'Не вышло', u'причина', u'Traceback…', [(u'Воздуховоды · id 5', 5)], u'C:\\a.log')
        text = dlg.plain_text(m)
        for part in (u'[Ошибка] Кнопка', u'Не вышло', u'причина', u'Traceback…', u'Воздуховоды · id 5', u'Журнал: C:\\a.log'):
            self.assertIn(part, text)

    def test_element_label_has_id(self):
        self.assertEqual(dlg.element_label(u'Воздуховоды', u'Тип 1', 123), u'Воздуховоды «Тип 1» · id 123')
        self.assertEqual(dlg.element_label(u'Гибкий воздуховод', u'', 7), u'Гибкий воздуховод · id 7')


class XamlTests(unittest.TestCase):
    def test_all_variants_are_well_formed_xml(self):
        for kind in (dlg.INFO, dlg.WARNING, dlg.ERROR):
            for elements in ([], [(u'a & b <c>', 1), (u'b', 2)], [(u'e', i) for i in range(12)]):
                for details in (u'', u'tb'):
                    for log in (u'', u'C:\\x.log'):
                        for confirm in (None, (u'Да', u'Нет')):
                            m = dlg.Message(kind, u'T & "x"', u'H', u'B', details, elements, log, confirm=confirm)
                            xml.dom.minidom.parseString(dlg.build_xaml(m).encode('utf-8'))

    def test_names_follow_content(self):
        m = dlg.Message(dlg.ERROR, u'T', u'H', u'B', u'tb', [(u'a', 1), (u'b', 2)], u'C:\\x.log')
        xaml = dlg.build_xaml(m)
        for name in (u'kind_text', u'heading', u'body', u'elem0', u'elem1', u'details', u'status', u'copy_btn', u'log_btn', u'close_btn'):
            self.assertIn(u'x:Name="%s"' % name, xaml)
        self.assertNotIn(u'elem2', xaml)
        self.assertNotIn(u'yes_btn', xaml)
        plain = dlg.build_xaml(dlg.Message(dlg.INFO, u'T', u'H'))
        for name in (u'elem0', u'details', u'log_btn'):
            self.assertNotIn(u'x:Name="%s"' % name, plain)

    def test_details_are_selectable_readonly_text(self):
        xaml = dlg.build_xaml(dlg.Message(dlg.ERROR, u'T', u'H', details=u'tb'))
        self.assertIn(u'IsReadOnly="True"', xaml)
        self.assertIn(u'VerticalScrollBarVisibility="Auto"', xaml)

    def test_confirm_has_yes_no_and_no_close(self):
        xaml = dlg.build_xaml(dlg.Message(dlg.WARNING, u'T', u'H', confirm=(u'Да', u'Нет')))
        self.assertIn(u'yes_btn', xaml)
        self.assertIn(u'no_btn', xaml)
        self.assertNotIn(u'close_btn', xaml)

    def test_styled_like_other_windows(self):
        xaml = dlg.build_xaml(dlg.Message(dlg.INFO, u'T', u'H'))
        for part in (u'WindowStyle="None"', u'x:Key="Link"', u'x:Name="title_bar"', u'Background="#14213D"'):
            self.assertIn(part, xaml)

    def test_kind_colors_have_enough_contrast(self):
        def lum(h):
            h = h.lstrip('#')
            r, g, b = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
        for kind, (bg, fg) in dlg.COLORS.items():
            hi, lo = sorted((lum(bg), lum(fg)), reverse=True)
            self.assertGreaterEqual((hi + 0.05) / (lo + 0.05), 4.5, kind)


class WindowTests(Base):
    def message(self, **kw):
        base = dict(kind=dlg.ERROR, title=u'Кнопка', heading=u'Не вышло', body=u'причина', details=u'Traceback X',
                    elements=[(u'Воздуховоды · id 11', 11), (u'Арматура · id 22', 22)], log=u'C:\\x\\btn.log')
        base.update(kw)
        return dlg.Message(**base)

    def test_texts_are_filled(self):
        res, state = self.run_dialog(lambda: dlg.show(self.message()))
        c = state.windows[0].ctl
        self.assertEqual((c['kind_text'].Text, c['heading'].Text, c['body'].Text, c['details'].Text),
                         (u'Ошибка', u'Не вышло', u'причина', u'Traceback X'))
        self.assertEqual((c['elem0'].Content, c['elem1'].Content), (u'Воздуховоды · id 11', u'Арматура · id 22'))
        self.assertEqual(state.windows[0].Title, u'Кнопка')
        self.assertTrue(res)

    def test_click_on_element_selects_it_in_model(self):
        def clicks(win):
            win.ctl['elem1'].Click.fire()
            win.ctl['elem0'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertEqual(self.selected, [22, 11])
        self.assertEqual(state.windows[0].ctl['status'].Text, u'Элемент выделен в модели.')

    def test_selection_failure_is_explained_not_raised(self):
        def boom(i):
            raise RuntimeError('нет такого элемента')
        dlg.configure(select=boom)

        def clicks(win):
            win.ctl['elem0'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertIn(u'Не удалось выделить', state.windows[0].ctl['status'].Text)

    def test_copy_puts_whole_message_into_clipboard(self):
        def clicks(win):
            win.ctl['copy_btn'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertEqual(len(self.copied), 1)
        for part in (u'Не вышло', u'причина', u'Traceback X', u'id 11', u'id 22', u'C:\\x\\btn.log'):
            self.assertIn(part, self.copied[0])
        self.assertIn(u'скопировано', state.windows[0].ctl['status'].Text)

    def test_copy_failure_is_explained(self):
        dlg.copy_to_clipboard = lambda text: False

        def clicks(win):
            win.ctl['copy_btn'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertIn(u'Не удалось скопировать', state.windows[0].ctl['status'].Text)

    def test_log_button_opens_log_file(self):
        def clicks(win):
            win.ctl['log_btn'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertEqual(self.opened, [u'C:\\x\\btn.log'])
        self.assertEqual(state.windows[0].ctl['status'].Text, u'Журнал открыт.')

    def test_close_button_closes(self):
        def clicks(win):
            win.ctl['close_btn'].Click.fire()
        _res, state = self.run_dialog(lambda: dlg.show(self.message()), clicks)
        self.assertTrue(state.windows[0].closed)

    def test_window_can_be_dragged(self):
        _res, state = self.run_dialog(lambda: dlg.show(self.message()))
        self.assertEqual(len(state.windows[0].MouseLeftButtonDown.handlers), 1)

    def test_more_than_eight_elements_show_rest_as_count(self):
        m = self.message(elements=[(u'e%d' % i, i) for i in range(11)])
        _res, state = self.run_dialog(lambda: dlg.show(m))
        c = state.windows[0].ctl
        self.assertEqual(c['elem7'].Content, u'e7')
        self.assertNotIn('elem8', c)
        self.assertIn(u'ещё 3', c['more'].Text)

    def test_confirm_returns_choice(self):
        def yes(win):
            win.ctl['yes_btn'].Click.fire()

        def no(win):
            win.ctl['no_btn'].Click.fire()
        m = dlg.Message(dlg.WARNING, u'T', u'Продолжить?', confirm=(u'Да, продолжить', u'Нет'))
        self.assertTrue(self.run_dialog(lambda: dlg.show(m), yes)[0])
        self.assertFalse(self.run_dialog(lambda: dlg.show(m), no)[0])
        self.assertFalse(self.run_dialog(lambda: dlg.show(m), None)[0])                # окно закрыли крестиком/Esc

    def test_confirm_button_texts(self):
        m = dlg.Message(dlg.WARNING, u'T', u'Вопрос', confirm=(u'Обновить', u'Создать новый'))
        _res, state = self.run_dialog(lambda: dlg.show(m))
        c = state.windows[0].ctl
        self.assertEqual((c['yes_btn'].Content, c['no_btn'].Content), (u'Обновить', u'Создать новый'))

    def test_ukrainian_strings(self):
        dlg.configure(strings=dlg.UK)
        try:
            _res, state = self.run_dialog(lambda: dlg.show(dlg.Message(dlg.WARNING, u'T', u'Увага', elements=[(u'a', 1)], log=u'x')))
            xaml = dlg.build_xaml(dlg.Message(dlg.WARNING, u'T', u'Увага', elements=[(u'a', 1)], log=u'x'))
            self.assertEqual(state.windows[0].ctl['kind_text'].Text, u'Увага')
            for part in (u'Копіювати', u'Відкрити журнал', u'Закрити', u'натисніть, щоб виділити'):
                self.assertIn(part, xaml)
        finally:
            dlg.configure(strings=dlg.RU)


class FallbackTests(Base):
    def test_window_failure_falls_back_to_standard_alert_with_full_text(self):
        alerts = []
        m = dlg.Message(dlg.ERROR, u'Кнопка', u'Не вышло', u'причина', u'tb', [(u'Воздуховоды · id 5', 5)], u'C:\\x.log')
        res, _state = self.run_dialog(lambda: dlg.show(m), crash=True, alerts=alerts)
        self.assertTrue(res)
        self.assertEqual(len(alerts), 1)
        for part in (u'Не вышло', u'id 5', u'tb', u'C:\\x.log'):
            self.assertIn(part, alerts[0][0])

    def test_confirm_falls_back_to_yes_no_alert(self):
        alerts = []
        m = dlg.Message(dlg.WARNING, u'T', u'Вопрос', confirm=(u'Да', u'Нет'))
        res, _state = self.run_dialog(lambda: dlg.show(m), crash=True, alerts=alerts)
        self.assertTrue(res)
        self.assertEqual(alerts[0][2:], (True, True))

    def test_not_configured_is_an_explicit_error(self):
        saved = dlg._CTX['forms']
        dlg._CTX['forms'] = None
        try:
            with self.assertRaises(RuntimeError):
                dlg.show(dlg.Message())
        finally:
            dlg._CTX['forms'] = saved


class HelpersTests(Base):
    def test_error_has_log_button_by_default_and_warn_does_not(self):
        shown = []
        real = dlg.show
        dlg.show = lambda msg: shown.append(msg) or True
        try:
            dlg.error(u'Не вышло\nпричина', title=u'T')
            dlg.warn(u'Внимание', title=u'T')
            dlg.info(u'Готово', title=u'T')
            dlg.confirm(u'Продолжить?', title=u'T', yes=u'Да', no=u'Нет')
        finally:
            dlg.show = real
        err, warn, info, ask = shown
        self.assertEqual((err.kind, err.log, warn.kind, warn.log, info.kind), (dlg.ERROR, u'C:\\x\\btn.log', dlg.WARNING, u'', dlg.INFO))
        self.assertEqual((ask.kind, ask.confirm), (dlg.WARNING, (u'Да', u'Нет')))

    def test_log_line_in_text_is_taken_as_log_button(self):
        shown = []
        real = dlg.show
        dlg.show = lambda msg: shown.append(msg) or True
        try:
            dlg.warn(u'Заголовок\nтекст\n\nЖурнал: C:\\y.log')
        finally:
            dlg.show = real
        self.assertEqual((shown[0].heading, shown[0].body, shown[0].log), (u'Заголовок', u'текст', u'C:\\y.log'))

    def test_open_path_uses_folder_when_file_is_missing(self):
        calls = []
        real_start = getattr(os, 'startfile', None)
        os.startfile = lambda p: calls.append(p)
        dlg.open_path = self.real[1]
        try:
            folder = os.path.dirname(os.path.abspath(__file__))
            self.assertTrue(dlg.open_path(os.path.join(folder, 'нет-такого.log')))
            self.assertTrue(dlg.open_path(os.path.abspath(__file__)))
        finally:
            if real_start is None:
                del os.startfile
            else:
                os.startfile = real_start
        self.assertEqual(calls, [folder, os.path.abspath(__file__)])

    def test_select_element_without_selector_is_false(self):
        dlg._CTX['select'] = None
        self.assertFalse(dlg.select_element(5))


class RevitSelectTests(unittest.TestCase):
    def test_select_and_show_sets_selection_and_zooms(self):
        calls = []

        class Ids(list):
            def Add(self, x):
                self.append(x)

        class ListOf(object):
            def __class_getitem__(cls, item):
                return Ids

        DB = types.SimpleNamespace(ElementId=lambda n: ('id', n))
        uidoc = types.SimpleNamespace(
            Selection=types.SimpleNamespace(SetElementIds=lambda ids: calls.append(('select', list(ids)))),
            ShowElements=lambda eid: calls.append(('show', eid)))
        hvac_revit.select_and_show(uidoc, DB, ListOf, 1234)
        self.assertEqual(calls, [('select', [('id', 1234)]), ('show', ('id', 1234))])

    def test_zoom_failure_does_not_undo_selection(self):
        calls = []

        class Ids(list):
            def Add(self, x):
                self.append(x)

        class ListOf(object):
            def __class_getitem__(cls, item):
                return Ids

        def boom(eid):
            raise RuntimeError('другой вид')
        DB = types.SimpleNamespace(ElementId=lambda n: n)
        uidoc = types.SimpleNamespace(Selection=types.SimpleNamespace(SetElementIds=lambda ids: calls.append(list(ids))),
                                      ShowElements=boom)
        hvac_revit.select_and_show(uidoc, DB, ListOf, 5)
        self.assertEqual(calls, [[5]])


if __name__ == '__main__':
    unittest.main()
