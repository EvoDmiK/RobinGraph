const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});try {
const page=await browser.newPage();await page.goto('https://robingraph.dove-nest.com/chat');
const rows=await page.evaluate(async()=>{const rows=[];for(const path of ['/health','/openapi.json','/v1/taxa/lineage?name='+encodeURIComponent('청둥오리')]){const r=await fetch(path);rows.push({path,status:r.status,body:await r.json()});}return rows;});
assert.ok(rows.every(r=>r.status===200));fs.writeFileSync(__dirname+'/public-api.json',JSON.stringify({transport:'Chromium same-origin fetch',rows,passed:true,earlier_urllib_attempt:'HTTP 403 at public edge; no application response verified by that attempt'},null,2)+'\n');console.log('Public API GET in Chromium: 3/3 HTTP200');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
