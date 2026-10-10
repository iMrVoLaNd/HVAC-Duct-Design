/*
 * Палитра систем вентиляции — в стиле эталонного скриншота (матовые «сигнальные» цвета).
 *
 * По 12 цветов на группу, подобраны вручную по референсам. Приточные — земляная палитра
 * (терракот, зелёные, горчица, охра, кирпич), цвета П1–П7 и П9–П12 взяты точно из легенд референсов.
 * Вытяжные — холодные, серые и коричневые; В1–В3 — плашки с первого скриншота.
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
    // Приточные — земляная палитра с референсов (BIM Shaded with Edges): терракот, зелёные, горчица, охра.
    // ref: true — цвет взят точно из легенды референса.
    supply: [
      { name: 'Терракотово-красный', nameUk: 'Теракотово-червоний',  hex: '#C35B44', ref: true },   // П1
      { name: 'Травянисто-зелёный', nameUk: 'Трав’янисто-зелений',   hex: '#699D5A', ref: true },   // П2
      { name: 'Горчично-жёлтый', nameUk: 'Гірчично-жовтий',      hex: '#CBA453', ref: true },   // П3
      { name: 'Охристо-оранжевый', nameUk: 'Охристо-помаранчевий',    hex: '#E37C21', ref: true },   // П4
      { name: 'Оливково-зелёный', nameUk: 'Оливково-зелений',     hex: '#89B07F', ref: true },   // П5
      { name: 'Кирпично-оранжевый', nameUk: 'Цегляно-помаранчевий',   hex: '#C94E00', ref: true },   // П6
      { name: 'Тёмно-зелёный', nameUk: 'Темно-зелений',        hex: '#316549', ref: true },   // П7
      { name: 'Ярко-жёлтый', nameUk: 'Яскраво-жовтий',          hex: '#EAC22E' },              // П8  (в референсе П8 ≈ П3, заменён)
      { name: 'Бордово-красный', nameUk: 'Бордово-червоний',      hex: '#9D382F', ref: true },   // П9  (в референсе П9 ≈ П6, заменён)
      { name: 'Оливково-хаки', nameUk: 'Оливково-хакі',        hex: '#596232', ref: true },   // П10
      { name: 'Тёмно-коричневый', nameUk: 'Темно-коричневий',     hex: '#433A2D', ref: true },   // П11
      { name: 'Тёмный сине-зелёный', nameUk: 'Темний синьо-зелений',  hex: '#2F4B46', ref: true }    // П12
    ],
    // Вытяжные — холодные, серые и коричневые; первые три — плашки с первого скриншота.
    exhaust: [
      { name: 'Синий', nameUk: 'Синій',            hex: '#0150B7', ref: true },   // В1
      { name: 'Сланцевый', nameUk: 'Сланцевий',        hex: '#405364', ref: true },   // В2
      { name: 'Винно-коричневый', nameUk: 'Винно-коричневий', hex: '#553C3F', ref: true },   // В3
      { name: 'Голубой', nameUk: 'Блакитний',          hex: '#4A9AD6' },
      { name: 'Бирюзовый', nameUk: 'Бірюзовий',        hex: '#1F8A8A' },
      { name: 'Серый', nameUk: 'Сірий',            hex: '#8A949E' },
      { name: 'Коричневый', nameUk: 'Коричневий',       hex: '#8A5A3C' },
      { name: 'Тёмно-синий', nameUk: 'Темно-синій',      hex: '#1F3563' },
      { name: 'Оливковый', nameUk: 'Оливковий',        hex: '#77783E' },
      { name: 'Тёмный изумруд', nameUk: 'Темний смарагд',   hex: '#17695B' },
      { name: 'Песочный', nameUk: 'Піщаний',         hex: '#B59B6E' },
      { name: 'Пыльная сирень', nameUk: 'Пильно-бузковий',   hex: '#8F7694' }
    ]
  };

  // Цвет боковых стенок воздуховода: приточные — красные, вытяжные — синие. Варианты оттенка:
  // чистые «стандартные» цвета Revit выбиваются из спокойной палитры, а спокойные оттенки сливаются
  // с заливками (красный с П9, синий с В1), поэтому лучший компромисс — тёмные оттенки (темнее любой заливки).
  var WALL_PRESETS = [
    { id: 'standard', name: 'Чистые',       supply: '#FF0000', exhaust: '#0000FF' },
    { id: 'soft',     name: 'Спокойные',    supply: '#C0392B', exhaust: '#1F4FD8' },
    { id: 'dark',     name: 'Тёмные',       supply: '#6B1A14', exhaust: '#0B2257' },
    { id: 'darker',   name: 'Самые тёмные', supply: '#5A140F', exhaust: '#081B45' }
  ];
  var PREFIX = { supply: 'П', exhaust: 'В' };

  function buildGroup(kind) {
    return COLORS[kind].map(function (c, i) {
      var rgb = hexToRgb(c.hex);
      return {
        kind: kind,
        n: i + 1,
        code: PREFIX[kind] + (i + 1),
        name: c.name,
        nameUk: c.nameUk,
        reference: !!c.ref,
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
    COLORS: COLORS, WALL_PRESETS: WALL_PRESETS, PREFIX: PREFIX, SYSTEMS: SYSTEMS,
    hexToRgb: hexToRgb, rgbToHex: rgbToHex, rgbToLab: rgbToLab, deltaE: deltaE,
    windowStats: windowStats
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Palette = api;
})(typeof window !== 'undefined' ? window : this);
