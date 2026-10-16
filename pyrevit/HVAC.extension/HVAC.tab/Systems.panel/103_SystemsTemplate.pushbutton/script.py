# -*- coding: utf-8 -*-
__title__ = u'Шаблон\nсистем'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'Створює шаблон виду з фільтрами для кожної системи вентиляції окремо (П1…П20, В1…В20): '
           u'фільтр за параметром ADSK_Система_Имя = «П1» для категорій вентиляції, '
           u'заливка кольором системи з палітри, лінії бічних стінок обраного кольору і товщини.')

# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
import os
import sys

# Папка lib розширення (HVAC.extension/lib). Зазвичай pyRevit додає її сам; додаємо явно про всяк випадок.
try:
    _LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
except Exception:
    _LIB = u'?'
try:
    import hvac_log
except ImportError:
    from pyrevit import forms
    forms.alert(u'Не знайдено файл lib\\hvac_log.py.\nСкопіюйте в розширення ВСЮ папку HVAC.extension разом із lib '
                u'(усі файли) і перезавантажте pyRevit.\n\nШукав тут: {0}'.format(_LIB),
                title=u'HVAC', exitscript=True)
TOOL = 'systems_template'
hvac_log.configure(os.path.dirname(os.path.abspath(__file__)), 'SystemsTemplate')       # журнал — в папке этой кнопки

try:
    from pyrevit import revit, DB, forms, script
    from System.Collections.Generic import List

    import hvac_palette
    import hvac_revit
except Exception:
    hvac_log.log_exception(TOOL, u'імпорт модулів')
    raise

doc = revit.doc
output = script.get_output()

# Категорії вентиляції, для яких створюється фільтр. Зайве видаліть, потрібне додайте
# (назви — BuiltInCategory). Категорії, до яких параметр не прив'язаний, будуть пропущені автоматично.
CATEGORIES = [
    (u'OST_DuctCurves', u'Повітроводи'),
    (u'OST_FlexDuctCurves', u'Гнучкі повітроводи'),
    (u'OST_DuctFitting', u'Фасонні частини повітроводів'),
    (u'OST_DuctAccessory', u'Арматура повітроводів'),
    (u'OST_DuctTerminal', u'Повітророзподільники'),
    (u'OST_DuctInsulations', u'Ізоляція повітроводів'),
    (u'OST_DuctLinings', u'Внутрішня ізоляція повітроводів'),
    (u'OST_PlaceHolderDucts', u'Заміщувачі повітроводів'),
    # (u'OST_MechanicalEquipment', u'Обладнання'),   # розкоментуйте, щоб фарбувати й обладнання
]

DEFAULT_TEMPLATE_NAME = u'ОВ_Системи_кольори'

# Типи видів, з яких можна створити шаблон (є графіка з фільтрами).
GRAPHIC_VIEW_TYPES = [u'FloorPlan', u'CeilingPlan', u'EngineeringPlan', u'AreaPlan', u'Section',
                      u'Elevation', u'Detail', u'ThreeD']

GROUPS = [
    (u'Усі системи (П і В)', ('supply', 'exhaust')),
    (u'Лише припливні (П)', ('supply',)),
    (u'Лише витяжні (В)', ('exhaust',)),
]


def eid_int(eid):
    """Числове значення ElementId (у нових версіях Revit — .Value, у старих — .IntegerValue)."""
    try:
        return eid.Value
    except AttributeError:
        return eid.IntegerValue


def ask_choice(options, message):
    choice = forms.CommandSwitchWindow.show(options, message=message)
    if not choice:
        script.exit()
    return choice


def is_graphic_view(view):
    allowed = [getattr(DB.ViewType, n) for n in GRAPHIC_VIEW_TYPES if hasattr(DB.ViewType, n)]
    return (not view.IsTemplate) and view.ViewType in allowed


def find_parameter(param_name):
    """Спільний або проєктний параметр за іменем (ADSK_Система_Имя)."""
    for cls in (DB.SharedParameterElement, DB.ParameterElement):
        for p in DB.FilteredElementCollector(doc).OfClass(cls):
            if hvac_revit.element_name(DB, p) == param_name:
                return p
    return None


def resolve_categories(param):
    """Категорії вентиляції, для яких параметр можна використати у фільтрі."""
    ok, skipped = [], []
    for bic_name, label in CATEGORIES:
        if not hasattr(DB.BuiltInCategory, bic_name):
            skipped.append(label)
            continue
        cat_id = DB.ElementId(getattr(DB.BuiltInCategory, bic_name))
        one = List[DB.ElementId]()
        one.Add(cat_id)
        try:
            common = DB.ParameterFilterUtilities.GetFilterableParametersInCommon(doc, one)
        except Exception:
            skipped.append(label)
            continue
        if any(eid_int(x) == eid_int(param.Id) for x in common):
            ok.append((cat_id, label))
        else:
            skipped.append(label)
    return ok, skipped


def find_solid_fill():
    """Суцільна заливка (Solid fill) для кольору поверхні."""
    fallback = None
    for fp in DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement):
        pattern = fp.GetFillPattern()
        if pattern.IsSolidFill:
            if pattern.Target == DB.FillPatternTarget.Drafting:
                return fp.Id
            fallback = fp.Id
    return fallback


def make_overrides(fill_rgb, line_rgb, line_weight, solid_id):
    ogs = DB.OverrideGraphicSettings()
    line_color = DB.Color(line_rgb[0], line_rgb[1], line_rgb[2])
    fill_color = DB.Color(fill_rgb[0], fill_rgb[1], fill_rgb[2])
    ogs.SetProjectionLineColor(line_color)
    ogs.SetProjectionLineWeight(line_weight)
    ogs.SetCutLineColor(line_color)
    ogs.SetCutLineWeight(line_weight)
    if solid_id is not None:
        ogs.SetSurfaceForegroundPatternId(solid_id)
        ogs.SetSurfaceForegroundPatternColor(fill_color)
        ogs.SetCutForegroundPatternId(solid_id)
        ogs.SetCutForegroundPatternColor(fill_color)
    return ogs


def view_templates():
    return dict((hvac_revit.element_name(DB, v), v) for v in DB.FilteredElementCollector(doc).OfClass(DB.View) if v.IsTemplate)


def unique_name(name, taken):
    if name not in taken:
        return name
    i = 2
    while u'{0}_{1}'.format(name, i) in taken:
        i += 1
    return u'{0}_{1}'.format(name, i)


def allow_filters_in_template(template):
    """Щоб шаблон керував фільтрами (V/G Overrides Filters), параметр не має бути у списку неконтрольованих."""
    try:
        filters_param = DB.ElementId(DB.BuiltInParameter.VIS_GRAPHICS_FILTERS)
        keep = List[DB.ElementId]()
        for pid in template.GetNonControlledTemplateParameterIds():
            if eid_int(pid) != eid_int(filters_param):
                keep.Add(pid)
        template.SetNonControlledTemplateParameterIds(keep)
    except Exception:
        pass   # у старих версіях API — нічого страшного, налаштування за замовчуванням


FORBIDDEN_NAME_CHARS = u'\\:{}[]|;<>?`~'      # Revit не принимает их в именах (шаблона, фильтра)
MAX_NAME_LENGTH = 100


def bad_name_chars(name):
    """Символы, которых в названии быть не может (Revit их отвергнет), без повторов, в порядке появления."""
    found = []
    for ch in name:
        if (ch in FORBIDDEN_NAME_CHARS or ord(ch) < 32) and ch not in found:
            found.append(ch)
    return found


def ask_template_name():
    """Название шаблона: пустое, с запрещёнными символами или слишком длинное не принимаем — спрашиваем снова.
    Закрыли диалог — выход."""
    default = DEFAULT_TEMPLATE_NAME
    while True:
        name = forms.ask_for_string(default=default, prompt=u'Назва шаблону виду:', title=u'Шаблон систем')
        if name is None:
            script.exit()
        name = u' '.join(name.split())                       # лишние пробелы и переводы строк
        bad = bad_name_chars(name)
        if not name:
            forms.alert(u'Введіть назву шаблону.', title=u'Шаблон систем')
        elif bad:
            forms.alert(u'У назві не можна використовувати: {0}'.format(u' '.join(bad)), title=u'Шаблон систем')
            default = u''.join(ch for ch in name if ch not in bad)
        elif len(name) > MAX_NAME_LENGTH:
            forms.alert(u'Назва задовга: не більше {0} символів.'.format(MAX_NAME_LENGTH), title=u'Шаблон систем')
            default = name[:MAX_NAME_LENGTH]
        else:
            return name


def main():
    view = doc.ActiveView
    if not is_graphic_view(view):
        forms.alert(u'Відкрийте план, розріз або 3D-вид: шаблон створюється на основі активного виду.',
                    title=u'Шаблон систем', exitscript=True)

    palette = hvac_palette.load()
    param_name = palette['parameter']

    # --- діалоги ---
    name = ask_template_name()

    group_label = ask_choice([g[0] for g in GROUPS], u'Для яких систем створити фільтри?')
    kinds = [g[1] for g in GROUPS if g[0] == group_label][0]

    preset = hvac_palette.find_by_label(palette['wall_presets'],
                                        ask_choice([p['label'] for p in palette['wall_presets']],
                                                   u'Колір ліній бічних стінок:'))
    width = hvac_palette.find_by_label(palette['wall_widths'],
                                       ask_choice([w['label'] for w in palette['wall_widths']],
                                                  u'Товщина ліній стінок:'))

    # --- перевірки ---
    param = find_parameter(param_name)
    if param is None:
        forms.alert(u'У проєкті немає параметра «{0}».\nДодайте його (спільний параметр ADSK) і прив\'яжіть до '
                    u'категорій вентиляції, потім запустіть кнопку ще раз.'.format(param_name),
                    title=u'Шаблон систем', exitscript=True)
    categories, skipped = resolve_categories(param)
    if not categories:
        forms.alert(u'Параметр «{0}» не прив\'язаний до жодної з категорій вентиляції зі списку CATEGORIES.'
                    .format(param_name), title=u'Шаблон систем', exitscript=True)
    cat_ids = List[DB.ElementId]()
    for cat_id, _label in categories:
        cat_ids.Add(cat_id)

    systems = hvac_palette.systems(palette, kinds)
    solid_id = find_solid_fill()

    # --- шаблон: новий або вже існуючий з такою назвою ---
    templates = view_templates()
    reuse = False
    if name in templates:
        reuse = forms.alert(u'Шаблон «{0}» вже існує.\nОновити в ньому фільтри (так) чи створити новий з іншою '
                            u'назвою (ні)?'.format(name), title=u'Шаблон систем', yes=True, no=True)
        if not reuse:
            name = unique_name(name, templates)

    created, updated = 0, 0
    t = DB.Transaction(doc, u'Шаблон виду: фільтри систем вентиляції')
    t.Start()
    try:
        if reuse:
            template = templates[name]
        else:
            template = view.CreateViewTemplate()
            template.Name = name
        allow_filters_in_template(template)

        existing = dict((hvac_revit.element_name(DB, f), f) for f in DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement))
        in_template = set(eid_int(i) for i in template.GetFilters())

        for s in systems:
            fname = hvac_palette.filter_name(s['name'])
            # Правило: ADSK_Система_Имя дорівнює «П1» (точний збіг: П1 не захоплює П10).
            rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(param.Id, s['name'])
            element_filter = DB.ElementParameterFilter(rule)
            if fname in existing:
                pf = existing[fname]
                pf.SetCategories(cat_ids)
                pf.SetElementFilter(element_filter)
                updated += 1
            else:
                pf = DB.ParameterFilterElement.Create(doc, fname, cat_ids, element_filter)
                created += 1
            if eid_int(pf.Id) not in in_template:
                template.AddFilter(pf.Id)
            template.SetFilterVisibility(pf.Id, True)
            ogs = make_overrides(s['rgb'], hvac_palette.wall_rgb(preset, s['kind']), width['revit_weight'], solid_id)
            template.SetFilterOverrides(pf.Id, ogs)
        t.Commit()
    except Exception:
        t.RollBack()
        raise

    # --- звіт ---
    output.print_md(u'## Шаблон виду «{0}»'.format(name))
    output.print_md(u'* Фільтрів створено: **{0}**, оновлено: **{1}** (системи: {2})'
                    .format(created, updated, u', '.join(s['name'] for s in systems)))
    output.print_md(u'* Правило: **{0}** дорівнює назві системи'.format(param_name))
    output.print_md(u'* Категорії: {0}'.format(u', '.join(label for _id, label in categories)))
    if skipped:
        output.print_md(u'* Пропущено (параметр не прив\'язаний або категорії немає): {0}'.format(u', '.join(skipped)))
    output.print_md(u'* Лінії стінок: {0}, {1}'.format(preset['label'], width['label'].lower()))
    if solid_id is None:
        output.print_md(u'* **Увага:** у проєкті не знайдено суцільної заливки — кольором пофарбовано лише лінії.')

    if forms.alert(u'Застосувати шаблон «{0}» до активного виду?'.format(name),
                   title=u'Шаблон систем', yes=True, no=True):
        with revit.Transaction(u'Застосувати шаблон виду'):
            view.ViewTemplateId = template.Id


hvac_log.run(TOOL, main, doc)
