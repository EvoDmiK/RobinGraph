const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const checks=[];
 try {
 for(const width of [1280,390]){
 for(const bird of ["까치", "큰부리까마귀"]){
 const page=await browser.newPage({viewport:{width,height:width===390?844:900},isMobile:width===390,hasTouch:width===390});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('https://robingraph-test.dove-nest.com/chat',{waitUntil:'domcontentloaded'});
 await page.locator('#question-input').fill(bird+'에 대해 알고 싶어');
 const pending=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:90000});
 await page.locator('#send-button').click();const response=await pending;const answer=await response.json();
 if(answer.result?.profile?.taxon.scientific_name!==(bird==='까치'?'Pica serica':'Corvus macrorhynchos'))throw Error('Wrong species');
 await page.locator('.message-answer .species-popup-trigger').click();
 const card=page.locator('.message-answer .species-card');await card.focus();await page.keyboard.press('Enter');await page.waitForTimeout(700);
 const badge=await card.locator(':scope > .species-conservation-badge').textContent();
 if(bird==='큰부리까마귀'&&badge!=='관심대상 (LC) · 2024 평가 · 참고')throw Error('Wrong badge: '+badge);
 const boxes=await card.locator('.species-distribution-empty').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect(),p=el.parentElement.getBoundingClientRect(),s=getComputedStyle(el);return {text:el.innerText,center_delta:(r.x+r.width/2)-(p.x+p.width/2),text_align:s.textAlign,align_items:s.alignItems,justify_content:s.justifyContent};}));
 if(bird==='까치'&&(boxes.length!==2||boxes.some(b=>Math.abs(b.center_delta)>1||b.text_align!=='center')))throw Error(JSON.stringify(boxes));
 if(bird==='까치'&&(!boxes[1].text.includes('생활 방식 · 땅에서 먹이 탐색')||!boxes[1].text.endsWith('비율 자료 없음')||boxes[1].text.includes('뜻하지')))throw Error('Unexpected description');
 if(errors.length)throw Error(errors.join('\n'));
 await page.screenshot({path:`/tmp/rg-qualitative-${bird}-${width}.png`});checks.push({width,bird,badge,actual_api:true,response_status:response.status(),boxes,page_errors:errors});await page.close();
 }}
 fs.writeFileSync('/tmp/rg-qualitative-browser.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
