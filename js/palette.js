/*
 * Палитра систем вентиляции — в стиле эталонного скриншота (матовые «сигнальные» цвета).
 *
 * По 12 цветов на группу, подобраны вручную. Первые цвета — ровно плашки со скриншота
 * (П1-П4 и В1-В3), остальные — «родня» к ним: спокойные, средней светлоты, одного характера.
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

  /* ---------- цвета систем ---------- */
  // Порядок = номер системы: П1, П2, ... / В1, В2, ...
  // Хотите другой цвет — поменяйте HEX здесь, проверка на странице пересчитается сама.

  var COLORS = {
    supply: [
      { name: 'Кирпичный',        hex: '#C1593C' },   // П1  — со скриншота
      { name: 'Зелёный',          hex: '#629D53' },   // П2  — со скриншота (Пн)
      { name: 'Оранжевый',        hex: '#FD7600' },   // П3  — со скриншота (Пд)
      { name: 'Золотистый',       hex: '#D29E3B' },   // П4  — со скриншота (Р)
      { name: 'Фиолетовый',       hex: '#6B5CAA' },
      { name: 'Пыльная роза',     hex: '#C9707F' },
      { name: 'Малиново-красный', hex: '#A8323E' },
      { name: 'Лаймовый',         hex: '#A3B04A' },
      { name: 'Хвойный',          hex: '#2F6B4A' },
      { name: 'Пурпурный',        hex: '#A8447A' },
      { name: 'Зелёная бирюза',   hex: '#3FA58A' },
      { name: 'Коралловый',       hex: '#E58A6E' }
    ],
    exhaust: [
      { name: 'Синий',            hex: '#0150B7' },   // В1  — со скриншота
      { name: 'Сланцевый',        hex: '#405364' },   // В2  — со скриншота (Ввыбр)
      { name: 'Винно-коричневый', hex: '#553C3F' },   // В3  — со скриншота (Вд)
      { name: 'Голубой',          hex: '#4A9AD6' },
      { name: 'Бирюзовый',        hex: '#1F8A8A' },
      { name: 'Серый',            hex: '#8A949E' },
      { name: 'Коричневый',       hex: '#8A5A3C' },
      { name: 'Тёмно-синий',      hex: '#1F3563' },
      { name: 'Оливковый',        hex: '#77783E' },
      { name: 'Тёмный изумруд',   hex: '#17695B' },
      { name: 'Песочный',         hex: '#B59B6E' },
      { name: 'Пыльная сирень',   hex: '#8F7694' }
    ]
  };

  // Сколько первых цветов в группе взято со скриншота как эталон.
  var REFERENCE_COUNT = { supply: 4, exhaust: 3 };

  // Цвет боковых стенок воздуховода — «стандартные» красный и синий.
  var WALL = { supply: '#FF0000', exhaust: '#0000FF' };
  var PREFIX = { supply: 'П', exhaust: 'В' };

  function buildGroup(kind) {
    return COLORS[kind].map(function (c, i) {
      var rgb = hexToRgb(c.hex);
      return {
        kind: kind,
        n: i + 1,
        code: PREFIX[kind] + (i + 1),
        name: c.name,
        reference: i < REFERENCE_COUNT[kind],
        wall: WALL[kind],
        hex: c.hex,
        rgb: rgb,
        lab: rgbToLab(rgb)
      };
    });
  }

  var SYSTEMS = { supply: buildGroup('supply'), exhaust: buildGroup('exhaust') };

  /* ---------- проверка различимости ---------- */

  // Худшая пара среди любых двух систем в скользящем окне из `size` номеров подряд.
  function windowStats(list, size) {
    var min = Infinity, pair = null;
    for (var i = 0; i < list.length; i++) {
      for (var j = i + 1; j < list.length && j < i + size; j++) {
        var d = deltaE(list[i].lab, list[j].lab);
        if (d < min) { min = d; pair = [list[i].code, list[j].code]; }
      }
    }
    return { min: min, pair: pair };
  }

  var api = {
    COLORS: COLORS, WALL: WALL, PREFIX: PREFIX, SYSTEMS: SYSTEMS,
    hexToRgb: hexToRgb, rgbToHex: rgbToHex, rgbToLab: rgbToLab, deltaE: deltaE,
    windowStats: windowStats
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Palette = api;
})(typeof window !== 'undefined' ? window : this);
