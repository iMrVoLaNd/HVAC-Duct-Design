/*
 * Переводы интерфейса: русский (ru) и украинский (uk).
 *
 * В index.html тексты помечены атрибутами:
 *   data-i18n="ключ"            — подставить текст
 *   data-i18n-html="ключ"       — подставить HTML (там, где внутри есть разметка)
 *   data-i18n-attr="title:ключ;aria-label:ключ" — перевести атрибуты
 * В js/app.js — I18N.t('ключ', аргумент1, ...), где в тексте {0}, {1} — места для аргументов.
 *
 * Чтобы добавить язык — скопируйте блок ru и переведите значения.
 */
(function (root) {
  'use strict';

  var CHIP_S = '<span class="chip chip--wall chip--supply" id="chip-supply"></span>';
  var CHIP_E = '<span class="chip chip--wall chip--exhaust" id="chip-exhaust"></span>';

  var DICT = {
    ru: {
      docTitle: 'Палитра систем вентиляции',
      docDescription: 'Цветовое кодирование приточных и вытяжных систем в BIM/CAD: по 12 цветов на группу в стиле сигнальной палитры.',

      ribbonShow: 'Показать', showAll: 'Все', showSupply: 'Приточные', showExhaust: 'Вытяжные',
      ribbonView: 'Вид', viewIso: 'Объём', viewPlan: 'План Revit',
      ribbonWalls: 'Стенки', wallsIso: 'В объёме',
      wallsIsoTitle: 'Подсветить длинные рёбра воздуховода цветом стенок в виде «Объём»',
      ribbonExport: 'Экспорт', ribbonLang: 'Язык',
      ariaShow: 'Показать системы', ariaView: 'Вид воздуховода', ariaWalls: 'Цвет боковых стенок',
      ariaExport: 'Экспорт', ariaLang: 'Язык интерфейса',

      sheetTitle: 'Цветовая палитра систем вентиляции',
      sheetSubtitle: 'Рекомендуемое кодирование воздуховодов (BIM / CAD)',
      noteRead: '<b>Как читать.</b> В виде «План Revit» боковые стенки воздуховода окрашены в цвет группы (' + CHIP_S
        + ' у приточных, ' + CHIP_E + ' у вытяжных), внутри — заливка цветом системы. Оттенок стенок переключается в ленте («Стенки»), '
        + 'а в виде «Объём» стенки включаются кнопкой «В объёме». Нажмите на HEX или RGB, чтобы скопировать значение для фильтра вида.',
      noteSource: '<b>Откуда цвета.</b> Цвета с пометкой «эталон» взяты точно из ваших референсов: приточные — земляная палитра из легенд '
        + '(терракот, травяной, горчичный, охра, кирпичный), вытяжные В1–В3 — со скриншота. Остальные подобраны вручную в том же характере. '
        + 'Двенадцати цветов на группу хватает на один этаж.',
      ariaCheck: 'Проверка различимости',

      titleSupply: 'Приточные системы (П)', titleExhaust: 'Вытяжные системы (В)',
      wallsRgb: ' · стенки RGB {0}',
      chipSupply: 'приточные {0}', chipExhaust: 'вытяжные {0}',
      wallTitle: 'Приточные {0}, вытяжные {1}',
      wall_standard: 'Чистые', wall_soft: 'Спокойные', wall_dark: 'Тёмные', wall_darker: 'Самые тёмные',
      badge: 'эталон', badgeTitle: 'Цвет взят из вашего референса',
      copyHex: 'Скопировать HEX', copyRgb: 'Скопировать RGB',
      copied: 'Скопировано: {0}', copyFail: 'Не удалось скопировать',
      ductAria: 'Воздуховод системы {0}',

      checkTitle: 'Проверка различимости',
      checkText: 'Считаем разницу между цветами по формуле CIEDE2000 (ΔE) и показываем худшую пару в группе. '
        + 'ΔE ≥ 20 — цвета кардинально разные, ≥ 15 — уверенно разные, ≥ 10 — разница заметна, если цвета лежат рядом.',
      thSystems: 'Системы', thWorst: 'Худшая пара, ΔE', thPair: 'Какая пара', thRating: 'Оценка',
      pairAnd: ' и ',
      q20: 'отлично', q15: 'хорошо', q10: 'заметно', q0: 'слабо',

      floorTitle: 'Проверка на «этаже»',
      floorHint: 'Системы прокладываются рядом, как в коридоре. Двигайте ползунок и смотрите, не сливаются ли соседние.',
      floorCount: 'Систем каждого вида:',
      floorSupply: 'Приточные', floorExhaust: 'Вытяжные', floorBoth: 'Вместе',
      floorAria: 'Параллельные воздуховоды',

      tbProject: 'Проект', tbProjectVal: 'Палитра систем вентиляции',
      tbSupply: 'Приточные', tbExhaust: 'Вытяжные',
      tbNext: 'Следующий этап', tbNextVal: 'Приточно-вытяжные (ПВ)',

      csvHead: ['Система', 'Группа', 'Цвет', 'R', 'G', 'B', 'HEX', 'Стенки R', 'Стенки G', 'Стенки B'],
      kindSupply: 'Приточная', kindExhaust: 'Вытяжная'
    },

    uk: {
      docTitle: 'Палітра систем вентиляції',
      docDescription: 'Колірне кодування припливних і витяжних систем у BIM/CAD: по 12 кольорів на групу в стилі сигнальної палітри.',

      ribbonShow: 'Показати', showAll: 'Усі', showSupply: 'Припливні', showExhaust: 'Витяжні',
      ribbonView: 'Вигляд', viewIso: 'Об’єм', viewPlan: 'План Revit',
      ribbonWalls: 'Стінки', wallsIso: 'В об’ємі',
      wallsIsoTitle: 'Підсвітити довгі ребра повітровода кольором стінок у вигляді «Об’єм»',
      ribbonExport: 'Експорт', ribbonLang: 'Мова',
      ariaShow: 'Показати системи', ariaView: 'Вигляд повітровода', ariaWalls: 'Колір бічних стінок',
      ariaExport: 'Експорт', ariaLang: 'Мова інтерфейсу',

      sheetTitle: 'Колірна палітра систем вентиляції',
      sheetSubtitle: 'Рекомендоване кодування повітроводів (BIM / CAD)',
      noteRead: '<b>Як читати.</b> У вигляді «План Revit» бічні стінки повітровода пофарбовані в колір групи (' + CHIP_S
        + ' у припливних, ' + CHIP_E + ' у витяжних), усередині — заливка кольором системи. Відтінок стінок перемикається в стрічці («Стінки»), '
        + 'а у вигляді «Об’єм» стінки вмикаються кнопкою «В об’ємі». Натисніть на HEX або RGB, щоб скопіювати значення для фільтра виду.',
      noteSource: '<b>Звідки кольори.</b> Кольори з позначкою «еталон» взяті точно з ваших референсів: припливні — земляна палітра з легенд '
        + '(теракот, трав’яний, гірчичний, охра, цегляний), витяжні В1–В3 — зі скриншота. Решта підібрана вручну в тому самому характері. '
        + 'Дванадцяти кольорів на групу вистачає на один поверх.',
      ariaCheck: 'Перевірка розрізнюваності',

      titleSupply: 'Припливні системи (П)', titleExhaust: 'Витяжні системи (В)',
      wallsRgb: ' · стінки RGB {0}',
      chipSupply: 'припливні {0}', chipExhaust: 'витяжні {0}',
      wallTitle: 'Припливні {0}, витяжні {1}',
      wall_standard: 'Чисті', wall_soft: 'Спокійні', wall_dark: 'Темні', wall_darker: 'Найтемніші',
      badge: 'еталон', badgeTitle: 'Колір узято з вашого референсу',
      copyHex: 'Скопіювати HEX', copyRgb: 'Скопіювати RGB',
      copied: 'Скопійовано: {0}', copyFail: 'Не вдалося скопіювати',
      ductAria: 'Повітровід системи {0}',

      checkTitle: 'Перевірка розрізнюваності',
      checkText: 'Рахуємо різницю між кольорами за формулою CIEDE2000 (ΔE) і показуємо найгіршу пару в групі. '
        + 'ΔE ≥ 20 — кольори кардинально різні, ≥ 15 — упевнено різні, ≥ 10 — різниця помітна, якщо кольори лежать поруч.',
      thSystems: 'Системи', thWorst: 'Найгірша пара, ΔE', thPair: 'Яка пара', thRating: 'Оцінка',
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
      kindSupply: 'Припливна', kindExhaust: 'Витяжна'
    }
  };

  var lang = 'uk';
  try {
    var saved = root.localStorage && root.localStorage.getItem('hvac-lang');
    if (saved && DICT[saved]) lang = saved;
  } catch (e) { /* localStorage может быть недоступен — остаёмся на языке по умолчанию */ }

  function t(key) {
    var v = DICT[lang][key];
    if (v === undefined) v = DICT.ru[key];
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
