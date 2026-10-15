/*
 * Выгрузка палитры сайта для кнопки pyRevit.
 *
 *   node tools/export-palette-json.js
 *
 * Читает js/palette.js (единый источник цветов) и пишет pyrevit/HVAC.extension/lib/palette.json.
 * Запускайте после любого изменения цветов или вариантов стенок на сайте.
 */
'use strict';

var fs = require('fs');
var path = require('path');
var P = require('../js/palette.js');

// Подписи вариантов стенок для диалога в Revit (украинский). Ключи = id из WALL_PRESETS.
var LABELS = {
  standard: 'Чисті (червоний / синій)',
  signal: 'Сигнальні',
  soft: 'Спокійні',
  muted: 'Приглушені',
  dark: 'Темні',
  black: 'Чорні',
  grey: 'Сірі'
};
var WIDTH_LABELS = { thin: 'Тонкі', medium: 'Середні', thick: 'Товсті' };
// Толщины линий в Revit (целые номера 1–16) для вариантов толщины.
var REVIT_WEIGHTS = { thin: 1, medium: 2, thick: 4 };

var systems = [];
['supply', 'exhaust'].forEach(function (kind) {
  P.SYSTEMS[kind].forEach(function (s) {
    systems.push({ name: s.code, kind: kind, color_name: s.nameUk, rgb: s.rgb });
  });
});

var out = {
  _comment: 'Сгенерировано tools/export-palette-json.js из js/palette.js. Не правьте руками.',
  parameter: 'ADSK_Система_Имя',
  systems: systems,
  wall_presets: P.WALL_PRESETS.map(function (w) {
    return { id: w.id, label: LABELS[w.id] || w.id, supply: P.hexToRgb(w.supply), exhaust: P.hexToRgb(w.exhaust) };
  }),
  wall_widths: P.WALL_WIDTHS.map(function (w) {
    return { id: w.id, label: WIDTH_LABELS[w.id] || w.id, revit_weight: REVIT_WEIGHTS[w.id] || 1 };
  })
};

var target = path.join(__dirname, '..', 'pyrevit', 'HVAC.extension', 'lib', 'palette.json');
fs.writeFileSync(target, JSON.stringify(out, null, 2) + '\n', 'utf8');
console.log('Записано: ' + path.relative(process.cwd(), target) + ' — систем: ' + systems.length
  + ', вариантов стенок: ' + out.wall_presets.length);
