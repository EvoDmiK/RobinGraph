"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/robingraph/api/static/birds.js", "utf8");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ""; this.value = "청둥오리"; this.listeners = {}; }
  appendChild(node) { this.children.push(node); }
  replaceChildren() { this.children = []; }
  setAttribute() {}
  addEventListener(name, fn) { this.listeners[name] = fn; }
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
async function run(response, options = {}) {
  const nodes = Object.fromEntries(["bird-form", "bird-name", "bird-scope", "bird-submit", "bird-status", "bird-card"].map(id => [id,new Element(id)]));
  nodes["bird-scope"].value = options.scope || "all";
  const fetchUrls = [];
  vm.runInNewContext(source, {
    document:{getElementById:id => nodes[id],createElement:tag => new Element(tag)},
    URL, URLSearchParams, AbortSignal, location:{search: options.search || ""},
    fetch:async (url) => { fetchUrls.push(url); return typeof response === "function" ? response(url) : response; }
  });
  await new Promise(resolve => setImmediate(resolve));
  nodes._fetchUrls = fetchUrls;
  return nodes;
}
test("species UI groups identical measurements, keeps both sources and renders licensed attribution as text", async () => {
  const trait = {name:"body_mass",value:843.42,display:"843.42",label:"체중",unit:"g",license_name:"CC0",source_url:"https://example.com",citation:"EltonTraits"};
  const nodes = await run({ok:true,json:async () => ({
    taxon:{korean_name:"청둥오리",scientific_name:"Anas platyrhynchos"},
    lineage:{taxonomy_source:"AviList",taxonomy_release:"v2025b",items:[]},
    traits:[trait,{...trait,citation:"AVONET"}],vegetation_note:"미수집",warnings:[],
    images:[{image_url:"https://thumb.wikimedia.org/bird.jpg",source_url:"https://commons.wikimedia.org/wiki/File:Bird.jpg",creator:"<script>name</script>",license_name:"CC BY 2.0",license_url:"https://creativecommons.org/licenses/by/2.0",title:"새"},
            {image_url:"javascript:alert(1)",source_url:"javascript:alert(1)",creator:"unsafe"}]
  })});
  const all = descendants(nodes["bird-card"]);
  assert.equal(all.filter(node => node.tag === "strong" && node.textContent === "체중").length, 1);
  assert.equal(all.filter(node => node.tag === "img").length, 1);
  assert.ok(all.some(node => node.tag === "a" && node.textContent === "CC BY 2.0"));
  assert.ok(all.some(node => node.textContent.includes("<script>name</script>")));
  assert.ok(all.some(node => node.textContent === "EltonTraits"));
  assert.ok(all.some(node => node.textContent === "AVONET"));
  assert.equal(nodes["bird-submit"].disabled, false);
});
test("unknown species UI reports a safe error and leaves card hidden", async () => {
  const nodes = await run({ok:false,status:404});
  assert.equal(nodes["bird-card"].hidden,true);
  assert.match(nodes["bird-status"].textContent,/찾지 못했습니다/);
  assert.equal(nodes["bird-submit"].disabled,false);
});

test("photo absence and broken image retry preserve species facts and attribution", async () => {
  const profile = {
    taxon:{korean_name:"청둥오리", scientific_name:"Anas platyrhynchos"},
    lineage:{taxonomy_source:"AviList",taxonomy_release:"v2025b",items:[]},
    traits:[],vegetation_note:"미수집",warnings:[],images:[],
    photo_availability:{status:"provider_unavailable",message:"사진 제공처에 연결하지 못했습니다."}
  };
  const absent = await run({ok:true,json:async () => profile});
  assert.ok(descendants(absent["bird-card"]).some(n => n.textContent === profile.photo_availability.message));
  assert.equal(absent["bird-card"].hidden,false);
  profile.images=[{image_url:"https://thumb.wikimedia.org/bird.jpg",source_url:"https://commons.wikimedia.org/wiki/File:Bird.jpg",creator:"Photographer",license_name:"CC BY 2.0",license_url:"https://creativecommons.org/licenses/by/2.0",title:"새"}];
  const loaded = await run({ok:true,json:async () => profile});
  const all = descendants(loaded["bird-card"]);
  const image = all.find(n=>n.tag==="img");
  const retry = all.find(n=>n.textContent==="사진 다시 불러오기");
  image.listeners.error(); assert.equal(image.hidden,true); assert.equal(retry.hidden,false);
  retry.listeners.click(); assert.equal(retry.disabled,true);
  image.listeners.load(); assert.equal(image.hidden,false); assert.equal(retry.hidden,true);
  assert.ok(all.some(n=>n.textContent==="CC BY 2.0"));
});

test("RG-406: birds.js propagates species_scope, renders display_name and distribution provenance, and clears stale card on scope change without auto-submitting", async () => {
  const profile = {
    taxon: {
      korean_name: "대륙검은지빠귀",
      english_name: "Eurasian Blackbird",
      display_name: "Eurasian Blackbird",
      scientific_name: "Turdus merula",
      distribution: {
        status: "outside",
        note: "원자료의 분포 기술에서 대한민국·한반도가 확인되지 않아 국외 분포로 분류했습니다. 국내 미조·길잃은새·사육 탈출 기록이 전혀 없다는 뜻은 아닙니다.",
        evidence: [{ source_title: "AviList v2025", source_url: "https://www.avilist.org/checklist/v2025" }],
      },
    },
    lineage: { taxonomy_source: "AviList", taxonomy_release: "v2025b", items: [] },
    traits: [], vegetation_note: "미수집", warnings: [], images: [],
  };
  const nodes = await run({ ok: true, json: async () => profile }, { search: "?name=Turdus%20merula&species_scope=outside" });
  assert.equal(nodes["bird-scope"].value, "outside");
  assert.equal(nodes._fetchUrls[0], "/v1/taxa/profile?name=Turdus+merula&species_scope=outside");
  const all = descendants(nodes["bird-card"]);
  assert.ok(all.some(n => n.tag === "h2" && n.textContent === "Eurasian Blackbird"));
  assert.ok(all.some(n => n.textContent && n.textContent.includes("분포 범위: 국외 분포 검토")));
  assert.ok(all.some(n => n.tag === "a" && n.href === "https://www.avilist.org/checklist/v2025"));

  // Changing scope clears old card, preserves typed name, and does not auto-fetch
  nodes["bird-name"].value = "까치 초안";
  nodes["bird-scope"].value = "korea";
  nodes["bird-scope"].listeners.change();
  assert.equal(nodes["bird-card"].hidden, true);
  assert.equal(nodes["bird-name"].value, "까치 초안");
  assert.equal(nodes._fetchUrls.length, 1);
});
