# -*- coding: utf-8 -*-
"""Проверки кнопки pyRevit без Revit.

Запуск из корня репозитория:   python3 -m unittest discover -s pyrevit/tests -v

1) Логика палитры (lib/hvac_palette.py + palette.json) — настоящий код.
2) «Сухой прогон» script.py на заглушках API Revit: проверяем, что кнопка делает ровно то, что нужно
   (шаблон, фильтры по одному на систему, правило ADSK_Система_Имя = П1, категории, цвета, повтор запуска).
   Заглушки повторяют только те вызовы API, которые использует скрипт; на настоящий Revit это не замена,
   но ловит опечатки и ошибки в логике.
"""
import io
import json
import os
import runpy
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, '..', 'HVAC.extension')
LIB = os.path.join(EXT, 'lib')
SCRIPT = os.path.join(EXT, 'HVAC.tab', 'Systems.panel', 'SystemsTemplate.pushbutton', 'script.py')
sys.path.insert(0, LIB)

import hvac_palette  # noqa: E402


class PaletteTests(unittest.TestCase):
    def setUp(self):
        self.p = hvac_palette.load()

    def test_parameter_and_counts(self):
        self.assertEqual(self.p['parameter'], u'ADSK_Система_Имя')
        self.assertEqual(len(hvac_palette.systems(self.p, ('supply',))), 20)
        self.assertEqual(len(hvac_palette.systems(self.p, ('exhaust',))), 20)
        self.assertEqual(len(hvac_palette.systems(self.p, ('supply', 'exhaust'))), 40)

    def test_names_are_cyrillic_and_unique(self):
        names = [s['name'] for s in self.p['systems']]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(hex(ord(names[0][0])), '0x41f')    # П (кирилиця)
        self.assertEqual(hex(ord(names[20][0])), '0x412')   # В (кирилиця)
        self.assertEqual(names[0], u'П1')
        self.assertEqual(names[39], u'В20')

    def test_colors_are_valid_rgb(self):
        for s in self.p['systems']:
            self.assertEqual(len(s['rgb']), 3)
            self.assertTrue(all(0 <= c <= 255 for c in s['rgb']), s)

    def test_palette_json_matches_site(self):
        """palette.json має збігатися з js/palette.js (перегенеруйте: node tools/export-palette-json.js)."""
        import subprocess
        root = os.path.abspath(os.path.join(HERE, '..', '..'))
        out = subprocess.check_output(
            ['node', '-e', "var P=require('./js/palette.js');console.log(JSON.stringify(P.SYSTEMS.supply.concat(P.SYSTEMS.exhaust)"
                           ".map(function(s){return [s.code,s.rgb]})))"], cwd=root).decode('utf-8')
        site = json.loads(out)
        mine = [[s['name'], s['rgb']] for s in self.p['systems']]
        self.assertEqual(site, mine)

    def test_filter_name_and_wall(self):
        self.assertEqual(hvac_palette.filter_name(u'П1'), u'ОВ_П1')
        preset = hvac_palette.find(self.p['wall_presets'], 'standard')
        self.assertEqual(hvac_palette.wall_rgb(preset, 'supply'), (255, 0, 0))
        self.assertEqual(hvac_palette.wall_rgb(preset, 'exhaust'), (0, 0, 255))


# ----------------------------------------------------------------------------------------------
# Заглушки Revit API
# ----------------------------------------------------------------------------------------------
class EId(object):
    def __init__(self, v):
        self.Value = v


class FakeList(list):
    def Add(self, x):
        self.append(x)


class Color(object):
    def __init__(self, r, g, b):
        self.rgb = (r, g, b)


class OGS(object):
    def __init__(self):
        self.d = {}

    def __getattr__(self, name):
        if name.startswith('Set'):
            return lambda *a: self.d.__setitem__(name[3:], a[0] if len(a) == 1 else a)
        raise AttributeError(name)


class FakeFilterElement(object):
    def __init__(self, name, cats, ef, ident):
        self.Name, self.cats, self.ef, self.Id = name, list(cats), ef, EId(ident)

    def SetCategories(self, cats):
        self.cats = list(cats)

    def SetElementFilter(self, ef):
        self.ef = ef


class FakeTemplate(object):
    def __init__(self, ident):
        self.Id, self.Name, self.IsTemplate = EId(ident), 'Новый', True
        self.filters, self.vis, self.overrides, self.non_controlled = [], {}, {}, FakeList([EId(111), EId(222)])

    def GetFilters(self):
        return [f for f in self.filters]

    def AddFilter(self, fid):
        assert fid.Value not in [f.Value for f in self.filters], 'повторне додавання фільтра'
        self.filters.append(fid)

    def SetFilterVisibility(self, fid, v):
        self.vis[fid.Value] = v

    def SetFilterOverrides(self, fid, ogs):
        self.overrides[fid.Value] = ogs

    def GetNonControlledTemplateParameterIds(self):
        return self.non_controlled

    def SetNonControlledTemplateParameterIds(self, ids):
        self.non_controlled = ids


class FakeView(object):
    IsTemplate = False

    def __init__(self, vtype, doc):
        self.ViewType, self.doc, self.ViewTemplateId = vtype, doc, None

    def CreateViewTemplate(self):
        t = FakeTemplate(5000 + len(self.doc.templates))
        self.doc.templates.append(t)
        return t


class FakeDoc(object):
    def __init__(self):
        self.templates, self.filters, self.next_id = [], [], 7000
        self.solid = types.SimpleNamespace(
            Id=EId(42), GetFillPattern=lambda: types.SimpleNamespace(IsSolidFill=True, Target='Drafting'))
        self.param_cats = None   # None — параметр доступний для всіх; або множина BuiltInCategory-int
        self.param = types.SimpleNamespace(Name=u'ADSK_Система_Имя', Id=EId(900))
        self.has_param = True
        self.view = None


def build_db(doc):
    DB = types.SimpleNamespace()
    DB.ElementId = EId
    cats = ['OST_DuctCurves', 'OST_FlexDuctCurves', 'OST_DuctFitting', 'OST_DuctAccessory', 'OST_DuctTerminal',
            'OST_DuctInsulations', 'OST_DuctLinings', 'OST_PlaceHolderDucts', 'OST_MechanicalEquipment']
    DB.BuiltInCategory = types.SimpleNamespace(**dict((c, 100 + i) for i, c in enumerate(cats)))
    DB.BuiltInParameter = types.SimpleNamespace(VIS_GRAPHICS_FILTERS=111)
    DB.ViewType = types.SimpleNamespace(FloorPlan='FloorPlan', CeilingPlan='CeilingPlan', Section='Section',
                                        ThreeD='ThreeD', Schedule='Schedule', Elevation='Elevation', Detail='Detail',
                                        EngineeringPlan='EngineeringPlan', AreaPlan='AreaPlan')
    DB.FillPatternTarget = types.SimpleNamespace(Drafting='Drafting', Model='Model')
    DB.Color, DB.OverrideGraphicSettings = Color, OGS

    class SharedParameterElement(object):
        pass

    class ParameterElement(object):
        pass

    class FillPatternElement(object):
        pass

    class ParameterFilterElement(object):
        @staticmethod
        def Create(d, name, cat_ids, ef):
            d.next_id += 1
            f = FakeFilterElement(name, cat_ids, ef, d.next_id)
            d.filters.append(f)
            return f

    class View(object):
        pass

    DB.SharedParameterElement, DB.ParameterElement = SharedParameterElement, ParameterElement
    DB.FillPatternElement, DB.ParameterFilterElement, DB.View = FillPatternElement, ParameterFilterElement, View

    class Collector(object):
        def __init__(self, d):
            self.d = d

        def OfClass(self, cls):
            d = self.d
            if cls is SharedParameterElement:
                return [d.param] if d.has_param else []
            if cls is ParameterElement:
                return []
            if cls is FillPatternElement:
                return [d.solid]
            if cls is ParameterFilterElement:
                return list(d.filters)
            if cls is View:
                return list(d.templates)
            return []

    DB.FilteredElementCollector = Collector

    class Utils(object):
        @staticmethod
        def GetFilterableParametersInCommon(d, ids):
            ok = d.param_cats is None or all(i.Value in d.param_cats for i in ids)
            return [d.param.Id] if ok else []

    DB.ParameterFilterUtilities = Utils
    DB.ParameterFilterRuleFactory = types.SimpleNamespace(
        CreateEqualsRule=lambda pid, value: ('eq', pid.Value, value))
    DB.ElementParameterFilter = lambda rule: ('epf', rule)

    class Transaction(object):
        log = []

        def __init__(self, d, name):
            self.name = name

        def Start(self):
            Transaction.log.append('start')

        def Commit(self):
            Transaction.log.append('commit')

        def RollBack(self):
            Transaction.log.append('rollback')

    DB.Transaction = Transaction
    return DB


class ExitScript(Exception):
    pass


def run_button(doc, answers, view_type='FloorPlan', apply_template=True, existing_template_reuse=True):
    """Запустити script.py на заглушках. Повертає (doc, output_lines, alerts)."""
    DB = build_db(doc)
    doc.view = FakeView(view_type, doc)
    alerts, lines = [], []

    class Output(object):
        def print_md(self, text):
            lines.append(text)

    def alert(msg, title=None, yes=False, no=False, exitscript=False):
        alerts.append(msg)
        if exitscript:
            raise ExitScript(msg)
        if u'вже існує' in msg:
            return existing_template_reuse
        return apply_template

    class Switch(object):
        @staticmethod
        def show(options, message=None):
            for key, value in answers.items():
                if key in message:
                    return [o for o in options if value in o][0]
            raise AssertionError('нема відповіді для: ' + message)

    forms = types.SimpleNamespace(
        ask_for_string=lambda default=None, prompt=None, title=None: answers.get('name', default),
        CommandSwitchWindow=Switch, alert=alert)

    def script_exit():
        raise ExitScript('exit')

    class RevitTr(object):
        def __init__(self, name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    revit = types.SimpleNamespace(doc=doc, uidoc=None, Transaction=RevitTr)
    script = types.SimpleNamespace(get_output=lambda: Output(), exit=script_exit)

    # doc.ActiveView для скрипта
    doc.ActiveView = doc.view
    pyrevit = types.ModuleType('pyrevit')
    pyrevit.revit, pyrevit.DB, pyrevit.forms, pyrevit.script = revit, DB, forms, script
    sysmod = types.ModuleType('System')
    coll = types.ModuleType('System.Collections')
    gen = types.ModuleType('System.Collections.Generic')
    gen.List = FakeList
    saved = dict((k, sys.modules.get(k)) for k in ('pyrevit', 'System', 'System.Collections', 'System.Collections.Generic'))
    sys.modules.update({'pyrevit': pyrevit, 'System': sysmod, 'System.Collections': coll,
                        'System.Collections.Generic': gen})
    try:
        runpy.run_path(SCRIPT, run_name='__main__')
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return doc, lines, alerts


# FakeList должен поддерживать List[DB.ElementId]() как в .NET
FakeList.__class_getitem__ = classmethod(lambda cls, item: cls)

ANSWERS = {u'Для яких систем': u'Усі', u'Колір ліній': u'Спокійні', u'Товщина': u'Середні', 'name': u'ОВ_Тест'}


class ButtonTests(unittest.TestCase):
    def test_creates_template_and_one_filter_per_system(self):
        doc, lines, alerts = run_button(FakeDoc(), ANSWERS)
        self.assertEqual(len(doc.templates), 1)
        tmpl = doc.templates[0]
        self.assertEqual(tmpl.Name, u'ОВ_Тест')
        self.assertEqual(len(doc.filters), 40)
        self.assertEqual(len(tmpl.filters), 40)
        self.assertEqual(sorted(f.Name for f in doc.filters)[0][:3], u'ОВ_')
        self.assertTrue(all(tmpl.vis[f.Id.Value] is True for f in doc.filters))

    def test_rule_is_parameter_equals_system_name(self):
        doc, _lines, _alerts = run_button(FakeDoc(), ANSWERS)
        f = [x for x in doc.filters if x.Name == u'ОВ_П1'][0]
        self.assertEqual(f.ef, ('epf', ('eq', 900, u'П1')))
        # П1 і П10 — окремі фільтри з точним збігом
        f10 = [x for x in doc.filters if x.Name == u'ОВ_П10'][0]
        self.assertEqual(f10.ef[1][2], u'П10')

    def test_categories_are_ventilation_only(self):
        doc, _lines, _alerts = run_button(FakeDoc(), ANSWERS)
        cat_values = sorted(c.Value for c in doc.filters[0].cats)
        self.assertEqual(cat_values, list(range(100, 108)))     # 8 категорій, без обладнання (108)

    def test_overrides_use_palette_fill_and_wall_color(self):
        doc, _lines, _alerts = run_button(FakeDoc(), ANSWERS)
        tmpl = doc.templates[0]
        p1 = [x for x in doc.filters if x.Name == u'ОВ_П1'][0]
        v1 = [x for x in doc.filters if x.Name == u'ОВ_В1'][0]
        o1, ov = tmpl.overrides[p1.Id.Value].d, tmpl.overrides[v1.Id.Value].d
        pal = hvac_palette.load()
        sys_p1 = [s for s in pal['systems'] if s['name'] == u'П1'][0]
        self.assertEqual(o1['SurfaceForegroundPatternColor'].rgb, tuple(sys_p1['rgb']))
        self.assertEqual(o1['ProjectionLineColor'].rgb, (192, 57, 43))      # «Спокійні», приплив — червоний
        self.assertEqual(ov['ProjectionLineColor'].rgb, (31, 79, 216))      # витяжка — синій
        self.assertEqual(o1['ProjectionLineWeight'], 2)
        self.assertEqual(o1['SurfaceForegroundPatternId'].Value, 42)

    def test_only_supply(self):
        answers = dict(ANSWERS)
        answers[u'Для яких систем'] = u'Лише припливні'
        doc, _lines, _alerts = run_button(FakeDoc(), answers)
        self.assertEqual(len(doc.filters), 20)
        self.assertTrue(all(f.Name.startswith(u'ОВ_П') for f in doc.filters))

    def test_filters_param_is_controlled_by_template(self):
        doc, _lines, _alerts = run_button(FakeDoc(), ANSWERS)
        remaining = [i.Value for i in doc.templates[0].non_controlled]
        self.assertNotIn(111, remaining)      # VIS_GRAPHICS_FILTERS більше не в «неконтрольованих»
        self.assertIn(222, remaining)

    def test_missing_parameter_aborts_without_changes(self):
        d = FakeDoc()
        d.has_param = False
        with self.assertRaises(ExitScript):
            run_button(d, ANSWERS)
        self.assertEqual((len(d.templates), len(d.filters)), (0, 0))

    def test_skips_categories_without_parameter(self):
        d = FakeDoc()
        d.param_cats = set([100, 102])        # параметр прив'язаний лише до повітроводів і фасонних частин
        doc, lines, _alerts = run_button(d, ANSWERS)
        self.assertEqual(sorted(c.Value for c in doc.filters[0].cats), [100, 102])
        self.assertTrue(any(u'Пропущено' in l for l in lines))

    def test_no_matching_categories_aborts(self):
        d = FakeDoc()
        d.param_cats = set([999])
        with self.assertRaises(ExitScript):
            run_button(d, ANSWERS)
        self.assertEqual(len(d.templates), 0)

    def test_rerun_updates_existing_filters_not_duplicates(self):
        d = FakeDoc()
        run_button(d, ANSWERS)
        self.assertEqual(len(d.filters), 40)
        # другий запуск: оновити існуючий шаблон («так»)
        run_button(d, ANSWERS, existing_template_reuse=True)
        self.assertEqual(len(d.filters), 40)
        self.assertEqual(len(d.templates), 1)
        self.assertEqual(len(d.templates[0].filters), 40)

    def test_rerun_with_new_name_when_declined(self):
        d = FakeDoc()
        run_button(d, ANSWERS)
        run_button(d, ANSWERS, existing_template_reuse=False)
        self.assertEqual(len(d.templates), 2)
        self.assertEqual(d.templates[1].Name, u'ОВ_Тест_2')
        self.assertEqual(len(d.filters), 40)           # фільтри ті самі, нові не плодяться

    def test_schedule_view_is_rejected(self):
        with self.assertRaises(ExitScript):
            run_button(FakeDoc(), ANSWERS, view_type='Schedule')

    def test_template_is_applied_to_active_view(self):
        d = FakeDoc()
        run_button(d, ANSWERS, apply_template=True)
        self.assertEqual(d.view.ViewTemplateId.Value, d.templates[0].Id.Value)

    def test_no_fstrings_for_ironpython34(self):
        """IronPython 3.4 не знає f-рядків: у коді кнопки їх бути не повинно."""
        import re
        for path in (SCRIPT, os.path.join(LIB, 'hvac_palette.py')):
            with io.open(path, encoding='utf-8') as f:
                text = f.read()
            self.assertIsNone(re.search(r"""(?<![A-Za-z0-9_])[fF][rR]?['"]""", text), path)


if __name__ == '__main__':
    unittest.main()
