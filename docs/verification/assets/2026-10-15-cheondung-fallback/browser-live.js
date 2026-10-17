// Opt-in actual TEST API browser check; requires Playwright outside the repository.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.ENTITY_QA_BASE || 'http://127.0.0.1:8001';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const width of [1280, 390, 320]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      const posts = [];
      page.on('pageerror', error => errors.push(String(error)));
      page.on('request', request => {
        if (request.method() === 'POST' && request.url().endsWith('/v1/chat')) posts.push(request.postDataJSON());
      });
      await page.goto(base + '/chat');
      const ask = async question => {
        await page.locator('#question-input').fill(question);
        const reply = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST', { timeout: 180000 });
        await page.locator('#question-input').press('Enter');
        const response = await reply;
        assert.equal(response.status(), 200);
        await page.locator('#question-input').waitFor({ state: 'visible' });
        await page.waitForFunction(() => !document.querySelector('#question-input').disabled);
        return response.json();
      };
      const exact = await ask('청둥 오리에 대해 알고 싶어');
      assert.equal(exact.entity_resolution.method, 'graph_normalized');
      assert.equal(exact.result.profile.taxon.scientific_name, 'Anas platyrhynchos');
      const typo = await ask('천둥오리는 뭘 먹어?');
      assert.equal(typo.disposition, 'clarify');
      const buttons = page.locator('.entity-candidate-button');
      assert.ok(await buttons.count() > 0 && await buttons.count() <= 3);
      const target = buttons.filter({ hasText: '청둥오리 (Anas platyrhynchos)' });
      assert.equal(await target.count(), 1);
      await target.scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, 'candidate viewport overflow');
      assert.ok((await target.boundingBox()).height >= 44, 'candidate touch target');
      await page.screenshot({ path: `${__dirname}/candidates-${width}.png`, fullPage: true });
      const countBefore = posts.length;
      // A stale manual filter must not redirect a confirmation to another taxon.
      await page.locator('#profile-name').evaluate(element => { element.value = '까치'; });
      await page.locator('#chat-intent').evaluate(element => { element.value = 'profile'; });
      assert.equal(posts.length, countBefore, 'rendering candidates must not auto-submit');
      const reply = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST', { timeout: 180000 });
      await target.focus();
      await target.press('Enter');
      const confirmed = await (await reply).json();
      await page.waitForFunction(() => !document.querySelector('#question-input').disabled);
      assert.equal(confirmed.disposition, 'answer');
      assert.equal(confirmed.result.profile.taxon.scientific_name, 'Anas platyrhynchos');
      assert.equal(confirmed.result.question_answer.topic, 'diet');
      assert.equal(posts.at(-1).filters.name, 'Anas platyrhynchos');
      assert.ok(posts.at(-1).question.includes('먹어'));
      assert.ok((await page.locator('#history').innerText()).includes('천둥오리는 뭘 먹어?'));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      assert.equal(overflow, false, 'horizontal viewport overflow');
      assert.deepEqual(errors, []);
      await page.screenshot({ path: `${__dirname}/browser-${width}.png`, fullPage: true });
      results.push({ width, passed: true, chat_posts: posts.length, keyboard_confirmation: true, stale_filter_ignored: true, topic: 'diet', page_errors: errors.length, horizontal_overflow: overflow });
      await page.close();
    }
    const result = { passed: true, mode: 'actual TEST API/Jina in Chromium, no route mocks; emulated viewports, not physical devices', results };
    fs.writeFileSync(`${__dirname}/browser-live.json`, JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
