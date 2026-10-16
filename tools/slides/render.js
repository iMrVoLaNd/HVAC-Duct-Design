// node render.js <имя_файла_без_расширения>   — запускать в папке, где лежит print.html (см. build_print.py)
// Нужен playwright (глобально: NODE_PATH=$(npm root -g)) и Chromium; путь к нему можно задать в CHROMIUM_PATH.
const { chromium } = require('playwright');
(async () => {
  const out = process.argv[2];
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + process.cwd() + '/print.html', { waitUntil: 'networkidle', timeout: 60000 }).catch(e => console.log('goto', e.message));
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(1000);
  console.log(await p.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight).join(', ')) || 'NO WEB FONTS');
  await p.pdf({ path: out + '.pdf', width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
  const secs = await p.$$('section');
  for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: out + '-' + String(i + 1).padStart(2, '0') + '.png' });
  await b.close();
})();
