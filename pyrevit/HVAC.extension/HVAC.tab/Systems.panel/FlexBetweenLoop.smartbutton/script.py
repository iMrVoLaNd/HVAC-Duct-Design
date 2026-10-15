# -*- coding: utf-8 -*-
__title__ = u'Цикл'
__author__ = u'HVAC-Duct-Design'
__doc__ = (u'Перемикач режиму «Гнучкий між конекторами»: вимкнено — будується одна пара і кнопка завершується, '
           u'увімкнено — пари будуються поспіль до Esc. За замовчуванням вимкнено. Стан запам\'ятовується.')

# Сумісно з IronPython 3.4 (pyRevit) і CPython: без f-рядків та сучасного синтаксису.
from pyrevit import script

SECTION = 'flex_between'


def _settings():
    import hvac_flex_settings
    return hvac_flex_settings


def _is_loop():
    try:
        return _settings().is_loop(script.get_config(SECTION))
    except Exception:
        return False            # у разі будь-якої помилки — вимкнено


def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    """Виконується при завантаженні панелі: ставить значок за збереженим станом."""
    try:
        ui_button_cmp.set_icon(script_cmp.get_bundle_file('on.png' if _is_loop() else 'off.png'))
    except Exception:
        pass
    return True


def toggle():
    settings = _settings()
    cfg = script.get_config(SECTION)
    new_state = not settings.is_loop(cfg)
    settings.set_loop(cfg, new_state)
    script.save_config()
    script.toggle_icon(new_state)
    try:
        from pyrevit import forms
        forms.show_balloon(u'Гнучкий між конекторами',
                           u'Цикл УВІМКНЕНО: пари будуються поспіль до Esc.' if new_state
                           else u'Цикл вимкнено: будується одна пара.')
    except Exception:
        pass


if __name__ == '__main__':
    toggle()
