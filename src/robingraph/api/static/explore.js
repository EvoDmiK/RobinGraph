/* Bird Explorer UI: structured condition search over GET /v1/taxa/explore.
 * All external strings are rendered strictly via textContent; links use safe http(s) validation. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root && typeof root === "object") {
    root.RobinGraphExplore = api;
  }
  if (typeof document !== "undefined" && document.getElementById && document.getElementById("explore-form")) {
    api.init(document, typeof window !== "undefined" ? window : null);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var SPECIES_SCOPES = ["all", "korea", "outside", "unknown"];
  var SCOPE_LABELS = {
    all: "전체 (한국어 우선)",
    korea: "국내 기록·분포 확인",
    outside: "국외 분포 검토 (영어 우선)",
    unknown: "한국 분포 미확인",
  };
  var SPECIES_SCOPE_NOTES = {
    all: "전체 분류군을 표시하며 검증된 한국어 이름을 먼저 보여줍니다. 국내 기록·분포 확인은 출처의 야생 기록·분포 유무이며 모두 텃새라는 뜻이 아닙니다.",
    korea: "대한민국을 기준으로 출처의 Korea·Korean Peninsula 표기도 포함하며, 북한만 명시한 근거는 제외합니다. 한국어 이름을 우선하며 계절·미조 기록을 포함하므로 텃새·현재 서식을 뜻하지 않습니다.",
    outside: "현재 일부 종의 정상 분포만 검토했으며 미확인 종은 포함하지 않습니다. 영어 이름을 우선하고 없으면 검증 국명·학명을 표시합니다. 우연한 도래나 사육 기록의 부재를 뜻하지 않습니다.",
    unknown: "한국 분포 근거를 아직 확인하지 못한 종을 표시하며 한국어 이름을 우선합니다. 국외 분포로 판정된 것이 아닙니다.",
  };

  var HABITATS = [
    "Forest",
    "Shrubland",
    "Woodland",
    "Grassland",
    "Rock",
    "Wetland",
    "Human Modified",
    "Coastal",
    "Marine",
    "Riverine",
    "Desert",
  ];
  var HABITAT_LABELS = {
    Forest: "숲 (Forest)",
    Shrubland: "관목 지대 (Shrubland)",
    Woodland: "성긴 숲 (Woodland)",
    Grassland: "초지 (Grassland)",
    Rock: "바위 지대 (Rock)",
    Wetland: "습지 (Wetland)",
    "Human Modified": "인공·변형 환경 (Human Modified)",
    Coastal: "해안 (Coastal)",
    Marine: "바다 (Marine)",
    Riverine: "하천 (Riverine)",
    Desert: "사막 (Desert)",
  };

  var DIETS = [
    "invertebrate",
    "endotherm_vertebrate",
    "ectotherm_vertebrate",
    "fish",
    "unknown_vertebrate",
    "carrion",
    "fruit",
    "nectar",
    "seed",
    "other_plant",
  ];
  var DIET_LABELS = {
    invertebrate: "곤충",
    endotherm_vertebrate: "고기 · 온혈동물",
    ectotherm_vertebrate: "고기 · 변온동물",
    fish: "물고기",
    unknown_vertebrate: "기타 고기",
    carrion: "사체",
    fruit: "열매",
    nectar: "꽃꿀",
    seed: "씨앗",
    other_plant: "기타 식물",
  };

  function normalizeSpeciesScope(value) {
    return typeof value === "string" && SPECIES_SCOPES.indexOf(value) !== -1 ? value : "all";
  }

  function sanitizeUrl(value) {
    if (typeof value !== "string") { return null; }
    var trimmed = value.trim();
    if (!/^https?:\/\//i.test(trimmed)) { return null; }
    try {
      var parsed = new URL(trimmed);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") { return null; }
      if (parsed.username || parsed.password) { return null; }
      return parsed.href;
    } catch (_) {
      return null;
    }
  }

  function createEl(doc, tag, text, className) {
    var node = doc.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function safeLink(doc, label, rawUrl, className) {
    var safeHref = sanitizeUrl(rawUrl);
    var text = typeof label === "string" && label.trim() ? label.trim() : (safeHref || "출처");
    if (!safeHref) {
      return createEl(doc, "span", text, className);
    }
    var a = createEl(doc, "a", text, className);
    a.href = safeHref;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  function speciesLabel(taxon, scope) {
    if (!taxon || typeof taxon !== "object") { return "새"; }
    var verifiedKorean = taxon.korean_name_status !== "machine-translated"
      && typeof taxon.korean_name === "string" && taxon.korean_name.trim()
      ? taxon.korean_name.trim()
      : "";
    var english = typeof taxon.english_name === "string" && taxon.english_name.trim()
      ? taxon.english_name.trim()
      : "";
    var scientific = typeof taxon.scientific_name === "string" && taxon.scientific_name.trim()
      ? taxon.scientific_name.trim()
      : "";
    var display = typeof taxon.display_name === "string" && taxon.display_name.trim()
      && (taxon.korean_name_status !== "machine-translated" || taxon.display_name.trim() !== taxon.korean_name)
      ? taxon.display_name.trim()
      : "";
    if (display) { return display; }
    if (normalizeSpeciesScope(scope) === "outside") {
      return english || verifiedKorean || scientific || "새";
    }
    return verifiedKorean || english || scientific || "새";
  }

  function normalizeDietList(rawDiets) {
    var list = Array.isArray(rawDiets)
      ? rawDiets
      : (typeof rawDiets === "string" && rawDiets.trim() ? rawDiets.split(",") : []);
    var seen = new Set();
    list.forEach(function (item) {
      if (typeof item === "string") {
        var key = item.trim();
        if (DIETS.indexOf(key) !== -1) {
          seen.add(key);
        }
      }
    });
    return DIETS.filter(function (key) { return seen.has(key); });
  }

  function buildExploreParams(state) {
    state = state || {};
    var params = new URLSearchParams();
    var scope = normalizeSpeciesScope(state.species_scope);
    params.set("species_scope", scope);

    var taxon = typeof state.taxon === "string" ? state.taxon.trim().slice(0, 100) : "";
    if (taxon) {
      params.set("taxon", taxon);
    }

    var habitat = typeof state.habitat === "string" && HABITATS.indexOf(state.habitat) !== -1
      ? state.habitat
      : "";
    if (habitat) {
      params.set("habitat", habitat);
    }

    var diets = normalizeDietList(state.diet);
    if (diets.length > 0) {
      params.set("diet", diets.join(","));
    }
    var page = Number(state.page);
    if (Number.isInteger(page) && page > 1 && page <= 10000) { params.set("page", String(page)); }
    return params;
  }

  function parseExploreSearch(searchString) {
    var raw = typeof searchString === "string" ? searchString.replace(/^\?/, "") : "";
    var params = new URLSearchParams(raw);
    var scopeRaw = params.get("species_scope");
    var taxonRaw = params.get("taxon");
    var habitatRaw = params.get("habitat");
    var dietRaw = params.get("diet");
    return {
      hasQuery: raw.trim().length > 0,
      rawQuery: raw.trim(),
      page: Number(params.get("page") || 1),
      species_scope: normalizeSpeciesScope(scopeRaw),
      taxon: typeof taxonRaw === "string" ? taxonRaw.trim().slice(0, 100) : "",
      habitat: typeof habitatRaw === "string" && HABITATS.indexOf(habitatRaw) !== -1 ? habitatRaw : "",
      diet: normalizeDietList(dietRaw),
    };
  }

  function formatValidationError(body) {
    var details = body && Array.isArray(body.detail) ? body.detail : [];
    var messages = [];
    var seen = new Set();
    function addMsg(msg) {
      if (msg && !seen.has(msg)) {
        seen.add(msg);
        messages.push(msg);
      }
    }
    details.forEach(function (err) {
      if (!err || typeof err !== "object") { return; }
      var type = typeof err.type === "string" ? err.type : "";
      var loc = Array.isArray(err.loc) ? err.loc.join(".") : "";
      if (type === "taxon_not_found") {
        addMsg("입력한 분류군을 활성 분류 체계에서 찾지 못했습니다. 목·과·속 단위의 국명(예: 참새목, 직박구리과) 또는 학명(예: Passeriformes)을 확인해 주세요.");
      } else if (type === "taxon_ambiguous") {
        addMsg("입력한 이름에 해당하는 분류군이 둘 이상입니다. 정확한 학명(예: Passeriformes)으로 입력해 주세요.");
      } else if (type === "taxon_rank_conflict") {
        addMsg("입력한 한국어 분류군 이름의 계급(목·과·속)이 활성 분류 자료의 실제 계급과 일치하지 않습니다.");
      } else if (type === "taxon_rank_unsupported" || type === "rank_unsupported") {
        addMsg("분류군 입력란에는 목·과·속 단위만 입력할 수 있습니다. 특정 종이나 아종은 새 도감(/birds)에서 직접 조회해 주세요.");
      } else if (loc.indexOf("taxon") !== -1) {
        addMsg("분류군 입력 형식이 올바르지 않습니다. 목·과·속 학명 한 단어(예: Passeriformes) 또는 한글 분류군 이름(예: 참새목)을 입력해 주세요.");
      } else if (type === "duplicate_parameter" || type === "extra_forbidden") {
        addMsg("허용되지 않거나 중복된 조회 파라미터가 포함되었습니다. 서식 환경은 1개만 선택할 수 있습니다.");
      } else {
        addMsg("조회 조건 형식이 올바르지 않습니다. 선택한 분포 범위·서식 환경·먹이 조건을 다시 확인해 주세요.");
      }
    });
    if (!messages.length) {
      return "조회 조건 형식이 올바르지 않습니다. 입력한 분류군과 선택 조건을 다시 확인해 주세요.";
    }
    return messages.join(" ");
  }

  function buildBirdsProfileHref(scientificName, scope) {
    var sci = typeof scientificName === "string" ? scientificName.trim() : "";
    var normalizedScope = normalizeSpeciesScope(scope);
    var params = new URLSearchParams();
    if (sci) { params.set("name", sci); }
    params.set("species_scope", normalizedScope);
    return "/birds?" + params.toString();
  }

  function renderStateBox(doc, container, stateKind, titleText, primaryText, secondaryText) {
    container.replaceChildren();
    container.hidden = false;
    container.setAttribute("data-result-state", stateKind);
    var box = createEl(doc, "div", null, "explore-state-box");
    box.setAttribute("data-state", stateKind);
    box.appendChild(createEl(doc, "h3", titleText));
    if (primaryText) {
      box.appendChild(createEl(doc, "p", primaryText));
    }
    if (secondaryText) {
      box.appendChild(createEl(doc, "p", secondaryText));
    }
    container.appendChild(box);
  }

  function renderExploreResult(doc, container, payload, requestedScope, options) {
    if (!payload || typeof payload !== "object") { return; }
    container.replaceChildren();
    container.hidden = false;

    var status = typeof payload.status === "string" ? payload.status : "answer";
    container.setAttribute("data-result-state", status);

    var queryEcho = payload.query && typeof payload.query === "object" ? payload.query : {};
    var activeScope = normalizeSpeciesScope(queryEcho.species_scope || requestedScope);
    var activeDiets = normalizeDietList(queryEcho.diet);

    // 1. Header & Applied Conditions
    var header = createEl(doc, "div", null, "explore-results-header");
    var titleText = typeof payload.title === "string" && payload.title.trim()
      ? payload.title.trim()
      : "조건으로 새 찾기 결과";
    header.appendChild(createEl(doc, "h2", titleText));

    var condBox = createEl(doc, "div", null, "graph-query-conditions");
    condBox.setAttribute("role", "group");
    condBox.setAttribute("aria-label", "적용된 검색 조건");
    var condList = createEl(doc, "ul", null, "graph-query-condition-list");

    var scopeChipText = "분포 범위: " + (SCOPE_LABELS[activeScope] || SCOPE_LABELS.all);
    condList.appendChild(createEl(doc, "li", scopeChipText, "graph-query-condition-chip"));

    if (payload.taxon && typeof payload.taxon === "object") {
      var taxonName = speciesLabel(payload.taxon, activeScope);
      var taxonSci = typeof payload.taxon.scientific_name === "string" ? payload.taxon.scientific_name.trim() : "";
      var taxonDisplay = taxonName && taxonSci && taxonName !== taxonSci
        ? taxonName + " (" + taxonSci + ")"
        : (taxonName || taxonSci);
      if (taxonDisplay) {
        condList.appendChild(createEl(doc, "li", "분류군: " + taxonDisplay, "graph-query-condition-chip"));
      }
    } else if (typeof queryEcho.taxon === "string" && queryEcho.taxon.trim()) {
      condList.appendChild(createEl(doc, "li", "분류군: " + queryEcho.taxon.trim(), "graph-query-condition-chip"));
    }

    if (Array.isArray(payload.conditions) && payload.conditions.length > 0) {
      payload.conditions.forEach(function (cond) {
        var label = cond && typeof cond === "object" && typeof cond.label === "string" ? cond.label.trim() : "";
        if (label) {
          condList.appendChild(createEl(doc, "li", label, "graph-query-condition-chip"));
        }
      });
    } else {
      if (typeof queryEcho.habitat === "string" && HABITAT_LABELS[queryEcho.habitat]) {
        condList.appendChild(createEl(doc, "li", "서식 환경: " + HABITAT_LABELS[queryEcho.habitat], "graph-query-condition-chip"));
      }
      activeDiets.forEach(function (dietKey) {
        condList.appendChild(createEl(doc, "li", "먹이 구성: " + (DIET_LABELS[dietKey] || dietKey) + " 포함", "graph-query-condition-chip"));
      });
    }
    condBox.appendChild(condList);
    header.appendChild(condBox);

    var hasDietCondition = activeDiets.length > 0 || (Array.isArray(payload.conditions) && payload.conditions.some(function (c) {
      return c && c.trait_name === "diet_distribution";
    }));
    var sortMessage = hasDietCondition
      ? "정렬 기준: 선택한 먹이 구성 비율 합산 높은 순 (모든 선택 먹이 > 0% AND 조건 · EltonTraits 확실성 A·B·C 근거, 가나다·알파벳순 아님)"
      : "정렬 기준: 이름순 (" + (activeScope === "outside" ? "영명 · 검증 국명 · 학명" : "검증 국명 · 영명 · 학명") + ")";
    header.appendChild(createEl(doc, "p", sortMessage, "explore-sort-note"));
    container.appendChild(header);

    // 2. Coverage summary
    if (payload.coverage && typeof payload.coverage === "object") {
      var cov = payload.coverage;
      var covBox = createEl(doc, "div", null, "explore-coverage");
      covBox.setAttribute("role", "group");
      covBox.setAttribute("aria-label", "조건 자료 범위 및 일치 현황");

      var pairs = [
        ["범위 내 대상", typeof cov.scoped === "number" ? cov.scoped + "종" : "-"],
        ["조건 자료 확인", typeof cov.evaluable === "number" ? cov.evaluable + "종" : "-"],
        ["조건 일치", typeof cov.matched === "number" ? cov.matched + "종" : "-"],
      ];
      pairs.forEach(function (pair) {
        var cell = createEl(doc, "div", null, "explore-coverage-item");
        cell.appendChild(createEl(doc, "span", pair[0], "explore-coverage-label"));
        cell.appendChild(createEl(doc, "strong", pair[1], "explore-coverage-value"));
        covBox.appendChild(cell);
      });
      container.appendChild(covBox);
    }

    // 3. Status-specific body (answer vs empty vs insufficient_data)
    if (status === "empty") {
      var emptyBox = createEl(doc, "div", null, "explore-state-box");
      emptyBox.setAttribute("data-state", "empty");
      emptyBox.appendChild(createEl(doc, "h3", "조건에 맞는 새가 없습니다 (일치 0종)"));
      if (typeof payload.text === "string" && payload.text.trim()) {
        emptyBox.appendChild(createEl(doc, "p", payload.text.trim()));
      }
      emptyBox.appendChild(createEl(
        doc,
        "p",
        "선택한 범위와 형질 자료를 검토했으나 지정한 조건을 모두 만족하는 종이 0종입니다. 서식 환경이나 먹이 조합을 완화해 다시 조회해 보세요."
      ));
      container.appendChild(emptyBox);
    } else if (status === "insufficient_data") {
      var insuffBox = createEl(doc, "div", null, "explore-state-box");
      insuffBox.setAttribute("data-state", "insufficient_data");
      insuffBox.appendChild(createEl(doc, "h3", "조건을 판단할 형질 자료가 없습니다 (자료 부족)"));
      if (typeof payload.text === "string" && payload.text.trim()) {
        insuffBox.appendChild(createEl(doc, "p", payload.text.trim()));
      }
      insuffBox.appendChild(createEl(
        doc,
        "p",
        "조건에 맞는 종이 0종인 것(불일치)이 아니라, 해당 범위에서 조건 형질을 평가할 수 있는 활성 자료가 확인되지 않은 상태입니다."
      ));
      container.appendChild(insuffBox);
    } else {
      if (typeof payload.text === "string" && payload.text.trim()) {
        container.appendChild(createEl(doc, "p", payload.text.trim(), "explore-summary-text"));
      }
      var items = Array.isArray(payload.items) ? payload.items : [];
      var pagination = payload.pagination;
      function appendPagination(position) {
        if (!pagination || pagination.total_pages <= 1) { return; }
        var nav = createEl(doc, "nav", null, "explore-pagination");
        nav.setAttribute("aria-label", position === "top" ? "검색 결과 상단 페이지" : "검색 결과 하단 페이지");
        var previous = createEl(doc, "button", "← 이전");
        previous.type = "button";
        previous.disabled = pagination.page <= 1;
        previous.addEventListener("click", function () { options.onPageChange(pagination.page - 1); });
        nav.appendChild(previous);
        var select = createEl(doc, "select", null, "explore-page-select");
        select.id = "explore-page-" + position;
        select.setAttribute("aria-label", "결과 페이지 선택");
        for (var page = 1; page <= pagination.total_pages; page += 1) {
          var option = createEl(doc, "option", page + " / " + pagination.total_pages + " 페이지");
          option.value = String(page);
          select.appendChild(option);
        }
        select.value = String(pagination.page);
        select.addEventListener("change", function () { options.onPageChange(Number(select.value)); });
        nav.appendChild(select);
        var next = createEl(doc, "button", "다음 →");
        next.type = "button";
        next.disabled = pagination.page >= pagination.total_pages;
        next.addEventListener("click", function () { options.onPageChange(pagination.page + 1); });
        nav.appendChild(next);
        container.appendChild(nav);
      }
      if (pagination && items.length) {
        var first = (pagination.page - 1) * pagination.page_size + 1;
        container.appendChild(createEl(doc, "p", "전체 " + pagination.total + "종 중 " + first + "–" +
          (first + items.length - 1) + "종", "explore-page-range"));
        if (options && options.onPageChange) { appendPagination("top"); }
      }

      if (items.length > 0) {
        var list = createEl(doc, "ul", null, "explore-species-list");
        items.forEach(function (item) {
          if (!item || typeof item !== "object" || !item.taxon || typeof item.taxon !== "object") { return; }
          var taxon = item.taxon;
          var card = createEl(doc, "li", null, "explore-species-card");
          var top = createEl(doc, "div", null, "explore-species-top");
          var identity = createEl(doc, "div", null, "explore-species-identity");

          var primaryLabel = speciesLabel(taxon, activeScope);
          identity.appendChild(createEl(doc, "strong", primaryLabel, "explore-species-name"));

          var sciName = typeof taxon.scientific_name === "string" ? taxon.scientific_name.trim() : "";
          if (sciName && sciName !== primaryLabel) {
            identity.appendChild(createEl(doc, "span", sciName, "explore-species-sci"));
          }

          var verifiedKo = taxon.korean_name_status !== "machine-translated" && typeof taxon.korean_name === "string"
            ? taxon.korean_name.trim() : "";
          var engName = typeof taxon.english_name === "string" ? taxon.english_name.trim() : "";
          var secondary = activeScope === "outside"
            ? (verifiedKo && verifiedKo !== primaryLabel ? verifiedKo : "")
            : (engName && engName !== primaryLabel && engName !== sciName ? engName : "");
          if (secondary) {
            identity.appendChild(createEl(doc, "span", secondary, "explore-species-sub"));
          }
          top.appendChild(identity);

          if (sciName) {
            var profileLink = createEl(doc, "a", "새 도감 보기 →", "explore-profile-link");
            profileLink.href = buildBirdsProfileHref(sciName, activeScope);
            if (options && options.onOpenProfile) {
              profileLink.setAttribute("aria-haspopup", "dialog");
              profileLink.addEventListener("click", function (event) {
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button > 0) { return; }
                event.preventDefault();
                options.onOpenProfile(profileLink, taxon, activeScope);
              });
            }
            top.appendChild(profileLink);
          }
          card.appendChild(top);

          if (Array.isArray(item.paths) && item.paths.length > 0) {
            var pathList = createEl(doc, "ul", null, "explore-item-paths");
            var cardSources = new Map();
            item.paths.forEach(function (p) {
              if (!p || typeof p.text !== "string" || !p.text.trim()) { return; }
              var pLi = createEl(doc, "li", p.text.trim());
              var pUrl = sanitizeUrl(p.source_url);
              var pName = typeof p.source_name === "string" && p.source_name.trim() ? p.source_name.trim() : "";
              if (pUrl && pName) {
                cardSources.set(pName + "|" + pUrl, { name: pName, url: pUrl });
              }
              pathList.appendChild(pLi);
            });
            card.appendChild(pathList);
            if (cardSources.size > 0) {
              var sourceDetails = createEl(doc, "details", null, "explore-card-sources");
              sourceDetails.appendChild(createEl(doc, "summary", "출처 " + cardSources.size + "개"));
              cardSources.forEach(function (src) {
                var sourceLine = createEl(doc, "p");
                sourceLine.appendChild(safeLink(doc, src.name, src.url));
                sourceDetails.appendChild(sourceLine);
              });
              card.appendChild(sourceDetails);
            }
          }

          list.appendChild(card);
        });
        container.appendChild(list);
        if (options && options.onPageChange) { appendPagination("bottom"); }
      }
    }

    // 4. Shared query/scope paths
    if (Array.isArray(payload.paths) && payload.paths.length > 0) {
      var sharedDetails = createEl(doc, "details", null, "graph-shared-paths graph-query-evidence");
      var sharedSummary = createEl(doc, "summary", "조회 범위 및 조건 확인 경로 (" + payload.paths.length + ")");
      sharedDetails.appendChild(sharedSummary);
      var sharedList = createEl(doc, "ul", null, "route-results");
      payload.paths.forEach(function (pathItem) {
        if (!pathItem || typeof pathItem.text !== "string" || !pathItem.text.trim()) { return; }
        var li = createEl(doc, "li", pathItem.text.trim());
        var url = sanitizeUrl(pathItem.source_url);
        var sName = typeof pathItem.source_name === "string" && pathItem.source_name.trim() ? pathItem.source_name.trim() : "";
        if (url && sName) {
          li.appendChild(createEl(doc, "span", " ("));
          li.appendChild(safeLink(doc, sName, url));
          li.appendChild(createEl(doc, "span", ")"));
        }
        sharedList.appendChild(li);
      });
      sharedDetails.appendChild(sharedList);
      container.appendChild(sharedDetails);
    }

    // 5. Sources disclosure
    if (Array.isArray(payload.sources) && payload.sources.length > 0) {
      var dedupedSources = [];
      var seenSourceKeys = new Set();
      payload.sources.forEach(function (src) {
        if (!src || typeof src !== "object") { return; }
        var rawName = typeof src.source_name === "string" && src.source_name.trim()
          ? src.source_name.trim()
          : (typeof src.name === "string" && src.name.trim() ? src.name.trim() : "");
        if (!rawName) { return; }
        var rawUrl = sanitizeUrl(src.source_url || src.url);
        var key = rawName + "|" + (rawUrl || "");
        if (seenSourceKeys.has(key)) { return; }
        seenSourceKeys.add(key);
        dedupedSources.push({ name: rawName, url: rawUrl });
      });
      if (dedupedSources.length > 0) {
        var sourcesDetails = createEl(doc, "details", null, "species-answer-sources explore-sources");
        sourcesDetails.appendChild(createEl(doc, "summary", "출처 및 근거 자료 (" + dedupedSources.length + ")"));
        dedupedSources.forEach(function (src) {
          var p = createEl(doc, "p");
          p.appendChild(safeLink(doc, src.name, src.url));
          sourcesDetails.appendChild(p);
        });
        container.appendChild(sourcesDetails);
      }
    }

    // 6. Limitations disclosure (collapsed by default, neutral style)
    var seenNotes = new Set();
    var noteItems = [];
    (Array.isArray(payload.limitations) ? payload.limitations : []).forEach(function (lim) {
      if (typeof lim === "string") {
        var trimmed = lim.trim();
        if (trimmed && !seenNotes.has(trimmed)) {
          seenNotes.add(trimmed);
          noteItems.push(trimmed);
        }
      }
    });
    if (noteItems.length > 0) {
      var notesDetails = createEl(doc, "details", null, "species-note graph-query-notes explore-limitations");
      var baseNoteTitle = status === "insufficient_data" ? "자료 한계 및 유의사항" : "안내 및 유의사항";
      notesDetails.appendChild(createEl(doc, "summary", baseNoteTitle + " (" + noteItems.length + ")"));
      var noteList = createEl(doc, "ul");
      noteItems.forEach(function (text) {
        noteList.appendChild(createEl(doc, "li", text));
      });
      notesDetails.appendChild(noteList);
      container.appendChild(notesDetails);
    }
  }

  function init(doc, win) {
    if (!doc || typeof doc.getElementById !== "function") { return null; }
    var form = doc.getElementById("explore-form");
    var taxonInput = doc.getElementById("explore-taxon");
    var habitatSelect = doc.getElementById("explore-habitat");
    var scopeNote = doc.getElementById("explore-scope-note");
    var submitBtn = doc.getElementById("explore-submit");
    var resetBtn = doc.getElementById("explore-reset");
    var statusRegion = doc.getElementById("explore-status");
    var resultsSection = doc.getElementById("explore-results");
    if (!form || !statusRegion || !resultsSection) { return null; }

    var scopeRadios = SPECIES_SCOPES.map(function (scope) {
      return doc.getElementById("explore-scope-" + scope);
    }).filter(Boolean);

    var dietCheckboxes = DIETS.map(function (key) {
      return doc.getElementById("explore-diet-" + key);
    }).filter(Boolean);

    var activeScope = "all";
    var requestGeneration = 0;
    var activeController = null;
    var profileGeneration = 0;
    var profilePopup = null;
    var profileCache = new Map();

    function clearProfilePopup() {
      profileGeneration += 1;
      if (profilePopup) {
        var popup = profilePopup;
        profilePopup = null;
        popup.disposePopup();
        popup.parentNode.removeChild(popup);
      }
    }

    async function openProfile(link, taxon, scope) {
      clearProfilePopup();
      var current = profileGeneration;
      var chat = win && win.RobinGraphChat;
      var fetcher = win && win.fetch;
      setStatus("새 도감 카드를 불러오고 있습니다…", false);
      link.setAttribute("aria-busy", "true");
      try {
        if (!chat || !fetcher) { throw new Error("unavailable"); }
        var params = new URLSearchParams({ name: taxon.scientific_name, species_scope: scope });
        var key = params.toString();
        var profile = profileCache.get(key);
        if (!profile) {
          var response = await fetcher("/v1/taxa/profile?" + key + "&defer_enrichment=true", { signal: AbortSignal.timeout(60000) });
          if (current !== profileGeneration) { return; }
          if (!response.ok) { throw new Error("unavailable"); }
          profile = await response.json();
        }
        if (current !== profileGeneration) { return; }
        if (!profile || !profile.taxon || profile.taxon.scientific_name !== taxon.scientific_name ||
            (taxon.taxon_id && profile.taxon.taxon_id !== taxon.taxon_id)) { throw new Error("identity"); }
        profileCache.set(key, profile);
        var card = chat.buildSpeciesCard(doc, profile, {
          fetcher: fetcher,
          speciesScope: scope,
          isActive: function () { return current === profileGeneration; },
        });
        if (card.sourceMaterial) {
          var sources = createEl(doc, "details", null, "card-details card-details-scroll explore-profile-sources");
          sources.appendChild(createEl(doc, "summary", "자료 출처"));
          sources.appendChild(card.sourceMaterial);
          card.querySelector(".species-card-back").appendChild(sources);
        }
        var popup = chat.buildSpeciesPopup(doc, card, profile);
        profilePopup = popup;
        var opener = popup.children[0];
        opener.hidden = true;
        doc.body.appendChild(popup);
        var dialog = popup.children[1];
        dialog.addEventListener("close", function () {
          if (profilePopup === popup) { clearProfilePopup(); }
          if (link.isConnected) { link.focus(); }
        });
        opener.click();
        setStatus(speciesLabel(profile.taxon, scope) + " 도감 카드를 열었습니다.", false);
        if (profile.enrichment_pending) {
          card.setNotesMessage("추가 설명을 불러오는 중입니다.", true);
          function fetchEnrichment(suffix) {
            return fetcher("/v1/taxa/profile?" + key + suffix, { signal: AbortSignal.timeout(60000) }).then(function (response) {
              if (!response.ok) { throw new Error("unavailable"); }
              return response.json();
            }).then(function (fresh) {
              if (current !== profileGeneration) { return null; }
              if (!fresh || !fresh.taxon || fresh.taxon.taxon_id !== profile.taxon.taxon_id ||
                  fresh.taxon.scientific_name !== taxon.scientific_name ||
                  !fresh.lineage || !profile.lineage || fresh.lineage.concept_set_id !== profile.lineage.concept_set_id ||
                  fresh.lineage.taxonomy_release !== profile.lineage.taxonomy_release) { throw new Error("identity"); }
              return fresh;
            });
          }
          if (!Array.isArray(profile.images) || !profile.images.length) {
            card.setEnrichmentMessage("사진을 불러오는 중입니다.");
            fetchEnrichment("&include_notes=false").then(function (fresh) {
              if (!fresh) { return; }
              var media = { images: fresh.images, photo_availability: fresh.photo_availability };
              card.updateEnrichment(media);
              Object.assign(profile, media);
            }).catch(function () {
              if (current === profileGeneration) { card.setEnrichmentMessage("사진 제공처를 현재 조회할 수 없습니다."); }
            });
          }
          fetchEnrichment("").then(function (fresh) {
            if (!fresh) { return; }
            card.updateEnrichment(fresh);
            profileCache.set(key, fresh);
          }).catch(function () {
            if (current === profileGeneration) {
              card.setNotesMessage("추가 설명을 불러오지 못했습니다. 먼저 표시한 정보는 계속 확인할 수 있습니다.");
            }
          });
        }
      } catch (_) {
        if (current === profileGeneration) {
          clearProfilePopup();
          setStatus("새 도감 카드를 불러오지 못했습니다. ‘새 도감 보기’를 다시 눌러 주세요.", true);
        }
      } finally {
        link.removeAttribute("aria-busy");
      }
    }

    function abortInFlight() {
      if (activeController && typeof activeController.abort === "function") {
        try { activeController.abort(); } catch (_) {}
      }
      activeController = null;
    }

    function setBusy(busy) {
      if (submitBtn) { submitBtn.disabled = Boolean(busy); }
      form.setAttribute("aria-busy", busy ? "true" : "false");
    }

    function setStatus(message, isError) {
      statusRegion.textContent = message;
      if (isError) {
        statusRegion.setAttribute("data-error", "true");
      } else {
        statusRegion.removeAttribute("data-error");
      }
    }

    function readFormState() {
      var selectedScope = activeScope;
      scopeRadios.forEach(function (radio) {
        if (radio.checked) { selectedScope = normalizeSpeciesScope(radio.value); }
      });
      var selectedDiets = [];
      dietCheckboxes.forEach(function (box) {
        if (box.checked) { selectedDiets.push(box.value); }
      });
      return {
        species_scope: selectedScope,
        taxon: taxonInput && typeof taxonInput.value === "string" ? taxonInput.value.trim() : "",
        habitat: habitatSelect && typeof habitatSelect.value === "string" ? habitatSelect.value : "",
        diet: normalizeDietList(selectedDiets),
      };
    }

    function applyStateToControls(state) {
      var nextScope = normalizeSpeciesScope(state && state.species_scope);
      activeScope = nextScope;
      scopeRadios.forEach(function (radio) {
        radio.checked = radio.value === nextScope;
      });
      if (scopeNote) {
        scopeNote.textContent = SPECIES_SCOPE_NOTES[nextScope] || SPECIES_SCOPE_NOTES.all;
      }
      if (taxonInput) {
        taxonInput.value = state && typeof state.taxon === "string" ? state.taxon : "";
      }
      if (habitatSelect) {
        habitatSelect.value = state && typeof state.habitat === "string" && HABITATS.indexOf(state.habitat) !== -1
          ? state.habitat
          : "";
      }
      var dietSet = new Set(normalizeDietList(state && state.diet));
      dietCheckboxes.forEach(function (box) {
        box.checked = dietSet.has(box.value);
      });
    }

    function invalidatePendingOnFilterEdit(statusMessage) {
      resultsSection.hidden = true;
      clearProfilePopup();
      requestGeneration += 1;
      abortInFlight();
      setBusy(false);
      if (statusMessage) {
        setStatus(statusMessage, false);
      }
    }

    function syncUrlSearch(queryString) {
      if (!win || !win.history || typeof win.history.replaceState !== "function") { return; }
      var pathname = (win.location && win.location.pathname) || "/explore";
      var target = queryString ? pathname + "?" + queryString : pathname;
      try {
        win.history.replaceState(null, "", target);
      } catch (_) {}
    }

    async function executeSearch(customQueryString, stateSnapshot) {
      clearProfilePopup();
      profileCache.clear();
      var myGeneration = ++requestGeneration;
      abortInFlight();
      var controller = typeof AbortController === "function" ? new AbortController() : null;
      activeController = controller;

      var state = stateSnapshot || readFormState();
      var params = buildExploreParams(state);
      var queryString = typeof customQueryString === "string" ? customQueryString : params.toString();

      setBusy(true);
      setStatus("선택한 조건에 맞는 새와 출처 근거를 확인하고 있습니다…", false);

      var fetchFn = (win && typeof win.fetch === "function") ? win.fetch : (typeof fetch === "function" ? fetch : null);
      if (!fetchFn) {
        setBusy(false);
        setStatus("브라우저 조회 기능을 사용할 수 없습니다.", true);
        return;
      }

      try {
        var options = { method: "GET" };
        if (controller && controller.signal) {
          options.signal = controller.signal;
        }
        var response = await fetchFn("/v1/taxa/explore" + (queryString ? "?" + queryString : ""), options);
        if (myGeneration !== requestGeneration) { return; }

        if (!response.ok) {
          if (response.status === 422) {
            var errBody = null;
            try { errBody = await response.json(); } catch (_) {}
            if (myGeneration !== requestGeneration) { return; }
            var validationMsg = formatValidationError(errBody);
            renderStateBox(
              doc,
              resultsSection,
              "validation_error",
              "조회 조건을 다시 확인해 주세요",
              validationMsg,
              "일치하는 종이 0종인 결과가 아니라, 입력한 분류군 또는 조건 형식을 확인하지 못해 조회를 멈추었습니다."
            );
            setStatus(validationMsg, true);
            return;
          }
          var unavailableMsg = "현재 조건으로 새 찾기 기능을 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.";
          renderStateBox(
            doc,
            resultsSection,
            "error",
            "조회 서비스를 일시적으로 사용할 수 없습니다",
            unavailableMsg,
            "조건 불일치(0종)나 자료 부족이 아니라 서버 응답 오류입니다."
          );
          setStatus(unavailableMsg, true);
          return;
        }

        var payload = await response.json();
        if (myGeneration !== requestGeneration) { return; }

        if (payload && payload.query && typeof payload.query === "object") {
          applyStateToControls(payload.query);
        }
        if (payload.query) { syncUrlSearch(buildExploreParams(payload.query).toString()); }
        renderExploreResult(doc, resultsSection, payload, state.species_scope, {
          onOpenProfile: openProfile,
          onPageChange: function (page) {
            var next = Object.assign({}, payload.query || state, { page: page });
            var query = buildExploreParams(next).toString();
            var generation = requestGeneration + 1;
            syncUrlSearch(query);
            executeSearch(query, next).then(function () {
              if (requestGeneration !== generation || resultsSection.hidden) { return; }
              if (resultsSection.scrollIntoView) { resultsSection.scrollIntoView({ block: "start" }); }
              var select = doc.getElementById("explore-page-top");
              if (select && select.focus) { select.focus({ preventScroll: true }); }
            });
          },
        });

        if (payload.status === "empty") {
          setStatus("조회가 완료되었습니다. 조건에 맞는 종이 없습니다 (0종).", false);
        } else if (payload.status === "insufficient_data") {
          setStatus("조회가 완료되었습니다. 선택한 조건을 판단할 형질 자료가 없습니다.", false);
        } else {
          var itemCount = Array.isArray(payload.items) ? payload.items.length : 0;
          var totalMatched = payload.coverage && typeof payload.coverage.matched === "number"
            ? payload.coverage.matched
            : itemCount;
          setStatus(
            "출처가 확인된 " + totalMatched + "종 중 " + itemCount + "종을 표시했습니다." +
              (payload.pagination ? " " + payload.pagination.page + " / " + payload.pagination.total_pages + " 페이지입니다." : ""),
            false
          );
        }
      } catch (err) {
        if (myGeneration !== requestGeneration) { return; }
        if (err && err.name === "AbortError") { return; }
        var netMsg = err && err.name === "TimeoutError"
          ? "조회 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
          : "현재 조건으로 새 찾기 기능을 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.";
        renderStateBox(
          doc,
          resultsSection,
          "error",
          "조회 중 연결 오류가 발생했습니다",
          netMsg,
          "조건 불일치(0종)나 자료 부족이 아니라 통신 오류입니다."
        );
        setStatus(netMsg, true);
      } finally {
        if (myGeneration === requestGeneration) {
          setBusy(false);
          activeController = null;
        }
      }
    }

    scopeRadios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (!radio.checked) { return; }
        var nextScope = normalizeSpeciesScope(radio.value);
        activeScope = nextScope;
        if (scopeNote) {
          scopeNote.textContent = SPECIES_SCOPE_NOTES[nextScope] || SPECIES_SCOPE_NOTES.all;
        }
        var label = SCOPE_LABELS[nextScope] || SCOPE_LABELS.all;
        invalidatePendingOnFilterEdit("분포 범위 기준을 ‘" + label + "’(으)로 변경했습니다. ‘조건으로 새 찾기’를 눌러 조회하세요.");
      });
    });

    if (taxonInput) {
      taxonInput.addEventListener("input", function () {
        invalidatePendingOnFilterEdit("분류군 입력이 변경되었습니다. ‘조건으로 새 찾기’를 눌러 조회하세요.");
      });
    }

    if (habitatSelect) {
      habitatSelect.addEventListener("change", function () {
        invalidatePendingOnFilterEdit("서식 환경 조건이 변경되었습니다. ‘조건으로 새 찾기’를 눌러 조회하세요.");
      });
    }

    dietCheckboxes.forEach(function (box) {
      box.addEventListener("change", function () {
        invalidatePendingOnFilterEdit("먹이 구성 조건이 변경되었습니다. ‘조건으로 새 찾기’를 눌러 조회하세요.");
      });
    });

    form.addEventListener("submit", function (event) {
      if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      var state = readFormState();
      var params = buildExploreParams(state);
      var queryString = params.toString();
      syncUrlSearch(queryString);
      executeSearch(queryString, state);
    });

    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        applyStateToControls({ species_scope: "all", taxon: "", habitat: "", diet: [] });
        invalidatePendingOnFilterEdit("조건을 초기화했습니다. 원하는 조건을 선택하고 ‘조건으로 새 찾기’를 눌러 조회하세요.");
        resultsSection.replaceChildren();
        resultsSection.hidden = true;
        resultsSection.removeAttribute("data-result-state");
        syncUrlSearch("");
      });
    }

    var initialSearch = (win && win.location && typeof win.location.search === "string")
      ? win.location.search
      : (typeof location !== "undefined" && typeof location.search === "string" ? location.search : "");
    var parsedInitial = parseExploreSearch(initialSearch);
    if (parsedInitial.hasQuery) {
      applyStateToControls(parsedInitial);
      executeSearch(parsedInitial.rawQuery, parsedInitial);
    }

    return {
      readFormState: readFormState,
      applyStateToControls: applyStateToControls,
      executeSearch: executeSearch,
    };
  }

  return {
    SPECIES_SCOPES: SPECIES_SCOPES,
    HABITATS: HABITATS,
    DIETS: DIETS,
    normalizeSpeciesScope: normalizeSpeciesScope,
    normalizeDietList: normalizeDietList,
    sanitizeUrl: sanitizeUrl,
    speciesLabel: speciesLabel,
    buildExploreParams: buildExploreParams,
    parseExploreSearch: parseExploreSearch,
    formatValidationError: formatValidationError,
    buildBirdsProfileHref: buildBirdsProfileHref,
    renderExploreResult: renderExploreResult,
    init: init,
  };
});
