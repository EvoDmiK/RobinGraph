/**
 * RobinGraph manual test UI. Talks only to same-origin `/health` and
 * `/v1/chat`. No innerHTML/insertAdjacentHTML/document.write is used
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
  var SAFE_IMAGE_HOSTS = ["upload.wikimedia.org", "thumb.wikimedia.org"];
  var RANK_LABELS = { order: "목", family: "과", genus: "속", species: "종", subspecies: "아종" };

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

  /**
   * Only ever return a URL that is safe to place in an `<img src>`: an
   * https URL on an allow-listed Wikimedia media host, exactly as the
   * server sent it. This is deliberately stricter than `sanitizeUrl` --
   * loading an `<img>` fetches a cross-origin resource (and leaks a
   * Referer/IP to whatever host is named) even though it can't execute
   * script, so the species photo pipeline only ever trusts the same two
   * Commons media hosts that `species_profile.py` itself validates
   * against before returning a photo. Anything else (a hostile host,
   * `javascript:`, `data:`, http, protocol-relative) returns null, which
   * callers must treat as "no photo" rather than render.
   */
  function sanitizeImageUrl(value) {
    if (typeof value !== "string") {
      return null;
    }
    var trimmed = value.trim();
    if (trimmed === "") {
      return null;
    }
    var parsed;
    try {
      parsed = new URL(trimmed);
    } catch (error) {
      return null;
    }
    if (parsed.protocol !== "https:") {
      return null;
    }
    if (SAFE_IMAGE_HOSTS.indexOf(parsed.hostname) === -1) {
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

  function boundedLimit(value) {
    var number = Number(value);
    return Number.isInteger(number) && number >= 1 && number <= 10 ? number : 10;
  }

  /** Build the exact typed body accepted by POST /v1/chat. */
  function buildChatPayload(question, intent, values) {
    var payload = { question: question, intent: intent };
    values = values || {};
    if (intent === "profile") {
      var profileName = typeof values.name === "string" ? values.name.trim() : "";
      payload.filters = profileName ? { kind: "profile", name: profileName } : { kind: "profile" };
    } else if (intent === "taxonomy") {
      var scientificName = typeof values.scientific_name === "string" ? values.scientific_name.trim() : "";
      var name = typeof values.name === "string" ? values.name.trim() : "";
      // The API accepts at most one taxonomy name field. Prefer the explicit
      // scientific name if a user happened to fill both controls.
      payload.filters = scientificName
        ? { kind: "taxonomy", scientific_name: scientificName }
        : name ? { kind: "taxonomy", name: name } : { kind: "taxonomy" };
    } else if (intent === "observations") {
      var observationFilters = { kind: "observations", limit: boundedLimit(values.limit) };
      ["taxon_key", "scientific_name", "place", "observed_from", "observed_to"].forEach(function (key) {
        if (typeof values[key] === "string" && values[key].trim()) {
          observationFilters[key] = values[key].trim();
        }
      });
      payload.filters = observationFilters;
    } else if (intent === "evidence") {
      payload.filters = {
        kind: "evidence",
        limit: boundedLimit(values.limit),
      };
    }
    return payload;
  }

  /** Convert typed route results into bounded plain-text lines for safe DOM rendering. */
  function resultSummaryLines(result) {
    if (!result || typeof result !== "object") {
      return [];
    }
    if (result.kind === "taxonomy" && result.lineage && Array.isArray(result.lineage.lineage)) {
      return result.lineage.lineage.slice(0, 20).map(function (item) {
        var rank = RANK_LABELS[item.rank] ? RANK_LABELS[item.rank] + " (" + item.rank + ")" : item.rank;
        var label = [rank, item.scientific_name].filter(Boolean).join(" · ");
        return item.korean_name
          ? label + " (" + item.korean_name + ")" + (item.korean_name_source_url ? " · 참고 국명" : "")
          : label + " · 한국어 이름 미등록";
      });
    }
    if (result.kind === "observations" && Array.isArray(result.results)) {
      return result.results.slice(0, 10).map(function (item) {
        var taxon = item.taxon && item.taxon.scientific_name ? item.taxon.scientific_name : "분류 미상";
        var place = item.place && item.place.name ? item.place.name : "장소 미상";
        var disclosure = item.coordinate_disclosure === "withheld" ? "좌표 비공개" : "공개 좌표";
        return [item.observed_at, taxon, place, disclosure].filter(Boolean).join(" · ");
      });
    }
    if (result.kind === "evidence" && result.search && Array.isArray(result.search.results)) {
      return result.search.results.slice(0, 10).map(function (item) {
        var channels = Array.isArray(item.channels) ? item.channels.join(", ") : "";
        return channels ? item.text + " [" + channels + "]" : item.text;
      });
    }
    return [];
  }

  // Trait names that read as the species' character (diet/habitat) rather
  // than a raw body measurement -- these, plus body_mass, stay visible by
  // default; every other measurement collapses. Mirrors the LABELS keys in
  // src/robingraph/retrieval/species_profile.py.
  var DIET_HABITAT_TRAIT_NAMES = [
    "habitat", "habitat_density_category", "primary_lifestyle", "trophic_niche",
    "trophic_level", "diet_category", "diet_distribution", "foraging_strata_distribution", "nocturnal",
  ];
  var PROMINENT_MEASUREMENT_NAMES = ["body_mass"];

  /**
   * Collapse duplicate trait claims (the same name/value/unit/inferred
   * reported by more than one dataset) into one group with every source
   * preserved -- mirrors birds.js's grouping so the same measurement from
   * two datasets renders as one fact with two citations, not two
   * near-identical cards.
   */
  function groupTraits(traits) {
    var groups = [];
    var index = {};
    traits.forEach(function (trait) {
      if (!trait || typeof trait !== "object") {
        return;
      }
      var key = JSON.stringify([trait.name, trait.value, trait.unit, trait.inferred]);
      if (!Object.prototype.hasOwnProperty.call(index, key)) {
        index[key] = { trait: trait, sources: [] };
        groups.push(index[key]);
      }
      index[key].sources.push(trait);
    });
    return groups;
  }

  /** Render one `.species-traits` grid of fact cards from grouped trait claims. */
  function buildTraitGrid(doc, groups) {
    var traitGrid = doc.createElement("div");
    traitGrid.className = "species-traits";
    groups.slice(0, 20).forEach(function (group) {
      var trait = group.trait;
      var traitCard = doc.createElement("div");
      traitCard.className = "trait-card";

      var label = doc.createElement("strong");
      label.textContent = trait.label || trait.name || "형질";
      traitCard.appendChild(label);

      var value = doc.createElement("span");
      value.className = "trait-value";
      var unit = trait.unit && trait.unit !== "percent" ? " " + trait.unit : "";
      value.textContent = (trait.display != null ? trait.display : "") + unit + (trait.inferred ? " (추정값)" : "");
      traitCard.appendChild(value);

      group.sources.forEach(function (sourceTrait) {
        if (!sourceTrait.citation && !sourceTrait.source_name) {
          return;
        }
        var source = doc.createElement("span");
        source.className = "trait-source";
        source.appendChild(safeLink(doc, sourceTrait.citation || sourceTrait.source_name, sourceTrait.source_url));
        if (sourceTrait.license_name) {
          var licenseSuffix = doc.createElement("span");
          licenseSuffix.textContent = " · " + sourceTrait.license_name;
          source.appendChild(licenseSuffix);
        }
        traitCard.appendChild(source);
      });
      traitGrid.appendChild(traitCard);
    });
    return traitGrid;
  }

  /** A plain `<a>` whose href is `sanitizeUrl`-checked, falling back to a `<span>` -- used by every sourced link in the species card. */
  function safeLink(doc, text, url) {
    var safeHref = sanitizeUrl(url);
    var node = doc.createElement(safeHref ? "a" : "span");
    node.textContent = text;
    if (safeHref) {
      node.href = safeHref;
      node.target = "_blank";
      node.rel = "noopener noreferrer";
    }
    return node;
  }

  /**
   * Build the inline species profile card for a `ChatSpeciesResult`
   * (`result.kind === "profile"`), rendering the exact same sourced
   * `GET /v1/taxa/profile` payload the dedicated /birds page consumes:
   * licensed photos with creator/credit/license links, trait fact cards
   * with their own citation, a vegetation-coverage caveat, and lineage
   * tucked behind a collapsible <details> (closed by default) since it is
   * reference detail, not the headline answer. Every photo src is
   * additionally gated by `sanitizeImageUrl`'s host allow-list -- an
   * `<img>` fetches a cross-origin resource even though it can't execute
   * script, so this is stricter than the plain-link `safeLink` helper
   * above. Returns null for a missing/malformed profile so a caller can
   * skip appending anything rather than render a broken card.
   */
  function buildSpeciesCard(doc, profile) {
    if (!profile || typeof profile !== "object" || !profile.taxon) {
      return null;
    }
    var taxon = profile.taxon;
    var card = doc.createElement("div");
    card.className = "species-card";

    var title = doc.createElement("p");
    title.className = "species-title";
    title.textContent = taxon.korean_name || taxon.scientific_name || "알 수 없는 종";
    card.appendChild(title);

    if (taxon.korean_name && taxon.scientific_name) {
      var scientificName = doc.createElement("p");
      scientificName.className = "species-scientific-name";
      scientificName.textContent = taxon.scientific_name;
      card.appendChild(scientificName);
    }

    var images = Array.isArray(profile.images) ? profile.images : [];
    var media = doc.createElement("div");
    media.className = "species-media";
    var renderedPhotoCount = 0;
    images.slice(0, 6).forEach(function (photo) {
      if (!photo || typeof photo !== "object") {
        return;
      }
      var imageSrc = sanitizeImageUrl(photo.image_url);
      if (!imageSrc) {
        return;
      }
      renderedPhotoCount += 1;
      var figure = doc.createElement("figure");
      var img = doc.createElement("img");
      img.src = imageSrc;
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.alt = (taxon.korean_name || taxon.scientific_name || "") + " 대표 사진: " + (photo.title || "");
      figure.appendChild(img);

      var caption = doc.createElement("figcaption");
      caption.appendChild(safeLink(doc, "원본 보기", photo.source_url));
      if (photo.creator) {
        var creditText = doc.createElement("span");
        creditText.textContent = " · " + photo.creator;
        caption.appendChild(creditText);
      }
      if (photo.license_name) {
        var separator = doc.createElement("span");
        separator.textContent = " · ";
        caption.appendChild(separator);
        caption.appendChild(safeLink(doc, photo.license_name, photo.license_url));
      }
      if (photo.credit) {
        var creditLine = doc.createElement("div");
        creditLine.textContent = photo.credit;
        caption.appendChild(creditLine);
      }
      figure.appendChild(caption);
      media.appendChild(figure);
    });
    if (renderedPhotoCount === 0) {
      var noPhoto = doc.createElement("p");
      noPhoto.className = "species-note";
      noPhoto.textContent = "라이선스가 확인된 대표 사진이 없습니다.";
      card.appendChild(noPhoto);
    } else {
      card.appendChild(media);
    }

    var traitGroups = groupTraits(Array.isArray(profile.traits) ? profile.traits : []);
    var traitNote = doc.createElement("p");
    traitNote.className = "species-note";
    traitNote.textContent =
      "수치는 자료에 기록된 종 평균입니다. 자료마다 먹이 분류가 다를 수 있습니다. 접은 날개 길이는 날개를 펼친 폭(날개폭)과 다릅니다.";
    card.appendChild(traitNote);

    if (traitGroups.length === 0) {
      var noTraits = doc.createElement("p");
      noTraits.className = "species-note";
      noTraits.textContent = "조회된 형질(특징·먹이·서식 환경) 정보가 없습니다.";
      card.appendChild(noTraits);
    } else {
      // Diet/habitat facts and the single headline measurement (body mass)
      // stay visible; every other body-measurement trait (beak/tarsus/wing/
      // tail length, etc.) is real but secondary, so it collapses behind a
      // <details> rather than turning the card into a wall of fact cards.
      var prominentGroups = traitGroups.filter(function (group) {
        return DIET_HABITAT_TRAIT_NAMES.indexOf(group.trait.name) !== -1 || PROMINENT_MEASUREMENT_NAMES.indexOf(group.trait.name) !== -1;
      });
      var remainingGroups = traitGroups.filter(function (group) {
        return prominentGroups.indexOf(group) === -1;
      });

      if (prominentGroups.length > 0) {
        card.appendChild(buildTraitGrid(doc, prominentGroups));
      }
      if (remainingGroups.length > 0) {
        var measurementsDetails = doc.createElement("details");
        measurementsDetails.className = "card-details";
        var measurementsSummary = doc.createElement("summary");
        measurementsSummary.textContent = "측정값 더 보기 (" + remainingGroups.length + ")";
        measurementsDetails.appendChild(measurementsSummary);
        measurementsDetails.appendChild(buildTraitGrid(doc, remainingGroups));
        card.appendChild(measurementsDetails);
      }
    }

    if (typeof profile.vegetation_note === "string" && profile.vegetation_note.trim()) {
      var vegetationNote = doc.createElement("p");
      vegetationNote.className = "vegetation-note";
      vegetationNote.textContent = profile.vegetation_note;
      card.appendChild(vegetationNote);
    }

    var profileWarnings = Array.isArray(profile.warnings) ? profile.warnings : [];
    if (profileWarnings.length > 0) {
      var profileWarnList = doc.createElement("ul");
      profileWarnList.className = "warnings";
      profileWarnings.forEach(function (warning) {
        var li = doc.createElement("li");
        li.textContent = "⚠ " + warning;
        profileWarnList.appendChild(li);
      });
      card.appendChild(profileWarnList);
    }

    var lineage = profile.lineage;
    var lineageItems = lineage && Array.isArray(lineage.items) ? lineage.items : [];
    if (lineageItems.length > 0) {
      var lineageDetails = doc.createElement("details");
      lineageDetails.className = "card-details";
      var lineageSummary = doc.createElement("summary");
      var sourceParts = [lineage.taxonomy_source, lineage.taxonomy_release].filter(Boolean);
      lineageSummary.textContent = "분류 계통 보기" + (sourceParts.length ? " (" + sourceParts.join(" · ") + ")" : "");
      lineageDetails.appendChild(lineageSummary);

      var lineageList = doc.createElement("ul");
      lineageList.className = "lineage-list";
      lineageItems.forEach(function (lineageItem) {
        if (!lineageItem || typeof lineageItem !== "object") {
          return;
        }
        var li = doc.createElement("li");
        var rankLabel = RANK_LABELS[lineageItem.rank] ? RANK_LABELS[lineageItem.rank] : lineageItem.rank;
        var namePart = lineageItem.korean_name
          ? lineageItem.korean_name + " · " + lineageItem.scientific_name
          : lineageItem.scientific_name;
        li.textContent = rankLabel + ": " + namePart;
        var koreanNameSourceUrl = sanitizeUrl(lineageItem.korean_name_source_url);
        if (koreanNameSourceUrl) {
          var koreanSourceLink = doc.createElement("a");
          koreanSourceLink.href = koreanNameSourceUrl;
          koreanSourceLink.textContent = " (국명 참고 출처)";
          koreanSourceLink.target = "_blank";
          koreanSourceLink.rel = "noopener noreferrer";
          li.appendChild(koreanSourceLink);
        }
        lineageList.appendChild(li);
      });
      lineageDetails.appendChild(lineageList);
      card.appendChild(lineageDetails);
    }

    return card;
  }

  function init(doc, win) {
    var form = doc.getElementById("chat-form");
    var input = doc.getElementById("question-input");
    var sendButton = doc.getElementById("send-button");
    var clearButton = doc.getElementById("clear-button");
    var history = doc.getElementById("history");
    var historyEmptyState = doc.getElementById("history-empty-state");
    var statusRegion = doc.getElementById("status-region");
    var spinner = doc.getElementById("spinner");
    var backendModeValue = doc.getElementById("backend-mode-value");
    var intent = doc.getElementById("chat-intent");
    var profileControls = doc.getElementById("profile-controls");
    var taxonomyControls = doc.getElementById("taxonomy-controls");
    var observationControls = doc.getElementById("observations-controls");
    var evidenceControls = doc.getElementById("evidence-controls");
    var promptChips = doc.getElementById("prompt-chips");
    // Prompt chips are plain static buttons declared once in index.html, so a
    // one-time snapshot of their children at init time is enough -- nothing
    // adds or removes chips afterward.
    var chipButtons = promptChips ? Array.prototype.slice.call(promptChips.children) : [];

    // Page-session only: this plain JS array is wiped on reload or clear.
    var messages = [];
    // Keep an explicit composition flag in addition to checking individual
    // key events.  A settled request may restore focus only once composition
    // has finished, so an IME confirmation is never interrupted.
    var isComposing = false;

    function setStatus(text) {
      statusRegion.textContent = text;
    }

    function setBusy(isBusy) {
      sendButton.disabled = isBusy;
      clearButton.disabled = isBusy;
      input.disabled = isBusy;
      intent.disabled = isBusy;
      chipButtons.forEach(function (chip) {
        chip.disabled = isBusy;
      });
      spinner.hidden = !isBusy;
      form.setAttribute("aria-busy", isBusy ? "true" : "false");
    }

    function restoreQuestionFocus() {
      // Focus is deliberately restored only after setBusy(false): calling it
      // while the request owns the form could disrupt an IME or steal focus
      // during the busy state.
      if (!input.disabled && !isComposing && typeof input.focus === "function") {
        input.focus();
      }
    }

    function syncModeControls() {
      profileControls.hidden = intent.value !== "profile";
      taxonomyControls.hidden = intent.value !== "taxonomy";
      observationControls.hidden = intent.value !== "observations";
      evidenceControls.hidden = intent.value !== "evidence";
    }

    function selectedFilterValues() {
      var selected = intent.value;
      if (selected === "profile") {
        return {
          name: doc.getElementById("profile-name").value,
        };
      }
      if (selected === "taxonomy") {
        return {
          scientific_name: doc.getElementById("taxonomy-scientific-name").value,
          name: doc.getElementById("taxonomy-name").value,
        };
      }
      if (selected === "observations") {
        return {
          taxon_key: doc.getElementById("observation-taxon-key").value,
          scientific_name: doc.getElementById("observation-scientific-name").value,
          place: doc.getElementById("observation-place").value,
          observed_from: doc.getElementById("observation-from").value,
          observed_to: doc.getElementById("observation-to").value,
          limit: doc.getElementById("observation-limit").value,
        };
      }
      if (selected === "evidence") {
        return {
          limit: doc.getElementById("evidence-limit").value,
        };
      }
      return {};
    }

    function scrollToLatest() {
      history.scrollTop = history.scrollHeight;
    }

    // The welcoming empty state is markup in index.html, not JS-generated,
    // so it is simply removed once real messages start and re-appended
    // verbatim on clear -- removeChild is a safe no-op if it is already
    // gone, so this never needs to track whether it is currently shown.
    function hideEmptyState() {
      if (historyEmptyState) {
        history.removeChild(historyEmptyState);
      }
    }

    function appendUserMessage(question) {
      hideEmptyState();
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
      var result = answer && answer.result;
      if (result && result.kind === "taxonomy" && result.lineage) {
        answerMetadata.push("분류 출처: " + result.lineage.taxonomy_source);
        answerMetadata.push("분류 릴리스: " + result.lineage.taxonomy_release);
        answerMetadata.push("개념집합: " + result.lineage.concept_set_id);
      }
      if (answerMetadata.length > 0) {
        var metadata = doc.createElement("p");
        metadata.className = "answer-metadata";
        metadata.textContent = answerMetadata.join(" · ");
        item.appendChild(metadata);
      }

      var resultLines = resultSummaryLines(result);
      if (resultLines.length > 0) {
        var resultList = doc.createElement("ul");
        resultList.className = "route-results";
        resultLines.forEach(function (line, index) {
          var resultItem = doc.createElement("li");
          resultItem.textContent = line;
          if (result.kind === "taxonomy") {
            var sourceUrl = sanitizeUrl(result.lineage.lineage[index].korean_name_source_url);
            if (sourceUrl) {
              var sourceLink = doc.createElement("a");
              sourceLink.href = sourceUrl;
              sourceLink.textContent = " [Wikidata]";
              sourceLink.target = "_blank";
              sourceLink.rel = "noopener noreferrer";
              resultItem.appendChild(sourceLink);
            }
          }
          resultList.appendChild(resultItem);
        });
        item.appendChild(resultList);
      }

      if (result && result.kind === "profile") {
        var speciesCard = buildSpeciesCard(doc, result.profile);
        if (speciesCard) {
          item.appendChild(speciesCard);
        }
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
      if (result && result.kind === "evidence" && result.search && Array.isArray(result.search.results)) {
        citations = result.search.results.map(function (item) {
          return {
            source_id: item.citation && item.citation.source_id,
            source_url: item.citation && item.citation.source_url,
            locator: item.citation && item.citation.locator,
            license_name: item.citation && item.citation.license_name,
            evidence_id: item.chunk_id,
          };
        });
      }
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
        .fetch("/health", { method: "GET", credentials: "omit" })
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
        .fetch("/v1/chat", {
          method: "POST",
          credentials: "omit",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildChatPayload(question, intent.value, selectedFilterValues())),
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
          restoreQuestionFocus();
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
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !isComposing) {
        event.preventDefault();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      }
    });

    input.addEventListener("compositionstart", function () {
      isComposing = true;
    });
    input.addEventListener("compositionend", function () {
      isComposing = false;
    });

    intent.addEventListener("change", syncModeControls);
    syncModeControls();

    clearButton.addEventListener("click", function () {
      messages.length = 0;
      while (history.firstChild) {
        history.removeChild(history.firstChild);
      }
      if (historyEmptyState) {
        history.appendChild(historyEmptyState);
      }
      setStatus("대화 기록을 지웠습니다.");
    });

    // Prompt chips always prefill the exact example question. Only a chip
    // explicitly marked `data-send="true"` also submits it immediately --
    // that is reserved for examples with a guaranteed route (see the
    // profile/taxonomy chips in index.html); every other chip only fills
    // the box so it never advertises a shortcut that might not route the
    // way its label implies.
    chipButtons.forEach(function (chip) {
      chip.addEventListener("click", function () {
        if (input.disabled) {
          return;
        }
        var question = chip.getAttribute("data-question");
        if (typeof question !== "string" || !question.trim()) {
          return;
        }
        input.value = question;
        if (chip.getAttribute("data-send") === "true") {
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
          } else {
            form.dispatchEvent(new Event("submit", { cancelable: true }));
          }
        } else {
          setStatus("질문을 입력창에 채웠습니다. 보내기를 눌러 전송하세요.");
          if (typeof input.focus === "function") {
            input.focus();
          }
        }
      });
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
    sanitizeImageUrl: sanitizeImageUrl,
    formatDisposition: formatDisposition,
    formatBackendMode: formatBackendMode,
    sanitizeErrorMessage: sanitizeErrorMessage,
    boundedLimit: boundedLimit,
    buildChatPayload: buildChatPayload,
    resultSummaryLines: resultSummaryLines,
    buildSpeciesCard: buildSpeciesCard,
    init: init,
  };
});
