"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("src/robingraph/api/static/birds.js", "utf8");
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ""; this.value = "청둥오리"; }
  appendChild(node) { this.children.push(node); }
  replaceChildren() { this.children = []; }
  setAttribute() {}
  addEventListener() {}
}
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
async function run(response) {
  const nodes = Object.fromEntries(["bird-form", "bird-name", "bird-submit", "bird-status", "bird-card"].map(id => [id,new Element(id)]));
  vm.runInNewContext(source, {
    document:{getElementById:id => nodes[id],createElement:tag => new Element(tag)},
    URL, URLSearchParams, AbortSignal, location:{search:""}, fetch:async () => response
  });
  await new Promise(resolve => setImmediate(resolve));
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
