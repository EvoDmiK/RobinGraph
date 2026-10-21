const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('fs');const assert=require('assert/strict');
const out=process.env.SCOPE_OUT;const expect=process.env.SCOPE_EXPECT==='1';
(async()=>{const b=await chromium.launch({headless:true});let rows=[];
try {for(const width of [1440,1024,768,480,390,320]){
const p=await b.newPage({viewport:{width,height:1100}});const errors=[];let chatPosts=0;
p.on('pageerror',e=>errors.push(String(e)));await p.route('**/*',r=>r.request().method()==='POST'?(chatPosts+=r.request().url().endsWith('/v1/chat')?1:0,r.abort()):r.continue());
await p.goto('https://robingraph-test.dove-nest.com/chat');await p.locator('#advanced-settings summary').click();
const boxes=await p.locator('.species-scope-option').evaluateAll(ns=>ns.map(n=>{let r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}));
if(expect){assert.equal(boxes[0].width,boxes[3].width);assert.equal(boxes[0].height,boxes[3].height);if(width>600){assert.equal(boxes[0].y,boxes[1].y);assert.equal(boxes[2].y,boxes[3].y)}else{assert.ok(boxes[1].y>boxes[0].y);}}
await p.locator('#question-input').fill('작성 중 질문');await p.locator('#species-scope-outside').focus();await p.keyboard.press('Space');assert.equal(await p.locator('#species-scope-outside').isChecked(),true);assert.equal(await p.locator('#question-input').inputValue(),'작성 중 질문');assert.equal(chatPosts,0);assert.deepEqual(errors,[]);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await p.locator('#species-scope-all').check();await p.locator('#question-input').focus();
await p.screenshot({path:out+`/scope-${width}.png`,fullPage:true});rows.push({width,boxes,passed:true,chatPosts});await p.close();}
fs.writeFileSync(out+'/layout.json',JSON.stringify({base:'https://robingraph-test.dove-nest.com',expectAligned:expect,rows},null,2)+'\n');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
