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

test("formatDisposition gives honest Korean labels for answer/abstain and a safe fallback for anything else", () => {
  const answer = chat.formatDisposition("answer");
  assert.equal(answer.label, "답변");
  assert.equal(answer.className, "disposition-answer");

  const abstain = chat.formatDisposition("abstain");
  assert.equal(abstain.className, "disposition-abstain");
  assert.match(abstain.label, /근거/);

  const clarify = chat.formatDisposition("clarify");
  assert.equal(clarify.className, "disposition-clarify");
  assert.match(clarify.label, /확인/);

  const hostileDisposition = "<script>alert(1)</script>";
  const fallback = chat.formatDisposition(hostileDisposition);
  assert.equal(fallback.className, "disposition-unknown");
  assert.equal(fallback.label, hostileDisposition);
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
