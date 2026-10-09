// Actual TEST chat/UI verification. No request interception or mocked API responses.
// NODE_PATH must resolve Playwright; PLAYWRIGHT_CHROME may point to a local Chrome.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
if (!out) throw Error('Pass an output directory');
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
  });
  const checks = [];
  try {
    for (const width of [1280, 390]) {
      for (const bird of [
        { question: '큰부리까마귀에 대해 알고 싶어', name: 'Corvus macrorhynchos', key: 'crow', category: 'LC' },
        { question: 'Pyrrhura subandina에 대해 알고 싶어', name: 'Pyrrhura subandina', key: 'parakeet', category: 'CR' },
      ]) {
        const page = await browser.newPage({ viewport: { width, height: width === 390 ? 844 : 900 }, isMobile: width === 390, hasTouch: width === 390 });
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto('https://robingraph-test.dove-nest.com/chat', { waitUntil: 'domcontentloaded' });
        await page.locator('#question-input').fill(bird.question);
        const pending = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST', { timeout: 90000 });
        await page.locator('#send-button').click();
        const response = await pending;
        const answer = await response.json();
        const profile = answer.result?.profile;
        if (response.status() !== 200 || profile?.taxon.scientific_name !== bird.name) throw Error('Wrong actual chat taxon: ' + bird.name);
        if (profile.conservation.category !== null || profile.conservation.reference_assessment?.category !== bird.category) throw Error('Wrong assessment contract');
        const brief = page.locator('.message-answer .species-chat-brief');
        if (!(await brief.textContent()).includes('참고 평가:')) throw Error('Reference missing in brief');
        await page.locator('.message-answer .species-popup-trigger').click();
        await page.waitForTimeout(700);
        // External bird photos can arrive progressively; wait before screenshots.
        await page.waitForFunction(() => [...document.querySelectorAll('.species-popup img')].every(img => img.complete), null, { timeout: 15000 }).catch(() => {});
        const card = page.locator('.message-answer .species-card');
        if (await card.getAttribute('data-conservation-tier') !== 'unconfirmed') throw Error('Reference inherited risk colour');
        const reference = card.locator(':scope > .species-reference-assessment');
        const text = await reference.textContent();
        if (!text.includes('(' + bird.category + ')') || !text.includes('분류 범위')) throw Error('Reference qualifier missing');
        if ((await card.locator(':scope > .species-conservation-badge').textContent()).includes('NE')) throw Error('Raw NE leaked into main badge');
        const box = await card.boundingBox();
        const fits = box.x >= -1 && box.y >= -1 && box.x + box.width <= width + 1 && box.y + box.height <= (width === 390 ? 844 : 900) + 1;
        if (!fits) throw Error('Card outside viewport');
        await page.screenshot({ path: path.join(out, `${bird.key}-front-${width}.png`) });
        await card.focus(); await page.keyboard.press('Enter'); await page.waitForTimeout(650);
        if (await card.getAttribute('data-face') !== 'back') throw Error('Card flip failed');
        const before = await card.evaluate(el => [el.scrollTop, el.querySelector('.species-card-back').scrollTop]);
        await page.mouse.move(box.x + box.width / 2, box.y + box.height * .6);
        await page.mouse.wheel(0, 500); await page.waitForTimeout(150);
        const after = await card.evaluate(el => [el.scrollTop, el.querySelector('.species-card-back').scrollTop]);
        if (JSON.stringify(before) !== JSON.stringify(after)) throw Error('Unexpected card scroll');
        if (width === 390) {
          const cdp = await page.context().newCDPSession(page);
          const start = box.x + box.width * .75, end = box.x + box.width * .2, y = box.y + box.height * .6;
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: start, y }] });
          for (let i = 1; i <= 12; i++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: start + (end - start) * i / 12, y }] });
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
          await cdp.detach();
        } else {
          await page.mouse.move(box.x + box.width * .75, box.y + box.height * .6); await page.mouse.down();
          await page.mouse.move(box.x + box.width * .2, box.y + box.height * .6, { steps: 16 }); await page.mouse.up();
        }
        await page.waitForTimeout(650);
        if (await card.getAttribute('data-face') !== 'front') throw Error('Drag or touch flip failed');
        await page.locator('.message-answer .species-popup-close').click();
        const sources = page.locator('.message-answer .species-answer-sources').first();
        await sources.locator(':scope > summary').click();
        if (!(await sources.textContent()).includes(profile.conservation.reference_assessment.assessment_citation)) throw Error('Reference citation missing');
        if (errors.length) throw Error(errors.join('\n'));
        checks.push({ width, question: bird.question, name: bird.name, actual_api: true, primary_category: null, reference_category: bird.category, neutral_colour: true, fits, scroll_delta: 0, gesture: width === 390 ? 'CDP touch swipe' : 'mouse drag', source_citation: true, page_errors: errors });
        await page.close();
      }
    }
    fs.writeFileSync(path.join(out, 'browser.json'), JSON.stringify({ response_mocking: false, checks }, null, 2) + '\n');
    console.log(JSON.stringify(checks));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
