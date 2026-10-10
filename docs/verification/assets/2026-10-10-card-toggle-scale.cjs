// Actual API profiles, real Chrome geometry; optional local JS/CSS interception.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
  const [base,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const checks=[],repro=process.env.RG_TOGGLE_REPRO==='1',local=process.env.RG_TOGGLE_LOCAL==='1';
  try {
    const api=await browser.newPage(),profiles={};
    for(const name of (repro?['Aix galericulata']:['Aix galericulata','Anas platyrhynchos','Pica serica'])){
      const cache=path.join(out,name.replace(/ /g,'-')+'.json');let p;
      if(fs.existsSync(cache))p=JSON.parse(fs.readFileSync(cache));
      else {const r=await api.request.get(base+'/v1/taxa/profile?name='+encodeURIComponent(name),{timeout:120000});assert.ok(r.ok());p=await r.json();fs.writeFileSync(cache,JSON.stringify(p));}
      profiles[name]=p.profile||p;assert.equal(profiles[name].taxon.scientific_name,name);
    }
    await api.close();
    for(const [width,height,mobile] of (process.env.RG_TOGGLE_SHORT_ONLY==='1'?[[390,640,true]]:repro?[[1280,900,false],[390,640,true]]:[[1280,900,false],[1280,700,false],[390,844,true],[390,640,true],[320,640,true],[844,390,true]]))for(const [name,profile]of Object.entries(profiles)){
      const context=await browser.newContext({viewport:{width,height},isMobile:mobile,hasTouch:mobile,reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      if(local||repro){await page.route('**/static/chat.js**',r=>r.fulfill({path:path.resolve(repro?'/tmp/rg-toggle-before.js':'src/robingraph/api/static/chat.js')}));await page.route('**/static/styles.css**',r=>r.fulfill({path:path.resolve('src/robingraph/api/static/styles.css')}));}
      await page.goto(base+'/chat',{waitUntil:'domcontentloaded',timeout:60000});await page.waitForFunction(()=>!!window.RobinGraphChat);
      await page.evaluate(p=>{const host=document.createElement('div');document.body.append(host);const c=RobinGraphChat.buildSpeciesCard(document,p);host.append(RobinGraphChat.buildSpeciesPopup(document,c,p));host.querySelector('button').click();},profile);
      const card=page.locator('dialog[open] .species-card');await card.press('Enter');await page.waitForTimeout(300);
      const geometry=()=>page.evaluate(()=>{const d=document.querySelector('dialog[open]'),f=d.querySelector('.species-card-fit-frame'),c=d.querySelector('.species-card'),r=d.getBoundingClientRect();return {scale:Number(f.dataset.fitScale),width:r.width,height:r.height,x:r.x,y:r.y,scrollTop:f.scrollTop,scrollHeight:f.scrollHeight,clientHeight:f.clientHeight,scrolling:f.dataset.fitScroll,titleFont:getComputedStyle(c.querySelector('.species-card-heading')).fontSize};});
      const baseline=await geometry(),toggles=card.locator('.card-details-scroll,.species-distribution-values'),records=[];
      assert.ok(await toggles.count()>=1);
      for(let i=0;i<await toggles.count();i++){
        const toggle=toggles.nth(i);const label=await toggle.locator('summary').innerText();
        // Native summary click also checks interaction and browser scroll anchoring.
        await toggle.locator('summary').click();await page.waitForTimeout(200);const expanded=await geometry();
        const enlarged=expanded.scale>baseline.scale+1e-6;
        if(!repro){assert.ok(Math.abs(expanded.scale-baseline.scale)<1e-6,'scale unchanged: '+label);assert.ok(Math.abs(expanded.width-baseline.width)<1,'width unchanged');assert.equal(expanded.scrolling,'true');assert.ok(expanded.x>=-1&&expanded.y>=-1&&expanded.x+expanded.width<=width+1&&expanded.y+expanded.height<=height+1);}
        if(i===0)await page.screenshot({path:path.join(out,name.replace(/ /g,'-')+'-'+width+'x'+height+'-expanded.png')});
        // Reach the actual end of expanded content (frame hides only scrollbar).
        await page.evaluate(()=>{const f=document.querySelector('dialog[open] .species-card-fit-frame');f.scrollTop=f.scrollHeight;});await page.waitForTimeout(100);const bottom=await geometry();
        if(!repro)assert.ok(Math.abs(bottom.scrollTop-(bottom.scrollHeight-bottom.clientHeight))<=2,'expanded content reachable');
        await toggle.evaluate(el=>{el.open=false;});await page.waitForTimeout(200);const collapsed=await geometry();
        if(!repro){assert.ok(Math.abs(collapsed.scale-baseline.scale)<1e-6);assert.equal(collapsed.scrollTop,0);assert.equal(collapsed.scrolling,'false');}
        records.push({label,expanded,bottom,collapsed,enlarged});
      }
      if(!repro&&await toggles.count()>1){
        await toggles.nth(0).evaluate(e=>{e.open=true;});await toggles.nth(1).evaluate(e=>{e.open=true;});await page.waitForTimeout(200);
        assert.ok(Math.abs((await geometry()).scale-baseline.scale)<1e-6);
        // Resize with two toggles still open, then return to the initial viewport.
        await page.setViewportSize({width,height:Math.max(320,height-80)});await page.waitForTimeout(250);
        const resized=await geometry();assert.ok(resized.scale<=baseline.scale+1e-6);
        await page.setViewportSize({width,height});await page.waitForTimeout(250);assert.ok(Math.abs((await geometry()).scale-baseline.scale)<1e-6);
        for(let i=0;i<await toggles.count();i++)await toggles.nth(i).evaluate(e=>{e.open=false;});await page.waitForTimeout(200);
      }
      assert.deepEqual(errors,[]);checks.push({name,width,height,mobile,baseline,toggles:records,pageErrors:errors});console.log(name,width,height,records.length);await context.close();
    }
    const result={passed:!repro||checks.every(c=>c.toggles.some(t=>t.enlarged)),mode:repro?'before-fix reproduction':local?'local JS/CSS with actual API profiles':'deployed JS/CSS with actual API profiles',base_url:base,cases:checks.length,checks};
    fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(result,null,2)+'\n');assert.ok(result.passed);
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
