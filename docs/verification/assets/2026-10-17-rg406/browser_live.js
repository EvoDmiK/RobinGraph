// Actual TEST HTTP/DB browser verification; external Playwright install required.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.RG406_QA_BASE || 'http://127.0.0.1:8001';
const out=process.env.RG406_OUTPUT_DIR || __dirname; fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});const rows=[];
 try {
  for(const width of [1280,390,320]) {
   const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];const posts=[];
   page.on('pageerror',e=>errors.push(String(e)));
   page.on('request',r=>{if(r.method()==='POST' && r.url().endsWith('/v1/chat'))posts.push(r.postDataJSON());});
   await page.goto(base+'/chat');
   await page.locator('#question-input').fill('작성 중 질문');
   await page.locator('#species-scope-outside').focus();await page.locator('#species-scope-outside').press('Space');
   assert.equal(await page.locator('#question-input').inputValue(),'작성 중 질문');assert.equal(posts.length,0);
   const ask=async(q,scope)=>{
    await page.locator('#species-scope-'+scope).check();
    await page.locator('#question-input').fill(q);
    const result=page.waitForResponse(r=>r.url().endsWith('/v1/chat') && r.request().method()==='POST',{timeout:180000});
    await page.locator('#question-input').press('Enter');const response=await result;
    assert.equal(response.status(),200);await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
    return response.json();
   };
   const korean=await ask('청둥오리에 대해 알려줘','korea');
   assert.equal(korean.disposition,'answer');assert.equal(korean.result.profile.taxon.distribution.status,'korea');
   await page.locator('#question-input').fill('작성 중 질문 유지');
   await page.locator('#species-scope-outside').check();
   assert.equal(await page.locator('#question-input').inputValue(),'작성 중 질문 유지');
   assert.equal(await page.locator('#history .message').count(),0,'old scope history must be cleared');
   const foreign=await ask('Nestor notabilis에 대해 알려줘','outside');
   assert.equal(foreign.disposition,'answer');assert.equal(foreign.result.profile.taxon.display_name,'Kea');
   assert.equal(foreign.result.profile.taxon.korean_name,'높은산앵무');
   assert.ok((await page.locator('.species-title').allTextContents()).includes('Kea'),'popup title must use English');
   assert.ok((await page.locator('#history').innerText()).includes('Kea'));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page overflow');
   await page.screenshot({path:out+`/foreign-${width}.png`,fullPage:true});
   const unknown=await ask('타조에 대해 알려줘','unknown');
   assert.equal(unknown.disposition,'answer');assert.equal(unknown.result.profile.taxon.distribution.status,'unknown');
   assert.deepEqual(posts.map(p=>p.species_scope),['korea','outside','unknown']);
   assert.deepEqual(errors,[]);rows.push({width,passed:true,requests:posts.length,pageerrors:errors});
   console.log(JSON.stringify(rows.at(-1)));await page.close();
  }
  const page=await browser.newPage();await page.goto(base+'/birds');
  await page.locator('#bird-scope').selectOption('outside');
  await page.locator('#bird-name').fill('Nestor notabilis');
  const reply=page.waitForResponse(r=>r.url().includes('/v1/taxa/profile') && r.url().includes('species_scope=outside'),{timeout:180000});
  await page.locator('#bird-submit').click();assert.equal((await reply).status(),200);
  await page.waitForFunction(()=>document.querySelector('#bird-card') && !document.querySelector('#bird-card').hidden);
  assert.equal(await page.locator('#bird-card h2').first().innerText(),'Kea');
  rows.push({page:'birds',passed:true,species_scope:'outside'});await page.close();
  fs.writeFileSync(out+'/browser-live.json',JSON.stringify({passed:true,base,scope:'Actual TEST HTTP and DB; Chromium viewport emulation, no route mocks',rows},null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
