"use strict";

/**
 * Browser-free acceptance checks for the RobinGraph manual chat test UI
 * under src/robingraph/api/static/. Run with:
 *
 *   node --test tests/frontend/chat_ui.test.js
 *
 * No Playwright/Selenium/CDP/browser is involved: this only requires
 * chat.js as a plain Node/CommonJS module (via the UMD wrapper at the top
 * of that file) and does plain text/regex assertions on index.html.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const STATIC_DIR = path.join(__dirname, "..", "..", "src", "robingraph", "api", "static");

const chat = require(path.join(STATIC_DIR, "chat.js"));
const jsSource = fs.readFileSync(path.join(STATIC_DIR, "chat.js"), "utf8");
const htmlSource = fs.readFileSync(path.join(STATIC_DIR, "index.html"), "utf8");

test("unverified translations fall back to English in cards, explanations and comparisons", () => {
  const profile = fakeProfilePayload().result.profile;
  profile.taxon.korean_name = "에메랄드턱벌새";
  profile.taxon.english_name = "Emerald-chinned Hummingbird";
  profile.taxon.korean_name_status = "machine-translated";
  profile.sections = [{ title: "기본 정보", items: [] }];
  const doc = { createElement: createFakeElement };
  const card = chat.buildSpeciesCard(doc, profile);
  const answer = chat.buildSpeciesAnswer(doc, profile);
  assert.equal(chat.speciesLabel(profile.taxon), "Emerald-chinned Hummingbird");
  assert.equal(answer.children[0].textContent, "Emerald-chinned Hummingbird");
  assert.equal(collectAllNodes(card).find(n => n.className === "species-title").textContent, "Emerald-chinned Hummingbird");
  const comparison = chat.buildSpeciesComparison(doc, profile, profile);
  assert.ok(collectAllNodes(comparison).some(n => n.textContent === "Emerald-chinned Hummingbird"));
  profile.taxon.korean_name_status = "community-sourced";
  assert.equal(chat.speciesLabel(profile.taxon), "에메랄드턱벌새");
});

function stripJsComments(source) {
  // Block comments first, then line comments; this file has no string or
  // regex literals containing "//", so a plain line-comment strip is safe.
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

test("chat.js contains no HTML-injection sink in executable code (comments may discuss them)", () => {
  const codeOnly = stripJsComments(jsSource);
  const forbidden = [
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function(",
  ];
  for (const sink of forbidden) {
    assert.equal(codeOnly.includes(sink), false, "chat.js must not use " + sink + " outside comments");
  }
});

test("chat.js wires the fail-closed disposition guard into the /v1/chat success path", () => {
  const codeOnly = stripJsComments(jsSource);
  // The success branch must gate on formatDisposition(...).recognized before
  // ever calling appendAnswerMessage, and must route the unrecognized case
  // through the dedicated "unsupported-response" error kind rather than
  // rendering the payload.
  assert.match(codeOnly, /dispositionInfo\.recognized/);
  assert.match(codeOnly, /kind:\s*"unsupported-response"/);

  const submitMatch = codeOnly.match(/function submitQuestion[\s\S]*?\n  \}\n/);
  assert.ok(submitMatch, "expected to locate submitQuestion in chat.js");
  const submitBody = submitMatch[0];
  const guardIndex = submitBody.indexOf("dispositionInfo.recognized");
  const renderIndex = submitBody.indexOf("appendAnswerMessage(result.payload)");
  assert.ok(guardIndex !== -1 && renderIndex !== -1, "expected both the guard and the render call in submitQuestion");
  assert.ok(guardIndex < renderIndex, "the recognized-disposition guard must run before rendering the answer");
});

test("chat submission and health checks fetch same-origin /health and /v1/chat", () => {
  const calls = Array.from(jsSource.matchAll(/\.fetch\(\s*"([^"]+)"/g)).map((match) => match[1]);
  assert.deepEqual(calls.sort(), ["/health", "/v1/chat"]);
  assert.equal(jsSource.includes("https://"), false, "no absolute/remote URL literal is allowed in chat.js");
  assert.equal(jsSource.includes("http://"), false, "no absolute/remote URL literal is allowed in chat.js");
});

test("chat.js has no browser persistence or analytics API", () => {
  for (const forbidden of ["local" + "Storage", "session" + "Storage", "document." + "cookie", "analytics"]) {
    assert.equal(jsSource.includes(forbidden), false, "must not contain " + forbidden);
  }
});

test("buildChatPayload sends only route-appropriate typed filters and bounds limits", () => {
  assert.deepEqual(chat.buildChatPayload("계통?", "auto", {}), { question: "계통?", intent: "auto" });
  assert.deepEqual(chat.buildChatPayload("계통?", "taxonomy", { scientific_name: " Anas platyrhynchos ", name: "청둥오리" }), {
    question: "계통?", intent: "taxonomy", filters: { kind: "taxonomy", scientific_name: "Anas platyrhynchos" },
  });
  assert.deepEqual(chat.buildChatPayload("관찰?", "observations", { place: " Seoul ", limit: "11", common_name: "ignored" }), {
    question: "관찰?", intent: "observations", filters: { kind: "observations", place: "Seoul", limit: 10 },
  });
  assert.deepEqual(chat.buildChatPayload("근거?", "evidence", { mode: "ignored", limit: "2" }), {
    question: "근거?", intent: "evidence", filters: { kind: "evidence", limit: 2 },
  });
  assert.deepEqual(chat.buildChatPayload("청둥오리?", "profile", { name: " 청둥오리 " }), {
    question: "청둥오리?", intent: "profile", filters: { kind: "profile", name: "청둥오리" },
  });
  assert.deepEqual(chat.buildChatPayload("청둥오리?", "profile", {}), {
    question: "청둥오리?", intent: "profile", filters: { kind: "profile" },
  });
});

test("sanitizeImageUrl (the render helper backing species photo <img src>) only accepts https Wikimedia media hosts", () => {
  assert.equal(chat.sanitizeImageUrl("https://upload.wikimedia.org/wikipedia/commons/mallard.jpg"), "https://upload.wikimedia.org/wikipedia/commons/mallard.jpg");
  assert.equal(chat.sanitizeImageUrl("https://thumb.wikimedia.org/wikipedia/commons/thumb/mallard.jpg"), "https://thumb.wikimedia.org/wikipedia/commons/thumb/mallard.jpg");

  const hostilePayloads = [
    "javascript:alert(1)",
    "data:image/png;base64,aGVsbG8=",
    "http://upload.wikimedia.org/x.jpg", // not https
    "https://evil.example/x.jpg", // not an allow-listed host
    "https://upload.wikimedia.org.evil.example/x.jpg", // lookalike host
    "//upload.wikimedia.org/x.jpg", // protocol-relative
    "not a url at all",
    "",
    "   ",
    null,
    undefined,
    42,
    {},
  ];
  for (const payload of hostilePayloads) {
    assert.equal(
      chat.sanitizeImageUrl(payload),
      null,
      "expected hostile/non-allow-listed image payload to be rejected: " + JSON.stringify(payload)
    );
  }
});

test("resultSummaryLines exposes typed lineage, public observations, and grounded evidence text with channels", () => {
  assert.deepEqual(chat.resultSummaryLines({
    kind: "taxonomy",
    lineage: { lineage: [{ rank: "species", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" }] },
  }), ["종 (species) · Anas platyrhynchos (청둥오리)"]);
  assert.deepEqual(chat.resultSummaryLines({
    kind: "taxonomy",
    lineage: { lineage: [
      { rank: "genus", scientific_name: "Anas", korean_name: "오리속", korean_name_source_url: "https://www.wikidata.org/wiki/Q214264" },
      { rank: "family", scientific_name: "UnknownFamily", korean_name: null },
    ] },
  }), ["속 (genus) · Anas (오리속) · 참고 국명", "과 (family) · UnknownFamily · 한국어 이름 미등록"]);
  assert.deepEqual(chat.resultSummaryLines({
    kind: "observations",
    results: [{ observed_at: "2025-01-02", taxon: { scientific_name: "Anas platyrhynchos" }, place: { name: "Seoul" }, coordinate_disclosure: "withheld" }],
  }), ["2025-01-02 · Anas platyrhynchos · Seoul · 좌표 비공개"]);
  assert.deepEqual(chat.resultSummaryLines({
    kind: "evidence",
    search: { results: [{ text: "grounded excerpt", channels: ["fulltext", "vector"] }] },
  }), ["grounded excerpt [fulltext, vector]"]);
});

test("sanitizeUrl (the render helper backing citation links) rejects every hostile URL scheme", () => {
  const hostilePayloads = [
    "javascript:alert(1)",
    "javascript:alert(document.cookie)",
    "JavaScript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "//evil.example/x",
    "  javascript:alert(1)",
    "not a url at all",
    "",
    "   ",
    null,
    undefined,
    42,
    {},
  ];
  for (const payload of hostilePayloads) {
    assert.equal(
      chat.sanitizeUrl(payload),
      null,
      "expected hostile payload to be rejected: " + JSON.stringify(payload)
    );
  }
});

test("sanitizeUrl accepts well-formed absolute http(s) URLs unchanged", () => {
  assert.equal(
    chat.sanitizeUrl("https://api.gbif.org/v1/occurrence/123"),
    "https://api.gbif.org/v1/occurrence/123"
  );
  assert.equal(
    chat.sanitizeUrl("http://example.invalid/source"),
    "http://example.invalid/source"
  );
});

test("formatDisposition gives honest Korean labels for answer/abstain/clarify and marks them recognized", () => {
  const answer = chat.formatDisposition("answer");
  assert.equal(answer.label, "답변");
  assert.equal(answer.className, "disposition-answer");
  assert.equal(answer.recognized, true);

  const abstain = chat.formatDisposition("abstain");
  assert.equal(abstain.className, "disposition-abstain");
  assert.match(abstain.label, /근거/);
  assert.equal(abstain.recognized, true);

  const clarify = chat.formatDisposition("clarify");
  assert.equal(clarify.className, "disposition-clarify");
  assert.match(clarify.label, /확인/);
  assert.equal(clarify.recognized, true);
});

test("formatDisposition fails closed on any unrecognized disposition: never echoes the raw value, never marks it recognized", () => {
  const hostilePayloads = [
    "<script>alert(1)</script>",
    "success",
    "ANSWER",
    "answered",
    "",
    "   ",
    null,
    undefined,
    42,
    {},
    ["answer"],
  ];
  for (const payload of hostilePayloads) {
    const result = chat.formatDisposition(payload);
    assert.equal(result.recognized, false, "expected unrecognized disposition: " + JSON.stringify(payload));
    assert.equal(result.className, "disposition-unknown");
    assert.notEqual(
      result.label,
      payload,
      "the raw unrecognized disposition value must never be echoed back as the display label"
    );
    if (typeof payload === "string" && payload) {
      assert.equal(
        result.label.includes(payload),
        false,
        "the raw unrecognized disposition value must not appear inside the fallback label"
      );
    }
  }
});

test("formatBackendMode explains fixture, Neo4j, unavailable, and unsupported modes", () => {
  assert.match(chat.formatBackendMode("fixture"), /합성 데이터/);
  assert.match(chat.formatBackendMode("fixture"), /검색 미지원/);
  assert.match(chat.formatBackendMode("neo4j"), /그래프 DB/);
  assert.match(chat.formatBackendMode("future-mode"), /지원되지 않는 모드/);
  assert.match(chat.formatBackendMode(null), /확인 불가/);
});

test("sanitizeErrorMessage never leaks raw exception detail and stays specific per failure kind", () => {
  assert.match(chat.sanitizeErrorMessage({ kind: "network" }), /연결/);
  assert.match(chat.sanitizeErrorMessage({ kind: "http", status: 503 }), /일시적/);
  assert.match(chat.sanitizeErrorMessage({ kind: "http", status: 404 }), /찾을/);
  assert.match(chat.sanitizeErrorMessage({ kind: "http", status: 500 }), /서버 오류/);
  assert.equal(chat.sanitizeErrorMessage({}), "요청 처리 중 알 수 없는 오류가 발생했습니다.");

  const overlong = new Array(5000).fill("a").join("");
  const capped = chat.sanitizeErrorMessage({ kind: "http", status: 422, detail: overlong });
  assert.ok(capped.length < 400, "an overlong backend detail string must be capped before display");

  const withControlChars = "line-one" + String.fromCharCode(0) + String.fromCharCode(31) + "line-two";
  const cleaned = chat.sanitizeErrorMessage({ kind: "http", status: 422, detail: withControlChars });
  assert.equal(cleaned.includes(String.fromCharCode(0)), false);
  assert.equal(cleaned.includes(String.fromCharCode(31)), false);
});

test("sanitizeErrorMessage gives honest, distinct client/access/rate-limit messages for 400/401/403/429 instead of a generic server error", () => {
  const badRequest = chat.sanitizeErrorMessage({ kind: "http", status: 400 });
  const unauthorized = chat.sanitizeErrorMessage({ kind: "http", status: 401 });
  const forbidden = chat.sanitizeErrorMessage({ kind: "http", status: 403 });
  const rateLimited = chat.sanitizeErrorMessage({ kind: "http", status: 429 });

  for (const message of [badRequest, unauthorized, forbidden, rateLimited]) {
    assert.equal(message.includes("서버 오류"), false, 'must not fall back to the generic "server error" message: ' + message);
  }

  assert.match(unauthorized, /인증/);
  assert.match(forbidden, /권한/);
  assert.match(rateLimited, /많습니다|재시도|다시 시도/);

  // All four must be textually distinct from each other (and from 422/404/503/generic).
  const allMessages = [
    badRequest,
    unauthorized,
    forbidden,
    rateLimited,
    chat.sanitizeErrorMessage({ kind: "http", status: 422 }),
    chat.sanitizeErrorMessage({ kind: "http", status: 404 }),
    chat.sanitizeErrorMessage({ kind: "http", status: 503 }),
    chat.sanitizeErrorMessage({ kind: "http", status: 500 }),
  ];
  assert.equal(new Set(allMessages).size, allMessages.length, "each status must map to a distinct honest message");

  // A raw backend detail on a 400 is still capped/stripped, like 422.
  const overlong400 = chat.sanitizeErrorMessage({ kind: "http", status: 400, detail: new Array(5000).fill("a").join("") });
  assert.ok(overlong400.length < 400, "an overlong 400 detail string must be capped before display");
  const controlChars400 = chat.sanitizeErrorMessage({
    kind: "http",
    status: 400,
    detail: "x" + String.fromCharCode(0) + "y",
  });
  assert.equal(controlChars400.includes(String.fromCharCode(0)), false);
});

test('sanitizeErrorMessage exposes a distinct, safe "unsupported-response" message for fail-closed unknown dispositions', () => {
  const message = chat.sanitizeErrorMessage({ kind: "unsupported-response" });
  assert.equal(typeof message, "string");
  assert.ok(message.length > 0);
  assert.equal(message.includes("서버 오류"), false);
  assert.notEqual(message, chat.sanitizeErrorMessage({ kind: "network" }));
  assert.notEqual(message, chat.sanitizeErrorMessage({}));
});

test("index.html declares every required interactive control and accessibility label", () => {
  const requiredMarkers = [
    'id="chat-form"',
    'id="chat-intent"',
    'id="question-input"',
    'id="send-button"',
    'id="clear-button"',
    'id="history"',
    'id="backend-mode-value"',
    'id="status-region"',
    'id="spinner"',
    'id="prompt-chips"',
    'id="advanced-settings"',
    'id="profile-controls"',
    'id="profile-name"',
    'type="submit"',
    'type="button"',
  ];
  for (const marker of requiredMarkers) {
    assert.ok(htmlSource.includes(marker), "index.html is missing required marker: " + marker);
  }

  assert.ok(htmlSource.includes("Shift+Enter"), "must document the Shift+Enter newline behavior");
  assert.ok(htmlSource.includes("Enter"), "must document the Enter-to-submit behavior");
  assert.ok(htmlSource.includes('role="log"'), "conversation history must be an accessible log region");
  assert.ok(htmlSource.includes('role="status"'), "the progress/status region must be an accessible status region");
  assert.ok(htmlSource.includes('aria-live="polite"'), "dynamic regions must announce updates politely");
  assert.match(htmlSource, /id="observation-limit"[^>]*min="1"[^>]*max="10"/);
  assert.equal(htmlSource.includes("common-name"), false, "unsupported common-name observation filter must not be exposed");
});

test("index.html nests a welcoming empty state inside #history so the conversation log is never a blank rectangle before the first message", () => {
  const historyMatch = htmlSource.match(/<section[^>]*\sid="history"[\s\S]*?<\/section>/);
  assert.ok(historyMatch, "expected to locate the #history section");
  assert.ok(historyMatch[0].includes('id="history-empty-state"'), "the empty state must be nested inside #history, not bolted on elsewhere");
  assert.ok(historyMatch[0].includes("어떤 새가 궁금한가요?"), "expected the welcoming empty-state title");
  assert.match(historyMatch[0], /사진.*먹이.*서식/, "the empty-state hint must mention photos, diet, and habitat");
});

test("index.html carries a small brand mark and a footer free of backend/API implementation jargon", () => {
  assert.ok(htmlSource.includes("RobinGraph"), "expected a visible RobinGraph brand mark");
  const footerMatch = htmlSource.match(/<footer[^>]*>[\s\S]*?<\/footer>/);
  assert.ok(footerMatch, "expected an <footer> element");
  for (const jargon of ["/health", "/v1/chat", "/v1/search", "same-origin", "오리진", "fixture 모드"]) {
    assert.equal(footerMatch[0].includes(jargon), false, "footer must not expose implementation detail: " + jargon);
  }
});

test("index.html renders a single inline chat experience: no separate /birds tab or link, and route/filter controls are tucked behind a collapsed advanced disclosure", () => {
  assert.equal(htmlSource.includes("/birds"), false, "species info must render inline in chat, not link out to a separate /birds page");
  assert.match(htmlSource, /<details[^>]*\sid="advanced-settings"/, "route selection and typed filters must live inside a <details> disclosure");
  assert.doesNotMatch(
    htmlSource,
    /<details[^>]*\sid="advanced-settings"[^>]*\sopen(\s|>)/,
    "the advanced disclosure must be collapsed by default"
  );
  // The disclosure must actually contain the intent select and every filter
  // fieldset, not just coexist with them elsewhere on the page.
  const detailsMatch = htmlSource.match(/<details[^>]*\sid="advanced-settings"[\s\S]*?<\/details>/);
  assert.ok(detailsMatch, "expected to locate the advanced-settings <details> block");
  for (const marker of ['id="chat-intent"', 'id="profile-controls"', 'id="taxonomy-controls"', 'id="observations-controls"', 'id="evidence-controls"']) {
    assert.ok(detailsMatch[0].includes(marker), "advanced-settings disclosure is missing: " + marker);
  }
});

test("index.html exposes natural-language prompt chips that prefill real example questions", () => {
  const chipsMatch = htmlSource.match(/<[^>]*\sid="prompt-chips"[^>]*>[\s\S]*?<\/section>/);
  assert.ok(chipsMatch, "expected to locate the #prompt-chips container");
  const chipTags = Array.from(chipsMatch[0].matchAll(/<button[^>]*>/g)).map((m) => m[0]);
  assert.ok(chipTags.length >= 3, "expected at least 3 example prompt chips");

  const questionOf = (tag) => (tag.match(/data-question="([^"]+)"/) || [])[1];
  for (const tag of chipTags) {
    const question = questionOf(tag);
    assert.ok(question && question.trim().length > 0, "every chip must carry a non-blank example question");
  }
  const questions = chipTags.map(questionOf);
  // The two worked examples from the product brief must be reachable as chips.
  assert.ok(questions.includes("청둥오리에 대해 알고 싶어."));
  assert.ok(questions.includes("청둥오리 분류체계에 대해 알려줘."));

  // Only chips whose route is guaranteed by the product brief (profile,
  // taxonomy) may auto-send; every other example (invented for this UI,
  // not contract-guaranteed to auto-route) must stay prefill-only so the
  // chip never advertises a shortcut it cannot promise.
  const guaranteedQuestions = ["청둥오리에 대해 알고 싶어.", "청둥오리 분류체계에 대해 알려줘."];
  for (const tag of chipTags) {
    const question = questionOf(tag);
    const sendsImmediately = /data-send="true"/.test(tag);
    assert.equal(
      sendsImmediately,
      guaranteedQuestions.includes(question),
      'only the backend-guaranteed example questions may carry data-send="true": ' + question
    );
  }
});

test("index.html discloses optional Gemini generation and evidence limits", () => {
  assert.ok(htmlSource.includes("Gemini API"));
  assert.ok(htmlSource.includes("설정된 경우"));
  assert.ok(htmlSource.includes("조회된 근거"));
  assert.ok(htmlSource.includes("답변을 보류"));
});

test("index.html only references same-origin local assets, never a remote script/stylesheet", () => {
  const scriptSrcs = Array.from(htmlSource.matchAll(/<script[^>]*\ssrc="([^"]+)"/g)).map((m) => m[1]);
  const linkHrefs = Array.from(htmlSource.matchAll(/<link[^>]*\shref="([^"]+)"/g)).map((m) => m[1]);
  assert.ok(scriptSrcs.length > 0, "expected at least one <script src> in index.html");
  for (const reference of scriptSrcs.concat(linkHrefs)) {
    assert.equal(/^https?:\/\//i.test(reference), false, "asset reference must be same-origin/relative: " + reference);
    assert.equal(reference.startsWith("//"), false, "asset reference must not be protocol-relative: " + reference);
  }
  assert.deepEqual(scriptSrcs, ["/static/chat.js"]);
  assert.deepEqual(linkHrefs, ["/static/styles.css"]);
});

// ---------------------------------------------------------------------------
// WCAG 2.1 AA contrast (>=4.5:1) for the send button and the
// answer/abstain/clarify badges, computed from the actual declarations in
// styles.css rather than eyeballed -- both the light (:root) and dark
// (`@media (prefers-color-scheme: dark)`) themes are checked.
// ---------------------------------------------------------------------------

const cssSource = fs.readFileSync(path.join(STATIC_DIR, "styles.css"), "utf8");

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const full = clean.length === 3 ? clean.split("").map((c) => c + c).join("") : clean;
  const num = parseInt(full, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function srgbChannelToLinear(channel) {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function relativeLuminance(hex) {
  const [r, g, b] = hexToRgb(hex).map(srgbChannelToLinear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// WCAG 2.1 contrast ratio formula (Success Criterion 1.4.3).
function contrastRatio(hexA, hexB) {
  const lA = relativeLuminance(hexA);
  const lB = relativeLuminance(hexB);
  const lighter = Math.max(lA, lB);
  const darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}

function extractCustomProperties(block) {
  const props = {};
  const re = /(--[\w-]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = re.exec(block)) !== null) {
    props[match[1]] = match[2].trim();
  }
  return props;
}

// The light theme lives in the top-level `:root { ... }` block (no nested
// braces), and the dark theme only overrides the variables that change,
// inside `@media (prefers-color-scheme: dark) { :root { ... } }` -- matching
// real CSS cascade semantics, unset variables in the dark block fall back to
// the light block's value on the same effective :root selector.
const lightRootMatch = cssSource.match(/:root\s*\{([^}]*)\}/);
assert.ok(lightRootMatch, "expected to find a top-level :root block in styles.css");
const lightVars = extractCustomProperties(lightRootMatch[1]);

const darkRootMatch = cssSource.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}/);
assert.ok(darkRootMatch, "expected to find a dark-mode :root override block in styles.css");
const darkVars = Object.assign({}, lightVars, extractCustomProperties(darkRootMatch[1]));

// Resolves a CSS value like "var(--color-accent)" or a literal "#ffffff"
// against a theme's variable table, following one or more levels of var()
// indirection.
function resolveColor(rawValue, themeVars) {
  let value = rawValue.trim();
  const seen = new Set();
  while (value.startsWith("var(")) {
    const name = value.slice(4, -1).trim();
    assert.equal(seen.has(name), false, "circular var() reference for " + name);
    seen.add(name);
    assert.ok(
      Object.prototype.hasOwnProperty.call(themeVars, name),
      "no themed value found for custom property " + name
    );
    value = themeVars[name].trim();
  }
  assert.match(value, /^#[0-9a-fA-F]{3,6}$/, "expected a hex color literal, got: " + value);
  return value;
}

// Finds the declaration block belonging to the first `{ ... }` that follows
// `marker` in the CSS source -- tolerant of grouped selectors like
// ".disposition-abstain,\n.disposition-clarify { ... }" since `marker` only
// needs to locate a point before the shared block's opening brace.
function declarationBlockFor(marker) {
  const markerIndex = cssSource.indexOf(marker);
  assert.notEqual(markerIndex, -1, "expected to find CSS selector: " + marker);
  const braceStart = cssSource.indexOf("{", markerIndex);
  const braceEnd = cssSource.indexOf("}", braceStart);
  return cssSource.slice(braceStart + 1, braceEnd);
}

function propertyValue(block, property) {
  const re = new RegExp("(?:^|;)\\s*" + property + "\\s*:\\s*([^;]+);");
  const match = block.match(re);
  assert.ok(match, "expected property " + property + " in block: " + block);
  return match[1].trim();
}

const CONTRAST_PAIRS = [
  { name: ".send-button (light)", selector: ".send-button {", themeVars: lightVars },
  { name: ".send-button (dark)", selector: ".send-button {", themeVars: darkVars },
  { name: ".disposition-answer (light)", selector: ".disposition-answer {", themeVars: lightVars },
  { name: ".disposition-answer (dark)", selector: ".disposition-answer {", themeVars: darkVars },
  { name: ".disposition-abstain (light)", selector: ".disposition-abstain,", themeVars: lightVars },
  { name: ".disposition-abstain (dark)", selector: ".disposition-abstain,", themeVars: darkVars },
  { name: ".disposition-clarify (light)", selector: ".disposition-clarify {", themeVars: lightVars },
  { name: ".disposition-clarify (dark)", selector: ".disposition-clarify {", themeVars: darkVars },
];

for (const pair of CONTRAST_PAIRS) {
  test(
    "WCAG 2.1 AA: " + pair.name + " foreground/background contrast is >=4.5:1",
    () => {
      const block = declarationBlockFor(pair.selector);
      const fg = resolveColor(propertyValue(block, "color"), pair.themeVars);
      const bg = resolveColor(propertyValue(block, "background"), pair.themeVars);
      const ratio = contrastRatio(fg, bg);
      assert.ok(
        ratio >= 4.5,
        pair.name + ": contrast of " + fg + " on " + bg + " is " + ratio.toFixed(3) + ", need >=4.5"
      );
    }
  );
}

test("contrastRatio sanity check against known WCAG reference pairs", () => {
  // Black-on-white is the maximum possible ratio (21:1).
  assert.ok(Math.abs(contrastRatio("#000000", "#ffffff") - 21) < 0.01);
  // Identical colors have the minimum possible ratio (1:1).
  assert.ok(Math.abs(contrastRatio("#336699", "#336699") - 1) < 0.001);
});

// ---------------------------------------------------------------------------
// A minimal, dependency-free fake DOM sufficient to exercise chat.js's real
// keydown -> preventDefault -> form.requestSubmit() -> submit event code
// path (init()'s actual registered listeners), without any browser,
// headless browser, or jsdom-style package dependency.
// ---------------------------------------------------------------------------

function createFakeElement(tagName) {
  const listeners = Object.create(null);
  let text = "";
  const el = {
    tagName: tagName,
    children: [],
    attributes: Object.create(null),
    className: "",
    disabled: false,
    hidden: false,
    value: "",
    href: "",
    target: "",
    rel: "",
    scrollTop: 0,
    scrollHeight: 0,
    focusCalls: 0,
    focus() {
      this.focusCalls += 1;
    },
    addEventListener(type, handler) {
      (listeners[type] = listeners[type] || []).push(handler);
    },
    // Synchronously invokes every listener registered for `type` with
    // `eventLike`, auto-attaching a real preventDefault()/defaultPrevented
    // pair if the caller didn't supply one -- this is what lets a test drive
    // chat.js's actual `input.addEventListener("keydown", ...)` handler with
    // the same event shape a browser would deliver.
    dispatch(type, eventLike) {
      const event = eventLike || {};
      event.type = type;
      if (typeof event.preventDefault !== "function") {
        event.defaultPrevented = false;
        event.preventDefault = function () {
          event.defaultPrevented = true;
        };
      }
      (listeners[type] || []).slice().forEach((handler) => handler(event));
      return event;
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
    },
    appendChild(child) {
      if (child.parentNode) child.parentNode.removeChild(child);
      this.children.push(child);
      child.parentNode = this;
      return child;
    },
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index === -1) {
        throw new Error("NotFoundError: node is not a child");
      }
      this.children.splice(index, 1);
      child.parentNode = null;
      return child;
    },
    get firstChild() {
      return this.children.length > 0 ? this.children[0] : null;
    },
  };
  Object.defineProperty(el, "textContent", {
    get() {
      return text;
    },
    set(value) {
      text = value;
    },
    enumerable: true,
  });
  return el;
}

function createFakeDom(fetchImplementation) {
  const REQUIRED_IDS = [
    "chat-form",
    "question-input",
    "send-button",
    "clear-button",
    "history",
    "status-region",
    "spinner",
    "backend-mode-value",
    "chat-intent",
    "profile-controls",
    "taxonomy-controls",
    "observations-controls",
    "evidence-controls",
    "profile-name",
    "taxonomy-scientific-name",
    "taxonomy-name",
    "observation-taxon-key",
    "observation-scientific-name",
    "observation-place",
    "observation-from",
    "observation-to",
    "observation-limit",
    "evidence-limit",
    "prompt-chips",
    "history-empty-state",
  ];
  const elementsById = {};
  for (const id of REQUIRED_IDS) {
    elementsById[id] = createFakeElement(id === "chat-form" ? "form" : "div");
  }
  elementsById["chat-intent"].value = "auto";
  elementsById["observation-limit"].value = "10";
  elementsById["evidence-limit"].value = "10";
  // Mirror index.html: the empty state is static markup already nested
  // inside #history before chat.js ever runs.
  elementsById["history"].appendChild(elementsById["history-empty-state"]);
  // The real element is a <form>; give it a requestSubmit() that behaves
  // like the browser's -- synchronously dispatching a cancelable "submit"
  // event to whatever chat.js registered via form.addEventListener("submit", ...).
  elementsById["chat-form"].requestSubmit = function () {
    return elementsById["chat-form"].dispatch("submit", { cancelable: true });
  };

  const doc = {
    getElementById(id) {
      return elementsById[id];
    },
    createElement(tag) {
      return createFakeElement(tag);
    },
  };
  const fetchCalls = [];
  // loadHealth() fires during init(); the default pending, never-resolving
  // promise keeps it out of the way of synchronous tests without any real
  // network/browser fetch implementation. Async tests inject deterministic
  // responses through fetchImplementation.
  const win = {
    fetch(url, options) {
      fetchCalls.push({ url, options });
      return fetchImplementation ? fetchImplementation(url, options) : new Promise(() => {});
    },
  };
  return { doc, win, elementsById, fetchCalls };
}

function pressKey(dom, keyEventOverrides) {
  const input = dom.elementsById["question-input"];
  return input.dispatch(
    "keydown",
    Object.assign({ key: "Enter", shiftKey: false, isComposing: false }, keyEventOverrides)
  );
}

test("mode changes expose only the selected route controls", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  const intent = dom.elementsById["chat-intent"];

  assert.equal(dom.elementsById["profile-controls"].hidden, true);
  assert.equal(dom.elementsById["taxonomy-controls"].hidden, true);
  assert.equal(dom.elementsById["observations-controls"].hidden, true);
  assert.equal(dom.elementsById["evidence-controls"].hidden, true);

  for (const selected of ["profile", "taxonomy", "observations", "evidence", "auto"]) {
    intent.value = selected;
    intent.dispatch("change", {});
    assert.equal(dom.elementsById["profile-controls"].hidden, selected !== "profile");
    assert.equal(dom.elementsById["taxonomy-controls"].hidden, selected !== "taxonomy");
    assert.equal(dom.elementsById["observations-controls"].hidden, selected !== "observations");
    assert.equal(dom.elementsById["evidence-controls"].hidden, selected !== "evidence");
  }
});

test("buildChatPayload + selectedFilterValues contract: selecting the profile route and typing a name sends {kind:'profile', name}", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  dom.elementsById["chat-intent"].value = "profile";
  dom.elementsById["chat-intent"].dispatch("change", {});
  dom.elementsById["profile-name"].value = " 청둥오리 ";
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});

  assert.equal(dom.fetchCalls.length, 2, "expected /health plus /v1/chat");
  const chatCall = dom.fetchCalls[1];
  assert.deepEqual(JSON.parse(chatCall.options.body), {
    question: "청둥오리에 대해 알고 싶어.",
    intent: "profile",
    filters: { kind: "profile", name: "청둥오리" },
  });
});

test("a data-send=\"true\" prompt chip prefills the example question and submits it through the normal send path", () => {
  const dom = createFakeDom((url) => (url === "/health" ? Promise.resolve(jsonResponse({ mode: "fixture" })) : new Promise(() => {})));
  const chip = dom.doc.createElement("button");
  chip.setAttribute("data-question", "청둥오리에 대해 알고 싶어.");
  chip.setAttribute("data-send", "true");
  dom.elementsById["prompt-chips"].appendChild(chip);
  chat.init(dom.doc, dom.win);

  chip.dispatch("click", {});

  assert.equal(dom.elementsById["question-input"].value, "", "the question is cleared once submitted, like a manual send");
  assert.equal(messageRows(dom.elementsById["history"]).length, 1, "expected the user message to render");
  assert.equal(collectedText(dom.elementsById["history"]).includes("청둥오리에 대해 알고 싶어."), true);
  assert.deepEqual(dom.fetchCalls.map((call) => call.url), ["/health", "/v1/chat"]);
});

test("a prompt chip without data-send=\"true\" only prefills the question -- it never advertises a send it cannot guarantee", () => {
  const dom = createFakeDom((url) => (url === "/health" ? Promise.resolve(jsonResponse({ mode: "fixture" })) : new Promise(() => {})));
  const chip = dom.doc.createElement("button");
  chip.setAttribute("data-question", "최근 관찰된 청둥오리 기록을 보여줘.");
  dom.elementsById["prompt-chips"].appendChild(chip);
  chat.init(dom.doc, dom.win);

  chip.dispatch("click", {});

  assert.equal(dom.elementsById["question-input"].value, "최근 관찰된 청둥오리 기록을 보여줘.", "the question is filled in for the user to review");
  // Only the welcoming empty state occupies #history -- a prefill-only chip
  // must not add a user message of its own.
  assert.equal(messageRows(dom.elementsById["history"]).length, 0, "a prefill-only chip must not submit on its own");
  assert.deepEqual(dom.fetchCalls.map((call) => call.url), ["/health"], "no /v1/chat request without an explicit send");
});

test("prompt chips do nothing while a request is already in flight", () => {
  const dom = createFakeDom((url) => (url === "/health" ? Promise.resolve(jsonResponse({ mode: "fixture" })) : new Promise(() => {})));
  const chip = dom.doc.createElement("button");
  chip.setAttribute("data-question", "청둥오리에 대해 알고 싶어.");
  chip.setAttribute("data-send", "true");
  dom.elementsById["prompt-chips"].appendChild(chip);
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "이미 입력 중인 질문";
  pressKey(dom, {});
  assert.equal(messageRows(dom.elementsById["history"]).length, 1);

  chip.dispatch("click", {});

  assert.equal(messageRows(dom.elementsById["history"]).length, 1, "a chip click must not submit a second question while busy");
});

test("the welcoming empty state is visible at first load, removed once the first message arrives, and restored by 대화 지우기 (clear)", () => {
  const dom = createFakeDom();
  const emptyState = dom.elementsById["history-empty-state"];

  // Present before chat.js has done anything (mirrors a cold page load).
  assert.deepEqual(dom.elementsById["history"].children, [emptyState]);

  chat.init(dom.doc, dom.win);
  assert.deepEqual(dom.elementsById["history"].children, [emptyState], "init() alone must not touch the empty state");

  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});
  assert.equal(dom.elementsById["history"].children.includes(emptyState), false, "the empty state must be removed once a real message is sent");
  assert.ok(collectedText(dom.elementsById["history"]).includes("청둥오리에 대해 알고 싶어."));

  dom.elementsById["clear-button"].dispatch("click", {});
  assert.deepEqual(dom.elementsById["history"].children, [emptyState], "대화 지우기 must restore the exact same empty-state element, with no leftover messages");
});

test("real keydown event path: Enter (not composing, not shifted) prevents default and submits via form.requestSubmit(), then the submit handler renders the user message", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);

  let requestSubmitCalls = 0;
  const realRequestSubmit = dom.elementsById["chat-form"].requestSubmit;
  dom.elementsById["chat-form"].requestSubmit = function () {
    requestSubmitCalls += 1;
    return realRequestSubmit.call(this);
  };

  dom.elementsById["question-input"].value = "IME 없이 입력한 질문";
  const event = pressKey(dom, { isComposing: false, shiftKey: false });

  assert.equal(event.defaultPrevented, true, "Enter-to-submit must call preventDefault on the keydown event");
  assert.equal(requestSubmitCalls, 1, "expected form.requestSubmit() to be invoked exactly once");
  assert.equal(messageRows(dom.elementsById["history"]).length, 1, "expected the submit handler to render the user message");
  assert.equal(dom.elementsById["question-input"].value, "", "expected the input to be cleared after submit");
});

test("real keydown event path: Enter fired right after IME composition ends (isComposing: false) still submits (post-composition Enter is preserved)", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "한글 조합이 끝난 뒤 엔터";

  const event = pressKey(dom, { isComposing: false, shiftKey: false });

  assert.equal(event.defaultPrevented, true);
  assert.equal(messageRows(dom.elementsById["history"]).length, 1);
  assert.equal(dom.elementsById["question-input"].value, "");
});

test("real keydown event path: Enter while event.isComposing is true is ignored, leaving the in-progress IME composition alone", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "한글 조합 중";

  const event = pressKey(dom, { isComposing: true, shiftKey: false });

  assert.notEqual(event.defaultPrevented, true, "must not preventDefault while composing");
  // Only the welcoming empty state occupies #history -- nothing was submitted.
  assert.equal(messageRows(dom.elementsById["history"]).length, 0, "must not submit while composing");
  assert.equal(dom.elementsById["question-input"].value, "한글 조합 중", "input must be left untouched while composing");
});

test("real keydown event path: Shift+Enter never submits, regardless of composition state, so a newline is preserved", () => {
  for (const isComposing of [false, true]) {
    const dom = createFakeDom();
    chat.init(dom.doc, dom.win);
    dom.elementsById["question-input"].value = "여러 줄";

    const event = pressKey(dom, { isComposing: isComposing, shiftKey: true });

    assert.notEqual(
      event.defaultPrevented,
      true,
      "Shift+Enter must not preventDefault (isComposing=" + isComposing + "), so the textarea inserts a newline"
    );
    // Only the welcoming empty state occupies #history -- nothing was submitted.
    assert.equal(messageRows(dom.elementsById["history"]).length, 0);
    assert.equal(dom.elementsById["question-input"].value, "여러 줄");
  }
});

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json() {
      return Promise.resolve(payload);
    },
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

async function settleEventPath() {
  // Drain the fetch -> response.json -> result -> finally promise chain.
  await new Promise((resolve) => setImmediate(resolve));
}

function collectedText(node) {
  return [node.textContent || ""].concat(node.children.flatMap(collectedText)).join(" ");
}

// #history always holds the welcoming empty-state placeholder until the
// first real message arrives (see the dedicated empty-state test below), so
// a raw `history.children.length` is no longer "how many messages rendered"
// -- it conflates the placeholder with actual rows. Every test that cares
// about rendered conversation turns counts real `.message` rows instead,
// which stays correct regardless of whether the placeholder happens to be
// present.
function messageRows(historyEl) {
  return historyEl.children.filter((child) => (child.className || "").split(" ")[0] === "message");
}

test("real fetch calls use exact relative URLs and credentials omit", () => {
  const dom = createFakeDom((url) => {
    if (url === "/health") return Promise.resolve(jsonResponse({ mode: "fixture" }));
    return new Promise(() => {});
  });
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "credential boundary";
  pressKey(dom, {});

  assert.deepEqual(
    dom.fetchCalls.map((call) => call.url),
    ["/health", "/v1/chat"]
  );
  for (const call of dom.fetchCalls) {
    assert.equal(call.options.credentials, "omit", call.url + " must omit ambient cookies");
  }
  assert.equal(dom.fetchCalls[0].options.method, "GET");
  assert.equal(dom.fetchCalls[1].options.method, "POST");
});

test("hostile malformed 2xx payload fails closed through the actual event path without rendering attacker content", async () => {
  const attackerText = "<img src=x onerror=alert('attacker')> secret-provider-detail";
  const dom = createFakeDom((url) => Promise.resolve(
    url === "/health"
      ? jsonResponse({ mode: "fixture" })
      : jsonResponse({ disposition: attackerText, answer_text: attackerText, warnings: [attackerText] })
  ));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "safe user question";
  pressKey(dom, {});
  await settleEventPath();

  const rendered = collectedText(dom.elementsById["history"]);
  assert.match(rendered, /지원되지 않는 응답 형식/);
  assert.equal(rendered.includes(attackerText), false);
  assert.equal(rendered.includes("secret-provider-detail"), false);
  assert.equal(messageRows(dom.elementsById["history"]).length, 2, "user message plus fixed error only");
});

test("question focus is restored only after the request settles, and never while IME composition is active", async () => {
  const request = deferred();
  const dom = createFakeDom((url) => (
    url === "/health" ? Promise.resolve(jsonResponse({ mode: "fixture" })) : request.promise
  ));
  chat.init(dom.doc, dom.win);
  const input = dom.elementsById["question-input"];
  input.value = "focus after settle";
  pressKey(dom, {});
  assert.equal(input.disabled, true, "the request must own the busy state before focus is restored");
  assert.equal(input.focusCalls, 0, "must not steal focus while busy");

  input.dispatch("compositionstart", {});
  request.resolve(jsonResponse({ disposition: "answer", answer_text: "safe", warnings: [] }));
  await settleEventPath();
  assert.equal(input.disabled, false);
  assert.equal(input.focusCalls, 0, "must not focus an active IME composition");

  input.dispatch("compositionend", {});
  assert.equal(input.focusCalls, 0, "composition end alone must not cause an extra focus jump");

  const settled = createFakeDom((url) => Promise.resolve(
    url === "/health" ? jsonResponse({ mode: "fixture" }) : jsonResponse({ disposition: "answer", answer_text: "safe", warnings: [] })
  ));
  chat.init(settled.doc, settled.win);
  settled.elementsById["question-input"].value = "restore focus";
  pressKey(settled, {});
  assert.equal(settled.elementsById["question-input"].focusCalls, 0);
  await settleEventPath();
  assert.equal(settled.elementsById["question-input"].focusCalls, 1, "focus returns only after request completion");
});

// ---------------------------------------------------------------------------
// ChatSpeciesResult (`result.kind === "profile"`) rendering: the species
// card must show licensed photos with creator/credit/license links,
// sourced trait fact cards, the vegetation-coverage caveat, and lineage
// behind a collapsible <details> -- all built via createElement/textContent
// (see the HTML-injection-sink test above), with every photo src and link
// href independently validated before it is ever placed in the DOM.
// ---------------------------------------------------------------------------

function fakeProfilePayload(profileOverrides) {
  return {
    selected_intent: "profile",
    route_method: "semantic",
    disposition: "answer",
    answer_text: "청둥오리에 대한 정보를 확인했습니다.",
    warnings: [],
    result: {
      kind: "profile",
      profile: Object.assign(
        {
          taxon: {
            taxon_id: "t1",
            rank: "species",
            scientific_name: "Anas platyrhynchos",
            authority: "Linnaeus, 1758",
            korean_name: "청둥오리",
            korean_name_status: "community-sourced",
            korean_name_source_url: "https://www.wikidata.org/wiki/Q27141",
          },
          lineage: {
            query_scientific_name: "Anas platyrhynchos",
            taxonomy_source: "AviList",
            taxonomy_release: "v2025b",
            concept_set_id: "cs1",
            query_name: "청둥오리",
            resolved_query_scientific_name: "Anas platyrhynchos",
            matched_by: "korean_name",
            items: [
              {
                taxon_id: "g1",
                rank: "genus",
                scientific_name: "Anas",
                authority: null,
                korean_name: "오리속",
                korean_name_status: "community-sourced",
                korean_name_source_url: "https://www.wikidata.org/wiki/Q214264",
              },
              {
                taxon_id: "t1",
                rank: "species",
                scientific_name: "Anas platyrhynchos",
                authority: "Linnaeus, 1758",
                korean_name: "청둥오리",
                korean_name_status: "community-sourced",
                korean_name_source_url: null,
              },
            ],
          },
          traits: [
            {
              name: "body_mass",
              label: "체중",
              value: 1083.3,
              display: "1083.3",
              unit: "g",
              inferred: false,
              summary_statistic: "mean",
              source_url: "https://example.org/avonet",
              citation: "AVONET",
              dataset_id: "ds1",
              release: "r1",
              license_name: "CC BY 4.0",
              source_name: "AVONET",
            },
          ],
          images: [
            {
              image_url: "https://upload.wikimedia.org/wikipedia/commons/mallard.jpg",
              source_url: "https://commons.wikimedia.org/wiki/File:Mallard.jpg",
              creator: "<script>alert('creator')</script>",
              credit: "Some Credit",
              license_name: "CC BY-SA 4.0",
              license_url: "https://creativecommons.org/licenses/by-sa/4.0",
              title: "Mallard photo",
            },
            {
              image_url: "javascript:alert(1)",
              source_url: "https://commons.wikimedia.org/wiki/File:Bad.jpg",
              creator: "attacker",
              license_name: "CC0",
              license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
              title: "bad",
            },
            {
              image_url: "https://evil.example/not-wikimedia.jpg",
              source_url: "https://commons.wikimedia.org/wiki/File:AlsoBad.jpg",
              creator: "attacker2",
              license_name: "CC0",
              license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
              title: "also bad",
            },
          ],
          warnings: ["사진 제공처를 현재 조회할 수 없습니다."],
          vegetation_note: "구체적인 식물·식생 목록은 아직 수집되지 않았습니다.",
        },
        profileOverrides || {}
      ),
    },
  };
}

function collectAllNodes(node) {
  return [node].concat((node.children || []).flatMap(collectAllNodes));
}

test("renders a species profile card with validated photos, sourced trait fact cards, a vegetation caveat, and a collapsible lineage", async () => {
  const dom = createFakeDom((url) =>
    Promise.resolve(url === "/health" ? jsonResponse({ mode: "fixture" }) : jsonResponse(fakeProfilePayload()))
  );
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});
  await settleEventPath();

  const allNodes = collectAllNodes(dom.elementsById["history"]);
  const renderedText = collectedText(dom.elementsById["history"]);

  assert.ok(renderedText.includes("청둥오리"), "expected the Korean name to render");
  assert.ok(renderedText.includes("Anas platyrhynchos"), "expected the scientific name to render");

  // Exactly one of the three photos is on the https Wikimedia allow-list;
  // the javascript: URL and the non-Wikimedia host must both be dropped.
  const imgNodes = allNodes.filter((node) => node.tagName === "img");
  assert.equal(imgNodes.length, 1, "only the allow-listed Wikimedia photo may render an <img>");
  assert.equal(imgNodes[0].src, "https://upload.wikimedia.org/wikipedia/commons/mallard.jpg");

  // The hostile creator string must appear only as inert text (via
  // textContent), never as a parsed/executable node.
  assert.ok(renderedText.includes("<script>alert('creator')</script>"));
  assert.equal(allNodes.filter((node) => node.tagName === "script").length, 0);

  // No element may ever carry the rejected javascript: or non-allow-listed
  // image URLs as an href/src, even as inert text-only fallback links.
  for (const node of allNodes) {
    assert.notEqual(node.href, "javascript:alert(1)");
    assert.notEqual(node.src, "javascript:alert(1)");
    assert.notEqual(node.src, "https://evil.example/not-wikimedia.jpg");
  }

  // Licensed credit link for the surviving photo.
  assert.ok(allNodes.some((node) => node.tagName === "a" && node.textContent === "CC BY-SA 4.0" && node.href === "https://creativecommons.org/licenses/by-sa/4.0"));

  // Trait fact card with its own citation link.
  assert.ok(allNodes.some((node) => node.tagName === "strong" && node.textContent === "체중"));
  assert.ok(renderedText.includes("1083.3 g"));
  assert.ok(allNodes.some((node) => node.tagName === "a" && node.textContent === "AVONET" && node.href === "https://example.org/avonet"));

  // Vegetation-coverage caveat is surfaced verbatim.
  assert.ok(renderedText.includes("구체적인 식물·식생 목록은 아직 수집되지 않았습니다."));

  // The profile's own warnings (distinct from top-level chat warnings) render too.
  assert.ok(renderedText.includes("사진 제공처를 현재 조회할 수 없습니다."));

  // Lineage is tucked behind a collapsed-by-default <details>.
  const lineageDetails = allNodes.find((node) => node.tagName === "details" &&
    node.children.some(child => child.tagName === "summary" && child.textContent.includes("분류 계통 보기")));
  assert.ok(lineageDetails, "expected a <details> element for the collapsible lineage");
  assert.notEqual(lineageDetails.open, true, "lineage must be collapsed by default");
  const lineageSummary = lineageDetails.children.find((child) => child.tagName === "summary");
  assert.ok(lineageSummary && lineageSummary.textContent.includes("AviList") && lineageSummary.textContent.includes("v2025b"));
  assert.ok(renderedText.includes("오리속"));

  // Reference lineage source link (Wikidata) for the genus-level entry.
  assert.ok(allNodes.some((node) => node.tagName === "a" && node.href === "https://www.wikidata.org/wiki/Q214264"));
});

test("species profile card groups identical measurements from multiple sources into one fact with both citations, keeps diet/habitat and body mass visible, and collapses other measurements", async () => {
  const bodyMassAvonet = {
    name: "body_mass", label: "체중", value: 1083.3, display: "1083.3", unit: "g", inferred: false,
    source_url: "https://example.org/avonet", citation: "AVONET", license_name: "CC BY 4.0",
  };
  const bodyMassTraits = {
    name: "body_mass", label: "체중", value: 1083.3, display: "1083.3", unit: "g", inferred: false,
    source_url: "https://example.org/traits", citation: "EltonTraits", license_name: "CC0",
  };
  const habitatTrait = {
    name: "habitat", label: "서식 환경", value: "Wetland", display: "습지", unit: null, inferred: false,
    source_url: "https://example.org/avonet", citation: "AVONET", license_name: "CC BY 4.0",
  };
  const wingLength = {
    name: "wing_length", label: "접은 날개 길이", value: 254.1, display: "254.1", unit: "mm", inferred: false,
    source_url: "https://example.org/avonet", citation: "AVONET", license_name: "CC BY 4.0",
  };
  const tailLength = {
    name: "tail_length", label: "꼬리 길이", value: 92.3, display: "92.3", unit: "mm", inferred: true,
    source_url: "https://example.org/avonet", citation: "AVONET", license_name: "CC BY 4.0",
  };

  const dom = createFakeDom((url) =>
    Promise.resolve(
      url === "/health"
        ? jsonResponse({ mode: "fixture" })
        : jsonResponse(fakeProfilePayload({ traits: [bodyMassAvonet, bodyMassTraits, habitatTrait, wingLength, tailLength] }))
    )
  );
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});
  await settleEventPath();

  const allNodes = collectAllNodes(dom.elementsById["history"]);
  const renderedText = collectedText(dom.elementsById["history"]);

  // One body_mass fact card, but both citations survive.
  const bodyMassCards = allNodes.filter((node) => node.tagName === "strong" && node.textContent === "체중");
  assert.equal(bodyMassCards.length, 1, "identical body_mass claims from two sources must collapse into one fact card");
  assert.ok(allNodes.some((node) => node.tagName === "a" && node.textContent === "AVONET"));
  assert.ok(allNodes.some((node) => node.tagName === "a" && node.textContent === "EltonTraits"));

  // Diet/habitat and body mass are visible without opening any <details>.
  assert.ok(renderedText.includes("습지"));
  assert.ok(renderedText.includes("1083.3 g"));

  // Secondary measurements (wing/tail length) are real but tucked behind a
  // "측정값 더 보기" collapsible, not dumped into the main visible grid.
  const measurementsDetails = allNodes.find(
    (node) => node.tagName === "details" && node.children.some((c) => c.tagName === "summary" && c.textContent.includes("측정값 더 보기"))
  );
  assert.ok(measurementsDetails, "expected a collapsed 측정값 더 보기 details for secondary measurements");
  assert.notEqual(measurementsDetails.open, true, "secondary measurements must be collapsed by default");
  assert.ok(collectedText(measurementsDetails).includes("254.1 mm"));
  assert.ok(collectedText(measurementsDetails).includes("92.3 mm"));
  // Those secondary measurements must appear only inside the collapsed
  // section, never duplicated into the always-visible part of the card.
  const measurementsSubtree = new Set(collectAllNodes(measurementsDetails));
  const visibleText = allNodes
    .filter((node) => !measurementsSubtree.has(node))
    .map((node) => node.textContent || "")
    .join(" ");
  assert.equal(visibleText.includes("254.1 mm"), false, "wing length must not be duplicated outside the collapsed section");
});

test("species profile card renders the photo.credit attribution line alongside creator/license", async () => {
  const dom = createFakeDom((url) =>
    Promise.resolve(url === "/health" ? jsonResponse({ mode: "fixture" }) : jsonResponse(fakeProfilePayload()))
  );
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});
  await settleEventPath();

  assert.ok(collectedText(dom.elementsById["history"]).includes("Some Credit"), "expected photo.credit attribution text to render");
});

test("species profile card gives honest fallback text instead of rendering nothing when photos/traits are empty", async () => {
  const dom = createFakeDom((url) =>
    Promise.resolve(
      url === "/health" ? jsonResponse({ mode: "fixture" }) : jsonResponse(fakeProfilePayload({ images: [], traits: [], warnings: [] }))
    )
  );
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어.";
  pressKey(dom, {});
  await settleEventPath();

  const renderedText = collectedText(dom.elementsById["history"]);
  assert.ok(renderedText.includes("라이선스가 확인된 대표 사진이 없습니다."));
  assert.ok(renderedText.includes("조회된 형질"));
});

// ---------------------------------------------------------------------------
// Adversarial `detail` payloads: secrets, internal URLs/paths, control
// characters, and very long text must never reach the rendered message for
// 400/422 (or any other status) -- sanitizeErrorMessage's fixed, honest
// per-status Korean messages must not read `detail` at all.
// ---------------------------------------------------------------------------

const ADVERSARIAL_DETAILS = [
  "sk-live-51H8x2KcQzT9v3nF7bJmP0wXyZaB1cDeGhIjKlMnOpQrStUvWxYz",
  "AKIAIOSFODNN7EXAMPLESECRETACCESSKEY",
  "postgres://admin:hunter2@10.0.4.17:5432/robingraph_prod",
  "internal error at /var/lib/robingraph/data/neo4j-creds.json",
  "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
  "Traceback (most recent call last): File \"/opt/app/internal/auth.py\", line 42",
  "line-one" + String.fromCharCode(0) + String.fromCharCode(7) + String.fromCharCode(27) + "line-two",
  new Array(20000).fill("A").join(""),
];

for (const status of [400, 422]) {
  test(
    "sanitizeErrorMessage never surfaces adversarial detail payloads (secrets/internal URLs/paths/control chars/very long text) for status " +
      status,
    () => {
      const baseline = chat.sanitizeErrorMessage({ kind: "http", status: status });
      for (const detail of ADVERSARIAL_DETAILS) {
        const message = chat.sanitizeErrorMessage({ kind: "http", status: status, detail: detail });
        assert.equal(message, baseline, "the fixed message must not vary based on the supplied detail");
        assert.ok(message.length < 200, "message must stay short regardless of an adversarial detail payload");
        for (let i = 0; i < 32; i += 1) {
          if (i === 9 || i === 10 || i === 13) continue; // tab/LF/CR are allowed whitespace in general text
          assert.equal(
            message.includes(String.fromCharCode(i)),
            false,
            "message must not contain control character code " + i
          );
        }
        // Spot-check that none of the adversarial substrings leak through.
        assert.equal(message.includes("sk-live-"), false);
        assert.equal(message.includes("hunter2"), false);
        assert.equal(message.includes("169.254.169.254"), false);
        assert.equal(message.includes("/var/lib/robingraph"), false);
        assert.equal(message.includes("/opt/app/internal"), false);
        assert.equal(message.includes("AKIAIOSFODNN7EXAMPLE"), false);
      }
    }
  );
}

test("sanitizeErrorMessage: the http branch never reads context.detail for any recognized status", () => {
  const codeOnly = stripJsComments(jsSource);
  const fnMatch = codeOnly.match(/function sanitizeErrorMessage\(context\) \{[\s\S]*?\n {2}\}\n/);
  assert.ok(fnMatch, "expected to locate the sanitizeErrorMessage function body");
  assert.equal(
    fnMatch[0].includes("context.detail"),
    false,
    "sanitizeErrorMessage must not read context.detail anywhere -- fixed messages only"
  );
});

test("species popup opens from its trigger and closes only from close or outside the card", () => {
  const doc = { createElement: createFakeElement };
  const card = createFakeElement("div");
  const popup = chat.buildSpeciesPopup(doc, card, { taxon: { korean_name: "청둥오리" } });
  const [trigger, dialog] = popup.children;
  let opens = 0;
  let closes = 0;
  dialog.showModal = () => { opens += 1; };
  dialog.close = () => { closes += 1; };
  dialog.getBoundingClientRect = () => ({ left: 100, right: 500, top: 100, bottom: 700 });
  assert.equal(trigger.getAttribute("aria-haspopup"), "dialog");
  assert.equal(dialog.getAttribute("aria-label"), "청둥오리 도감 카드");
  trigger.dispatch("click");
  assert.equal(opens, 1);
  dialog.dispatch("click", { target: card, clientX: 200, clientY: 200 });
  dialog.dispatch("click", { target: dialog, clientX: 110, clientY: 110 });
  assert.equal(closes, 0, "clicks inside the card must preserve it");
  dialog.dispatch("click", { target: dialog, clientX: 20, clientY: 200 });
  assert.equal(closes, 1);
  dialog.children[0].dispatch("click");
  assert.equal(closes, 2);
  trigger.dispatch("click");
  assert.equal(opens, 2, "a closed card can be reopened");
});

test("card front contains compact facts; photo attribution and full trait sources are on the reversible back", () => {
  const profile = fakeProfilePayload().result.profile;
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const front = card.children.find(node => node.className === "species-card-front");
  const back = card.children.find(node => node.className === "species-card-back");
  const flip = collectAllNodes(card).find(node => node.className === "species-card-flip");
  assert.equal(back.hidden, true);
  assert.equal(front.hidden, false);
  assert.ok(collectedText(front).includes("1083.3 g"));
  assert.equal(collectAllNodes(front).some(node => node.tagName === "a"), false);
  assert.equal(collectAllNodes(front).filter(node => node.tagName === "dt").length, 1);
  assert.ok(collectedText(back).includes("Some Credit"));
  assert.ok(collectedText(back).includes("AVONET"));
  assert.ok(collectAllNodes(back).some(node => node.href === "https://creativecommons.org/licenses/by-sa/4.0"));
  flip.dispatch("click");
  assert.equal(back.hidden, false);
  assert.equal(front.hidden, true);
  assert.equal(flip.getAttribute("aria-pressed"), "true");
  flip.dispatch("click");
  assert.equal(front.hidden, false);
  assert.equal(back.hidden, true);
  flip.dispatch("click");
  card.showFront();
  assert.equal(front.hidden, false);
  assert.equal(back.hidden, true);
});

test("card flips at the edge, ignores repeated clicks, and cancels stale transitions on reset", () => {
  const doc = { createElement: createFakeElement, defaultView: { matchMedia: () => ({matches:false}) } };
  const card = chat.buildSpeciesCard(doc, fakeProfilePayload().result.profile);
  const front = card.children.find(node => node.className === "species-card-front");
  const back = card.children.find(node => node.className === "species-card-back");
  const flip = collectAllNodes(card).find(node => node.className === "species-card-flip");
  const animations = [];
  card.animate = (frames, options) => {
    const animation = {frames, options, cancelled:false, cancel() {this.cancelled=true;}};
    animations.push(animation); return animation;
  };
  flip.dispatch("click");
  assert.equal(back.hidden, true, "keep front visible until the card reaches its edge");
  flip.dispatch("click");
  assert.equal(animations.length, 1);
  animations[0].onfinish();
  assert.equal(back.hidden, false);
  assert.equal(front.hidden, true);
  assert.equal(animations[0].cancelled, true);
  assert.match(animations[1].frames[0].transform, /rotateY\(-90deg\)/);
  animations[1].onfinish();
  assert.equal(flip.disabled, false);
  flip.dispatch("click");
  const stale = animations[2].onfinish;
  card.showFront();
  stale();
  assert.equal(animations.length, 3, "a cancelled transition cannot resume after reopening");
  assert.equal(front.hidden, false);
  assert.equal(flip.disabled, false);
  doc.defaultView.matchMedia = () => ({matches:true});
  flip.dispatch("click");
  assert.equal(animations.length, 3, "reduced motion switches immediately");
  assert.equal(back.hidden, false);
});

test("consecutive questions send and render without clearing; clearing then restarting remains valid", async () => {
  const dom = createFakeDom((url) => Promise.resolve(jsonResponse(
    url === "/health" ? {mode:"fixture"} : fakeProfilePayload()
  )));
  chat.init(dom.doc, dom.win);
  for (const question of ["청둥오리에 대해 알고 싶어", "해오라기에 대해 알고 싶어", "참새에 대해 알고 싶어"]) {
    dom.elementsById["question-input"].value = question;
    pressKey(dom, {});
    await settleEventPath();
    assert.equal(dom.elementsById["question-input"].disabled, false);
  }
  assert.equal(dom.fetchCalls.filter(call => call.url === "/v1/chat").length, 3);
  assert.equal(messageRows(dom.elementsById["history"]).length, 6);
  dom.elementsById["clear-button"].dispatch("click");
  assert.equal(dom.elementsById["history-empty-state"].parentNode, dom.elementsById["history"]);
  dom.elementsById["question-input"].value = "다시 청둥오리에 대해 알고 싶어";
  pressKey(dom, {});
  await settleEventPath();
  assert.equal(dom.fetchCalls.filter(call => call.url === "/v1/chat").length, 4);
  assert.equal(messageRows(dom.elementsById["history"]).length, 2);
});

test("photo buttons move between validated images and sources start collapsed", () => {
  const profile = fakeProfilePayload().result.profile;
  profile.images = [profile.images[0], Object.assign({}, profile.images[0], {image_url: "https://upload.wikimedia.org/second.jpg", title: "두 번째 사진"})];
  const card = chat.buildSpeciesCard({createElement: createFakeElement}, profile);
  const all = collectAllNodes(card);
  const figures = all.filter(node => node.tagName === "figure");
  const previous = all.find(node => node.getAttribute("aria-label") === "이전 사진");
  const next = all.find(node => node.getAttribute("aria-label") === "다음 사진");
  const count = all.find(node => node.getAttribute("aria-live") === "polite");
  assert.deepEqual(figures.map(node => node.hidden), [false, true]);
  assert.equal(previous.disabled, true);
  assert.equal(count.textContent, "사진 1 / 2");
  next.dispatch("click");
  assert.deepEqual(figures.map(node => node.hidden), [true, false]);
  assert.equal(next.disabled, true);
  assert.equal(previous.disabled, false);
  assert.equal(count.textContent, "사진 2 / 2");
  previous.dispatch("click");
  assert.deepEqual(figures.map(node => node.hidden), [false, true]);
  for (const details of all.filter(node => ["species-photo-sources", "trait-source-toggle"].includes(node.className))) {
    assert.notEqual(details.open, true);
    assert.equal(details.children[0].tagName, "summary");
    assert.ok(collectedText(details).includes("CC"));
  }
});

// ---------------------------------------------------------------------------
// Habitat emblem + verified Red List palette.
// ---------------------------------------------------------------------------

const cssSourceForCards = fs.readFileSync(path.join(STATIC_DIR, "styles.css"), "utf8");
const HABITAT_VALUES = ["Forest", "Shrubland", "Woodland", "Grassland", "Rock", "Wetland", "Human Modified", "Coastal", "Marine", "Riverine", "Desert"];

function svgCapableDoc() {
  return {
    createElement: createFakeElement,
    createElementNS(namespace, tagName) {
      const el = createFakeElement(tagName);
      el.namespaceURI = namespace;
      return el;
    },
  };
}

function habitatProfile(value, conservation) {
  const profile = fakeProfilePayload().result.profile;
  profile.traits = profile.traits.concat(value === undefined ? [] : [{ name: "habitat", label: "서식 환경", value: value, display: value }]);
  if (conservation !== undefined) profile.conservation = conservation;
  return profile;
}

const VERIFIED_SOURCE = { source_name: "IUCN Red List", source_url: "https://www.iucnredlist.org/species/22680186", source_release: "2025-1" };

test("habitatEmblemInfo maps every raw AVONET habitat value to a distinct emblem and falls back to unknown", () => {
  const infos = HABITAT_VALUES.map((value) => chat.habitatEmblemInfo(habitatProfile(value)));
  assert.equal(new Set(infos.map((info) => info.slug)).size, HABITAT_VALUES.length);
  assert.equal(new Set(infos.map((info) => info.path)).size, HABITAT_VALUES.length);
  assert.equal(new Set(infos.map((info) => info.label)).size, HABITAT_VALUES.length);
  assert.ok(infos.every((info) => info.known && /[가-힣]/.test(info.label)));
  assert.equal(chat.habitatEmblemInfo(habitatProfile("Forest")).label, "숲");
  assert.equal(chat.habitatEmblemInfo(habitatProfile(" human modified ")).slug, "human-modified");
  for (const odd of [undefined, "Aquatic", "", 42, null, "<svg onload=x>"]) {
    const info = chat.habitatEmblemInfo(habitatProfile(odd));
    assert.equal(info.slug, "unknown", "expected unknown fallback for " + JSON.stringify(odd));
    assert.equal(info.known, false);
  }
  assert.equal(chat.habitatEmblemInfo(null).slug, "unknown");
});

test("the card's top-right emblem is an accessible SVG chosen by habitat, with a text fallback", () => {
  const card = chat.buildSpeciesCard(svgCapableDoc(), habitatProfile("Marine"));
  const emblem = collectAllNodes(card).find((node) => (node.className || "").startsWith("species-emblem"));
  assert.equal(emblem.className, "species-emblem habitat-marine");
  assert.equal(emblem.getAttribute("role"), "img");
  assert.equal(emblem.getAttribute("aria-label"), "서식 환경: 바다");
  const svg = emblem.children[0];
  assert.equal(svg.tagName, "svg");
  assert.match(svg.namespaceURI, /\/2000\/svg$/);
  assert.equal(svg.getAttribute("aria-hidden"), "true");
  assert.equal(svg.children[0].getAttribute("d"), chat.habitatEmblemInfo(habitatProfile("Marine")).path);

  const fallback = chat.buildSpeciesCard({ createElement: createFakeElement }, habitatProfile(undefined));
  const unknownEmblem = collectAllNodes(fallback).find((node) => (node.className || "").startsWith("species-emblem"));
  assert.equal(unknownEmblem.className, "species-emblem habitat-unknown");
  assert.equal(unknownEmblem.getAttribute("aria-label"), "서식 환경 미확인");
  assert.equal(unknownEmblem.children.length, 0);
  assert.ok(unknownEmblem.textContent.length > 0);
});

test("conservationInfo trusts only exact category codes with a source; DD/NE/unknown stay neutral", () => {
  const expected = { LC: ["관심대상", "lc"], NT: ["준위협", "nt"], VU: ["취약", "vu"], EN: ["위기", "en"], CR: ["위급", "cr"], EW: ["야생절멸", "ew"], EX: ["절멸", "ex"] };
  for (const [code, [label, tier]] of Object.entries(expected)) {
    const info = chat.conservationInfo(Object.assign({ category: code, label: "무시됨" }, VERIFIED_SOURCE));
    assert.deepEqual([info.label, info.tier, info.verified], [label, tier, true]);
    assert.equal(info.badgeText, "IUCN 적색목록 " + label + " (" + code + ")");
  }
  for (const [code, label] of [["DD", "정보부족"], ["NE", "미평가"]]) {
    const info = chat.conservationInfo(Object.assign({ category: code }, VERIFIED_SOURCE));
    assert.equal(info.tier, "unconfirmed");
    assert.equal(info.verified, false);
    assert.equal(info.badgeText, "IUCN 적색목록 " + label + " (" + code + ")");
  }
  for (const raw of ["CR (PE)", "CR (PEW)"]) {
    const info = chat.conservationInfo(Object.assign({ category: raw }, VERIFIED_SOURCE));
    assert.deepEqual([info.category, info.tier, info.badgeText], ["CR", "cr", "IUCN 적색목록 위급 (CR)"]);
  }
  const unconfirmedInputs = [
    { category: "CR (XX)", source_name: "IUCN" }, { category: "CR(PE)", source_name: "IUCN" },
    null, undefined, "EN", {}, { category: null }, { category: "en", source_name: "IUCN" },
    { category: ["EN"], source_name: "IUCN" }, { category: "toString", source_name: "IUCN" },
    { category: "CR" }, { category: "CR", source_name: "  " },
  ];
  for (const input of unconfirmedInputs) {
    const info = chat.conservationInfo(input);
    assert.equal(info.tier, "unconfirmed", JSON.stringify(input));
    assert.equal(info.category, null);
    assert.equal(info.badgeText, "멸종위기 등급 미확인");
  }
});

test("card, dialog, and chat button carry the verified tier; sources and the abundance caveat sit on the back", () => {
  const profile = habitatProfile("Wetland", Object.assign({ category: "EN", label: "위기" }, VERIFIED_SOURCE));
  const card = chat.buildSpeciesCard(svgCapableDoc(), profile);
  assert.equal(card.className, "species-card risk-en");
  const badge = card.children.find((node) => node.className === "species-conservation-badge");
  assert.equal(badge.textContent, "IUCN 적색목록 위기 (EN)");
  assert.match(badge.getAttribute("title"), /실제로 보기 드문지/);

  const front = card.children.find((node) => node.className === "species-card-front");
  const back = card.children.find((node) => node.className === "species-card-back");
  assert.equal(collectAllNodes(front).some((node) => node.tagName === "a"), false, "front stays link-free");
  const sources = collectAllNodes(back).find((node) => node.className === "species-conservation-sources");
  assert.equal(sources.tagName, "details");
  assert.notEqual(sources.open, true);
  assert.equal(sources.children[0].textContent, "멸종위기 등급 출처");
  assert.ok(collectAllNodes(sources).some((node) => node.tagName === "a" && node.textContent === "IUCN Red List" && node.href === VERIFIED_SOURCE.source_url && node.rel === "noopener noreferrer"));
  assert.ok(collectedText(sources).includes("릴리스 2025-1 기준"));
  assert.ok(collectedText(sources).includes("현재 최신 평가와 다를 수 있습니다"));
  assert.ok(collectedText(sources).includes("개체 수·관찰 빈도"));
  for (const node of collectAllNodes(card)) {
    assert.equal((node.textContent || "").includes("희귀"), false, "never label the species as rare");
  }

  const popup = chat.buildSpeciesPopup(svgCapableDoc(), card, profile);
  assert.equal(popup.children[0].className, "species-popup-trigger risk-en");
  assert.equal(popup.children[1].className, "species-popup risk-en");
});

test("hostile or unverified conservation data renders neutral, inert text", () => {
  const profile = habitatProfile("Forest", { category: "CR", label: "<b>x</b>", source_name: "evil", source_url: "javascript:alert(1)" });
  const card = chat.buildSpeciesCard(svgCapableDoc(), profile);
  assert.equal(card.className, "species-card risk-cr");
  const nodes = collectAllNodes(card);
  assert.equal(nodes.some((node) => node.href === "javascript:alert(1)"), false);
  assert.ok(nodes.some((node) => node.tagName === "span" && node.textContent === "evil"));
  assert.equal(collectedText(card).includes("<b>x</b>"), false, "backend label is never echoed");

  const neutral = chat.buildSpeciesCard(svgCapableDoc(), habitatProfile("Forest", { category: "DD", source_name: "IUCN" }));
  assert.equal(neutral.className, "species-card risk-unconfirmed");
  const missing = chat.buildSpeciesCard(svgCapableDoc(), habitatProfile("Forest"));
  assert.equal(missing.className, "species-card risk-unconfirmed");
  const missingSources = collectAllNodes(missing).find((node) => node.className === "species-conservation-sources");
  assert.ok(collectedText(missingSources).includes("중립"));
});

test("chat shows the summary answer, a brief habitat/Red List line, then the card button", async () => {
  const payload = fakeProfilePayload();
  payload.answer_text = "청둥오리는 습지에 사는 오리입니다.";
  payload.result.profile = habitatProfile("Wetland", Object.assign({ category: "LC", label: "관심대상" }, VERIFIED_SOURCE));
  payload.result.profile.summary = payload.answer_text;
  const dom = createFakeDom((url) => Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고 싶어";
  pressKey(dom, {});
  await settleEventPath();
  const answer = messageRows(dom.elementsById["history"])[1];
  const textIndex = answer.children.findIndex((node) => node.tagName === "p" && node.textContent === payload.answer_text);
  const briefIndex = answer.children.findIndex((node) => node.className === "species-chat-brief risk-lc");
  const popupIndex = answer.children.findIndex((node) => node.className === "species-popup-entry");
  assert.ok(textIndex !== -1 && textIndex < briefIndex && briefIndex < popupIndex);
  const brief = answer.children[briefIndex];
  assert.ok(collectedText(brief).includes("서식 환경: 습지"));
  assert.ok(collectedText(brief).includes("IUCN 적색목록 관심대상 (LC)"));
  assert.equal(brief.children[0].className, "species-emblem habitat-wetland");
  assert.match(answer.children[popupIndex].children[0].textContent, /도감 카드 보기/);
});

test("styles.css defines every habitat emblem, every risk tier, and a reduced-motion guard for foil", () => {
  for (const value of HABITAT_VALUES.concat(["unknown"])) {
    const slug = value === "unknown" ? "unknown" : chat.habitatEmblemInfo(habitatProfile(value)).slug;
    assert.match(cssSourceForCards, new RegExp("\\.species-emblem\\.habitat-" + slug + "\\s*\\{"));
  }
  for (const tier of ["unconfirmed", "nt", "vu", "en", "cr", "ew", "ex"]) {
    assert.match(cssSourceForCards, new RegExp("\\.species-popup\\.risk-" + tier + "[\\s,{]"));
    assert.match(cssSourceForCards, new RegExp("\\.species-card\\.risk-" + tier + "\\s*\\{"));
  }
  assert.match(cssSourceForCards, /prefers-reduced-motion: reduce\)\s*\{[^}]*risk-cr[^}]*animation: none/);
});

 test("possibly extinct source flags stay visible without changing the CR palette", () => {
  for (const [raw, label] of [["CR (PE)", "절멸 가능성"], ["CR (PEW)", "야생절멸 가능성"]]) {
    const info = chat.conservationInfo(Object.assign({ category: "CR", category_raw: raw }, VERIFIED_SOURCE));
    assert.equal(info.tier, "cr");
    assert.ok(info.badgeText.includes(label));
  }
});

test("structured species answers preserve sections, source attribution, unknown facts and inert hostile text", () => {
  const profile = { taxon: { korean_name: "청둥오리" }, sections: [
    { title: "외관 특징", items: [{ text: "성체 수컷의 머리는 녹색입니다.", source_name: "Wikipedia", source_url: "https://en.wikipedia.org/w/index.php?oldid=123", license_name: "CC BY-SA 4.0", license_url: "https://creativecommons.org/licenses/by-sa/4.0/" }] },
    { title: "재미있는 사실", items: [], empty_text: "출처를 아직 확인하지 못했습니다." },
    { title: "자료", items: [{ text: "<script>alert(1)</script>", source_name: "unsafe", source_url: "javascript:alert(1)" }] },
  ] };
  const answer = chat.buildSpeciesAnswer({ createElement: createFakeElement }, profile);
  const nodes = collectAllNodes(answer);
  assert.deepEqual(nodes.filter((n) => n.tagName === "h4").map((n) => n.textContent), ["외관 특징", "재미있는 사실", "자료"]);
  assert.ok(nodes.some((n) => n.textContent === "출처를 아직 확인하지 못했습니다."));
  assert.ok(nodes.some((n) => n.textContent === "<script>alert(1)</script>"));
  assert.equal(nodes.filter((n) => n.tagName === "script").length, 0);
  const sources = nodes.find((n) => n.className === "species-answer-sources");
  assert.equal(sources.open, undefined);
  assert.equal(nodes.filter((n) => n.tagName === "a").length, 2);
  assert.ok(nodes.filter((n) => n.tagName === "a").every((n) => n.href.startsWith("https://")));
  assert.equal(chat.buildSpeciesAnswer({ createElement: createFakeElement }, {}), null);
});

test("related explorer loads lazily, toggles, compares attributed values and rejects a changed taxonomy", async () => {
  const left = {taxon:{taxon_id:"mallard", scientific_name:"Anas platyrhynchos", korean_name:"청둥오리"},
    lineage:{concept_set_id:"active", taxonomy_release:"v2025b"}, traits:[], images:[]};
  const right = {taxon:{taxon_id:"peer", scientific_name:"Anas acuta", korean_name:"고방오리"},
    lineage:{concept_set_id:"active", taxonomy_release:"v2025b"}, traits:[
      {name:"habitat", display:"습지", source_name:"AVONET", source_url:"https://example.org/avonet", release:"v1"},
      {name:"diet_category", display:"invented", source_name:"bad", source_url:"javascript:bad"}], images:[]};
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({url,options});
    return {ok:true, json:async () => url.startsWith("/v1/taxa/related") ? {
      ...left.lineage, taxon:left.taxon, taxonomy_source:"AviList", note:"분류 관계",
      groups:[{rank:"genus",label:"같은 속의 새", ancestor:{scientific_name:"Anas"},
        items:[right.taxon,{taxon_id:"unknown",scientific_name:"Anas unknown",korean_name:null}], source_name:"AviList", source_url:"https://example.org/taxonomy"}]
    } : right};
  };
  const doc = {createElement:createFakeElement};
  const explorer = chat.buildRelatedExplorer(doc, left, fetcher);
  assert.equal(calls.length, 0);
  explorer.children[0].dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.credentials, "omit");
  explorer.children[0].dispatch("click");
  assert.equal(explorer.children[1].hidden, true);
  explorer.children[0].dispatch("click");
  assert.equal(calls.length, 1);
  assert.equal(collectAllNodes(explorer).some(n => n.getAttribute("aria-label") === "Anas unknown · 비교하기"), true);
  const choose = collectAllNodes(explorer).find(n => n.getAttribute("aria-label") === "고방오리 · 비교하기");
  choose.dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  let all = collectAllNodes(explorer);
  assert.ok(all.some(n => n.tagName === "table"));
  assert.ok(all.some(n => n.textContent === "습지"));
  assert.ok(all.some(n => n.textContent === "확인된 자료 없음"));
  assert.ok(!all.some(n => n.tagName === "td" && n.textContent.includes("invented")));
  assert.ok(all.some(n => n.tagName === "a" && n.href === "https://example.org/avonet"));
  right.lineage.taxonomy_release = "new";
  choose.dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  assert.match(explorer.children[1].children[0].textContent, /분류 자료가 갱신/);
});

test("related explorer can retry outages and refuses stale relationship responses", async () => {
  const profile = {taxon:{taxon_id:"t",scientific_name:"Bird name"}, lineage:{concept_set_id:"active",taxonomy_release:"v1"}};
  let calls = 0;
  const explorer = chat.buildRelatedExplorer({createElement:createFakeElement}, profile, async () => {
    calls++; return {ok:calls > 1, json:async () => ({taxon:profile.taxon,concept_set_id:"old",taxonomy_release:"v0",groups:[]})};
  });
  explorer.children[0].dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  assert.match(explorer.children[1].children[0].textContent, /再|재시도/);
  explorer.children[0].dispatch("click"); explorer.children[0].dispatch("click");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 2);
  assert.equal(collectAllNodes(explorer).filter(n => n.tagName === "h3").length, 0);
});

test("related exploration stays in the explanation and comparison, outside every species card", async () => {
  const payload = fakeProfilePayload();
  payload.result.profile.sections = [{title:"기본 정보",items:[{text:"청둥오리"}]}];
  const dom = createFakeDom(url => Promise.resolve(jsonResponse(url === "/health" ? {mode:"fixture"} : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리 알려줘";
  pressKey(dom, {});
  await settleEventPath();
  const answer = messageRows(dom.elementsById["history"])[1];
  const explanation = collectAllNodes(answer).find(n => n.className === "species-answer");
  assert.equal(answer.children.filter(n => n.className === "species-related").length, 1);
  const cards = collectAllNodes(answer).filter(n => n.className.startsWith("species-card risk-"));
  assert.equal(cards.length, 1);
  assert.equal(collectAllNodes(cards[0]).some(n => n.className === "species-related"), false);
  const comparison = chat.buildSpeciesComparison({createElement:createFakeElement}, payload.result.profile, payload.result.profile);
  assert.equal(comparison.children.filter(n => n.className === "species-related").length, 1);
  for (const card of collectAllNodes(comparison).filter(n => n.className.startsWith("species-card risk-"))) {
    assert.equal(collectAllNodes(card).some(n => n.className === "species-related"), false);
  }
});

test("species headings use Korean names first, then sourced English common names, retaining scientific identity", () => {
  const doc = {createElement:createFakeElement};
  const profile = {taxon:{scientific_name:"Anas albogularis",english_name:"Andaman Teal"},
    lineage:{items:[]},traits:[],images:[],sections:[{title:"기본 정보",items:[]}]};
  const card = chat.buildSpeciesCard(doc, profile);
  assert.equal(collectAllNodes(card).find(n => n.className === "species-title").textContent, "Andaman Teal");
  assert.equal(collectAllNodes(card).find(n => n.className === "species-scientific-name").textContent, "Anas albogularis");
  assert.equal(chat.buildSpeciesAnswer(doc, profile).children[0].textContent, "Andaman Teal");
  profile.taxon.korean_name = "한국어 이름";
  assert.equal(chat.buildSpeciesAnswer(doc, profile).children[0].textContent, "한국어 이름");
});

// ---------------------------------------------------------------------------
// Name / domestic-form relationships (`result.kind === "name_relations"` and
// the lazy GET /v1/taxa/name-relations explorer): rendered only in the
// explanation area, never inside a species card.
// ---------------------------------------------------------------------------

function fakeNameRelations(overrides) {
  return Object.assign({
    query_name: "오리",
    summary: "‘오리’는 여러 야생종과 가축형을 함께 가리키는 통칭입니다.",
    is_search_term: true,
    taxonomy_source: "AviList",
    taxonomy_release: "v2025b",
    concept_set_id: "cs1",
    relations: [
      { name: "집오리", entity_kind: "domestic_form", relation_type: "domestic_form_of", relation_label: "가축형의 기원종",
        note: "집오리는 청둥오리에서 가축화된 품종군입니다.",
        taxon: { scientific_name: "Anas platyrhynchos", korean_name: "청둥오리", english_name: "Mallard", taxon_id: "t1" },
        sources: [{ title: "Wikipedia: Domestic duck", url: "https://en.wikipedia.org/wiki/Domestic_duck" }] },
      { name: "흰뺨검둥오리", entity_kind: "species", relation_type: "common_name_member", relation_label: "통칭에 포함되는 야생종",
        note: "<img src=x onerror=alert(1)>",
        taxon: { scientific_name: "Anas zonorhyncha", korean_name: "흰뺨검둥오리", taxon_id: "t2" },
        sources: [{ title: "<script>bad()</script>", url: "javascript:alert(1)" }, { title: "Protocol-relative", url: "//evil.example/x" }] },
    ],
  }, overrides || {});
}

test("scientific-name relationship lookup displays Korean heading and omits duplicate English name", () => {
  const data = fakeNameRelations({ query_name: "Anas platyrhynchos", is_search_term: false });
  const section = chat.buildNameRelations({ createElement: createFakeElement }, data, async () => {});
  assert.equal(section.children[0].textContent, "‘청둥오리’ 이름 관계");
  assert.match(collectedText(section), /청둥오리 · Anas platyrhynchos/);
  assert.doesNotMatch(collectedText(section), /Mallard/);
});

function profileFor(taxon) {
  return fakeProfilePayload({ taxon: Object.assign({ rank: "species" }, taxon) }).result.profile;
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("name_relations chat result renders labelled, noted ambiguity choices in the explanation with explicit profile buttons", async () => {
  const payload = { disposition: "clarify", answer_text: "‘오리’는 하나의 종이 아닙니다. 어떤 새를 말씀하시는지 골라주세요.", warnings: [],
    result: { kind: "name_relations", relationships: fakeNameRelations() } };
  const dom = createFakeDom((url) => Promise.resolve(jsonResponse(
    url === "/health" ? { mode: "fixture" } : url === "/v1/chat" ? payload : profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" })
  )));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "오리 알려줘";
  pressKey(dom, {});
  await settleEventPath();
  const answer = messageRows(dom.elementsById["history"])[1];
  assert.match(collectedText(answer), /추가 확인 필요/);
  assert.ok(answer.children.some((n) => n.textContent === payload.answer_text));
  const nodes = collectAllNodes(answer);
  const items = nodes.filter((n) => /^name-relation( |$)/.test(n.className || ""));
  assert.equal(items.length, 2);
  assert.ok(nodes.some((n) => n.className === "name-relation-label" && n.textContent === "가축형의 기원종"));
  assert.ok(nodes.some((n) => n.textContent === "집오리는 청둥오리에서 가축화된 품종군입니다."));
  assert.ok(nodes.some((n) => n.textContent === "관련 야생종: 청둥오리 · Anas platyrhynchos"));
  const buttons = nodes.filter((n) => n.className === "name-relation-choose");
  assert.deepEqual(buttons.map((b) => b.textContent), ["청둥오리 · 관련 야생종 자료 보기", "흰뺨검둥오리 · 연결된 종 자료 보기"]);
  assert.equal(dom.fetchCalls.filter((c) => c.url.startsWith("/v1/taxa/")).length, 0, "choices must not prefetch profiles");

  buttons[0].dispatch("click");
  await tick();
  const profileCall = dom.fetchCalls.find((c) => c.url.startsWith("/v1/taxa/profile"));
  assert.equal(profileCall.url, "/v1/taxa/profile?name=Anas%20platyrhynchos");
  assert.equal(profileCall.options.credentials, "omit");
  const after = collectAllNodes(answer);
  const caveat = after.find((n) => n.className === "name-relation-caveat");
  assert.match(caveat.textContent, /‘오리’\(이\)라는 이름이 가리키는 범위 전체의 자료가 아니라/);
  assert.match(caveat.textContent, /관련 야생종 청둥오리/);
  const cards = after.filter((n) => (n.className || "").startsWith("species-card risk-"));
  assert.equal(cards.length, 1);
  const cardNodes = collectAllNodes(cards[0]);
  assert.equal(cardNodes.find((n) => n.className === "species-title").textContent, "청둥오리", "card keeps the wild species name, never the domestic/query name");
  assert.equal(cardNodes.some((n) => /name-relation|species-name-relations/.test(n.className || "")), false, "relations must stay outside the card");
  assert.equal(cardNodes.some((n) => /집오리|‘오리’/.test(n.textContent || "")), false);
});

test("domestic-form relations carry an explicit domestic/wild warning; ordinary relations do not", () => {
  const section = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations(), async () => { throw new Error("unused"); });
  const items = collectAllNodes(section).filter((n) => /^name-relation( |$)/.test(n.className || ""));
  assert.equal(items[0].className, "name-relation name-relation-domestic");
  assert.match(collectAllNodes(items[0]).find((n) => n.className === "name-relation-warning").textContent, /가축형과 야생 개체군의 정보를 구분합니다/);
  assert.equal(items[1].className, "name-relation");
  assert.equal(collectAllNodes(items[1]).some((n) => n.className === "name-relation-warning"), false);
  assert.ok(collectAllNodes(section).some((n) => /통칭의 사용 범위·가축형 관계를 구분해 확인합니다/.test(n.textContent)), "is_search_term note");
});

test("selecting a domestic relation appends the domestic caveat to the wild-species explanation", async () => {
  const section = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations(),
    async () => jsonResponse(profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" })));
  collectAllNodes(section).find((n) => n.className === "name-relation-choose").dispatch("click");
  await tick();
  const caveat = collectAllNodes(section).find((n) => n.className === "name-relation-caveat");
  assert.match(caveat.textContent, /‘가축형의 기원종’ 관계로/);
  assert.match(caveat.textContent, /가축형에 그대로 적용되지 않습니다/);
});

test("relation sources are sanitized: only http(s) hrefs become links and hostile text stays inert", () => {
  const section = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations(), null);
  const nodes = collectAllNodes(section);
  const links = nodes.filter((n) => n.tagName === "a");
  assert.deepEqual(links.map((n) => n.href), ["https://en.wikipedia.org/wiki/Domestic_duck"]);
  assert.equal(links[0].rel, "noopener noreferrer");
  const inert = nodes.find((n) => n.textContent === "<script>bad()</script>");
  assert.equal(inert.tagName, "span");
  assert.equal(inert.href, "");
  assert.ok(nodes.some((n) => n.tagName === "span" && n.textContent === "Protocol-relative"));
  assert.ok(nodes.some((n) => n.textContent === "<img src=x onerror=alert(1)>"));
  assert.equal(nodes.some((n) => n.tagName === "script" || n.tagName === "img"), false);
});

test("malformed name_relations payloads render a fixed fallback; empty relations say so honestly", async () => {
  assert.equal(chat.buildNameRelations({ createElement: createFakeElement }, { relations: "nope" }), null);
  assert.equal(chat.isNameRelationsPayload([]), false);
  const empty = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations({ relations: [] }));
  assert.ok(collectAllNodes(empty).some((n) => n.textContent === "출처가 확인된 통칭·가축형 관계가 없습니다."));
  const payload = { disposition: "clarify", answer_text: "확인 필요", warnings: [], result: { kind: "name_relations", relationships: { relations: null } } };
  const dom = createFakeDom((url) => Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "오리";
  pressKey(dom, {});
  await settleEventPath();
  assert.match(collectedText(messageRows(dom.elementsById["history"])[1]), /이름 관계 자료의 형식을 확인할 수 없어/);
});

test("candidate selection drops stale responses, ignores repeat clicks in flight, and rejects a mismatched taxon", async () => {
  const pending = {};
  const calls = [];
  const section = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations(), (url) => {
    calls.push(url);
    const d = deferred(); pending[url] = d; return d.promise;
  });
  const [first, second] = collectAllNodes(section).filter((n) => n.className === "name-relation-choose");
  first.dispatch("click"); first.dispatch("click");
  await tick();
  assert.equal(calls.length, 1, "repeat click on the in-flight candidate must not refetch");
  second.dispatch("click");
  await tick();
  assert.equal(calls.length, 2);
  pending["/v1/taxa/profile?name=Anas%20zonorhyncha"].resolve(jsonResponse(profileFor({ taxon_id: "t2", scientific_name: "Anas zonorhyncha", korean_name: "흰뺨검둥오리" })));
  await tick();
  pending["/v1/taxa/profile?name=Anas%20platyrhynchos"].resolve(jsonResponse(profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" })));
  await tick();
  const titles = collectAllNodes(section).filter((n) => n.className === "species-title").map((n) => n.textContent);
  assert.deepEqual(titles, ["흰뺨검둥오리"], "the older selection must never overwrite the newer one");

  const mismatch = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations(),
    async () => jsonResponse(profileFor({ taxon_id: "other", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" })));
  collectAllNodes(mismatch).find((n) => n.className === "name-relation-choose").dispatch("click");
  await tick();
  assert.equal(collectAllNodes(mismatch).some((n) => (n.className || "").startsWith("species-card")), false);
  assert.match(collectAllNodes(mismatch).find((n) => n.className === "name-relations-status").textContent, /분류 자료가 바뀌었습니다/);
});

test("species explanation offers a lazy 통칭·가축형 button outside the card that fetches by scientific name", async () => {
  const payload = fakeProfilePayload();
  payload.result.profile.sections = [{ title: "기본 정보", items: [{ text: "청둥오리" }] }];
  const relations = fakeNameRelations({ query_name: "Anas platyrhynchos", is_search_term: false });
  const dom = createFakeDom((url) => Promise.resolve(jsonResponse(
    url === "/health" ? { mode: "fixture" } : url === "/v1/chat" ? payload : relations
  )));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리 알려줘";
  pressKey(dom, {});
  await settleEventPath();
  const answer = messageRows(dom.elementsById["history"])[1];
  const explanation = collectAllNodes(answer).find((n) => n.className === "species-answer");
  assert.equal(answer.children.filter((n) => n.className === "species-related").length, 1, "same genus/family explorer is preserved");
  const extra = answer.children.find(n => n.className === "species-extra-info");
  assert.equal(extra.tagName, "details"); assert.ok(!extra.open);
  const explorer = extra.children.find((n) => n.className === "species-name-relations");
  assert.ok(explorer);
  const card = collectAllNodes(answer).find((n) => (n.className || "").startsWith("species-card risk-"));
  assert.equal(collectAllNodes(card).some((n) => n.className === "species-name-relations"), false);
  assert.equal(explorer.children[0].textContent, "통칭·가축형 관계 알아보기");
  assert.equal(dom.fetchCalls.filter((c) => c.url.startsWith("/v1/taxa/name-relations")).length, 0, "lazy until clicked");
  explorer.children[0].dispatch("click");
  explorer.children[0].dispatch("click"); explorer.children[0].dispatch("click");
  await tick();
  const calls = dom.fetchCalls.filter((c) => c.url.startsWith("/v1/taxa/name-relations"));
  assert.deepEqual(calls.map((c) => c.url), ["/v1/taxa/name-relations?name=Anas%20platyrhynchos"]);
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(collectAllNodes(explorer).filter((n) => /^name-relation( |$)/.test(n.className || "")).length, 2);
});

test("name-relations explorer explains a missing endpoint, retries, and rejects unsupported or stale payloads", async () => {
  const profile = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" });
  const responses = [jsonResponse({ detail: "secret-internal" }, 404), jsonResponse({ relations: "bad" }),
    jsonResponse(fakeNameRelations({ taxonomy_release: "old" })), jsonResponse(fakeNameRelations())];
  let calls = 0;
  const explorer = chat.buildNameRelationsExplorer({ createElement: createFakeElement }, profile, async () => responses[calls++]);
  const button = explorer.children[0];
  const status = () => explorer.children[1].children[0].textContent;
  button.dispatch("click"); await tick();
  assert.match(status(), /찾지 못했거나, 서버가 아직 이 조회를 지원하지 않습니다/);
  assert.equal(status().includes("secret-internal"), false);
  button.dispatch("click"); button.dispatch("click"); await tick();
  assert.match(status(), /지원되지 않는 응답 형식/);
  button.dispatch("click"); button.dispatch("click"); await tick();
  assert.match(status(), /분류 자료가 갱신/);
  assert.equal(collectAllNodes(explorer).some((n) => n.className === "name-relations"), false);
  button.dispatch("click"); button.dispatch("click"); await tick();
  assert.equal(calls, 4);
  assert.ok(collectAllNodes(explorer).some((n) => n.className === "name-relations"));

  const offline = chat.buildNameRelationsExplorer({ createElement: createFakeElement }, profile, async () => { throw new TypeError("Failed to fetch secret"); });
  offline.children[0].dispatch("click"); await tick();
  assert.match(offline.children[1].children[0].textContent, /불러오지 못했습니다/);
  assert.equal(offline.children[1].children[0].textContent.includes("secret"), false);
});

test("lookups that settle after 대화 지우기 never render into the cleared conversation", async () => {
  const payload = fakeProfilePayload();
  payload.result.profile.sections = [{ title: "기본 정보", items: [{ text: "청둥오리" }] }];
  const lookup = deferred();
  const dom = createFakeDom((url) => (
    url.startsWith("/v1/taxa/name-relations") ? lookup.promise : Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : payload))
  ));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리";
  pressKey(dom, {});
  await settleEventPath();
  const explorer = collectAllNodes(dom.elementsById["history"]).find((n) => n.className === "species-name-relations");
  explorer.children[0].dispatch("click");
  await tick();
  dom.elementsById["clear-button"].dispatch("click");
  lookup.resolve(jsonResponse(fakeNameRelations()));
  await tick();
  assert.equal(collectAllNodes(explorer).some((n) => n.className === "name-relations"), false);
  assert.equal(explorer.children[1].children[0].textContent, "통칭·가축형 관계를 조회하는 중입니다.");
  assert.equal(messageRows(dom.elementsById["history"]).length, 0);
});

test("styles.css styles the name-relation explanation, warnings and caveat", () => {
  const css = fs.readFileSync(path.join(STATIC_DIR, "styles.css"), "utf8");
  for (const selector of [".species-name-relations", ".name-relation-warning", ".name-relation-caveat", ".name-relation-label"]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.") + "[\\s,{]"));
  }
});

// ---------------------------------------------------------------------------
// RG-005: a same-genus/family peer comparison becomes its own assistant chat
// bubble; the original species explanation is never replaced.
// ---------------------------------------------------------------------------

const RG005_LINEAGE = { taxonomy_source: "AviList", taxonomy_release: "v2025b", concept_set_id: "cs1" };

function rg005Peer(taxonId, scientificName, koreanName, traitOverrides) {
  return {
    taxon: { taxon_id: taxonId, scientific_name: scientificName, korean_name: koreanName },
    lineage: Object.assign({ items: [] }, RG005_LINEAGE),
    traits: [Object.assign({ name: "habitat", label: "서식 환경", display: "습지", source_name: "AVONET",
      source_url: "https://example.org/avonet", release: "v1" }, traitOverrides || {})],
    images: [],
  };
}

function rg005Related() {
  return Object.assign({}, RG005_LINEAGE, {
    taxon: { taxon_id: "t1", scientific_name: "Anas platyrhynchos" },
    note: "분류 관계 안내", groups: [{
      rank: "genus", label: "같은 속의 새", ancestor: { scientific_name: "Anas", korean_name: "오리속" },
      source_name: "AviList", source_url: "https://example.org/avilist",
      items: [
        { taxon_id: "p1", scientific_name: "Anas acuta", korean_name: "고방오리" },
        { taxon_id: "p2", scientific_name: "Anas crecca", korean_name: "쇠오리" },
      ],
    }],
  });
}

async function rg005Start(peerResponder) {
  const payload = fakeProfilePayload();
  payload.result.profile.sections = [{ title: "기본 정보", items: [{ text: "청둥오리 설명" }] }];
  const dom = createFakeDom((url) => {
    if (url === "/health") return Promise.resolve(jsonResponse({ mode: "fixture" }));
    if (url === "/v1/chat") return Promise.resolve(jsonResponse(payload));
    if (url.startsWith("/v1/taxa/related")) return Promise.resolve(jsonResponse(rg005Related()));
    if (url.startsWith("/v1/taxa/profile")) return peerResponder(decodeURIComponent(url.split("name=")[1]));
    return Promise.resolve(jsonResponse({}, 404));
  });
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리 알려줘";
  pressKey(dom, {});
  await settleEventPath();
  const history = dom.elementsById["history"];
  const answer = messageRows(history)[1];
  const explorer = collectAllNodes(answer).find((n) => n.className === "species-related");
  explorer.children[0].dispatch("click");
  await tick();
  const peerButton = (name) => collectAllNodes(explorer).find((n) => n.tagName === "button" && n.getAttribute("aria-label") === name + " · 비교하기");
  const status = () => explorer.children[1].children[0].textContent;
  const bubbles = () => messageRows(history).filter((n) => n.className === "message message-answer message-comparison");
  return { dom, history, answer, explorer, peerButton, status, bubbles };
}

test("RG-005: a peer comparison is appended as a separate assistant bubble and the original explanation is preserved", async () => {
  const ctx = await rg005Start((name) => Promise.resolve(jsonResponse(rg005Peer("p1", name, "고방오리"))));
  const answerChildrenBefore = ctx.answer.children.slice();
  ctx.peerButton("고방오리").dispatch("click");
  await tick();
  const rows = messageRows(ctx.history);
  assert.equal(rows.length, 3, "user question, original answer, then a new comparison bubble");
  const bubble = ctx.bubbles()[0];
  assert.equal(rows[2], bubble);
  assert.deepEqual(ctx.answer.children, answerChildrenBefore, "the original answer bubble is not rewritten");
  assert.ok(collectAllNodes(ctx.answer).some((n) => n.className === "species-answer"));
  assert.equal(collectAllNodes(ctx.answer).some((n) => n.className === "species-comparison"), false, "no comparison inside the original explanation");
  const nodes = collectAllNodes(bubble);
  assert.equal(bubble.getAttribute("aria-label"), "청둥오리 · 고방오리 비교");
  assert.ok(nodes.some((n) => n.tagName === "th" && n.textContent === "청둥오리"));
  assert.ok(nodes.some((n) => n.tagName === "th" && n.textContent === "고방오리"));
  assert.ok(nodes.some((n) => n.tagName === "a" && n.href === "https://example.org/avonet"), "attributed trait source link");
  assert.ok(nodes.some((n) => n.className === "species-comparison-version" && n.textContent === "분류 기준: AviList · v2025b"));
  assert.ok(nodes.some((n) => n.className === "species-comparison-relation" && /오리속 \(속\)/.test(n.textContent)));
  const cardButtons = nodes.filter((n) => (n.className || "").startsWith("species-popup-trigger")).map((n) => n.textContent);
  assert.deepEqual(cardButtons, ["청둥오리 · 도감 카드 보기 ↗", "고방오리 · 도감 카드 보기 ↗"]);
  assert.match(ctx.status(), /새 답변으로 추가/);
});

test("RG-005: consecutive peer selections each add their own bubble; a repeated click while loading fetches once", async () => {
  const waits = {};
  const calls = [];
  const ctx = await rg005Start((name) => { calls.push(name); const d = deferred(); waits[name] = d; return d.promise; });
  const acuta = ctx.peerButton("고방오리");
  acuta.dispatch("click");
  acuta.dispatch("click");
  ctx.peerButton("쇠오리").dispatch("click");
  await tick();
  assert.deepEqual(calls, ["Anas acuta", "Anas crecca"]);
  assert.equal(acuta.disabled, true, "the loading peer button is disabled");
  waits["Anas acuta"].resolve(jsonResponse(rg005Peer("p1", "Anas acuta", "고방오리")));
  await tick();
  waits["Anas crecca"].resolve(jsonResponse(rg005Peer("p2", "Anas crecca", "쇠오리")));
  await tick();
  assert.deepEqual(ctx.bubbles().map((b) => b.getAttribute("aria-label")), ["청둥오리 · 고방오리 비교", "청둥오리 · 쇠오리 비교"]);
  assert.equal(acuta.disabled, false);
  acuta.dispatch("click");
  await tick();
  assert.equal(calls.length, 3, "a settled peer can be compared again");
  waits["Anas acuta"].resolve(jsonResponse(rg005Peer("p1", "Anas acuta", "고방오리")));
  await tick();
  assert.equal(ctx.bubbles().length, 3);
  assert.equal(messageRows(ctx.history).length, 5);
});

test("RG-005: a failed comparison shows a retry message without a bubble, and clicking again succeeds", async () => {
  let attempts = 0;
  const ctx = await rg005Start((name) => {
    attempts += 1;
    return Promise.resolve(attempts === 1 ? jsonResponse({ detail: "secret-internal" }, 503) : jsonResponse(rg005Peer("p1", name, "고방오리")));
  });
  ctx.peerButton("고방오리").dispatch("click");
  await tick();
  assert.equal(ctx.bubbles().length, 0);
  assert.match(ctx.status(), /고방오리 비교 자료를 불러오지 못했습니다\. 다시 눌러 재시도하세요/);
  assert.equal(ctx.status().includes("secret-internal"), false);
  assert.equal(ctx.peerButton("고방오리").disabled, false);
  ctx.peerButton("고방오리").dispatch("click");
  await tick();
  assert.equal(attempts, 2);
  assert.equal(ctx.bubbles().length, 1);
});

test("RG-005: changed taxonomy or a different taxon never becomes a comparison bubble", async () => {
  for (const peer of [
    Object.assign(rg005Peer("p1", "Anas acuta", "고방오리"), { lineage: Object.assign({}, RG005_LINEAGE, { taxonomy_release: "v2026a" }) }),
    rg005Peer("someone-else", "Anas acuta", "고방오리"),
  ]) {
    const ctx = await rg005Start(() => Promise.resolve(jsonResponse(peer)));
    ctx.peerButton("고방오리").dispatch("click");
    await tick();
    assert.equal(ctx.bubbles().length, 0);
    assert.match(ctx.status(), /분류 자료가 갱신된 경우/);
  }
});

test("RG-005: clearing the conversation before a comparison resolves drops the late response", async () => {
  const wait = deferred();
  const ctx = await rg005Start(() => wait.promise);
  const button = ctx.peerButton("고방오리");
  button.dispatch("click");
  await tick();
  ctx.dom.elementsById["clear-button"].dispatch("click");
  wait.resolve(jsonResponse(rg005Peer("p1", "Anas acuta", "고방오리")));
  await tick();
  assert.equal(messageRows(ctx.history).length, 0, "no bubble appears in the cleared conversation");
  assert.deepEqual(ctx.history.children, [ctx.dom.elementsById["history-empty-state"]]);
  assert.equal(button.disabled, false);
});

test("RG-005: comparison bubbles render hostile trait text inert and drop unsafe sources", async () => {
  const hostile = "<img src=x onerror=alert(1)>";
  const ctx = await rg005Start((name) => Promise.resolve(jsonResponse(Object.assign(rg005Peer("p1", name, "고방오리"), {
    traits: [
      { name: "habitat", display: hostile, source_name: "AVONET", source_url: "https://example.org/avonet" },
      { name: "diet_category", display: "invented", source_name: "bad", source_url: "javascript:alert(1)" },
    ],
  }))));
  ctx.peerButton("고방오리").dispatch("click");
  await tick();
  const nodes = collectAllNodes(ctx.bubbles()[0]);
  assert.ok(nodes.some((n) => n.textContent === hostile));
  const table = nodes.find((n) => n.className === "species-comparison-table");
  const tableNodes = collectAllNodes(table);
  assert.equal(tableNodes.some((n) => n.tagName === "img" || n.tagName === "script"), false);
  assert.equal(tableNodes.some((n) => n.tagName === "td" && n.textContent.includes("invented")), false);
  assert.ok(nodes.filter((n) => n.tagName === "a").every((n) => /^https:\/\//.test(n.href)));
  assert.equal(table.getAttribute("role"), "region");
  assert.equal(table.getAttribute("tabindex"), "0", "the wide table can be scrolled by keyboard on narrow screens");
});

test("RG-005: a comparison opened from inside a comparison bubble also becomes its own bubble", async () => {
  const ctx = await rg005Start((name) => Promise.resolve(jsonResponse(rg005Peer(name === "Anas acuta" ? "p1" : "p2", name, name === "Anas acuta" ? "고방오리" : "쇠오리"))));
  ctx.peerButton("고방오리").dispatch("click");
  await tick();
  const nested = collectAllNodes(ctx.bubbles()[0]).find((n) => n.className === "species-related");
  assert.ok(nested);
  const cards = collectAllNodes(ctx.bubbles()[0]).filter((n) => (n.className || "").startsWith("species-card risk-"));
  for (const card of cards) {
    assert.equal(collectAllNodes(card).some((n) => n.className === "species-related"), false, "explorers stay outside cards");
  }
});

// ---------------------------------------------------------------------------
// RG-008: feeding-ecology icons from sourced diet traits only.
// ---------------------------------------------------------------------------

const DIET_SOURCE = { source_name: "AVONET", source_url: "https://example.org/avonet", release: "v1", license_name: "CC BY 4.0" };
function dietProfile(traits) {
  return { taxon: { taxon_id: "h", scientific_name: "Ardea cinerea", korean_name: "왜가리" }, images: [],
    traits: [{ name: "habitat", value: "Wetland", display: "습지", ...DIET_SOURCE }].concat(traits) };
}
const dietKeys = (profile) => chat.dietIconInfo(profile).icons.map((icon) => icon.key);

test("RG-008: a sourced diet distribution yields one icon per positive member, sorted, with vertebrate subgroups merged", () => {
  const info = chat.dietIconInfo(dietProfile([{ name: "diet_distribution", label: "먹이 구성", ...DIET_SOURCE,
    value: { fish: 60, ectotherm_vertebrate: 20, endotherm_vertebrate: 10, invertebrate: 10, seed: 0, fruit: null, carrion: -5, nectar: Infinity, mystery_food: 40 } }]));
  assert.equal(info.basis, "distribution");
  assert.deepEqual(info.icons.map((i) => i.key), ["fish", "vertebrate", "invertebrate"], "왜가리 example: 물고기 + 척추동물 from sourced shares; 0/null/negative/unknown dropped");
  assert.deepEqual(info.icons.map((i) => i.text), ["먹이: 물고기 60%", "먹이: 척추동물 30%", "먹이: 무척추동물 10%"]);
});

test("RG-008: fish-only distribution adds a clearly labelled parent 척추동물 grouping; duplicate records are not summed", () => {
  const second = { ...DIET_SOURCE, source_name: "Second", source_url: "https://example.org/second" };
  const info = chat.dietIconInfo(dietProfile([
    { name: "diet_distribution", ...DIET_SOURCE, value: { fish: 100 } },
    { name: "diet_distribution", ...second, value: { fish: 100 } },
  ]));
  assert.deepEqual(info.icons.map((i) => i.key), ["fish", "vertebrate"]);
  assert.equal(info.icons[1].parentGroup, true);
  assert.equal(info.icons[1].text, "먹이: 척추동물 (상위 묶음 · 물고기 포함)");
  assert.equal(info.icons[0].text, "먹이: 물고기 100%", "two identical {fish:100} records stay 100%, never 200%");
  assert.deepEqual(info.sources.map((t) => t.source_name), ["AVONET"], "the first valid record is the single display basis");
  assert.equal(info.otherDistributionCount, 1);
});

test("RG-008: VertFishScav and Aquatic predator stay single broad icons and never imply fish", () => {
  assert.deepEqual(dietKeys(dietProfile([{ name: "diet_category", value: "VertFishScav", ...DIET_SOURCE }])), ["vert_fish_scav"]);
  const broad = chat.dietIconInfo(dietProfile([{ name: "diet_category", value: "VertFishScav", ...DIET_SOURCE }])).icons[0];
  assert.equal(broad.broad, true);
  assert.match(broad.text, /묶음 범주/);
  assert.deepEqual(dietKeys(dietProfile([{ name: "trophic_niche", value: "Aquatic predator", ...DIET_SOURCE }])), ["aquatic_predator"]);
  assert.deepEqual(dietKeys(dietProfile([
    { name: "diet_category", value: "VertFishScav", ...DIET_SOURCE },
    { name: "diet_distribution", value: { fish: 70, carrion: 30 }, ...DIET_SOURCE },
  ])), ["fish", "carrion", "vertebrate"], "a distribution supplies members and overrides the combined category");
});

test("RG-008: fallback order is diet_category then trophic_niche; unsourced, unknown and null values are excluded", () => {
  assert.deepEqual(dietKeys(dietProfile([
    { name: "trophic_niche", value: "Invertivore", ...DIET_SOURCE },
    { name: "diet_category", value: "Invertebrate", ...DIET_SOURCE },
    { name: "diet_category", value: "Invertebrate", ...DIET_SOURCE, source_name: "Other", source_url: "https://example.org/o" },
  ])), ["invertebrate"]);
  assert.deepEqual(dietKeys(dietProfile([{ name: "trophic_niche", value: "Frugivore", ...DIET_SOURCE }])), ["fruit"]);
  assert.deepEqual(dietKeys(dietProfile([
    { name: "diet_category", value: "NA", ...DIET_SOURCE },
    { name: "diet_category", value: null, ...DIET_SOURCE },
    { name: "trophic_niche", value: "Invertivore", source_name: "bad", source_url: "javascript:alert(1)" },
    { name: "diet_distribution", value: { fish: 50 }, source_name: "" , source_url: "https://example.org/x" },
  ])), []);
  assert.deepEqual(dietKeys(dietProfile([])), [], "habitat (Wetland) and the species name never imply a diet");
});

test("RG-008: card front and chat brief show accessible diet icons next to the habitat emblem; legend with sources on the back", async () => {
  const profile = dietProfile([{ name: "diet_distribution", label: "먹이 구성", ...DIET_SOURCE, value: { fish: 70, invertebrate: 30 } }]);
  profile.conservation = null;
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const heading = card.children.find((n) => n.className === "species-card-heading");
  assert.ok(heading.children.some((n) => n.className.startsWith("species-emblem habitat-wetland")), "habitat emblem retained");
  const front = card.children.find((n) => n.className === "species-card-front");
  const icons = collectAllNodes(front).find((n) => n.className === "species-diet-icons");
  assert.equal(icons.getAttribute("aria-label"), "먹이 아이콘 · 먹이 구성 비율");
  assert.deepEqual(icons.children.map((n) => n.className), ["diet-icon diet-fish", "diet-icon diet-invertebrate", "diet-icon diet-vertebrate diet-parent"]);
  assert.deepEqual(icons.children.map((n) => n.getAttribute("title")), ["먹이: 물고기 70%", "먹이: 무척추동물 30%", "먹이: 척추동물 (상위 묶음 · 물고기 포함)"]);
  assert.equal(icons.children[0].children[0].getAttribute("aria-hidden"), "true");
  const back = card.children.find((n) => n.className === "species-card-back");
  const legend = collectAllNodes(back).find((n) => n.className === "species-diet-legend");
  assert.ok(collectAllNodes(legend).some((n) => n.tagName === "a" && n.href === "https://example.org/avonet"));
  assert.ok(collectAllNodes(legend).some((n) => /서식지나 이름으로 먹이를 추정하지 않습니다/.test(n.textContent)));
  const brief = chat.buildSpeciesBrief({ createElement: createFakeElement }, profile);
  assert.equal(brief.children[0].className, "species-emblem habitat-wetland");
  assert.equal(brief.children.find((n) => n.className === "species-diet-icons").children.length, 3);
  const none = chat.buildSpeciesCard({ createElement: createFakeElement }, dietProfile([]));
  assert.equal(collectAllNodes(none).some((n) => n.className === "species-diet-icons" && n.parentNode.className === "species-card-front"), false);
  assert.match(collectAllNodes(none).find((n) => n.className === "species-diet-legend").children[1].textContent, /먹이 아이콘을 표시하지 않습니다/);
});

test("RG-008: diet icons use SVG when available and a glyph fallback otherwise", () => {
  const profile = dietProfile([{ name: "diet_category", value: "PlantSeed", ...DIET_SOURCE }]);
  const svgCard = chat.buildSpeciesCard(svgCapableDoc(), profile);
  const svgIcon = collectAllNodes(svgCard).find((n) => n.className === "diet-icon diet-plant-seed diet-broad");
  assert.equal(svgIcon.children[0].children[0].tagName, "svg");
  const plain = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const plainIcon = collectAllNodes(plain).find((n) => n.className === "diet-icon diet-plant-seed diet-broad");
  assert.equal(plainIcon.children[0].textContent, "▤");
});

test("RG-008: styles.css defines every diet icon class", () => {
  const css = fs.readFileSync(path.join(STATIC_DIR, "styles.css"), "utf8");
  for (const key of ["invertebrate", "vertebrate", "fish", "carrion", "fruit", "nectar", "seed", "plant", "vert-fish-scav", "plant-seed", "fruit-nectar", "omnivore", "aquatic-predator", "herbivore-aquatic", "herbivore-terrestrial"]) {
    assert.match(css, new RegExp("\\.diet-" + key + " \\{"), key);
  }
  assert.match(css, /\.species-diet-icons \{/);
});

test("RG-008: actual 왜가리 EltonTraits distribution shows 물고기, 척추동물 and 무척추동물 with sourced shares", () => {
  const info = chat.dietIconInfo(dietProfile([{ name: "diet_distribution", ...DIET_SOURCE, source_name: "EltonTraits",
    value: { invertebrate: 20, endotherm_vertebrate: 10, ectotherm_vertebrate: 10, fish: 60 } }]));
  assert.deepEqual(info.icons.map((i) => i.text).sort(), ["먹이: 무척추동물 20%", "먹이: 물고기 60%", "먹이: 척추동물 20%"]);
  assert.equal(info.icons[0].key, "fish");
  assert.equal(info.icons.some((i) => i.parentGroup), false, "real vertebrate shares exist, so no synthetic parent icon");
});

// ---------------------------------------------------------------------------
// RG-009: photo availability, broken images, and provider retry.
// ---------------------------------------------------------------------------

function photoProfile(overrides) {
  return Object.assign(fakeProfilePayload().result.profile, overrides || {});
}
const cardPart = (card, className) => card.children.find((n) => n.className === className);

test("RG-009: each no-photo status shows a generic placeholder with a fixed reason; facts and flip still work", () => {
  const expected = {
    no_licensed_photo: "사용 조건이 확인된 대표 사진을 아직 찾지 못했습니다.",
    unconfirmed_taxon: "사진 자료의 종 식별을 확인하지 못해 사진을 표시하지 않습니다.",
    ambiguous_taxon: "사진 자료가 여러 종 식별자에 연결되어 대표 사진을 선택하지 않았습니다.",
    provider_unavailable: "사진 제공처에 연결하지 못했습니다.",
  };
  for (const [status, message] of Object.entries(expected)) {
    const card = chat.buildSpeciesCard(svgCapableDoc(), photoProfile({ images: [], photo_availability: { status, message: "server text <b>x</b>" } }));
    const front = cardPart(card, "species-card-front");
    const back = cardPart(card, "species-card-back");
    const nodes = collectAllNodes(front);
    const placeholder = nodes.find((n) => n.className === "species-photo-placeholder");
    assert.equal(placeholder.getAttribute("role"), "img");
    assert.equal(placeholder.getAttribute("aria-label"), "사진 없음: " + message);
    assert.ok(nodes.some((n) => n.className === "species-photo-reason" && n.textContent === message));
    assert.equal(nodes.some((n) => n.tagName === "img" || n.tagName === "figure"), false, "never another species' photo");
    assert.equal(collectedText(card).includes("server text"), false, "server message is not echoed");
    assert.ok(collectedText(front).includes("1083.3 g"), "facts preserved without photos");
    assert.equal(nodes.some((n) => n.tagName === "a"), false);
    const flip = collectAllNodes(card).find((n) => n.className === "species-card-flip");
    flip.dispatch("click");
    assert.equal(back.hidden, false);
    assert.equal(front.hidden, true);
    card.showFront();
    assert.equal(front.hidden, false);
  }
});

test("RG-009: unknown status, missing status and all-unsafe photo URLs fall back to one honest generic reason", () => {
  for (const profile of [
    photoProfile({ images: [], photo_availability: { status: "weird", message: "<script>x</script>" } }),
    photoProfile({ images: [], photo_availability: undefined }),
    photoProfile({ images: [{ image_url: "javascript:alert(1)" }, { image_url: "https://evil.example/a.jpg" }], photo_availability: { status: "available" } }),
  ]) {
    const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
    const nodes = collectAllNodes(card);
    assert.ok(nodes.some((n) => n.className === "species-photo-reason" && n.textContent === "라이선스가 확인된 대표 사진이 없습니다."));
    assert.equal(nodes.some((n) => n.tagName === "img"), false);
    assert.equal(nodes.some((n) => n.className === "species-photo-retry"), false);
    assert.equal(collectedText(card).includes("<script>"), false);
  }
});

test("RG-009: a broken image shows a reload control that re-requests the same validated URL; attribution stays", () => {
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, photoProfile());
  const nodes = collectAllNodes(card);
  const img = nodes.find((n) => n.tagName === "img");
  const broken = nodes.find((n) => n.className === "species-photo-broken");
  const figure = nodes.find((n) => n.tagName === "figure");
  assert.equal(broken.hidden, true);
  img.dispatch("error");
  assert.equal(img.hidden, true);
  assert.equal(broken.hidden, false);
  assert.equal(figure.getAttribute("data-photo-state"), "error");
  assert.match(collectedText(broken), /사진을 불러오지 못했습니다/);
  img.src = "";
  broken.children.find((n) => n.className === "species-photo-reload").dispatch("click");
  assert.equal(img.src, "https://upload.wikimedia.org/wikipedia/commons/mallard.jpg");
  assert.equal(img.hidden, false);
  assert.equal(broken.hidden, true);
  img.dispatch("load");
  assert.equal(figure.getAttribute("data-photo-state"), "loaded");
  const back = cardPart(card, "species-card-back");
  assert.ok(collectAllNodes(back).some((n) => n.tagName === "a" && n.href === "https://creativecommons.org/licenses/by-sa/4.0"));
  assert.ok(collectedText(back).includes("Some Credit"));
});

test("RG-009: gallery navigation keeps working when every image is broken", () => {
  const base = fakeProfilePayload().result.profile.images[0];
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, photoProfile({
    images: [base, Object.assign({}, base, { image_url: "https://upload.wikimedia.org/two.jpg", title: "두 번째" }), base],
  }));
  const nodes = collectAllNodes(card);
  const figures = nodes.filter((n) => n.tagName === "figure");
  assert.equal(figures.length, 3, "duplicates are not removed by the UI; backend owns dedupe");
  figures.forEach((figure) => figure.children[0].dispatch("error"));
  const next = nodes.find((n) => n.getAttribute("aria-label") === "다음 사진");
  const count = nodes.find((n) => n.getAttribute("aria-live") === "polite");
  next.dispatch("click");
  assert.deepEqual(figures.map((f) => f.hidden), [true, false, true]);
  assert.equal(count.textContent, "사진 2 / 3");
  assert.equal(figures[1].children[1].hidden, false, "the visible broken photo offers its own reload");
  assert.equal(figures.every((f) => f.getAttribute("data-photo-state") === "error"), true);
});

test("RG-009: provider failure retry re-fetches the same species profile and only accepts a matching taxon and release", async () => {
  const calls = [];
  const fresh = photoProfile();
  const wait = deferred();
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, photoProfile({ images: [], photo_availability: { status: "provider_unavailable" } }), {
    fetcher: (url, options) => { calls.push({ url, options }); return wait.promise; },
  });
  const retry = collectAllNodes(card).find((n) => n.className === "species-photo-retry");
  retry.dispatch("click");
  retry.dispatch("click");
  await tick();
  assert.equal(calls.length, 1, "repeated clicks while loading do not refetch");
  assert.equal(calls[0].url, "/v1/taxa/profile?name=Anas%20platyrhynchos");
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(retry.disabled, true);
  wait.resolve(jsonResponse(fresh));
  await tick();
  const nodes = collectAllNodes(card);
  assert.equal(nodes.filter((n) => n.tagName === "img").length, 1);
  assert.equal(nodes.some((n) => n.className === "species-photo-placeholder"), false);
  assert.ok(collectAllNodes(cardPart(card, "species-card-back")).some((n) => n.className === "species-photo-sources"));
  const flip = nodes.find((n) => n.className === "species-card-flip");
  flip.dispatch("click");
  assert.equal(cardPart(card, "species-card-back").hidden, false);
});

test("RG-009: retry never substitutes a different taxon, survives errors, and falls back to guidance without a transport", async () => {
  const other = photoProfile();
  other.taxon = Object.assign({}, other.taxon, { taxon_id: "different" });
  let mode = "mismatch";
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, photoProfile({ images: [], photo_availability: { status: "provider_unavailable" } }), {
    fetcher: async () => (mode === "mismatch" ? jsonResponse(other) : jsonResponse({ detail: "secret" }, 503)),
  });
  const retry = collectAllNodes(card).find((n) => n.className === "species-photo-retry");
  const status = () => collectAllNodes(card).find((n) => n.className === "species-note" && n.getAttribute("role") === "status").textContent;
  retry.dispatch("click");
  await tick();
  assert.equal(collectAllNodes(card).some((n) => n.tagName === "img"), false);
  assert.match(status(), /분류 자료가 바뀌어 사진을 갱신하지 않았습니다/);
  mode = "error";
  retry.dispatch("click");
  await tick();
  assert.match(status(), /잠시 후 다시 시도하세요/);
  assert.equal(status().includes("secret"), false);
  assert.equal(retry.disabled, false);
  const offline = chat.buildSpeciesCard({ createElement: createFakeElement }, photoProfile({ images: [], photo_availability: { status: "provider_unavailable" } }));
  assert.equal(collectAllNodes(offline).some((n) => n.className === "species-photo-retry"), false);
  assert.ok(collectedText(offline).includes("같은 질문을 다시 보내면"));
});

test("RG-009: in chat, a provider-failure answer keeps its explanation, and a retry that settles after clearing is dropped", async () => {
  const payload = fakeProfilePayload({ images: [], photo_availability: { status: "provider_unavailable" } });
  payload.result.profile.sections = [{ title: "기본 정보", items: [{ text: "청둥오리 설명" }] }];
  const wait = deferred();
  const dom = createFakeDom((url) => url.startsWith("/v1/taxa/profile") ? wait.promise
    : Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리 알려줘";
  pressKey(dom, {});
  await settleEventPath();
  const answer = messageRows(dom.elementsById["history"])[1];
  assert.ok(collectAllNodes(answer).some((n) => n.className === "species-answer"));
  const card = collectAllNodes(answer).find((n) => (n.className || "").startsWith("species-card risk-"));
  const retry = collectAllNodes(card).find((n) => n.className === "species-photo-retry");
  retry.dispatch("click");
  await tick();
  dom.elementsById["clear-button"].dispatch("click");
  wait.resolve(jsonResponse(fakeProfilePayload().result.profile));
  await tick();
  assert.equal(collectAllNodes(card).some((n) => n.tagName === "img"), false, "late retry result is not rendered after clear");
  assert.equal(retry.disabled, false);
});

test("RG-009: styles.css styles the placeholder, broken-image and retry states", () => {
  const css = fs.readFileSync(path.join(STATIC_DIR, "styles.css"), "utf8");
  for (const selector of [".species-photo-placeholder", ".species-photo-broken", ".species-photo-reload", ".species-photo-retry"]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.") + "[\\s,{]"));
  }
});

test("RG-008 fix: conflicting distribution records are never fused; the first valid sourced record is the basis", () => {
  const other = { ...DIET_SOURCE, source_name: "Other dataset", source_url: "https://example.org/other" };
  const profile = dietProfile([
    { name: "diet_distribution", ...DIET_SOURCE, source_url: "javascript:alert(1)", value: { seed: 100 } },
    { name: "diet_distribution", ...DIET_SOURCE, value: { mystery: 50, fish: 0 } },
    { name: "diet_distribution", label: "먹이 구성", ...DIET_SOURCE, value: { fish: 60, ectotherm_vertebrate: 10, endotherm_vertebrate: 10, invertebrate: 20 } },
    { name: "diet_distribution", label: "먹이 구성", ...other, value: { invertebrate: 70, seed: 30 } },
  ]);
  const info = chat.dietIconInfo(profile);
  assert.equal(info.basis, "distribution");
  assert.deepEqual(info.icons.map((i) => i.text), ["먹이: 물고기 60%", "먹이: 척추동물 20%", "먹이: 무척추동물 20%"],
    "vertebrate subgroups aggregate inside the chosen record only; seed from the other source is not added");
  assert.deepEqual(info.sources.map((t) => t.source_url), ["https://example.org/avonet"]);
  assert.equal(info.otherDistributionCount, 1);
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const legend = collectAllNodes(card).find((n) => n.className === "species-diet-legend");
  assert.match(legend.children[1].textContent, /서로 다른 자료의 비율을 더하지 않습니다/);
  assert.deepEqual(collectAllNodes(legend).filter((n) => n.tagName === "a").map((n) => n.href), ["https://example.org/avonet"]);
  const back = card.children.find((n) => n.className === "species-card-back");
  assert.ok(collectAllNodes(back).some((n) => n.tagName === "a" && n.href === "https://example.org/other"), "the other record's source stays in the trait panel");
});

// ---------------------------------------------------------------------------
// RG-006 follow-up: reviewed activity pattern with raw source claims kept as provenance.
// ---------------------------------------------------------------------------

function nightHeronProfile() {
  const profile = fakeProfilePayload().result.profile;
  profile.taxon = { taxon_id: "nn", scientific_name: "Nycticorax nycticorax", korean_name: "해오라기" };
  profile.traits = [{
    name: "activity_pattern", label: "활동 시간", value: true,
    display: "야행성", unit: null, inferred: false,
    source_name: "Cornell Lab of Ornithology · Black-crowned Night Heron Life History",
    source_url: "https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory",
    citation: "Cornell Lab of Ornithology, Life History · Food", license_name: "출처 기반 독자 요약 · 원문 미재배포",
    review_note: "활동 시간은 별도 출처를 검토해 설명했습니다. 원자료의 야행성 코드와 출처는 검토 기록에 보존합니다.",
    source_claims: [{ name: "nocturnal", label: "야행성", value: false, display: "아니요", source_name: "AVONET",
      source_url: "https://example.org/avonet-nocturnal", release: "v1", license_name: "CC BY 4.0", citation: "AVONET" },
      { name: "hostile", value: { nested: true } }],
  }];
  return profile;
}

test("RG-006 follow-up: reviewed activity stays visible; the raw nocturnal=false claim is only collapsed provenance", () => {
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, nightHeronProfile());
  const back = card.children.find((n) => n.className === "species-card-back");
  const traitCards = collectAllNodes(back).filter((n) => n.className === "trait-card");
  const activity = traitCards.find((n) => n.children[0].textContent === "활동 시간");
  assert.ok(activity, "activity_pattern is a prominent trait, not hidden under 측정값 더 보기");
  assert.equal(collectAllNodes(back).some((n) => n.className === "card-details" && collectAllNodes(n).includes(activity)), false);
  assert.equal(activity.children[1].textContent, "야행성");
  const details = activity.children.find((n) => n.className === "trait-source-toggle");
  assert.notEqual(details.open, true, "provenance starts collapsed");
  assert.ok(collectAllNodes(details).some((n) => n.className === "trait-review-note" && /원자료의 야행성 코드/.test(n.textContent)));
  const claims = collectAllNodes(details).filter((n) => n.className === "trait-source-claim");
  assert.equal(claims.length, 1, "non-scalar claims are skipped");
  assert.match(claims[0].children[0].textContent, /^원자료 분류값 \(현재 결론 아님\): nocturnal = false/);
  assert.ok(collectAllNodes(claims[0]).some((n) => n.tagName === "a" && n.href === "https://example.org/avonet-nocturnal"));
  assert.ok(collectAllNodes(details).some((n) => n.tagName === "a" && n.href === "https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory"));
  assert.equal(collectAllNodes(card).some((n) => n.textContent === "아니요" || /야행성.*아니요|아니요.*야행성/.test(n.textContent || "")), false,
    "the raw 아니요 is never rendered as a current verdict");
});

test("RG-006 follow-up: unsafe claim source URLs render as inert text", () => {
  const profile = nightHeronProfile();
  profile.traits[0].source_claims[0].source_url = "javascript:alert(1)";
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const claim = collectAllNodes(card).find((n) => n.className === "trait-source-claim");
  assert.equal(collectAllNodes(claim).some((n) => n.tagName === "a"), false);
  assert.ok(collectAllNodes(claim).some((n) => n.tagName === "span" && n.textContent === "AVONET"));
});

test("single common-name graph target automatically loads a closed card; multiple targets require choice", async () => {
  const relation = fakeNameRelations().relations[1];
  let requests = 0;
  const single = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations({ relations: [relation] }), async () => {
    requests++;
    return jsonResponse(profileFor(relation.taxon));
  });
  await tick();
  assert.equal(requests, 1);
  assert.ok(collectAllNodes(single).some(n => /^species-chat-brief /.test(n.className || "")));
  assert.match(collectedText(single), /그래프에서 연결된/);
  assert.equal(collectAllNodes(single).some(n => n.tagName === "dialog" && n.open), false);
  const second = Object.assign({}, relation, { taxon: { taxon_id: "other", scientific_name: "Other species" } });
  chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations({ relations: [relation, second] }), async () => { requests++; });
  await tick();
  assert.equal(requests, 1, "never arbitrarily choose between graph targets");
});

test("subspecies references retain parent provenance without becoming own stats, habitat, photos or risk", () => {
  const parent = { scientific_name: "Anas platyrhynchos", taxon_id: "t1", rank: "species" };
  const profile = profileFor({ scientific_name: "Anas platyrhynchos test", taxon_id: "sub1", rank: "subspecies" });
  profile.traits = [];
  profile.images = [];
  profile.conservation = { code: "unknown" };
  profile.parent_species = { taxon: parent };
  profile.reference_traits = [{ name: "body_mass", label: "체중", display: "999", unit: "g", reference_scope: "species", reference_taxon: parent }];
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const nodes = collectAllNodes(card);
  assert.equal(nodes.find(n => n.className === "species-category").textContent, "아종");
  assert.match(nodes.find(n => n.className === "species-parent").textContent, /소속 종: Anas platyrhynchos/);
  const reference = nodes.find(n => n.className === "card-details species-reference");
  assert.equal(reference.tagName, "details");
  assert.match(collectedText(reference), /종 수준 참고 정보/);
  assert.match(collectedText(reference), /Anas platyrhynchos/);
  assert.equal(collectedText(nodes.find(n => n.className === "species-quick-facts")).includes("999"), false);
  assert.equal(card.getAttribute("data-conservation-tier"), "unconfirmed");
  assert.equal(nodes.some(n => n.tagName === "img"), false);
});

test("automatic common-name profile settling after clear is discarded", async () => {
  const pending = deferred();
  let active = true;
  const relation = fakeNameRelations().relations[1];
  const section = chat.buildNameRelations({ createElement: createFakeElement }, fakeNameRelations({ relations: [relation] }), () => pending.promise, () => active);
  active = false;
  pending.resolve(jsonResponse(profileFor(relation.taxon)));
  await tick();
  assert.equal(collectAllNodes(section).some(n => /^species-chat-brief /.test(n.className || "")), false);
});

test("subspecies list uses sourced names, folded scientific identity and accessible cards", async () => {
  const species = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" });
  const sub = { taxon_id: "sub1", rank: "subspecies", scientific_name: "Anas platyrhynchos conboschas", english_name: "Greenland Mallard", english_name_source_url: "https://www.dof.dk/", description: "분포 차이: 그린란드 남서부 해안에 분포합니다." };
  const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, async () => jsonResponse({ parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b", subspecies: [sub], source_url: "https://www.avilist.org/" }));
  assert.equal(explorer.children[2].hidden, true);
  explorer.children[0].dispatch("click"); await tick();
  const row = collectAllNodes(explorer).find(n => /subspecies-peer/.test(n.className));
  assert.equal(row.children[0].children[0].textContent, "Greenland Mallard");
  assert.match(collectedText(row.children[0]), /그린란드 남서부/);
  assert.doesNotMatch(collectedText(row.children[0]), /Anas platyrhynchos/);
  const details = row.children.find(n => n.tagName === "details");
  assert.ok(!details.open);
  assert.match(collectedText(details), /Anas platyrhynchos conboschas/);
  assert.equal(row.children.find(n => n.tagName === "button").getAttribute("aria-label"), "Greenland Mallard · 아종 자료 보기");
  explorer.children[0].dispatch("click");
  assert.equal(explorer.children[2].hidden, true);
  assert.equal(explorer.children[0].getAttribute("aria-expanded"), "false");
});

test("unnamed subspecies use distribution captions without inventing common names", async () => {
  const species = profileFor({ taxon_id: "heron", scientific_name: "Ardea cinerea", korean_name: "왜가리" });
  const sub = { taxon_id: "firasa", rank: "subspecies", scientific_name: "Ardea cinerea firasa", display_label: "왜가리 아종 · 마다가스카르 분포", description: "마다가스카르에 분포하는 아종입니다.", description_source_url: "https://www.birdlife.org.za/" };
  const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, async () => jsonResponse({ parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b", subspecies: [sub] }));
  explorer.children[0].dispatch("click"); await tick();
  const row = collectAllNodes(explorer).find(n => /subspecies-peer/.test(n.className));
  assert.equal(row.children[0].children[0].textContent, sub.display_label);
  assert.doesNotMatch(collectedText(row.children[0]), /firasa|이름 미등록/);
  assert.match(collectedText(row.children.find(n => n.tagName === "details")), /별도 한국어·영어 통칭|분포 설명 출처/);
  assert.equal(row.children.find(n => n.tagName === "button").getAttribute("aria-label"), sub.display_label + " · 아종 자료 보기");
});

test("global subspecies distribution fallback is preserved in folded details and selected labels", async () => {
  const species = profileFor({ taxon_id: "parus", scientific_name: "Parus major", english_name: "Great Tit" });
  const sub = { taxon_id: "major", rank: "subspecies", scientific_name: "Parus major major", display_label: "Great Tit 아종 · Europe to western Siberia", description: "Europe to western Siberia; winter range <script>inert</script>", description_language: "en", range_text: "Europe to western Siberia; winter range <script>inert</script>", description_source_url: "https://explore.avilist.org/data/avilist-2025b.json" };
  const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, async () => jsonResponse({ parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b", subspecies: [sub] }));
  explorer.children[0].dispatch("click"); await tick();
  const row = collectAllNodes(explorer).find(n => /subspecies-peer/.test(n.className));
  assert.equal(row.children[0].children[0].textContent, sub.display_label);
  assert.match(collectedText(row.children[0]), /분포\(영어 원문\): .*Europe/);
  const details = row.children.find(n => n.tagName === "details");
  assert.ok(!details.open);
  assert.match(collectedText(details), /winter range <script>inert<\/script>/);
  assert.equal(collectAllNodes(details).some(n => n.tagName === "script"), false);
  assert.equal(chat.buildSpeciesAnswer({ createElement: createFakeElement }, {taxon:sub,sections:[{title:"분류",items:[]}]}).children[0].textContent, sub.display_label);
});

test("identical subspecies distribution captions remain distinguishable by list number", async () => {
  const species = profileFor({ taxon_id: "parent", scientific_name: "Species test", english_name: "Test Bird" });
  const subs = ["first", "second"].map(id => ({taxon_id:id, rank:"subspecies", scientific_name:"Species test "+id, display_label:"Test Bird 아종 · same islands"}));
  const explorer = chat.buildSubspeciesExplorer({ createElement:createFakeElement },species,async()=>jsonResponse({parent_species:{taxon:species.taxon},concept_set_id:"cs1",taxonomy_release:"v2025b",subspecies:subs}));
  explorer.children[0].dispatch("click"); await tick();
  const rows=collectAllNodes(explorer).filter(n=>/subspecies-peer/.test(n.className));
  assert.equal(rows[0].children[0].children[0].textContent,"Test Bird 아종 · same islands · 아종 1");
  assert.equal(rows[1].children[0].children[0].textContent,"Test Bird 아종 · same islands · 아종 2");
});

test("subspecies explorer fetches lazily and rejects a selected profile from another release", async () => {
  const species = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" });
  const sub = { taxon_id: "sub1", rank: "subspecies", scientific_name: "Anas platyrhynchos test" };
  let calls = 0;
  const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, async url => {
    calls++;
    if (url.startsWith("/v1/taxa/subspecies")) {
      return jsonResponse({ parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b", subspecies: [sub], has_more: true, source_name: "AviList", source_url: "https://www.avilist.org/" });
    }
    const other = profileFor(sub);
    other.lineage.taxonomy_release = "stale";
    return jsonResponse(other);
  });
  assert.equal(calls, 0);
  explorer.children[0].dispatch("click");
  await tick();
  assert.equal(calls, 1);
  assert.match(collectedText(explorer), /일부 아종만 표시/);
  assert.match(collectedText(explorer), /청둥오리 아종 1/);
  assert.equal(explorer.children[0].getAttribute("aria-expanded"), "true");
  collectAllNodes(explorer).find(n => n.tagName === "button" && n.textContent === "아종 보기").dispatch("click");
  await tick();
  assert.equal(calls, 2);
  assert.match(collectedText(explorer), /아종 자료를 확인하지 못했습니다/);
  assert.equal(collectAllNodes(explorer).some(n => /^species-chat-brief /.test(n.className || "")), false);
});

test("subspecies card accepts independently sourced distribution while rejecting unsafe links", () => {
  const profile = profileFor({rank:"subspecies",scientific_name:"Ardea cinerea jouyi",taxon_id:"jouyi",english_name:"Oriental Grey Heron"});
  profile.subspecies_metadata={source_url:"https://explore.avilist.org/data/avilist-2025b.json",source_name:"AviList",section:{key:"subspecies_taxonomy",items:[{text:"분류"},{text:"동아시아에 분포하는 아종입니다.",source_name:"BirdLife South Africa",source_url:"https://www.birdlife.org.za/red-data-book/red-list/grey-heron/"},{text:"unsafe distribution",source_url:"javascript:alert(1)"}]}};
  const card=chat.buildSpeciesCard({createElement:createFakeElement},profile);
  const front=collectAllNodes(card).find(n=>n.className==="species-card-front");
  assert.match(collectedText(front),/동아시아에 분포하는 아종/);
  assert.doesNotMatch(collectedText(front),/unsafe distribution/);
  const details=collectAllNodes(card).find(n=>n.className==="card-details species-subspecies-sources");
  assert.ok(collectAllNodes(details).some(n=>n.tagName==="a"&&n.href==="https://www.birdlife.org.za/red-data-book/red-list/grey-heron/"));
});

test("subspecies card shows only its sourced reviewed description and keeps raw range in source details", () => {
  const profile = profileFor({ rank: "subspecies", scientific_name: "Anas platyrhynchos test", taxon_id: "sub1" });
  profile.subspecies_metadata = { section: { key: "subspecies_taxonomy", items: [{ text: "분류 문장" }, { text: "검토된 아종 고유 분포 설명", source_name: "AviList", source_url: "https://www.avilist.org/" }] }, source_url: "https://www.avilist.org/", source_name: "AviList", range_raw: "Reviewed source range <script>inert</script>" };
  const card = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  const front = collectAllNodes(card).find(n => n.className === "species-card-front");
  assert.match(collectedText(front), /검토된 아종 고유 분포 설명/);
  assert.doesNotMatch(collectedText(front), /Reviewed source range/);
  const sources = collectAllNodes(card).find(n => n.className === "card-details species-subspecies-sources");
  assert.match(collectedText(sources), /분류·아종 설명 출처/);
  assert.match(collectedText(sources), /Reviewed source range/);
  assert.equal(collectAllNodes(sources).find(n => n.tagName === "a").href, "https://www.avilist.org/");
  profile.subspecies_metadata.source_url = "javascript:alert(1)";
  const unsafe = chat.buildSpeciesCard({ createElement: createFakeElement }, profile);
  assert.doesNotMatch(collectedText(unsafe), /검토된 아종 고유 분포 설명|Reviewed source range/);
  assert.match(collectedText(unsafe), /아직 확인하지 못했습니다/);
});

function ecologicalFixture() {
  const source = { source_name: "AVONET", source_url: "https://example.org/avonet", dataset_id: "avonet", release: "v1", license_name: "CC BY", citation: "Reviewed category" };
  return { taxon: { taxon_id: "t1" }, concept_set_id: "cs1", taxonomy_release: "v2025b", groups: [
    { relation: "habitat", value: "wetland", display: "습지", source, items: [{ taxon_id: "peer1", rank: "species", scientific_name: "Peer species", english_name: "English peer", evidence: source }], has_more: true },
    { relation: "trophic_niche", value: "Omnivore", display: "잡식", source, items: [{ taxon_id: "peer2", rank: "species", scientific_name: "Second species", evidence: source }] }
  ] };
}

test("ecological explorer is lazy, sourced and separate; comparisons create independent bubbles with name fallbacks", async () => {
  const data = ecologicalFixture();
  const left = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos" });
  const bubbles = [];
  const calls = [];
  const explorer = chat.buildEcologicalExplorer({ createElement: createFakeElement }, left, async url => {
    calls.push(url);
    if (url.startsWith("/v1/taxa/ecological-related")) { return jsonResponse(data); }
    return jsonResponse(profileFor(data.groups.flatMap(g => g.items).find(p => url.endsWith(encodeURIComponent(p.scientific_name)))));
  }, { onComparison: (panel, info) => bubbles.push({ panel, info }) });
  assert.equal(calls.length, 0);
  explorer.children[0].dispatch("click");
  await tick();
  assert.match(collectedText(explorer), /같은 서식 환경의 새 · 습지/);
  assert.match(collectedText(explorer), /같은 먹이 생태의 새 · 잡식/);
  assert.match(collectedText(explorer), /가까운 계통이나 실제 공존·먹이 관계를 뜻하지 않습니다/);
  assert.match(collectedText(explorer), /English peer/);
  assert.match(collectedText(explorer), /Second species/);
  assert.equal(collectAllNodes(explorer).filter(n => n.className === "ecological-source").length, 4);
  const choices = collectAllNodes(explorer).filter(n => n.tagName === "button" && /비교하기/.test(n.textContent));
  choices[0].dispatch("click"); choices[1].dispatch("click");
  await tick();
  assert.equal(bubbles.length, 2);
  assert.deepEqual(bubbles.map(b => b.info.right.taxon.taxon_id), ["peer1", "peer2"]);
  assert.equal(collectAllNodes(explorer).some(n => n.className === "species-comparison"), false);
  assert.ok(bubbles.every(b => collectAllNodes(b.panel).some(n => n.className === "species-ecological-related")));
  assert.match(collectedText(bubbles[0].panel), /공유 생태 범주: 습지/);
  assert.equal(collectAllNodes(chat.buildSpeciesCard({ createElement: createFakeElement }, left)).some(n => n.className === "species-ecological-related"), false);
});

test("ecological explorer skips unsupported values and unsafe source groups; hostile text stays inert", async () => {
  const data = ecologicalFixture();
  data.groups.push(Object.assign({}, data.groups[0], { value: "unsupported", display: "MUST SKIP" }));
  data.groups.push(Object.assign({}, data.groups[0], { source: { source_name: "bad", source_url: "javascript:alert(1)" }, display: "UNSAFE GROUP" }));
  data.groups[0].display = "<script>inert label</script>";
  for (let i = 0; i < 4; i++) { data.groups[0].items.push({ ...data.groups[0].items[0], taxon_id: "extra" + i, scientific_name: "Extra species" + i, english_name: "Extra " + i }); }
  data.groups[0].items.push({ taxon_id: "bad", rank: "species", scientific_name: "Unsafe peer", evidence: { source_name: "bad", source_url: "//evil.example" } });
  const explorer = chat.buildEcologicalExplorer({ createElement: createFakeElement }, profileFor({ taxon_id: "t1" }), async () => jsonResponse(data));
  explorer.children[0].dispatch("click"); await tick();
  assert.match(collectedText(explorer), /<script>inert label<\/script>/);
  assert.doesNotMatch(collectedText(explorer), /MUST SKIP|UNSAFE GROUP|Unsafe peer|Extra 2|Extra 3/);
  assert.equal(collectAllNodes(explorer).filter(n => (n.className || "").split(" ").includes("ecological-peer")).length, 4); // 3 habitat + 1 niche
  assert.match(collectedText(explorer), /범주별 최대 3종/);
  assert.equal(collectAllNodes(explorer).some(n => n.tagName === "script"), false);
  assert.ok(collectAllNodes(explorer).filter(n => n.tagName === "a").every(n => n.href === "https://example.org/avonet"));
});

test("ecological lookup failure retries and stale releases or late-clear responses never render peers", async () => {
  let count = 0;
  const left = profileFor({ taxon_id: "t1" });
  const explorer = chat.buildEcologicalExplorer({ createElement: createFakeElement }, left, async () => {
    count++;
    if (count === 1) { throw new Error("offline"); }
    return jsonResponse(ecologicalFixture());
  });
  explorer.children[0].dispatch("click"); await tick();
  assert.match(collectedText(explorer), /재시도/);
  explorer.children[0].dispatch("click"); explorer.children[0].dispatch("click"); await tick();
  assert.equal(count, 2);
  assert.match(collectedText(explorer), /English peer/);
  const stale = ecologicalFixture(); stale.taxonomy_release = "old";
  const outdated = chat.buildEcologicalExplorer({ createElement: createFakeElement }, left, async () => jsonResponse(stale));
  outdated.children[0].dispatch("click"); await tick();
  assert.match(collectedText(outdated), /분류 자료가 갱신되었습니다/);
  assert.doesNotMatch(collectedText(outdated), /English peer/);
  const pending = deferred(); let active = true;
  const late = chat.buildEcologicalExplorer({ createElement: createFakeElement }, left, () => pending.promise, { isActive: () => active });
  late.children[0].dispatch("click"); active = false; pending.resolve(jsonResponse(ecologicalFixture())); await tick();
  assert.doesNotMatch(collectedText(late), /English peer/);
});

test("ecological peer comparison rejects changed IDs/releases and ignores late responses", async () => {
  let active = true;
  let callbacks = 0;
  const pending = deferred();
  const explorer = chat.buildEcologicalExplorer({ createElement: createFakeElement }, profileFor({ taxon_id: "t1" }), url => url.startsWith("/v1/taxa/ecological-related") ? Promise.resolve(jsonResponse(ecologicalFixture())) : pending.promise, { isActive: () => active, onComparison: () => callbacks++ });
  explorer.children[0].dispatch("click"); await tick();
  collectAllNodes(explorer).find(n => n.tagName === "button" && /English peer/.test(n.getAttribute("aria-label") || "")).dispatch("click");
  const wrong = profileFor({ taxon_id: "wrong", scientific_name: "Peer species" });
  pending.resolve(jsonResponse(wrong)); await tick();
  assert.equal(callbacks, 0);
  assert.match(collectedText(explorer), /비교 자료를 표시하지 않았습니다/);
  active = false;
  collectAllNodes(explorer).find(n => n.tagName === "button" && /English peer/.test(n.getAttribute("aria-label") || "")).dispatch("click"); await tick();
  assert.equal(callbacks, 0);
});

test("targeted diet answer appears first with sources and keeps the card without unrelated full sections", async () => {
  const payload = fakeProfilePayload();
  payload.result.question_answer = { topic: "diet", title: "무엇을 먹나요?", text: "검토된 자료에서 잡식으로 분류됩니다.", items: [{ text: "씨앗과 무척추동물", source_name: "Reviewed diet", source_url: "https://example.org/diet" }, { text: "<script>inert fact</script>", source_name: "Unsafe", source_url: "javascript:alert(1)" }] };
  const dom = createFakeDom(url => Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리는 뭘 먹어?";
  pressKey(dom, {}); await settleEventPath();
  const answer = messageRows(dom.elementsById.history)[1];
  const targeted = answer.children.find(n => n.className === "species-question-answer");
  assert.ok(targeted);
  assert.equal(targeted.children[0].textContent, "무엇을 먹나요?");
  assert.match(collectedText(targeted), /씨앗과 무척추동물/);
  assert.equal(collectAllNodes(targeted).filter(n => n.tagName === "a").length, 1);
  assert.equal(collectAllNodes(targeted).some(n => n.tagName === "script"), false);
  assert.equal(collectAllNodes(answer).some(n => n.className === "species-answer"), false);
  assert.ok(collectAllNodes(answer).some(n => n.className === "species-popup-trigger risk-unconfirmed" || /^species-popup-trigger /.test(n.className || "")));
});

test("direct ecological answer displays peers without another lookup and comparison creates a separate answer", async () => {
  const payload = fakeProfilePayload();
  payload.result.question_answer = { topic: "ecological_related", title: "같은 생태 범주의 새", text: "같은 자료의 서식 환경을 기준으로 찾았습니다.", items: [], relations: ecologicalFixture() };
  const peer = profileFor(ecologicalFixture().groups[0].items[0]);
  const dom = createFakeDom(url => Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : url.startsWith("/v1/taxa/profile") ? peer : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리와 같은 서식 환경의 새는?";
  pressKey(dom, {}); await settleEventPath(); await tick();
  const answer = messageRows(dom.elementsById.history)[1];
  const explorer = collectAllNodes(answer).find(n => n.className === "species-ecological-related");
  assert.equal(explorer.children[1].hidden, false);
  assert.match(collectedText(explorer), /English peer/);
  assert.equal(dom.fetchCalls.some(c => c.url.startsWith("/v1/taxa/ecological-related")), false);
  collectAllNodes(explorer).find(n => n.tagName === "button" && /English peer/.test(n.getAttribute("aria-label") || "")).dispatch("click"); await tick();
  assert.equal(messageRows(dom.elementsById.history).length, 3);
  assert.equal(collectAllNodes(messageRows(dom.elementsById.history)[2]).filter(n => n.tagName === "dialog").length, 2);
  assert.match(collectedText(answer), /English peer/);
});

test("initial relation data is validated and taxonomy peers use scientific-name fallback without lookup", async () => {
  const left = profileFor({ taxon_id: "t1" });
  const data = { taxon: left.taxon, taxonomy_source: "AviList", concept_set_id: "cs1", taxonomy_release: "v2025b", note: "같은 속", groups: [{ rank: "genus", label: "같은 속의 새", ancestor: { scientific_name: "Anas" }, source_name: "AviList", source_url: "https://example.org/taxonomy", items: [{ taxon_id: "peer", scientific_name: "Anas peer" }] }] };
  let calls = 0;
  const explorer = chat.buildRelatedExplorer({ createElement: createFakeElement }, left, () => { calls++; }, { initialData: data, initiallyOpen: true });
  await tick();
  assert.equal(calls, 0);
  assert.match(collectedText(explorer), /Anas peer/);
  const stale = chat.buildEcologicalExplorer({ createElement: createFakeElement }, left, () => { calls++; }, { initialData: Object.assign(ecologicalFixture(), { concept_set_id: "old" }), initiallyOpen: true });
  await tick();
  assert.equal(calls, 0);
  assert.doesNotMatch(collectedText(stale), /English peer/);
  assert.match(collectedText(stale), /분류 자료가 갱신되었습니다/);
});

test("targeted answers retain reviewed common-name provenance with safe source links", () => {
  const context = fakeNameRelations({ query_name: "검둥오리", summary: "검토된 통칭 관계", relations: [fakeNameRelations().relations[1]] });
  const answer = chat.buildQuestionAnswer({ createElement: createFakeElement }, { topic: "diet", title: "먹이", text: "통칭으로 연결된 종의 먹이", items: [], name_context: context });
  const details = collectAllNodes(answer).find(n => n.className === "question-answer-name-context");
  assert.equal(details.tagName, "details");
  assert.match(collectedText(details), /검토된 통칭 관계/);
  assert.match(collectedText(details), /흰뺨검둥오리 · 통칭에 포함되는 야생종/);
  assert.match(collectedText(details), /<script>bad\(\)<\/script>/);
  assert.equal(collectAllNodes(details).some(n => n.tagName === "script"), false);
  assert.equal(collectAllNodes(details).some(n => n.tagName === "a"), false);
  context.relations[0].sources = [{ title: "Reviewed alias", url: "https://example.org/alias" }];
  const sourced = chat.buildQuestionAnswer({ createElement: createFakeElement }, { topic: "diet", title: "먹이", text: "직접 답변", items: [], name_context: context });
  assert.equal(collectAllNodes(sourced).find(n => n.tagName === "a").href, "https://example.org/alias");
});

function similarityFixture() {
  const peers = [3, 1, 2, 4].map(rank => ({ taxon_id: "sim" + rank, rank: "species", scientific_name: "Similar species " + rank, english_name: "Peer " + rank, similarity_rank: rank, similarity_score: 100 - rank * 10, similarity_reasons: [{ label: rank === 1 ? "<script>same genus</script>" : "같은 서식 환경", source_name: "Reviewed graph", source_url: rank === 1 ? "javascript:alert(1)" : "https://example.org/graph" }] }));
  return { taxon: { taxon_id: "t1" }, taxonomy_source: "AviList", taxonomy_release: "v2025b", concept_set_id: "cs1", ranking: { method: "taxonomy-ecology-v1", limit: 3, candidate_scope: "same_family" }, note: "분류·생태 자료 점수이며 외형이나 진화적 거리 측정값이 아닙니다.", groups: [{ rank: "similarity", label: "그래프 유사도 상위 3종", source_name: "Reviewed graph", source_url: "https://example.org/graph", items: peers, has_more: true }] };
}

test("ordinary introduction follows the reference layout with folded TOP3, extra information and all answer sources", async () => {
  const payload = fakeProfilePayload({
    conservation: Object.assign({ category: "LC" }, VERIFIED_SOURCE),
    sections: [
      { key: "basic", title: "기본 정보", items: [{ text: "전체 종 소개", source_name: "Reviewed profile", source_url: "https://example.org/profile" }] },
      { key: "appearance", title: "외관 특징", items: [{ text: "외관 설명", source_name: "Appearance source", source_url: "https://example.org/appearance" }] },
      { key: "ecology", title: "생활과 먹이", items: [{ text: "생활 설명", source_name: "Ecology source", source_url: "https://example.org/ecology" }] },
      { key: "fun_facts", title: "재미있는 사실", items: [{ text: "재미있는 사실 설명", source_name: "Fun facts source", source_url: "https://example.org/facts" }] },
    ],
  });
  payload.citations = [{ source_id: "API evidence", source_url: "https://example.org/evidence", evidence_id: "e1", locator: "page 1", license_name: "CC BY" }];
  payload.result.similar_species = similarityFixture();
  const peer = profileFor(payload.result.similar_species.groups[0].items.find(p => p.similarity_rank === 1));
  const dom = createFakeDom(url => Promise.resolve(jsonResponse(url === "/health" ? { mode: "fixture" } : url.startsWith("/v1/taxa/profile") ? peer : payload)));
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "청둥오리에 대해 알고싶어";
  pressKey(dom, {}); await settleEventPath(); await tick();
  const answer = messageRows(dom.elementsById.history)[1];
  const explanation = answer.children.find(n => n.className === "species-answer");
  assert.match(collectedText(explanation), /기본 정보\s+전체 종 소개/);
  assert.ok(explanation.children.some(n => /^species-chat-brief /.test(n.className || "")));
  assert.ok(collectAllNodes(answer).some(n => /^species-popup-trigger /.test(n.className || "")));
  const explorer = answer.children.find(n => n.className === "species-related");
  assert.equal(explorer.children[0].getAttribute("aria-expanded"), "false");
  assert.equal(explorer.children[1].hidden, true);
  assert.equal(explorer.children[0].textContent, "근연 관계 우선 3종 살펴보기");
  const extra = answer.children.find(n => n.className === "species-extra-info");
  assert.equal(extra.tagName, "details"); assert.ok(!extra.open);
  assert.deepEqual(extra.children.slice(1).map(n => n.className), ["species-ecological-related", "species-subspecies", "species-name-relations"]);
  const sources = answer.children.find(n => n.className === "species-answer-sources");
  assert.equal(answer.children.at(-1), sources); assert.ok(!sources.open);
  for (const name of ["Reviewed profile", "Appearance source", "Ecology source", "Fun facts source", "IUCN Red List", "API evidence"]) {
    assert.ok(collectedText(sources).includes(name), "footer retains " + name);
  }
  assert.deepEqual(explanation.children.map(n => n.className), ["", "species-answer-section", "species-chat-brief risk-lc", "species-answer-section", "species-answer-section", "species-answer-section"]);
  assert.equal(explanation.children.at(-1).children[0].textContent, "재미있는 사실");
  assert.equal(explanation.children.some(n => n.className === "species-answer-sources"), false);
  assert.equal(dom.fetchCalls.some(c => c.url.startsWith("/v1/taxa/")), false, "folded exploration never fetches");
  assert.ok(answer.children.indexOf(explanation) < answer.children.findIndex(n => n.className === "species-popup-entry"));
  assert.ok(answer.children.findIndex(n => n.className === "species-popup-entry") < answer.children.indexOf(explorer));
  assert.ok(answer.children.indexOf(explorer) < answer.children.indexOf(extra));
  explorer.children[0].dispatch("click"); await tick();
  assert.equal(explorer.children[0].getAttribute("aria-expanded"), "true");
  assert.equal(explorer.children[1].hidden, false);
  explorer.children[0].dispatch("click");
  assert.equal(explorer.children[1].hidden, true);
  explorer.children[0].dispatch("click");
  assert.equal(explorer.children[1].hidden, false);
  const choices = collectAllNodes(explorer).filter(n => n.tagName === "button" && /비교하기/.test(n.textContent));
  assert.deepEqual(choices.map(n => n.getAttribute("aria-label")), ["1위 · Peer 1 · 가중 점수 90점 · 비교하기", "2위 · Peer 2 · 가중 점수 80점 · 비교하기", "3위 · Peer 3 · 가중 점수 70점 · 비교하기"]);
  assert.ok(collectAllNodes(explorer).some(n => n.tagName === "a" && n.textContent === "Reviewed graph" && n.href === "https://example.org/graph"));
  assert.equal(dom.fetchCalls.some(c => c.url.startsWith("/v1/taxa/related")), false);
  choices[0].dispatch("click"); await tick();
  const rows = messageRows(dom.elementsById.history);
  assert.equal(rows.length, 3);
  assert.equal(rows[1], answer);
  assert.equal(collectAllNodes(answer).some(n => n.className === "species-comparison"), false);
  assert.match(collectedText(rows[2]), /가중 점수 90점/);
  assert.equal(collectAllNodes(rows[2]).filter(n => n.tagName === "dialog").length, 2);
});

test("ranked fallback scores disclose missing phylogeny and retain fractional scores", async () => {
  const data = similarityFixture();
  data.ranking.method = "taxonomy-phylogeny-ecology-v3";
  const peer = data.groups[0].items.find(p => p.similarity_rank === 1);
  peer.score_basis = "taxonomy_ecology_fallback";
  peer.similarity_score = 66.67;
  const explorer = chat.buildRelatedExplorer({ createElement: createFakeElement }, profileFor({ taxon_id: "t1" }), () => {}, { initialData: data, initiallyOpen: true });
  await tick();
  assert.match(collectedText(explorer), /분류·생태 대체 점수\(계통 자료 부족\) 66.67점/);
});

test("ranked similar species render TOP3 in rank order with scores, explanation and safe provenance", async () => {
  const explorer = chat.buildRelatedExplorer({ createElement: createFakeElement }, profileFor({ taxon_id: "t1" }), () => { throw new Error("no lookup"); }, { initialData: similarityFixture(), initiallyOpen: true });
  await tick();
  const buttons = collectAllNodes(explorer).filter(n => n.tagName === "button" && /비교하기/.test(n.textContent));
  assert.deepEqual(buttons.map(n => n.getAttribute("aria-label")), ["1위 · Peer 1 · 가중 점수 90점 · 비교하기", "2위 · Peer 2 · 가중 점수 80점 · 비교하기", "3위 · Peer 3 · 가중 점수 70점 · 비교하기"]);
  const rows = collectAllNodes(explorer).filter(n => n.className === "comparison-peer");
  assert.equal(rows.length, 3);
  rows.forEach((row, index) => {
    assert.ok(collectAllNodes(row).some(n => n.tagName === "strong" && n.textContent === "Peer " + (index + 1)));
    assert.ok(collectAllNodes(row).some(n => n.tagName === "i" && n.textContent === "Similar species " + (index + 1)));
    assert.equal(row.children.find(n => n.className === "comparison-peer-score").textContent, (index + 1) + "위 · 가중 점수 " + (90 - index * 10) + "점");
    assert.equal(row.children.find(n => n.tagName === "button").textContent, "비교하기");
    assert.equal(row.children.filter(n => n.tagName === "details").length, 1);
    assert.ok(!row.children.find(n => n.tagName === "details").open);
  });
  assert.doesNotMatch(collectedText(explorer), /Peer 4|12종/);
  assert.match(collectedText(explorer), /외형이나 진화적 거리/);
  assert.match(collectedText(explorer), /<script>same genus<\/script>/);
  assert.equal(collectAllNodes(explorer).some(n => n.tagName === "script"), false);
  assert.ok(collectAllNodes(explorer).filter(n => n.tagName === "a").every(n => n.href === "https://example.org/graph"));
});

test("ranked comparison preserves similarity reasons in a new bubble and rejects stale peer release", async () => {
  const data = similarityFixture();
  const left = profileFor({ taxon_id: "t1" });
  const bubbles = [];
  let stale = false;
  const explorer = chat.buildRelatedExplorer({ createElement: createFakeElement }, left, async () => {
    const peer = profileFor(data.groups[0].items.find(p => p.similarity_rank === 1));
    if (stale) { peer.lineage.taxonomy_release = "old"; }
    return jsonResponse(peer);
  }, { initialData: data, initiallyOpen: true, onComparison: panel => bubbles.push(panel) });
  await tick();
  const button = collectAllNodes(explorer).find(n => n.tagName === "button" && /^1위/.test(n.getAttribute("aria-label") || ""));
  button.dispatch("click"); await tick();
  assert.equal(bubbles.length, 1);
  assert.match(collectedText(bubbles[0]), /가중 점수 90점/);
  assert.match(collectedText(bubbles[0]), /비교 후보 근거와 출처/);
  assert.match(collectedText(bubbles[0]), /진화 거리나 유전 유사도/);
  assert.equal(collectAllNodes(bubbles[0]).filter(n => n.tagName === "dialog").length, 2);
  stale = true; button.dispatch("click"); await tick();
  assert.equal(bubbles.length, 1);
  assert.match(collectedText(explorer), /비교 자료를 표시하지 않았습니다/);
});

test("Jev subspecies answers show the supplied list immediately without another list request", async () => {
  const species = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos", korean_name: "청둥오리" });
  const data = { parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b",
    source_url: "https://www.avilist.org/", subspecies: [{ taxon_id: "sub1", rank: "subspecies", scientific_name: "Anas platyrhynchos conboschas", english_name: "Greenland Mallard" }] };
  let fetches = 0;
  const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, async () => { fetches++; throw Error("unexpected duplicate"); }, null, data);
  await tick();
  assert.equal(fetches, 0);
  assert.equal(explorer.children[2].hidden, false);
  assert.equal(explorer.children[0].getAttribute("aria-expanded"), "true");
  assert.match(collectedText(explorer), /Greenland Mallard/);
  const answer = chat.buildQuestionAnswer({ createElement: createFakeElement }, { topic: "subspecies", title: "청둥오리 · 아종 목록", text: "아종 1개", items: [] });
  assert.match(collectedText(answer), /아종 1개/);
});

test("Jev supplied subspecies lists from another parent or release are rejected", async () => {
  const species = profileFor({ taxon_id: "t1", scientific_name: "Anas platyrhynchos" });
  for (const changes of [{ concept_set_id: "wrong" }, { parent_species: { taxon: { taxon_id: "wrong" } } }]) {
    const data = Object.assign({ parent_species: { taxon: species.taxon }, concept_set_id: "cs1", taxonomy_release: "v2025b", subspecies: [{ taxon_id: "bad", english_name: "Wrong bird" }] }, changes);
    const explorer = chat.buildSubspeciesExplorer({ createElement: createFakeElement }, species, null, null, data);
    await tick();
    assert.doesNotMatch(collectedText(explorer), /Wrong bird/);
    assert.match(collectedText(explorer), /확인하지 못했습니다/);
  }
});
