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
    var details = doc.createElement("details");
    details.className = "species-diet-legend";
    var summary = doc.createElement("summary");
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
  /**
   * Two-species comparison: target names, sourced traits (only claims with a
   * safe source URL and named source), and a popup card for each species.
   * `options` is threaded into the nested related explorer so a follow-up
   * comparison opened from inside this panel also becomes its own bubble.
   */
  function buildSpeciesComparison(doc, left, right, options) {
    options = options || {};
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
      if (leftCard) { panel.appendChild(buildSpeciesPopup(doc, leftCard, left)); }
    }
    var card = buildSpeciesCard(doc, right, cardOptions);
    if (card) { panel.appendChild(buildSpeciesPopup(doc, card, right)); }
    panel.appendChild(buildRelatedExplorer(doc, right, options.fetcher, options.explorer));
    panel.appendChild(buildEcologicalExplorer(doc, right, options.fetcher, options.explorer));
    return panel;
  }

  function speciesLabel(taxon) {
    return taxon && ((taxon.korean_name_status !== "machine-translated" && taxon.korean_name) || taxon.english_name || taxon.scientific_name) || "새";
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
  function similarityLabel(peer) {
    var score = typeof peer.similarity_score === "number" && Number.isFinite(peer.similarity_score) && peer.similarity_score >= 0 && peer.similarity_score <= 100 ? peer.similarity_score : null;
    return (Number.isInteger(peer.similarity_rank) && peer.similarity_rank >= 1 && peer.similarity_rank <= 3 ? peer.similarity_rank + "위 · " : "") + speciesLabel(peer) + (score !== null ? (peer.score_basis === "taxonomy_ecology_fallback" ? " · 분류·생태 대체 점수(계통 자료 부족) " : " · 가중 점수 ") + score + "점" : "");
  }

  function buildComparisonPeer(doc, peer, ranked) {
    var row = doc.createElement("div"); row.className = "comparison-peer";
    var identity = doc.createElement("div"); identity.className = "comparison-peer-identity";
    var name = doc.createElement("strong"); name.textContent = speciesLabel(peer); identity.appendChild(name);
    var scientific = doc.createElement("i"); scientific.textContent = peer.scientific_name; identity.appendChild(scientific);
    row.appendChild(identity);
    if (ranked) {
      var score = doc.createElement("span"); score.className = "comparison-peer-score";
      score.textContent = peer.similarity_rank + "위 · " + (peer.score_basis === "taxonomy_ecology_fallback" ? "분류·생태 대체 점수(계통 자료 부족) " : "가중 점수 ") + peer.similarity_score + "점";
      score.setAttribute("aria-label", "비교 후보 " + score.textContent); row.appendChild(score);
    }
    var button = doc.createElement("button"); button.type = "button"; button.className = "comparison-peer-choose";
    button.textContent = "비교하기";
    button.setAttribute("aria-label", (ranked ? similarityLabel(peer) : speciesLabel(peer)) + " · 비교하기");
    row.appendChild(button);
    return { row: row, button: button };
  }

  function buildRelatedExplorer(doc, profile, fetcher, options) {
    options = options || {};
    var active = typeof options.isActive === "function" ? options.isActive : function () { return true; };
    var onComparison = typeof options.onComparison === "function" ? options.onComparison : null;
    var section = doc.createElement("section"); section.className = "species-related";
    section.setAttribute("aria-label", speciesLabel(profile.taxon) + " 관련 새 탐색");
    var open = doc.createElement("button"); open.type = "button";
    open.textContent = "같은 속·과의 새 살펴보기";
    if (options.initialData && options.initialData.ranking) { open.textContent = "근연 관계 우선 3종 살펴보기"; }
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
        if (!other || !other.taxon || other.taxon.taxon_id !== peer.taxon_id || !other.lineage || !matchesRelease(other.lineage)) { throw new Error("changed"); }
        if (!settle()) { return; }
        var panel = buildSpeciesComparison(doc, profile, other, {
          fetcher: fetcher, bothCards: !!onComparison,
          explorer: { onComparison: onComparison, isActive: active },
        });
        var relation = doc.createElement("p");
        relation.className = "species-comparison-relation";
        relation.textContent = "공유 분류군: " + (group.ancestor ? (group.ancestor.korean_name || group.ancestor.scientific_name) : "확인 불가") + " (" + (RANK_LABELS[group.rank] || group.rank) + ")";
        if (group.rank === "similarity") { relation.textContent = similarityLabel(peer); panel.appendChild(buildSimilarityEvidence(doc, peer)); var scoreNote = doc.createElement("p"); scoreNote.textContent = "계통·분류·생태의 가중 점수입니다. 계통 자료가 없으면 분류·생태만 100점으로 환산합니다. 진화 거리나 유전 유사도의 측정값은 아닙니다."; panel.appendChild(scoreNote); }
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
      var request = initialData ? Promise.resolve(initialData) : fetchJson("/v1/taxa/related", profile.taxon.scientific_name);
      initialData = null;
      request.then(function (data) {
        if (!data.taxon || data.taxon.taxon_id !== profile.taxon.taxon_id || !matchesRelease(data)) { throw new Error("changed"); }
        if (!active()) { return; }
        while (results.firstChild) { results.removeChild(results.firstChild); }
        var note = doc.createElement("p"); note.className = "species-note"; note.textContent = data.note; results.appendChild(note);
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
            var choice = buildComparisonPeer(doc, peer, ranked);
            choice.button.addEventListener("click", function () { selectPeer(peer, group, choice.button); });
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
        status.textContent = "분류 관계를 불러오지 못했습니다. 접었다 다시 펼쳐 재시도하거나, 카드를 다시 열어주세요.";
      });
    }
    open.addEventListener("click", toggle);
    if (options.initiallyOpen) { toggle(); }
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
          selection.appendChild(buildSpeciesPopup(doc, card, profile));
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
        content.appendChild(buildSpeciesPopup(doc, buildSpeciesCard(doc, other, { fetcher: fetcher, isActive: isActive }), other));
      }).catch(function () { pending = false; if (typeof isActive !== "function" || isActive()) { content.textContent = "상위 종 자료를 확인하지 못했습니다. 다시 눌러 재시도하세요."; } });
    });
    return section;
  }

  function buildSubspeciesExplorer(doc, profile, fetcher, isActive) {
    var active = typeof isActive === "function" ? isActive : function () { return true; };
    var section = doc.createElement("section");
    section.className = "species-subspecies";
    var button = doc.createElement("button");
    button.type = "button";
    button.textContent = "이 종의 아종 살펴보기";
    var content = doc.createElement("div");
    var status = doc.createElement("p");
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
    button.addEventListener("click", function () {
      if (loaded) { content.hidden = !content.hidden; return; }
      if (pending) { return; }
      pending = true;
      status.textContent = "아종 목록을 불러오는 중입니다.";
      fetchTaxaJson(doc, fetcher, "/v1/taxa/subspecies", profile.taxon.scientific_name, 30000).then(function (data) {
        pending = false;
        if (!active()) { return; }
        if (!matches(data) || !data.parent_species || !data.parent_species.taxon || data.parent_species.taxon.taxon_id !== profile.taxon.taxon_id || !Array.isArray(data.subspecies)) { throw new Error("changed"); }
        loaded = true;
        status.textContent = data.subspecies.length ? "그래프에 연결된 아종을 선택하세요." : "이 분류 기준에서 연결된 아종이 없습니다.";
        if (data.source_url) { content.appendChild(safeLink(doc, data.source_name || "분류 출처", data.source_url)); }
        if (data.has_more) { var notice = doc.createElement("p"); notice.textContent = "일부 아종만 표시합니다. 전체 목록은 분류 출처에서 확인하세요."; content.appendChild(notice); }
        var selected = doc.createElement("div");
        data.subspecies.forEach(function (taxon) {
          var choice = doc.createElement("button");
          choice.type = "button";
          choice.textContent = (profile.taxon.korean_name ? speciesLabel(profile.taxon) + "의 아종 · " : "") + nameRelationTaxonLabel(taxon) + " · 아종 자료 보기";
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
              selected.appendChild(buildSpeciesPopup(doc, card, other));
              status.textContent = "선택한 아종의 자료를 불러왔습니다.";
            }).catch(function () { if (active() && current === generation) { status.textContent = "아종 자료를 확인하지 못했습니다. 다시 선택하세요."; } });
          });
          content.appendChild(choice);
        });
        content.appendChild(selected);
      }).catch(function () { pending = false; if (active()) { status.textContent = "아종 목록을 확인하지 못했습니다. 다시 눌러 재시도하세요."; } });
    });
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
    var conservation = conservationInfo(profile.conservation);
    var card = doc.createElement("div");
    card.className = "species-card risk-" + conservation.tier;
    card.setAttribute("data-conservation-tier", conservation.tier);

    var title = doc.createElement("p");
    title.className = "species-title";
    title.textContent = speciesLabel(taxon);
    var heading = doc.createElement("div");
    heading.className = "species-card-heading";
    var category = doc.createElement("span");
    category.className = "species-category";
    category.textContent = taxon.rank === "subspecies" ? "아종" : "조류 도감";
    heading.appendChild(category);
    heading.appendChild(title);
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
    if (taxon.rank === "subspecies") {
      var metadata = profile.subspecies_metadata;
      var metadataSection = metadata && metadata.section;
      var metadataSource = metadata && sanitizeUrl(metadata.source_url);
      var description = doc.createElement("p");
      description.className = "species-subspecies-description";
      var descriptions = metadataSection && metadataSection.key === "subspecies_taxonomy" && Array.isArray(metadataSection.items) ? metadataSection.items.slice(1).filter(function (item) { return item && typeof item.text === "string" && item.text.trim() && sanitizeUrl(item.source_url) === metadataSource; }).map(function (item) { return item.text; }) : [];
      description.textContent = metadataSource && descriptions.length ? descriptions.join(" ") : "이 아종만의 외형·분포 차이는 검토된 자료에서 아직 확인하지 못했습니다.";
      front.appendChild(description);
      if (metadataSource) {
        var metadataDetails = doc.createElement("details");
        metadataDetails.className = "card-details species-subspecies-sources";
        var metadataSummary = doc.createElement("summary");
        metadataSummary.textContent = "분류·아종 설명 출처";
        metadataDetails.appendChild(metadataSummary);
        metadataDetails.appendChild(safeLink(doc, metadata.source_name || "분류 출처", metadataSource));
        if (typeof metadata.range_raw === "string" && metadata.range_raw.trim()) {
          var rawRange = doc.createElement("blockquote");
          rawRange.textContent = metadata.range_raw;
          metadataDetails.appendChild(rawRange);
        }
        back.appendChild(metadataDetails);
      }
    }

    // Photos live in their own slots so a provider retry can re-render them
    // without touching the facts, flip state, or the explanation.
    var photoArea = doc.createElement("div");
    photoArea.className = "species-photo-area";
    front.appendChild(photoArea);
    var photoSourcesSlot = doc.createElement("div");
    photoSourcesSlot.className = "species-photo-sources-slot";
    back.appendChild(photoSourcesSlot);
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
        renderPhotos(fresh.images, fresh.photo_availability);
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
      var photoSources = doc.createElement("details");
      photoSources.className = "species-photo-sources";
      var photoSummary = doc.createElement("summary");
      photoSummary.textContent = "사진 출처 · 라이선스";
      photoSources.appendChild(photoSummary);
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
    }
    renderPhotos(profile.images, profile.photo_availability);

    var dietInfo = dietIconInfo(profile);
    if (dietInfo.icons.length) { front.appendChild(buildDietIcons(doc, dietInfo)); }
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
    if (taxon.rank === "subspecies") { frontNote.textContent = "아종에 직접 연결된 자료 · 출처는 뒷면"; }
    front.appendChild(frontNote);

    var traitNote = doc.createElement("p");
    traitNote.className = "species-note";
    traitNote.textContent =
      "수치는 자료에 기록된 종 평균입니다. 자료마다 먹이 분류가 다를 수 있습니다. 접은 날개 길이는 날개를 펼친 폭(날개폭)과 다릅니다.";
    back.appendChild(traitNote);
    if (taxon.rank === "subspecies") { traitNote.textContent = "아종에 직접 연결된 형질입니다. 종 수준 참고 정보는 별도로 표시합니다."; }
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
        reference.appendChild(buildTraitGrid(doc, groupTraits([trait])));
      });
      back.appendChild(reference);
    }

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

    back.appendChild(buildDietLegend(doc, dietInfo));

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
        var commonName = lineageItem.korean_name || lineageItem.english_name ? speciesLabel(lineageItem) : null;
        var namePart = commonName ? commonName + " · " + lineageItem.scientific_name : lineageItem.scientific_name;
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
    var flipAnimation = null;
    var flipTarget = null;
    var flipGeneration = 0;
    function resetFlip() {
      flipGeneration += 1;
      if (flipAnimation) { flipAnimation.cancel(); flipAnimation = null; }
      if (flipTarget) { flipTarget.setAttribute("data-flipping", "false"); }
      flip.disabled = false;
    }
    card.showFront = function () { resetFlip(); showFace(false); };
    flip.addEventListener("click", function () {
      if (flip.disabled) { return; }
      var showBack = back.hidden;
      var view = doc.defaultView;
      var reducedMotion = view && view.matchMedia && view.matchMedia("(prefers-reduced-motion: reduce)").matches;
      var target = card.parentNode && card.parentNode.tagName.toLowerCase() === "dialog" ? card.parentNode : card;
      if (reducedMotion || typeof target.animate !== "function") { showFace(showBack); return; }
      flipTarget = target;
      flip.disabled = true;
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
      flipAnimation.onfinish = function () {
        if (generation !== flipGeneration) { return; }
        var outgoing = flipAnimation;
        showFace(showBack);
        flipAnimation = target.animate([
          { transform: pose(-90 * direction, 3 * direction, .94), filter: "brightness(1.2)" },
          { transform: pose(5 * direction, -.6 * direction, 1.01), filter: "brightness(1.03)", offset: .82 },
          { transform: pose(0, 0, 1), filter: "brightness(1)" }
        ], { duration: 390, easing: "cubic-bezier(.15,.65,.25,1)", fill: "both" });
        outgoing.cancel();
        flipAnimation.onfinish = function () {
          if (generation === flipGeneration) { resetFlip(); }
        };
      };
    });
    footer.appendChild(flip);
    card.appendChild(footer);
    return card;
  }

  /**
   * One-line chat summary shown next to the card button: habitat emblem,
   * habitat name, and the validated red-list badge. The prose explanation
   * itself is the server's `answer_text` (built from `profile.summary`).
   */
  function buildQuestionAnswer(doc, questionAnswer) {
    if (!questionAnswer || ["diet", "habitat", "activity", "appearance", "related", "ecological_related"].indexOf(questionAnswer.topic) === -1) { return null; }
    var section = doc.createElement("section"); section.className = "species-question-answer";
    var title = doc.createElement("h3"); title.textContent = typeof questionAnswer.title === "string" ? questionAnswer.title : "질문에 대한 답변"; section.appendChild(title);
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
      if (showBrief && (section.key === "basic" || section.title === "기본 정보")) { answer.appendChild(buildSpeciesBrief(doc, profile)); }
    });
    if (showBrief) {
      var briefSources = dietIconInfo(profile).sources.concat((profile.traits || []).filter(function (trait) { return trait.name === "habitat"; }));
      if (conservationInfo(profile.conservation).verified) { briefSources.push(profile.conservation); }
      briefSources.forEach(function (source) {
        var url = sanitizeUrl(source.source_url);
        if (url && typeof source.source_name === "string" && !seen[url]) {
          seen[url] = true; sources.push({ name: source.source_name, url: url, license: source.license_name, licenseUrl: sanitizeUrl(source.license_url) });
        }
      });
    }
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
    var diet = dietIconInfo(profile);
    if (diet.icons.length) { brief.appendChild(buildDietIcons(doc, diet)); }
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
    dialog.appendChild(card);
    wrapper.appendChild(dialog);
    opener.addEventListener("click", function () {
      if (card.showFront) { card.showFront(); }
      dialog.showModal();
    });
    close.addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("close", function () { if (card.showFront) { card.showFront(); } });
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
    // Bumped by 대화 지우기 so lazy lookups that settle after a clear never
    // write into (or announce status for) the discarded conversation.
    var conversationGeneration = 0;

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
      var targeted = buildQuestionAnswer(doc, questionAnswer);
      var structured = targeted || (answer.result && answer.result.kind === "profile" ? buildSpeciesAnswer(doc, answer.result.profile, true) : null);
      var answerSources = null;
      if (structured) {
        answerSources = Array.from(structured.children).find(function (child) { return child.className === "species-answer-sources"; }) || null;
        if (answerSources) { structured.removeChild(answerSources); }
      }
      if (targeted) {
        var factSourceUrls = {};
        (Array.isArray(questionAnswer.items) ? questionAnswer.items : []).forEach(function (fact) {
          var url = fact && sanitizeUrl(fact.source_url);
          if (!url || typeof fact.source_name !== "string" || factSourceUrls[url]) { return; }
          factSourceUrls[url] = true;
          if (!answerSources) {
            answerSources = doc.createElement("details"); answerSources.className = "species-answer-sources";
            answerSources.appendChild(doc.createElement("summary"));
          }
          var row = doc.createElement("p"); row.appendChild(safeLink(doc, fact.source_name, url));
          if (fact.license_name) { row.appendChild(safeLink(doc, " · " + fact.license_name, fact.license_url)); }
          answerSources.appendChild(row);
        });
      }
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
        var speciesCard = buildSpeciesCard(doc, result.profile, { fetcher: taxaFetch, isActive: conversationGuard() });
        if (speciesCard) {
          if (!targeted && !structured) { item.appendChild(buildSpeciesBrief(doc, result.profile)); }
          item.appendChild(buildSpeciesPopup(doc, speciesCard, result.profile));
          var extra = doc.createElement("details"); extra.className = "species-extra-info";
          var extraTitle = doc.createElement("summary"); extraTitle.textContent = "추가 정보"; extra.appendChild(extraTitle);
          if (result.profile.taxon.rank !== "subspecies") {
            var relatedOptions = { onComparison: appendComparisonMessage, isActive: conversationGuard() };
            var ecologicalOptions = { onComparison: appendComparisonMessage, isActive: conversationGuard() };
            if (targeted && questionAnswer.relations) {
              var directOptions = questionAnswer.topic === "related" ? relatedOptions : questionAnswer.topic === "ecological_related" ? ecologicalOptions : null;
              if (directOptions) { directOptions.initialData = questionAnswer.relations; directOptions.initiallyOpen = true; }
            } else if (!targeted && result.similar_species) {
              relatedOptions.initialData = result.similar_species;
            }
            item.appendChild(buildRelatedExplorer(doc, result.profile, taxaFetch, relatedOptions));
            var ecological = buildEcologicalExplorer(doc, result.profile, taxaFetch, ecologicalOptions);
            if (targeted && questionAnswer.topic === "ecological_related") { item.appendChild(ecological); }
            else { extra.appendChild(ecological); }
          }
          if (result.profile.taxon.rank !== "subspecies") { extra.appendChild(buildSubspeciesExplorer(doc, result.profile, taxaFetch, conversationGuard())); }
          else { extra.appendChild(buildParentSpeciesExplorer(doc, result.profile, taxaFetch, conversationGuard())); }
          extra.appendChild(buildNameRelationsExplorer(doc, result.profile, taxaFetch, conversationGuard()));
          item.appendChild(extra);
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
          answerSources.appendChild(citeList);
        } else { item.appendChild(citeList); }
      }

      if (answerSources) {
        var sourceCount = Array.from(answerSources.children).slice(1).reduce(function (count, row) { return count + (row.className === "citations" ? row.children.length : 1); }, 0);
        answerSources.children[0].textContent = "답변 출처 보기 (" + sourceCount + ")";
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
      conversationGeneration += 1;
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
    conservationInfo: conservationInfo,
    photoAvailabilityInfo: photoAvailabilityInfo,
    init: init,
  };
});
