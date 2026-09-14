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

test("chat.js wires the fail-closed disposition guard into the /v1/answers success path", () => {
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

test("chat.js only ever fetches same-origin /health and /v1/answers", () => {
  const calls = Array.from(jsSource.matchAll(/\.fetch\(\s*"([^"]+)"/g)).map((match) => match[1]);
  assert.deepEqual(calls.sort(), ["/health", "/v1/answers"]);
  assert.equal(jsSource.includes("https://"), false, "no absolute/remote URL literal is allowed in chat.js");
  assert.equal(jsSource.includes("http://"), false, "no absolute/remote URL literal is allowed in chat.js");
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
    'id="question-input"',
    'id="send-button"',
    'id="clear-button"',
    'id="history"',
    'id="backend-mode-value"',
    'id="status-region"',
    'id="spinner"',
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
});

test("index.html honestly discloses this is a deterministic, evidence-grounded UI, not an LLM/Hermes chatbot", () => {
  assert.ok(htmlSource.includes("Hermes"), "the disclaimer should name Hermes in order to explicitly disclaim it");
  assert.ok(htmlSource.includes("생성형 언어모델"));
  assert.ok(htmlSource.includes("결정론"));

  // The sentence naming Hermes must be phrased as a negation ("...하지
  // 않고/않습니다"), not an affirmative claim that Hermes powers this UI.
  const hermesSentenceMatch = htmlSource.match(/[^.]*Hermes[^.]*\./);
  assert.ok(hermesSentenceMatch, "expected to find a sentence mentioning Hermes");
  const hermesSentence = hermesSentenceMatch[0];
  assert.ok(hermesSentence.includes("않"), "the Hermes sentence must explicitly negate/disclaim it: " + hermesSentence);
  assert.equal(/사용합니다|기반입니다|기반으로 (작동|동작)합니다/.test(hermesSentence), false);
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
      this.children.push(child);
      return child;
    },
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index !== -1) {
        this.children.splice(index, 1);
      }
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

function createFakeDom() {
  const REQUIRED_IDS = [
    "chat-form",
    "question-input",
    "send-button",
    "clear-button",
    "history",
    "status-region",
    "spinner",
    "backend-mode-value",
  ];
  const elementsById = {};
  for (const id of REQUIRED_IDS) {
    elementsById[id] = createFakeElement(id === "chat-form" ? "form" : "div");
  }
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
  // loadHealth() fires during init(); a pending, never-resolving promise
  // keeps it out of the way of the synchronous keydown assertions below
  // without needing any real network/browser fetch implementation.
  const win = {
    fetch() {
      return new Promise(() => {});
    },
  };
  return { doc, win, elementsById };
}

function pressKey(dom, keyEventOverrides) {
  const input = dom.elementsById["question-input"];
  return input.dispatch(
    "keydown",
    Object.assign({ key: "Enter", shiftKey: false, isComposing: false }, keyEventOverrides)
  );
}

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
  assert.equal(dom.elementsById["history"].children.length, 1, "expected the submit handler to render the user message");
  assert.equal(dom.elementsById["question-input"].value, "", "expected the input to be cleared after submit");
});

test("real keydown event path: Enter fired right after IME composition ends (isComposing: false) still submits (post-composition Enter is preserved)", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "한글 조합이 끝난 뒤 엔터";

  const event = pressKey(dom, { isComposing: false, shiftKey: false });

  assert.equal(event.defaultPrevented, true);
  assert.equal(dom.elementsById["history"].children.length, 1);
  assert.equal(dom.elementsById["question-input"].value, "");
});

test("real keydown event path: Enter while event.isComposing is true is ignored, leaving the in-progress IME composition alone", () => {
  const dom = createFakeDom();
  chat.init(dom.doc, dom.win);
  dom.elementsById["question-input"].value = "한글 조합 중";

  const event = pressKey(dom, { isComposing: true, shiftKey: false });

  assert.notEqual(event.defaultPrevented, true, "must not preventDefault while composing");
  assert.equal(dom.elementsById["history"].children.length, 0, "must not submit while composing");
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
    assert.equal(dom.elementsById["history"].children.length, 0);
    assert.equal(dom.elementsById["question-input"].value, "여러 줄");
  }
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
