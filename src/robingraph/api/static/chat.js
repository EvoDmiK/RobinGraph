/**
 * RobinGraph manual test UI. Talks only to same-origin `/health` and
 * `/v1/answers`. No innerHTML/insertAdjacentHTML/document.write is used
 * anywhere in this file -- all dynamic content is inserted via
 * `textContent`/`createElement`, which never interprets its input as
 * markup. The one place hostile *server* content could still reach an
 * executable sink despite that is an `href` built from `citation.source_url`
 * (e.g. a `javascript:` URL) -- `sanitizeUrl` below is the guard for that.
 *
 * The pure helpers (`sanitizeUrl`, `formatDisposition`,
 * `sanitizeErrorMessage`) are exported via `module.exports` so they can be
 * unit-tested under plain Node with no browser/DOM involved.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.RobinGraphChat = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var SAFE_URL_SCHEMES = ["http:", "https:"];

  /**
   * Only ever return a URL that is safe to place in an `href` attribute:
   * an absolute http(s) URL exactly as the server sent it. Rejects
   * `javascript:`, `data:`, `vbscript:`, protocol-relative ("//host/..")
   * and malformed strings by returning null, which callers must render as
   * inert plain text instead of a link.
   */
  function sanitizeUrl(value) {
    if (typeof value !== "string") {
      return null;
    }
    var trimmed = value.trim();
    if (trimmed === "") {
      return null;
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      return null;
    }
    var parsed;
    try {
      parsed = new URL(trimmed);
    } catch (error) {
      return null;
    }
    if (SAFE_URL_SCHEMES.indexOf(parsed.protocol) === -1) {
      return null;
    }
    return trimmed;
  }

  var DISPOSITION_LABELS = {
    answer: { label: "답변", className: "disposition-answer" },
    abstain: { label: "보류 (근거 부족)", className: "disposition-abstain" },
    clarify: { label: "추가 확인 필요", className: "disposition-clarify" },
  };

  /**
   * Only answer/abstain/clarify are known-safe dispositions. Anything else
   * (a future backend value, or a hostile/garbled payload) must never be
   * echoed back as if it were trusted content, and must never be treated as
   * a rendered answer -- callers branch on `recognized` to fail closed.
   */
  function formatDisposition(disposition) {
    // Require an exact string match rather than `DISPOSITION_LABELS[disposition]`:
    // bracket lookup coerces its key to a string first, so a non-string
    // payload like `["answer"]` (e.g. a malformed/hostile JSON body) would
    // otherwise coerce to "answer" and be treated as recognized.
    if (typeof disposition === "string" && Object.prototype.hasOwnProperty.call(DISPOSITION_LABELS, disposition)) {
      var known = DISPOSITION_LABELS[disposition];
      return { label: known.label, className: known.className, recognized: true };
    }
    return { label: "지원되지 않는 응답", className: "disposition-unknown", recognized: false };
  }

  function formatBackendMode(mode) {
    if (mode === "fixture") {
      return "fixture (합성 데이터 · 문헌 검색 미지원)";
    }
    if (mode === "neo4j") {
      return "neo4j (그래프 DB · 근거 기반 답변)";
    }
    if (typeof mode === "string" && mode.trim()) {
      return "지원되지 않는 모드: " + mode.trim();
    }
    return "확인 불가";
  }

  /**
   * Turn a failure into a short, honest, non-leaking Korean message.
   * Never surfaces a raw exception message or stack trace, and never
   * echoes any server-provided `detail` string either: a `detail` is
   * attacker-influenced input as far as this UI is concerned (it can
   * contain secrets, internal URLs/paths, control characters, or
   * unbounded length even if our own backend never intends that), so it
   * is accepted on the context object for forward-compatibility but is
   * never read or displayed. Each 4xx status we recognize
   * (400/401/403/422/404/429/503) gets its own fixed, honest message
   * (bad request / auth required / forbidden / validation / not found /
   * rate-limited / temporarily unavailable) rather than being collapsed
   * into a generic "server error" -- only a genuinely unrecognized status
   * falls through to the generic message below.
   */
  function sanitizeErrorMessage(context) {
    context = context || {};
    if (context.kind === "network") {
      return "서버에 연결할 수 없습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요.";
    }
    if (context.kind === "unsupported-response") {
      return "지원되지 않는 응답 형식을 받았습니다. 다시 시도해주세요.";
    }
    if (context.kind === "http") {
      var status = context.status;
      if (status === 400) {
        return "요청이 올바르지 않습니다. 입력 내용을 확인한 뒤 다시 시도하세요.";
      }
      if (status === 401) {
        return "인증이 필요합니다. 로그인 상태를 확인한 뒤 다시 시도하세요.";
      }
      if (status === 403) {
        return "이 작업에 대한 접근 권한이 없습니다.";
      }
      if (status === 422) {
        return "입력을 확인해주세요. 질문은 1자 이상 2,000자 이하로 입력해야 합니다.";
      }
      if (status === 404) {
        return "요청한 정보를 찾을 수 없습니다.";
      }
      if (status === 429) {
        return "요청이 너무 많습니다. 잠시 후 다시 시도하세요.";
      }
      if (status === 503) {
        return "백엔드를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도하세요.";
      }
      return "서버 오류가 발생했습니다 (상태 코드 " + Number(status) + ").";
    }
    return "요청 처리 중 알 수 없는 오류가 발생했습니다.";
  }

  function init(doc, win) {
    var form = doc.getElementById("chat-form");
    var input = doc.getElementById("question-input");
    var sendButton = doc.getElementById("send-button");
    var clearButton = doc.getElementById("clear-button");
    var history = doc.getElementById("history");
    var statusRegion = doc.getElementById("status-region");
    var spinner = doc.getElementById("spinner");
    var backendModeValue = doc.getElementById("backend-mode-value");

    // Page-session only: lives in a plain JS array for as long as this tab
    // stays open. Never written to localStorage/sessionStorage/cookies, and
    // wiped by "대화 지우기" or a reload -- there is no persistence layer.
    var messages = [];

    function setStatus(text) {
      statusRegion.textContent = text;
    }

    function setBusy(isBusy) {
      sendButton.disabled = isBusy;
      clearButton.disabled = isBusy;
      input.disabled = isBusy;
      spinner.hidden = !isBusy;
      form.setAttribute("aria-busy", isBusy ? "true" : "false");
    }

    function scrollToLatest() {
      history.scrollTop = history.scrollHeight;
    }

    function appendUserMessage(question) {
      var item = doc.createElement("div");
      item.className = "message message-user";

      var label = doc.createElement("strong");
      label.textContent = "나";
      item.appendChild(label);

      var text = doc.createElement("p");
      text.textContent = question;
      item.appendChild(text);

      history.appendChild(item);
      messages.push({ role: "user", text: question });
      scrollToLatest();
    }

    function appendAnswerMessage(answer) {
      var item = doc.createElement("div");
      item.className = "message message-answer";

      var label = doc.createElement("strong");
      label.textContent = "RobinGraph";
      item.appendChild(label);

      var dispositionInfo = formatDisposition(answer.disposition);
      var badge = doc.createElement("span");
      badge.className = "badge " + dispositionInfo.className;
      badge.textContent = dispositionInfo.label;
      item.appendChild(badge);

      var text = doc.createElement("p");
      text.textContent = answer.answer_text;
      item.appendChild(text);

      var answerMetadata = [];
      if (answer.taxonomy_release) {
        answerMetadata.push("분류 릴리스: " + answer.taxonomy_release);
      }
      if (answer.data_cutoff) {
        answerMetadata.push("데이터 기준일: " + answer.data_cutoff);
      }
      if (answerMetadata.length > 0) {
        var metadata = doc.createElement("p");
        metadata.className = "answer-metadata";
        metadata.textContent = answerMetadata.join(" · ");
        item.appendChild(metadata);
      }

      var warnings = Array.isArray(answer.warnings) ? answer.warnings : [];
      if (warnings.length > 0) {
        var warnList = doc.createElement("ul");
        warnList.className = "warnings";
        warnings.forEach(function (warning) {
          var li = doc.createElement("li");
          li.textContent = "⚠ " + warning;
          warnList.appendChild(li);
        });
        item.appendChild(warnList);
      }

      var citations = Array.isArray(answer.citations) ? answer.citations : [];
      if (citations.length > 0) {
        var citeList = doc.createElement("ul");
        citeList.className = "citations";
        citations.forEach(function (citation) {
          var li = doc.createElement("li");

          var safeUrl = sanitizeUrl(citation.source_url);
          var sourceNode;
          if (safeUrl) {
            sourceNode = doc.createElement("a");
            sourceNode.href = safeUrl;
            sourceNode.target = "_blank";
            sourceNode.rel = "noopener noreferrer";
            sourceNode.textContent = citation.source_id;
          } else {
            sourceNode = doc.createElement("span");
            sourceNode.textContent = citation.source_id;
          }
          li.appendChild(sourceNode);

          var meta = doc.createElement("span");
          meta.className = "citation-meta";
          meta.textContent =
            " — 근거 " + citation.evidence_id +
            " · " + citation.locator +
            " (" + citation.license_name + ")";
          li.appendChild(meta);

          citeList.appendChild(li);
        });
        item.appendChild(citeList);
      }

      history.appendChild(item);
      messages.push({ role: "assistant", answer: answer });
      scrollToLatest();
    }

    function appendErrorMessage(text) {
      var item = doc.createElement("div");
      item.className = "message message-error";
      item.textContent = text;
      history.appendChild(item);
      messages.push({ role: "error", text: text });
      scrollToLatest();
    }

    function loadHealth() {
      win
        .fetch("/health", { method: "GET" })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("health check failed");
          }
          return response.json();
        })
        .then(function (payload) {
          backendModeValue.textContent = formatBackendMode(payload && payload.mode);
        })
        .catch(function () {
          backendModeValue.textContent = "확인 불가 (질문 API는 계속 시도할 수 있음)";
        });
    }

    function submitQuestion(question) {
      setBusy(true);
      setStatus("답변을 불러오는 중입니다…");

      win
        .fetch("/v1/answers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: question }),
        })
        .then(function (response) {
          return response
            .json()
            .catch(function () {
              return null;
            })
            .then(function (payload) {
              return { response: response, payload: payload };
            });
        })
        .then(function (result) {
          if (!result.response.ok) {
            // The server's `detail` string is never read here: see
            // sanitizeErrorMessage's fixed, honest per-status messages.
            appendErrorMessage(sanitizeErrorMessage({ kind: "http", status: result.response.status }));
            return;
          }
          // Fail closed: only answer/abstain/clarify are known-safe
          // dispositions. A 2xx with any other (or missing) disposition is
          // never rendered as a successful answer, and the unrecognized
          // value itself is never echoed back as trusted content -- the
          // user only ever sees a fixed, generic "unsupported response"
          // message.
          var dispositionInfo = formatDisposition(result.payload && result.payload.disposition);
          if (!dispositionInfo.recognized) {
            appendErrorMessage(sanitizeErrorMessage({ kind: "unsupported-response" }));
            return;
          }
          appendAnswerMessage(result.payload);
        })
        .catch(function () {
          appendErrorMessage(sanitizeErrorMessage({ kind: "network" }));
        })
        .then(function () {
          setBusy(false);
          setStatus("");
        });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var question = input.value.trim();
      if (!question) {
        return;
      }
      appendUserMessage(question);
      input.value = "";
      submitQuestion(question);
    });

    input.addEventListener("keydown", function (event) {
      // event.isComposing is true while an IME (Korean/Japanese/Chinese
      // input method) is still composing the current character block.
      // Some IMEs report the confirming keystroke as "Enter" too, so
      // without this guard, confirming a composition would also submit
      // the form. Once composition ends, isComposing is false again and
      // Enter submits normally; Shift+Enter always inserts a newline
      // regardless of composition state.
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      }
    });

    clearButton.addEventListener("click", function () {
      messages.length = 0;
      while (history.firstChild) {
        history.removeChild(history.firstChild);
      }
      setStatus("대화 기록을 지웠습니다.");
    });

    loadHealth();
  }

  if (typeof document !== "undefined" && typeof window !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document, window);
    });
  }

  return {
    sanitizeUrl: sanitizeUrl,
    formatDisposition: formatDisposition,
    formatBackendMode: formatBackendMode,
    sanitizeErrorMessage: sanitizeErrorMessage,
    init: init,
  };
});
