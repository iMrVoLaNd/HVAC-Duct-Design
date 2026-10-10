(function () {
  'use strict';

  var P = window.Palette;
  var KIND_TITLE = { supply: 'Приточные системы (П)', exhaust: 'Вытяжные системы (В)' };

  /* ---------- общие заливки (штриховки) ---------- */

  function fillRef(s) {
    return s.pattern === 'solid' ? s.hex : 'url(#fill-' + s.kind + '-' + s.n + ')';
  }

  function buildDefs() {
    var defs = document.querySelector('#defs defs');
    var html = '';
    ['supply', 'exhaust'].forEach(function (kind) {
      P.SYSTEMS[kind].forEach(function (s) {
        var id = 'fill-' + kind + '-' + s.n;
        if (s.pattern === 'diag') {
          html += '<pattern id="' + id + '" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            + '<rect width="7" height="7" fill="' + s.hex + '"/>'
            + '<line x1="0" y1="0" x2="0" y2="7" stroke="#fff" stroke-width="1.8" stroke-opacity=".8"/></pattern>';
        } else if (s.pattern === 'cross') {
          html += '<pattern id="' + id + '" width="8" height="8" patternUnits="userSpaceOnUse">'
            + '<rect width="8" height="8" fill="' + s.hex + '"/>'
            + '<path d="M0 .5H8M.5 0V8" stroke="#fff" stroke-width="1.4" stroke-opacity=".8" fill="none"/></pattern>';
        } else if (s.pattern === 'dots') {
          html += '<pattern id="' + id + '" width="7" height="7" patternUnits="userSpaceOnUse">'
            + '<rect width="7" height="7" fill="' + s.hex + '"/>'
            + '<circle cx="3.5" cy="3.5" r="1.5" fill="#fff" fill-opacity=".85"/></pattern>';
        }
      });
    });
    defs.innerHTML = html;
  }

  /* ---------- рисование воздуховода в плане ---------- */

  // Карточка: воздуховод 300x200 в плане — заливка, боковые стенки, фланцы, осевая, стрелка потока, марка.
  function ductSvg(s) {
    var x1 = 34, x2 = 206, y1 = 34, y2 = 76, ym = 55;
    var supply = s.kind === 'supply';
    var arrow = supply
      ? 'M70 21H170M162 16L170 21L162 26'
      : 'M170 21H70M78 16L70 21L78 26';
    return '<svg class="duct" viewBox="0 0 240 112" role="img" aria-label="Воздуховод системы ' + s.code + '">'
      + '<rect x="' + x1 + '" y="' + y1 + '" width="' + (x2 - x1) + '" height="' + (y2 - y1) + '" fill="' + fillRef(s) + '"/>'
      + '<path d="M' + x1 + ' ' + y1 + 'H' + x2 + 'M' + x1 + ' ' + y2 + 'H' + x2 + '" stroke="' + s.wall + '" stroke-width="4.5" fill="none"/>'
      // фланцы
      + '<rect x="' + (x1 - 6) + '" y="' + (y1 - 6) + '" width="6" height="' + (y2 - y1 + 12) + '" fill="#fff" stroke="#111" stroke-width="1"/>'
      + '<rect x="' + x2 + '" y="' + (y1 - 6) + '" width="6" height="' + (y2 - y1 + 12) + '" fill="#fff" stroke="#111" stroke-width="1"/>'
      // осевая линия
      + '<path d="M14 ' + ym + 'H226" stroke="#111" stroke-width=".8" stroke-dasharray="14 3 2 3" fill="none"/>'
      // направление потока
      + '<path d="' + arrow + '" stroke="#111" stroke-width="1.2" fill="none"/>'
      // марка системы
      + '<rect x="104" y="44" width="32" height="22" rx="2" fill="#fff" stroke="#111" stroke-width="1"/>'
      + '<text x="120" y="60" text-anchor="middle" class="duct__tag">' + s.code + '</text>'
      // размерная линия
      + '<path d="M' + x1 + ' 95H' + x2 + 'M' + x1 + ' 90V100M' + x2 + ' 90V100" stroke="#111" stroke-width=".8" fill="none"/>'
      + '<text x="120" y="108" text-anchor="middle" class="duct__dim">L = 2000</text>'
      + '</svg>';
  }

  /* ---------- карточки и группы ---------- */

  function cardHtml(s) {
    var rgb = s.rgb.join(', ');
    return '<article class="card" data-kind="' + s.kind + '">'
      + ductSvg(s)
      + '<div class="card__meta">'
      + '<div class="card__name"><b>' + s.code + '</b> ' + s.name + '</div>'
      + '<div class="card__vals">'
      + '<button type="button" class="val" data-copy="' + s.hex + '" title="Скопировать HEX">' + s.hex + '</button>'
      + '<button type="button" class="val" data-copy="' + rgb + '" title="Скопировать RGB">' + s.rgb.join(' · ') + '</button>'
      + '</div></div></article>';
  }

  function render() {
    var out = '';
    ['supply', 'exhaust'].forEach(function (kind) {
      var list = P.SYSTEMS[kind], pre = P.PREFIX[kind];
      out += '<section class="group group--' + kind + '" data-kind="' + kind + '">'
        + '<h2 class="group__title">' + KIND_TITLE[kind] + ' <small>' + pre + '1–' + pre + list.length
        + ' · стенки RGB ' + P.hexToRgb(P.WALL[kind]).join('·') + '</small></h2>';
      P.TIERS.forEach(function (tier, t) {
        var a = t * 10 + 1, b = t * 10 + 10;
        out += '<h3 class="tier">' + pre + a + '–' + pre + b + ' <span>' + tier.label + '</span></h3>'
          + '<div class="grid">' + list.slice(t * 10, t * 10 + 10).map(cardHtml).join('') + '</div>';
      });
      out += '</section>';
    });
    document.getElementById('groups').innerHTML = out;
  }

  /* ---------- проверка различимости ---------- */

  function quality(de) {
    if (de >= 20) return 'отлично';
    if (de >= 15) return 'хорошо';
    return 'на пределе';
  }

  function renderCheck() {
    var rows = ['supply', 'exhaust'].map(function (kind) {
      var st = P.windowStats(P.SYSTEMS[kind], 10);
      var pre = P.PREFIX[kind];
      return '<tr><th>' + pre + '</th>'
        + '<td><b>' + st.min.toFixed(1) + '</b></td>'
        + '<td>' + st.pair[0] + ' и ' + st.pair[1] + '</td>'
        + '<td class="q">' + quality(st.min) + '</td></tr>';
    }).join('');
    document.getElementById('check').innerHTML =
      '<h2 class="group__title">Проверка различимости</h2>'
      + '<p>Для каждых 10 систем подряд (П1…П10, П2…П11 и т. д.) считаем разницу цветов по формуле CIEDE2000 (ΔE). '
      + 'Если заливка разная (сплошная / штриховка / сетка / точки), системы различимы по рисунку. '
      + 'ΔE ≥ 15 — цвета уверенно разные, ≥ 20 — кардинально.</p>'
      + '<table class="stats"><thead><tr><th>Группа</th><th>Худшая пара, ΔE</th><th>Какая пара</th><th>Оценка</th></tr></thead>'
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
    var svg = '<svg viewBox="0 0 740 ' + (top * 2 + items.length * pitch) + '" class="floor__svg" role="img" aria-label="Параллельные воздуховоды">';
    items.forEach(function (s, i) {
      var y = top + i * pitch;
      svg += '<rect x="' + x1 + '" y="' + y + '" width="' + (x2 - x1) + '" height="' + h + '" fill="' + fillRef(s) + '"/>'
        + '<path d="M' + x1 + ' ' + y + 'H' + x2 + 'M' + x1 + ' ' + (y + h) + 'H' + x2 + '" stroke="' + s.wall + '" stroke-width="2.4" fill="none"/>'
        + '<rect x="' + (x1 - 3) + '" y="' + (y - 2) + '" width="3" height="' + (h + 4) + '" fill="#fff" stroke="#111" stroke-width=".8"/>'
        + '<rect x="' + x2 + '" y="' + (y - 2) + '" width="3" height="' + (h + 4) + '" fill="#fff" stroke="#111" stroke-width=".8"/>'
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

  function patternLabel(id) {
    return P.TIERS.filter(function (t) { return t.pattern === id; })[0].label;
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
    var head = ['Система', 'Группа', 'Цвет', 'R', 'G', 'B', 'HEX', 'Заливка', 'Стенки R', 'Стенки G', 'Стенки B'];
    var rows = allSystems().map(function (s) {
      var w = P.hexToRgb(s.wall);
      return [s.code, s.kind === 'supply' ? 'Приточная' : 'Вытяжная', s.name,
        s.rgb[0], s.rgb[1], s.rgb[2], s.hex, patternLabel(s.pattern), w[0], w[1], w[2]].join(';');
    });
    // BOM, чтобы Excel правильно открыл кириллицу
    download('hvac-palette.csv', 'text/csv;charset=utf-8', '\ufeff' + [head.join(';')].concat(rows).join('\r\n'));
  }

  function exportJson() {
    var data = allSystems().map(function (s) {
      return { system: s.code, kind: s.kind, color_name: s.name, rgb: s.rgb, hex: s.hex,
        pattern: s.pattern, wall_rgb: P.hexToRgb(s.wall) };
    });
    download('hvac-palette.json', 'application/json', JSON.stringify(data, null, 2));
  }

  /* ---------- события ---------- */

  function bind() {
    document.getElementById('groups').addEventListener('click', function (e) {
      var b = e.target.closest('[data-copy]');
      if (!b) return;
      copyText(b.dataset.copy).then(
        function () { toast('Скопировано: ' + b.dataset.copy); },
        function () { toast('Не удалось скопировать'); });
    });

    document.getElementById('filter').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      this.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
      var f = b.dataset.filter;
      document.querySelectorAll('.group').forEach(function (g) {
        g.hidden = f !== 'all' && g.dataset.kind !== f;
      });
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

  buildDefs();
  render();
  renderCheck();
  renderFloor();
  bind();
})();
