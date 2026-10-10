(function () {
  'use strict';

  var P = window.Palette;
  var t = window.I18N.t;
  // Название цвета на текущем языке.
  function nm(s) { return window.I18N.getLang() === 'uk' ? s.nameUk : s.name; }
  var view = 'iso';           // 'iso' — объём, как на референсах; 'plan' — план Revit со стенками
  var filter = 'all';
  var isoWalls = false;       // подсвечивать ли боковые стенки (длинные рёбра) в объёмном виде
  var wallId = 'dark';        // вариант цвета боковых стенок (см. Palette.WALL_PRESETS)

  function wallPreset() {
    return P.WALL_PRESETS.filter(function (w) { return w.id === wallId; })[0];
  }
  function wallOf(kind) { return wallPreset()[kind]; }
  function rgbText(hex) { return P.hexToRgb(hex).join('·'); }

  // Применить выбранный цвет стенок: CSS-переменные (рамка заголовков, плашки) и подписи.
  function applyWalls() {
    var root = document.documentElement.style;
    root.setProperty('--supply', wallOf('supply'));
    root.setProperty('--exhaust', wallOf('exhaust'));
    document.getElementById('chip-supply').textContent = t('chipSupply', rgbText(wallOf('supply')));
    document.getElementById('chip-exhaust').textContent = t('chipExhaust', rgbText(wallOf('exhaust')));
  }

  function renderWallButtons() {
    document.getElementById('walls').innerHTML = P.WALL_PRESETS.map(function (w) {
      return '<button type="button" data-wall="' + w.id + '"' + (w.id === wallId ? ' class="is-active"' : '')
        + ' title="' + t('wallTitle', w.supply, w.exhaust) + '">'
        + '<i class="dot" style="background:' + w.supply + '"></i><i class="dot" style="background:' + w.exhaust + '"></i>'
        + t('wall_' + w.id) + '</button>';
    }).join('');
  }

  /* ---------- воздуховод в объёме (как BIM «Shaded with Edges» на референсах) ---------- */

  // Осветлить (t > 0) или затемнить (t < 0) цвет. Грани воздуховода — оттенки одного цвета системы.
  function shade(hex, t) {
    var target = t > 0 ? 255 : 0, k = Math.abs(t);
    return P.rgbToHex(P.hexToRgb(hex).map(function (v) { return v + (target - v) * k; }));
  }

  function add(p, v, k) { k = k === undefined ? 1 : k; return [p[0] + v[0] * k, p[1] + v[1] * k]; }
  function pts(list) { return list.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' '); }
  function poly(list, fill) {
    return '<polygon points="' + pts(list) + '" fill="' + fill + '" stroke="#1d1d1d" stroke-width=".9" stroke-linejoin="round"/>';
  }

  // Боковая грань — ровно цвет системы (чтобы HEX на карточке совпадал с тем, что видно), верх светлее.
  function ductIsoSvg(s) {
    var A = [60, 118], L = [132, -44], H = [0, -34], D = [-28, -15], T = [-5, 1.7];
    var AH = add(A, H), AL = add(A, L), ALH = add(AL, H);
    var out = '<svg class="duct" viewBox="0 0 240 140" role="img" aria-label="' + t('ductAria', s.code) + '">';

    // подвес
    var hang = add(add(AH, L, 0.5), D, 0.5);
    out += '<line x1="' + hang[0] + '" y1="' + hang[1] + '" x2="' + hang[0] + '" y2="10" stroke="#6b6b6b" stroke-width="1.1"/>';

    // боковая и верхняя грани
    out += poly([A, AL, ALH, AH], s.hex);
    out += poly([AH, ALH, add(ALH, D), add(AH, D)], shade(s.hex, 0.14));

    // боковые стенки: длинные рёбра воздуховода цветом группы (если включено)
    if (isoWalls) {
      var edge = function (p, q) {
        return '<line x1="' + p[0].toFixed(1) + '" y1="' + p[1].toFixed(1) + '" x2="' + q[0].toFixed(1) + '" y2="' + q[1].toFixed(1)
          + '" stroke="' + wallOf(s.kind) + '" stroke-width="1.9" stroke-linecap="round"/>';
      };
      out += edge(A, AL) + edge(AH, ALH) + edge(add(AH, D), add(ALH, D));
    }

    // стыки (рёбра жёсткости) — две полосы поперёк воздуховода
    [0.36, 0.68].forEach(function (u) {
      var w = 0.05;
      out += poly([add(A, L, u), add(A, L, u + w), add(add(A, L, u + w), H), add(add(A, L, u), H)], shade(s.hex, -0.1));
      out += poly([add(AH, L, u), add(AH, L, u + w), add(add(AH, L, u + w), D), add(add(AH, L, u), D)], shade(s.hex, 0.06));
    });

    // фланец на ближнем торце с тёмным проёмом
    function fp(sd, th) { return add(add(add(A, T), D, sd), H, th); }
    out += poly([fp(-0.14, -0.14), fp(1.14, -0.14), fp(1.14, 1.14), fp(-0.14, 1.14)], shade(s.hex, -0.08));
    out += poly([fp(0.15, 0.15), fp(0.85, 0.15), fp(0.85, 0.85), fp(0.15, 0.85)], '#2b2b2b');
    out += poly([fp(0.24, 0.24), fp(0.76, 0.24), fp(0.76, 0.76), fp(0.24, 0.76)], '#575757');

    // направление потока — стрелка под воздуховодом
    var a0 = add(add(A, [0, 16]), L, 0.2), a1 = add(add(A, [0, 16]), L, 0.8);
    var ux = L[0] / Math.hypot(L[0], L[1]), uy = L[1] / Math.hypot(L[0], L[1]);
    var tip = s.kind === 'supply' ? a1 : a0, tail = s.kind === 'supply' ? a0 : a1, dir = s.kind === 'supply' ? 1 : -1;
    var wing = function (sign) {
      return [tip[0] - dir * (ux * 7) + sign * (-uy * 3.5), tip[1] - dir * (uy * 7) + sign * (ux * 3.5)];
    };
    out += '<path d="M' + tail[0] + ' ' + tail[1] + 'L' + tip[0] + ' ' + tip[1]
      + 'M' + wing(1)[0] + ' ' + wing(1)[1] + 'L' + tip[0] + ' ' + tip[1] + 'L' + wing(-1)[0] + ' ' + wing(-1)[1]
      + '" stroke="#1d1d1d" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';

    // марка системы в кружке с выноской, как на референсах
    var anchor = add(add(AH, L, 0.82), D, 0.5);
    out += '<line x1="' + anchor[0] + '" y1="' + anchor[1] + '" x2="199" y2="34" stroke="#1d1d1d" stroke-width=".8"/>'
      + '<circle cx="213" cy="30" r="14" fill="#fff" stroke="#1d1d1d" stroke-width=".9"/>'
      + '<text x="213" y="34" text-anchor="middle" class="duct__tag duct__tag--iso">' + s.code + '</text>';

    return out + '</svg>';
  }

  /* ---------- воздуховод в плане (Revit: боковые стенки красные / синие) ---------- */

  // Фланцы: по краям (крупнее) и между секциями — белые прямоугольники с чёрным контуром, выступают за стенки.
  // Как в плане Revit: воздуховод делится стыками на 5 секций.
  function flangesSvg(x1, x2, y1, y2, endW, endOut, midW, midOut, stroke) {
    var out = '', i;
    function rect(cx, w, out_) {
      return '<rect x="' + (cx - w / 2).toFixed(1) + '" y="' + (y1 - out_) + '" width="' + w + '" height="' + (y2 - y1 + 2 * out_)
        + '" fill="#fff" stroke="#111" stroke-width="' + stroke + '"/>';
    }
    for (i = 1; i < 5; i++) out += rect(x1 + (x2 - x1) * i / 5, midW, midOut);
    return out + rect(x1, endW, endOut) + rect(x2, endW, endOut);
  }

  // Карточка (план Revit): заливка цветом системы, боковые стенки, фланцы-стыки, номер системы и выноска.
  function ductSvg(s) {
    var x1 = 34, x2 = 206, y1 = 34, y2 = 78;
    return '<svg class="duct" viewBox="0 0 240 100" role="img" aria-label="' + t('ductAria', s.code) + '">'
      + '<rect x="' + x1 + '" y="' + y1 + '" width="' + (x2 - x1) + '" height="' + (y2 - y1) + '" fill="' + s.hex + '"/>'
      + '<path d="M' + x1 + ' ' + y1 + 'H' + x2 + 'M' + x1 + ' ' + y2 + 'H' + x2 + '" stroke="' + wallOf(s.kind) + '" stroke-width="1.8" fill="none"/>'
      + flangesSvg(x1, x2, y1, y2, 6, 7, 4.5, 4, 1)
      // выноска: от номера системы внутрь воздуховода
      + '<line x1="127" y1="21" x2="115" y2="62" stroke="#111" stroke-width="1"/>'
      + '<text x="128" y="16" text-anchor="middle" class="duct__tag duct__tag--plan">' + s.code + '</text>'
      + '</svg>';
  }

  /* ---------- карточки и группы ---------- */

  function cardHtml(s) {
    var rgb = s.rgb.join(', ');
    return '<article class="card" data-kind="' + s.kind + '">'
      + (view === 'iso' ? ductIsoSvg(s) : ductSvg(s))
      + '<div class="card__meta">'
      + '<div class="card__name"><b>' + s.code + '</b> ' + nm(s)
      + (s.reference ? ' <span class="badge" title="' + t('badgeTitle') + '">' + t('badge') + '</span>' : '') + '</div>'
      + '<div class="card__vals">'
      + '<button type="button" class="val" data-copy="' + s.hex + '" title="' + t('copyHex') + '">' + s.hex + '</button>'
      + '<button type="button" class="val" data-copy="' + rgb + '" title="' + t('copyRgb') + '">' + s.rgb.join(' · ') + '</button>'
      + '</div></div></article>';
  }

  // Таблица цветового кодирования — квадраты с кодом, как внизу скриншота-эталона.
  function swatchTable(list) {
    return '<div class="swatches">' + list.map(function (s) {
      return '<div class="swatch"><i style="background:' + s.hex + '"></i><span>' + s.code + '</span></div>';
    }).join('') + '</div>';
  }

  function render() {
    var out = '';
    ['supply', 'exhaust'].forEach(function (kind) {
      var list = P.SYSTEMS[kind], pre = P.PREFIX[kind];
      out += '<section class="group group--' + kind + '" data-kind="' + kind + '">'
        + '<h2 class="group__title">' + t(kind === 'supply' ? 'titleSupply' : 'titleExhaust') + ' <small>' + pre + '1–' + pre + list.length
        + (view === 'plan' ? t('wallsRgb', rgbText(wallOf(kind))) : '') + '</small></h2>'
        + swatchTable(list);
      out += '<div class="grid">' + list.map(cardHtml).join('') + '</div>';
      out += '</section>';
    });
    document.getElementById('groups').innerHTML = out;
    applyFilter();
  }

  function applyFilter() {
    document.querySelectorAll('.group').forEach(function (g) {
      g.hidden = filter !== 'all' && g.dataset.kind !== filter;
    });
  }

  /* ---------- проверка различимости ---------- */

  function quality(de) {
    if (de >= 20) return t('q20');
    if (de >= 15) return t('q15');
    if (de >= 10) return t('q10');
    return t('q0');
  }

  function renderCheck() {
    var rows = '';
    ['supply', 'exhaust'].forEach(function (kind) {
      var list = P.SYSTEMS[kind], pre = P.PREFIX[kind];
      var st = P.windowStats(list, list.length);
      var names = st.pair.map(function (code) {
        return code + ' ' + nm(list.filter(function (s) { return s.code === code; })[0]);
      });
      rows += '<tr><th>' + pre + '1–' + pre + list.length + '</th>'
        + '<td><b>' + st.min.toFixed(1) + '</b></td>'
        + '<td>' + names[0] + t('pairAnd') + names[1] + '</td>'
        + '<td class="q">' + quality(st.min) + '</td></tr>';
    });
    document.getElementById('check').innerHTML =
      '<h2 class="group__title">' + t('checkTitle') + '</h2>'
      + '<p>' + t('checkText') + '</p>'
      + '<table class="stats"><thead><tr><th>' + t('thSystems') + '</th><th>' + t('thWorst') + '</th><th>' + t('thPair')
      + '</th><th>' + t('thRating') + '</th></tr></thead>'
      + '<tbody>' + rows + '</tbody></table>';
  }

  /* ---------- «этаж»: параллельные воздуховоды ---------- */

  function renderFloor() {
    var n = +document.getElementById('floor-range').value;
    var kind = document.querySelector('#floor-kind .is-active').dataset.kind;
    document.getElementById('floor-n').textContent = n;

    var items = [];
    for (var i = 0; i < n; i++) {
      if (kind !== 'exhaust') items.push(P.SYSTEMS.supply[i]);
      if (kind !== 'supply') items.push(P.SYSTEMS.exhaust[i]);
    }
    var pitch = 22, h = 14, x1 = 64, x2 = 676, top = 14;
    var svg = '<svg viewBox="0 0 740 ' + (top * 2 + items.length * pitch) + '" class="floor__svg" role="img" aria-label="' + t('floorAria') + '">';
    items.forEach(function (s, i) {
      var y = top + i * pitch;
      svg += '<rect x="' + x1 + '" y="' + y + '" width="' + (x2 - x1) + '" height="' + h + '" fill="' + s.hex + '"/>'
        + '<path d="M' + x1 + ' ' + y + 'H' + x2 + 'M' + x1 + ' ' + (y + h) + 'H' + x2 + '" stroke="' + wallOf(s.kind) + '" stroke-width="1.2" fill="none"/>'
        + flangesSvg(x1, x2, y, y + h, 3, 2, 2.4, 1.6, .7)
        + '<text x="' + (x1 - 10) + '" y="' + (y + h - 2) + '" text-anchor="end" class="floor__lbl">' + s.code + '</text>'
        + '<text x="' + (x2 + 10) + '" y="' + (y + h - 2) + '" class="floor__lbl">' + s.code + '</text>';
    });
    document.getElementById('floor-plan').innerHTML = svg + '</svg>';
  }

  /* ---------- копирование и экспорт ---------- */

  var toastTimer;
  function toast(msg) {
    var el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('is-on'); }, 1600);
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy') ? resolve() : reject(); } catch (e) { reject(e); }
      document.body.removeChild(ta);
    });
  }

  function allSystems() {
    return P.SYSTEMS.supply.concat(P.SYSTEMS.exhaust);
  }

  function download(name, mime, text) {
    var blob = new Blob([text], { type: mime });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  function exportCsv() {
    var head = t('csvHead');
    var rows = allSystems().map(function (s) {
      var w = P.hexToRgb(wallOf(s.kind));
      return [s.code, s.kind === 'supply' ? t('kindSupply') : t('kindExhaust'), nm(s),
        s.rgb[0], s.rgb[1], s.rgb[2], s.hex, w[0], w[1], w[2]].join(';');
    });
    // BOM, чтобы Excel правильно открыл кириллицу
    download('hvac-palette.csv', 'text/csv;charset=utf-8', '\ufeff' + [head.join(';')].concat(rows).join('\r\n'));
  }

  function exportJson() {
    var data = allSystems().map(function (s) {
      return { system: s.code, kind: s.kind, color_name: nm(s), rgb: s.rgb, hex: s.hex,
        wall_rgb: P.hexToRgb(wallOf(s.kind)), wall_hex: wallOf(s.kind) };
    });
    download('hvac-palette.json', 'application/json', JSON.stringify(data, null, 2));
  }

  /* ---------- события ---------- */

  function bind() {
    document.getElementById('groups').addEventListener('click', function (e) {
      var b = e.target.closest('[data-copy]');
      if (!b) return;
      copyText(b.dataset.copy).then(
        function () { toast(t('copied', b.dataset.copy)); },
        function () { toast(t('copyFail')); });
    });

    document.getElementById('filter').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      this.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
      filter = b.dataset.filter;
      applyFilter();
    });

    document.getElementById('view').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      this.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
      view = b.dataset.view;
      render();
    });

    document.getElementById('walls').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      wallId = b.dataset.wall;
      this.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
      applyWalls();
      render();
      renderFloor();
    });

    document.getElementById('iso-walls').addEventListener('click', function () {
      isoWalls = !isoWalls;
      this.setAttribute('aria-pressed', String(isoWalls));
      render();
    });

    document.getElementById('lang').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      window.I18N.setLang(b.dataset.lang);
      renderAll();
    });

    document.getElementById('floor-kind').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      this.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
      renderFloor();
    });
    document.getElementById('floor-range').addEventListener('input', renderFloor);
    document.getElementById('dl-csv').addEventListener('click', exportCsv);
    document.getElementById('dl-json').addEventListener('click', exportJson);
  }

  // Всё, что зависит от языка, перерисовываем целиком.
  function renderAll() {
    window.I18N.applyStatic();
    document.querySelectorAll('#lang button').forEach(function (x) {
      x.classList.toggle('is-active', x.dataset.lang === window.I18N.getLang());
    });
    renderWallButtons();
    applyWalls();
    render();
    renderCheck();
    renderFloor();
  }

  renderAll();
  bind();
})();
