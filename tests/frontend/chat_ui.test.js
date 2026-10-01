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

test("chat.js only ever fetches same-origin /health and /v1/chat", () => {
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
