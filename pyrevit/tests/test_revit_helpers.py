# -*- coding: utf-8 -*-
"""Тести hvac_revit.element_name (без Revit)."""
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'HVAC.extension', 'lib')
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import hvac_revit  # noqa: E402


class Normal(object):
    Name = u'Гибкий'


class AmbiguousName(object):
    @property
    def Name(self):
        raise AttributeError('ambiguous')


class NameRaisesRuntime(object):
    @property
    def Name(self):
        raise RuntimeError('перша-помилка')


class ElementNameTests(unittest.TestCase):
    def test_plain_name(self):
        self.assertEqual(hvac_revit.element_name(types.SimpleNamespace(), Normal()), u'Гибкий')

    def test_descriptor_fallback_like_ironpython3(self):
        class Desc(object):
            def __get__(self, obj, objtype=None):
                return u'через-дескриптор'
        DB = types.SimpleNamespace(Element=types.SimpleNamespace(Name=Desc()))
        self.assertEqual(hvac_revit.element_name(DB, AmbiguousName()), u'через-дескриптор')

    def test_getvalue_fallback_like_ironpython2(self):
        DB = types.SimpleNamespace(Element=types.SimpleNamespace(
            Name=types.SimpleNamespace(GetValue=lambda e: u'через-GetValue')))
        self.assertEqual(hvac_revit.element_name(DB, AmbiguousName()), u'через-GetValue')

    def test_raises_first_error_when_nothing_works(self):
        DB = types.SimpleNamespace(Element=types.SimpleNamespace(Name=object()))
        with self.assertRaises(RuntimeError) as cm:
            hvac_revit.element_name(DB, NameRaisesRuntime())
        self.assertIn('перша-помилка', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
