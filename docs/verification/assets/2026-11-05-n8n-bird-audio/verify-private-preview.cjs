'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process');
const WORK='/tmp/robingraph-n8n-audio-20261105';
const CID=process.argv[2];
if(!/^[a-f0-9]{64}$/.test(CID||''))throw Error('candidate_id required');
const CHROME='/Users/kimdove/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const token=fs.readFileSync('/Users/kimdove/robingraph-test/private/audio.env','utf8').split('\n').find(x=>x.startsWith('ROBINGRAPH_INGEST_INTERNAL_TOKEN=')).split('=')[1];
const origin='http://192.168.219.97:8000';
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'rg-audio-private-'));
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const server=net.createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;await new Promise(r=>server.close(r));
 const chrome=spawn(CHROME,['--headless','--disable-gpu','--no-first-run','--disable-background-networking','--mute-audio',`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore'});
 let ws;
 try{
  let pages;for(let n=0;n<40;n++){try{pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();break}catch{await delay(100)}}
  ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.addEventListener('open',r);ws.addEventListener('error',j)});
  let id=0;const pending=new Map(),requests=[];
  ws.addEventListener('message',ev=>{const m=JSON.parse(ev.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(Error('CDP error'));else p.resolve(m.result)}else if(m.method==='Network.requestWillBeSent'){requests.push({url:m.params.request.url,method:m.params.request.method})}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const k=++id;pending.set(k,{resolve,reject});ws.send(JSON.stringify({id:k,method,params}))});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true});if(r.exceptionDetails)throw Error('Preview browser evaluation failed');return r.result.value};
  await send('Page.bringToFront');await send('Network.enable');await send('Network.setBlockedURLs',{urls:['https://upload.wikimedia.org/*','https://commons.wikimedia.org/*']});await send('Page.enable');await send('Page.navigate',{url:origin+'/chat'});await delay(700);
  const loaded=await evaluate(`(async()=>{const r=await fetch('/internal/v1/audio/preview/${CID}',{headers:{Authorization:${JSON.stringify('Bearer '+token)}},redirect:'error'});if(!r.ok)throw Error('Private preview HTTP '+r.status);const b=await r.blob();const a=document.createElement('audio');a.controls=true;a.preload='none';a.src=URL.createObjectURL(b);document.body.replaceChildren(a);window.previewAudio=a;return {status:r.status,mime:b.type,bytes:b.size,preload:a.preload,autoplay:a.autoplay};})()`);
  await evaluate('(async()=>{await window.previewAudio.play();return true})()');for(let n=0;n<24;n++){await delay(250);const state=await evaluate('({time:window.previewAudio.currentTime,error:window.previewAudio.error?.code||null})');if(state.time>.3||state.error)break;}
  const playback=await evaluate('(()=>{const a=window.previewAudio;const r={current_time:a.currentTime,duration:a.duration,paused:a.paused,ready_state:a.readyState,error_code:a.error?.code||null,decoded_bytes:a.webkitAudioDecodedByteCount||null};a.pause();a.currentTime=0;return r})()');
  const screenshot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(WORK+'/private-preview-native.png',Buffer.from(screenshot.data,'base64'));
  const result={candidate_id:CID,origin,loaded,playback,passed:playback.current_time>0&&playback.ready_state>=2&&!playback.error_code,cdn_requests:requests.filter(r=>r.url.includes('wikimedia.org')).length,scope:'actual authenticated TEST cached bytes, isolated native Chromium controls; no human listening; no publication'};
  fs.writeFileSync(WORK+'/private-preview-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  await send('Browser.close');
 }finally{if(ws)ws.close();if(chrome.exitCode===null)chrome.kill('SIGTERM');await delay(250);fs.rmSync(profile,{recursive:true,force:true})}
})().catch(e=>{console.error(e.message);process.exitCode=1});
