# -*- coding: utf-8 -*-
"""Общий вид окон (hvac_ui): XAML собирается без остатков заготовок, корректен как XML, нужные имена на месте."""
import os
import re
import sys
import types
import unittest
import xml.dom.minidom

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_ui as ui


def build(body=u'', with_info=False, title=u'Окно'):
    parts = [ui.info_block()] if with_info else []
    parts.append(body)
    return ui.window_xaml(title, 420, u'\n'.join(parts))


class XamlTests(unittest.TestCase):
    def parse(self, text):
        return xml.dom.minidom.parseString(text.encode('utf-8'))

    def test_window_is_well_formed_with_and_without_info(self):
        for with_info in (False, True):
            self.parse(build(ui.label(u'Подпись') + u'\n' + ui.buttons(u'ok_btn', u'OK'), with_info))

    def test_no_placeholders_left(self):
        text = build(u'', True)
        self.assertEqual(re.findall(r'@\w+@', text), [])

    def test_title_in_system_title_and_in_header_and_escaped(self):
        text = build(u'', title=u'A & B <x> "q"')
        self.assertIn(u'Title="A &amp; B &lt;x&gt; &quot;q&quot;"', text)
        self.assertIn(u'x:Name="title_text" Text="A &amp; B &lt;x&gt; &quot;q&quot;"', text)
        self.parse(text)

    def test_window_look(self):
        text = build(u'')
        for part in (u'WindowStyle="None"', u'Background="#FBFAF6"', u'BorderBrush="#14213D"',
                     u'Background="#14213D"', u'Width="420"'):
            self.assertIn(part, text)

    def test_styles_present(self):
        text = build(u'')
        for target in (u'TargetType="Button"', u'TargetType="TextBox"', u'TargetType="ComboBox"',
                       u'TargetType="ComboBoxItem"', u'TargetType="CheckBox"', u'x:Key="Chip"',
                       u'x:Key="ChipToggle"', u'x:Key="Label"', u'x:Key="Muted"'):
            self.assertIn(target, text)

    def test_header_is_named_for_dragging(self):
        self.assertIn(u'x:Name="title_bar"', build(u''))

    def test_enable_drag_moves_window_on_mouse_down(self):
        class Event(object):
            def __init__(self):
                self.handlers = []

            def __iadd__(self, h):
                self.handlers.append(h)
                return self

        class Win(object):
            def __init__(self, fail=False):
                self.MouseLeftButtonDown = Event()
                self.moved = 0
                self.fail = fail

            def DragMove(self):
                self.moved += 1
                if self.fail:
                    raise RuntimeError('кнопку уже отпустили')

        win = Win()
        self.assertTrue(ui.enable_drag(win))
        win.MouseLeftButtonDown.handlers[0](None, None)
        self.assertEqual(win.moved, 1)
        bad = Win(fail=True)
        ui.enable_drag(bad)
        bad.MouseLeftButtonDown.handlers[0](None, None)               # ошибка DragMove не должна вылетать наружу
        self.assertEqual(bad.moved, 1)
        self.assertFalse(ui.enable_drag(object()))                    # нет события — тихо False

    def test_default_button_is_primary(self):
        text = build(u'')
        self.assertIn(u'<Trigger Property="IsDefault" Value="True">', text)

    def test_info_block_names(self):
        text = build(u'', True)
        self.assertIn(u'x:Name="info_title"', text)
        self.assertIn(u'x:Name="info"', text)
        self.assertNotIn(u'x:Name="info"', build(u'', False))

    def test_buttons_helper(self):
        text = ui.buttons(u'save_btn', u'Сохранить')
        self.assertIn(u'x:Name="save_btn"', text)
        self.assertIn(u'IsDefault="True"', text)
        self.assertIn(u'IsCancel="True"', text)
        self.assertIn(u'Content="Отмена"', text)

    def test_label_escapes(self):
        self.assertIn(u'Text="Длина &amp; тип"', ui.label(u'Длина & тип'))


class HelperTests(unittest.TestCase):
    class Win(object):
        def __init__(self, names):
            self.ctl = dict((n, types.SimpleNamespace(Text=u'')) for n in names)
            self.Title = u''

        def FindName(self, name):
            return self.ctl[name]

    def test_set_title_sets_both(self):
        w = self.Win(['title_text'])
        ui.set_title(w, u'Тип')
        self.assertEqual((w.Title, w.ctl['title_text'].Text), (u'Тип', u'Тип'))

    def test_set_title_without_header_is_not_fatal(self):
        w = self.Win([])
        ui.set_title(w, u'Тип')
        self.assertEqual(w.Title, u'Тип')

    def test_fill_info(self):
        w = self.Win(['info_title', 'info'])
        ui.fill_info(w, u'Найден воздуховод', u'Тип: A\nДлина: 1 мм')
        self.assertEqual((w.ctl['info_title'].Text, w.ctl['info'].Text), (u'Найден воздуховод', u'Тип: A\nДлина: 1 мм'))

    def test_fill_info_without_block_is_not_fatal(self):
        ui.fill_info(self.Win([]), u'x', u'y')

    def test_size_text(self):
        self.assertEqual(ui.size_text(u'Ø200'), u'Ø200 мм')
        self.assertEqual(ui.size_text(u'400×200'), u'400×200 мм')
        self.assertEqual(ui.size_text(u'?'), u'?')


if __name__ == '__main__':
    unittest.main()
