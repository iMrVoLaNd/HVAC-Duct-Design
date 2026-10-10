/*
 * Подбор палитры в стиле скриншота-эталона (матовые «сигнальные» цвета).
 *
 *   node tools/generate-palette.js
 *
 * Берёт эталонные цвета (СЕМЬ плашек со скриншота) как первые в списках, а остальные
 * подбирает «методом самой дальней точки»: каждый следующий цвет — тот из кандидатов,
 * который сильнее всего отличается (CIEDE2000) от уже выбранных. Кандидаты ограничены
 * матовым диапазоном по светлоте и насыщенности, как у эталона.
 *
 * Результат печатается в виде массивов — вставьте их в js/palette.js (объект COLORS).
 */
'use strict';

var P = require('../js/palette.js');

var COUNT = 40;

// Эталон со скриншота (нижняя таблица цветового кодирования).
var SEEDS = {
  supply:  ['#C1593C', '#629D53', '#FD7600', '#D29E3B'],   // П1, Пн, Пд, Р
  exhaust: ['#0150B7', '#405364', '#553C3F']               // В1, Ввыбр, Вд
};

// Какие оттенки (угол hue в Lab) допустимы в группе. Приточные — «тёплые» + зелёные + фиолетовые,
// вытяжные — холодные, серые и коричневые.
function allowed(kind, L, C, h) {
  var cool = h >= 165 && h < 305;
  // Общие правила «стиля» — все цвета спокойные, средней светлоты, как семь эталонных плашек:
  if (L < 34) return kind === 'exhaust' && C < 16;          // совсем тёмные — только нейтральные (как графит В3)
  if (L > 56 && C < 50) return false;                       // без пастели
  if (L > 56 && !(h >= 40 && h < 150)) return false;        // светлые — только тёплые (оранжевый, золотой, зелёный)
  if (h >= 70 && h < 125 && L < 58) return false;           // без грязных тёмно-жёлтых и болотных
  // Насыщенность — как у эталонных плашек (кирпичный C54, зелёный C47, золотой C58): без кислотных цветов.
  if (kind === 'supply') return C >= 30 && C <= 54 && !cool;
  if (C < 22) return L < 58;                                // серые, сланцевые
  if (cool) return C <= 60;                                 // бирюзовый, голубой, синий, индиго
  return h >= 35 && h < 70 && L < 46 && C < 42;             // коричневые
}

function labToRgb(L, a, b) {
  var fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200;
  function inv(t) { return t * t * t > 0.008856 ? t * t * t : (t - 16 / 116) / 7.787; }
  var x = inv(fx) * 0.95047, y = inv(fy), z = inv(fz) * 1.08883;
  var lin = [
    x * 3.2404542 + y * -1.5371385 + z * -0.4985314,
    x * -0.9692660 + y * 1.8760108 + z * 0.0415560,
    x * 0.0556434 + y * -0.2040259 + z * 1.0572252
  ];
  return lin.map(function (v) {
    v = v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(Math.max(v, 0), 1 / 2.4) - 0.055;
    return v * 255;
  });
}

function candidates(kind) {
  var out = [];
  // Светлота и насыщенность — как у семи эталонных плашек (L 28-68, C до ~85): матовые, не пастель и не неон.
  for (var L = 26; L <= 70; L += 4) {
    for (var C = 0; C <= 66; C += 4) {
      for (var h = 0; h < 360; h += 6) {
        if (!allowed(kind, L, C, h)) continue;
        var rad = h * Math.PI / 180;
        var rgb = labToRgb(L, C * Math.cos(rad), C * Math.sin(rad));
        if (rgb.some(function (v) { return v < 0 || v > 255; })) continue;
        var hex = P.rgbToHex(rgb);
        out.push({ hex: hex, lab: P.rgbToLab(P.hexToRgb(hex)) });
      }
    }
  }
  return out;
}

function pick(kind) {
  var chosen = SEEDS[kind].map(function (hex) { return { hex: hex, lab: P.rgbToLab(P.hexToRgb(hex)) }; });
  var pool = candidates(kind);
  while (chosen.length < COUNT) {
    var best = null, bestD = -1;
    pool.forEach(function (c) {
      var d = Infinity;
      chosen.forEach(function (s) { d = Math.min(d, P.deltaE(c.lab, s.lab)); });
      if (d > bestD) { bestD = d; best = c; }
    });
    chosen.push(best);
  }
  return chosen;
}

['supply', 'exhaust'].forEach(function (kind) {
  var list = pick(kind);
  console.log('\n// ' + kind + ' (' + list.length + ')');
  console.log(JSON.stringify(list.map(function (c) { return c.hex; })));
});
