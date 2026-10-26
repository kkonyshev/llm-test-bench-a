const puppeteer = require('puppeteer-core');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const file = process.argv[2], shot = process.argv[3];
  const b = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', userDataDir: process.argv[4], args: ['--no-first-run', '--no-default-browser-check', '--use-angle=metal', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage(); await p.setViewport({ width: 1280, height: 720 });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errs.push('console.' + m.type() + ': ' + m.text().slice(0, 200)); });
  p.on('requestfailed', r => errs.push('REQFAIL: ' + r.url() + ' ' + (r.failure() && r.failure().errorText)));
  await p.goto('file://' + file, { waitUntil: 'load', timeout: 60000 }).catch(e => errs.push('GOTO: ' + e.message));
  await sleep(3000);
  await p.screenshot({ path: shot.replace('.png', '-title.png') });
  const btns = await p.evaluate(() => [...document.querySelectorAll('button')].filter(b => b.offsetParent).map(b => b.id + ':' + b.textContent.trim().slice(0, 20)));
  console.log('buttons:', JSON.stringify(btns));
  const sig = () => p.evaluate(() => { const c = document.querySelector('canvas'); return (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 160); });
  const t0 = await sig(); console.log('title text:', t0);
  const start = await p.evaluateHandle(() => [...document.querySelectorAll('button')].find(b => b.offsetParent && /start|play|run|go/i.test(b.textContent)));
  if (start.asElement()) { await start.asElement().click().catch(() => {}); console.log('clicked start button'); }
  else { await p.mouse.click(640, 400); await p.keyboard.press('Enter'); await p.keyboard.press('Space'); console.log('pressed click/Enter/Space'); }
  await sleep(2500); const t1 = await sig();
  await p.keyboard.press('ArrowLeft'); await sleep(400); await p.keyboard.press('ArrowUp'); await sleep(2500);
  const t2 = await sig();
  console.log('after 2.5s:', t1); console.log('after 5.5s:', t2);
  await p.screenshot({ path: shot });
  console.log(errs.slice(0, 8).join('\n') || 'no errors');
  await b.close();
})();
