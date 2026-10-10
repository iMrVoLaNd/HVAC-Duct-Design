/*
 * Палитра систем вентиляции — в стиле эталонного скриншота (матовые «сигнальные» цвета).
 *
 * Первые цвета в списках — ровно плашки со скриншота (П1, Пн, Пд, Р и В1, Ввыбр, Вд).
 * Остальные подобраны скриптом tools/generate-palette.js в том же стиле так, чтобы каждый
 * следующий цвет сильнее всего отличался от уже выбранных: первые десять — самые разные,
 * дальше различия постепенно уменьшаются.
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
      '#C1593C', '#629D53', '#FD7600', '#D29E3B', '#4B30A3', '#DC42A9', '#5A4309', '#075C38', '#802441', '#906AE7',
      '#802904', '#A6B416', '#94713A', '#825286', '#D41B4C', '#406F0F', '#88851A', '#BC687C', '#308563', '#FD8C6C',
      '#81077B', '#BB1971', '#95521C', '#BF6D06', '#A3051F', '#9B72AB', '#3BC359', '#9A4B4D', '#9A48BF', '#563A71',
      '#324E16', '#048B16', '#ED3677', '#628E01', '#B43801', '#D5595E', '#EC9846', '#6E55A3', '#638044', '#8AB958'
    ],
    exhaust: [
      '#0150B7', '#405364', '#553C3F', '#0B9371', '#937E63', '#8F7A96', '#5A4309', '#208CA7', '#16503E', '#7D72E5',
      '#925238', '#647154', '#2483DE', '#7A828B', '#44483F', '#5C547B', '#A17772', '#376B6F', '#6D615C', '#7D596A',
      '#6B877F', '#586E95', '#633E29', '#775F3D', '#156A92', '#423D88', '#178581', '#524E58', '#2C4C4E', '#828277',
      '#596661', '#7D7CB0', '#236F58', '#8B7E82', '#6F6A7E', '#6057B1', '#57717E', '#44553A', '#514535', '#76504C'
    ]
  };

  // Сколько первых цветов в группе взято со скриншота как эталон.
  var REFERENCE_COUNT = { supply: 4, exhaust: 3 };

  // Цвет боковых стенок воздуховода — «стандартные» красный и синий.
  var WALL = { supply: '#FF0000', exhaust: '#0000FF' };
  var PREFIX = { supply: 'П', exhaust: 'В' };

  /* ---------- название цвета (грубо, по оттенку) ---------- */

  function colorName(lab) {
    var L = lab[0], C = Math.hypot(lab[1], lab[2]);
    var h = Math.atan2(lab[2], lab[1]) * 180 / Math.PI;
    if (h < 0) h += 360;
    if (C < 14) {
      if (L < 46 && (h < 60 || h >= 330)) return 'Тёмно-коричневый';
      return L < 30 ? 'Графитовый' : 'Серый';
    }
    if (C < 22 && h >= 200 && h < 300) return 'Сланцевый';
    if (h >= 30 && h < 95 && C < 42) return L < 46 ? 'Коричневый' : 'Бежевый';
    if (C < 30 && (h >= 300 || h < 14)) return 'Пыльно-лиловый';
    var name;
    if (h >= 340 || h < 14) name = L >= 58 ? 'Розовый' : 'Малиновый';
    else if (h < 35) name = 'Красный';
    else if (h < 52) name = 'Кирпичный';
    else if (h < 70) name = 'Оранжевый';
    else if (h < 95) name = 'Золотистый';
    else if (h < 125) name = 'Лаймовый';
    else if (h < 150) name = 'Зелёный';
    else if (h < 200) name = 'Изумрудный';
    else if (h < 250) name = 'Бирюзовый';
    else if (h < 285) name = 'Голубой';
    else if (h < 303) name = 'Синий';
    else if (h < 318) name = 'Фиолетовый';
    else name = 'Пурпурный';
    return L < 38 ? name + ' тёмный' : name;
  }

  function buildGroup(kind) {
    return COLORS[kind].map(function (hex, i) {
      var rgb = hexToRgb(hex), lab = rgbToLab(rgb);
      return {
        kind: kind,
        n: i + 1,
        code: PREFIX[kind] + (i + 1),
        name: colorName(lab),
        reference: i < REFERENCE_COUNT[kind],
        wall: WALL[kind],
        hex: hex,
        rgb: rgb,
        lab: lab
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
    colorName: colorName, windowStats: windowStats
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Palette = api;
})(typeof window !== 'undefined' ? window : this);
