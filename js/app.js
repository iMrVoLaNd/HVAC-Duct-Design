(function () {
  'use strict';

  var P = window.Palette;
  var KIND_TITLE = { supply: 'Приточные системы (П)', exhaust: 'Вытяжные системы (В)' };

  /* ---------- рисование воздуховода в плане ---------- */

  // Карточка: воздуховод 300x200 в плане — заливка, боковые стенки, фланцы, осевая, стрелка потока, марка.
  function ductSvg(s) {
    var x1 = 34, x2 = 206, y1 = 31, y2 = 79, ym = 55;
    var supply = s.kind === 'supply';
    var arrow = supply
      ? 'M70 21H170M162 16L170 21L162 26'
      : 'M170 21H70M78 16L70 21L78 26';
    return '<svg class="duct" viewBox="0 0 240 112" role="img" aria-label="Воздуховод системы ' + s.code + '">'
      + '<rect x="' + x1 + '" y="' + y1 + '" width="' + (x2 - x1) + '" height="' + (y2 - y1) + '" fill="' + s.hex + '"/>'
      + '<path d="M' + x1 + ' ' + y1 + 'H' + x2 + 'M' + x1 + ' ' + y2 + 'H' + x2 + '" stroke="' + s.wall + '" stroke-width="1.5" fill="none"/>'
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
      + '<div class="card__name"><b>' + s.code + '</b> ' + s.name
      + (s.reference ? ' <span class="badge" title="Цвет взят со скриншота-эталона">эталон</span>' : '') + '</div>'
      + '<div class="card__vals">'
      + '<button type="button" class="val" data-copy="' + s.hex + '" title="Скопировать HEX">' + s.hex + '</button>'
      + '<button type="button" class="val" data-copy="' + rgb + '" title="Скопировать RGB">' + s.rgb.join(' · ') + '</button>'
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
        + '<h2 class="group__title">' + KIND_TITLE[kind] + ' <small>' + pre + '1–' + pre + list.length
        + ' · стенки RGB ' + P.hexToRgb(P.WALL[kind]).join('·') + '</small></h2>'
        + swatchTable(list);
      out += '<div class="grid">' + list.map(cardHtml).join('') + '</div>';
      out += '</section>';
    });
    document.getElementById('groups').innerHTML = out;
  }

  /* ---------- проверка различимости ---------- */

  function quality(de) {
    if (de >= 20) return 'отлично';
    if (de >= 15) return 'хорошо';
    if (de >= 10) return 'заметно';
    return 'слабо';
  }

  function renderCheck() {
    var rows = '';
    ['supply', 'exhaust'].forEach(function (kind) {
      var list = P.SYSTEMS[kind], pre = P.PREFIX[kind];
      var st = P.windowStats(list, list.length);
      var names = st.pair.map(function (code) {
        return code + ' ' + list.filter(function (s) { return s.code === code; })[0].name;
      });
      rows += '<tr><th>' + pre + '1–' + pre + list.length + '</th>'
        + '<td><b>' + st.min.toFixed(1) + '</b></td>'
        + '<td>' + names[0] + ' и ' + names[1] + '</td>'
        + '<td class="q">' + quality(st.min) + '</td></tr>';
    });
    document.getElementById('check').innerHTML =
      '<h2 class="group__title">Проверка различимости</h2>'
      + '<p>Считаем разницу между цветами по формуле CIEDE2000 (ΔE) и показываем худшую пару в группе. '
      + 'ΔE ≥ 20 — цвета кардинально разные, ≥ 15 — уверенно разные, ≥ 10 — разница заметна, если цвета лежат рядом.</p>'
      + '<table class="stats"><thead><tr><th>Системы</th><th>Худшая пара, ΔE</th><th>Какая пара</th><th>Оценка</th></tr></thead>'
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
      svg += '<rect x="' + x1 + '" y="' + y + '" width="' + (x2 - x1) + '" height="' + h + '" fill="' + s.hex + '"/>'
        + '<path d="M' + x1 + ' ' + y + 'H' + x2 + 'M' + x1 + ' ' + (y + h) + 'H' + x2 + '" stroke="' + s.wall + '" stroke-width="1.2" fill="none"/>'
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

  function download(name, mime, text) {
    var blob = new Blob([text], { type: mime });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  function exportCsv() {
    var head = ['Система', 'Группа', 'Цвет', 'R', 'G', 'B', 'HEX', 'Стенки R', 'Стенки G', 'Стенки B'];
    var rows = allSystems().map(function (s) {
      var w = P.hexToRgb(s.wall);
      return [s.code, s.kind === 'supply' ? 'Приточная' : 'Вытяжная', s.name,
        s.rgb[0], s.rgb[1], s.rgb[2], s.hex, w[0], w[1], w[2]].join(';');
    });
    // BOM, чтобы Excel правильно открыл кириллицу
    download('hvac-palette.csv', 'text/csv;charset=utf-8', '\ufeff' + [head.join(';')].concat(rows).join('\r\n'));
  }

  function exportJson() {
    var data = allSystems().map(function (s) {
      return { system: s.code, kind: s.kind, color_name: s.name, rgb: s.rgb, hex: s.hex,
        wall_rgb: P.hexToRgb(s.wall) };
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

  render();
  renderCheck();
  renderFloor();
  bind();
})();
