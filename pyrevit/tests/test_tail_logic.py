# -*- coding: utf-8 -*-
"""Чистая логика FlexTail (hvac_tail): ввод длины, запоминание, план разреза, тексты сообщений."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_tail as ht

FT = 1.0 / 304.8


class Cfg(object):
    def __init__(self, **kw):
        self.d = dict(kw)

    def get_option(self, k, default=None):
        return self.d.get(k, default)

    def set_option(self, k, v):
        self.d[k] = v


class ParseTests(unittest.TestCase):
    def test_plain_comma_spaces_and_units(self):
        self.assertEqual(ht.parse_length_mm(u'500'), 500.0)
        self.assertEqual(ht.parse_length_mm(u' 1 250,5 '), 1250.5)
        self.assertEqual(ht.parse_length_mm(u'750 мм'), 750.0)
        self.assertEqual(ht.parse_length_mm(u'750mm'), 750.0)
        self.assertEqual(ht.parse_length_mm(u'1 000'), 1000.0)

    def test_rejects_garbage_empty_zero_negative_and_huge(self):
        for bad in (u'', u'   ', u'abc', u'0', u'-300', u'4', u'50001', u'nan', u'1,2,3', None):
            self.assertIsNone(ht.parse_length_mm(bad), bad)

    def test_limits_are_inclusive(self):
        self.assertEqual(ht.parse_length_mm(u'5'), 5.0)
        self.assertEqual(ht.parse_length_mm(u'50000'), 50000.0)

    def test_format(self):
        self.assertEqual(ht.format_mm(500), u'500')
        self.assertEqual(ht.format_mm(1234.5), u'1234.5')
        self.assertEqual(ht.format_mm(1000.04), u'1000')


class RememberTests(unittest.TestCase):
    def test_default_when_nothing_saved(self):
        self.assertEqual(ht.get_last_length(Cfg()), 500)

    def test_saved_value_is_returned_and_survives_roundtrip(self):
        cfg = Cfg()
        ht.set_last_length(cfg, 1250.5)
        self.assertEqual(ht.get_last_length(cfg), 1250.5)

    def test_broken_saved_value_falls_back_to_default(self):
        self.assertEqual(ht.get_last_length(Cfg(length_mm=u'мусор')), 500)
        self.assertEqual(ht.get_last_length(Cfg(length_mm=u'0')), 500)

    def test_broken_config_object_is_not_fatal(self):
        class Boom(object):
            def get_option(self, *a):
                raise RuntimeError('нет доступа')
        self.assertEqual(ht.get_last_length(Boom()), 500)

    def test_chips(self):
        self.assertEqual(ht.CHIPS_MM, (300, 500, 1000, 1500, 2000, 2500))
        self.assertIn(ht.DEFAULT_LENGTH_MM, ht.CHIPS_MM)


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        cfg = Cfg()
        self.assertEqual((ht.get_default_length(cfg), ht.is_remember(cfg), ht.start_length(cfg)), (500, True, 500))
        self.assertEqual(ht.SECTION, 'flex_tail')

    def test_default_length_roundtrip_and_bad_value(self):
        cfg = Cfg()
        ht.set_default_length(cfg, 750)
        self.assertEqual(ht.get_default_length(cfg), 750)
        self.assertEqual(ht.get_default_length(Cfg(default_length_mm=u'??')), 500)

    def test_remember_roundtrip(self):
        cfg = Cfg()
        ht.set_remember(cfg, False)
        self.assertFalse(ht.is_remember(cfg))
        ht.set_remember(cfg, True)
        self.assertTrue(ht.is_remember(cfg))

    def test_start_length_uses_last_when_remembering_else_default(self):
        cfg = Cfg(length_mm=u'1200', default_length_mm=u'800')
        self.assertEqual(ht.start_length(cfg), 1200)
        ht.set_remember(cfg, False)
        self.assertEqual(ht.start_length(cfg), 800)

    def test_last_length_falls_back_to_configured_default(self):
        self.assertEqual(ht.get_last_length(Cfg(default_length_mm=u'800')), 800)
        self.assertEqual(ht.get_last_length(Cfg(length_mm=u'junk', default_length_mm=u'800')), 800)

    def test_broken_config_is_not_fatal(self):
        class Boom(object):
            def get_option(self, *a):
                raise RuntimeError('нет доступа')
        self.assertEqual((ht.start_length(Boom()), ht.is_remember(Boom())), (500, True))


class PlanTests(unittest.TestCase):
    def test_longer_duct_is_split_at_requested_length(self):
        p = ht.plan_tail(500 * FT, 2000 * FT)
        self.assertEqual((p['mode'], p['note']), ('split', None))
        self.assertAlmostEqual(p['distance'], 500 * FT)

    def test_shorter_duct_is_converted_whole_with_short_note(self):
        p = ht.plan_tail(500 * FT, 300 * FT)
        self.assertEqual((p['mode'], p['note']), ('whole', 'short'))
        self.assertAlmostEqual(p['distance'], 300 * FT)

    def test_equal_length_is_whole_without_note(self):
        for d in (500.0, 500.4, 499.6):                       # в пределах миллиметра — «столько же»
            p = ht.plan_tail(500 * FT, d * FT)
            self.assertEqual((p['mode'], p['note']), ('whole', None), d)

    def test_tiny_leftover_converts_whole(self):
        p = ht.plan_tail(1998 * FT, 2000 * FT)                # остаток 2 мм — Revit не построит
        self.assertEqual((p['mode'], p['note']), ('whole', 'leftover'))

    def test_leftover_just_above_minimum_still_splits(self):
        p = ht.plan_tail(1990 * FT, 2000 * FT)                # остаток 10 мм
        self.assertEqual(p['mode'], 'split')

    def test_notes_mention_both_lengths(self):
        short = ht.note_text('short', 500, 300)
        self.assertIn(u'300', short)
        self.assertIn(u'500', short)
        self.assertIn(u'целиком', short)
        leftover = ht.note_text('leftover', 1998, 2000)
        self.assertIn(u'2000', leftover)
        self.assertIn(u'1998', leftover)
        self.assertEqual(ht.note_text(None, 1, 2), u'')


if __name__ == '__main__':
    unittest.main()
