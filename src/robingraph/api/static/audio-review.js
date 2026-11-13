/* Review access and unsaved notes live in this tab only; metadata never becomes HTML. */
(function () {
  "use strict";
  var form = document.getElementById("review-connect-form");
  var keyInput = document.getElementById("review-key");
  var connectButton = document.getElementById("review-connect");
  var disconnectButton = document.getElementById("review-disconnect");
  var library = document.getElementById("review-library");
  var filter = document.getElementById("review-status-filter");
  var list = document.getElementById("review-candidates");
  var more = document.getElementById("review-more");
  var refresh = document.getElementById("review-refresh");
  var status = document.getElementById("review-status");
  var token = "", session = 0, view = 0, offset = 0, loading = false;
  var drafts = new Map(), fieldSequence = 0;
  var requests = new Set(), audio = null, objectUrl = null, playButton = null;
  var previewController = null;
  var statuses = {
    awaiting_review: "검토 대기", approved: "검토 승인", published: "공개됨",
    rejected: "검토 반려", deferred: "수집 보류"
  };

  function text(value) { return typeof value === "string" && value.trim() ? value.trim() : "미확인"; }
  function node(tag, className, value) {
    var element = document.createElement(tag);
    if (className) { element.className = className; }
    if (value != null) { element.textContent = value; }
    return element;
  }
  function safeLink(value, label) {
    try {
      var url = new URL(value);
      if ((url.protocol === "https:" || url.protocol === "http:") && !url.username && !url.password) {
        var link = node("a", "", label);
        link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
        return link;
      }
    } catch (error) { /* Missing or unsafe links stay plain text. */ }
    return node("span", "", label);
  }
  function message(value, failed) {
    status.textContent = value;
    status.setAttribute("data-error", failed ? "true" : "false");
  }
  function stopAudio() {
    if (previewController) { previewController.abort(); previewController = null; }
    if (audio) {
      audio.pause(); audio.removeAttribute("src"); audio.load(); audio.remove(); audio = null;
    }
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    if (playButton) { playButton.disabled = false; playButton = null; }
  }
  function disconnect(note) {
    session += 1; view += 1; token = ""; keyInput.value = ""; drafts.clear();
    list.querySelectorAll("input, textarea").forEach(function (field) { field.value = ""; });
    requests.forEach(function (controller) { controller.abort(); }); requests.clear();
    stopAudio(); loading = false; offset = 0; filter.disabled = false;
    list.replaceChildren(); library.hidden = true; more.hidden = true;
    keyInput.disabled = false; connectButton.hidden = false; connectButton.disabled = false;
    disconnectButton.hidden = true;
    message(note || "연결을 해제했습니다. 접속키와 불러온 음원을 지웠습니다.", !!note);
  }
  async function request(path, controller) {
    requests.add(controller);
    var requestSession = session;
    var response = await fetch(path, {
      method: "GET", headers: { Authorization: "Bearer " + token },
      credentials: "omit", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer", signal: controller.signal
    });
    if (requestSession !== session || controller.signal.aborted) { return null; }
    if (response.status === 401 || response.status === 403) {
      disconnect("접속키를 확인해 주세요. 검토 전용 접속키만 사용할 수 있습니다.");
      return null;
    }
    if (!response.ok) { throw new Error("Review request failed"); }
    return response;
  }
  async function preview(item, button, player, feedback) {
    stopAudio();
    var path = "/internal/v1/audio/preview/" + item.candidate_id;
    if (!/^[a-f0-9]{64}$/.test(item.candidate_id) || item.preview_url !== path) {
      feedback.textContent = "미리듣기 경로를 확인하지 못했습니다."; return;
    }
    var currentSession = session, controller = new AbortController();
    previewController = controller; playButton = button; button.disabled = true;
    feedback.textContent = "음원을 불러오고 있습니다…";
    try {
      var response = await request(path, controller);
      if (!response) { return; }
      var blob = await response.blob();
      if (currentSession !== session || controller.signal.aborted) { return; }
      if (!blob.size || blob.size > 25 * 1024 * 1024 || !/^(audio\/(ogg|mpeg|mp3|wav|x-wav)|application\/ogg)$/i.test(blob.type)) {
        throw new Error("Invalid audio response");
      }
      objectUrl = URL.createObjectURL(blob);
      audio = node("audio"); audio.controls = true; audio.preload = "none"; audio.src = objectUrl;
      audio.setAttribute("aria-label", text(item.scientific_name) + " 수집 음원 미리듣기");
      audio.addEventListener("error", function () { feedback.textContent = "음원을 재생하지 못했습니다. 원본 출처를 확인해 주세요."; });
      player.appendChild(audio); feedback.textContent = "저장된 음원입니다. 직접 들어보고 원본 출처와 대조해 주세요.";
      try { await audio.play(); } catch (error) { feedback.textContent = "재생 버튼을 눌러 음원을 들어보세요."; }
    } catch (error) {
      if (currentSession === session && !controller.signal.aborted) {
        feedback.textContent = "음원을 불러오지 못했습니다. 다시 시도해 주세요.";
      }
    } finally {
      requests.delete(controller);
      if (previewController === controller) { previewController = null; button.disabled = false; }
    }
  }
  var assessmentFields = {
    playback: ["재생 상태", {unchecked:"미확인",normal:"정상",silent:"무음",file_error:"파일 오류"}],
    source: ["출처 확인", {unchecked:"미확인",checked:"원문 확인"}],
    identification: ["종 동정 근거", {unchecked:"미확인",uploader_only:"등록자 표기만 확인",additional_evidence:"추가 동정 근거 있음",uncertain:"불확실"}],
    decision: ["검토 판정", {pending:"검토 대기",hold:"보류",candidate:"채택 후보",exclude:"제외"}]
  };
  function assessmentPanel(item, canAssess, onSaved) {
    var panel = node("details", "review-assessment"), summary = node("summary");
    var saved = node("div", "review-assessment-saved");
    function renderSaved() {
      saved.replaceChildren();
      var assessment = item.assessment;
      summary.textContent = "검토 기록 · " + (assessment && assessmentFields.decision[1][assessment.decision] || "미작성");
      if (!assessment) { saved.appendChild(node("p", "", "아직 저장된 검토 기록이 없습니다.")); return; }
      saved.appendChild(node("p", "", "저장 기록 · " + text(assessment.reviewer) + " · " + text(assessment.assessed_at)));
      Object.keys(assessmentFields).forEach(function (name) {
        var definition = assessmentFields[name];
        saved.appendChild(node("p", "", definition[0] + ": " + (definition[1][assessment[name]] || "미확인")));
      });
      if (assessment.identification_note) { saved.appendChild(node("p", "review-assessment-note", "동정 근거: " + text(assessment.identification_note))); }
      if (assessment.note) { saved.appendChild(node("p", "review-assessment-note", "메모: " + text(assessment.note))); }
    }
    renderSaved(); panel.appendChild(summary); panel.appendChild(saved);
    panel.appendChild(node("p", "review-card-subtitle", "채택 후보는 공개 승인이 아니며, 제외는 파일 삭제가 아닙니다. 재생만으로 검토 항목이 자동 체크되지 않습니다."));
    if (!canAssess) {
      panel.appendChild(node("p", "review-card-subtitle", "조회 전용 접속입니다. 검토 기록 작성용 접속키로 연결하면 기록을 저장할 수 있습니다."));
      return panel;
    }
    var editor = node("form", "review-assessment-form"), fields = {};
    editor.autocomplete = "off";
    var values = drafts.get(item.candidate_id) || item.assessment || {};
    function field(name, labelText, element) {
      var label = node("label", "", labelText);
      element.id = "assessment-" + (++fieldSequence) + "-" + name;
      element.name = name; label.htmlFor = element.id;
      editor.appendChild(label); editor.appendChild(element); fields[name] = element;
      element.addEventListener("input", remember);
      element.addEventListener("change", remember);
      return element;
    }
    function read() {
      var result = {};
      Object.keys(fields).forEach(function (name) { result[name] = fields[name].value; });
      return result;
    }
    function remember() {
      drafts.set(item.candidate_id, read());
      fields.identification_note.required = fields.identification.value === "additional_evidence";
    }
    var reviewer = field("reviewer", "검토자", node("input"));
    reviewer.type = "text"; reviewer.maxLength = 120; reviewer.required = true; reviewer.value = values.reviewer || "";
    Object.keys(assessmentFields).forEach(function (name) {
      var definition = assessmentFields[name], select = field(name, definition[0], node("select"));
      Object.keys(definition[1]).forEach(function (value) {
        var option = node("option", "", definition[1][value]); option.value = value; select.appendChild(option);
      });
      select.value = values[name] || (name === "decision" ? "pending" : "unchecked");
    });
    var identityNote = field("identification_note", "추가 동정 근거 · 추가 근거 선택 시 필수", node("textarea"));
    identityNote.rows = 3; identityNote.maxLength = 1000; identityNote.value = values.identification_note || "";
    identityNote.required = fields.identification.value === "additional_evidence";
    var note = field("note", "자유 메모 · 최대 2,000자", node("textarea"));
    note.rows = 3; note.maxLength = 2000; note.value = values.note || "";
    var submit = node("button", "send-button", "검토 기록 저장"); submit.type = "submit";
    var feedback = node("p", "review-player-status"); feedback.setAttribute("role", "status");
    if (drafts.has(item.candidate_id)) { feedback.textContent = "미저장 입력을 유지했습니다. 위의 최신 저장 기록을 확인한 뒤 저장하세요."; }
    editor.appendChild(submit); editor.appendChild(feedback); panel.appendChild(editor);
    editor.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (submit.disabled || !token) { return; }
      var input = read();
      if (!input.reviewer.trim() || input.reviewer.length > 120 || input.note.length > 2000 || input.identification_note.length > 1000 ||
          (input.identification === "additional_evidence" && !input.identification_note.trim())) {
        feedback.textContent = "검토자와 추가 동정 근거를 확인하고 입력 길이를 줄여 주세요."; return;
      }
      if ([input.reviewer, input.note, input.identification_note].some(function (value) { return value.indexOf(token) !== -1; })) {
        feedback.textContent = "접속키를 검토 내용에 넣을 수 없습니다."; return;
      }
      remember(); submit.disabled = true;
      Object.keys(fields).forEach(function (name) { fields[name].disabled = true; });
      feedback.textContent = "검토 기록을 저장하고 있습니다…";
      var currentSession = session, currentView = view, controller = new AbortController();
      requests.add(controller);
      try {
        var response = await fetch("/internal/v1/audio/assessment", {
          method:"POST", headers:{Authorization:"Bearer " + token,"Content-Type":"application/json"},
          body:JSON.stringify(Object.assign({candidate_id:item.candidate_id,expected_updated_at:item.updated_at},input)),
          credentials:"omit",cache:"no-store",redirect:"error",referrerPolicy:"no-referrer",signal:controller.signal
        });
        if (currentSession !== session || currentView !== view || controller.signal.aborted) { return; }
        if (response.status === 401 || response.status === 403) { disconnect("검토 기록 작성 권한을 확인해 주세요."); return; }
        if (response.status === 409) {
          feedback.textContent = "다른 변경과 충돌했습니다. 입력은 유지했습니다. ‘목록 새로 조회’로 최신 저장 기록을 확인한 뒤 다시 저장해 주세요."; return;
        }
        if (!response.ok) { throw new Error("Assessment save failed"); }
        var result = await response.json();
        if (currentSession !== session || currentView !== view || controller.signal.aborted) { return; }
        if (result.candidate_id !== item.candidate_id || typeof result.updated_at !== "string" || !result.assessment) { throw new Error("Invalid assessment response"); }
        item.updated_at = result.updated_at; item.assessment = result.assessment; drafts.delete(item.candidate_id);
        renderSaved(); onSaved(); feedback.textContent = "검토 기록을 저장했습니다. 공개 승인이나 파일 삭제는 실행하지 않았습니다.";
      } catch (error) {
        if (currentSession === session && currentView === view && !controller.signal.aborted) { feedback.textContent = "저장하지 못했습니다. 입력은 유지했습니다. 연결과 입력을 확인한 뒤 다시 저장해 주세요."; }
      } finally {
        requests.delete(controller);
        if (currentSession === session && currentView === view) {
          submit.disabled = false; Object.keys(fields).forEach(function (name) { fields[name].disabled = false; });
        }
      }
    });
    return panel;
  }
  function card(item, canAssess) {
    var record = item.recording || {}, review = item.review || {};
    var article = node("article", "review-card");
    var header = node("div", "review-card-header"), heading = node("div", "review-card-heading");
    heading.appendChild(node("h3", "", text(item.korean_name || item.scientific_name)));
    if (item.korean_name) { heading.appendChild(node("p", "review-scientific", text(item.scientific_name))); }
    heading.appendChild(node("p", "review-card-subtitle", "등록 종 · 수집 시 종 표기"));
    header.appendChild(heading);
    header.appendChild(node("span", "review-badge" + (item.status === "approved" || item.status === "published" ? " review-badge-reviewed" : ""), (item.status === "deferred" && item.error_code === "provider_rate_limited" ? "외부 제한으로 보류" : statuses[item.status]) || "상태 미확인"));
    article.appendChild(header);
    if (item.status === "deferred") {
      article.appendChild(node("p", "review-card-subtitle", (item.error_code === "provider_rate_limited" ? "외부 제공처의 요청 제한으로 수집을 보류했습니다. " : "수집을 보류한 항목입니다. ") + "재시도 시각이 지나도 수집 완료를 뜻하지 않습니다."));
    }
    article.appendChild(node("p", "", text(record.title || item.file_title)));
    var facts = node("dl", "review-facts");
    function fact(label, value) {
      var group = node("div", "review-fact"), detail = node("dd");
      group.appendChild(node("dt", "", label));
      if (typeof value === "string") { detail.textContent = value; } else { detail.appendChild(value); }
      group.appendChild(detail); facts.appendChild(group); return detail;
    }
    fact("종 동정", review.taxon_verified === true ? "동정 확인 기록 있음" : "독립 동정 미확인");
    fact("청취 검토", review.playback_verified === true ? "청취 확인 기록 있음" : "사람의 청취 검토 미확인");
    fact("녹음자", text(record.creator));
    fact("라이선스", safeLink(record.license_url, text(record.license_name)));
    fact("원본 출처", safeLink(record.source_url, record.source_url ? "원본 파일과 설명 보기 ↗" : "미확인"));
    fact("소리 유형", text(record.recording_type));
    fact("녹음 일시 · 원자료", text(record.recorded_at));
    fact("녹음 장소 · 원자료", text(record.location));
    fact("수집 일시", text(item.collected_at));
    var updatedDetail = fact("상태 갱신 일시", text(item.updated_at));
    if (review.reviewer) { fact("검토자", text(review.reviewer)); }
    if (review.reviewed_at) { fact("검토 일시", text(review.reviewed_at)); }
    if (item.retry_at) { fact("재시도 가능 일시", text(item.retry_at)); }
    if (item.error_code) { fact("수집 상태 코드", text(item.error_code)); }
    article.appendChild(facts);
    var player = node("div", "review-player"), feedback = node("p", "review-player-status");
    feedback.setAttribute("role", "status");
    if (item.preview_url) {
      var button = node("button", "clear-button", "미리듣기"); button.type = "button";
      button.setAttribute("aria-label", text(item.scientific_name) + " 음원 미리듣기");
      button.addEventListener("click", function () { preview(item, button, player, feedback); });
      player.appendChild(button); feedback.textContent = "눌러서 저장된 음원을 불러옵니다.";
    } else { feedback.textContent = "아직 저장된 음원이 없어 미리들을 수 없습니다."; }
    player.appendChild(feedback); article.appendChild(player);
    article.appendChild(assessmentPanel(item, canAssess, function () { updatedDetail.textContent = text(item.updated_at); }));
    return article;
  }
  async function load(reset) {
    if (!token || loading) { return; }
    loading = true; more.disabled = true; filter.disabled = true; refresh.disabled = true;
    var currentSession = session, controller = new AbortController();
    if (reset) { view += 1; offset = 0; stopAudio(); list.replaceChildren(); more.hidden = true; }
    message("수집된 음원을 불러오고 있습니다…");
    var query = new URLSearchParams({ limit: "20", offset: String(offset) });
    if (filter.value) { query.set("status", filter.value); }
    try {
      var response = await request("/internal/v1/audio/candidates?" + query, controller);
      if (!response) { return; }
      var body = await response.json();
      if (currentSession !== session) { return; }
      if (!body || !Array.isArray(body.items) || body.items.length > 50 || typeof body.has_more !== "boolean" ||
          (body.has_more && (!Number.isInteger(body.next_offset) || body.next_offset <= offset || body.next_offset > 10000))) {
        throw new Error("Invalid candidate page");
      }
      body.items.forEach(function (item) { if (item && typeof item === "object") { list.appendChild(card(item, body.can_assess === true)); } });
      library.hidden = false;
      keyInput.disabled = true; connectButton.hidden = true; disconnectButton.hidden = false;
      more.hidden = !body.has_more; offset = body.next_offset;
      if (!body.items.length && reset) { list.replaceChildren(node("p", "review-empty", "조건에 맞는 수집 음원이 없습니다.")); }
      message(body.can_assess === true ? "검토 기록을 작성할 수 있습니다. 수집 상태와 공개 승인은 변경하지 않습니다." : "조회 전용 접속입니다. 저장된 검토 기록과 음원을 확인할 수 있습니다.");
    } catch (error) {
      if (currentSession === session && !controller.signal.aborted) { message("목록을 불러오지 못했습니다. 연결을 다시 시도해 주세요.", true); }
    } finally {
      requests.delete(controller);
      if (currentSession === session) { loading = false; more.disabled = false; filter.disabled = false; refresh.disabled = false; connectButton.disabled = false; }
    }
  }
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var value = keyInput.value.trim();
    if (!value) { message("검토 전용 접속키를 입력해 주세요.", true); return; }
    disconnect(); token = value; keyInput.value = ""; connectButton.disabled = true; disconnectButton.hidden = false;
    load(true);
  });
  disconnectButton.addEventListener("click", function () { disconnect(); keyInput.focus(); });
  filter.addEventListener("change", function () { load(true); });
  more.addEventListener("click", function () { load(false); });
  refresh.addEventListener("click", function () { load(true); });
  window.addEventListener("pagehide", function () { disconnect(); });
}());
