// Real TEST profile payloads and browser layout; optional local CSS interception.
// This exercises card rendering directly, not intent routing or language generation.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
  const [base,out]=process.argv.slice(2);if(!base||!out)throw Error('usage: node script <base URL> <output directory>');
  fs.mkdirSync(out,{recursive:true});const local=process.env.RG_LAYOUT_LOCAL==='1';
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const profiles={},checks=[];
  try {
    const api=await browser.newPage();
    for(const name of ['Anas platyrhynchos','Raphus cucullatus','Pica serica']) {
      let raw;
      if(process.env.RG_LAYOUT_PROFILE_CACHE) {
        raw=JSON.parse(fs.readFileSync(path.join(process.env.RG_LAYOUT_PROFILE_CACHE,'rg-layout-'+name.replace(/ /g,'-')+'.json'),'utf8'));
      } else {
        const response=await api.request.get(base+'/v1/taxa/profile?name='+encodeURIComponent(name),{timeout:120000});assert.ok(response.ok());raw=await response.json();
      }
      const profile=raw.profile||raw;assert.equal(profile.taxon.scientific_name,name);profiles[name]=profile;console.log('PROFILE',name);
    }
    await api.close();
    const scenarios=[];
    for(const [width,height] of [[1280,900],[1280,700],[390,844],[320,640]])for(const name of Object.keys(profiles))scenarios.push({name,width,height,variant:'live'});
    for(const [width,height] of [[1280,900],[390,844]])for(const variant of ['missing','long'])scenarios.push({name:'Anas platyrhynchos',width,height,variant});
    for(const {name,width,height,variant} of scenarios) {
      console.log('CASE',name,width,height,variant);
      const context=await browser.newContext({viewport:{width,height},isMobile:width<600,hasTouch:width<600,reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      if(local)await page.route('**/static/styles.css**',route=>route.fulfill({path:path.resolve('src/robingraph/api/static/styles.css')}));
      await page.goto(base+'/chat');const profile=structuredClone(profiles[name]);
      if(variant==='missing'){profile.images=[];profile.traits=[];profile.sections=[];profile.photo_availability={status:'not_found'};}
      if(variant==='long'){for(const s of profile.sections||[])if(s.key==='appearance')for(const item of s.items||[])if(item.text)item.text+=' '+item.text;}
      await page.evaluate(profile=>{const host=document.createElement('div');host.className='message-answer';document.body.appendChild(host);const card=RobinGraphChat.buildSpeciesCard(document,profile);host.appendChild(RobinGraphChat.buildSpeciesPopup(document,card,profile));host.querySelector('.species-popup-trigger').click();},profile);
      const dialog=page.locator('dialog[open]'),card=dialog.locator('.species-card'),frame=dialog.locator('.species-card-fit-frame');
      await page.waitForTimeout(200);
      const geometry=()=>page.evaluate(()=>{
        const d=document.querySelector('dialog[open]'),c=d.querySelector('.species-card'),f=d.querySelector('.species-card-fit-frame');
        const rect=e=>{if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height};};
        return{dialog:rect(d),card:rect(c),frame:rect(f),scale:Number(f.dataset.fitScale),scrollTop:f.scrollTop,overflowY:getComputedStyle(f).overflowY,
          photo:rect(c.querySelector('.species-media figure:not([hidden])')),placeholder:rect(c.querySelector('.species-photo-placeholder')),boxes:[...c.querySelectorAll('.species-distribution-column')].map(column=>({column:rect(column),box:rect(column.querySelector('.species-distribution-empty')),title:rect(column.querySelector('h4')),text:column.innerText}))};
      });
      const fit=g=>{assert.equal(g.overflowY,'clip');assert.equal(g.scrollTop,0);assert.ok(g.card.y>=g.frame.y-1);assert.ok(g.card.y+g.card.height<=g.frame.y+g.frame.height+1);assert.ok(g.dialog.x>=-1&&g.dialog.y>=-1);assert.ok(g.dialog.x+g.dialog.width<=width+1&&g.dialog.y+g.dialog.height<=height+1);};
      const front=await geometry();fit(front);
      if(width>=600&&front.photo)assert.ok(Math.abs(front.photo.width/front.photo.height-7/6)<.01,'common desktop photo ratio');
      let decodedImages=0;for(const image of await card.locator('.species-media img').all())try{await image.evaluate(el=>Promise.race([el.decode(),new Promise((_,reject)=>setTimeout(()=>reject(Error('image timeout')),5000))]));decodedImages++;}catch{}
      let photoSwitch=false;
      if(variant==='live'&&name==='Anas platyrhynchos') {
        const before=await card.locator('.species-media figure:not([hidden]) img').getAttribute('src');await card.getByRole('button',{name:'다음 사진',exact:true}).click();
        const after=await card.locator('.species-media figure:not([hidden]) img').getAttribute('src');assert.notEqual(before,after);assert.equal(await card.locator('.species-photo-controls span').innerText(),'사진 2 / 2');photoSwitch=true;
        const second=await geometry();assert.ok(Math.abs(second.photo.height-front.photo.height)<1);await card.getByRole('button',{name:'이전 사진',exact:true}).click();
      }
      const stem=name.replace(/ /g,'-')+'-'+width+'x'+height+'-'+variant;
      await page.screenshot({path:path.join(out,stem+'-front.png')});
      await card.press('Enter');await page.waitForTimeout(200);assert.equal(await card.locator('.species-card-back').isVisible(),true);
      const back=await geometry();fit(back);assert.ok(Math.abs(back.card.height-front.card.height)<1);
      for(const {column,box,title} of back.boxes)if(box){assert.ok(Math.abs(box.x+box.width/2-column.x-column.width/2)<1,'box centered in column');assert.ok(Math.abs(box.x+box.width/2-title.x-title.width/2)<1,'box centered below title');}
      const b=await card.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height*.65);await page.mouse.wheel(0,300);await page.waitForTimeout(100);fit(await geometry());
      await page.screenshot({path:path.join(out,stem+'-back.png')});
      let touchSwipe=false;
      if(width<600) {
        const session=await context.newCDPSession(page),y=b.y+b.height*.55,x=b.x+b.width*.2;
        await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,id:1}]});
        for(let i=1;i<=10;i++)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+b.width*.6*i/10,y,id:1}]});
        await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
        await page.waitForFunction(()=>!document.querySelector('dialog[open] .species-card-front').hidden);touchSwipe=true;fit(await geometry());
      }
      assert.deepEqual(errors,[]);checks.push({name,width,height,variant,front,back,photoSwitch,touchSwipe,decodedImages,pageErrors:errors});await context.close();
    }
    const report={passed:true,mode:local?'TEST API profiles with local CSS interception':'TEST API profiles and deployed CSS/JS',profiles:process.env.RG_LAYOUT_PROFILE_CACHE?'previously fetched TEST API payloads':'fresh TEST API payloads',cases:checks.length,checks};
    fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,mode:report.mode,cases:checks.length}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
