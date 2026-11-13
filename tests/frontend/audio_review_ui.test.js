"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/robingraph/api/static/audio-review.js", "utf8");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ""; this.hidden = false; this.disabled = false; this.listeners = {}; this.attributes = {}; this._text = ""; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(""); }
  set textContent(value) { this._text = String(value); this.children = []; }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  replaceChildren(...children) { this._text = ""; this.children.forEach(n => { n.parentNode = null; }); this.children = []; children.forEach(n => this.appendChild(n)); }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; if (key === "src") this.src = ""; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  querySelectorAll(selector) { return all(this).slice(1).filter(n => selector.split(",").map(s=>s.trim()).includes(n.tag)); }
  remove() { this.parentNode.children = this.parentNode.children.filter(n => n !== this); this.parentNode = null; }
  focus() { this.focused = true; }
  play() { this.played = true; return Promise.resolve(); }
  pause() { this.paused = true; }
  load() { this.loaded = true; }
}
function all(node) { return [node, ...node.children.flatMap(all)]; }
const id = "a".repeat(64);
function candidate(values = {}) {
  return {candidate_id:id, scientific_name:"Fixture species", korean_name:"검증용 이름", status:"awaiting_review", file_title:"File:sample.ogg", updated_at:"2026-11-09T01:00:00Z", collected_at:"2026-11-05T02:00:00Z", preview_url:"/internal/v1/audio/preview/"+id,
    recording:{title:"Original recording", creator:"Original recorder", license_name:"CC BY-SA 4.0", license_url:"https://creativecommons.org/licenses/by-sa/4.0/", source_url:"https://commons.wikimedia.org/wiki/File:sample.ogg", location:"Original location", recorded_at:"2010-01-02", evidence:{retrieved_at:"2026-11-05T00:00:00Z"}}, ...values};
}
function response(body, status = 200) { return {ok:status >= 200 && status < 300, status, json:async () => body, blob:async () => new Blob(["fixture"], {type:"audio/ogg"})}; }
function setup(fetcher = () => response({items:[candidate()],has_more:false,next_offset:null})) {
  const names = ["review-connect-form","review-key","review-connect","review-disconnect","review-library","review-status-filter","review-candidates","review-more","review-refresh","review-status"];
  const elements = Object.fromEntries(names.map(name => [name,new Element(name)]));
  elements["review-library"].hidden = true; elements["review-more"].hidden = true;
  const calls = [], urls = [], revoked = [], events = {};
  class ObjectURL extends URL {}
  ObjectURL.createObjectURL = () => { const url = "blob:fixture-"+urls.length; urls.push(url); return url; };
  ObjectURL.revokeObjectURL = value => revoked.push(value);
  vm.runInNewContext(source, {
    document:{getElementById:name => elements[name], createElement:tag => new Element(tag)},
    window:{addEventListener:(name, fn) => { events[name] = fn; }},
    URL:ObjectURL, URLSearchParams, AbortController,
    fetch:async (path, options) => { calls.push({path,options}); return fetcher(path, options); }
  });
  const click = element => element.listeners.click();
  async function settle() { for (let i=0;i<4;i++) await new Promise(resolve => setImmediate(resolve)); }
  async function connect() { elements["review-key"].value = "fixture-read-only-key"; elements["review-connect-form"].listeners.submit({preventDefault(){}}); await settle(); }
  return {elements,calls,urls,revoked,events,click,settle,connect,nodes:() => all(elements["review-candidates"])};
}

test("review authenticates only by GET header, clears key input, and renders exact metadata and unverified identity without writes", async () => {
  const f = setup(); assert.equal(f.calls.length,0); await f.connect();
  assert.equal(f.elements["review-key"].value,"");
  assert.equal(f.elements["review-library"].hidden,false);
  assert.equal(f.calls[0].path,"/internal/v1/audio/candidates?limit=20&offset=0");
  assert.equal(f.calls[0].options.headers.Authorization,"Bearer fixture-read-only-key");
  assert.equal(f.calls[0].options.method,"GET"); assert.equal(f.calls[0].options.credentials,"omit");
  assert.equal(f.calls[0].options.redirect,"error"); assert.equal(f.calls[0].options.cache,"no-store");
  const text = f.elements["review-candidates"].textContent;
  for (const value of ["검증용 이름","Fixture species","검토 대기","독립 동정 미확인","사람의 청취 검토 미확인","Original recorder","Original location","2010-01-02","2026-11-05T02:00:00Z"]) assert.ok(text.includes(value),value);
  assert.ok(!text.includes("fixture-read-only-key"));
  assert.ok(!text.includes("2026-11-05T00:00:00Z"),"source metadata time must not masquerade as collection time");
  assert.ok(f.nodes().filter(n => n.tag === "a").every(n => n.rel === "noopener noreferrer"));
  assert.equal(f.nodes().filter(n => n.tag === "audio").length,0,"metadata list must not download audio");
});

test("malicious source metadata stays text; script, data, credentialed and relative links never become navigation", async () => {
  for (const bad of ["javascript:alert(1)","data:text/html,bad","https://user:pass@example.test/","/internal/v1/audio/stage"]) {
    const f=setup(() => response({items:[candidate({korean_name:"<img src=x onerror=alert(1)>", recording:{creator:"<script>alert(1)</script>", source_url:bad, license_url:bad, license_name:"<b>CC</b>"}})],has_more:false,next_offset:null}));
    await f.connect();
    assert.ok(f.elements["review-candidates"].textContent.includes("<script>alert(1)</script>"));
    assert.equal(f.nodes().filter(n => ["a","img","script"].includes(n.tag)).length,0);
  }
  assert.ok(!/innerHTML|localStorage|sessionStorage|document\.cookie|console\./.test(source));
});

test("pagination and status filtering use bounded offset and clear old selection; empty and failed pages are explicit", async () => {
  const f=setup(path => {
    if (path.includes("status=rejected")) return response({items:[],has_more:false,next_offset:null});
    return response({items:[candidate()],has_more:!path.includes("offset=20"),next_offset:path.includes("offset=20")?null:20});
  });
  await f.connect(); assert.equal(f.elements["review-more"].hidden,false);
  f.click(f.elements["review-more"]); await f.settle();
  assert.ok(f.calls[1].path.endsWith("offset=20")); assert.equal(f.nodes().filter(n=>n.tag==="article").length,2);
  f.elements["review-status-filter"].value="rejected"; f.elements["review-status-filter"].listeners.change(); await f.settle();
  assert.match(f.calls[2].path,/offset=0&status=rejected/);
  assert.match(f.elements["review-candidates"].textContent,/조건에 맞는 수집 음원이 없습니다/);
  const failed=setup(()=>{throw new Error("secret backend detail");});await failed.connect();
  assert.match(failed.elements["review-status"].textContent,/불러오지 못했습니다/);
  assert.ok(!failed.elements["review-status"].textContent.includes("secret"));
  assert.equal(failed.elements["review-connect"].disabled,false);
});

test("expired review access clears list and prevents preview use even after previously connected", async () => {
  const f=setup(path=>path.includes("preview")?response({},401):response({items:[candidate()],has_more:false,next_offset:null}));
  await f.connect(); f.click(f.nodes().find(n=>n.tag==="button")); await f.settle();
  assert.equal(f.elements["review-library"].hidden,true); assert.equal(f.nodes().length,1);
  assert.match(f.elements["review-status"].textContent,/검토 전용 접속키만/);
  const first=setup(()=>response({},401));await first.connect();
  assert.equal(first.elements["review-library"].hidden,true);assert.equal(first.urls.length,0);
});

test("preview fetches only exact same-origin candidate path, creates one player, and revokes on switching/filter/disconnect/pagehide", async () => {
  const secondId="b".repeat(64);
  const f=setup(path=>path.includes("preview")?response({}):response({items:[candidate(),candidate({candidate_id:secondId,preview_url:"/internal/v1/audio/preview/"+secondId})],has_more:false,next_offset:null}));
  await f.connect(); const buttons=f.nodes().filter(n=>n.tag==="button");
  f.click(buttons[0]); await f.settle();
  const first=f.nodes().find(n=>n.tag==="audio");
  assert.equal(first.controls,true);assert.equal(first.preload,"none");assert.equal(first.autoplay,undefined);assert.ok(first.played);
  assert.equal(f.calls[1].path,"/internal/v1/audio/preview/"+id);
  assert.equal(f.calls[1].options.headers.Authorization,"Bearer fixture-read-only-key");
  f.click(buttons[1]);await f.settle();
  assert.ok(first.paused);assert.equal(first.src,"");assert.deepEqual(f.revoked,["blob:fixture-0"]);
  assert.equal(f.nodes().filter(n=>n.tag==="audio").length,1);
  f.elements["review-status-filter"].listeners.change();await f.settle();assert.equal(f.revoked.length,2);
  f.click(f.nodes().find(n=>n.tag==="button"));await f.settle();
  f.click(f.elements["review-disconnect"]);assert.equal(f.revoked.length,3);assert.ok(f.elements["review-key"].focused);
  await f.connect();f.click(f.nodes().find(n=>n.tag==="button"));await f.settle();f.events.pagehide();assert.equal(f.revoked.length,4);
  assert.equal(f.elements["review-key"].value,"");assert.equal(f.elements["review-library"].hidden,true);
});

test("provider-limited deferred candidates have no playback and elapsed retry time never implies completion", async () => {
  const f=setup(()=>response({items:[candidate({status:"deferred",recording:null,preview_url:null,error_code:"provider_rate_limited",retry_at:"2020-01-01T00:00:00Z"})],has_more:false,next_offset:null}));
  await f.connect();
  assert.match(f.elements["review-candidates"].textContent,/외부 제한으로 보류/);
  assert.match(f.elements["review-candidates"].textContent,/재시도 시각이 지나도 수집 완료를 뜻하지 않습니다/);
  assert.equal(f.nodes().filter(n=>n.tag==="button"||n.tag==="audio").length,0);
  assert.match(f.elements["review-candidates"].textContent,/아직 저장된 음원이 없어/);
});

test("unsafe preview URLs and failed/non-audio responses remain inert with retry and do not expose remote errors", async () => {
  const bad=setup(()=>response({items:[candidate({preview_url:"https://evil.example/"})],has_more:false,next_offset:null}));
  await bad.connect();bad.click(bad.nodes().find(n=>n.tag==="button"));await bad.settle();assert.equal(bad.calls.length,1);assert.equal(bad.urls.length,0);
  for (const reply of [()=>{throw new Error("sensitive diagnostic");},()=>({...response({}),blob:async()=>new Blob(["<html>"],{type:"text/html"})})]) {
    const f=setup(path=>path.includes("preview")?reply():response({items:[candidate()],has_more:false,next_offset:null}));
    await f.connect();const button=f.nodes().find(n=>n.tag==="button");f.click(button);await f.settle();
    assert.equal(button.disabled,false);assert.equal(f.urls.length,0);assert.match(f.elements["review-candidates"].textContent,/불러오지 못했습니다/);
    assert.ok(!f.elements["review-candidates"].textContent.includes("sensitive"));
  }
});

test("disconnect aborts pending response bodies and late completions cannot restore metadata or object URLs", async () => {
  let resolveBody;
  const f=setup(()=>({...response({}),json:()=>new Promise(resolve=>{resolveBody=resolve;})}));
  await f.connect();f.click(f.elements["review-disconnect"]);assert.equal(f.calls[0].options.signal.aborted,true);
  resolveBody({items:[candidate()],has_more:false,next_offset:null});await f.settle();
  assert.equal(f.nodes().length,1);assert.equal(f.elements["review-library"].hidden,true);
  let resolveBlob;
  const p=setup(path=>path.includes("preview")?({...response({}),blob:()=>new Promise(resolve=>{resolveBlob=resolve;})}):response({items:[candidate()],has_more:false,next_offset:null}));
  await p.connect();p.click(p.nodes().find(n=>n.tag==="button"));await p.settle();p.events.pagehide();
  assert.ok(p.calls[1].options.signal.aborted);resolveBlob(new Blob(["audio"],{type:"audio/ogg"}));await p.settle();
  assert.equal(p.urls.length,0);
});

test("review markup uses labeled native keyboard controls and a responsive dedicated sheet without embedded key or fixtures", () => {
  const html=fs.readFileSync("src/robingraph/api/static/audio-review.html","utf8");
  const css=fs.readFileSync("src/robingraph/api/static/audio-review.css","utf8");
  assert.match(html,/type="password" autocomplete="off"/);assert.match(html,/label for="review-key"/);
  assert.match(html,/type="submit"/);assert.match(html,/aria-live="polite"/);
  assert.ok(!/value="[^"]+"[^>]*id="review-key"|fixture|Bearer |sample\.ogg/.test(html));
  assert.match(css,/@media \(max-width: 540px\)/);assert.match(css,/:focus-visible/);assert.match(css,/overflow-wrap: anywhere/);
});

function editorFields(f) { return Object.fromEntries(f.nodes().filter(n=>n.name).map(n=>[n.name,n])); }
function editorForm(f) { return f.nodes().find(n=>n.tag==="form"); }
function edit(f,name,value) { const element=editorFields(f)[name];element.value=value;element.listeners.input(); }
async function submitAssessment(f) { await editorForm(f).listeners.submit({preventDefault(){}});await f.settle(); }
function assessment(values={}) { return {reviewer:"Reviewer",playback:"unchecked",source:"unchecked",identification:"unchecked",decision:"pending",note:"",identification_note:"",assessed_at:"2026-11-10T01:00:00Z",...values}; }

test("readonly access can view safe saved assessment separately from collection state but exposes no editor", async () => {
  for (const permission of [false,"true",undefined]) {
    const f=setup(()=>response({items:[candidate({assessment:assessment({decision:"candidate",note:"<script>stored note</script>",identification_note:"<img src=x>"})})],can_assess:permission,has_more:false,next_offset:null}));
    await f.connect();
    assert.equal(editorForm(f),undefined);assert.match(f.elements["review-candidates"].textContent,/조회 전용 접속/);
    assert.match(f.elements["review-candidates"].textContent,/검토 기록 · 채택 후보/);
    assert.match(f.elements["review-candidates"].textContent,/검토 대기/);
    assert.match(f.elements["review-candidates"].textContent,/<script>stored note<\/script>/);
    assert.equal(f.nodes().filter(n=>n.tag==="script"||n.tag==="img").length,0);
    assert.equal(f.calls.length,1);
  }
});

test("assessment requires explicit submit, keeps playback unchecked after listening, and updates saved record and expected version", async () => {
  const f=setup((path,options)=>{
    if(options.method==="POST") return response({candidate_id:id,updated_at:"2026-11-10T01:00:00Z",assessment:assessment(JSON.parse(options.body))});
    if(path.includes("preview"))return response({});
    return response({items:[candidate()],can_assess:true,has_more:false,next_offset:null});
  });
  await f.connect();
  const fields=editorFields(f);assert.equal(fields.playback.value,"unchecked");assert.equal(fields.decision.value,"pending");
  assert.equal(f.nodes().find(n=>n.tag==="details").open,undefined);
  f.click(f.nodes().find(n=>n.tag==="button"));await f.settle();
  assert.equal(fields.playback.value,"unchecked","native listening must not assert a human review outcome");
  edit(f,"reviewer","Reviewer");edit(f,"note","<b>literal draft</b>");
  assert.equal(f.calls.filter(c=>c.options.method==="POST").length,0);
  await submitAssessment(f);
  const posts=f.calls.filter(c=>c.options.method==="POST");assert.equal(posts.length,1);
  assert.equal(posts[0].path,"/internal/v1/audio/assessment");
  const body=JSON.parse(posts[0].options.body);
  assert.equal(body.expected_updated_at,"2026-11-09T01:00:00Z");assert.equal(body.candidate_id,id);
  assert.deepEqual(Object.keys(body).sort(),["candidate_id","expected_updated_at","reviewer","playback","source","identification","decision","note","identification_note"].sort());
  assert.equal(body.playback,"unchecked");assert.equal(body.note,"<b>literal draft</b>");
  assert.equal(posts[0].options.redirect,"error");assert.equal(posts[0].options.credentials,"omit");
  assert.match(f.elements["review-candidates"].textContent,/검토 기록을 저장했습니다/);
  assert.match(f.elements["review-candidates"].textContent,/2026-11-10T01:00:00Z/);
  await submitAssessment(f);
  assert.equal(JSON.parse(f.calls.filter(c=>c.options.method==="POST")[1].options.body).expected_updated_at,"2026-11-10T01:00:00Z");
});

test("assessment validates required evidence and prevents the active access key from entering any saved notes", async () => {
  const f=setup(()=>response({items:[candidate()],can_assess:true,has_more:false,next_offset:null}));await f.connect();
  edit(f,"reviewer","Reviewer");edit(f,"identification","additional_evidence");
  assert.equal(editorFields(f).identification_note.required,true);
  await submitAssessment(f);assert.match(f.elements["review-candidates"].textContent,/추가 동정 근거/);
  assert.equal(f.calls.length,1);
  edit(f,"identification_note","External citation");edit(f,"note","fixture-read-only-key");await submitAssessment(f);
  assert.match(f.elements["review-candidates"].textContent,/접속키를 검토 내용에 넣을 수 없습니다/);assert.equal(f.calls.length,1);
});

test("409 preserves draft, manual reload shows latest saved record alongside draft, and no retry occurs automatically", async () => {
  let reads=0;
  const f=setup((path,options)=>{
    if(options.method==="POST")return response({},409);
    reads++;
    return response({items:[candidate({updated_at:reads===1?"old-version":"new-version",assessment:reads===1?null:assessment({note:"Other reviewer saved"})})],can_assess:true,has_more:false,next_offset:null});
  });
  await f.connect();edit(f,"reviewer","My reviewer");edit(f,"note","My unsaved memo");await submitAssessment(f);
  assert.match(f.elements["review-candidates"].textContent,/다른 변경과 충돌/);
  assert.equal(editorFields(f).note.value,"My unsaved memo");assert.equal(f.calls.length,2);
  f.click(f.elements["review-refresh"]);await f.settle();
  assert.equal(editorFields(f).note.value,"My unsaved memo");assert.equal(editorFields(f).reviewer.value,"My reviewer");
  assert.match(f.elements["review-candidates"].textContent,/Other reviewer saved/);
  assert.match(f.elements["review-candidates"].textContent,/미저장 입력을 유지했습니다/);
  assert.equal(f.calls.filter(c=>c.options.method==="POST").length,1);
  await submitAssessment(f);
  assert.equal(JSON.parse(f.calls.filter(c=>c.options.method==="POST")[1].options.body).expected_updated_at,"new-version");
});

test("save failures preserve inputs without rendering response details or resubmitting, and disconnect wipes detached editors", async () => {
  for(const failure of [422,502,"network"]){
    const f=setup((path,options)=>{
      if(options.method==="POST"){if(failure==="network")throw Error("private error");return response({detail:"private error"},failure);}
      return response({items:[candidate()],can_assess:true,has_more:false,next_offset:null});
    });
    await f.connect();edit(f,"reviewer","Reviewer");edit(f,"note","Private draft");await submitAssessment(f);
    assert.equal(editorFields(f).note.value,"Private draft");assert.match(f.elements["review-candidates"].textContent,/저장하지 못했습니다/);
    assert.ok(!f.elements["review-candidates"].textContent.includes("private error"));assert.equal(f.calls.filter(c=>c.options.method==="POST").length,1);
    const old=editorFields(f);f.click(f.elements["review-disconnect"]);
    assert.equal(old.note.value,"");assert.equal(old.reviewer.value,"");
    await f.connect();assert.equal(editorFields(f).note.value,"");
  }
});

test("stale save responses after filter or disconnect cannot replace records or restore deleted notes", async () => {
  for(const disconnect of [false,true]){
    let complete;
    const f=setup((path,options)=>options.method==="POST"?new Promise(resolve=>{complete=resolve;}):response({items:[candidate()],can_assess:true,has_more:false,next_offset:null}));
    await f.connect();edit(f,"reviewer","Reviewer");edit(f,"note","Unsaved draft");
    const saving=editorForm(f).listeners.submit({preventDefault(){}});await f.settle();
    if(disconnect){f.click(f.elements["review-disconnect"]);await f.connect();}
    else{f.elements["review-status-filter"].listeners.change();await f.settle();}
    complete(response({candidate_id:id,updated_at:"stale-version",assessment:assessment({note:"Stale response"})}));await saving;await f.settle();
    assert.ok(!f.elements["review-candidates"].textContent.includes("Stale response"));
    assert.equal(editorFields(f).note.value,disconnect?"":"Unsaved draft");
  }
});
