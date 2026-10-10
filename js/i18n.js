/*
 * Переводы интерфейса: украинский (uk) и английский (en).
 *
 * В index.html тексты помечены атрибутами:
 *   data-i18n="ключ"            — подставить текст
 *   data-i18n-html="ключ"       — подставить HTML (там, где внутри есть разметка)
 *   data-i18n-attr="title:ключ;aria-label:ключ" — перевести атрибуты
 * В js/app.js — I18N.t('ключ', аргумент1, ...), где в тексте {0}, {1} — места для аргументов.
 *
 * Чтобы добавить язык — скопируйте блок en и переведите значения.
 */
(function (root) {
  'use strict';

  var CHIP_S = '<span class="chip chip--wall chip--supply" id="chip-supply"></span>';
  var CHIP_E = '<span class="chip chip--wall chip--exhaust" id="chip-exhaust"></span>';

  var DICT = {
    en: {
      docTitle: 'Ventilation System Color Palette',
      docDescription: 'Color coding of supply and exhaust systems in BIM/CAD: 20 colors per group in a signal-palette style.',

      ribbonShow: 'Show', showAll: 'All', showSupply: 'Supply', showExhaust: 'Exhaust', showPipes: 'Pipes',
      ribbonView: 'View', viewIso: '3D', viewPlan: 'Revit plan',
      ribbonWalls: 'Walls', wallsIso: 'In 3D', ribbonThick: 'Thickness',
      wallsIsoTitle: 'Highlight the long edges of the duct with the wall color in the 3D view',
      ribbonExport: 'Export', ribbonLang: 'Language',
      ariaShow: 'Show systems', ariaView: 'Duct view', ariaWalls: 'Side wall color', ariaThick: 'Wall line thickness',
      ariaExport: 'Export', ariaLang: 'Interface language',

      sheetTitle: 'Ventilation System Color Palette',
      sheetSubtitle: 'Recommended duct color coding (BIM / CAD)',
      noteRead: '<b>How to read.</b> In the “Revit plan” view the duct side walls are drawn in the group color (' + CHIP_S
        + ' for supply, ' + CHIP_E + ' for exhaust) and the fill inside is the system color. The wall shade is switched in the ribbon (“Walls”), '
        + 'and in the 3D view the walls are turned on with the “In 3D” button. Click a HEX or RGB value to copy it for a view filter.',
      noteSource: '<b>Where the colors come from.</b> Colors marked “reference” are taken exactly from your references: supply — the earthy palette '
        + 'from the legends (terracotta, grass green, mustard, ochre, brick), exhaust В1–В3 — from the screenshot. The rest are hand-picked in the same '
        + 'character. Twenty colors per group are ordered so that systems with neighboring numbers look as different as possible.',
      notePipes: '<b>Pipes.</b> The piping colors are taken from your K1 air-conditioning scheme and assigned as you asked: '
        + 'gas — green, liquid — purple, drain — orange, recirculation — pink. Codes К1.1–К1.4 follow the scheme and are easy to rename.',
      ariaCheck: 'Distinguishability check',

      titleSupply: 'Supply systems (П)', titleExhaust: 'Exhaust systems (В)', titlePipes: 'Air-conditioning piping (К)',
      wallsRgb: ' · walls RGB {0}',
      chipSupply: 'supply {0}', chipExhaust: 'exhaust {0}',
      wallTitle: 'Supply {0}, exhaust {1}',
      wall_standard: 'Pure', wall_signal: 'Signal', wall_soft: 'Soft', wall_muted: 'Muted', wall_dark: 'Dark', wall_black: 'Black', wall_grey: 'Grey',
      thick_thin: 'Thin', thick_medium: 'Medium', thick_thick: 'Thick',
      badge: 'reference', badgeTitle: 'Color taken from your reference',
      copyHex: 'Copy HEX', copyRgb: 'Copy RGB',
      copied: 'Copied: {0}', copyFail: 'Could not copy',
      ductAria: 'Duct of system {0}', pipeAria: 'Pipe {0}',

      checkTitle: 'Distinguishability check',
      checkText: 'We measure the difference between colors with the CIEDE2000 formula (ΔE) and show the worst pair for each scope. '
        + 'ΔE ≥ 20 — radically different, ≥ 15 — clearly different, ≥ 10 — the difference is noticeable when the colors sit side by side.',
      thSystems: 'Systems · scope', rowNeighbors: 'neighbor numbers', rowWindow: 'any 5 in a row', rowAll: 'all pairs', thWorst: 'Worst pair, ΔE', thPair: 'Which pair', thRating: 'Rating',
      pairAnd: ' and ',
      q20: 'excellent', q15: 'good', q10: 'noticeable', q0: 'weak',

      floorTitle: 'Check on a “floor”',
      floorHint: 'Systems run side by side, as in a corridor. Move the slider and see whether neighbors blend together.',
      floorCount: 'Systems of each type:',
      floorSupply: 'Supply', floorExhaust: 'Exhaust', floorBoth: 'Both',
      floorAria: 'Parallel ducts',

      tbProject: 'Project', tbProjectVal: 'Ventilation system palette',
      tbSupply: 'Supply', tbExhaust: 'Exhaust',
      tbNext: 'Next stage', tbNextVal: 'Supply-exhaust (ПВ)',

      csvHead: ['System', 'Group', 'Color', 'R', 'G', 'B', 'HEX', 'Wall R', 'Wall G', 'Wall B'],
      kindSupply: 'Supply', kindExhaust: 'Exhaust', kindPipes: 'Piping'
    },

    uk: {
      docTitle: 'Палітра систем вентиляції',
      docDescription: 'Колірне кодування припливних і витяжних систем у BIM/CAD: по 20 кольорів на групу в стилі сигнальної палітри.',

      ribbonShow: 'Показати', showAll: 'Усі', showSupply: 'Припливні', showExhaust: 'Витяжні', showPipes: 'Трубопроводи',
      ribbonView: 'Вигляд', viewIso: 'Об’єм', viewPlan: 'План Revit',
      ribbonWalls: 'Стінки', wallsIso: 'В об’ємі', ribbonThick: 'Товщина',
      wallsIsoTitle: 'Підсвітити довгі ребра повітровода кольором стінок у вигляді «Об’єм»',
      ribbonExport: 'Експорт', ribbonLang: 'Мова',
      ariaShow: 'Показати системи', ariaView: 'Вигляд повітровода', ariaWalls: 'Колір бічних стінок', ariaThick: 'Товщина лінії стінок',
      ariaExport: 'Експорт', ariaLang: 'Мова інтерфейсу',

      sheetTitle: 'Колірна палітра систем вентиляції',
      sheetSubtitle: 'Рекомендоване кодування повітроводів (BIM / CAD)',
      noteRead: '<b>Як читати.</b> У вигляді «План Revit» бічні стінки повітровода пофарбовані в колір групи (' + CHIP_S
        + ' у припливних, ' + CHIP_E + ' у витяжних), усередині — заливка кольором системи. Відтінок стінок перемикається в стрічці («Стінки»), '
        + 'а у вигляді «Об’єм» стінки вмикаються кнопкою «В об’ємі». Натисніть на HEX або RGB, щоб скопіювати значення для фільтра виду.',
      noteSource: '<b>Звідки кольори.</b> Кольори з позначкою «еталон» взяті точно з ваших референсів: припливні — земляна палітра з легенд '
        + '(теракот, трав’яний, гірчичний, охра, цегляний), витяжні В1–В3 — зі скриншота. Решта підібрана вручну в тому самому характері. '
        + 'Двадцять кольорів на групу розставлені так, щоб системи з сусідніми номерами якомога сильніше відрізнялися.',
      notePipes: '<b>Трубопроводи.</b> Кольори труб зняті з вашої схеми кондиціонування К1 і розподілені так, як ви просили: '
        + 'газ — зелений, рідина — фіолетовий, дренаж — оранжевий, рециркуляція — рожевий. Коди К1.1–К1.4 відповідають схемі, їх легко перейменувати.',
      ariaCheck: 'Перевірка розрізнюваності',

      titleSupply: 'Припливні системи (П)', titleExhaust: 'Витяжні системи (В)', titlePipes: 'Трубопроводи кондиціонування (К)',
      wallsRgb: ' · стінки RGB {0}',
      chipSupply: 'припливні {0}', chipExhaust: 'витяжні {0}',
      wallTitle: 'Припливні {0}, витяжні {1}',
      wall_standard: 'Чисті', wall_signal: 'Сигнальні', wall_soft: 'Спокійні', wall_muted: 'Приглушені', wall_dark: 'Темні', wall_black: 'Чорні', wall_grey: 'Сірі',
      thick_thin: 'Тонкі', thick_medium: 'Середні', thick_thick: 'Товсті',
      badge: 'еталон', badgeTitle: 'Колір узято з вашого референсу',
      copyHex: 'Скопіювати HEX', copyRgb: 'Скопіювати RGB',
      copied: 'Скопійовано: {0}', copyFail: 'Не вдалося скопіювати',
      ductAria: 'Повітровід системи {0}', pipeAria: 'Труба {0}',

      checkTitle: 'Перевірка розрізнюваності',
      checkText: 'Рахуємо різницю між кольорами за формулою CIEDE2000 (ΔE) і показуємо найгіршу пару для кожного діапазону. '
        + 'ΔE ≥ 20 — кольори кардинально різні, ≥ 15 — упевнено різні, ≥ 10 — різниця помітна, якщо кольори лежать поруч.',
      thSystems: 'Системи · діапазон', rowNeighbors: 'сусідні номери', rowWindow: 'будь-які 5 поспіль', rowAll: 'усі пари', thWorst: 'Найгірша пара, ΔE', thPair: 'Яка пара', thRating: 'Оцінка',
      pairAnd: ' і ',
      q20: 'відмінно', q15: 'добре', q10: 'помітно', q0: 'слабко',

      floorTitle: 'Перевірка на «поверсі»',
      floorHint: 'Системи прокладаються поруч, як у коридорі. Рухайте повзунок і дивіться, чи не зливаються сусідні.',
      floorCount: 'Систем кожного виду:',
      floorSupply: 'Припливні', floorExhaust: 'Витяжні', floorBoth: 'Разом',
      floorAria: 'Паралельні повітроводи',

      tbProject: 'Проєкт', tbProjectVal: 'Палітра систем вентиляції',
      tbSupply: 'Припливні', tbExhaust: 'Витяжні',
      tbNext: 'Наступний етап', tbNextVal: 'Припливно-витяжні (ПВ)',

      csvHead: ['Система', 'Група', 'Колір', 'R', 'G', 'B', 'HEX', 'Стінки R', 'Стінки G', 'Стінки B'],
      kindSupply: 'Припливна', kindExhaust: 'Витяжна', kindPipes: 'Трубопровід'
    }
  };

  var lang = 'uk';
  try {
    var saved = root.localStorage && root.localStorage.getItem('hvac-lang');
    if (saved && DICT[saved]) lang = saved;
  } catch (e) { /* localStorage может быть недоступен — остаёмся на языке по умолчанию */ }

  function t(key) {
    var v = DICT[lang][key];
    if (v === undefined) v = DICT.en[key];
    if (typeof v !== 'string') return v === undefined ? key : v;
    var args = Array.prototype.slice.call(arguments, 1);
    return v.replace(/\{(\d+)\}/g, function (_, i) { return args[+i]; });
  }

  // Перевести всё, что размечено в index.html.
  function applyStatic() {
    var doc = root.document;
    doc.documentElement.lang = lang;
    doc.title = t('docTitle');
    doc.querySelector('meta[name="description"]').setAttribute('content', t('docDescription'));
    doc.querySelectorAll('[data-i18n]').forEach(function (el) { el.textContent = t(el.dataset.i18n); });
    doc.querySelectorAll('[data-i18n-html]').forEach(function (el) { el.innerHTML = t(el.dataset.i18nHtml); });
    doc.querySelectorAll('[data-i18n-attr]').forEach(function (el) {
      el.dataset.i18nAttr.split(';').forEach(function (pair) {
        var p = pair.split(':');
        el.setAttribute(p[0], t(p[1]));
      });
    });
  }

  function setLang(next) {
    if (!DICT[next]) return;
    lang = next;
    try { root.localStorage.setItem('hvac-lang', next); } catch (e) { /* не страшно */ }
  }

  root.I18N = { t: t, applyStatic: applyStatic, setLang: setLang, getLang: function () { return lang; }, langs: Object.keys(DICT) };
})(window);
