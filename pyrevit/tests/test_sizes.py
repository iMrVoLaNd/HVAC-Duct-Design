# -*- coding: utf-8 -*-
"""Тести hvac_sizes (без Revit)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_sizes as hs  # noqa: E402

FT = 1 / 304.8      # 1 мм у футах


class SizesTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(hs.label(hs.round_size(200 * FT)), u'Ø200')
        self.assertEqual(hs.label(hs.round_size(160.5 * FT)), u'Ø160.5')
        self.assertEqual(hs.label(hs.box_size('rect', 400 * FT, 200 * FT)), u'400×200')
        self.assertEqual(hs.label(hs.box_size('oval', 300 * FT, 150 * FT)), u'овал 300×150')
        self.assertEqual(hs.label(hs.unknown_size()), u'?')

    def test_same_size_with_tolerance(self):
        a = hs.round_size(200 * FT)
        self.assertTrue(hs.same_size(a, hs.round_size(200.4 * FT)))
        self.assertFalse(hs.same_size(a, hs.round_size(201 * FT)))

    def test_rect_compares_both_dimensions(self):
        a = hs.box_size('rect', 400 * FT, 200 * FT)
        self.assertTrue(hs.same_size(a, hs.box_size('rect', 400 * FT, 200 * FT)))
        self.assertFalse(hs.same_size(a, hs.box_size('rect', 400 * FT, 250 * FT)))
        self.assertFalse(hs.same_size(a, hs.box_size('rect', 200 * FT, 400 * FT)))      # не міняємо ширину з висотою

    def test_different_shapes_never_same(self):
        self.assertFalse(hs.same_size(hs.round_size(200 * FT), hs.box_size('rect', 200 * FT, 200 * FT)))
        self.assertFalse(hs.same_size(hs.box_size('rect', 1, 1), hs.box_size('oval', 1, 1)))

    def test_unknown_equals_unknown_so_no_question(self):
        self.assertTrue(hs.same_size(hs.unknown_size(), hs.unknown_size()))
        self.assertFalse(hs.same_size(hs.unknown_size(), hs.round_size(1)))

    def test_types_for_shape(self):
        entries = [('A', 'round'), ('B', 'rect'), ('C', None)]
        self.assertEqual(hs.types_for_shape(entries, 'round'), ['A', 'C'])
        self.assertEqual(hs.types_for_shape(entries, 'oval'), ['C'])
        self.assertEqual(hs.types_for_shape(entries, None), ['A', 'B', 'C'])
        self.assertEqual(hs.types_for_shape([('A', 'round')], 'rect'), [])

    def test_dim_label_in_millimetres(self):
        self.assertEqual(hs.dim_label(300 * FT), u'300')
        self.assertEqual(hs.dim_label(62.5 * FT), u'62.5')

    def test_dedupe_keeps_order(self):
        a, b = hs.round_size(200 * FT), hs.round_size(160 * FT)
        self.assertEqual(hs.dedupe_sizes([a, b, hs.round_size(200.1 * FT), b]), [a, b])


if __name__ == '__main__':
    unittest.main()
