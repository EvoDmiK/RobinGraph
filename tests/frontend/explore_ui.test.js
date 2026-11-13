"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const STATIC_DIR = path.join(__dirname, "../../src/robingraph/api/static");
const exploreHtml = fs.readFileSync(path.join(STATIC_DIR, "explore.html"), "utf8");
const exploreCss = fs.readFileSync(path.join(STATIC_DIR, "explore.css"), "utf8");
const exploreJsSource = fs.readFileSync(path.join(STATIC_DIR, "explore.js"), "utf8");
const indexHtml = fs.readFileSync(path.join(STATIC_DIR, "index.html"), "utf8");
const explore = require(path.join(STATIC_DIR, "explore.js"));

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toLowerCase();
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.className = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
    this._text = "";
  }
  get textContent() {
    return this._text + this.children.map((c) => c.textContent).join("");
  }
  set textContent(val) {
    this._text = String(val ?? "");
    this.children = [];
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  removeChild(child) {
    this.children = this.children.filter((node) => node !== child);
    child.parentNode = null;
  }
  replaceChildren(...nodes) {
    this._text = "";
    this.children = [];
    nodes.forEach((n) => this.appendChild(n));
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
  }
  getAttribute(k) {
    return this.attributes[k];
  }
  removeAttribute(k) {
    delete this.attributes[k];
  }
  addEventListener(type, fn) {
    if (!this.listeners[type]) { this.listeners[type] = []; }
    this.listeners[type].push(fn);
  }
  dispatch(type, event = {}) {
    (this.listeners[type] || []).forEach((fn) => fn(event));
  }
}

function allNodes(root) {
  return [root, ...(root.children || []).flatMap(allNodes)];
}

function createExploreDom(fetcher, initialSearch = "") {
  const elements = {};
  const register = (id, tag = "div") => {
    const el = new FakeElement(tag);
    el.id = id;
    elements[id] = el;
    return el;
  };

  register("explore-form", "form");
  register("explore-taxon", "input");
  register("explore-habitat", "select");
  register("explore-scope-note", "p");
  register("explore-submit", "button");
  register("explore-reset", "button");
  register("explore-status", "p");
  const results = register("explore-results", "section");
  results.hidden = true;

  for (const scope of explore.SPECIES_SCOPES) {
    const radio = register("explore-scope-" + scope, "input");
    radio.value = scope;
    radio.checked = scope === "all";
  }

  for (const diet of explore.DIETS) {
    const box = register("explore-diet-" + diet, "input");
    box.value = diet;
    box.checked = false;
  }

  const fetchCalls = [];
  const replacedUrls = [];
  const doc = {
    body: new FakeElement("body"),
    getElementById: (id) => elements[id] || null,
    createElement: (tag) => new FakeElement(tag),
  };
  const win = {
    location: { pathname: "/explore", search: initialSearch },
    history: {
      replaceState: (_state, _title, url) => {
        replacedUrls.push(url);
      },
    },
    fetch: (url, options) => {
      fetchCalls.push({ url, options });
      return fetcher(url, options);
    },
  };

  const controller = explore.init(doc, win);
  return { elements, doc, win, fetchCalls, replacedUrls, controller };
}

async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

function jsonRes(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

test("explore.html, explore.css, explore.js, and index.html declare required controls, links, and safe code rules", () => {
  assert.ok(indexHtml.includes('href="/explore"'), "index.html must provide an entry link to /explore");
  assert.ok(exploreHtml.includes('href="/chat"'), "explore.html must link back to /chat");
  assert.ok(exploreHtml.includes('href="/birds"'), "explore.html must link to /birds");

  for (const scope of ["all", "korea", "outside", "unknown"]) {
    assert.ok(exploreHtml.includes(`id="explore-scope-${scope}"`), `missing scope radio: ${scope}`);
  }
  for (const habitat of explore.HABITATS) {
    assert.ok(exploreHtml.includes(`value="${habitat}"`), `missing habitat option: ${habitat}`);
  }
  for (const diet of explore.DIETS) {
    assert.ok(exploreHtml.includes(`id="explore-diet-${diet}"`), `missing diet checkbox: ${diet}`);
  }
  assert.ok(exploreHtml.includes("모두 0%보다 큰 종(AND 조건)"), "must explain multi-diet AND semantics");
  assert.ok(exploreHtml.includes("선택한 먹이 비율의 합계가 높은 순"), "must explain diet sum descending sort");
  assert.ok(exploreCss.includes("@media (max-width: 640px)"), "explore.css must include mobile responsive layout");
  assert.equal(
    /innerHTML|outerHTML|insertAdjacentHTML|document\.write|localStorage|sessionStorage|document\.cookie|console\./.test(exploreJsSource),
    false,
    "explore.js must not contain HTML injection sinks, storage APIs, or console calls"
  );
});

test("buildExploreParams omits empty optional parameters and normalizes diet keys to contract order", () => {
  const emptyParams = explore.buildExploreParams({ species_scope: "all", taxon: "   ", habitat: "", diet: [] });
  assert.equal(emptyParams.toString(), "species_scope=all");

  const fullParams = explore.buildExploreParams({
    species_scope: "korea",
    taxon: " 참새목 ",
    habitat: "Forest",
    diet: ["seed", "fruit", "seed", "invalid_key"],
  });
  assert.equal(fullParams.get("species_scope"), "korea");
  assert.equal(fullParams.get("taxon"), "참새목");
  assert.equal(fullParams.get("habitat"), "Forest");
  assert.equal(fullParams.get("diet"), "fruit,seed", "diet keys must follow canonical EltonTraits order without duplicates");
});

test("shareable URL restores exact filter selection, renders answer with coverage, 20-cap, sources, limitations, and /birds links", async () => {
  const samplePayload = {
    status: "answer",
    title: "참새목 (Passeriformes) 중 조건에 맞는 종",
    text: "국내 기록 범위에서 조건에 모두 맞습니다.",
    taxon: { taxon_id: "t_order", rank: "order", scientific_name: "Passeriformes", korean_name: "참새목" },
    conditions: [
      { trait_name: "habitat", label: "서식 환경 숲(Forest)" },
      { trait_name: "diet_distribution", label: "먹이 구성에 열매 포함" },
      { trait_name: "diet_distribution", label: "먹이 구성에 씨앗 포함" },
    ],
    coverage: { scoped: 320, evaluable: 300, matched: 25 },
    has_more: true,
    pagination: { page: 1, page_size: 20, total: 25, total_pages: 2 },
    items: [
      {
        taxon: {
          taxon_id: "sp1",
          rank: "species",
          scientific_name: "Zosterops japonicus",
          korean_name: "동박새",
          english_name: "Warbling White-eye",
        },
        paths: [
          { text: "서식 환경: 숲 (Forest)", source_name: "AVONET", source_url: "https://doi.org/10.6084/m9.figshare.16586228.v7" },
          { text: "먹이 구성: 열매 40% · 씨앗 20% · EltonTraits 확실성 A", source_name: "EltonTraits", source_url: "https://doi.org/10.6084/m9.figshare.3559887.v1" },
        ],
      },
    ],
    paths: [
      { text: "범위 확인: 국내 기록 종", source_name: "AviList v2025b", source_url: "https://explore.avilist.org" },
    ],
    sources: [
      { name: "AVONET", url: "https://doi.org/10.6084/m9.figshare.16586228.v7" },
      { source_name: "EltonTraits v1", source_url: "https://doi.org/10.6084/m9.figshare.3559887.v1" },
    ],
    limitations: [
      "그래프에 종과 직접 연결된 형질 주장만 검색합니다.",
      "그래프에 종과 직접 연결된 형질 주장만 검색합니다. ",
    ],
    query: {
      species_scope: "korea",
      taxon: "Passeriformes",
      habitat: "Forest",
      diet: ["fruit", "seed"],
    },
  };

  const dom = createExploreDom(
    () => jsonRes(samplePayload),
    "?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=seed,fruit"
  );
  await settle();

  assert.equal(dom.fetchCalls.length, 1);
  assert.equal(
    dom.fetchCalls[0].url,
    "/v1/taxa/explore?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=seed,fruit"
  );
  assert.equal(dom.elements["explore-scope-korea"].checked, true);
  assert.equal(dom.elements["explore-taxon"].value, "Passeriformes");
  assert.equal(dom.elements["explore-habitat"].value, "Forest");
  assert.equal(dom.elements["explore-diet-fruit"].checked, true);
  assert.equal(dom.elements["explore-diet-seed"].checked, true);
  assert.equal(dom.elements["explore-diet-fish"].checked, false);

  const results = dom.elements["explore-results"];
  assert.equal(results.hidden, false);
  const text = results.textContent;
  assert.ok(text.includes("참새목 (Passeriformes) 중 조건에 맞는 종"));
  assert.ok(text.includes("320종"));
  assert.ok(text.includes("300종"));
  assert.ok(text.includes("25종"));
  assert.ok(text.includes("전체 25종 중 1–1종"));
  assert.ok(text.includes("선택한 먹이 구성 비율 합산 높은 순"));
  assert.ok(text.includes("동박새"));
  assert.ok(text.includes("Zosterops japonicus"));

  const nodes = allNodes(results);
  const profileLink = nodes.find((n) => n.tagName === "a" && n.className === "explore-profile-link");
  assert.ok(profileLink);
  assert.equal(profileLink.href, "/birds?name=Zosterops+japonicus&species_scope=korea");

  const cardSources = nodes.find((n) => n.className === "explore-card-sources");
  assert.ok(cardSources);
  assert.equal(cardSources.open, undefined);
  assert.equal(cardSources.children[0].textContent, "출처 2개");
  const sourceLinks = allNodes(cardSources).filter((n) => n.tagName === "a");
  assert.deepEqual(sourceLinks.map((n) => n.textContent), ["AVONET", "EltonTraits"]);
  assert.equal(sourceLinks[0].href, samplePayload.items[0].paths[0].source_url);
  const evidenceList = nodes.find((n) => n.className === "explore-item-paths");
  assert.equal(allNodes(evidenceList).filter((n) => n.tagName === "a").length, 0);
  assert.ok(evidenceList.textContent.includes("EltonTraits 확실성 A"));

  const limitationsBox = nodes.find((n) => n.className && n.className.includes("explore-limitations"));
  assert.ok(limitationsBox);
  assert.equal(limitationsBox.open, undefined, "limitations disclosure must be collapsed by default");
  assert.ok(limitationsBox.textContent.includes("안내 및 유의사항 (1)"), "duplicate limitations must be deduplicated");
});

test("outside scope prioritizes English common names and propagates outside scope to /birds profile link", async () => {
  const payload = {
    status: "answer",
    title: "국외 분포 조류 조회",
    text: "국외 분포 검토 결과입니다.",
    coverage: { scoped: 100, evaluable: 100, matched: 1 },
    has_more: false,
    items: [
      {
        taxon: {
          taxon_id: "sp_out",
          rank: "species",
          scientific_name: "Turdus merula",
          korean_name: "대륙검은지빠귀",
          english_name: "Eurasian Blackbird",
        },
        paths: [],
      },
    ],
    sources: [],
    limitations: [],
    query: { species_scope: "outside", taxon: null, habitat: null, diet: [] },
  };

  const dom = createExploreDom(() => jsonRes(payload), "?species_scope=outside");
  await settle();

  const nodes = allNodes(dom.elements["explore-results"]);
  const primaryName = nodes.find((n) => n.className === "explore-species-name");
  assert.ok(primaryName);
  assert.equal(primaryName.textContent, "Eurasian Blackbird");

  const profileLink = nodes.find((n) => n.className === "explore-profile-link");
  assert.ok(profileLink);
  assert.equal(profileLink.href, "/birds?name=Turdus+merula&species_scope=outside");
});

test("empty, insufficient_data, 422 validation error, and 503 unavailable states are visibly distinct", async () => {
  let currentResponse = () => jsonRes({
    status: "empty",
    title: "조건 결과 없음",
    text: "조건을 모두 만족하는 종이 없습니다.",
    coverage: { scoped: 500, evaluable: 420, matched: 0 },
    items: [],
    sources: [],
    limitations: [],
  });

  const dom = createExploreDom((url, opts) => currentResponse(url, opts));

  // 1. Empty (0 matching species)
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} });
  await settle();
  assert.equal(dom.elements["explore-results"].getAttribute("data-result-state"), "empty");
  assert.ok(dom.elements["explore-results"].textContent.includes("조건에 맞는 새가 없습니다 (일치 0종)"));

  // 2. Insufficient data (evaluable = 0)
  currentResponse = () => jsonRes({
    status: "insufficient_data",
    title: "자료 부족",
    text: "활성 형질 자료가 확인되지 않았습니다.",
    coverage: { scoped: 50, evaluable: 0, matched: 0 },
    items: [],
    sources: [],
    limitations: ["직접 연결된 형질 자료만 평가합니다."],
  });
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} });
  await settle();
  assert.equal(dom.elements["explore-results"].getAttribute("data-result-state"), "insufficient_data");
  assert.ok(dom.elements["explore-results"].textContent.includes("조건을 판단할 형질 자료가 없습니다"));

  // 3. 422 Validation error (e.g. taxon_not_found & taxon_rank_unsupported)
  currentResponse = () => jsonRes(
    { detail: [{ type: "taxon_not_found", loc: ["query", "taxon"], msg: "not found" }] },
    422
  );
  dom.elements["explore-taxon"].value = "없는분류군";
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} });
  await settle();
  assert.equal(dom.elements["explore-results"].getAttribute("data-result-state"), "validation_error");
  assert.ok(dom.elements["explore-results"].textContent.includes("활성 분류 체계에서 찾지 못했습니다"));

  // 4. 503 Server unavailable error
  currentResponse = () => jsonRes({ detail: "Bird explorer is temporarily unavailable" }, 503);
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} });
  await settle();
  assert.equal(dom.elements["explore-results"].getAttribute("data-result-state"), "error");
  assert.ok(dom.elements["explore-results"].textContent.includes("일시적으로 사용할 수 없습니다"));
  assert.equal(dom.elements["explore-results"].textContent.includes("temporarily unavailable"), false, "must not echo raw server exception text");
});

test("changing filter controls does not auto-submit and drops stale in-flight responses", async () => {
  let resolveSlow;
  const slowPromise = new Promise((resolve) => {
    resolveSlow = resolve;
  });

  const dom = createExploreDom(() => slowPromise);
  dom.elements["explore-taxon"].value = "Passeriformes";
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} });
  assert.equal(dom.fetchCalls.length, 1);
  assert.equal(dom.elements["explore-submit"].disabled, true);

  // User changes habitat while request #1 is still in flight
  dom.elements["explore-habitat"].value = "Wetland";
  dom.elements["explore-habitat"].dispatch("change", {});

  assert.equal(dom.fetchCalls.length, 1, "changing a filter must not auto-submit");
  assert.equal(dom.elements["explore-submit"].disabled, false, "submit button must be re-enabled when filter edit invalidates pending search");

  // Stale response resolves now
  resolveSlow({
    ok: true,
    status: 200,
    json: async () => ({
      status: "answer",
      title: "이전 오래된 응답",
      items: [],
      query: { species_scope: "all", taxon: "Passeriformes", habitat: "Forest", diet: [] },
    }),
  });
  await settle();

  assert.equal(dom.elements["explore-results"].hidden, true, "stale response must not render into results");
  assert.equal(dom.elements["explore-habitat"].value, "Wetland", "stale response must not overwrite newer filter state");
});

test("hostile URLs and HTML strings in payload are neutralized as plain text", async () => {
  const hostilePayload = {
    status: "answer",
    title: "<script>alert(1)</script>",
    text: "<img src=x onerror=alert(1)>",
    items: [
      {
        taxon: {
          scientific_name: "Anas platyrhynchos",
          korean_name: "<b>청둥오리</b>",
        },
        paths: [
          { text: "경로", source_name: "Evil", source_url: "javascript:alert(1)" },
          { text: "자격증명", source_name: "Creds", source_url: "https://user:pass@example.com/data" },
        ],
      },
    ],
    sources: [
      { name: "DataUrl", url: "data:text/html,evil" },
      { name: "RelativeUrl", url: "/internal/admin" },
    ],
    limitations: ["<svg onload=alert(1)>"],
  };

  const dom = createExploreDom(() => jsonRes(hostilePayload), "?species_scope=all");
  await settle();

  const nodes = allNodes(dom.elements["explore-results"]);
  const links = nodes.filter((n) => n.tagName === "a");
  // Only the safe /birds profile link should be an <a> tag; all hostile source URLs become <span>
  assert.equal(links.length, 1);
  assert.ok(links[0].href.startsWith("/birds?"));
  assert.ok(dom.elements["explore-results"].textContent.includes("<script>alert(1)</script>"));
});

test("explorer opens the shared species popup with exact identity and scope, and closes without losing results", async () => {
  const taxon = { taxon_id: "bird-1", scientific_name: "Asio otus", korean_name: "칡부엉이" };
  const lineage = { concept_set_id: "active", taxonomy_release: "2025b" };
  const payload = { status: "answer", items: [{ taxon }], query: { species_scope: "korea" } };
  let finishEnrichment, finishMedia, enriched = 0;
  const dom = createExploreDom((url) => {
    if (!url.startsWith("/v1/taxa/profile")) return jsonRes(payload);
    if (url.includes("defer_enrichment=true")) return jsonRes({ taxon, lineage, enrichment_pending: true });
    if (url.includes("include_notes=false")) return new Promise((resolve) => { finishMedia = resolve; });
    return new Promise((resolve) => { finishEnrichment = resolve; });
  }, "?species_scope=korea");
  await settle();
  let popup, cardOptions, disposed = 0;
  dom.win.RobinGraphChat = {
    buildSpeciesCard: (_doc, profile, options) => {
      assert.deepEqual(profile.taxon, taxon); cardOptions = options;
      const card = new FakeElement("div");
      card.setEnrichmentMessage = () => {};
      card.setNotesMessage = () => {};
      card.updateEnrichment = () => { enriched++; };
      return card;
    },
    buildSpeciesPopup: () => {
      popup = new FakeElement("div");
      const opener = new FakeElement("button"), dialog = new FakeElement("dialog");
      opener.click = () => { dialog.open = true; };
      popup.appendChild(opener); popup.appendChild(dialog);
      popup.disposePopup = () => { disposed++; dialog.open = false; };
      return popup;
    },
  };
  const results = dom.elements["explore-results"];
  const link = allNodes(results).find((n) => n.className === "explore-profile-link");
  let prevented = 0, focused = 0;
  link.isConnected = true; link.focus = () => { focused++; };
  link.dispatch("click", { ctrlKey: true, preventDefault: () => { prevented++; } });
  assert.equal(dom.fetchCalls.length, 1);
  link.dispatch("click", { preventDefault: () => { prevented++; } });
  await settle();
  assert.equal(prevented, 1);
  assert.equal(dom.fetchCalls[1].url, "/v1/taxa/profile?name=Asio+otus&species_scope=korea&defer_enrichment=true");
  assert.equal(cardOptions.speciesScope, "korea");
  assert.equal(cardOptions.isActive(), true);
  assert.equal(popup.children[1].open, true);
  assert.equal(enriched, 0, "popup must open while enrichment is still pending");
  finishMedia({ ok: true, json: async () => ({ taxon, lineage, images: [{ image_url: "https://upload.wikimedia.org/bird.jpg" }] }) });
  await settle();
  assert.equal(enriched, 1, "photo must appear while notes are still pending");
  finishEnrichment({ ok: true, json: async () => ({ taxon, lineage }) });
  await settle();
  assert.equal(enriched, 2);
  assert.equal(link.getAttribute("aria-haspopup"), "dialog");
  popup.children[1].dispatch("close");
  assert.equal(disposed, 1);
  assert.equal(cardOptions.isActive(), false);
  assert.equal(dom.doc.body.children.length, 0);
  assert.equal(focused, 1);
  assert.ok(results.textContent.includes("칡부엉이"));
  const requests = dom.fetchCalls.length;
  link.dispatch("click", { preventDefault() {} });
  await settle();
  assert.equal(popup.children[1].open, true);
  assert.equal(dom.fetchCalls.length, requests, "reopening uses the already loaded profile");
});

test("failed, mismatched, and stale profile responses never open a different species card", async () => {
  const taxon = { scientific_name: "Asio otus" };
  const payload = { status: "answer", items: [{ taxon }] };
  let respond;
  const dom = createExploreDom((url) => url.startsWith("/v1/taxa/profile") ? new Promise((resolve) => { respond = resolve; }) : jsonRes(payload), "?species_scope=all");
  await settle();
  let built = 0;
  dom.win.RobinGraphChat = { buildSpeciesCard: () => { built++; throw new Error("unexpected card"); } };
  const link = allNodes(dom.elements["explore-results"]).find((n) => n.className === "explore-profile-link");
  for (const response of [{ ok: false, status: 503 }, { ok: true, json: async () => ({ taxon: { scientific_name: "Other bird" } }) }]) {
    link.dispatch("click", { preventDefault() {} });
    respond(response);
    await settle();
    assert.ok(dom.elements["explore-status"].textContent.includes("불러오지 못했습니다"));
    assert.equal(dom.doc.body.children.length, 0);
  }
  link.dispatch("click", { preventDefault() {} });
  dom.elements["explore-taxon"].dispatch("input");
  const status = dom.elements["explore-status"].textContent;
  respond({ ok: true, json: async () => ({ taxon }) });
  await settle();
  assert.equal(dom.elements["explore-status"].textContent, status);
  assert.equal(dom.doc.body.children.length, 0);
  assert.equal(built, 0);
});

test("pagination restores URL page, preserves applied filters, reaches last page, and resets on new search", async () => {
  const dom = createExploreDom((url) => {
    const params = new URL(url, "https://example.org").searchParams;
    const page = Math.min(3, Number(params.get("page") || 1));
    const start = (page - 1) * 20, size = Math.min(20, 45 - start);
    return jsonRes({ status: "answer", coverage: { scoped: 60, evaluable: 50, matched: 45 }, has_more: page < 3,
      pagination: { page, page_size: 20, total: 45, total_pages: 3 },
      query: { species_scope: params.get("species_scope"), taxon: params.get("taxon"), habitat: params.get("habitat"), diet: (params.get("diet") || "").split(",").filter(Boolean), page },
      items: Array.from({ length: size }, (_, i) => ({ taxon: { taxon_id: "fixture-" + (start + i), scientific_name: "Fixture " + (start + i) } })),
    });
  }, "?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=fruit&page=2");
  await settle();
  const results = dom.elements["explore-results"];
  const pagers = () => allNodes(results).filter((n) => n.className === "explore-pagination");
  assert.equal(pagers().length, 2);
  assert.equal(pagers()[0].children[1].value, "2");
  assert.ok(results.textContent.includes("전체 45종 중 21–40종"));
  assert.equal(allNodes(results).filter((n) => n.className === "explore-species-card").length, 20);
  const select = pagers()[1].children[1];
  select.value = "3"; select.dispatch("change"); await settle();
  assert.ok(results.textContent.includes("전체 45종 중 41–45종"));
  assert.equal(pagers()[0].children[2].disabled, true);
  const query = new URL(dom.fetchCalls.at(-1).url, "https://example.org").searchParams;
  assert.equal(query.get("species_scope"), "korea");
  assert.equal(query.get("taxon"), "Passeriformes");
  assert.equal(query.get("habitat"), "Forest");
  assert.equal(query.get("diet"), "fruit");
  assert.equal(query.get("page"), "3");
  assert.ok(dom.replacedUrls.at(-1).endsWith("page=3"));
  pagers()[0].children[0].dispatch("click"); await settle();
  assert.equal(pagers()[0].children[1].value, "2");
  dom.elements["explore-diet-fruit"].checked = false;
  dom.elements["explore-diet-seed"].checked = true;
  dom.elements["explore-diet-seed"].dispatch("change");
  assert.equal(results.hidden, true, "edited filters must not leave old pagination active");
  dom.elements["explore-form"].dispatch("submit", { preventDefault() {} }); await settle();
  assert.equal(pagers()[0].children[1].value, "1");
  assert.equal(pagers()[0].children[0].disabled, true);
  const reset = new URL(dom.fetchCalls.at(-1).url, "https://example.org").searchParams;
  assert.equal(reset.has("page"), false);
  assert.equal(reset.get("diet"), "seed");
});
