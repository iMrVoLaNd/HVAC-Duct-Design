/*
 * Палитра систем вентиляции.
 *
 * Идея: 10 базовых оттенков на группу (приточные / вытяжные), расставленных так,
 * чтобы соседние по номеру системы (П1 и П2, П2 и П3 ...) сильно отличались.
 * Дальше палитра повторяется «со сдвигом»: П11-П20 — те же оттенки, но светлые
 * и в другом порядке, П21-П30 — тёмные, П31-П40 — с белой штриховкой.
 *
 * Модуль работает и в браузере (window.Palette), и в Node (require).
 */
(function (root) {
  'use strict';

  /* ---------- цветовая математика ---------- */

  function hexToRgb(hex) {
    var h = hex.replace('#', '');
    return [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16); });
  }

  function rgbToHex(rgb) {
    return '#' + rgb.map(function (v) {
      var s = Math.round(Math.max(0, Math.min(255, v))).toString(16);
      return s.length < 2 ? '0' + s : s;
    }).join('').toUpperCase();
  }

  // sRGB -> CIE Lab (D65)
  function rgbToLab(rgb) {
    var lin = rgb.map(function (v) {
      v /= 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    var x = (lin[0] * 0.4124564 + lin[1] * 0.3575761 + lin[2] * 0.1804375) / 0.95047;
    var y = (lin[0] * 0.2126729 + lin[1] * 0.7151522 + lin[2] * 0.0721750);
    var z = (lin[0] * 0.0193339 + lin[1] * 0.1191920 + lin[2] * 0.9503041) / 1.08883;
    function f(t) { return t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116; }
    var fx = f(x), fy = f(y), fz = f(z);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  }

  // CIEDE2000: «насколько глаз видит разницу». ~2 — еле заметно, >20 — явно разные цвета.
  function deltaE(lab1, lab2) {
    var rad = Math.PI / 180, deg = 180 / Math.PI;
    var L1 = lab1[0], a1 = lab1[1], b1 = lab1[2];
    var L2 = lab2[0], a2 = lab2[1], b2 = lab2[2];
    var C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2);
    var Cm = (C1 + C2) / 2;
    var G = 0.5 * (1 - Math.sqrt(Math.pow(Cm, 7) / (Math.pow(Cm, 7) + Math.pow(25, 7))));
    var a1p = (1 + G) * a1, a2p = (1 + G) * a2;
    var C1p = Math.hypot(a1p, b1), C2p = Math.hypot(a2p, b2);
    var h1p = C1p === 0 ? 0 : (Math.atan2(b1, a1p) * deg + 360) % 360;
    var h2p = C2p === 0 ? 0 : (Math.atan2(b2, a2p) * deg + 360) % 360;
    var dLp = L2 - L1, dCp = C2p - C1p, dhp = 0;
    if (C1p * C2p !== 0) {
      dhp = h2p - h1p;
      if (dhp > 180) dhp -= 360;
      else if (dhp < -180) dhp += 360;
    }
    var dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(dhp * rad / 2);
    var Lpm = (L1 + L2) / 2, Cpm = (C1p + C2p) / 2, hpm = h1p + h2p;
    if (C1p * C2p !== 0) {
      hpm = Math.abs(h1p - h2p) <= 180 ? (h1p + h2p) / 2
        : (h1p + h2p < 360 ? (h1p + h2p + 360) / 2 : (h1p + h2p - 360) / 2);
    }
    var T = 1 - 0.17 * Math.cos((hpm - 30) * rad) + 0.24 * Math.cos(2 * hpm * rad)
      + 0.32 * Math.cos((3 * hpm + 6) * rad) - 0.20 * Math.cos((4 * hpm - 63) * rad);
    var dTheta = 30 * Math.exp(-Math.pow((hpm - 275) / 25, 2));
    var Rc = 2 * Math.sqrt(Math.pow(Cpm, 7) / (Math.pow(Cpm, 7) + Math.pow(25, 7)));
    var Sl = 1 + 0.015 * Math.pow(Lpm - 50, 2) / Math.sqrt(20 + Math.pow(Lpm - 50, 2));
    var Sc = 1 + 0.045 * Cpm, Sh = 1 + 0.015 * Cpm * T;
    var Rt = -Math.sin(2 * dTheta * rad) * Rc;
    return Math.sqrt(Math.pow(dLp / Sl, 2) + Math.pow(dCp / Sc, 2) + Math.pow(dHp / Sh, 2)
      + Rt * (dCp / Sc) * (dHp / Sh));
  }

  function mix(rgb, target, t) {
    return rgb.map(function (v, i) { return v + (target[i] - v) * t; });
  }

  /* ---------- базовые оттенки (по 10 на группу) ---------- */
  // Порядок важен: соседние в списке — максимально разные.

  var BASE = {
    supply: [
      { name: 'Красный',        hex: '#C8372D' },
      { name: 'Зелёный',        hex: '#3FA34D' },
      { name: 'Фиолетовый',     hex: '#7E3FA8' },
      { name: 'Жёлтый',         hex: '#F5C518' },
      { name: 'Розовый',        hex: '#E8468F' },
      { name: 'Тёмно-зелёный',  hex: '#1F6B43' },
      { name: 'Оранжевый',      hex: '#F47B20' },
      { name: 'Бордовый',       hex: '#7A1E33' },
      { name: 'Лаймовый',       hex: '#A5D12B' },
      { name: 'Лавандовый',     hex: '#B9A2E0' }
    ],
    exhaust: [
      { name: 'Синий',          hex: '#1F5FD0' },
      { name: 'Коричневый',     hex: '#7A4B2B' },
      { name: 'Голубой',        hex: '#55C1F0' },
      { name: 'Графитовый',     hex: '#4A4F57' },
      { name: 'Бирюзовый',      hex: '#16A58F' },
      { name: 'Песочный',       hex: '#C9AE86' },
      { name: 'Серый',          hex: '#8A949E' },
      { name: 'Тёмно-синий',    hex: '#172E73' },
      { name: 'Изумрудный',     hex: '#0B6B5D' },
      { name: 'Оливковый',      hex: '#6B6B2F' }
    ]
  };

  // Цвет боковых стенок воздуховода — «стандартные» красный и синий.
  var WALL = { supply: '#FF0000', exhaust: '#0000FF' };
  var PREFIX = { supply: 'П', exhaust: 'В' };

  /* ---------- «сдвиги» для 2-го, 3-го и 4-го десятка ---------- */
  // Цветов, которые глаз уверенно различает на чертеже, около 10-12. Поэтому
  // для систем 11-40 оттенки повторяются, но меняется тип заливки
  // (в Revit это «образец штриховки» в фильтре вида): П11 = П1 + штриховка.
  // Системы с разным типом заливки считаются различимыми, даже если цвет тот же.

  var TIERS = [
    { id: 'solid', label: 'сплошная',               pattern: 'solid' },
    { id: 'diag',  label: 'диагональная штриховка', pattern: 'diag'  },
    { id: 'cross', label: 'сетка',                  pattern: 'cross' },
    { id: 'dots',  label: 'точки',                  pattern: 'dots'  }
  ];

  function buildGroup(kind) {
    var base = BASE[kind], out = [];
    TIERS.forEach(function (tier, t) {
      base.forEach(function (b, j) {
        var rgb = hexToRgb(b.hex);
        var n = t * base.length + j + 1;
        out.push({
          kind: kind,
          n: n,
          code: PREFIX[kind] + n,
          name: b.name,
          tier: tier.id,
          pattern: tier.pattern,
          wall: WALL[kind],
          hex: b.hex,
          rgb: rgb,
          lab: rgbToLab(rgb)
        });
      });
    });
    return out;
  }

  var SYSTEMS = { supply: buildGroup('supply'), exhaust: buildGroup('exhaust') };

  /* ---------- проверка различимости ---------- */

  // Разница между двумя системами: ΔE по цвету, а если заливка разная
  // (сплошная / штриховка / сетка) — считаем системы различимыми (Infinity).
  function distance(a, b) {
    return a.pattern !== b.pattern ? Infinity : deltaE(a.lab, b.lab);
  }

  // Худшая пара среди любых двух систем в скользящем окне из `size` номеров подряд.
  function windowStats(list, size) {
    var min = Infinity, pair = null;
    for (var i = 0; i < list.length; i++) {
      for (var j = i + 1; j < list.length && j < i + size; j++) {
        var d = distance(list[i], list[j]);
        if (d < min) { min = d; pair = [list[i].code, list[j].code]; }
      }
    }
    return { min: min, pair: pair };
  }

  var api = {
    BASE: BASE, WALL: WALL, PREFIX: PREFIX, TIERS: TIERS, SYSTEMS: SYSTEMS,
    hexToRgb: hexToRgb, rgbToHex: rgbToHex, rgbToLab: rgbToLab, deltaE: deltaE,
    distance: distance, windowStats: windowStats
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Palette = api;
})(typeof window !== 'undefined' ? window : this);
