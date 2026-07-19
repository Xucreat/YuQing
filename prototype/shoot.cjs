// Screenshot exporter for the 舆情 MVP prototype.
// Uses the system-installed Microsoft Edge / Chrome via Playwright channel
// (avoids downloading a separate Chromium binary).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const base = 'file://' + path.resolve(__dirname, 'index.html');
const outDir = path.resolve(__dirname, 'png');
fs.mkdirSync(outDir, { recursive: true });

const shots = [
  { name: '01-login',         hash: '#/login',      w: 1440, h: 900 },
  { name: '02-dashboard',     hash: '#/dashboard',  w: 1440, h: 900 },
  { name: '03-opinions',      hash: '#/opinions',   w: 1440, h: 900 },
  { name: '04-opinion-detail',hash: '#/opinion/1',  w: 1440, h: 900 },
  { name: '05-events',        hash: '#/events',     w: 1440, h: 900 },
  { name: '06-flow',          hash: '#/flow',       w: 1440, h: 900 },
];

async function launchBrowser() {
  const channels = ['msedge', 'chrome'];
  for (const ch of channels) {
    try {
      const b = await chromium.launch({ channel: ch, headless: true, args: ['--no-sandbox'] });
      console.log('launched via channel:', ch);
      return b;
    } catch (e) {
      console.log('channel', ch, 'unavailable:', e.message.split('\n')[0]);
    }
  }
  return chromium.launch({ headless: true, args: ['--no-sandbox'] });
}

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1440, height: 900 } });
  for (const s of shots) {
    await page.setViewportSize({ width: s.w, height: s.h });
    await page.goto(base + s.hash, { waitUntil: 'networkidle' });
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(outDir, s.name + '.png'), fullPage: true });
    console.log('saved', s.name + '.png');
  }
  await browser.close();
  console.log('DONE');
})().catch((e) => { console.error(e); process.exit(1); });
