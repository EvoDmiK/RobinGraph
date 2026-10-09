/**
 * RobinGraph manual test UI. Talks only to same-origin `/health` and
 * `/v1/chat` and read-only species exploration endpoints (`/v1/taxa/profile`,
 * `/v1/taxa/related`, `/v1/taxa/name-relations`). No innerHTML/insertAdjacentHTML/document.write is used
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
          : label + (item.english_name ? " (" + item.english_name + ")" : " · 한국어 이름 미등록");
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
    "activity_pattern",
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

  /**
   * A reviewed trait (e.g. `activity_pattern`) may carry the original
   * dataset claims it supersedes in `source_claims`. They are shown only
   * inside the collapsed source details, labelled as raw source codes with
   * the raw value (never the translated 예/아니요), so they cannot read as
   * the current conclusion.
   */
  function appendTraitProvenance(doc, sourceDetails, trait) {
    if (typeof trait.review_note === "string" && trait.review_note.trim()) {
      var note = doc.createElement("p");
      note.className = "trait-review-note";
      note.textContent = trait.review_note;
      sourceDetails.appendChild(note);
    }
    var claims = Array.isArray(trait.source_claims) ? trait.source_claims : [];
    claims.slice(0, 5).forEach(function (claim) {
      if (!claim || typeof claim !== "object" || typeof claim.name !== "string") { return; }
      var raw = claim.value;
      if (raw !== null && typeof raw === "object") { return; }
      var row = doc.createElement("p");
      row.className = "trait-source-claim";
      var label = doc.createElement("span");
      label.textContent = "원자료 분류값 (현재 결론 아님): " + claim.name + " = " + String(raw) + " · ";
      row.appendChild(label);
      row.appendChild(safeLink(doc, claim.citation || claim.source_name || "원자료", claim.source_url));
      var meta = [claim.release, claim.license_name].filter(function (part) { return typeof part === "string" && part.trim(); });
      if (meta.length) {
        var suffix = doc.createElement("span");
        suffix.textContent = " · " + meta.join(" · ");
        row.appendChild(suffix);
      }
      sourceDetails.appendChild(row);
    });
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

      var sourceDetails = doc.createElement("details");
      sourceDetails.className = "trait-source-toggle";
      var sourceSummary = doc.createElement("summary");
      sourceSummary.textContent = "자료 출처 (" + group.sources.length + ")";
      sourceDetails.appendChild(sourceSummary);
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
        sourceDetails.appendChild(source);
      });
      appendTraitProvenance(doc, sourceDetails, trait);
      if (sourceDetails.children.length > 1) { traitCard.appendChild(sourceDetails); }
      traitGrid.appendChild(traitCard);
    });
    return traitGrid;
  }

  /** Card-only layout: keep the shared facts renderer and collect its citations. */
  var CARD_BASIC_LABELS = { body_mass: "체중", diet_category: "먹이 유형", habitat: "서식 환경", primary_lifestyle: "주 생활 방식" };

  function cardTraitValue(trait) {
    var unit = trait.unit && trait.unit !== "percent" ? " " + trait.unit : "";
    var display = trait.display != null ? trait.display : "";
    if (trait.name === "body_mass" && trait.unit === "g") {
      var raw = trait.value != null ? trait.value : trait.display;
      var amount = typeof raw === "number" ? raw : typeof raw === "string" && /^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(raw.trim()) ? Number(raw.replace(/,/g, "")) : NaN;
      if (Number.isFinite(amount) && amount >= 1000) { display = (amount / 1000).toFixed(2); unit = " kg"; }
    }
    return display + unit + (trait.inferred ? " (추정값)" : "");
  }

  function buildCardTraitGrid(doc, groups, sourceTarget, scopeLabel, ensureLayout) {
    var grid = buildTraitGrid(doc, groups);
    var distributionNumbers = { diet_distribution: 0, foraging_strata_distribution: 0 };
    var pair = doc.createElement("div"); pair.className = "species-distribution-pair";
    var columns = {};
    Object.keys(distributionNumbers).forEach(function (name) {
      var column = doc.createElement("section"); column.className = "species-distribution-column";
      column.setAttribute("data-distribution-kind", name);
      var title = doc.createElement("h4"); title.textContent = name === "diet_distribution" ? "먹이 구성" : "먹이 활동 위치";
      column.appendChild(title); pair.appendChild(column); columns[name] = column;
    });
    Array.prototype.slice.call(grid.children).forEach(function (traitCard, index) {
      var trait = groups[index].trait;
      var originalValue = traitCard.children[1].textContent;
      if (trait.name === "body_mass") { traitCard.children[1].textContent = cardTraitValue(trait); }
      var originalLabel = traitCard.children[0].textContent;
      var compositionLabel = "";
      var distribution = Object.prototype.hasOwnProperty.call(distributionNumbers, trait.name);
      if (distribution) {
        compositionLabel = "자료 " + (++distributionNumbers[trait.name]);
        traitCard.className += " trait-card-distribution";
        var chart = buildDistributionChart(doc, trait, compositionLabel, scopeLabel);
        traitCard.children[0].textContent = compositionLabel;
        traitCard.children[1].textContent = "";
        traitCard.children[1].appendChild(chart);
        columns[trait.name].appendChild(traitCard);
      }
      var sourceDetails = Array.prototype.slice.call(traitCard.children).find(function (child) {
        return child.className === "trait-source-toggle";
      });
      if (!sourceDetails && !distribution) { return; }
      var entry = doc.createElement("section");
      entry.className = "species-trait-source-entry";
      var heading = doc.createElement("h5");
      heading.textContent = (scopeLabel ? scopeLabel + " · " : "") + originalLabel + (compositionLabel ? " · " + compositionLabel : "") + ": " + originalValue;
      entry.appendChild(heading);
      // The source panel keeps the original display and every recorded member,
      // including 0%, invalid values, and independently sourced distributions.
      if (distribution) {
        var raw = doc.createElement("p"); raw.className = "species-distribution-source-values";
        raw.textContent = distributionRawText(trait);
        entry.appendChild(raw);
      }
      if (sourceDetails) {
        sourceDetails.removeChild(sourceDetails.firstChild);
        while (sourceDetails.firstChild) { entry.appendChild(sourceDetails.firstChild); }
        traitCard.removeChild(sourceDetails);
      } else {
        var unconfirmed = doc.createElement("p"); unconfirmed.textContent = "출처 정보 없음"; entry.appendChild(unconfirmed);
      }
      sourceTarget.appendChild(entry);
    });
    if (ensureLayout) {
      Object.keys(CARD_BASIC_LABELS).forEach(function (name) {
        if (groups.some(function (group) { return group.trait.name === name; })) { return; }
        var row = doc.createElement("div"); row.className = "trait-card species-trait-empty";
        var label = doc.createElement("strong"); label.textContent = CARD_BASIC_LABELS[name];
        var value = doc.createElement("span"); value.className = "trait-value"; value.textContent = "자료 없음";
        row.appendChild(label); row.appendChild(value); grid.appendChild(row);
      });
    }
    if (ensureLayout || distributionNumbers.diet_distribution || distributionNumbers.foraging_strata_distribution) {
      Object.keys(columns).forEach(function (name) {
        if (columns[name].children.length === 1) {
          var empty = doc.createElement("p"); empty.className = "species-distribution-empty";
          empty.textContent = "기록된 자료 없음"; columns[name].appendChild(empty);
        }
      });
      grid.appendChild(pair);
    }
    return grid;
  }

  var DISTRIBUTION_LABELS = {
    diet_distribution: { invertebrate: "무척추동물", endotherm_vertebrate: "온혈 척추동물", ectotherm_vertebrate: "변온 척추동물",
      unknown_vertebrate: "기타 척추동물", fish: "물고기", carrion: "사체", fruit: "열매", nectar: "꽃꿀", seed: "씨앗", other_plant: "기타 식물" },
    foraging_strata_distribution: { ground: "지면", understory: "하층", midhigh: "중상층", mid_high: "중상층", canopy: "수관",
      aerial: "공중", water: "수면", pelagic: "외해", below_water_surface: "수중", around_water_surface: "수면 주변" },
  };
  var distributionTooltipSequence = 0;
  function distributionAmountText(value) {
    if (typeof value === "number") { return String(value) + "%"; }
    if (value !== null && typeof value === "object") {
      try { return JSON.stringify(value); } catch (error) { return "비율 미확인"; }
    }
    return String(value);
  }
  function distributionRawText(trait) {
    var values = trait.value;
    if (!values || typeof values !== "object" || Array.isArray(values)) { return "원자료: " + distributionAmountText(values); }
    var labels = DISTRIBUTION_LABELS[trait.name] || {};
    return Object.keys(values).map(function (key) {
      var label = Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : "미분류 항목 (" + key + ")";
      return label + " [" + key + "] " + distributionAmountText(values[key]);
    }).join(" · ") || "기록된 구성 항목 없음";
  }
  function clearDistributionTooltips(root, preserveTarget) {
    var preserved = preserveTarget;
    while (preserved && preserved !== root && typeof preserved.clearTooltip !== "function") { preserved = preserved.parentNode; }
    function visit(node) {
      if (typeof node.clearTooltip === "function" && node !== preserved) { node.clearTooltip(); }
      Array.prototype.slice.call(node.children || []).forEach(visit);
    }
    visit(root);
  }

  /** Filled donut arcs use a fixed 100% circle, never a normalized dataset sum. */
  function buildDistributionChart(doc, trait, datasetLabel, scopeLabel) {
    var chart = doc.createElement("div"); chart.className = "species-distribution-chart";
    chart.setAttribute("data-trait", trait.name);
    chart.setAttribute("data-source-label", datasetLabel);
    chart.setAttribute("data-tooltip-visible", "false");
    chart.setAttribute("aria-label", (scopeLabel ? scopeLabel + " · " : "") + (trait.label || trait.name) + " · " + datasetLabel + (trait.inferred ? " · 추정값" : ""));
    var values = trait.value;
    var objectValues = !!values && typeof values === "object" && !Array.isArray(values);
    var labels = DISTRIBUTION_LABELS[trait.name] || {};
    var entries = objectValues ? Object.keys(values).map(function (key) {
      var amount = values[key];
      return { key: key, amount: amount, valid: typeof amount === "number" && Number.isFinite(amount) && amount >= 0 && amount <= 100,
        known: Object.prototype.hasOwnProperty.call(labels, key), label: Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : "미분류 항목 (" + key + ")" };
    }) : [];
    var total = entries.reduce(function (sum, entry) { return sum + (entry.valid ? entry.amount : 0); }, 0);
    var invalid = !objectValues || !entries.length || entries.some(function (entry) { return !entry.valid; });
    var drawable = !invalid && total <= 100;
    chart.setAttribute("data-chart-state", drawable ? "ready" : "unconfirmed");
    var tooltip = doc.createElement("div"); tooltip.className = "species-distribution-tooltip";
    tooltip.setAttribute("role", "tooltip"); tooltip.id = "distribution-tooltip-" + (++distributionTooltipSequence); tooltip.hidden = true;
    var temporary = [];
    function detachTemporary() {
      temporary.forEach(function (guard) { guard.owner.removeEventListener(guard.type, chart.clearTooltip); });
      temporary = [];
    }
    chart.clearTooltip = function () {
      tooltip.hidden = true;
      chart.setAttribute("data-tooltip-visible", "false");
      chart.setAttribute("data-active-component", "");
      detachTemporary();
    };
    function temporaryGuard(owner, type) {
      if (owner && owner.addEventListener && owner.removeEventListener) {
        owner.addEventListener(type, chart.clearTooltip); temporary.push({ owner: owner, type: type });
      }
    }
    function showTooltip(entry) {
      detachTemporary();
      tooltip.textContent = entry.label + " · " + distributionAmountText(entry.amount) + (trait.inferred ? " · 추정값" : "");
      tooltip.hidden = false;
      chart.setAttribute("data-tooltip-visible", "true"); chart.setAttribute("data-active-component", entry.key);
      temporaryGuard(doc.defaultView, "blur"); temporaryGuard(doc.defaultView, "resize");
      var scrollOwner = chart.parentNode;
      while (scrollOwner) {
        if (String(scrollOwner.tagName).toLowerCase() === "dialog" || /(?:^|\s)species-card-(?:front|back)(?:\s|$)/.test(scrollOwner.className || "")) { temporaryGuard(scrollOwner, "scroll"); }
        scrollOwner = scrollOwner.parentNode;
      }
    }
    function svgNode(tag) { return doc.createElementNS ? doc.createElementNS(SVG_NS, tag) : doc.createElement(tag); }
    function point(radius, percent) {
      var angle = percent / 100 * Math.PI * 2;
      return [Math.round((60 + radius * Math.sin(angle)) * 1000000) / 1000000, Math.round((60 - radius * Math.cos(angle)) * 1000000) / 1000000];
    }
    function ringPath(start, amount) {
      var end = start + amount;
      var pieces = Math.ceil(amount / 50);
      var path = "M " + point(50, start).join(" ");
      for (var i = 1; i <= pieces; i += 1) { path += " A 50 50 0 0 1 " + point(50, start + amount * i / pieces).join(" "); }
      path += " L " + point(31, end).join(" ");
      for (var j = 1; j <= pieces; j += 1) { path += " A 31 31 0 0 0 " + point(31, end - amount * j / pieces).join(" "); }
      return path + " Z";
    }
    var colors = ["#387b63", "#7da052", "#c2a65b", "#5f8eae", "#997398", "#8e9b73", "#c48164", "#639c9d", "#a3a85c", "#6d7796"];
    // The donut segments and the 항목·비율 swatches share one palette.
    function componentColor(entry) {
      if (entry.missing) { return "#c8cdbf"; }
      var colorIndex = Object.keys(labels).indexOf(entry.key);
      return colors[(colorIndex >= 0 ? colorIndex : Object.keys(labels).length) % colors.length];
    }
    if (drawable) {
      var svg = svgNode("svg");
      svg.setAttribute("class", "species-distribution-svg"); svg.setAttribute("viewBox", "0 0 120 120");
      svg.setAttribute("role", "img"); svg.setAttribute("aria-label", (trait.label || trait.name) + " 도넛 차트 · 항목과 비율은 아래 목록에서 확인할 수 있습니다.");
      var offset = 0;
      var visible = entries.filter(function (entry) { return entry.amount > 0; });
      if (total < 100) { visible.push({ key: "unrecorded", amount: 100 - total, label: "미기록분", missing: true }); }
      visible.forEach(function (entry) {
        var segment = svgNode("path"); segment.setAttribute("class", "species-distribution-segment");
        segment.setAttribute("d", ringPath(offset, entry.amount)); segment.setAttribute("data-start-percent", String(offset));
        segment.setAttribute("data-component", entry.key); segment.setAttribute("data-percent", String(entry.amount));
        segment.setAttribute("fill", componentColor(entry));
        segment.setAttribute("aria-label", entry.label + " " + distributionAmountText(entry.amount) + (trait.inferred ? " · 추정값" : ""));
        segment.addEventListener("pointerenter", function (event) {
          if (event.pointerType !== "mouse" || event.buttons) { return; }
          var ancestor = chart;
          while (ancestor) {
            if (ancestor.getAttribute && (ancestor.getAttribute("data-dragging") === "true" || ancestor.getAttribute("aria-busy") === "true")) { return; }
            ancestor = ancestor.parentNode;
          }
          showTooltip(entry);
        });
        segment.addEventListener("pointerleave", chart.clearTooltip);
        svg.appendChild(segment); offset += entry.amount;
      });
      var center = svgNode("text"); center.setAttribute("x", "60"); center.setAttribute("y", "61"); center.setAttribute("text-anchor", "middle");
      center.setAttribute("class", "species-distribution-total"); center.setAttribute("aria-hidden", "true"); center.textContent = Math.round(total * 1000000) / 1000000 + "%"; svg.appendChild(center);
      var centerLabel = svgNode("text"); centerLabel.setAttribute("x", "60"); centerLabel.setAttribute("y", "74"); centerLabel.setAttribute("text-anchor", "middle");
      centerLabel.setAttribute("class", "species-distribution-total-label"); centerLabel.setAttribute("aria-hidden", "true"); centerLabel.textContent = "기록 비율"; svg.appendChild(centerLabel);
      chart.appendChild(svg);
    } else {
      var fallback = doc.createElement("p"); fallback.className = "species-distribution-fallback";
      fallback.textContent = total > 100 ? "합계 " + Math.round(total * 1000000) / 1000000 + "% · 비율 확인 필요" : "구성 비율 확인 필요";
      chart.appendChild(fallback);
    }
    chart.appendChild(tooltip);
    // The dataset label ("자료 1") stays in data-source-label, the aria-label and the
    // sources toggle; the card face only shows caveats, and nothing when there are none.
    var caveats = [];
    if (drawable && total < 100) { caveats.push("미기록분 " + Math.round((100 - total) * 1000000) / 1000000 + "%"); }
    if (trait.inferred) { caveats.push("추정값"); }
    if (entries.some(function (entry) { return !entry.known; })) { caveats.push("미분류 항목 포함"); }
    var note = doc.createElement("p"); note.className = "species-distribution-note";
    note.textContent = caveats.join(" · "); note.hidden = caveats.length === 0;
    chart.appendChild(note);
    var details = doc.createElement("details"); details.className = "species-distribution-values";
    var summary = doc.createElement("summary"); summary.textContent = "항목·비율"; details.appendChild(summary);
    var list = doc.createElement("ul");
    entries.forEach(function (entry) {
      var row = doc.createElement("li"); row.setAttribute("data-component", entry.key);
      if (entry.valid) { row.setAttribute("data-raw-percent", String(entry.amount)); }
      if (entry.valid && entry.amount === 0) { row.className = "species-distribution-zero"; }
      var swatch = svgNode("svg"); swatch.setAttribute("class", "species-distribution-swatch");
      swatch.setAttribute("viewBox", "0 0 10 10"); swatch.setAttribute("aria-hidden", "true");
      var dot = svgNode("circle"); dot.setAttribute("cx", "5"); dot.setAttribute("cy", "5"); dot.setAttribute("r", "4.5");
      dot.setAttribute("fill", componentColor(entry)); swatch.appendChild(dot); row.appendChild(swatch);
      var name = doc.createElement("span"); name.className = "species-distribution-name"; name.textContent = entry.label; row.appendChild(name);
      // The separator keeps the plain-text form "항목 · 40%" for text extraction; CSS hides it.
      var separator = doc.createElement("span"); separator.className = "species-distribution-sep"; separator.textContent = " · "; row.appendChild(separator);
      var amountText = doc.createElement("span"); amountText.className = "species-distribution-amount";
      amountText.textContent = distributionAmountText(entry.amount) + (entry.valid ? "" : " · 비율 미확인"); row.appendChild(amountText);
      list.appendChild(row);
    });
    if (!entries.length) { var noData = doc.createElement("li"); noData.textContent = "원자료: " + distributionAmountText(values); list.appendChild(noData); }
    details.appendChild(list); chart.appendChild(details);
    chart.addEventListener("pointercancel", chart.clearTooltip);
    chart.addEventListener("pointerdown", chart.clearTooltip);
    chart.addEventListener("pointerleave", chart.clearTooltip);
    return chart;
  }

  // Habitat emblems keyed by the raw AVONET `habitat` trait value (not the
  // Korean display string, which may change). Each is a 24x24 stroked SVG
  // path so it stays crisp and inherits `currentColor`; `glyph` is the
  // plain-text fallback for documents without createElementNS.
  // Split so the file carries no absolute URL literal (see chat_ui tests).
  var SVG_NS = ["http:", "", "www.w3.org", "2000", "svg"].join("/");
  var HABITAT_EMBLEMS = {
    forest: { slug: "forest", label: "숲", glyph: "▲",
      path: "M8 3l-5 8h3l-4 6h12l-4-6h3z M8 17v4 M17 6l-4 6h2.5l-3 5h9l-3-5H21z M17 17v4" },
    shrubland: { slug: "shrubland", label: "관목 지대", glyph: "♣",
      path: "M3 19c0-3 2-5 4.5-5 .8-2.5 3-3.6 5-3 2-1.6 5-1 6 1.6 2 .6 3 2.4 3 4.4z M2 21h20 M9 19v-3 M15 19v-4" },
    woodland: { slug: "woodland", label: "성긴 숲", glyph: "♠",
      path: "M12 21v-8 M12 15l-3-2.5 M12 16l3-2 M12 3a6 6 0 0 0-6 6 4 4 0 0 0 4 4h4a4 4 0 0 0 4-4 6 6 0 0 0-6-6z M3 21h18" },
    grassland: { slug: "grassland", label: "초지", glyph: "ψ",
      path: "M2 21h20 M5 21c0-4-1-7-3-9 M8.5 21c0-5 1-9 3-12 M12.5 21c0-4 1.5-7 4.5-9 M16.5 21c0-3 2-6 5-7" },
    rock: { slug: "rock", label: "바위 지대", glyph: "◭",
      path: "M2 21l5-9 4 3 3.5-8L22 21z M11 15l2.5 6 M7 12l1 4" },
    wetland: { slug: "wetland", label: "습지", glyph: "≈",
      path: "M2 18c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0 M2 21.5c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0 M8 15V9 M8 3.5c-1 0-1.6 1.2-1.6 2.8S7 9 8 9s1.6-1.2 1.6-2.7S9 3.5 8 3.5z M13 15V6 M17 15c0-3 1-5 3.5-6.5" },
    human_modified: { slug: "human-modified", label: "인공·변형 환경", glyph: "⌂",
      path: "M2 21h20 M3.5 21V11l6-5 6 5v10 M15.5 21V8H21v13 M7.5 21v-5h4v5 M17.5 11h1.5 M17.5 14.5h1.5" },
    coastal: { slug: "coastal", label: "해안", glyph: "⛰",
      path: "M2 21V11l4-3 3.5 4V21 M10 16.5c2-1.5 4-1.5 6 0s4 1.5 6 0 M10 20.5c2-1.5 4-1.5 6 0s4 1.5 6 0 M15 6a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0" },
    marine: { slug: "marine", label: "바다", glyph: "〰",
      path: "M2 15.5c3 0 4.5-8 9.5-8 3 0 5 2 5 4.6 0 2-1.4 3.2-3 3.2s-2.6-1-2.6-2.2 M2 20c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0 M18 6.5c1.5-1.8 2.5-2 4-2" },
    riverine: { slug: "riverine", label: "하천", glyph: "§",
      path: "M7 2c-4 4 4 6 0 10s4 6 0 10 M15 2c-4 4 4 6 0 10s4 6 0 10 M10.5 7.5h1.5 M10 16.5h1.5" },
    desert: { slug: "desert", label: "사막", glyph: "☼",
      path: "M2 21h20 M9 21V6a1.5 1.5 0 0 1 3 0v15 M9 12H7a1.5 1.5 0 0 1-1.5-1.5V8.5 M12 14h2a1.5 1.5 0 0 0 1.5-1.5V10 M17 5a2 2 0 1 0 4 0 2 2 0 1 0-4 0" },
  };
  var UNKNOWN_HABITAT_EMBLEM = { slug: "unknown", label: "서식 환경 미확인", glyph: "?",
    path: "M20 3C12 3 6 9 6 17l-2.5 3.5 M6 17c6.5 0 12-4.5 14-14 M9.5 13.5l5-5 M8 16l3.5-.5" };

  /**
   * Choose the habitat emblem from the profile's first `habitat` trait whose
   * raw value is in the known AVONET vocabulary. Matching is
   * case/whitespace-insensitive; anything else falls back to a neutral
   * "unknown" emblem rather than guessing.
   */
  function habitatEmblemInfo(profile) {
    var traits = profile && Array.isArray(profile.traits) ? profile.traits : [];
    for (var i = 0; i < traits.length; i += 1) {
      var trait = traits[i];
      if (!trait || trait.name !== "habitat" || typeof trait.value !== "string") { continue; }
      var key = trait.value.trim().toLowerCase().replace(/[\s-]+/g, "_");
      if (Object.prototype.hasOwnProperty.call(HABITAT_EMBLEMS, key)) {
        var known = HABITAT_EMBLEMS[key];
        return { slug: known.slug, label: known.label, glyph: known.glyph, path: known.path, known: true };
      }
    }
    var unknown = UNKNOWN_HABITAT_EMBLEM;
    return { slug: unknown.slug, label: unknown.label, glyph: unknown.glyph, path: unknown.path, known: false };
  }

  function buildHabitatEmblem(doc, info) {
    var emblem = doc.createElement("span");
    emblem.className = "species-emblem habitat-" + info.slug;
    var accessibleLabel = info.known ? "서식 환경: " + info.label : info.label;
    emblem.setAttribute("role", "img");
    emblem.setAttribute("aria-label", accessibleLabel);
    emblem.setAttribute("title", accessibleLabel);
    if (typeof doc.createElementNS === "function") {
      var svg = doc.createElementNS(SVG_NS, "svg");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("focusable", "false");
      var path = doc.createElementNS(SVG_NS, "path");
      path.setAttribute("d", info.path);
      svg.appendChild(path);
      emblem.appendChild(svg);
    } else {
      emblem.textContent = info.glyph;
    }
    return emblem;
  }

  // Feeding-ecology icons. Keys are food *components*; combined source
  // categories (VertFishScav, PlantSeed, FruiNect) get their own single
  // broad icon so a combined category never implies every member is eaten.
  // Paths are 24x24 strokes that inherit `currentColor`.
  var DIET_ICONS = {
    invertebrate: { label: "무척추동물", glyph: "✱",
      path: "M12 7a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0v-5a3 3 0 0 1 3-3z M10 5L8 3 M14 5l2-2 M9 11H5 M9 15l-4 2 M15 11h4 M15 15l4 2" },
    vertebrate: { label: "척추동물", glyph: "⌇",
      path: "M8.5 6.5l9 9 M6.5 4.5a2 2 0 1 0-2 2 2 2 0 1 0 2 2l2-2 M17.5 19.5a2 2 0 1 0 2-2 2 2 0 1 0-2-2l-2 2" },
    fish: { label: "물고기", glyph: "≻",
      path: "M3 12c3-4 8-5 12-3l4-3v12l-4-3c-4 2-9 1-12-3z M8 11.5h.01" },
    carrion: { label: "사체", glyph: "☠",
      path: "M12 3a7 7 0 0 0-7 7v3l2 2v4h10v-4l2-2v-3a7 7 0 0 0-7-7z M9 11h.01 M15 11h.01 M10 19v-3 M14 19v-3" },
    fruit: { label: "열매", glyph: "●",
      path: "M12 9c-4 0-6 3-6 6s2 6 6 6 6-3 6-6-2-6-6-6z M12 9c0-3 1-5 3-6" },
    nectar: { label: "꽃꿀", glyph: "✿",
      path: "M10 12a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M12 4v4 M12 16v4 M4 12h4 M16 12h4" },
    seed: { label: "씨앗", glyph: "◊",
      path: "M12 3c4 3 5 9 0 18-5-9-4-15 0-18z M12 7v10" },
    plant: { label: "기타 식물", glyph: "♣",
      path: "M12 21v-9 M12 12c0-4 3-7 7-7 0 4-3 7-7 7z M12 15c0-3-2-5-5-5 0 3 2 5 5 5z" },
    vert_fish_scav: { label: "척추동물·물고기·사체 (묶음 범주)", glyph: "▣", broad: true,
      path: "M4 4h16v16H4z M8.5 9h.01 M15.5 9h.01 M12 15h.01" },
    plant_seed: { label: "식물·씨앗 (묶음 범주)", glyph: "▤", broad: true,
      path: "M4 4h16v16H4z M12 18v-6 M12 12c0-3 2-5 5-5 M12 14c0-2-2-4-4-4" },
    fruit_nectar: { label: "열매·꽃꿀 (묶음 범주)", glyph: "▥", broad: true,
      path: "M4 4h16v16H4z M10 14a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M12 8v4" },
    omnivore: { label: "잡식", glyph: "⊕",
      path: "M6 3v8 M9 3v8 M6 7h3 M7.5 11v10 M17 3c-2 2-2 6 0 8v10" },
    aquatic_predator: { label: "수생동물 포식", glyph: "≋",
      path: "M2 17c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0 M12 3v9 M9 9l3 3 3-3" },
    herbivore_aquatic: { label: "수생 초식", glyph: "≈",
      path: "M12 15V8 M12 8c0-3 2-5 5-5 M2 18c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0" },
    herbivore_terrestrial: { label: "육상 초식", glyph: "♠",
      path: "M2 21h20 M12 21v-9 M12 12c0-4 3-7 7-7 0 4-3 7-7 7z" },
  };
  // AVONET Diet distribution members (percentages).
  var DIET_DISTRIBUTION_KEYS = {
    invertebrate: "invertebrate", endotherm_vertebrate: "vertebrate", ectotherm_vertebrate: "vertebrate",
    unknown_vertebrate: "vertebrate", fish: "fish", carrion: "carrion", fruit: "fruit", nectar: "nectar",
    seed: "seed", other_plant: "plant",
  };
  var DIET_CATEGORY_KEYS = {
    Invertebrate: "invertebrate", VertFishScav: "vert_fish_scav", PlantSeed: "plant_seed",
    FruiNect: "fruit_nectar", Omnivore: "omnivore",
  };
  var TROPHIC_NICHE_KEYS = {
    Invertivore: "invertebrate", Vertivore: "vertebrate", "Aquatic predator": "aquatic_predator",
    Frugivore: "fruit", Nectarivore: "nectar", Granivore: "seed", Omnivore: "omnivore",
    Scavenger: "carrion", "Herbivore aquatic": "herbivore_aquatic", "Herbivore terrestrial": "herbivore_terrestrial",
  };

  function sourcedTraits(profile, name) {
    var traits = profile && Array.isArray(profile.traits) ? profile.traits : [];
    return traits.filter(function (trait) {
      return trait && trait.name === name && typeof trait.source_name === "string" && trait.source_name.trim() &&
        sanitizeUrl(trait.source_url);
    });
  }

  /**
   * Feeding icons from sourced diet traits only -- never from habitat or the
   * species name. A sourced `diet_distribution` with positive finite
   * percentages wins and yields one icon per member (vertebrate subgroups
   * merge into one 척추동물 icon; fish keeps its own icon and, when no other
   * vertebrate share is present, a labelled parent 척추동물 grouping icon).
   * Otherwise the sourced `diet_category`, then `trophic_niche`, gives one
   * icon each. Unknown values, null and 0% are dropped; duplicates merge.
   */
  function dietIconInfo(profile) {
    var icons = [];
    var byKey = {};
    var sources = [];
    function add(key, percent, source, detail) {
      if (!Object.prototype.hasOwnProperty.call(DIET_ICONS, key)) { return; }
      if (!byKey[key]) {
        var meta = DIET_ICONS[key];
        byKey[key] = { key: key, label: meta.label, path: meta.path, glyph: meta.glyph, broad: !!meta.broad,
          percent: null, parentGroup: false, detail: detail || null };
        icons.push(byKey[key]);
      }
      if (typeof percent === "number") { byKey[key].percent = (byKey[key].percent || 0) + percent; }
      if (source && sources.indexOf(source) === -1) { sources.push(source); }
    }
    // Exactly one distribution record is the display basis: the first
    // sourced record with at least one valid, recognized positive member.
    // Percentages from different records (even identical duplicates) are
    // never added together; other records stay in the card's trait panels.
    function validMembers(trait) {
      var value = trait.value;
      if (!value || typeof value !== "object" || Array.isArray(value)) { return []; }
      return Object.keys(value).filter(function (member) {
        var amount = value[member];
        return Object.prototype.hasOwnProperty.call(DIET_DISTRIBUTION_KEYS, member) &&
          typeof amount === "number" && isFinite(amount) && amount > 0 && amount <= 100;
      });
    }
    var distributions = sourcedTraits(profile, "diet_distribution").filter(function (trait) {
      return validMembers(trait).length > 0;
    });
    var otherDistributionCount = Math.max(0, distributions.length - 1);
    if (distributions.length) {
      var chosen = distributions[0];
      validMembers(chosen).forEach(function (member) {
        add(DIET_DISTRIBUTION_KEYS[member], chosen.value[member], chosen);
      });
    }
    var basis = icons.length ? "distribution" : null;
    if (basis) {
      icons.sort(function (a, b) { return b.percent - a.percent; });
      if (byKey.fish && !byKey.vertebrate) {
        add("vertebrate", null, null);
        byKey.vertebrate.parentGroup = true;
        byKey.vertebrate.detail = "상위 묶음 · 물고기 포함";
      }
    } else {
      [["diet_category", DIET_CATEGORY_KEYS], ["trophic_niche", TROPHIC_NICHE_KEYS]].some(function (pair) {
        sourcedTraits(profile, pair[0]).forEach(function (trait) {
          var raw = typeof trait.value === "string" ? trait.value.trim() : "";
          if (Object.prototype.hasOwnProperty.call(pair[1], raw)) { add(pair[1][raw], null, trait); }
        });
        if (icons.length) { basis = pair[0]; }
        return icons.length > 0;
      });
    }
    icons.forEach(function (icon) {
      var text = icon.label;
      if (icon.percent != null) { text += " " + Math.round(icon.percent * 10) / 10 + "%"; }
      if (icon.detail) { text += " (" + icon.detail + ")"; }
      icon.text = "먹이: " + text;
    });
    return { icons: icons, basis: basis, sources: sources, otherDistributionCount: otherDistributionCount };
  }

  var DIET_BASIS_LABELS = {
    distribution: "먹이 구성 비율", diet_category: "먹이 유형 범주", trophic_niche: "먹이 생태 범주",
  };

  function buildDietIcons(doc, info) {
    var list = doc.createElement("ul");
    list.className = "species-diet-icons";
    list.setAttribute("aria-label", "먹이 아이콘 · " + (DIET_BASIS_LABELS[info.basis] || "자료 없음"));
    info.icons.forEach(function (icon) {
      var item = doc.createElement("li");
      item.className = "diet-icon diet-" + icon.key.replace(/_/g, "-") + (icon.broad ? " diet-broad" : "") + (icon.parentGroup ? " diet-parent" : "");
      item.setAttribute("title", icon.text);
      var symbol = doc.createElement("span");
      symbol.className = "diet-icon-symbol";
      symbol.setAttribute("aria-hidden", "true");
      if (typeof doc.createElementNS === "function") {
        var svg = doc.createElementNS(SVG_NS, "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("focusable", "false");
        var path = doc.createElementNS(SVG_NS, "path");
        path.setAttribute("d", icon.path);
        svg.appendChild(path);
        symbol.appendChild(svg);
      } else {
        symbol.textContent = icon.glyph;
      }
      item.appendChild(symbol);
      var text = doc.createElement("span");
      text.className = "diet-icon-label";
      text.textContent = icon.text;
      item.appendChild(text);
      list.appendChild(item);
    });
    return list;
  }

  /** Legend + source links for the diet icons (card back). */
  function buildDietLegend(doc, info) {
    var details = doc.createElement("section");
    details.className = "species-diet-legend";
    var summary = doc.createElement("h4");
    summary.textContent = "먹이 아이콘 기준 · 출처";
    details.appendChild(summary);
    var basis = doc.createElement("p");
    basis.textContent = info.basis
      ? "기준: " + DIET_BASIS_LABELS[info.basis] + ". 서식지나 이름으로 먹이를 추정하지 않습니다." +
        (info.basis !== "distribution" ? " 묶음 범주는 구성 항목 각각을 먹는다는 뜻이 아닙니다." : "") +
        (info.basis === "distribution" && info.otherDistributionCount > 0
          ? " 먹이 구성 자료가 여럿이면 아래 한 자료의 비율만 표시하며, 서로 다른 자료의 비율을 더하지 않습니다. 나머지 자료는 형질 출처에서 확인할 수 있습니다."
          : "")
      : "출처가 확인된 먹이 자료가 없어 먹이 아이콘을 표시하지 않습니다.";
    details.appendChild(basis);
    if (info.icons.length) {
      details.appendChild(buildDietIcons(doc, info));
    }
    info.sources.forEach(function (trait) {
      var row = doc.createElement("p");
      row.appendChild(safeLink(doc, trait.source_name, trait.source_url));
      var meta = [trait.label || trait.name, trait.release, trait.license_name].filter(Boolean).join(" · ");
      if (meta) {
        var span = doc.createElement("span");
        span.textContent = " · " + meta;
        row.appendChild(span);
      }
      details.appendChild(row);
    });
    return details;
  }

  // IUCN Red List categories with the Korean labels used by the national
  // red list. `tier` drives the card palette only; it is a visual cue for
  // assessed extinction risk and never a measure of how many birds are
  // actually around a given place.
  var CONSERVATION_CATEGORIES = {
    LC: { label: "관심대상", tier: "lc" },
    NT: { label: "준위협", tier: "nt" },
    VU: { label: "취약", tier: "vu" },
    EN: { label: "위기", tier: "en" },
    CR: { label: "위급", tier: "cr" },
    EW: { label: "야생절멸", tier: "ew" },
    EX: { label: "절멸", tier: "ex" },
    DD: { label: "정보부족", tier: "unconfirmed" },
    NE: { label: "미평가", tier: "unconfirmed" },
  };

  // Source identity and URL/release completeness are separate from risk color.
  // These checks verify provenance fields, never a live IUCN assessment.
  var PICA_SERICA_OVERRIDE_NOTE = "사용자 요청으로 까치의 앱 표시 등급을 LC로 임시 보정했습니다. 원자료의 NE와 평가 종 범위 확인 필요 상태는 보존합니다.";

  function isPicaSericaManualOverride(data) {
    var original = data.original_snapshot;
    return data.evidence_kind === "manual_override" && data.assessment_status === "manual_override" &&
      data.source_id === "robingraph-manual-pica-serica" && data.source_name === "RobinGraph 임시 보정" &&
      data.source_release === "2026-10-09" && data.source_url === null &&
      data.category === "LC" && data.category_raw === "LC" && data.label === "관심대상" &&
      data.independently_verified === false && data.taxon_id === "avilist-taxon:v2025b:20193" &&
      data.scientific_name === "Pica serica" && data.taxonomy_release === "v2025b" &&
      data.concept_set_id === "rg:concept-set:avilist-v2025b" && data.taxonomy_category_raw === "NE" &&
      data.quality_note === PICA_SERICA_OVERRIDE_NOTE && data.override_reason === PICA_SERICA_OVERRIDE_NOTE &&
      !!original && typeof original === "object" && original.evidence_kind === "taxonomy_snapshot" &&
      original.source_id === "avilist-v2025b" && original.source_release === "v2025b" &&
      original.snapshot_sha256 === "3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411" &&
      original.category === "NE" && typeof original.category_raw === "string" && original.category_raw.trim() === "NE" &&
      original.assessment_status === "needs_review" && original.independently_verified === false &&
      conservationInfo(original).snapshot;
  }

  function appendManualOverrideEvidence(doc, parent, data) {
    var reason = doc.createElement("p");
    reason.textContent = data.override_reason;
    parent.appendChild(reason);
    var limitation = doc.createElement("p");
    limitation.textContent = "앱 표시만 임시 보정한 값입니다. 공식 평가를 새로 확인한 결과가 아닙니다.";
    parent.appendChild(limitation);
    var original = doc.createElement("p");
    original.textContent = "원자료: AviList NE · 릴리스 " + data.original_snapshot.source_release + " · 평가 자료 연결 확인 필요 · ";
    original.appendChild(safeLink(doc, data.original_snapshot.source_name, data.original_snapshot.source_url));
    parent.appendChild(original);
  }

  function isLinkedRedListChecklist(data) {
    var digits = /^[1-9][0-9]*$/;
    return data.evidence_kind === "red_list_checklist" &&
      data.assessment_status === "linked_checklist" && data.independently_verified === false &&
      data.source_id === "gbif-iucn-2026-1" && data.source_release === "2026-1" &&
      data.source_name === "IUCN Red List · GBIF public checklist" &&
      data.source_url === "https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3" &&
      data.snapshot_sha256 === "2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d" &&
      data.mapping_method === "exact_avilist_birdlife_sis_and_scientific_name" &&
      data.assessment_scope === "global" &&
      data.license_name === "CC BY 4.0" && data.license_url === "https://creativecommons.org/licenses/by/4.0/" &&
      typeof data.sis_id === "string" && digits.test(data.sis_id) &&
      typeof data.assessment_id === "string" && digits.test(data.assessment_id) &&
      data.assessment_reference_url === "https://www.iucnredlist.org/species/" + data.sis_id + "/" + data.assessment_id &&
      (data.assessment_year == null ||
        (Number.isInteger(data.assessment_year) && data.assessment_year >= 1900 && data.assessment_year <= 2026)) &&
      [data.assessment_citation, data.publisher, data.citation].every(function (value) {
        return typeof value === "string" && !!value.trim();
      }) &&
      typeof data.category === "string" && data.category !== "NE" &&
      Object.prototype.hasOwnProperty.call(CONSERVATION_CATEGORIES, data.category) &&
      data.category_raw === data.category;
  }

  function conservationInfo(conservation, taxon) {
    var data = conservation && typeof conservation === "object" ? conservation : {};
    if (isPicaSericaManualOverride(data) && (arguments.length < 2 ||
        (taxon && taxon.taxon_id === data.taxon_id && taxon.scientific_name === data.scientific_name && taxon.rank === "species"))) {
      return { category: "LC", label: "관심대상", tier: "lc", verified: false, sourceVerified: false,
        snapshot: false, checklist: false, manualOverride: true, note: PICA_SERICA_OVERRIDE_NOTE,
        badgeText: "관심대상 (LC) · 임시 보정" };
    }
    var checklist = isLinkedRedListChecklist(data);
    var url = sanitizeUrl(data.source_url), parsed = null;
    try { parsed = url ? new URL(url) : null; } catch (_) { /* unconfirmed */ }
    var hosts = ["avilist.org", "www.avilist.org", "explore.avilist.org",
      "iucnredlist.org", "www.iucnredlist.org", "nrl.iucnredlist.org", "datazone.birdlife.org"];
    var sourceVerified = checklist || !!(parsed && parsed.protocol === "https:" && !parsed.username && !parsed.password &&
      (!parsed.port || parsed.port === "443") && hosts.indexOf(parsed.hostname) !== -1 &&
      typeof data.source_name === "string" && data.source_name.trim() &&
      typeof data.source_release === "string" && data.source_release.trim());
    if ((data.evidence_kind === "red_list_checklist" && !checklist) || data.evidence_kind === "manual_override") { sourceVerified = false; }
    var aviListHost = parsed && ["avilist.org", "www.avilist.org", "explore.avilist.org"].indexOf(parsed.hostname) !== -1;
    var snapshot = !!(sourceVerified && aviListHost &&
      ((data.evidence_kind === "taxonomy_snapshot" && data.source_id === "avilist-" + data.source_release) ||
       (!data.evidence_kind && data.source_name === "AviList global avian checklist")));
    var category = data.category;
    var raw = typeof data.category_raw === "string" ? data.category_raw.trim().toUpperCase() : category;
    var qualifierMatch = typeof raw === "string" ? /^CR\s*\((PEW?)\)$/.exec(raw) : null;
    if (typeof category === "string" && /^CR\s*\((PEW?)\)$/.test(category)) { category = "CR"; }
    var base = { category: null, label: "미확인", tier: "unconfirmed", verified: false,
      sourceVerified: sourceVerified, snapshot: snapshot, checklist: checklist, manualOverride: false, badgeText: "멸종위기 등급 미확인" };
    if ((data.evidence_kind && data.evidence_kind !== "taxonomy_snapshot" && !checklist) ||
        (data.evidence_kind === "taxonomy_snapshot" && !snapshot)) { return base; }
    if (!sourceVerified || typeof category !== "string" ||
        !Object.prototype.hasOwnProperty.call(CONSERVATION_CATEGORIES, category)) { return base; }
    if (typeof data.category_raw === "string") {
      var rawCode = /^CR\s*\(PEW?\)$/.test(raw) ? "CR" : raw;
      if (rawCode !== category) { return base; }
    }
    if (snapshot && category === "NE") {
      return Object.assign(base, { category: "NE", label: "평가 연결 확인 필요",
        badgeText: "평가 자료 연결 확인 필요 (AviList NE)" });
    }
    var known = CONSERVATION_CATEGORIES[category];
    var qualifier = category === "CR" && qualifierMatch ?
      (qualifierMatch[1] === "PE" ? " · 절멸 가능성" : " · 야생절멸 가능성") : "";
    return Object.assign(base, { category: category, label: known.label, tier: known.tier,
      verified: known.tier !== "unconfirmed",
      badgeText: "IUCN 적색목록 " + known.label + " (" + category + ")" + qualifier +
        (checklist ? " · 공개 평가목록 기준" : (snapshot ? " · 자료 기준" : "")) });
  }

  var CONSERVATION_NOTE =
    "적색목록 등급은 멸종 위험 평가 결과이며, 특정 지역에서 실제로 보기 드문지(개체 수·관찰 빈도)를 뜻하지 않습니다. " +
    "표시된 등급은 출처 자료의 릴리스 기준이므로 IUCN의 현재 최신 평가와 다를 수 있습니다. 카드 색상은 이 등급만 반영합니다.";

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

  /** Keep source materials intact so async refreshes can re-elect unique links. */
  function buildCombinedAnswerSources(doc, initialMaterial) {
    var panel = doc.createElement("details");
    panel.className = "species-answer-sources";
    var summary = doc.createElement("summary");
    panel.appendChild(summary);
    var materials = [];
    function sourceText(node) {
      if (node.childNodes) { return node.textContent || ""; }
      return (node.textContent || "") + Array.prototype.slice.call(node.children || []).map(sourceText).join(" ");
    }
    function sourceUrls(node) {
      var urls = [];
      function visit(item) {
        if (String(item.tagName || "").toLowerCase() === "a" && sanitizeUrl(item.href)) { urls.push(item.href); }
        Array.prototype.slice.call(item.children || []).forEach(visit);
      }
      visit(node);
      return urls;
    }
    function copy(node, seenUrls, seenRows) {
      if (node.nodeType === 3) { return doc.createTextNode(node.nodeValue); }
      var tag = String(node.tagName || "").toLowerCase();
      if (!tag) { return null; }
      var contextRow = tag === "p" || tag === "li" || node.className === "species-trait-source-entry" || node.className === "species-photo-source";
      if (contextRow) {
        var fingerprint = JSON.stringify([tag, node.className || "", sourceText(node), sourceUrls(node)]);
        if (seenRows[fingerprint]) { return null; }
        seenRows[fingerprint] = true;
      }
      var url = tag === "a" ? sanitizeUrl(node.href) : null;
      var duplicate = url && seenUrls[url];
      if (url && !duplicate) { seenUrls[url] = true; }
      var targetTag = duplicate ? "span" : tag;
      var clone = node.namespaceURI === SVG_NS && doc.createElementNS
        ? doc.createElementNS(SVG_NS, targetTag) : doc.createElement(targetTag);
      var attributes = node.attributes || {};
      if (typeof attributes.length === "number") {
        Array.prototype.slice.call(attributes).forEach(function (attribute) {
          if (!duplicate || ["href", "target", "rel"].indexOf(attribute.name) === -1) { clone.setAttribute(attribute.name, attribute.value); }
        });
      } else {
        Object.keys(attributes).forEach(function (name) {
          if (!duplicate || ["href", "target", "rel"].indexOf(name) === -1) { clone.setAttribute(name, attributes[name]); }
        });
      }
      if (typeof node.className === "string") { clone.className = node.className; }
      if (url && !duplicate) { clone.href = url; clone.target = "_blank"; clone.rel = "noopener noreferrer"; }
      if (!node.childNodes) { clone.textContent = node.textContent || ""; }
      Array.prototype.slice.call(node.childNodes || node.children || []).forEach(function (child) {
        var copied = copy(child, seenUrls, seenRows);
        if (copied) { clone.appendChild(copied); }
      });
      return clone;
    }
    panel.refreshSources = function () {
      while (panel.children.length > 1) { panel.removeChild(panel.children[1]); }
      var urls = Object.create(null);
      var rows = Object.create(null);
      materials.forEach(function (material) {
        Array.prototype.slice.call(material.children || []).forEach(function (child) {
          if (String(child.tagName).toLowerCase() === "summary") { return; }
          var clone = copy(child, urls, rows);
          if (clone) { panel.appendChild(clone); }
        });
      });
      summary.textContent = "답변 출처 보기 (" + Object.keys(urls).length + ")";
    };
    panel.addSourceMaterial = function (material) {
      if (material && materials.indexOf(material) === -1) { materials.push(material); }
      panel.refreshSources();
    };
    if (initialMaterial) { panel.addSourceMaterial(initialMaterial); }
    return panel;
  }

  function combineCardSources(doc, card, sources) {
    var panel = sources && sources.addSourceMaterial ? sources : buildCombinedAnswerSources(doc, sources);
    if (card && card.sourceMaterial) {
      panel.addSourceMaterial(card.sourceMaterial);
      card.onSourcesChanged = panel.refreshSources;
    }
    return panel;
  }

  function appendProfilePopup(doc, container, card, profile, explanation) {
    var sources = explanation && Array.prototype.slice.call(explanation.children).find(function (child) { return child.className === "species-answer-sources"; });
    if (sources) { explanation.removeChild(sources); }
    sources = combineCardSources(doc, card, sources);
    container.appendChild(buildSpeciesPopup(doc, card, profile));
    container.appendChild(sources);
    return sources;
  }

  /**
   * Build the sourced species profile card for a `ChatSpeciesResult`
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
  /**
   * Two-species comparison: target names, sourced traits (only claims with a
   * safe source URL and named source), and a popup card for each species.
   * `options` is threaded into the nested related explorer so a follow-up
   * comparison opened from inside this panel also becomes its own bubble.
   */
  function buildSpeciesComparison(doc, left, right, options) {
    options = options || {};
    var comparisonCallback = options.explorer && options.explorer.onComparison;
    if (comparisonCallback && typeof comparisonCallback.beforeComparison === "function") { comparisonCallback.beforeComparison(); }
    var comparisonSources = buildCombinedAnswerSources(doc);
    var cardOptions = { fetcher: options.fetcher, isActive: options.explorer && options.explorer.isActive };
    var panel = doc.createElement("section");
    panel.className = "species-comparison";
    var heading = doc.createElement("h3");
    heading.textContent = "두 새 비교";
    panel.appendChild(heading);
    var tableWrap = doc.createElement("div");
    tableWrap.className = "species-comparison-table";
    tableWrap.setAttribute("tabindex", "0");
    tableWrap.setAttribute("role", "region");
    tableWrap.setAttribute("aria-label", "비교 표");
    var table = doc.createElement("table");
    var caption = doc.createElement("caption");
    caption.textContent = "먹이 · 서식 환경 · 생활 방식 · 체중";
    table.appendChild(caption);
    var head = doc.createElement("thead");
    var titles = doc.createElement("tr");
    ["특징", speciesLabel(left.taxon),
      speciesLabel(right.taxon)].forEach(function (text) {
      var th = doc.createElement("th"); th.scope = "col"; th.textContent = text; titles.appendChild(th);
    });
    head.appendChild(titles); table.appendChild(head);
    var body = doc.createElement("tbody");
    [["diet_category", "먹이 유형"], ["trophic_niche", "먹이 생태 범주"],
      ["habitat", "서식 환경"], ["primary_lifestyle", "주 생활 방식"], ["body_mass", "체중"]].forEach(function (field) {
      var row = doc.createElement("tr");
      var label = doc.createElement("th"); label.scope = "row"; label.textContent = field[1]; row.appendChild(label);
      [left, right].forEach(function (profile) {
        var cell = doc.createElement("td");
        var traits = (Array.isArray(profile.traits) ? profile.traits : []).filter(function (trait) {
          return trait && trait.name === field[0] && trait.display != null && sanitizeUrl(trait.source_url) && trait.source_name;
        });
        if (!traits.length) { cell.textContent = "확인된 자료 없음"; }
        groupTraits(traits).forEach(function (group) {
          var trait = group.trait;
          var value = doc.createElement("p");
          value.textContent = trait.display + (trait.unit && trait.unit !== "percent" ? " " + trait.unit : "") + (trait.inferred ? " (추정값)" : "");
          cell.appendChild(value);
          var details = doc.createElement("details");
          var summary = doc.createElement("summary"); summary.textContent = "출처"; details.appendChild(summary);
          group.sources.forEach(function (source) {
            details.appendChild(safeLink(doc, source.source_name, source.source_url));
            var meta = doc.createElement("p");
            meta.textContent = [source.release, source.license_name, source.summary_statistic === "mean" ? "종 평균" : null, source.citation].filter(Boolean).join(" · ");
            details.appendChild(meta);
          });
          cell.appendChild(details);
        });
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
    table.appendChild(body); tableWrap.appendChild(table); panel.appendChild(tableWrap);
    var note = doc.createElement("p"); note.className = "species-note";
    note.textContent = "자료별 범주와 측정 기준이 다를 수 있습니다. 자료가 없는 항목은 차이로 판단하지 않습니다.";
    panel.appendChild(note);
    if (options.bothCards) {
      var leftCard = buildSpeciesCard(doc, left, cardOptions);
      if (leftCard) { panel.appendChild(buildSpeciesPopup(doc, leftCard, left)); combineCardSources(doc, leftCard, comparisonSources); }
    }
    var card = buildSpeciesCard(doc, right, cardOptions);
    if (card) { panel.appendChild(buildSpeciesPopup(doc, card, right)); combineCardSources(doc, card, comparisonSources); }
    panel.appendChild(buildRelatedExplorer(doc, right, options.fetcher, options.explorer));
    panel.appendChild(buildEcologicalExplorer(doc, right, options.fetcher, options.explorer));
    panel.appendChild(comparisonSources);
    return panel;
  }

  function speciesLabel(taxon) {
    return taxon && ((taxon.korean_name_status !== "machine-translated" && taxon.korean_name) || taxon.english_name || taxon.display_label || taxon.scientific_name) || "새";
  }

  /**
   * Lazy same-genus/family explorer. With `options.onComparison` (the chat
   * page), each peer comparison is handed off as a brand-new assistant
   * bubble and the original explanation is never replaced; without it
   * (standalone use) the comparison renders in place below the peer list.
   * Each peer has its own in-flight guard, so different peers can be
   * compared one after another while a repeated click on a loading peer is
   * ignored; a failed peer can simply be clicked again. `options.isActive`
   * drops responses that settle after the conversation was cleared.
   */
  function buildSimilarityEvidence(doc, peer) {
    var details = doc.createElement("details"); details.className = "similarity-evidence";
    var title = doc.createElement("summary"); title.textContent = "비교 후보 근거와 출처"; details.appendChild(title);
    (Array.isArray(peer.similarity_reasons) ? peer.similarity_reasons : []).forEach(function (reason) {
      if (!reason || typeof reason.label !== "string") { return; }
      var line = doc.createElement("p"); line.textContent = reason.label + (typeof reason.points === "number" && reason.points > 0 ? " · " + reason.points + "점" : "") + (typeof reason.display === "string" ? " · " + reason.display : ""); details.appendChild(line);
      if (typeof reason.source_name === "string") { details.appendChild(safeLink(doc, reason.source_name, reason.source_url)); }
      (Array.isArray(reason.supporting_studies) ? reason.supporting_studies : []).forEach(function (study) {
        if (study && typeof study.citation === "string") { details.appendChild(safeLink(doc, study.citation, study.source_url)); }
      });
      if (Array.isArray(reason.conflicting_sources) && reason.conflicting_sources.length) {
        var conflict = doc.createElement("p"); conflict.textContent = "일부 연구에서는 다른 계통 관계를 제시합니다."; details.appendChild(conflict);
      }
      if (typeof reason.target_source_url === "string") { details.appendChild(safeLink(doc, "기준 종의 생태 출처", reason.target_source_url)); }
    });
    return details;
  }
  function similarityLabel(peer, priority) {
    var score = typeof peer.similarity_score === "number" && Number.isFinite(peer.similarity_score) && peer.similarity_score >= 0 && peer.similarity_score <= 100 ? peer.similarity_score : null;
    return (Number.isInteger(peer.similarity_rank) && peer.similarity_rank >= 1 && peer.similarity_rank <= 3 ? (priority === "korean_name_then_weighted_score" ? "추천 " + peer.similarity_rank : peer.similarity_rank + "위") + " · " : "") + speciesLabel(peer) + (score !== null ? (peer.score_basis === "taxonomy_ecology_fallback" ? " · 분류·생태 대체 점수(계통 자료 부족) " : " · 가중 점수 ") + score + "점" : "");
  }

  function buildComparisonPeer(doc, peer, ranked, priority) {
    var row = doc.createElement("div"); row.className = "comparison-peer";
    var identity = doc.createElement("div"); identity.className = "comparison-peer-identity";
    var name = doc.createElement("strong"); name.textContent = speciesLabel(peer); identity.appendChild(name);
    var scientific = doc.createElement("i"); scientific.textContent = peer.scientific_name; identity.appendChild(scientific);
    row.appendChild(identity);
    if (ranked) {
      row.setAttribute("data-ranked", "true");
      var rank = doc.createElement("span"); rank.className = "comparison-peer-rank";
      rank.textContent = priority === "korean_name_then_weighted_score" ? "추천 " + peer.similarity_rank : peer.similarity_rank + "위"; row.appendChild(rank);
      var score = doc.createElement("span"); score.className = "comparison-peer-score";
      score.textContent = peer.similarity_score + "점";
      score.setAttribute("aria-label", "비교 후보 " + similarityLabel(peer, priority)); row.appendChild(score);
      var basis = doc.createElement("span"); basis.className = "comparison-peer-basis";
      basis.textContent = peer.score_basis === "taxonomy_ecology_fallback" ? "분류·생태 대체 점수(계통 자료 부족)" : "가중 점수";
      row.appendChild(basis);
      var chips = doc.createElement("div"); chips.className = "comparison-peer-reasons";
      var seenReasons = {};
      (Array.isArray(peer.similarity_reasons) ? peer.similarity_reasons : []).forEach(function (reason) {
        if (!reason || typeof reason.label !== "string" || !reason.label.trim() || seenReasons[reason.label] || chips.children.length >= 3) { return; }
        seenReasons[reason.label] = true;
        var chip = doc.createElement("span"); chip.textContent = reason.label; chips.appendChild(chip);
      });
      row.appendChild(chips);
    }
    var button = doc.createElement("button"); button.type = "button"; button.className = "comparison-peer-choose";
    button.textContent = "비교하기";
    button.setAttribute("aria-label", (ranked ? similarityLabel(peer, priority) : speciesLabel(peer)) + " · 비교하기");
    row.appendChild(button);
    return { row: row, button: button };
  }

  function buildRankingCriteria(doc, data) {
    var ranking = data && data.ranking;
    var supported = ranking && ranking.limit === 3 &&
      ["taxonomy-ecology-v1", "taxonomy-phylogeny-ecology-v2", "taxonomy-phylogeny-ecology-v3"].indexOf(ranking.method) !== -1;
    var weights = supported && ranking.weights;
    var keys = ["phylogenetic_clade", "same_genus", "same_family", "same_habitat", "same_trophic_niche"];
    var valid = weights && typeof weights === "object" && !Array.isArray(weights) && Object.keys(weights).length === keys.length && keys.every(function (key) {
      return typeof weights[key] === "number" && Number.isFinite(weights[key]) && weights[key] >= 0 && weights[key] <= 100;
    }) && Math.abs(keys.reduce(function (sum, key) { return sum + weights[key]; }, 0) - 100) < 0.000001;
    var section = doc.createElement("section"); section.className = "similarity-criteria";
    if (supported && ranking.priority === "korean_name_then_weighted_score") {
      var priority = doc.createElement("p"); priority.className = "similarity-priority";
      priority.textContent = "한국어 이름 우선 · 점수순"; section.appendChild(priority);
    }
    if (!valid) {
      var fallback = doc.createElement("p"); fallback.className = "species-note";
      fallback.textContent = data && typeof data.note === "string" ? data.note : "점수 기준을 확인할 수 없습니다.";
      section.appendChild(fallback); return section;
    }
    var title = doc.createElement("h4"); title.textContent = "점수 반영 비중"; section.appendChild(title);
    var badges = doc.createElement("dl"); badges.className = "similarity-weight-badges";
    [["계통", weights.phylogenetic_clade], ["분류", Number((weights.same_genus + weights.same_family).toFixed(6))],
      ["서식 환경", weights.same_habitat], ["먹이 생태", weights.same_trophic_niche]].forEach(function (entry) {
      var badge = doc.createElement("div");
      var label = doc.createElement("dt"); label.textContent = entry[0]; badge.appendChild(label);
      var value = doc.createElement("dd"); value.textContent = entry[1] + "%"; badge.appendChild(value);
      badges.appendChild(badge);
    });
    section.appendChild(badges);
    var details = doc.createElement("details"); details.className = "similarity-calculation-details";
    var summary = doc.createElement("summary"); summary.textContent = "계산 방식과 자료 한계"; details.appendChild(summary);
    var caveat = doc.createElement("p");
    caveat.textContent = "계통 자료가 부족한 후보는 확인된 분류·생태 비중만으로 100점에 환산합니다. 이 가중 점수는 실제 진화 거리나 유전 유사도의 측정값이 아닙니다.";
    details.appendChild(caveat);
    if (ranking.priority === "korean_name_then_weighted_score") {
      var policy = doc.createElement("p"); policy.textContent = "검증표에 한국어 이름이 있는 후보를 먼저 표시하고, 같은 표시 조건 안에서 점수순으로 정렬합니다. 한국어 이름의 유무로 과학적 근연 순위를 추정하지 않습니다."; details.appendChild(policy);
    }
    if (typeof data.note === "string" && data.note.trim()) { var note = doc.createElement("p"); note.textContent = data.note; details.appendChild(note); }
    section.appendChild(details); return section;
  }

  function buildRelatedExplorer(doc, profile, fetcher, options) {
    options = options || {};
    var active = typeof options.isActive === "function" ? options.isActive : function () { return true; };
    var onComparison = typeof options.onComparison === "function" ? options.onComparison : null;
    var section = doc.createElement("section"); section.className = "species-related";
    section.setAttribute("aria-label", speciesLabel(profile.taxon) + " 관련 새 탐색");
    var open = doc.createElement("button"); open.type = "button";
    open.textContent = "같은 속·과의 새 살펴보기";
    if ((options.initialData && options.initialData.ranking) || options.endpoint === "/v1/taxa/similar") { open.textContent = "근연 관계 우선 3종 살펴보기"; }
    open.setAttribute("aria-expanded", "false");
    if (options.inline) { section.setAttribute("data-inline", "true"); }
    else { section.appendChild(open); }
    var content = doc.createElement("div"); content.hidden = true; section.appendChild(content);
    var status = doc.createElement("p"); status.setAttribute("role", "status"); content.appendChild(status);
    var results = doc.createElement("div"); content.appendChild(results);
    var comparison = doc.createElement("div"); content.appendChild(comparison);
    var loaded = false;
    var pending = {};
    function fetchJson(path, name) {
      var transport = fetcher || (doc.defaultView && typeof doc.defaultView.fetch === "function" && doc.defaultView.fetch.bind(doc.defaultView));
      if (!transport) { return Promise.reject(new Error("unavailable")); }
      return transport(path + "?name=" + encodeURIComponent(name), {credentials:"omit", signal:typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(path === "/v1/taxa/profile" ? 60000 : 30000) : undefined}).then(function (response) {
        if (!response.ok) { throw new Error("unavailable"); } return response.json();
      });
    }
    function matchesRelease(data) {
      return profile.lineage && data.concept_set_id === profile.lineage.concept_set_id && data.taxonomy_release === profile.lineage.taxonomy_release;
    }
    function selectPeer(peer, group, button, priority) {
      var key = String(peer.taxon_id || peer.scientific_name);
      if (pending[key]) { return; }
      pending[key] = true;
      if (button) { button.disabled = true; button.setAttribute("aria-busy", "true"); }
      content.setAttribute("aria-busy", "true");
      if (!onComparison) { while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); } }
      var peerName = speciesLabel(peer);
      status.textContent = peerName + " 비교 자료를 불러오는 중입니다.";
      function settle() {
        delete pending[key];
        if (button) { button.disabled = false; button.setAttribute("aria-busy", "false"); }
        if (!Object.keys(pending).length) { content.setAttribute("aria-busy", "false"); }
        return active();
      }
      return fetchJson("/v1/taxa/profile", peer.scientific_name).then(function (other) {
        if (!other || !other.taxon || other.taxon.taxon_id !== peer.taxon_id || !other.lineage || !matchesRelease(other.lineage)) { throw new Error("changed"); }
        if (!settle()) { return; }
        var panel = buildSpeciesComparison(doc, profile, other, {
          fetcher: fetcher, bothCards: !!onComparison,
          explorer: { onComparison: onComparison, isActive: active },
        });
        var relation = doc.createElement("p");
        relation.className = "species-comparison-relation";
        relation.textContent = "공유 분류군: " + (group.ancestor ? (group.ancestor.korean_name || group.ancestor.scientific_name) : "확인 불가") + " (" + (RANK_LABELS[group.rank] || group.rank) + ")";
        if (group.rank === "similarity") { relation.textContent = similarityLabel(peer, priority); panel.appendChild(buildSimilarityEvidence(doc, peer)); var scoreNote = doc.createElement("p"); scoreNote.textContent = "계통·분류·생태의 가중 점수입니다. 계통 자료가 없으면 분류·생태만 100점으로 환산합니다. 진화 거리나 유전 유사도의 측정값은 아닙니다."; panel.appendChild(scoreNote); }
        panel.appendChild(relation);
        var version = doc.createElement("p");
        version.className = "species-comparison-version";
        version.textContent = "분류 기준: " + [profile.lineage.taxonomy_source, profile.lineage.taxonomy_release].filter(Boolean).join(" · ");
        panel.appendChild(version);
        if (onComparison) {
          onComparison(panel, { left: profile, right: other, group: group });
          status.textContent = speciesLabel(profile.taxon) + "와(과) " + peerName + " 비교를 새 답변으로 추가했습니다.";
          return;
        }
        while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); }
        comparison.appendChild(panel);
        if (typeof panel.scrollIntoView === "function") { panel.scrollIntoView({block:"start"}); }
        status.textContent = "비교 자료를 불러왔습니다.";
      }).catch(function (error) {
        if (!settle()) { return; }
        status.textContent = error && error.message === "changed"
          ? peerName + " 비교 자료를 표시하지 않았습니다. 분류 자료가 갱신된 경우 질문을 다시 보내주세요."
          : peerName + " 비교 자료를 불러오지 못했습니다. 다시 눌러 재시도하세요.";
      });
    }
    var initialData = options.initialData;
    function toggle() {
      content.hidden = !content.hidden; open.setAttribute("aria-expanded", String(!content.hidden));
      if (content.hidden || loaded) { return; }
      loaded = true; status.textContent = "분류 관계를 조회하는 중입니다.";
      var request = initialData ? Promise.resolve(initialData) : fetchJson(options.endpoint || "/v1/taxa/related", profile.taxon.scientific_name);
      initialData = null;
      request.then(function (data) {
        if (!data.taxon || data.taxon.taxon_id !== profile.taxon.taxon_id || !matchesRelease(data)) { throw new Error("changed"); }
        if (!active()) { return; }
        while (results.firstChild) { results.removeChild(results.firstChild); }
        results.appendChild(buildRankingCriteria(doc, data));
        var version = doc.createElement("p"); version.textContent = data.taxonomy_source + " · " + data.taxonomy_release; results.appendChild(version);
        var rankedRemaining = data.ranking && data.ranking.limit === 3 ? 3 : null;
        if (rankedRemaining !== null) { open.textContent = "근연 관계 우선 3종 살펴보기"; }
        (Array.isArray(data.groups) ? data.groups : []).forEach(function (group) {
          var block = doc.createElement("section");
          var title = doc.createElement("h3");
          title.textContent = group.label + (group.ancestor ? " · " + (group.ancestor.korean_name || group.ancestor.scientific_name) : ""); block.appendChild(title);
          var peers = (Array.isArray(group.items) ? group.items : []).filter(function (peer) {
            return peer && peer.taxon_id && typeof peer.scientific_name === "string" && peer.scientific_name.trim();
          });
          var ranked = group.rank === "similarity" || rankedRemaining !== null;
          if (ranked) { peers = peers.filter(function (peer) { return Number.isInteger(peer.similarity_rank) && peer.similarity_rank >= 1 && peer.similarity_rank <= 3 && typeof peer.similarity_score === "number" && Number.isFinite(peer.similarity_score) && peer.similarity_score >= 0 && peer.similarity_score <= 100; }).sort(function (left, right) { return left.similarity_rank - right.similarity_rank; }); }
          if (!peers.length) {
            var empty = doc.createElement("p"); empty.textContent = "현재 분류 자료에서 이름이 확인된 다른 종이 없습니다."; block.appendChild(empty);
          }
          var visiblePeers = peers.slice(0, ranked ? (rankedRemaining === null ? 3 : rankedRemaining) : 12);
          if (rankedRemaining !== null) { rankedRemaining -= visiblePeers.length; }
          visiblePeers.forEach(function (peer) {
            var priority = data.ranking && data.ranking.priority;
            var choice = buildComparisonPeer(doc, peer, ranked, priority);
            choice.button.addEventListener("click", function () { selectPeer(peer, group, choice.button, priority); });
            if (ranked || sanitizeUrl(peer.korean_name_source_url)) {
              var evidence = ranked ? buildSimilarityEvidence(doc, peer) : doc.createElement("details");
              if (!ranked) { var summary = doc.createElement("summary"); summary.textContent = "이름 출처"; evidence.appendChild(summary); }
              if (sanitizeUrl(peer.korean_name_source_url)) { evidence.appendChild(safeLink(doc, "이름 출처", peer.korean_name_source_url)); }
              choice.row.appendChild(evidence);
            }
            block.appendChild(choice.row);
          });
          if (group.has_more && !ranked) { var more = doc.createElement("p"); more.textContent = "이름이 확인된 종 중 최대 12종을 표시합니다."; block.appendChild(more); }
          var source = doc.createElement("details");
          var summary = doc.createElement("summary"); summary.textContent = "분류 관계의 출처"; source.appendChild(summary);
          source.appendChild(safeLink(doc, group.source_name || data.taxonomy_source, group.source_url));
          var release = doc.createElement("p"); release.textContent = "분류 버전: " + data.taxonomy_release; source.appendChild(release);
          block.appendChild(source); results.appendChild(block);
        });
        status.textContent = "비교할 새를 선택하세요.";
      }).catch(function () {
        loaded = false; if (!active()) { return; }
        status.textContent = options.inline
          ? "분류 관계를 불러오지 못했습니다. 분류 자료가 갱신되었을 수 있으니 질문을 다시 보내주세요."
          : "분류 관계를 불러오지 못했습니다. 접었다 다시 펼쳐 재시도하거나, 카드를 다시 열어주세요.";
      });
    }
    open.addEventListener("click", toggle);
    if (options.initiallyOpen || options.inline) { toggle(); }
    return section;
  }

  var ECOLOGICAL_NOTE = "같은 자료의 생태 분류값을 공유하는 종입니다. 가까운 계통이나 실제 공존·먹이 관계를 뜻하지 않습니다.";
  function supportedEcologicalGroup(group) {
    if (!group || typeof group.value !== "string" || typeof group.display !== "string" || !group.display.trim() || !group.source || !group.source.source_name || !sanitizeUrl(group.source.source_url)) { return false; }
    if (group.relation === "habitat") { return Object.prototype.hasOwnProperty.call(HABITAT_EMBLEMS, group.value.trim().toLowerCase().replace(/[\s-]+/g, "_")); }
    return group.relation === "trophic_niche" && Object.prototype.hasOwnProperty.call(TROPHIC_NICHE_KEYS, group.value);
  }
  function buildEcologicalSource(doc, source) {
    var details = doc.createElement("details"); details.className = "ecological-source";
    var summary = doc.createElement("summary"); summary.textContent = "생태 분류값의 출처"; details.appendChild(summary);
    details.appendChild(safeLink(doc, source.source_name, source.source_url));
    var metadata = doc.createElement("p"); metadata.textContent = [source.dataset_id, source.release, source.license_name, source.citation].filter(Boolean).join(" · "); details.appendChild(metadata);
    return details;
  }

  function buildEcologicalExplorer(doc, profile, fetcher, options) {
    options = options || {};
    var active = typeof options.isActive === "function" ? options.isActive : function () { return true; };
    var onComparison = typeof options.onComparison === "function" ? options.onComparison : null;
    var section = doc.createElement("section"); section.className = "species-ecological-related";
    section.setAttribute("aria-label", speciesLabel(profile.taxon) + " 생태 범주 탐색");
    var open = doc.createElement("button"); open.type = "button";
    open.textContent = "같은 서식 환경·먹이 생태의 새 살펴보기";
    open.setAttribute("aria-expanded", "false"); section.appendChild(open);
    var content = doc.createElement("div"); content.hidden = true; section.appendChild(content);
    var status = doc.createElement("p"); status.setAttribute("role", "status"); content.appendChild(status);
    var results = doc.createElement("div"); content.appendChild(results);
    var comparison = doc.createElement("div"); content.appendChild(comparison);
    var loaded = false;
    var pending = {};
    function fetchJson(path, name) {
      var transport = fetcher || (doc.defaultView && typeof doc.defaultView.fetch === "function" && doc.defaultView.fetch.bind(doc.defaultView));
      if (!transport) { return Promise.reject(new Error("unavailable")); }
      return transport(path + "?name=" + encodeURIComponent(name), {credentials:"omit", signal:typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(path === "/v1/taxa/profile" ? 60000 : 30000) : undefined}).then(function (response) {
        if (!response.ok) { throw new Error("unavailable"); } return response.json();
      });
    }
    function matchesRelease(data) {
      return profile.lineage && data.concept_set_id === profile.lineage.concept_set_id && data.taxonomy_release === profile.lineage.taxonomy_release;
    }
    function selectPeer(peer, group, button) {
      var key = String(peer.taxon_id || peer.scientific_name);
      if (pending[key]) { return; }
      pending[key] = true;
      if (button) { button.disabled = true; button.setAttribute("aria-busy", "true"); }
      content.setAttribute("aria-busy", "true");
      if (!onComparison) { while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); } }
      var peerName = speciesLabel(peer);
      status.textContent = peerName + " 비교 자료를 불러오는 중입니다.";
      function settle() {
        delete pending[key];
        if (button) { button.disabled = false; button.setAttribute("aria-busy", "false"); }
        if (!Object.keys(pending).length) { content.setAttribute("aria-busy", "false"); }
        return active();
      }
      return fetchJson("/v1/taxa/profile", peer.scientific_name).then(function (other) {
        if (!other || !other.taxon || other.taxon.rank !== "species" || other.taxon.taxon_id !== peer.taxon_id || !other.lineage || !matchesRelease(other.lineage)) { throw new Error("changed"); }
        if (!settle()) { return; }
        var panel = buildSpeciesComparison(doc, profile, other, {
          fetcher: fetcher, bothCards: !!onComparison,
          explorer: { onComparison: onComparison, isActive: active },
        });
        var relation = doc.createElement("p");
        relation.className = "species-comparison-relation";
        relation.textContent = "공유 생태 범주: " + group.display;
        panel.appendChild(buildEcologicalSource(doc, group.source));
        panel.appendChild(buildEcologicalSource(doc, peer.evidence));
        panel.appendChild(relation);
        var ecologicalNote = doc.createElement("p"); ecologicalNote.className = "species-note"; ecologicalNote.textContent = ECOLOGICAL_NOTE; panel.appendChild(ecologicalNote);
        var version = doc.createElement("p");
        version.className = "species-comparison-version";
        version.textContent = "분류 기준: " + [profile.lineage.taxonomy_source, profile.lineage.taxonomy_release].filter(Boolean).join(" · ");
        panel.appendChild(version);
        if (onComparison) {
          onComparison(panel, { left: profile, right: other, group: group });
          status.textContent = speciesLabel(profile.taxon) + "와(과) " + peerName + " 비교를 새 답변으로 추가했습니다.";
          return;
        }
        while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); }
        comparison.appendChild(panel);
        if (typeof panel.scrollIntoView === "function") { panel.scrollIntoView({block:"start"}); }
        status.textContent = "비교 자료를 불러왔습니다.";
      }).catch(function (error) {
        if (!settle()) { return; }
        status.textContent = error && error.message === "changed"
          ? peerName + " 비교 자료를 표시하지 않았습니다. 분류 자료가 갱신된 경우 질문을 다시 보내주세요."
          : peerName + " 비교 자료를 불러오지 못했습니다. 다시 눌러 재시도하세요.";
      });
    }
    var initialData = options.initialData;
    function toggle() {
      content.hidden = !content.hidden; open.setAttribute("aria-expanded", String(!content.hidden));
      if (content.hidden || loaded) { return; }
      loaded = true; status.textContent = "생태 범주를 조회하는 중입니다.";
      var request = initialData ? Promise.resolve(initialData) : fetchJson("/v1/taxa/ecological-related", profile.taxon.scientific_name);
      initialData = null;
      request.then(function (data) {
        if (!data.taxon || data.taxon.taxon_id !== profile.taxon.taxon_id || !matchesRelease(data)) { throw new Error("changed"); }
        if (!active()) { return; }
        while (results.firstChild) { results.removeChild(results.firstChild); }
        var note = doc.createElement("p"); note.className = "species-note"; note.textContent = ECOLOGICAL_NOTE; results.appendChild(note);
        var version = doc.createElement("p"); version.textContent = data.taxonomy_source + " · " + data.taxonomy_release; results.appendChild(version);
        var count = 0;
        (Array.isArray(data.groups) ? data.groups : []).forEach(function (group) {
          if (!supportedEcologicalGroup(group)) { return; }
          count++;
          var block = doc.createElement("section");
          var title = doc.createElement("h3");
          title.textContent = (group.relation === "habitat" ? "같은 서식 환경의 새" : "같은 먹이 생태의 새") + " · " + group.display;
          block.appendChild(title);
          block.appendChild(buildEcologicalSource(doc, group.source));
          var peers = (Array.isArray(group.items) ? group.items : []).filter(function (peer) {
            return peer && peer.rank === "species" && peer.taxon_id && typeof peer.scientific_name === "string" && peer.scientific_name.trim() && peer.taxon_id !== profile.taxon.taxon_id && peer.evidence && peer.evidence.source_name && sanitizeUrl(peer.evidence.source_url);
          });
          if (!peers.length) { var empty = doc.createElement("p"); empty.textContent = "같은 자료에서 출처가 확인된 다른 종이 없습니다."; block.appendChild(empty); }
          peers.slice(0, 3).forEach(function (peer) {
            var choice = buildComparisonPeer(doc, peer, false);
            choice.row.className += " ecological-peer";
            choice.button.addEventListener("click", function () { selectPeer(peer, group, choice.button); });
            var evidence = buildEcologicalSource(doc, peer.evidence);
            if (sanitizeUrl(peer.korean_name_source_url)) { evidence.appendChild(safeLink(doc, "이름 출처", peer.korean_name_source_url)); }
            choice.row.appendChild(evidence);
            block.appendChild(choice.row);
          });
          if (group.has_more || peers.length > 3) { var more = doc.createElement("p"); more.textContent = "일부 종만 표시합니다 (범주별 최대 3종)."; block.appendChild(more); }
          results.appendChild(block);
        });
        status.textContent = count ? "비교할 새를 선택하세요." : "출처가 확인된 서식 환경·먹이 생태 관련 종이 없습니다.";
      }).catch(function (error) {
        loaded = false; if (!active()) { return; }
        status.textContent = error && error.message === "changed" ? "분류 자료가 갱신되었습니다. 질문을 다시 보내 최신 생태 범주를 확인하세요." : "생태 범주를 불러오지 못했습니다. 접었다 다시 펼쳐 재시도하거나, 카드를 다시 열어주세요.";
      });
    }
    open.addEventListener("click", toggle);
    if (options.initiallyOpen) { toggle(); }
    return section;
  }

  /**
   * GET a read-only `/v1/taxa/*` JSON endpoint with `?name=` URL-encoded.
   * A non-2xx rejects with an Error carrying `status` so callers can pick a
   * fixed, honest message; a missing transport rejects with status 0.
   */
  function fetchTaxaJson(doc, fetcher, path, name, timeoutMs) {
    var transport = fetcher || (doc.defaultView && typeof doc.defaultView.fetch === "function" && doc.defaultView.fetch.bind(doc.defaultView));
    if (!transport) {
      var missing = new Error("unavailable"); missing.status = 0;
      return Promise.reject(missing);
    }
    var signal = typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(timeoutMs) : undefined;
    return Promise.resolve().then(function () {
      return transport(path + "?name=" + encodeURIComponent(name), { method: "GET", credentials: "omit", signal: signal });
    }).then(function (response) {
      if (!response || !response.ok) {
        var failure = new Error("unavailable"); failure.status = response ? response.status : 0;
        throw failure;
      }
      return response.json();
    });
  }

  function nameRelationsErrorText(error) {
    var status = error && error.status;
    if (status === 404) {
      return "이 이름의 통칭·가축형 관계 자료를 찾지 못했거나, 서버가 아직 이 조회를 지원하지 않습니다.";
    }
    if (status === 429 || status === 503) {
      return sanitizeErrorMessage({ kind: "http", status: status });
    }
    if (error && error.unsupported) {
      return sanitizeErrorMessage({ kind: "unsupported-response" });
    }
    return "통칭·가축형 관계를 불러오지 못했습니다. 잠시 후 다시 시도하세요.";
  }

  /** Shape check for the `GET /v1/taxa/name-relations` payload (also `result.relationships`). */
  function isNameRelationsPayload(data) {
    return !!(data && typeof data === "object" && !Array.isArray(data) && Array.isArray(data.relations));
  }

  /** Domestic-form relations get an explicit "not the same animal as the wild species" warning. */
  function isDomesticRelation(relation) {
    var text = [relation && relation.entity_kind, relation && relation.relation_type].filter(function (value) {
      return typeof value === "string";
    }).join(" ");
    return /domestic|가축|사육/i.test(text);
  }

  function nameRelationTaxonLabel(taxon) {
    if (!taxon || typeof taxon !== "object") { return ""; }
    var label = speciesLabel(taxon);
    return label + (taxon.scientific_name && taxon.scientific_name !== label ? " · " + taxon.scientific_name : "");
  }

  var DOMESTIC_WARNING =
    "가축형과 야생 개체군의 정보를 구분합니다. 표시되는 측정값·사진·멸종위기 등급은 야생 개체군 기준 자료이며 가축형에 그대로 적용되지 않습니다.";

  /**
   * Render a source-backed name/domestic-form relationship payload in the
   * explanation area (never inside a species card). Each related taxon gets
   * an explicit button that fetches `/v1/taxa/profile` for its scientific
   * name; the chosen profile is shown with a caveat stating it is the
   * related wild species, not the queried name itself. Only the newest
   * selection may render (older responses are dropped), and `isActive`
   * lets the chat page drop responses that settle after 대화 지우기.
   * Returns null for a malformed payload.
   */
  function buildNameRelations(doc, relationships, fetcher, isActive, onComparison) {
    if (!isNameRelationsPayload(relationships)) { return null; }
    var data = relationships;
    var active = typeof isActive === "function" ? isActive : function () { return true; };
    var queryName = typeof data.query_name === "string" && data.query_name.trim() ? data.query_name.trim() : "검색어";
    var targets = [];
    data.relations.forEach(function (relation) {
      var taxon = relation && relation.taxon;
      if (!taxon || !taxon.scientific_name) { return; }
      var key = taxon.taxon_id || taxon.scientific_name;
      if (!targets.some(function (item) { return (item.taxon.taxon_id || item.taxon.scientific_name) === key; })) { targets.push(relation); }
    });
    if (!data.is_search_term) {
      var queried = targets.find(function (relation) { return relation.taxon.scientific_name === queryName; });
      if (queried) { queryName = speciesLabel(queried.taxon); }
    }
    var automatic = targets.length === 1 && data.relations.every(function (relation) { return !isDomesticRelation(relation); }) && /common_name/.test([targets[0].relation_type, targets[0].entity_kind].join(" "));
    var section = doc.createElement("section");
    section.className = "name-relations";
    section.setAttribute("aria-label", queryName + " 이름 관계");

    var heading = doc.createElement("h3");
    heading.textContent = "‘" + queryName + "’ 이름 관계";
    section.appendChild(heading);
    if (typeof data.summary === "string" && data.summary.trim()) {
      var summary = doc.createElement("p");
      summary.className = "name-relations-summary";
      summary.textContent = data.summary;
      section.appendChild(summary);
    }
    if (data.is_search_term === true && !automatic) {
      var searchTerm = doc.createElement("p");
      searchTerm.className = "species-note";
      searchTerm.textContent = "‘" + queryName + "’은(는) 여러 종이나 가축형을 함께 가리키는 데에도 쓰이는 이름입니다. 통칭의 사용 범위·가축형 관계를 구분해 확인합니다. 아래 관련 종 중 하나를 골라 확인하세요.";
      section.appendChild(searchTerm);
    }
    var versionParts = [data.taxonomy_source, data.taxonomy_release].filter(function (value) {
      return typeof value === "string" && value.trim();
    });
    if (versionParts.length) {
      var version = doc.createElement("p");
      version.className = "answer-metadata";
      version.textContent = "분류 기준: " + versionParts.join(" · ");
      section.appendChild(version);
    }

    var relations = data.relations.filter(function (relation) {
      return relation && typeof relation === "object" && typeof relation.name === "string" && relation.name.trim();
    }).slice(0, 20);
    var status = doc.createElement("p");
    status.className = "name-relations-status";
    status.setAttribute("role", "status");
    var selection = doc.createElement("div");
    selection.className = "name-relation-selection";
    if (!relations.length) {
      var empty = doc.createElement("p");
      empty.className = "species-answer-empty";
      empty.textContent = "출처가 확인된 통칭·가축형 관계가 없습니다.";
      section.appendChild(empty);
      return section;
    }

    var generation = 0;
    var pendingKey = null;
    function clearSelection() {
      while (selection.firstChild) { selection.removeChild(selection.firstChild); }
    }
    function choose(relation) {
      var taxon = relation.taxon;
      var key = taxon.taxon_id || taxon.scientific_name;
      if (pendingKey === key) { return; }
      var current = ++generation;
      pendingKey = key;
      clearSelection();
      section.setAttribute("aria-busy", "true");
      status.textContent = taxon.scientific_name + " 자료를 불러오는 중입니다.";
      function settle() {
        if (current !== generation) { return false; }
        pendingKey = null;
        section.setAttribute("aria-busy", "false");
        return active();
      }
      fetchTaxaJson(doc, fetcher, "/v1/taxa/profile", taxon.scientific_name, 60000).then(function (profile) {
        if (!settle()) { return; }
        var sameTaxon = profile && profile.taxon && (taxon.taxon_id ? profile.taxon.taxon_id === taxon.taxon_id : profile.taxon.scientific_name === taxon.scientific_name);
        var sameRelease = !data.concept_set_id || (profile && profile.lineage && profile.lineage.concept_set_id === data.concept_set_id && profile.lineage.taxonomy_release === data.taxonomy_release);
        if (!sameTaxon || !sameRelease) {
          status.textContent = "선택한 종의 분류 자료가 바뀌었습니다. 질문을 다시 보내 최신 관계를 확인하세요.";
          return;
        }
        var candidateName = nameRelationTaxonLabel(profile.taxon) || taxon.scientific_name;
        var caveat = doc.createElement("p");
        caveat.className = "name-relation-caveat";
        caveat.setAttribute("role", "note");
        caveat.textContent = "아래는 ‘" + queryName + "’(이)라는 이름이 가리키는 범위 전체의 자료가 아니라, 출처에서 ‘" + relation.name + "’과(와) " +
          (typeof relation.relation_label === "string" && relation.relation_label.trim() ? "‘" + relation.relation_label.trim() + "’ 관계로 " : "") +
          (isDomesticRelation(relation) ? "연결된 관련 야생종 " : "연결된 종 ") + candidateName + "의 자료입니다." + (isDomesticRelation(relation) ? " " + DOMESTIC_WARNING : "");
        if (automatic) { caveat.textContent = "‘" + queryName + "’과(와) 그래프에서 연결된 " + candidateName + "의 자료입니다."; }
        selection.appendChild(caveat);
        var explanation = buildSpeciesAnswer(doc, profile);
        if (explanation) {
          selection.appendChild(explanation);
        } else if (typeof profile.summary === "string" && profile.summary.trim()) {
          var text = doc.createElement("p");
          text.textContent = profile.summary;
          selection.appendChild(text);
        }
        var card = buildSpeciesCard(doc, profile, { fetcher: fetcher, isActive: active });
        if (card) {
          if (profile.lineage && profile.taxon.rank !== "subspecies") { selection.appendChild(buildRelatedExplorer(doc, profile, fetcher, { onComparison: onComparison, isActive: active })); selection.appendChild(buildEcologicalExplorer(doc, profile, fetcher, { onComparison: onComparison, isActive: active })); }
          if (profile.taxon.rank !== "subspecies") { selection.appendChild(buildSubspeciesExplorer(doc, profile, fetcher, active)); }
          else { selection.appendChild(buildParentSpeciesExplorer(doc, profile, fetcher, active)); }
          selection.appendChild(buildSpeciesBrief(doc, profile));
          appendProfilePopup(doc, selection, card, profile, explanation);
        }
        status.textContent = candidateName + " 자료를 불러왔습니다.";
      }).catch(function (error) {
        if (!settle()) { return; }
        status.textContent = error && error.status === 404
          ? "선택한 종의 자료를 찾을 수 없습니다."
          : "선택한 종의 자료를 불러오지 못했습니다. 다시 눌러 재시도하세요.";
      });
    }

    var list = doc.createElement("ul");
    list.className = "name-relation-list";
    relations.forEach(function (relation) {
      var domestic = isDomesticRelation(relation);
      var li = doc.createElement("li");
      li.className = "name-relation" + (domestic ? " name-relation-domestic" : "");
      var title = doc.createElement("p");
      title.className = "name-relation-title";
      var name = doc.createElement("strong");
      name.textContent = relation.name;
      title.appendChild(name);
      var label = doc.createElement("span");
      label.className = "name-relation-label";
      label.textContent = typeof relation.relation_label === "string" && relation.relation_label.trim() ? relation.relation_label : "관계";
      title.appendChild(label);
      li.appendChild(title);
      var taxonLabel = nameRelationTaxonLabel(relation.taxon);
      if (taxonLabel) {
        var taxonLine = doc.createElement("p");
        taxonLine.className = "name-relation-taxon";
        taxonLine.textContent = (domestic ? "관련 야생종: " : "연결된 종: ") + taxonLabel;
        li.appendChild(taxonLine);
      }
      if (typeof relation.note === "string" && relation.note.trim()) {
        var note = doc.createElement("p");
        note.className = "species-note";
        note.textContent = relation.note;
        li.appendChild(note);
      }
      if (domestic) {
        var warning = doc.createElement("p");
        warning.className = "name-relation-warning";
        warning.textContent = "⚠ " + DOMESTIC_WARNING;
        li.appendChild(warning);
      }
      var sources = (Array.isArray(relation.sources) ? relation.sources : []).filter(function (source) {
        return source && typeof source === "object";
      }).slice(0, 5);
      var sourceLine = doc.createElement("p");
      sourceLine.className = "name-relation-sources";
      var sourcePrefix = doc.createElement("span");
      sourcePrefix.textContent = sources.length ? "출처: " : "출처 정보 없음";
      sourceLine.appendChild(sourcePrefix);
      sources.forEach(function (source, index) {
        if (index > 0) {
          var separator = doc.createElement("span");
          separator.textContent = " · ";
          sourceLine.appendChild(separator);
        }
        var sourceTitle = typeof source.title === "string" && source.title.trim() ? source.title : "출처 " + (index + 1);
        sourceLine.appendChild(safeLink(doc, sourceTitle, source.url));
      });
      li.appendChild(sourceLine);
      var taxon = relation.taxon;
      if (taxon && typeof taxon === "object" && typeof taxon.scientific_name === "string" && taxon.scientific_name.trim()) {
        var button = doc.createElement("button");
        button.type = "button";
        button.className = "name-relation-choose";
        button.textContent = speciesLabel(taxon) + (domestic ? " · 관련 야생종 자료 보기" : " · 연결된 종 자료 보기");
        button.addEventListener("click", function () { choose(relation); });
        li.appendChild(button);
      }
      list.appendChild(li);
    });
    section.appendChild(list);
    section.appendChild(status);
    section.appendChild(selection);
    if (automatic) { choose(targets[0]); }
    return section;
  }

  /**
   * Lazy "통칭·가축형 관계 알아보기" button for the species explanation area.
   * Nothing is fetched until the first expand; a failed load can be retried
   * by collapsing and expanding again, and repeated clicks while a request
   * is in flight never start a second one.
   */
  function buildParentSpeciesExplorer(doc, profile, fetcher, isActive) {
    var section = doc.createElement("section");
    section.className = "species-parent-explorer";
    var parent = profile.parent_species && profile.parent_species.taxon;
    if (!parent) { return section; }
    var button = doc.createElement("button");
    button.type = "button";
    button.textContent = "상위 종 " + nameRelationTaxonLabel(parent) + " 자료 보기";
    var content = doc.createElement("div");
    section.appendChild(button);
    section.appendChild(content);
    var pending = false;
    button.addEventListener("click", function () {
      if (pending) { return; }
      pending = true;
      fetchTaxaJson(doc, fetcher, "/v1/taxa/profile", parent.scientific_name, 60000).then(function (other) {
        pending = false;
        if (typeof isActive === "function" && !isActive()) { return; }
        if (!other.taxon || other.taxon.taxon_id !== parent.taxon_id || !other.lineage || !profile.lineage || other.lineage.concept_set_id !== profile.lineage.concept_set_id || other.lineage.taxonomy_release !== profile.lineage.taxonomy_release) { throw new Error("changed"); }
        while (content.firstChild) { content.removeChild(content.firstChild); }
        var answer = buildSpeciesAnswer(doc, other);
        if (answer) { content.appendChild(answer); }
        content.appendChild(buildSpeciesBrief(doc, other));
        appendProfilePopup(doc, content, buildSpeciesCard(doc, other, { fetcher: fetcher, isActive: isActive }), other, answer);
      }).catch(function () { pending = false; if (typeof isActive !== "function" || isActive()) { content.textContent = "상위 종 자료를 확인하지 못했습니다. 다시 눌러 재시도하세요."; } });
    });
    return section;
  }

  function buildSubspeciesExplorer(doc, profile, fetcher, isActive, initialData) {
    var active = typeof isActive === "function" ? isActive : function () { return true; };
    var section = doc.createElement("section");
    section.className = "species-subspecies";
    var button = doc.createElement("button");
    button.type = "button";
    button.textContent = "이 종의 아종 살펴보기";
    button.setAttribute("aria-expanded", "false");
    var content = doc.createElement("div");
    content.className = "subspecies-content";
    content.hidden = true;
    var status = doc.createElement("p");
    status.className = "subspecies-status";
    status.hidden = true;
    status.setAttribute("role", "status");
    section.appendChild(button);
    section.appendChild(status);
    section.appendChild(content);
    var loaded = false;
    var pending = false;
    var generation = 0;
    function matches(data) {
      return profile.lineage && data.concept_set_id === profile.lineage.concept_set_id && data.taxonomy_release === profile.lineage.taxonomy_release;
    }
    function load() {
      if (loaded) { content.hidden = !content.hidden; status.hidden = content.hidden; button.setAttribute("aria-expanded", String(!content.hidden)); return; }
      if (pending) { return; }
      pending = true;
      content.hidden = false;
      status.hidden = false;
      button.setAttribute("aria-expanded", "true");
      status.textContent = "아종 목록을 불러오는 중입니다.";
      var dataRequest = initialData ? Promise.resolve(initialData) : fetchTaxaJson(doc, fetcher, "/v1/taxa/subspecies", profile.taxon.scientific_name, 30000);
      initialData = null;
      dataRequest.then(function (data) {
        pending = false;
        if (!active()) { return; }
        if (!matches(data) || !data.parent_species || !data.parent_species.taxon || data.parent_species.taxon.taxon_id !== profile.taxon.taxon_id || !Array.isArray(data.subspecies)) { throw new Error("changed"); }
        loaded = true;
        status.textContent = data.subspecies.length ? "아종의 이름과 분포를 살펴보세요." : "이 분류 기준에서 연결된 아종이 없습니다.";
        if (data.source_url) { var source = doc.createElement("p"); source.className = "subspecies-source"; source.appendChild(safeLink(doc, "분류 기준 · AviList", data.source_url)); content.appendChild(source); }
        if (data.has_more) { var notice = doc.createElement("p"); notice.textContent = "일부 아종만 표시합니다. 전체 목록은 분류 출처에서 확인하세요."; content.appendChild(notice); }
        var selected = doc.createElement("div");
        var labels = data.subspecies.map(function (taxon, index) { return (taxon.korean_name_status !== "machine-translated" && taxon.korean_name) || taxon.english_name || taxon.display_label || speciesLabel(data.parent_species.taxon) + " 아종 " + (index + 1); });
        data.subspecies.forEach(function (taxon, index) {
          var entry = buildComparisonPeer(doc, taxon, false);
          entry.row.className += " subspecies-peer";
          var label = labels[index];
          if (labels.filter(function (other) { return other === label; }).length > 1) { label += " · 아종 " + (index + 1); }
          entry.row.children[0].children[0].textContent = label;
          // Scientific identity and reference links stay available without dominating the list.
          var scientific = entry.row.children[0].children[1];
          entry.row.children[0].removeChild(scientific);
          var info = doc.createElement("details"); info.className = "subspecies-identity";
          var infoTitle = doc.createElement("summary"); infoTitle.textContent = "학명·출처"; info.appendChild(infoTitle);
          info.appendChild(scientific);
          if (taxon.english_name_source_url) { info.appendChild(safeLink(doc, "영어 이름 출처", taxon.english_name_source_url)); }
          if (taxon.description_source_url) { info.appendChild(safeLink(doc, "분포 설명 출처", taxon.description_source_url)); }
          if (typeof taxon.range_text === "string" && taxon.range_text.trim()) { var range = doc.createElement("p"); range.className = "subspecies-range-original"; range.setAttribute("lang", "en"); range.textContent = taxon.range_text; info.appendChild(range); }
          if (!taxon.korean_name && !taxon.english_name) { var unnamed = doc.createElement("p"); unnamed.textContent = "별도 한국어·영어 통칭은 확인되지 않았습니다." + (taxon.display_label && taxon.range_text ? " 제목은 분포를 이용한 설명이며 정식 아종명이 아닙니다." : ""); info.appendChild(unnamed); }
          entry.row.appendChild(info);
          if (typeof taxon.description === "string" && taxon.description.trim()) {
            var description = doc.createElement("p"); description.className = "subspecies-description";
            if (taxon.description_language === "en") {
              description.textContent = "분포(영어 원문): ";
              var original = doc.createElement("span"); original.setAttribute("lang", "en"); original.textContent = taxon.description; description.appendChild(original);
            } else { description.textContent = taxon.description.replace(/^분포 차이:\s*/, ""); }
            entry.row.children[0].appendChild(description);
          }
          var choice = entry.button;
          choice.textContent = "아종 보기";
          choice.setAttribute("aria-label", label + " · 아종 자료 보기");
          choice.addEventListener("click", function () {
            var current = ++generation;
            status.textContent = "아종 자료를 불러오는 중입니다.";
            fetchTaxaJson(doc, fetcher, "/v1/taxa/profile", taxon.scientific_name, 60000).then(function (other) {
              if (!active() || current !== generation) { return; }
              if (!other.taxon || other.taxon.rank !== "subspecies" || other.taxon.taxon_id !== taxon.taxon_id || !other.lineage || !matches(other.lineage)) { throw new Error("changed"); }
              while (selected.firstChild) { selected.removeChild(selected.firstChild); }
              var answer = buildSpeciesAnswer(doc, other);
              if (answer) { selected.appendChild(answer); }
              var card = buildSpeciesCard(doc, other, { fetcher: fetcher, isActive: active });
              selected.appendChild(buildSpeciesBrief(doc, other));
              appendProfilePopup(doc, selected, card, other, answer);
              status.textContent = "선택한 아종의 자료를 불러왔습니다.";
            }).catch(function () { if (active() && current === generation) { status.textContent = "아종 자료를 확인하지 못했습니다. 다시 선택하세요."; } });
          });
          content.appendChild(entry.row);
        });
        content.appendChild(selected);
      }).catch(function () { pending = false; if (active()) { status.textContent = "아종 목록을 확인하지 못했습니다. 다시 눌러 재시도하세요."; } });
    }
    button.addEventListener("click", load);
    if (initialData) { load(); }
    return section;
  }

  function buildNameRelationsExplorer(doc, profile, fetcher, isActive) {
    var active = typeof isActive === "function" ? isActive : function () { return true; };
    var section = doc.createElement("section");
    section.className = "species-name-relations";
    var open = doc.createElement("button");
    open.type = "button";
    open.textContent = "통칭·가축형 관계 알아보기";
    open.setAttribute("aria-expanded", "false");
    section.appendChild(open);
    var content = doc.createElement("div");
    content.hidden = true;
    section.appendChild(content);
    var status = doc.createElement("p");
    status.setAttribute("role", "status");
    content.appendChild(status);
    var results = doc.createElement("div");
    content.appendChild(results);
    var state = "idle";
    var lineage = profile && profile.lineage;
    open.addEventListener("click", function () {
      content.hidden = !content.hidden;
      open.setAttribute("aria-expanded", String(!content.hidden));
      if (content.hidden || state !== "idle") { return; }
      state = "loading";
      status.textContent = "통칭·가축형 관계를 조회하는 중입니다.";
      fetchTaxaJson(doc, fetcher, "/v1/taxa/name-relations", profile.taxon.scientific_name, 30000).then(function (data) {
        if (!isNameRelationsPayload(data)) {
          var unsupported = new Error("unsupported"); unsupported.unsupported = true;
          throw unsupported;
        }
        if (lineage && lineage.concept_set_id && (data.concept_set_id !== lineage.concept_set_id || data.taxonomy_release !== lineage.taxonomy_release)) {
          throw new Error("changed");
        }
        if (!active()) { return; }
        while (results.firstChild) { results.removeChild(results.firstChild); }
        results.appendChild(buildNameRelations(doc, data, fetcher, active));
        state = "loaded";
        status.textContent = data.relations.length ? "통칭·가축형 관계를 불러왔습니다." : "출처가 확인된 통칭·가축형 관계가 없습니다.";
      }).catch(function (error) {
        state = "idle";
        if (!active()) { return; }
        status.textContent = error && error.message === "changed"
          ? "분류 자료가 갱신되었습니다. 질문을 다시 보내주세요."
          : nameRelationsErrorText(error) + " 접었다 다시 펼쳐 재시도할 수 있습니다.";
      });
    });
    return section;
  }

  var PHOTO_PLACEHOLDER_PATH = "M4 15c2-4 6-6 10-5l4-3 1 2-2 2c1 3-1 7-6 8H6 M14 10l-2 3 M11 9.5a.5.5 0 1 0 1 0 .5.5 0 1 0-1 0 M6 18l-2 3";
  // Fixed copy per backend photo status; the server's own `message` is not
  // echoed so an unexpected status never surfaces as trusted text.
  var PHOTO_STATUS_MESSAGES = {
    cancelled: "사진 조회를 중단했습니다. 질문을 다시 보내 확인하세요.",
    available: "출처와 라이선스가 확인된 사진입니다.",
    no_licensed_photo: "사용 조건이 확인된 대표 사진을 아직 찾지 못했습니다.",
    unconfirmed_taxon: "사진 자료의 종 식별을 확인하지 못해 사진을 표시하지 않습니다.",
    ambiguous_taxon: "사진 자료가 여러 종 식별자에 연결되어 대표 사진을 선택하지 않았습니다.",
    provider_unavailable: "사진 제공처에 연결하지 못했습니다.",
  };

  function photoAvailabilityInfo(availability) {
    var status = availability && typeof availability === "object" ? availability.status : null;
    if (typeof status === "string" && Object.prototype.hasOwnProperty.call(PHOTO_STATUS_MESSAGES, status) && status !== "available") {
      return { status: status, message: PHOTO_STATUS_MESSAGES[status] };
    }
    // No status, "available" with zero displayable photos (all filtered as
    // unsafe), or an unknown status: one honest generic reason.
    return { status: "none", message: "라이선스가 확인된 대표 사진이 없습니다." };
  }

  function buildSpeciesCard(doc, profile, options) {
    if (!profile || typeof profile !== "object" || !profile.taxon) {
      return null;
    }
    var cardOptions = options || {};
    var taxon = profile.taxon;
    var conservation = conservationInfo(profile.conservation, profile.taxon);
    var card = doc.createElement("div");
    card.className = "species-card risk-" + conservation.tier;
    card.setAttribute("data-conservation-tier", conservation.tier);

    var title = doc.createElement("p");
    title.className = "species-title";
    var koreanTitle = taxon.korean_name_status !== "machine-translated" && typeof taxon.korean_name === "string" ? taxon.korean_name.trim() : "";
    var englishTitle = typeof taxon.english_name === "string" ? taxon.english_name.trim() : "";
    title.textContent = koreanTitle || englishTitle || speciesLabel(taxon);
    var heading = doc.createElement("div");
    heading.className = "species-card-heading";
    var category = doc.createElement("span");
    category.className = "species-category";
    category.textContent = taxon.rank === "subspecies" ? "아종" : "조류 도감";
    heading.appendChild(category);
    var names = doc.createElement("div");
    names.className = "species-card-names";
    names.appendChild(title);
    if (koreanTitle && englishTitle && koreanTitle !== englishTitle) {
      var englishName = doc.createElement("small");
      englishName.className = "species-english-name";
      englishName.textContent = englishTitle;
      names.appendChild(englishName);
    }
    heading.appendChild(names);
    heading.appendChild(buildHabitatEmblem(doc, habitatEmblemInfo(profile)));
    card.appendChild(heading);

    if ((taxon.korean_name || taxon.english_name) && taxon.scientific_name) {
      var scientificName = doc.createElement("p");
      scientificName.className = "species-scientific-name";
      scientificName.textContent = taxon.scientific_name;
      card.appendChild(scientificName);
    }

    if (taxon.rank === "subspecies" && profile.parent_species && profile.parent_species.taxon) {
      var parent = doc.createElement("p");
      parent.className = "species-parent";
      parent.textContent = "소속 종: " + nameRelationTaxonLabel(profile.parent_species.taxon);
      card.appendChild(parent);
    }
    var conservationBadge = doc.createElement("p");
    conservationBadge.className = "species-conservation-badge";
    conservationBadge.textContent = conservation.badgeText;
    conservationBadge.setAttribute("title", conservation.note || CONSERVATION_NOTE);
    card.appendChild(conservationBadge);

    var front = doc.createElement("section");
    front.className = "species-card-front";
    front.setAttribute("aria-label", "주요 특징");
    front.tabIndex = 0;
    var back = doc.createElement("section");
    back.className = "species-card-back";
    back.setAttribute("aria-label", "상세 정보");
    back.tabIndex = 0;
    back.hidden = true;
    var faces = doc.createElement("div");
    faces.className = "species-card-faces";
    faces.appendChild(front);
    faces.appendChild(back);
    card.appendChild(faces);
    var backTitle = doc.createElement("h3");
    backTitle.textContent = "상세 정보";
    back.appendChild(backTitle);
    var cardSources = doc.createElement("div");
    cardSources.className = "species-profile-source-material";
    card.sourceMaterial = cardSources;
    card.refreshSources = function () {
      if (card.onSourcesChanged) { card.onSourcesChanged(); }
      if (card.requestFit) { card.requestFit(); }
    };
    function sourceSection(className, headingText) {
      var section = doc.createElement("section");
      section.className = className;
      var heading = doc.createElement("h4");
      heading.textContent = headingText;
      section.appendChild(heading);
      return section;
    }
    var dataNotes = sourceSection("species-data-notes", "자료 해석 안내");
    var observationArea = doc.createElement("section");
    observationArea.className = "species-observation-points";
    var observationSourcesSlot = doc.createElement("div");
    observationSourcesSlot.className = "species-observation-sources-slot";
    cardSources.appendChild(observationSourcesSlot);
    var observationSections = profile.sections;
    var observationPending = !!profile.enrichment_pending;
    var observationMessage = "";

    function renderObservations() {
      clearNode(observationArea); clearNode(observationSourcesSlot);
      var heading = doc.createElement("h4"); heading.textContent = "관찰 포인트";
      observationArea.appendChild(heading);
      var selected = [];
      var seenTexts = Object.create(null);
      // Species-level notes cannot establish an individual subspecies' features.
      if (taxon.rank !== "subspecies") {
        ["appearance", "fun_facts"].forEach(function (key) {
          (Array.isArray(observationSections) ? observationSections : []).forEach(function (section) {
            if (!section || section.key !== key) { return; }
            (Array.isArray(section.items) ? section.items : []).forEach(function (item) {
              if (selected.length >= 2 || !item || typeof item.text !== "string" || !item.text.trim() ||
                  typeof item.source_name !== "string" || !item.source_name.trim() || !sanitizeUrl(item.source_url)) { return; }
              var text = item.text.trim();
              if (/^(?:평균\s+)?(?:부리 길이\s*\(전체\)|접은 날개 길이|꼬리 길이)\s*:/.test(text) || seenTexts[text]) { return; }
              seenTexts[text] = true; selected.push({ item: item, kind: key });
            });
          });
        });
      }
      var state = selected.length ? "ready" : taxon.rank === "subspecies" ? "subspecies" : observationPending ? "pending" : "unavailable";
      observationArea.setAttribute("data-observation-state", state);
      if (!selected.length) {
        var empty = doc.createElement("p"); empty.className = "species-observation-empty";
        empty.textContent = state === "subspecies" ? "이 아종만의 관찰 특징은 아직 확인하지 못했습니다." : state === "pending"
          ? "‘더 알아보기’에서 추가 자료를 확인하세요." : observationMessage || "출처가 확인된 관찰 자료가 아직 없습니다.";
        observationArea.appendChild(empty);
      } else {
        var list = doc.createElement("ul"); list.className = "species-observation-list";
        var sources = sourceSection("species-observation-sources", "관찰 포인트 근거");
        selected.forEach(function (selection) {
          var item = selection.item;
          var li = doc.createElement("li");
          if (selection.kind === "fun_facts") {
            var kind = doc.createElement("span"); kind.className = "species-observation-kind"; kind.textContent = "알아두기"; li.appendChild(kind);
          }
          var text = doc.createElement("span"); text.textContent = item.text; li.appendChild(text); list.appendChild(li);
          var entry = doc.createElement("section"); entry.className = "species-observation-source-entry";
          var quote = doc.createElement("blockquote"); quote.textContent = item.text; entry.appendChild(quote);
          entry.appendChild(safeLink(doc, item.source_name, item.source_url));
          // Retain every supplied provenance field, including nested citation
          // metadata, without turning raw text or URLs into executable markup.
          var provenanceLabels = { license_name: "이용 조건", license_url: "이용 조건 주소", release: "자료 릴리스", source_release: "자료 릴리스", locator: "자료 위치", evidence_id: "근거 ID", citation: "인용 정보" };
          Object.keys(item).forEach(function (key) {
            if (["text", "source_name", "source_url"].indexOf(key) !== -1 || item[key] == null) { return; }
            var meta = doc.createElement("p");
            meta.textContent = (provenanceLabels[key] || key) + ": " + (typeof item[key] === "object" ? JSON.stringify(item[key]) : String(item[key]));
            entry.appendChild(meta);
          });
          sources.appendChild(entry);
        });
        observationArea.appendChild(list); observationSourcesSlot.appendChild(sources);
      }
      card.refreshSources();
    }
    if (taxon.rank === "subspecies") {
      var metadata = profile.subspecies_metadata;
      var metadataSection = metadata && metadata.section;
      var metadataSource = metadata && sanitizeUrl(metadata.source_url);
      var description = doc.createElement("p");
      description.className = "species-subspecies-description";
      var descriptions = metadataSection && metadataSection.key === "subspecies_taxonomy" && Array.isArray(metadataSection.items) ? metadataSection.items.slice(1).filter(function (item) { return item && typeof item.text === "string" && item.text.trim() && sanitizeUrl(item.source_url); }).map(function (item) { return item.text; }) : [];
      description.textContent = metadataSource && descriptions.length ? descriptions.join(" ") : "이 아종만의 외형·분포 차이는 검토된 자료에서 아직 확인하지 못했습니다.";
      front.appendChild(description);
      if (metadataSource) {
        var metadataDetails = sourceSection("card-details species-subspecies-sources", "분류·아종 설명 출처");
        metadataDetails.appendChild(safeLink(doc, metadata.source_name || "분류 출처", metadataSource));
        if (taxon.english_name_source_url) { metadataDetails.appendChild(safeLink(doc, "영어 이름 출처", taxon.english_name_source_url)); }
        var descriptionSources = {};
        (metadataSection && Array.isArray(metadataSection.items) ? metadataSection.items.slice(1) : []).forEach(function (item) {
          var url = item && sanitizeUrl(item.source_url);
          if (url && url !== metadataSource && !descriptionSources[url]) { descriptionSources[url] = true; metadataDetails.appendChild(safeLink(doc, item.source_name || "분포 설명 출처", url)); }
        });
        if (typeof metadata.range_raw === "string" && metadata.range_raw.trim()) {
          var rawRange = doc.createElement("blockquote");
          rawRange.textContent = metadata.range_raw;
          metadataDetails.appendChild(rawRange);
        }
        cardSources.appendChild(metadataDetails);
      }
    }

    // Photos live in their own slots so a provider retry can re-render them
    // without touching the facts, flip state, or the explanation.
    var photoArea = doc.createElement("div");
    photoArea.className = "species-photo-area";
    front.appendChild(photoArea);
    var photoSourcesSlot = doc.createElement("div");
    photoSourcesSlot.className = "species-photo-sources-slot";
    cardSources.appendChild(photoSourcesSlot);
    var photoRetrying = false;

    function clearNode(node) {
      while (node.firstChild) { node.removeChild(node.firstChild); }
    }

    function buildPhotoPlaceholder(reasonText) {
      var placeholder = doc.createElement("div");
      placeholder.className = "species-photo-placeholder";
      placeholder.setAttribute("role", "img");
      placeholder.setAttribute("aria-label", "사진 없음: " + reasonText);
      if (typeof doc.createElementNS === "function") {
        var svg = doc.createElementNS(SVG_NS, "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("focusable", "false");
        var path = doc.createElementNS(SVG_NS, "path");
        // A deliberately generic bird outline, not any particular species.
        path.setAttribute("d", PHOTO_PLACEHOLDER_PATH);
        svg.appendChild(path);
        placeholder.appendChild(svg);
      } else {
        var glyph = doc.createElement("span");
        glyph.setAttribute("aria-hidden", "true");
        glyph.textContent = "◌";
        placeholder.appendChild(glyph);
      }
      var reason = doc.createElement("p");
      reason.className = "species-photo-reason";
      reason.textContent = reasonText;
      placeholder.appendChild(reason);
      return placeholder;
    }

    function retryProvider(button, retryStatus) {
      if (photoRetrying) { return; }
      photoRetrying = true;
      button.disabled = true;
      retryStatus.textContent = "사진 정보를 다시 조회하는 중입니다.";
      var guard = typeof cardOptions.isActive === "function" ? cardOptions.isActive : function () { return true; };
      fetchTaxaJson(doc, cardOptions.fetcher, "/v1/taxa/profile", taxon.scientific_name, 60000).then(function (fresh) {
        photoRetrying = false;
        button.disabled = false;
        if (!guard()) { return; }
        var sameTaxon = fresh && fresh.taxon && fresh.taxon.taxon_id === taxon.taxon_id;
        var lineage = profile.lineage;
        var sameRelease = !lineage || !lineage.concept_set_id || (fresh.lineage &&
          fresh.lineage.concept_set_id === lineage.concept_set_id && fresh.lineage.taxonomy_release === lineage.taxonomy_release);
        if (!sameTaxon || !sameRelease) {
          retryStatus.textContent = "분류 자료가 바뀌어 사진을 갱신하지 않았습니다. 질문을 다시 보내주세요.";
          return;
        }
        card.updateEnrichment(fresh);
      }).catch(function () {
        photoRetrying = false;
        button.disabled = false;
        if (!guard()) { return; }
        retryStatus.textContent = "사진 제공처에 아직 연결하지 못했습니다. 잠시 후 다시 시도하세요.";
      });
    }

    function renderPhotos(images, availability) {
      clearNode(photoArea);
      clearNode(photoSourcesSlot);
      var photoSources = sourceSection("species-photo-sources", "사진 출처 · 라이선스");
      var photoFigures = [];
      var media = doc.createElement("div");
      media.className = "species-media";
      var renderedPhotoCount = 0;
      (Array.isArray(images) ? images : []).slice(0, 6).forEach(function (photo) {
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
        img.alt = speciesLabel(taxon) + " 대표 사진: " + (photo.title || "");
        figure.appendChild(img);
        var broken = doc.createElement("div");
        broken.className = "species-photo-broken";
        broken.hidden = true;
        var brokenText = doc.createElement("p");
        brokenText.setAttribute("role", "status");
        brokenText.textContent = "사진을 불러오지 못했습니다.";
        broken.appendChild(brokenText);
        var reload = doc.createElement("button");
        reload.type = "button";
        reload.className = "species-photo-reload";
        reload.textContent = "사진 다시 불러오기";
        broken.appendChild(reload);
        figure.appendChild(broken);
        img.addEventListener("error", function () {
          img.hidden = true;
          broken.hidden = false;
          figure.setAttribute("data-photo-state", "error");
        });
        img.addEventListener("load", function () {
          img.hidden = false;
          broken.hidden = true;
          figure.setAttribute("data-photo-state", "loaded");
        });
        reload.addEventListener("click", function () {
          broken.hidden = true;
          img.hidden = false;
          figure.setAttribute("data-photo-state", "loading");
          // Re-request exactly the same validated URL; never a substitute.
          if (typeof img.removeAttribute === "function") { img.removeAttribute("src"); }
          img.src = imageSrc;
        });

        var caption = doc.createElement("div");
        caption.className = "species-photo-source";
        var photoLabel = doc.createElement("strong");
        photoLabel.textContent = "사진 " + renderedPhotoCount + " · " + (photo.title || "대표 사진");
        caption.appendChild(photoLabel);
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
        photoSources.appendChild(caption);
        figure.hidden = photoFigures.length > 0;
        photoFigures.push(figure);
        media.appendChild(figure);
      });
      if (renderedPhotoCount === 0) {
        var info = photoAvailabilityInfo(availability);
        photoArea.appendChild(buildPhotoPlaceholder(info.message));
        if (info.status === "provider_unavailable") {
          var retryStatus = doc.createElement("p");
          retryStatus.className = "species-note";
          retryStatus.setAttribute("role", "status");
          var retry = doc.createElement("button");
          retry.type = "button";
          retry.className = "species-photo-retry";
          retry.textContent = "사진 다시 조회";
          var canRetry = !!(cardOptions.fetcher || (doc.defaultView && typeof doc.defaultView.fetch === "function"));
          if (canRetry && taxon.scientific_name) {
            retry.addEventListener("click", function () { retryProvider(retry, retryStatus); });
            photoArea.appendChild(retry);
          } else {
            retryStatus.textContent = "잠시 후 같은 질문을 다시 보내면 사진을 다시 조회합니다.";
          }
          photoArea.appendChild(retryStatus);
        }
        card.refreshSources();
        return;
      }
      photoArea.appendChild(media);
      if (photoFigures.length > 1) {
        var photoControls = doc.createElement("div");
        photoControls.className = "species-photo-controls";
        var previous = doc.createElement("button");
        previous.type = "button";
        previous.textContent = "←";
        previous.setAttribute("aria-label", "이전 사진");
        var count = doc.createElement("span");
        count.setAttribute("aria-live", "polite");
        var next = doc.createElement("button");
        next.type = "button";
        next.textContent = "→";
        next.setAttribute("aria-label", "다음 사진");
        var photoIndex = 0;
        var showPhoto = function (index) {
          photoIndex = index;
          photoFigures.forEach(function (item, i) { item.hidden = i !== index; });
          previous.disabled = index === 0;
          next.disabled = index === photoFigures.length - 1;
          count.textContent = "사진 " + (index + 1) + " / " + photoFigures.length;
        };
        previous.addEventListener("click", function () { showPhoto(Math.max(0, photoIndex - 1)); });
        next.addEventListener("click", function () { showPhoto(Math.min(photoFigures.length - 1, photoIndex + 1)); });
        photoControls.appendChild(previous);
        photoControls.appendChild(count);
        photoControls.appendChild(next);
        showPhoto(0);
        photoArea.appendChild(photoControls);
      }
      photoSourcesSlot.appendChild(photoSources);
      card.refreshSources();
    }
    if (profile.enrichment_pending) {
      photoArea.appendChild(buildPhotoPlaceholder("사진과 추가 설명은 ‘더 알아보기’를 눌러 확인하세요."));
    } else { renderPhotos(profile.images, profile.photo_availability); }
    // A photo-only update leaves notes intact; explicit empty sections clear
    // both the visible notes and their detached provenance. Keep profile
    // untouched here so deferred enrichment can compare initial sections.
    card.updateEnrichment = function (fresh) {
      renderPhotos(fresh.images, fresh.photo_availability);
      if (Object.prototype.hasOwnProperty.call(fresh, "sections")) {
        observationSections = fresh.sections; observationPending = !!fresh.enrichment_pending; observationMessage = "";
        renderObservations();
      }
    };
    card.setEnrichmentMessage = function (message, finished) {
      clearNode(photoArea); photoArea.appendChild(buildPhotoPlaceholder(message));
      if (finished) {
        observationPending = false;
        observationMessage = "추가 관찰 자료를 확인하지 못했습니다. 질문을 다시 보내 확인하세요.";
        renderObservations();
      }
    };

    var dietInfo = dietIconInfo(profile);
    if (dietInfo.icons.length) { front.appendChild(buildDietIcons(doc, dietInfo)); }
    var traitGroups = groupTraits(Array.isArray(profile.traits) ? profile.traits : []);
    var traitSources = sourceSection("species-trait-sources", "형질 · 측정 자료 출처");
    cardSources.appendChild(traitSources);
    var facts = doc.createElement("dl");
    facts.className = "species-quick-facts";
    Object.keys(CARD_BASIC_LABELS).forEach(function (name) {
      var group = traitGroups.find(function (item) { return item.trait.name === name; });
      var trait = group && group.trait;
      var label = doc.createElement("dt");
      label.textContent = trait ? trait.label || CARD_BASIC_LABELS[name] : CARD_BASIC_LABELS[name];
      var value = doc.createElement("dd");
      value.textContent = trait ? cardTraitValue(trait) : "자료 없음";
      facts.appendChild(label);
      facts.appendChild(value);
    });
    front.appendChild(facts);
    var traitNote = doc.createElement("p");
    traitNote.className = "species-note";
    traitNote.textContent =
      "수치는 자료에 기록된 종 평균입니다. 자료마다 먹이 분류가 다를 수 있습니다. 접은 날개 길이는 날개를 펼친 폭(날개폭)과 다릅니다.";
    if (taxon.rank === "subspecies") {
      traitNote.textContent = "아종에 직접 연결된 형질입니다. 종 수준 참고 정보는 별도로 표시합니다.";
      back.appendChild(traitNote);
    } else { dataNotes.appendChild(traitNote); }
    if (taxon.rank === "subspecies" && Array.isArray(profile.reference_traits) && profile.reference_traits.length) {
      var reference = doc.createElement("details");
      reference.className = "card-details species-reference";
      var referenceHeading = doc.createElement("summary");
      referenceHeading.textContent = "종 수준 참고 정보";
      reference.appendChild(referenceHeading);
      var referenceNote = doc.createElement("p");
      referenceNote.textContent = "상위 종의 자료이며 이 아종의 측정값·먹이·서식지로 확정할 수 없습니다.";
      reference.appendChild(referenceNote);
      profile.reference_traits.filter(function (trait) { return trait.reference_scope === "species" && trait.reference_taxon; }).forEach(function (trait) {
        var provenance = doc.createElement("p");
        provenance.className = "species-reference-provenance";
        provenance.textContent = "종 수준 참고 · " + nameRelationTaxonLabel(trait.reference_taxon);
        reference.appendChild(provenance);
        reference.appendChild(buildCardTraitGrid(doc, groupTraits([trait]), traitSources,
          "종 수준 참고 · " + nameRelationTaxonLabel(trait.reference_taxon)));
      });
      back.appendChild(reference);
    }

    if (traitGroups.length === 0) {
      var noTraits = doc.createElement("p");
      noTraits.className = "species-note";
      noTraits.textContent = "조회된 형질(특징·먹이·서식 환경) 정보가 없습니다.";
      front.appendChild(noTraits);
    }
    // Keep basic rows and distribution places even when no data is recorded.
    // Secondary measurements retain their existing optional details panel.
    var prominentGroups = traitGroups.filter(function (group) {
      return DIET_HABITAT_TRAIT_NAMES.indexOf(group.trait.name) !== -1 || PROMINENT_MEASUREMENT_NAMES.indexOf(group.trait.name) !== -1;
    });
    var remainingGroups = traitGroups.filter(function (group) {
      return prominentGroups.indexOf(group) === -1;
    });
    back.appendChild(buildCardTraitGrid(doc, prominentGroups, traitSources, null, true));
    if (remainingGroups.length > 0) {
      var measurementsDetails = doc.createElement("details");
      measurementsDetails.className = "card-details card-details-scroll";
      var measurementsSummary = doc.createElement("summary");
      measurementsSummary.textContent = "측정값 더 보기 (" + remainingGroups.length + ")";
      measurementsDetails.appendChild(measurementsSummary);
      measurementsDetails.appendChild(buildCardTraitGrid(doc, remainingGroups, traitSources));
      back.appendChild(measurementsDetails);
    }
    if (traitSources.children.length === 1) { cardSources.removeChild(traitSources); }
    cardSources.appendChild(buildDietLegend(doc, dietInfo));

    if (typeof profile.vegetation_note === "string" && profile.vegetation_note.trim()) {
      var vegetationNote = doc.createElement("p");
      vegetationNote.className = "vegetation-note";
      vegetationNote.textContent = profile.vegetation_note;
      dataNotes.appendChild(vegetationNote);
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
      back.appendChild(profileWarnList);
      var warningNote = doc.createElement("p");
      warningNote.className = "species-front-note";
      warningNote.textContent = "자료 안내 " + profileWarnings.length + "건 · 뒷면에서 확인";
      front.appendChild(warningNote);
    }
    front.appendChild(observationArea);
    renderObservations();

    var conservationSection = sourceSection("species-conservation-sources", "멸종위기 등급 출처");
    var conservationStatus = doc.createElement("p");
    conservationStatus.textContent = conservation.badgeText;
    conservationSection.appendChild(conservationStatus);
    var rawConservation = profile.conservation && typeof profile.conservation === "object" ? profile.conservation : null;
    if (rawConservation && typeof rawConservation.source_name === "string") {
      var conservationSource = doc.createElement("span");
      conservationSource.className = "trait-source";
      var sourcePrefix = doc.createElement("span");
      sourcePrefix.textContent = "기준 자료: ";
      conservationSource.appendChild(sourcePrefix);
      conservationSource.appendChild(safeLink(doc, rawConservation.source_name,
        (rawConservation.evidence_kind === "red_list_checklist" && !conservation.checklist) ||
          rawConservation.evidence_kind === "manual_override" ? null : rawConservation.source_url));
      var releaseSuffix = doc.createElement("span");
      releaseSuffix.textContent = typeof rawConservation.source_release === "string" && rawConservation.source_release.trim()
        ? " · 릴리스 " + rawConservation.source_release.trim() + " 기준"
        : " · 릴리스 정보 없음";
      conservationSource.appendChild(releaseSuffix);
      conservationSection.appendChild(conservationSource);
      if (conservation.manualOverride) { appendManualOverrideEvidence(doc, conservationSection, rawConservation); }
      var quality = doc.createElement("p");
      quality.className = "species-note";
      quality.textContent = conservation.checklist
        ? "검증 범위: 공개 IUCN 평가목록과 AviList 종명·BirdLife SIS ID 연결 확인. 개별 평가 원문을 독립 검증하거나 최신 평가를 실시간 조회한 결과가 아닙니다."
        : conservation.snapshot
        ? (conservation.category === "NE"
          ? "연결 상태: 평가 대상의 종 범위를 확인해야 합니다. AviList NE를 실제 IUCN 미평가 판정으로 단정할 수 없습니다."
          : "검증 범위: 분류 자료에 기록된 등급과 출처·릴리스 확인. 평가 원문·평가 연도의 독립 검증은 완료되지 않았습니다.")
        : "검증 범위: 출처·자료 버전 확인. 최신 평가를 실시간으로 조회한 결과가 아닙니다.";
      if (conservation.manualOverride) { quality.textContent = "표시 기준: 사용자 요청에 따른 까치 한정 임시 LC 보정 · 독립 평가 검증 전"; }
      else if (!conservation.sourceVerified) { quality.textContent = "출처 또는 자료 버전을 확인하지 못해 카드 색상을 중립으로 표시합니다."; }
      conservationSection.appendChild(quality);
      if (conservation.checklist) {
        var assessmentDetails = doc.createElement("p");
        assessmentDetails.className = "species-note";
        assessmentDetails.textContent = (rawConservation.assessment_year == null ? "평가 연도 확인되지 않음" :
          "개별 평가 연도: " + rawConservation.assessment_year) + " · 평가 범위: 전 세계 (global)";
        conservationSection.appendChild(assessmentDetails);
        conservationSection.appendChild(safeLink(doc, "공식 IUCN 개별 평가 페이지", rawConservation.assessment_reference_url));
        var license = doc.createElement("p");
        license.className = "species-note";
        license.appendChild(safeLink(doc, rawConservation.license_name, rawConservation.license_url));
        conservationSection.appendChild(license);
        ["발행기관: " + rawConservation.publisher, "자료 인용: " + rawConservation.citation,
          "개별 평가 인용: " + rawConservation.assessment_citation].forEach(function (text) {
          var citation = doc.createElement("p");
          citation.className = "species-note";
          citation.textContent = text;
          conservationSection.appendChild(citation);
        });
        if (typeof rawConservation.taxonomy_category_raw === "string" && /^CR\s*\(PEW?\)$/.test(rawConservation.taxonomy_category_raw)) {
          var taxonomyAnnotation = doc.createElement("p");
          taxonomyAnnotation.className = "species-note";
          taxonomyAnnotation.textContent = "AviList 분류 원본 등급: " + rawConservation.taxonomy_category_raw;
          conservationSection.appendChild(taxonomyAnnotation);
        }
      }
      if (typeof rawConservation.snapshot_sha256 === "string" && /^[a-f0-9]{64}$/i.test(rawConservation.snapshot_sha256)) {
        var checksum = doc.createElement("p");
        checksum.className = "species-note";
        checksum.textContent = "원자료 SHA-256: " + rawConservation.snapshot_sha256;
        conservationSection.appendChild(checksum);
      }
      var referenceUrl = sanitizeUrl(rawConservation.assessment_reference_url);
      if (referenceUrl && new URL(referenceUrl).hostname === "datazone.birdlife.org" && new URL(referenceUrl).protocol === "https:" && !new URL(referenceUrl).username && !new URL(referenceUrl).password && (!new URL(referenceUrl).port || new URL(referenceUrl).port === "443") && conservation.category !== "NE") {
        conservationSection.appendChild(safeLink(doc, "평가 참고 페이지 (원문 독립 검증 전)", referenceUrl));
      }
      var rawCategory = typeof rawConservation.category_raw === "string" ? rawConservation.category_raw.trim().toUpperCase() : "";
      if (/^CR\s*\(PEW?\)$/.test(rawCategory)) {
        var annotation = doc.createElement("p");
        annotation.className = "species-note";
        annotation.textContent = "원본 등급: " + rawCategory + (/^CR\s*\(PE\)$/.test(rawCategory) ? " · 절멸 가능성이 있는 위급종" : " · 야생절멸 가능성이 있는 위급종");
        conservationSection.appendChild(annotation);
      }
    } else {
      var noConservation = doc.createElement("p");
      noConservation.textContent = "검증된 멸종위기 등급 자료가 없어 카드 색상을 중립으로 표시합니다.";
      conservationSection.appendChild(noConservation);
    }
    var conservationNote = doc.createElement("p");
    conservationNote.className = "species-note";
    conservationNote.textContent = conservation.manualOverride ? PICA_SERICA_OVERRIDE_NOTE : CONSERVATION_NOTE;
    conservationSection.appendChild(conservationNote);
    cardSources.appendChild(conservationSection);

    var lineage = profile.lineage;
    var lineageItems = lineage && Array.isArray(lineage.items) ? lineage.items : [];
    if (lineageItems.length > 0) {
      var lineageDetails = doc.createElement("details");
      lineageDetails.className = "card-details card-details-scroll";
      var lineageSummary = doc.createElement("summary");
      lineageSummary.textContent = "분류 계통 보기";
      lineageDetails.appendChild(lineageSummary);
      var lineageSources = sourceSection("species-lineage-sources", "분류 계통 · 이름 출처");
      var lineageBasis = doc.createElement("p");
      lineageBasis.textContent = [lineage.taxonomy_source, lineage.taxonomy_release, lineage.concept_set_id].filter(Boolean).join(" · ") || "분류 출처 정보 없음";
      lineageSources.appendChild(lineageBasis);

      var lineageList = doc.createElement("ul");
      lineageList.className = "lineage-list";
      lineageItems.forEach(function (lineageItem) {
        if (!lineageItem || typeof lineageItem !== "object") {
          return;
        }
        var li = doc.createElement("li");
        var rankLabel = RANK_LABELS[lineageItem.rank] ? RANK_LABELS[lineageItem.rank] : lineageItem.rank;
        var commonName = lineageItem.korean_name || lineageItem.english_name ? speciesLabel(lineageItem) : null;
        var namePart = commonName ? commonName + " · " + lineageItem.scientific_name : lineageItem.scientific_name;
        li.textContent = rankLabel + ": " + namePart;
        var koreanNameSourceUrl = sanitizeUrl(lineageItem.korean_name_source_url);
        if (koreanNameSourceUrl) {
          var nameSource = doc.createElement("p");
          nameSource.appendChild(safeLink(doc, rankLabel + ": " + namePart + " · 국명 참고 출처", koreanNameSourceUrl));
          lineageSources.appendChild(nameSource);
        }
        lineageList.appendChild(li);
      });
      lineageDetails.appendChild(lineageList);
      back.appendChild(lineageDetails);
      cardSources.appendChild(lineageSources);
    }
    if (dataNotes.children.length > 1) { cardSources.appendChild(dataNotes); }

    var flipping = false;
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "group");
    card.setAttribute("aria-roledescription", "양면 조류 카드");
    card.setAttribute("aria-keyshortcuts", "Enter Space");
    function showFace(showBack) {
      clearDistributionTooltips(card);
      back.hidden = !showBack;
      front.hidden = showBack;
      // Both faces contribute to the shared grid height. Only the visible face
      // may receive focus, pointer input or accessibility navigation.
      front.inert = !!showBack;
      back.inert = !showBack;
      front.setAttribute("aria-hidden", String(!!showBack));
      back.setAttribute("aria-hidden", String(!showBack));
      card.setAttribute("data-face", showBack ? "back" : "front");
      card.setAttribute("aria-label", speciesLabel(taxon) + " 도감 카드 · " + (showBack ? "뒷면 상세 정보" : "앞면 주요 특징") + " · 좌우 드래그 또는 Enter·Space로 뒤집기");
      var dialog = popupDialog(card);
      if (dialog) { dialog.scrollTop = 0; }
      front.scrollTop = 0; back.scrollTop = 0;
      if (typeof card.resetFitScroll === "function") { card.resetFitScroll(); }
    }
    var flipAnimation = null;
    var flipTarget = null;
    var flipGeneration = 0;
    var drag = null;
    var suppressClick = false;
    var suppressGeneration = 0;
    var DRAG_SLOP = 6;
    var TOUCH_SLOP = 10;
    var DRAG_MAX_ANGLE = 90;
    // Glossy coat (RG-015): a noninteractive overlay whose sheen position and
    // strength are pure functions of the card's current rotation angle, so it
    // travels with the card, reverses with the drag direction, and is animated
    // with the same duration/easing as the card transform. At rest it is
    // invisible (CSS opacity 0), so nothing can stay highlighted.
    var gloss = doc.createElement("div");
    gloss.className = "species-card-gloss";
    gloss.setAttribute("aria-hidden", "true");
    var glossAnimation = null;
    // Strength rises quickly (concave) so the sheen is clearly visible by
    // ~20-30deg yet is exactly 0 flat; the position stays linear in the angle.
    function glossFrame(angle) {
      var a = Math.max(-DRAG_MAX_ANGLE, Math.min(DRAG_MAX_ANGLE, angle));
      var strength = Math.pow(Math.abs(a) / DRAG_MAX_ANGLE, 0.6) * 0.95;
      return { backgroundPosition: (50 + a / DRAG_MAX_ANGLE * 30) + "% 0%", opacity: String(Math.round(strength * 1000) / 1000) };
    }
    function setGlossAngle(angle) {
      if (!gloss.style) { return; }
      var frame = glossFrame(angle);
      gloss.style.backgroundPosition = frame.backgroundPosition;
      gloss.style.opacity = frame.opacity;
    }
    function clearGloss() {
      if (glossAnimation) { glossAnimation.cancel(); glossAnimation = null; }
      if (gloss.style) { gloss.style.backgroundPosition = ""; gloss.style.opacity = ""; }
    }
    // Runs the sheen alongside a card animation: same options object values,
    // started in the same task, keyframes derived from the same angles.
    // stops: [{ angle, offset? }]
    function animateGloss(stops, options) {
      if (typeof gloss.animate !== "function") { return null; }
      // The strength curve is not linear in the angle, so each segment is split
      // into sub-keyframes at angles interpolated linearly in time. The card's
      // transform interpolates the angle linearly under the same easing, so the
      // sheen stays locked to the card's pose.
      var SUBDIVISIONS = 4;
      var frames = [];
      stops.forEach(function (stop, index) {
        var offset = stop.offset !== undefined ? stop.offset : index / (stops.length - 1);
        if (index > 0) {
          var prev = stops[index - 1];
          var prevOffset = prev.offset !== undefined ? prev.offset : (index - 1) / (stops.length - 1);
          // Sub-sample times plus the exact sign change (angle 0 => strength 0),
          // which would otherwise be interpolated to a nonzero strength.
          var times = [];
          for (var k = 1; k < SUBDIVISIONS; k += 1) { times.push({ t: k / SUBDIVISIONS, zero: false }); }
          if (prev.angle * stop.angle < 0) {
            var zeroAt = prev.angle / (prev.angle - stop.angle);
            times = times.filter(function (entry) { return Math.abs(entry.t - zeroAt) > 1e-6; });
            times.push({ t: zeroAt, zero: true });
            times.sort(function (a, b) { return a.t - b.t; });
          }
          times.forEach(function (entry) {
            var mid = glossFrame(entry.zero ? 0 : prev.angle + (stop.angle - prev.angle) * entry.t);
            mid.offset = prevOffset + (offset - prevOffset) * entry.t;
            frames.push(mid);
          });
        }
        var frame = glossFrame(stop.angle);
        frame.offset = offset;
        frames.push(frame);
      });
      var previous = glossAnimation;
      glossAnimation = gloss.animate(frames, options);
      if (previous) { previous.cancel(); }
      return glossAnimation;
    }
    function dragView() { return doc.defaultView || null; }
    function clearDragStyle(target) {
      if (target && target.style) {
        target.style.transform = "";
        target.style.filter = "";
        target.style.userSelect = "";
      }
      if (target) {
        target.setAttribute("data-dragging", "false");
        target.setAttribute("data-drag-commit", "false");
      }
      card.setAttribute("data-dragging", "false");
      card.setAttribute("data-drag-commit", "false");
      if (gloss.style) { gloss.style.backgroundPosition = ""; gloss.style.opacity = ""; }
    }
    function addDragGuard(owner, type, fn, capture) {
      if (!owner || !owner.addEventListener) { return; }
      owner.addEventListener(type, fn, !!capture);
      drag.guards.push({ owner: owner, type: type, fn: fn, capture: !!capture });
    }
    function detachDragGuards() {
      if (!drag || !drag.guards) { return; }
      drag.guards.forEach(function (g) {
        if (g.owner.removeEventListener) { g.owner.removeEventListener(g.type, g.fn, g.capture); }
      });
      drag.guards = [];
    }
    function hasActiveSelection() {
      var view = dragView();
      var selection = view && view.getSelection ? view.getSelection() : null;
      return !!(selection && selection.isCollapsed === false && (selection.rangeCount === undefined || selection.rangeCount > 0));
    }
    // Drops any in-progress drag without flipping: used by pointercancel,
    // lostpointercapture, blur/resize, reopening, and conversation reset.
    function cancelDrag() {
      if (!drag) { return; }
      var current = drag;
      detachDragGuards();
      drag = null;
      if (current.captured && card.releasePointerCapture) {
        try { card.releasePointerCapture(current.pointerId); } catch (error) { /* capture already gone */ }
      }
      clearDragStyle(current.target);
    }
    function resetFlip() {
      clearDistributionTooltips(card);
      flipGeneration += 1;
      if (flipAnimation) { flipAnimation.cancel(); flipAnimation = null; }
      clearGloss();
      if (flipTarget) { flipTarget.setAttribute("data-flipping", "false"); }
      flipping = false; card.setAttribute("aria-busy", "false");
      cancelDrag();
    }
    card.showFront = function () { suppressClick = false; suppressGeneration += 1; resetFlip(); showFace(false); };
    function flipCard() {
      if (flipping) { return; }
      cancelDrag();
      var showBack = back.hidden;
      var view = doc.defaultView;
      var reducedMotion = view && view.matchMedia && view.matchMedia("(prefers-reduced-motion: reduce)").matches;
      var target = popupDialog(card) || card;
      if (reducedMotion || typeof target.animate !== "function") { showFace(showBack); return; }
      flipTarget = target;
      flipping = true; card.setAttribute("aria-busy", "true");
      target.setAttribute("data-flipping", "true");
      var generation = ++flipGeneration;
      var direction = showBack ? 1 : -1;
      function pose(angle, tilt, scale) {
        return "perspective(1100px) rotateY(" + angle + "deg) rotateZ(" + tilt + "deg) scale(" + scale + ")";
      }
      flipAnimation = target.animate([
        { transform: pose(0, 0, 1), filter: "brightness(1)" },
        { transform: pose(90 * direction, -3 * direction, .94), filter: "brightness(1.2)" }
      ], { duration: 270, easing: "cubic-bezier(.45,0,.8,.4)", fill: "both" });
      animateGloss([{ angle: 0 }, { angle: 90 * direction }], { duration: 270, easing: "cubic-bezier(.45,0,.8,.4)", fill: "both" });
      flipAnimation.onfinish = function () {
        if (generation !== flipGeneration) { return; }
        var outgoing = flipAnimation;
        showFace(showBack);
        flipAnimation = target.animate([
          { transform: pose(-90 * direction, 3 * direction, .94), filter: "brightness(1.2)" },
          { transform: pose(5 * direction, -.6 * direction, 1.01), filter: "brightness(1.03)", offset: .82 },
          { transform: pose(0, 0, 1), filter: "brightness(1)" }
        ], { duration: 390, easing: "cubic-bezier(.15,.65,.25,1)", fill: "both" });
        animateGloss([{ angle: -90 * direction }, { angle: 5 * direction, offset: .82 }, { angle: 0 }], { duration: 390, easing: "cubic-bezier(.15,.65,.25,1)", fill: "both" });
        outgoing.cancel();
        flipAnimation.onfinish = function () {
          if (generation === flipGeneration) { resetFlip(); }
        };
      };
    }
    showFace(false);
    card.setAttribute("aria-busy", "false");
    card.addEventListener("keydown", function (event) {
      if (event.target !== card || event.repeat || event.altKey || event.ctrlKey || event.metaKey ||
          (event.key !== "Enter" && event.key !== " ")) { return; }
      event.preventDefault();
      flipCard();
    });

    // Drag-to-flip for the mouse and a primary single touch (pen unsupported).
    // Photos, placeholders and decorative graphics share the card's swipe.
    // Taps still activate controls; horizontal drags over them flip the card.
    // Text editing and explicit media/drag interactions remain native.
    function isDragExempt(node, touch) {
      if (!node) { return true; }
      while (node && node !== card) {
        var tag = String(node.tagName || "").toLowerCase();
        if (tag === "input" || tag === "select" ||
            tag === "textarea" || tag === "label" || tag === "video" || tag === "audio") { return true; }
        if (node.isContentEditable) { return true; }
        var attr = function (name) { return node.getAttribute ? node.getAttribute(name) : null; };
        var editable = attr("contenteditable");
        if (editable !== null && editable !== "false") { return true; }
        if (attr("draggable") === "true" || attr("data-card-drag-exempt") === "true") { return true; }
        var role = attr("role");
        if (role === "textbox") { return true; }
        node = node.parentNode;
      }
      return false;
    }
    function dragTarget() {
      return popupDialog(card) || card;
    }
    function dragPose(angle, scale) {
      return "perspective(1100px) rotateY(" + angle + "deg) scale(" + scale + ")";
    }
    function reducedMotionNow() {
      var view = dragView();
      return !!(view && view.matchMedia && view.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }
    function dragWidth(target) {
      var rect = target.getBoundingClientRect ? target.getBoundingClientRect() : null;
      var width = rect && rect.width ? rect.width : (target.offsetWidth || 320);
      return Math.max(width, 1);
    }
    function dragThreshold(width) { return Math.max(40, width * 0.25); }
    function finishDrag(commit) {
      var current = drag;
      if (!current || !current.active) { cancelDrag(); return; }
      var target = current.target;
      var angle = current.angle;
      var direction = current.dx >= 0 ? 1 : -1;
      var showBack = back.hidden;
      cancelDrag();
      if (commit && (reducedMotion_or_no_animate(target))) { showFace(showBack); return; }
      if (typeof target.animate !== "function") { if (commit) { showFace(showBack); } return; }
      flipTarget = target;
      flipping = true; card.setAttribute("aria-busy", "true");
      var generation = ++flipGeneration;
      if (!commit) {
        flipAnimation = target.animate([
          { transform: dragPose(angle, 1 - Math.abs(angle) / 900) },
          { transform: dragPose(0, 1) }
        ], { duration: 200, easing: "cubic-bezier(.2,.7,.3,1)", fill: "both" });
        animateGloss([{ angle: angle }, { angle: 0 }], { duration: 200, easing: "cubic-bezier(.2,.7,.3,1)", fill: "both" });
        flipAnimation.onfinish = function () { if (generation === flipGeneration) { resetFlip(); } };
        return;
      }
      target.setAttribute("data-flipping", "true");
      var remaining = Math.max(60, 270 * (1 - Math.abs(angle) / DRAG_MAX_ANGLE));
      flipAnimation = target.animate([
        { transform: dragPose(angle, 1 - Math.abs(angle) / 900) },
        { transform: dragPose(DRAG_MAX_ANGLE * direction, .94), filter: "brightness(1.2)" }
      ], { duration: remaining, easing: "cubic-bezier(.45,0,.8,.4)", fill: "both" });
      animateGloss([{ angle: angle }, { angle: DRAG_MAX_ANGLE * direction }], { duration: remaining, easing: "cubic-bezier(.45,0,.8,.4)", fill: "both" });
      flipAnimation.onfinish = function () {
        if (generation !== flipGeneration) { return; }
        var outgoing = flipAnimation;
        showFace(showBack);
        flipAnimation = target.animate([
          { transform: dragPose(-DRAG_MAX_ANGLE * direction, .94), filter: "brightness(1.2)" },
          { transform: dragPose(0, 1), filter: "brightness(1)" }
        ], { duration: 390, easing: "cubic-bezier(.15,.65,.25,1)", fill: "both" });
        animateGloss([{ angle: -DRAG_MAX_ANGLE * direction }, { angle: 0 }], { duration: 390, easing: "cubic-bezier(.15,.65,.25,1)", fill: "both" });
        outgoing.cancel();
        flipAnimation.onfinish = function () { if (generation === flipGeneration) { resetFlip(); } };
      };
    }
    function reducedMotion_or_no_animate(target) {
      return reducedMotionNow() || typeof target.animate !== "function";
    }
    card.addEventListener("pointerdown", function (event) {
      clearDistributionTooltips(card);
      suppressClick = false;
      suppressGeneration += 1; // a stale release timer must not clear a newer swipe's suppression
      if (drag) {
        // A second touch anywhere (pinch) or a touch during a mouse drag ends the gesture.
        if (event.pointerId !== drag.pointerId && (drag.kind === "touch" || event.pointerType === "touch")) { cancelDrag(); }
        return;
      }
      if (flipping) { return; }
      var touch = event.pointerType === "touch";
      if ((!touch && event.pointerType !== "mouse") || event.button !== 0 || event.isPrimary === false) { return; }
      if (!touch && (event.shiftKey || event.altKey || event.ctrlKey || event.metaKey)) { return; }
      if (isDragExempt(event.target, touch)) { return; }
      if (touch && hasActiveSelection()) { return; }
      drag = { kind: touch ? "touch" : "mouse", pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, dx: 0, angle: 0, active: false, captured: false, target: dragTarget(), guards: [] };
      var guard = function () { cancelDrag(); };
      var view = dragView();
      addDragGuard(view, "blur", guard);
      addDragGuard(view, "resize", guard);
      if (touch) {
        // Selection, context menu, or any extra touch anywhere hands control back to the browser.
        addDragGuard(doc, "pointerdown", function (e) { if (drag && e.pointerId !== drag.pointerId) { cancelDrag(); } }, true);
        addDragGuard(doc, "contextmenu", guard, true);
        addDragGuard(doc, "selectionchange", function () { if (hasActiveSelection()) { cancelDrag(); } });
      }
    });
    card.addEventListener("pointermove", function (event) {
      if (!drag || event.pointerId !== drag.pointerId) { return; }
      var touch = drag.kind === "touch";
      // Mouse button released outside the window/card while we weren't capturing.
      // Touch contact reports buttons === 0 only on hover-less releases; not a release signal.
      if (!touch && event.buttons === 0) { cancelDrag(); return; }
      var dx = event.clientX - drag.startX;
      var dy = event.clientY - drag.startY;
      var slop = touch ? TOUCH_SLOP : DRAG_SLOP;
      if (!drag.active) {
        if (Math.abs(dx) < slop || Math.abs(dx) < Math.abs(dy) * 1.2) {
          if (Math.abs(dy) > slop * 2 && Math.abs(dy) > Math.abs(dx)) { cancelDrag(); }
          return;
        }
        drag.active = true;
        drag.width = dragWidth(drag.target);
        // Touch pointers are already implicitly captured by the browser.
        if (!touch && card.setPointerCapture) {
          try { card.setPointerCapture(drag.pointerId); drag.captured = true; } catch (error) { /* pointer already released */ }
        }
        if (!touch) {
          var view = dragView();
          var selection = view && view.getSelection ? view.getSelection() : null;
          if (selection && selection.removeAllRanges) { selection.removeAllRanges(); }
        }
        if (drag.target.style) { drag.target.style.userSelect = "none"; }
        drag.target.setAttribute("data-dragging", "true");
        card.setAttribute("data-dragging", "true");
      }
      if (!touch) { event.preventDefault(); }
      drag.dx = dx;
      var commit = Math.abs(dx) >= dragThreshold(drag.width);
      drag.commit = commit;
      drag.target.setAttribute("data-drag-commit", String(commit));
      card.setAttribute("data-drag-commit", String(commit));
      if (reducedMotionNow()) { return; }
      drag.angle = Math.max(-DRAG_MAX_ANGLE, Math.min(DRAG_MAX_ANGLE, dx / drag.width * 120));
      if (drag.target.style) {
        drag.target.style.transform = dragPose(drag.angle, 1 - Math.abs(drag.angle) / 900);
      }
      setGlossAngle(drag.angle);
    });
    card.addEventListener("pointerup", function (event) {
      if (!drag || event.pointerId !== drag.pointerId) { return; }
      if (!drag.active) { cancelDrag(); return; }
      suppressClick = true;
      var commit = Math.abs(drag.dx) >= dragThreshold(drag.width);
      var delay = drag.kind === "touch" ? 400 : 0;
      var generation = ++suppressGeneration;
      finishDrag(commit);
      var view = dragView();
      if (view && view.setTimeout) { view.setTimeout(function () { if (generation === suppressGeneration) { suppressClick = false; } }, delay); }
    });
    card.addEventListener("pointercancel", function (event) {
      if (drag && event.pointerId === drag.pointerId) { cancelDrag(); }
    });
    card.addEventListener("lostpointercapture", function (event) {
      // Only the tracked pointer counts. Touch holds implicit capture on a child
      // (losing it ends the gesture); mouse capture is explicit on the card, so
      // bubbled child events are ignored.
      if (!drag || event.pointerId !== drag.pointerId) { return; }
      if (drag.kind === "touch") { cancelDrag(); return; }
      if (drag.captured && (!event.target || event.target === card)) { cancelDrag(); }
    });
    // A drag must not also fire the button/link click under the release point.
    card.addEventListener("click", function (event) {
      if (!suppressClick) { return; }
      suppressClick = false;
      event.preventDefault();
      if (event.stopPropagation) { event.stopPropagation(); }
    }, true);
    card.addEventListener("dragstart", function (event) {
      // An image's native drag can start before the flip gesture reaches its slop.
      if (drag) { event.preventDefault(); }
    });

    card.appendChild(gloss);
    return card;
  }

  /**
   * One-line chat summary shown next to the card button: habitat emblem,
   * habitat name, and the validated red-list badge. The prose explanation
   * itself is the server's `answer_text` (built from `profile.summary`).
   */
  function buildTaxonomyAnswer(doc, lineage) {
    var section = doc.createElement("section"); section.className = "taxonomy-answer";
    var header = doc.createElement("div"); header.className = "taxonomy-answer-header";
    var title = doc.createElement("h3"); title.textContent = "분류 계통"; header.appendChild(title);
    var data = lineage && typeof lineage === "object" ? lineage : {};
    [data.taxonomy_source, data.taxonomy_release].forEach(function (value) {
      if (typeof value !== "string" || !value.trim()) { return; }
      var chip = doc.createElement("span"); chip.className = "taxonomy-version-chip"; chip.textContent = value; header.appendChild(chip);
    });
    section.appendChild(header);
    var taxa = (Array.isArray(data.lineage) ? data.lineage : []).filter(function (taxon) { return taxon && typeof taxon === "object"; }).slice(0, 20);
    if (taxa.length) {
      var list = doc.createElement("ol"); list.className = "taxonomy-timeline"; list.setAttribute("aria-label", "상위 분류부터 조회한 분류군까지");
      taxa.forEach(function (taxon, index) {
        var row = doc.createElement("li"); row.className = "taxonomy-taxon";
        if (index === taxa.length - 1) { row.setAttribute("data-terminal", "true"); }
        var rank = typeof taxon.rank === "string" && taxon.rank.trim() ? taxon.rank : "unknown";
        var badge = doc.createElement("span"); badge.className = "taxonomy-rank-badge"; badge.textContent = RANK_LABELS[rank] || "분류"; row.appendChild(badge);
        var identity = doc.createElement("div"); identity.className = "taxonomy-taxon-identity";
        var scientific = typeof taxon.scientific_name === "string" && taxon.scientific_name.trim() ? taxon.scientific_name : null;
        var korean = taxon.korean_name_status !== "machine-translated" && typeof taxon.korean_name === "string" && taxon.korean_name.trim() ? taxon.korean_name : null;
        var name = doc.createElement(korean ? "strong" : "i"); name.className = "taxonomy-taxon-name"; name.textContent = korean || scientific || "이름 미등록"; identity.appendChild(name);
        if (korean && scientific) { var latin = doc.createElement("i"); latin.className = "taxonomy-scientific-name"; latin.textContent = scientific; identity.appendChild(latin); }
        var rankEnglish = doc.createElement("span"); rankEnglish.className = "taxonomy-rank-english"; rankEnglish.textContent = rank === "unknown" ? "분류 단계 미등록" : rank; identity.appendChild(rankEnglish);
        if (korean) {
          var sourceUrl = sanitizeUrl(taxon.korean_name_source_url);
          var naming = doc.createElement("div"); naming.className = "taxonomy-name-provenance";
          var status = doc.createElement("span");
          status.textContent = taxon.korean_name_status === "community-sourced" || taxon.korean_name_status === "community-sourced-reference" ? "참고 국명" : "국명";
          naming.appendChild(status);
          if (sourceUrl) {
            var sourceHost = new URL(sourceUrl).hostname;
            naming.appendChild(safeLink(doc, sourceHost === "www.wikidata.org" || sourceHost === "wikidata.org" ? "Wikidata 출처" : "국명 출처", sourceUrl));
          }
          identity.appendChild(naming);
        }
        row.appendChild(identity); list.appendChild(row);
      });
      section.appendChild(list);
    } else {
      var empty = doc.createElement("p"); empty.className = "taxonomy-empty"; empty.textContent = "표시할 분류 계통 자료가 없습니다."; section.appendChild(empty);
    }
    var details = doc.createElement("details"); details.className = "taxonomy-context-details";
    var summary = doc.createElement("summary"); summary.textContent = "분류 기준 상세"; details.appendChild(summary);
    var concept = doc.createElement("p"); concept.textContent = "개념집합: " + (typeof data.concept_set_id === "string" && data.concept_set_id.trim() ? data.concept_set_id : "미등록"); details.appendChild(concept);
    section.appendChild(details);
    return section;
  }

  function buildQuestionAnswer(doc, questionAnswer, options) {
    if (!questionAnswer || ["diet", "habitat", "activity", "appearance", "related", "ecological_related", "subspecies"].indexOf(questionAnswer.topic) === -1) { return null; }
    var section = doc.createElement("section"); section.className = "species-question-answer";
    var title = doc.createElement("h3"); title.textContent = typeof questionAnswer.title === "string" ? questionAnswer.title : "질문에 대한 답변"; section.appendChild(title);
    var rankedExplorer = options && options.rankedExplorer;
    if (!rankedExplorer) {
      var text = doc.createElement("p"); text.textContent = typeof questionAnswer.text === "string" ? questionAnswer.text : ""; section.appendChild(text);
      var facts = doc.createElement("ul"); facts.className = "question-answer-facts";
      (Array.isArray(questionAnswer.items) ? questionAnswer.items : []).forEach(function (fact) {
        if (!fact || typeof fact.text !== "string" || !fact.text.trim()) { return; }
        var item = doc.createElement("li");
        var value = doc.createElement("span"); value.textContent = fact.text; item.appendChild(value);
        if (typeof fact.source_name === "string" && fact.source_name.trim()) { item.appendChild(safeLink(doc, " · " + fact.source_name, fact.source_url)); }
        facts.appendChild(item);
      });
      if (facts.children.length) { section.appendChild(facts); }
    } else { section.appendChild(rankedExplorer); }
    var context = questionAnswer.name_context;
    if (isNameRelationsPayload(context)) {
      var aliases = doc.createElement("details"); aliases.className = "question-answer-name-context";
      var aliasHeading = doc.createElement("summary"); aliasHeading.textContent = "통칭 연결과 출처"; aliases.appendChild(aliasHeading);
      if (typeof context.summary === "string") { var aliasSummary = doc.createElement("p"); aliasSummary.textContent = context.summary; aliases.appendChild(aliasSummary); }
      context.relations.forEach(function (relation) {
        if (!relation || typeof relation.name !== "string") { return; }
        var relationship = doc.createElement("p");
        relationship.textContent = relation.name + " · " + (relation.relation_label || "이름 관계") + (relation.taxon ? " · " + speciesLabel(relation.taxon) : "");
        aliases.appendChild(relationship);
        if (typeof relation.note === "string") { var aliasNote = doc.createElement("p"); aliasNote.textContent = relation.note; aliases.appendChild(aliasNote); }
        (Array.isArray(relation.sources) ? relation.sources : []).forEach(function (source) {
          if (!source || typeof source.title !== "string") { return; }
          aliases.appendChild(safeLink(doc, source.title, source.url));
        });
      });
      section.appendChild(aliases);
    }

    return section;
  }

  function buildSpeciesAnswer(doc, profile, showBrief) {
    if (!profile || !Array.isArray(profile.sections) || !profile.sections.length) { return null; }
    var answer = doc.createElement("div");
    answer.className = "species-answer";
    var heading = doc.createElement("h3");
    heading.textContent = speciesLabel(profile.taxon);
    answer.appendChild(heading);
    var sources = [];
    var seen = {};
    profile.sections.slice(0, 4).forEach(function (section) {
      if (!section || typeof section.title !== "string") { return; }
      if (profile.enrichment_pending && (!Array.isArray(section.items) || !section.items.some(function (item) {
        return item && typeof item.text === "string" && item.text.trim();
      }))) { return; }
      var block = doc.createElement("section");
      block.className = "species-answer-section";
      var title = doc.createElement("h4");
      title.textContent = section.title;
      block.appendChild(title);
      var items = Array.isArray(section.items) ? section.items.filter(function (item) {
        return item && typeof item.text === "string" && item.text.trim();
      }).slice(0, section.key === "appearance" ? 5 : 4) : [];
      if (items.length) {
        var list = doc.createElement("ul");
        items.forEach(function (item) {
          var li = doc.createElement("li");
          li.textContent = item.text;
          list.appendChild(li);
          var url = sanitizeUrl(item.source_url);
          var sourceKey = JSON.stringify([url, item.source_name, item.license_name, item.license_url]);
          if (url && typeof item.source_name === "string" && !seen[sourceKey]) {
            seen[sourceKey] = true;
            sources.push({ name:item.source_name, url:url, license:item.license_name,
              licenseUrl:sanitizeUrl(item.license_url) });
          }
        });
        block.appendChild(list);
      } else {
        var empty = doc.createElement("p");
        empty.className = "species-answer-empty";
        empty.textContent = section.empty_text || "출처가 확인된 자료가 없습니다.";
        block.appendChild(empty);
      }
      answer.appendChild(block);
      if (showBrief && (section.key === "basic" || section.title === "기본 정보")) { answer.appendChild(buildSpeciesBrief(doc, profile)); }
    });
    var answerConservation = conservationInfo(profile.conservation, profile.taxon);
    if (answerConservation.checklist) {
      var conservationData = profile.conservation;
      var conservationSourceKey = JSON.stringify([conservationData.source_url, conservationData.source_name,
        conservationData.license_name, conservationData.license_url]);
      var existingConservationSource = sources.find(function (source) {
        return source.url === conservationData.source_url && source.name === conservationData.source_name &&
          source.license === conservationData.license_name && source.licenseUrl === conservationData.license_url;
      });
      seen[conservationSourceKey] = true;
      if (existingConservationSource) { existingConservationSource.conservation = conservationData; }
      else {
        sources.push({ name: conservationData.source_name, url: conservationData.source_url,
          license: conservationData.license_name, licenseUrl: conservationData.license_url, conservation: conservationData });
      }
    }
    if (showBrief) {
      var briefSources = dietIconInfo(profile).sources.concat((profile.traits || []).filter(function (trait) { return trait.name === "habitat"; }));
      if (answerConservation.sourceVerified) { briefSources.push(profile.conservation); }
      briefSources.forEach(function (source) {
        var url = sanitizeUrl(source.source_url);
        var sourceKey = JSON.stringify([url, source.source_name, source.license_name, source.license_url]);
        if (url && typeof source.source_name === "string" && !seen[sourceKey]) {
          seen[sourceKey] = true; sources.push({ name: source.source_name, url: url, license: source.license_name, licenseUrl: sanitizeUrl(source.license_url) });
        }
      });
    }
    if (sources.length || answerConservation.manualOverride) {
      var details = doc.createElement("details");
      details.className = "species-answer-sources";
      var summary = doc.createElement("summary");
      summary.textContent = "답변 출처 보기 (" + (sources.length + (answerConservation.manualOverride ? 1 : 0)) + ")";
      details.appendChild(summary);
      if (answerConservation.manualOverride) {
        appendManualOverrideEvidence(doc, details, profile.conservation);
      }
      sources.forEach(function (source) {
        var row = doc.createElement("p");
        row.appendChild(safeLink(doc, source.name, source.url));
        if (source.license) {
          var license = doc.createElement("span");
          license.textContent = source.conservation ? " · " : " · 한국어 요약·재구성 · ";
          row.appendChild(license);
          row.appendChild(safeLink(doc, source.license, source.licenseUrl));
        }
        details.appendChild(row);
        if (source.conservation) {
          var conservationMeta = doc.createElement("p");
          conservationMeta.textContent = "릴리스 " + source.conservation.source_release + " · " +
            (source.conservation.assessment_year == null ? "평가 연도 확인되지 않음" :
              "개별 평가 연도 " + source.conservation.assessment_year) + " · 전 세계 평가 · 공개 평가목록 기준";
          details.appendChild(conservationMeta);
          details.appendChild(safeLink(doc, "공식 IUCN 개별 평가 페이지", source.conservation.assessment_reference_url));
          var conservationCaveat = doc.createElement("p");
          conservationCaveat.textContent = "종명·BirdLife SIS ID로 연결한 공개 목록입니다. 개별 평가 원문의 독립 검증 및 최신 평가 실시간 조회는 완료되지 않았습니다.";
          details.appendChild(conservationCaveat);
          ["자료 인용: " + source.conservation.citation, "개별 평가 인용: " + source.conservation.assessment_citation,
            "발행기관: " + source.conservation.publisher].forEach(function (text) {
            var citation = doc.createElement("p");
            citation.textContent = text;
            details.appendChild(citation);
          });
          if (typeof source.conservation.taxonomy_category_raw === "string" && /^CR\s*\(PEW?\)$/.test(source.conservation.taxonomy_category_raw)) {
            var taxonomyAnnotation = doc.createElement("p");
            taxonomyAnnotation.textContent = "AviList 분류 원본 등급: " + source.conservation.taxonomy_category_raw;
            details.appendChild(taxonomyAnnotation);
          }
        }
      });
      answer.appendChild(details);
    }
    return answer;
  }

  function buildSpeciesBrief(doc, profile) {
    var habitat = habitatEmblemInfo(profile);
    var conservation = conservationInfo(profile && profile.conservation, profile && profile.taxon);
    var brief = doc.createElement("p");
    brief.className = "species-chat-brief risk-" + conservation.tier;
    brief.appendChild(buildHabitatEmblem(doc, habitat));
    var habitatText = doc.createElement("span");
    habitatText.textContent = habitat.known ? "서식 환경: " + habitat.label : habitat.label;
    brief.appendChild(habitatText);
    var diet = dietIconInfo(profile);
    if (diet.icons.length) { brief.appendChild(buildDietIcons(doc, diet)); }
    var badge = doc.createElement("span");
    badge.className = "species-conservation-badge";
    badge.textContent = conservation.badgeText;
    badge.setAttribute("title", conservation.note || CONSERVATION_NOTE);
    brief.appendChild(badge);
    return brief;
  }

  function popupDialog(node) {
    var parent = node.parentNode;
    while (parent) {
      if (String(parent.tagName).toLowerCase() === "dialog") { return parent; }
      parent = parent.parentNode;
    }
    return null;
  }

  /** Native dialog supplies focus containment, Escape, and focus restoration. */
  function buildSpeciesPopup(doc, card, profile) {
    var wrapper = doc.createElement("div");
    wrapper.className = "species-popup-entry";
    var opener = doc.createElement("button");
    opener.type = "button";
    var tier = typeof card.getAttribute === "function" ? card.getAttribute("data-conservation-tier") : null;
    tier = tier || "unconfirmed";
    opener.className = "species-popup-trigger risk-" + tier;
    var name = speciesLabel(profile.taxon);
    opener.textContent = name + " · 도감 카드 보기 ↗";
    opener.setAttribute("aria-haspopup", "dialog");
    wrapper.appendChild(opener);

    var dialog = doc.createElement("dialog");
    dialog.className = "species-popup risk-" + tier;
    dialog.setAttribute("aria-label", name + " 도감 카드");
    var close = doc.createElement("button");
    close.type = "button";
    close.className = "species-popup-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "도감 카드 닫기");
    dialog.appendChild(close);
    var fitFrame = doc.createElement("div"); fitFrame.className = "species-card-fit-frame";
    var fitSurface = doc.createElement("div"); fitSurface.className = "species-card-fit-surface";
    fitSurface.appendChild(card); fitFrame.appendChild(fitSurface); dialog.appendChild(fitFrame);
    wrapper.appendChild(dialog);
    var view = doc.defaultView;
    var fitActive = false, fitRaf = null, fitObserver = null;
    function mobileFit() {
      return view && view.matchMedia && view.matchMedia("(max-width: 600px), (max-height: 600px) and (pointer: coarse)").matches;
    }
    function scrollToggleOpen() {
      var toggles = typeof card.querySelectorAll === "function" ? card.querySelectorAll(".card-details-scroll, .species-distribution-values") : [];
      for (var i = 0; i < toggles.length; i += 1) { if (toggles[i].open) { return true; } }
      return false;
    }
    function fitCard() {
      fitRaf = null;
      if (!fitActive || !dialog.open || dialog.isConnected === false) { return; }
      // Keep a user's pinch enlargement intact. Refit when zoom returns to 1.
      if (view.visualViewport && view.visualViewport.scale > 1.01) { return; }
      // Measure from the CSS viewport width, not the previously narrowed
      // chrome. Otherwise a height-fitted phone card would shrink on every
      // observer callback. The final width is applied only after measuring.
      if (dialog.style) { dialog.style.width = ""; }
      if (fitSurface.style) { fitSurface.style.width = ""; }
      var width = fitFrame.clientWidth, height = fitFrame.clientHeight;
      if (!(width > 0 && height > 0)) { return; }
      var mobile = mobileFit();
      var naturalWidth = fitSurface.offsetWidth;
      if (!(naturalWidth > 0)) { return; }
      var widthScale = Math.min(1, width / naturalWidth);
      var minimum = mobile ? Math.max(780, height / widthScale) : height;
      card.style.minHeight = minimum + "px";
      // offset sizes are untransformed; measuring the scaled rect would make
      // subsequent observer callbacks progressively shrink or oscillate.
      var naturalHeight = fitSurface.offsetHeight;
      if (!(naturalWidth > 0 && naturalHeight > 0)) { return; }
      // While "측정값 더 보기", "분류 계통 보기" or a chart's "항목·비율" is open, keep the card at a
      // readable size (fit the width only) and let the frame scroll vertically
      // instead of shrinking the whole card to the frame height.
      var scrolling = scrollToggleOpen();
      var scale = Math.min(1, width / naturalWidth);
      if (!scrolling) { scale = Math.min(scale, height / naturalHeight); }
      fitSurface.style.transform = "scale(" + scale + ")";
      // A scaled surface keeps its unscaled layout height; trim the difference
      // so the scroll range matches what is visible.
      fitSurface.style.marginBottom = scrolling && scale < 1 ? "-" + (naturalHeight * (1 - scale)) + "px" : "";
      fitFrame.setAttribute("data-fit-scroll", scrolling ? "true" : "false");
      if (!scrolling && fitFrame.scrollTop) { fitFrame.scrollTop = 0; }
      fitFrame.setAttribute("data-fit-scale", String(scale));
      // The silver frame follows the scaled card on every viewport so its thickness never depends on the scale.
      if (dialog.style && dialog.offsetWidth > 0) {
        var chrome = dialog.offsetWidth - width;
        dialog.style.width = (naturalWidth * scale + chrome) + "px";
        // Pin the measured width: a surface that follows its frame would be shrunk twice.
        if (fitSurface.style) { fitSurface.style.width = naturalWidth + "px"; }
      }
    }
    function scheduleFit() {
      if (!fitActive || fitRaf !== null) { return; }
      if (view && view.requestAnimationFrame) { fitRaf = view.requestAnimationFrame(fitCard); }
      else { fitCard(); }
    }
    function stopFit() {
      fitActive = false;
      if (fitRaf !== null && view && view.cancelAnimationFrame) { view.cancelAnimationFrame(fitRaf); }
      fitRaf = null;
      if (fitObserver) { fitObserver.disconnect(); fitObserver = null; }
      if (view && view.removeEventListener) { view.removeEventListener("resize", scheduleFit); }
      if (view && view.visualViewport && view.visualViewport.removeEventListener) { view.visualViewport.removeEventListener("resize", scheduleFit); }
      card.removeEventListener("load", scheduleFit, true); card.removeEventListener("toggle", scheduleFit, true);
    }
    function startFit() {
      stopFit();
      if (!dialog.open) { return; }
      card.resetFitScroll();
      fitActive = true;
      if (view && view.addEventListener) { view.addEventListener("resize", scheduleFit); }
      if (view && view.visualViewport && view.visualViewport.addEventListener) { view.visualViewport.addEventListener("resize", scheduleFit); }
      card.addEventListener("load", scheduleFit, true); card.addEventListener("toggle", scheduleFit, true);
      if (view && typeof view.ResizeObserver === "function") {
        fitObserver = new view.ResizeObserver(scheduleFit); fitObserver.observe(fitFrame); fitObserver.observe(card);
      }
      scheduleFit();
    }
    card.requestFit = scheduleFit;
    card.resetFitScroll = function () { if (fitFrame.scrollTop) { fitFrame.scrollTop = 0; } };
    fitFrame.addEventListener("scroll", function () { clearDistributionTooltips(card); });
    wrapper.disposePopup = function () { stopFit(); if (dialog.open && dialog.close) { dialog.close(); } };
    var backdropPress = null;
    function isBackdrop(event) {
      // The dialog's padded interior is still part of the card, not backdrop.
      if (event.target !== dialog) { return false; }
      var bounds = dialog.getBoundingClientRect();
      return event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom;
    }
    // A gesture starting inside the dialog can end with a dialog click outside
    // its bounds (including padding drags). Only a press AND release that
    // began on the backdrop can dismiss the popup; release coordinates alone
    // cannot distinguish that drag from an intentional outside click.
    dialog.addEventListener("pointerdown", function (event) {
      clearDistributionTooltips(card, event.target);
      backdropPress = null;
      if (event.button === 0 && event.isPrimary !== false && isBackdrop(event)) {
        backdropPress = { pointerId: event.pointerId, released: false };
      }
    }, true);
    dialog.addEventListener("pointerup", function (event) {
      if (!backdropPress || event.pointerId !== backdropPress.pointerId ||
          event.button !== 0 || !isBackdrop(event)) {
        backdropPress = null;
        return;
      }
      backdropPress.released = true;
    }, true);
    dialog.addEventListener("pointercancel", function () { backdropPress = null; }, true);
    opener.addEventListener("click", function () {
      backdropPress = null;
      if (card.showFront) { card.showFront(); }
      dialog.showModal();
      startFit();
    });
    close.addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("close", function () {
      stopFit();
      backdropPress = null;
      if (card.showFront) { card.showFront(); }
    });
    dialog.addEventListener("click", function (event) {
      var press = backdropPress;
      backdropPress = null;
      if (press && press.released &&
          (typeof event.pointerId !== "number" || event.pointerId === press.pointerId) &&
          isBackdrop(event)) {
        dialog.close();
      }
    });
    return wrapper;
  }

  function buildDeferredEnrichment(doc, profile, options) {
    var section = doc.createElement("section"); section.className = "species-enrichment";
    var active = options.isActive || function () { return true; };
    var cancelled = false;
    var started = false;
    var photoPending = true;
    var pendingStatuses = [];
    var loadButton = doc.createElement("button"); loadButton.type = "button";
    loadButton.className = "species-enrichment-load"; loadButton.textContent = "더 알아보기";
    section.appendChild(loadButton);
    function current() { return !cancelled && active(); }
    function status(text) {
      var node = doc.createElement("p"); node.setAttribute("role", "status");
      node.textContent = text; section.appendChild(node); pendingStatuses.push(node); return node;
    }
    function finish(node, text) {
      pendingStatuses = pendingStatuses.filter(function (item) { return item !== node; });
      node.textContent = text;
    }
    function matches(data, lineage) {
      return data && data.taxon && data.taxon.taxon_id === profile.taxon.taxon_id &&
        profile.lineage && profile.lineage.concept_set_id && profile.lineage.taxonomy_release && lineage &&
        lineage.concept_set_id === profile.lineage.concept_set_id && lineage.taxonomy_release === profile.lineage.taxonomy_release;
    }
    function startEnrichment() {
      if (started || !current()) { return; }
      started = true; loadButton.disabled = true;
      options.card.setEnrichmentMessage("사진을 불러오는 중입니다.");
      var profileStatus = status("사진·추가 설명을 불러오는 중입니다.");
      fetchTaxaJson(doc, options.fetcher, "/v1/taxa/profile", profile.taxon.scientific_name, 60000).then(function (fresh) {
        if (!current()) { return; }
        if (!matches(fresh, fresh && fresh.lineage)) { throw new Error("changed"); }
        options.card.updateEnrichment(fresh);
        photoPending = false;
        var initialSections = (Array.isArray(profile.sections) ? profile.sections : []).filter(function (initial) {
          return initial && Array.isArray(initial.items) && initial.items.some(function (item) {
            return item && typeof item.text === "string" && item.text.trim();
          });
        });
        var additionalSections = (Array.isArray(fresh.sections) ? fresh.sections : []).filter(function (candidate) {
          return candidate && !initialSections.some(function (initial) {
            return (candidate.key ? candidate.key === initial.key : candidate.title === initial.title) &&
              JSON.stringify(candidate.items || []) === JSON.stringify(initial.items || []);
          });
        });
        var explanation = buildSpeciesAnswer(doc, { taxon: fresh.taxon, sections: additionalSections });
        if (explanation) {
          var extraSources = Array.prototype.slice.call(explanation.children).find(function (child) { return child.className === "species-answer-sources"; });
          if (extraSources && options.onSources) { explanation.removeChild(extraSources); options.onSources(extraSources); }
          section.appendChild(explanation);
        }
        var initialWarnings = Array.isArray(profile.warnings) ? profile.warnings : [];
        var newWarnings = (Array.isArray(fresh.warnings) ? fresh.warnings : []).filter(function (warning) {
          return typeof warning === "string" && initialWarnings.indexOf(warning) === -1;
        });
        if (newWarnings.length) {
          var warnings = doc.createElement("ul"); warnings.className = "warnings";
          newWarnings.forEach(function (warning) { var item = doc.createElement("li"); item.textContent = "⚠ " + warning; warnings.appendChild(item); });
          section.appendChild(warnings);
        }
        Object.assign(profile, fresh, { enrichment_pending: false });
        finish(profileStatus, "사진·추가 설명 조회를 마쳤습니다.");
      }).catch(function (error) {
        if (!current()) { return; }
        photoPending = false;
        profile.enrichment_pending = false;
        profile.photo_availability = { status: "provider_unavailable" };
        options.card.setEnrichmentMessage("사진을 불러오지 못했습니다. 질문을 다시 보내 재시도하세요.", true);
        finish(profileStatus, error && error.message === "changed"
          ? "분류 자료가 바뀌어 사진·추가 설명을 표시하지 않았습니다. 질문을 다시 보내주세요."
          : "사진·추가 설명을 불러오지 못했습니다. 먼저 표시한 답변은 계속 확인할 수 있습니다.");
      });
      if (options.onSimilar) {
        var similarStatus = status("비슷한 새 추천을 불러오는 중입니다.");
        fetchTaxaJson(doc, options.fetcher, "/v1/taxa/similar", profile.taxon.scientific_name, 30000).then(function (data) {
          if (!current()) { return; }
          if (!matches(data, data)) { throw new Error("changed"); }
          options.onSimilar(data);
          finish(similarStatus, "비슷한 새 추천을 불러왔습니다.");
        }).catch(function (error) {
          if (!current()) { return; }
          finish(similarStatus, error && error.message === "changed"
            ? "분류 자료가 바뀌어 추천을 표시하지 않았습니다. 질문을 다시 보내주세요."
            : "비슷한 새 추천을 불러오지 못했습니다. 다른 자료는 계속 확인할 수 있습니다.");
        });
      }
    }
    loadButton.addEventListener("click", startEnrichment);
    section.cancelEnrichment = function (includeNotStarted) {
      if (!started && !includeNotStarted) { return false; }
      cancelled = true;
      loadButton.disabled = true;
      if (!started) { status("이전 답변의 추가 조회를 중단했습니다. 다시 확인하려면 질문을 보내주세요."); }
      if (photoPending) {
        profile.enrichment_pending = false;
        profile.photo_availability = { status: "cancelled" };
        options.card.setEnrichmentMessage("사진 조회를 중단했습니다. 질문을 다시 보내 확인하세요.", true);
      }
      pendingStatuses.forEach(function (node) { node.textContent = "추가 자료 조회를 중단했습니다. 다시 확인하려면 질문을 보내주세요."; });
      pendingStatuses = [];
      return true;
    };
    return section;
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
    // Bumped by 대화 지우기 so lazy lookups that settle after a clear never
    // write into (or announce status for) the discarded conversation.
    var conversationGeneration = 0;
    var enrichmentSections = [];

    function cancelEnrichments(includeNotStarted) {
      enrichmentSections = enrichmentSections.filter(function (section) { return !section.cancelEnrichment(includeNotStarted === true); });
    }
    appendComparisonMessage.beforeComparison = cancelEnrichments;

    function conversationGuard() {
      var generation = conversationGeneration;
      return function () { return generation === conversationGeneration; };
    }

    function taxaFetch(url, options) {
      return win.fetch(url, options);
    }

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
    // verbatim on clear. Only remove it while attached: the browser throws
    // NotFoundError if a later question tries to remove the same node again.
    function hideEmptyState() {
      if (historyEmptyState && historyEmptyState.parentNode === history) {
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

      var questionAnswer = answer.result && answer.result.kind === "profile" && answer.result.question_answer;
      var ranking = questionAnswer && questionAnswer.relations && questionAnswer.relations.ranking;
      var directRanked = questionAnswer && questionAnswer.topic === "related" && ranking && ranking.limit === 3 &&
        ["taxonomy-ecology-v1", "taxonomy-phylogeny-ecology-v2", "taxonomy-phylogeny-ecology-v3"].indexOf(ranking.method) !== -1;
      var rankedExplorer = directRanked ? buildRelatedExplorer(doc, answer.result.profile, taxaFetch, {
        initialData: questionAnswer.relations, inline: true, onComparison: appendComparisonMessage, isActive: conversationGuard(),
      }) : null;
      var targeted = buildQuestionAnswer(doc, questionAnswer, { rankedExplorer: rankedExplorer });
      var structured = targeted || (answer.result && answer.result.kind === "profile" ? buildSpeciesAnswer(doc, answer.result.profile, true) : null);
      var answerSources = null;
      if (structured) {
        answerSources = Array.from(structured.children).find(function (child) { return child.className === "species-answer-sources"; }) || null;
        if (answerSources) { structured.removeChild(answerSources); }
      }
      if (targeted && !directRanked) {
        var factSourceUrls = {};
        (Array.isArray(questionAnswer.items) ? questionAnswer.items : []).forEach(function (fact) {
          var url = fact && sanitizeUrl(fact.source_url);
          var sourceKey = fact && JSON.stringify([url, fact.source_name, fact.license_name, fact.license_url, fact.text, fact.locator]);
          if (!url || typeof fact.source_name !== "string" || factSourceUrls[sourceKey]) { return; }
          factSourceUrls[sourceKey] = true;
          if (!answerSources) {
            answerSources = doc.createElement("details"); answerSources.className = "species-answer-sources";
            answerSources.appendChild(doc.createElement("summary"));
          }
          var row = doc.createElement("p"); row.appendChild(safeLink(doc, fact.source_name, url));
          if (fact.license_name) { row.appendChild(safeLink(doc, " · " + fact.license_name, fact.license_url)); }
          var context = [fact.text, fact.locator].filter(function (value) { return typeof value === "string" && value.trim(); });
          if (context.length) { var factContext = doc.createElement("span"); factContext.textContent = " · " + context.join(" · "); row.appendChild(factContext); }
          answerSources.appendChild(row);
        });
      }
      if (answer.result && answer.result.kind === "profile") { answerSources = buildCombinedAnswerSources(doc, answerSources); }
      if (structured) {
        item.appendChild(structured);
      } else {
        var text = doc.createElement("p");
        text.textContent = answer.answer_text;
        item.appendChild(text);
      }
      if (answer.result && answer.result.kind === "name_relations") {
        var nameRelations = buildNameRelations(doc, answer.result.relationships, taxaFetch, conversationGuard(), appendComparisonMessage);
        if (nameRelations) {
          item.appendChild(nameRelations);
        } else {
          var malformed = doc.createElement("p");
          malformed.className = "species-answer-empty";
          malformed.textContent = "이름 관계 자료의 형식을 확인할 수 없어 표시하지 않았습니다.";
          item.appendChild(malformed);
        }
      }

      var result = answer && answer.result;
      if (result && result.kind === "taxonomy") { item.appendChild(buildTaxonomyAnswer(doc, result.lineage)); }
      var resultLines = result && result.kind === "taxonomy" ? [] : resultSummaryLines(result);
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
        var speciesCard = buildSpeciesCard(doc, result.profile, { fetcher: taxaFetch, isActive: conversationGuard() });
        if (speciesCard) {
          if (!targeted && !structured) { item.appendChild(buildSpeciesBrief(doc, result.profile)); }
          answerSources = combineCardSources(doc, speciesCard, answerSources);
          item.appendChild(buildSpeciesPopup(doc, speciesCard, result.profile));
          var extra = doc.createElement("details"); extra.className = "species-extra-info";
          var extraTitle = doc.createElement("summary"); extraTitle.textContent = "더 알아보기"; extra.appendChild(extraTitle);
          if (result.profile.taxon.rank !== "subspecies") {
            var relatedOptions = { onComparison: appendComparisonMessage, isActive: conversationGuard() };
            var ecologicalOptions = { onComparison: appendComparisonMessage, isActive: conversationGuard() };
            if (targeted && questionAnswer.relations) {
              var directOptions = questionAnswer.topic === "related" ? relatedOptions : questionAnswer.topic === "ecological_related" ? ecologicalOptions : null;
              if (directOptions) { directOptions.initialData = questionAnswer.relations; directOptions.initiallyOpen = true; }
            } else if (!targeted && result.similar_species) {
              relatedOptions.initialData = result.similar_species;
            }
            if (!targeted) { relatedOptions.endpoint = "/v1/taxa/similar"; }
            var relatedSlot = result.profile.enrichment_pending && !targeted ? doc.createElement("div") : null;
            if (relatedSlot) { relatedSlot.className = "species-related-slot"; extra.appendChild(relatedSlot); }
            else if (!directRanked) {
              var related = buildRelatedExplorer(doc, result.profile, taxaFetch, relatedOptions);
              if (targeted && questionAnswer.topic === "related") { item.appendChild(related); }
              else { extra.appendChild(related); }
            }
            var ecological = buildEcologicalExplorer(doc, result.profile, taxaFetch, ecologicalOptions);
            if (targeted && questionAnswer.topic === "ecological_related") { item.appendChild(ecological); }
            else { extra.appendChild(ecological); }
          }
          if (result.profile.taxon.rank !== "subspecies") {
            var subspeciesExplorer = buildSubspeciesExplorer(doc, result.profile, taxaFetch, conversationGuard(), result.subspecies);
            if (targeted && questionAnswer.topic === "subspecies") { item.appendChild(subspeciesExplorer); }
            else { extra.appendChild(subspeciesExplorer); }
          }
          else { extra.appendChild(buildParentSpeciesExplorer(doc, result.profile, taxaFetch, conversationGuard())); }
          extra.appendChild(buildNameRelationsExplorer(doc, result.profile, taxaFetch, conversationGuard()));
          item.appendChild(extra);
          if (result.profile.enrichment_pending) {
            var deferred = buildDeferredEnrichment(doc, result.profile, {
              fetcher: taxaFetch, isActive: conversationGuard(), card: speciesCard,
              onSources: function (material) { answerSources.addSourceMaterial(material); },
              onSimilar: relatedSlot ? function (data) {
                relatedSlot.appendChild(buildRelatedExplorer(doc, result.profile, taxaFetch, {
                  initialData: data, onComparison: appendComparisonMessage, isActive: conversationGuard(),
                }));
              } : null,
            });
            item.appendChild(deferred); enrichmentSections.push(deferred);
          }
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
        if (result && result.kind === "profile") {
          if (!answerSources) {
            answerSources = doc.createElement("details"); answerSources.className = "species-answer-sources";
            var sourceTitle = doc.createElement("summary"); answerSources.appendChild(sourceTitle);
          }
          var citationMaterial = doc.createElement("div"); citationMaterial.appendChild(citeList);
          answerSources.addSourceMaterial(citationMaterial);
        } else { item.appendChild(citeList); }
      }

      if (answerSources) {
        if (answerSources.refreshSources) { answerSources.refreshSources(); }
        item.appendChild(answerSources);
      }

      history.appendChild(item);
      messages.push({ role: "assistant", answer: answer });
      if (structured && typeof item.getBoundingClientRect === "function" && typeof history.getBoundingClientRect === "function") {
        history.scrollTop += item.getBoundingClientRect().top - history.getBoundingClientRect().top - 12;
      } else {
        scrollToLatest();
      }
    }

    /**
     * A same-genus/family comparison is its own assistant bubble appended to
     * the end of the conversation; the explanation it came from is left
     * untouched, so consecutive comparisons stack as separate turns.
     */
    function appendComparisonMessage(panel, info) {
      cancelEnrichments();
      hideEmptyState();
      var item = doc.createElement("div");
      item.className = "message message-answer message-comparison";
      var names = speciesLabel(info.left.taxon) + " · " + speciesLabel(info.right.taxon);
      item.setAttribute("role", "article");
      item.setAttribute("aria-label", names + " 비교");
      var label = doc.createElement("strong");
      label.textContent = "RobinGraph";
      item.appendChild(label);
      var badge = doc.createElement("span");
      badge.className = "badge disposition-answer";
      badge.textContent = "비교";
      item.appendChild(badge);
      var intro = doc.createElement("p");
      intro.className = "comparison-intro";
      intro.textContent = names + " 비교입니다. 출처가 확인된 형질만 표시합니다.";
      item.appendChild(intro);
      item.appendChild(panel);
      history.appendChild(item);
      messages.push({ role: "assistant", comparison: {
        left: info.left.taxon && info.left.taxon.taxon_id, right: info.right.taxon && info.right.taxon.taxon_id,
      } });
      if (typeof item.scrollIntoView === "function") {
        item.scrollIntoView({ block: "start" });
      } else {
        scrollToLatest();
      }
      return item;
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
      cancelEnrichments();
      setBusy(true);
      setStatus("답변을 불러오는 중입니다…");

      win
        .fetch("/v1/chat", {
          method: "POST",
          credentials: "omit",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(Object.assign(buildChatPayload(question, intent.value, selectedFilterValues()), { defer_discovery: true })),
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
      cancelEnrichments(true);
      conversationGeneration += 1;
      messages.length = 0;
      function disposePopups(node) {
        if (node.disposePopup) { node.disposePopup(); }
        Array.prototype.slice.call(node.children || []).forEach(disposePopups);
      }
      disposePopups(history);
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
    buildDeferredEnrichment: buildDeferredEnrichment,
    buildRelatedExplorer: buildRelatedExplorer,
    buildEcologicalExplorer: buildEcologicalExplorer,
    speciesLabel: speciesLabel,
    buildNameRelations: buildNameRelations,
    buildNameRelationsExplorer: buildNameRelationsExplorer,
    buildSubspeciesExplorer: buildSubspeciesExplorer,
    isNameRelationsPayload: isNameRelationsPayload,
    buildSpeciesComparison: buildSpeciesComparison,
    buildSpeciesPopup: buildSpeciesPopup,
    buildSpeciesBrief: buildSpeciesBrief,
    habitatEmblemInfo: habitatEmblemInfo,
    dietIconInfo: dietIconInfo,
    buildSpeciesAnswer: buildSpeciesAnswer,
    buildQuestionAnswer: buildQuestionAnswer,
    buildTaxonomyAnswer: buildTaxonomyAnswer,
    conservationInfo: conservationInfo,
    photoAvailabilityInfo: photoAvailabilityInfo,
    init: init,
  };
});
