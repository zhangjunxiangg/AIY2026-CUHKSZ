const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  const filePath = 'file:///J:/Hackthon-Art/MRobots-OS-AIY-hackthon/0802-meeting-ppt/index.html';
  await page.goto(filePath, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  for (let i = 0; i < 18; i++) {
    if (i > 0) {
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(1200);
    }
    await page.screenshot({ path: `J:/Hackthon-Art/MRobots-OS-AIY-hackthon/0802-meeting-ppt/screenshot-${String(i + 1).padStart(2, '0')}.png` });
  }

  await browser.close();
  console.log('Done');
})();
