/**
 * RobinGraph manual test UI. Talks only to same-origin `/health` and
 * `/v1/chat` and read-only species exploration endpoints. No innerHTML/insertAdjacentHTML/document.write is used
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
      if (sourceDetails.children.length > 1) { traitCard.appendChild(sourceDetails); }
      traitGrid.appendChild(traitCard);
    });
    return traitGrid;
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

  /**
   * Validate `profile.conservation`. Only an exact known category code with a
   * named source counts as verified; DD/NE keep their code in the badge but
   * use the neutral palette, and anything missing/unknown is "미확인". The
   * Korean label comes from the fixed table above so it can never disagree
   * with the code.
   */
  function conservationInfo(conservation) {
    var category = conservation && typeof conservation === "object" ? conservation.category : null;
    // The source dataset annotates some CR rows as "CR (PE)" / "CR (PEW)"
    // (possibly extinct / in the wild); the backend normalizes these, but
    // accept the exact raw forms here too rather than dropping to 미확인.
    if (category === "CR (PE)" || category === "CR (PEW)") {
      category = "CR";
    }
    var hasSource = !!(conservation && typeof conservation.source_name === "string" && conservation.source_name.trim());
    if (typeof category !== "string" || !Object.prototype.hasOwnProperty.call(CONSERVATION_CATEGORIES, category) || !hasSource) {
      return { category: null, label: "미확인", tier: "unconfirmed", verified: false,
        badgeText: "멸종위기 등급 미확인" };
    }
    var known = CONSERVATION_CATEGORIES[category];
    var rawCategory = typeof conservation.category_raw === "string" ? conservation.category_raw.trim().toUpperCase() : "";
    var qualifier = category === "CR" && rawCategory === "CR (PE)" ? " · 절멸 가능성" :
      category === "CR" && rawCategory === "CR (PEW)" ? " · 야생절멸 가능성" : "";
    return {
      category: category,
      label: known.label,
      tier: known.tier,
      verified: known.tier !== "unconfirmed",
      badgeText: "IUCN 적색목록 " + known.label + " (" + category + ")" + qualifier,
    };
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
  function buildSpeciesComparison(doc, left, right) {
    var panel = doc.createElement("section");
    panel.className = "species-comparison";
    var heading = doc.createElement("h3");
    heading.textContent = "두 새 비교";
    panel.appendChild(heading);
    var table = doc.createElement("table");
    var caption = doc.createElement("caption");
    caption.textContent = "먹이 · 서식 환경 · 생활 방식 · 체중";
    table.appendChild(caption);
    var head = doc.createElement("thead");
    var titles = doc.createElement("tr");
    ["특징", left.taxon.korean_name || left.taxon.scientific_name,
      right.taxon.korean_name || right.taxon.scientific_name].forEach(function (text) {
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
    table.appendChild(body); panel.appendChild(table);
    var note = doc.createElement("p"); note.className = "species-note";
    note.textContent = "자료별 범주와 측정 기준이 다를 수 있습니다. 자료가 없는 항목은 차이로 판단하지 않습니다.";
    panel.appendChild(note);
    var card = buildSpeciesCard(doc, right);
    if (card) { panel.appendChild(buildSpeciesPopup(doc, card, right)); }
    return panel;
  }

  function buildRelatedExplorer(doc, profile, fetcher) {
    var section = doc.createElement("section"); section.className = "species-related";
    var open = doc.createElement("button"); open.type = "button";
    open.textContent = "같은 속·과의 새 살펴보기";
    open.setAttribute("aria-expanded", "false"); section.appendChild(open);
    var content = doc.createElement("div"); content.hidden = true; section.appendChild(content);
    var status = doc.createElement("p"); status.setAttribute("role", "status"); content.appendChild(status);
    var results = doc.createElement("div"); content.appendChild(results);
    var comparison = doc.createElement("div"); content.appendChild(comparison);
    var loaded = false;
    var selecting = false;
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
    function selectPeer(peer, group) {
      if (selecting) { return; }
      selecting = true; content.setAttribute("aria-busy", "true");
      while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); }
      status.textContent = "비교할 새의 자료를 불러오는 중입니다.";
      return fetchJson("/v1/taxa/profile", peer.scientific_name).then(function (other) {
        if (!other.taxon || other.taxon.taxon_id !== peer.taxon_id || !other.lineage || !matchesRelease(other.lineage)) { throw new Error("changed"); }
        while (comparison.firstChild) { comparison.removeChild(comparison.firstChild); }
        var panel = buildSpeciesComparison(doc, profile, other);
        var relation = doc.createElement("p");
        relation.textContent = "공유 분류군: " + (group.ancestor.korean_name || group.ancestor.scientific_name) + " (" + (RANK_LABELS[group.rank] || group.rank) + ") · " + profile.lineage.taxonomy_release;
        panel.appendChild(relation);
        comparison.appendChild(panel);
        if (typeof panel.scrollIntoView === "function") { panel.scrollIntoView({block:"start"}); }
        status.textContent = "비교 자료를 불러왔습니다.";
      }).catch(function () {
        status.textContent = "비교 자료를 불러오지 못했습니다. 분류 자료가 갱신된 경우 카드를 다시 열어주세요.";
      }).finally(function () { selecting = false; content.setAttribute("aria-busy", "false"); });
    }
    open.addEventListener("click", function () {
      content.hidden = !content.hidden; open.setAttribute("aria-expanded", String(!content.hidden));
      if (content.hidden || loaded) { return; }
      loaded = true; status.textContent = "분류 관계를 조회하는 중입니다.";
      fetchJson("/v1/taxa/related", profile.taxon.scientific_name).then(function (data) {
        if (!data.taxon || data.taxon.taxon_id !== profile.taxon.taxon_id || !matchesRelease(data)) { throw new Error("changed"); }
        while (results.firstChild) { results.removeChild(results.firstChild); }
        var note = doc.createElement("p"); note.className = "species-note"; note.textContent = data.note; results.appendChild(note);
        var version = doc.createElement("p"); version.textContent = data.taxonomy_source + " · " + data.taxonomy_release; results.appendChild(version);
        (Array.isArray(data.groups) ? data.groups : []).forEach(function (group) {
          var block = doc.createElement("section");
          var title = doc.createElement("h3");
          title.textContent = group.label + (group.ancestor ? " · " + (group.ancestor.korean_name || group.ancestor.scientific_name) : ""); block.appendChild(title);
          var peers = Array.isArray(group.items) ? group.items : [];
          if (!peers.length) {
            var empty = doc.createElement("p"); empty.textContent = "현재 분류 자료에서 다른 종을 확인하지 못했습니다."; block.appendChild(empty);
          }
          peers.slice(0, 12).forEach(function (peer) {
            var button = doc.createElement("button"); button.type = "button";
            button.textContent = (peer.korean_name || peer.scientific_name) + " · 비교하기";
            button.addEventListener("click", function () { selectPeer(peer, group); }); block.appendChild(button);
          });
          if (group.has_more) { var more = doc.createElement("p"); more.textContent = "학명순으로 최대 12종을 표시합니다."; block.appendChild(more); }
          var source = doc.createElement("details");
          var summary = doc.createElement("summary"); summary.textContent = "분류 관계의 출처"; source.appendChild(summary);
          source.appendChild(safeLink(doc, group.source_name || data.taxonomy_source, group.source_url));
          var release = doc.createElement("p"); release.textContent = "분류 버전: " + data.taxonomy_release; source.appendChild(release);
          block.appendChild(source); results.appendChild(block);
        });
        status.textContent = "비교할 새를 선택하세요.";
      }).catch(function () {
        loaded = false; status.textContent = "분류 관계를 불러오지 못했습니다. 접었다 다시 펼쳐 재시도하거나, 카드를 다시 열어주세요.";
      });
    });
    return section;
  }

  function buildSpeciesCard(doc, profile) {
    if (!profile || typeof profile !== "object" || !profile.taxon) {
      return null;
    }
    var taxon = profile.taxon;
    var conservation = conservationInfo(profile.conservation);
    var card = doc.createElement("div");
    card.className = "species-card risk-" + conservation.tier;
    card.setAttribute("data-conservation-tier", conservation.tier);

    var title = doc.createElement("p");
    title.className = "species-title";
    title.textContent = taxon.korean_name || taxon.scientific_name || "알 수 없는 종";
    var heading = doc.createElement("div");
    heading.className = "species-card-heading";
    var category = doc.createElement("span");
    category.className = "species-category";
    category.textContent = "조류 도감";
    heading.appendChild(category);
    heading.appendChild(title);
    heading.appendChild(buildHabitatEmblem(doc, habitatEmblemInfo(profile)));
    card.appendChild(heading);

    if (taxon.korean_name && taxon.scientific_name) {
      var scientificName = doc.createElement("p");
      scientificName.className = "species-scientific-name";
      scientificName.textContent = taxon.scientific_name;
      card.appendChild(scientificName);
    }

    var conservationBadge = doc.createElement("p");
    conservationBadge.className = "species-conservation-badge";
    conservationBadge.textContent = conservation.badgeText;
    conservationBadge.setAttribute("title", CONSERVATION_NOTE);
    card.appendChild(conservationBadge);

    var front = doc.createElement("section");
    front.className = "species-card-front";
    front.setAttribute("aria-label", "주요 특징");
    var back = doc.createElement("section");
    back.className = "species-card-back";
    back.setAttribute("aria-label", "출처와 상세 정보");
    back.hidden = true;
    card.appendChild(front);
    card.appendChild(back);
    var backTitle = doc.createElement("h3");
    backTitle.textContent = "출처 · 상세 정보";
    back.appendChild(backTitle);
    var photoSources = doc.createElement("details");
    photoSources.className = "species-photo-sources";
    var photoSummary = doc.createElement("summary");
    photoSummary.textContent = "사진 출처 · 라이선스";
    photoSources.appendChild(photoSummary);
    var photoFigures = [];

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
      var noPhoto = doc.createElement("p");
      noPhoto.className = "species-note";
      noPhoto.textContent = "라이선스가 확인된 대표 사진이 없습니다.";
      front.appendChild(noPhoto);
    } else {
      front.appendChild(media);
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
        function showPhoto(index) {
          photoIndex = index;
          photoFigures.forEach(function (item, i) { item.hidden = i !== index; });
          previous.disabled = index === 0;
          next.disabled = index === photoFigures.length - 1;
          count.textContent = "사진 " + (index + 1) + " / " + photoFigures.length;
        }
        previous.addEventListener("click", function () { showPhoto(Math.max(0, photoIndex - 1)); });
        next.addEventListener("click", function () { showPhoto(Math.min(photoFigures.length - 1, photoIndex + 1)); });
        photoControls.appendChild(previous);
        photoControls.appendChild(count);
        photoControls.appendChild(next);
        showPhoto(0);
        front.appendChild(photoControls);
      }
      back.appendChild(photoSources);
    }

    var traitGroups = groupTraits(Array.isArray(profile.traits) ? profile.traits : []);
    var facts = doc.createElement("dl");
    facts.className = "species-quick-facts";
    ["body_mass", "diet_category", "habitat", "primary_lifestyle"].forEach(function (name) {
      var group = traitGroups.find(function (item) { return item.trait.name === name; });
      if (!group) { return; }
      var trait = group.trait;
      var label = doc.createElement("dt");
      label.textContent = trait.label || trait.name;
      var value = doc.createElement("dd");
      var unit = trait.unit && trait.unit !== "percent" ? " " + trait.unit : "";
      value.textContent = (trait.display != null ? trait.display : "") + unit + (trait.inferred ? " (추정값)" : "");
      facts.appendChild(label);
      facts.appendChild(value);
    });
    front.appendChild(facts);
    var frontNote = doc.createElement("p");
    frontNote.className = "species-front-note";
    frontNote.textContent = "수치는 종 평균 · 사진과 자료 출처는 뒷면";
    front.appendChild(frontNote);
    front.appendChild(buildRelatedExplorer(doc, profile));

    var traitNote = doc.createElement("p");
    traitNote.className = "species-note";
    traitNote.textContent =
      "수치는 자료에 기록된 종 평균입니다. 자료마다 먹이 분류가 다를 수 있습니다. 접은 날개 길이는 날개를 펼친 폭(날개폭)과 다릅니다.";
    back.appendChild(traitNote);

    if (traitGroups.length === 0) {
      var noTraits = doc.createElement("p");
      noTraits.className = "species-note";
      noTraits.textContent = "조회된 형질(특징·먹이·서식 환경) 정보가 없습니다.";
      front.appendChild(noTraits);
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
        back.appendChild(buildTraitGrid(doc, prominentGroups));
      }
      if (remainingGroups.length > 0) {
        var measurementsDetails = doc.createElement("details");
        measurementsDetails.className = "card-details";
        var measurementsSummary = doc.createElement("summary");
        measurementsSummary.textContent = "측정값 더 보기 (" + remainingGroups.length + ")";
        measurementsDetails.appendChild(measurementsSummary);
        measurementsDetails.appendChild(buildTraitGrid(doc, remainingGroups));
        back.appendChild(measurementsDetails);
      }
    }

    if (typeof profile.vegetation_note === "string" && profile.vegetation_note.trim()) {
      var vegetationNote = doc.createElement("p");
      vegetationNote.className = "vegetation-note";
      vegetationNote.textContent = profile.vegetation_note;
      back.appendChild(vegetationNote);
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

    var conservationSection = doc.createElement("details");
    conservationSection.className = "species-conservation-sources";
    var conservationSummary = doc.createElement("summary");
    conservationSummary.textContent = "멸종위기 등급 출처";
    conservationSection.appendChild(conservationSummary);
    var conservationStatus = doc.createElement("p");
    conservationStatus.textContent = conservation.badgeText;
    conservationSection.appendChild(conservationStatus);
    var rawConservation = profile.conservation && typeof profile.conservation === "object" ? profile.conservation : null;
    if (conservation.category && rawConservation) {
      var conservationSource = doc.createElement("span");
      conservationSource.className = "trait-source";
      var sourcePrefix = doc.createElement("span");
      sourcePrefix.textContent = "기준 자료: ";
      conservationSource.appendChild(sourcePrefix);
      conservationSource.appendChild(safeLink(doc, rawConservation.source_name, rawConservation.source_url));
      var releaseSuffix = doc.createElement("span");
      releaseSuffix.textContent = typeof rawConservation.source_release === "string" && rawConservation.source_release.trim()
        ? " · 릴리스 " + rawConservation.source_release.trim() + " 기준"
        : " · 릴리스 정보 없음";
      conservationSource.appendChild(releaseSuffix);
      conservationSection.appendChild(conservationSource);
      var rawCategory = typeof rawConservation.category_raw === "string" ? rawConservation.category_raw.trim().toUpperCase() : "";
      if (rawCategory === "CR (PE)" || rawCategory === "CR (PEW)") {
        var annotation = doc.createElement("p");
        annotation.className = "species-note";
        annotation.textContent = "원본 등급: " + rawCategory + (rawCategory === "CR (PE)" ? " · 절멸 가능성이 있는 위급종" : " · 야생절멸 가능성이 있는 위급종");
        conservationSection.appendChild(annotation);
      }
    } else {
      var noConservation = doc.createElement("p");
      noConservation.textContent = "검증된 멸종위기 등급 자료가 없어 카드 색상을 중립으로 표시합니다.";
      conservationSection.appendChild(noConservation);
    }
    var conservationNote = doc.createElement("p");
    conservationNote.className = "species-note";
    conservationNote.textContent = CONSERVATION_NOTE;
    conservationSection.appendChild(conservationNote);
    back.appendChild(conservationSection);

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
      back.appendChild(lineageDetails);
    }

    var footer = doc.createElement("div");
    footer.className = "species-card-footer";
    var flip = doc.createElement("button");
    flip.type = "button";
    flip.className = "species-card-flip";
    flip.textContent = "출처 보기 ↻";
    flip.setAttribute("aria-pressed", "false");
    function showFace(showBack) {
      back.hidden = !showBack;
      front.hidden = showBack;
      flip.textContent = showBack ? "앞면 보기 ↻" : "출처 보기 ↻";
      flip.setAttribute("aria-pressed", String(showBack));
      if (card.parentNode) { card.parentNode.scrollTop = 0; }
    }
    card.showFront = function () { showFace(false); };
    flip.addEventListener("click", function () { showFace(back.hidden); });
    footer.appendChild(flip);
    card.appendChild(footer);
    return card;
  }

  /**
   * One-line chat summary shown next to the card button: habitat emblem,
   * habitat name, and the validated red-list badge. The prose explanation
   * itself is the server's `answer_text` (built from `profile.summary`).
   */
  function buildSpeciesAnswer(doc, profile) {
    if (!profile || !Array.isArray(profile.sections) || !profile.sections.length) { return null; }
    var answer = doc.createElement("div");
    answer.className = "species-answer";
    var heading = doc.createElement("h3");
    heading.textContent = profile.taxon && (profile.taxon.korean_name || profile.taxon.scientific_name) || "조류 정보";
    answer.appendChild(heading);
    var sources = [];
    var seen = {};
    profile.sections.slice(0, 4).forEach(function (section) {
      if (!section || typeof section.title !== "string") { return; }
      var block = doc.createElement("section");
      block.className = "species-answer-section";
      var title = doc.createElement("h4");
      title.textContent = section.title;
      block.appendChild(title);
      var items = Array.isArray(section.items) ? section.items.filter(function (item) {
        return item && typeof item.text === "string" && item.text.trim();
      }).slice(0, 4) : [];
      if (items.length) {
        var list = doc.createElement("ul");
        items.forEach(function (item) {
          var li = doc.createElement("li");
          li.textContent = item.text;
          list.appendChild(li);
          var url = sanitizeUrl(item.source_url);
          if (url && typeof item.source_name === "string" && !seen[url]) {
            seen[url] = true;
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
    });
    if (sources.length) {
      var details = doc.createElement("details");
      details.className = "species-answer-sources";
      var summary = doc.createElement("summary");
      summary.textContent = "답변 출처 보기 (" + sources.length + ")";
      details.appendChild(summary);
      sources.forEach(function (source) {
        var row = doc.createElement("p");
        row.appendChild(safeLink(doc, source.name, source.url));
        if (source.license) {
          var license = doc.createElement("span");
          license.textContent = " · 한국어 요약·재구성 · ";
          row.appendChild(license);
          row.appendChild(safeLink(doc, source.license, source.licenseUrl));
        }
        details.appendChild(row);
      });
      answer.appendChild(details);
    }
    return answer;
  }

  function buildSpeciesBrief(doc, profile) {
    var habitat = habitatEmblemInfo(profile);
    var conservation = conservationInfo(profile && profile.conservation);
    var brief = doc.createElement("p");
    brief.className = "species-chat-brief risk-" + conservation.tier;
    brief.appendChild(buildHabitatEmblem(doc, habitat));
    var habitatText = doc.createElement("span");
    habitatText.textContent = habitat.known ? "서식 환경: " + habitat.label : habitat.label;
    brief.appendChild(habitatText);
    var badge = doc.createElement("span");
    badge.className = "species-conservation-badge";
    badge.textContent = conservation.badgeText;
    badge.setAttribute("title", CONSERVATION_NOTE);
    brief.appendChild(badge);
    return brief;
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
    var name = profile.taxon.korean_name || profile.taxon.scientific_name || "새";
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
    dialog.appendChild(card);
    wrapper.appendChild(dialog);
    opener.addEventListener("click", function () {
      if (card.showFront) { card.showFront(); }
      dialog.showModal();
    });
    close.addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("click", function (event) {
      // The dialog's padded interior is still part of the card, not backdrop.
      if (event.target !== dialog) { return; }
      var bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom) {
        dialog.close();
      }
    });
    return wrapper;
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

      var structured = answer.result && answer.result.kind === "profile" ? buildSpeciesAnswer(doc, answer.result.profile) : null;
      if (structured) {
        item.appendChild(structured);
      } else {
        var text = doc.createElement("p");
        text.textContent = answer.answer_text;
        item.appendChild(text);
      }

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
          item.appendChild(buildSpeciesBrief(doc, result.profile));
          item.appendChild(buildSpeciesPopup(doc, speciesCard, result.profile));
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
      if (structured && typeof item.getBoundingClientRect === "function" && typeof history.getBoundingClientRect === "function") {
        history.scrollTop += item.getBoundingClientRect().top - history.getBoundingClientRect().top - 12;
      } else {
        scrollToLatest();
      }
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
    buildRelatedExplorer: buildRelatedExplorer,
    buildSpeciesComparison: buildSpeciesComparison,
    buildSpeciesPopup: buildSpeciesPopup,
    buildSpeciesBrief: buildSpeciesBrief,
    habitatEmblemInfo: habitatEmblemInfo,
    buildSpeciesAnswer: buildSpeciesAnswer,
    conservationInfo: conservationInfo,
    init: init,
  };
});
