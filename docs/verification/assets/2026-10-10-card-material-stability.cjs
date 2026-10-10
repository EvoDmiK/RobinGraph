// Real Mandarin Duck profile; cloned conservation grades test every palette,
// not actual assessments. Compare only masked background pixels, not text.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),zlib=require('zlib'),assert=require('node:assert/strict');
function pngPixels(file){const b=fs.readFileSync(file),parts=[],w=b.readUInt32BE(16),h=b.readUInt32BE(20),channels=b[25]===2?3:4;for(let p=8;p<b.length;){let n=b.readUInt32BE(p);if(b.toString('ascii',p+4,p+8)==='IDAT')parts.push(b.subarray(p+8,p+8+n));p+=12+n;}const raw=zlib.inflateSync(Buffer.concat(parts)),row=w*channels,out=Buffer.alloc(h*row);let p=0;const paeth=(a,b,c)=>{let v=a+b-c,x=Math.abs(v-a),y=Math.abs(v-b),z=Math.abs(v-c);return x<=y&&x<=z?a:y<=z?b:c;};for(let y=0;y<h;y++){let f=raw[p++];for(let x=0;x<row;x++){let a=x>=channels?out[y*row+x-channels]:0,u=y?out[(y-1)*row+x]:0,c=y&&x>=channels?out[(y-1)*row+x-channels]:0;out[y*row+x]=(raw[p++]+(f===0?0:f===1?a:f===2?u:f===3?Math.floor((a+u)/2):paeth(a,u,c)))&255;}}return out;}
(async()=>{
 const [base,out]=process.argv.slice(2),local=process.env.RG_GLOSS_LOCAL==='1',repro=process.env.RG_GLOSS_REPRO==='1';fs.mkdirSync(out,{recursive:true});
 const b=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true}),api=await b.newPage();
 const response=await api.request.get(base+'/v1/taxa/profile?name=Aix%20galericulata',{timeout:120000});assert.ok(response.ok());const raw=await response.json(),profile=raw.profile||raw;assert.equal(profile.taxon.scientific_name,'Aix galericulata');await api.close();
 const checks=[];
 try{
 for(const [width,height,mobile]of [[1280,900,false],[390,640,true]])for(const grade of (repro?['LC']:['LC','NT','VU','EN','CR','EW','EX','DD','unknown'])){
  const ctx=await b.newContext({viewport:{width,height},isMobile:mobile,hasTouch:mobile,reducedMotion:'no-preference'}),page=await ctx.newPage();
  if(local){for(const name of ['chat.js','styles.css'])await page.route('**/static/'+name+'**',r=>r.fulfill({path:path.resolve('src/robingraph/api/static/'+name)}));}
  await page.goto(base+'/chat',{waitUntil:'domcontentloaded',timeout:60000});await page.waitForFunction(()=>!!window.RobinGraphChat);
  const p=structuredClone(profile);if(grade!=='LC')p.conservation={...profile.conservation,category:grade==='unknown'?null:grade,category_raw:grade==='unknown'?null:grade,taxonomy_category_raw:grade==='unknown'?null:grade};
  await page.evaluate(p=>{const h=document.createElement('div');document.body.append(h);const c=RobinGraphChat.buildSpeciesCard(document,p);h.append(RobinGraphChat.buildSpeciesPopup(document,c,p));h.querySelector('button').click();},p);
  const card=page.locator('dialog[open] .species-card');await card.press('Enter');await page.waitForTimeout(1000);
  const tier=await card.getAttribute('data-conservation-tier');assert.equal(tier,['DD','unknown'].includes(grade)?'unconfirmed':grade.toLowerCase());
  const sample=async label=>{
   const state=await card.evaluate(c=>{const g=c.querySelector('.species-card-gloss'),s=getComputedStyle(c),r=c.getBoundingClientRect(),f=c.closest('.species-card-fit-frame');return{materialHeight:c.style.getPropertyValue('--species-card-material-height'),backgroundSize:s.backgroundSize,height:r.height,width:r.width,scale:f.dataset.fitScale,scrollTop:f.scrollTop,glossOpacity:getComputedStyle(g).opacity,glossAnimations:g.getAnimations().length};});
   const r=await card.boundingBox(),file=path.join(out,grade+'-'+width+'-'+label+'.png');await page.screenshot({path:file,clip:{x:r.x+12,y:r.y+50,width:r.width-24,height:120},style:'.species-card > * {visibility:hidden!important}'});return {state,file};
  };
  const closed=await sample('closed');await card.locator('.card-details-scroll').first().evaluate(e=>{e.open=true;});await page.waitForTimeout(250);const opened=await sample('opened');
  const a=pngPixels(closed.file),openedPixels=pngPixels(opened.file);assert.equal(a.length,openedPixels.length);let maxDelta=0,totalDelta=0;for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-openedPixels[i]);maxDelta=Math.max(maxDelta,d);totalDelta+=d;}const meanDelta=totalDelta/a.length,pixelsEqual=a.equals(openedPixels),materialStable=maxDelta<=1&&meanDelta<0.01;
  assert.equal(closed.state.glossOpacity,'0');assert.equal(opened.state.glossOpacity,'0');assert.equal(opened.state.glossAnimations,0);
  if(repro)assert.equal(pixelsEqual,false,'reproduce static material movement');
  else{assert.equal(opened.state.materialHeight,closed.state.materialHeight);assert.equal(opened.state.backgroundSize,closed.state.backgroundSize);assert.equal(opened.state.scale,closed.state.scale);assert.ok(materialStable,'stable material raster: '+grade+' '+width);}
  await card.locator('.card-details-scroll').first().evaluate(e=>{e.open=false;});await page.waitForTimeout(250);
  let dragGloss=null;
  if(!repro&&grade==='LC'&&!mobile){const r=await card.boundingBox();await page.mouse.move(r.x+r.width*.4,r.y+100);await page.mouse.down();await page.mouse.move(r.x+r.width*.4+40,r.y+100,{steps:5});dragGloss=await card.locator('.species-card-gloss').evaluate(g=>getComputedStyle(g).opacity);assert.ok(Number(dragGloss)>0,'flip sheen retained');await page.mouse.up();await page.waitForTimeout(350);assert.equal(await card.locator('.species-card-gloss').evaluate(g=>getComputedStyle(g).opacity),'0');}
  checks.push({grade,tier,width,height,mobile,closed:closed.state,opened:opened.state,pixelsEqual,materialStable,maxDelta,meanDelta,dragGloss});console.log(grade,width,materialStable,maxDelta,meanDelta);await ctx.close();
 }
 const report={passed:true,base_url:base,mode:repro?'before-fix reproduction':local?'local CSS/JS with actual API profile':'deployed CSS/JS with actual API profile',method:'9 palette fixtures derived from Mandarin Duck; static material crop masks text, decoded PNG pixels compared; tolerance max 1/255 channel and mean less than 0.01/255; normal motion enabled',cases:checks.length,checks};fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exit(1)});
