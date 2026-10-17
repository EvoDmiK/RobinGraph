/* Read-only species cards: all provider strings are rendered as text. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (parent) parent.appendChild(node);
    return node;
  }
  function safeUrl(value) {
    try { const url = new URL(value); return url.protocol === "https:" ? url.href : null; }
    catch (_) { return null; }
  }
  function link(text, url, parent) {
    const href = safeUrl(url);
    const node = element(href ? "a" : "span", text, parent);
    if (href) { node.href = href; node.target = "_blank"; node.rel = "noopener noreferrer"; }
    return node;
  }
  const ranks = {order:"목", family:"과", genus:"속", species:"종", subspecies:"아종"};
  const scopes = ["all", "korea", "outside", "unknown"];
  const distLabels = {korea:"국내 기록·분포 확인", outside:"국외 분포 검토", unknown:"미확인"};
  const distNotes = {
    korea:"국내 기록·분포 확인: 출처에 한국의 야생 기록 또는 분포가 있습니다. 텃새·철새·미조 구분과 현재 서식 여부는 확인되지 않았습니다.",
    outside:"국외 분포 검토: 검토한 출처의 정상 분포가 한국 밖입니다. 우연한 도래나 사육 기록이 없다는 뜻은 아닙니다.",
    unknown:"미확인: 한국 분포 근거를 확인하지 못했습니다. 국외 분포라는 뜻은 아닙니다."
  };
  function currentScope() {
    const node = $("bird-scope");
    return node && scopes.includes(node.value) ? node.value : "all";
  }
  function speciesLabel(taxon) {
    const display = typeof taxon.display_name === "string" && taxon.display_name.trim() && (taxon.korean_name_status !== "machine-translated" || taxon.display_name.trim() !== taxon.korean_name) ? taxon.display_name.trim() : "";
    return display || (taxon.korean_name_status !== "machine-translated" && taxon.korean_name) || taxon.english_name || taxon.scientific_name;
  }
  function render(profile) {
    const card = $("bird-card"); card.replaceChildren(); card.hidden = false;
    element("h2", speciesLabel(profile.taxon), card);
    element("p", profile.taxon.scientific_name, card);
    const dist = profile.taxon && profile.taxon.distribution;
    if (dist && distLabels[dist.status]) {
      const distSection = element("section", undefined, card); distSection.className = "species-distribution-info";
      element("strong", `분포 범위: ${distLabels[dist.status]}`, distSection);
      element("p", distNotes[dist.status], distSection);
      (Array.isArray(dist.evidence) ? dist.evidence : []).forEach((ev) => {
        if (!ev || typeof ev !== "object") return;
        const row = element("small", undefined, distSection);
        link(ev.source_title || ev.source_id || "분포 출처", ev.source_url, row);
        const meta = [ev.category ? `범주 ${ev.category}` : "", ev.source_text || ""].filter(Boolean).join(" · ");
        if (meta) element("span", ` · ${meta}`, row);
      });
    }
    const layout = element("div", undefined, card); layout.className = "species-layout";
    const media = element("section", undefined, layout); media.setAttribute("aria-label", "대표 사진");
    let renderedPhotos = 0;
    (Array.isArray(profile.images) ? profile.images : []).forEach((photo) => {
      const url = safeUrl(photo.image_url);
      if (!url || !["upload.wikimedia.org", "thumb.wikimedia.org"].includes(new URL(url).hostname)) return;
      renderedPhotos += 1;
      const figure = element("figure", undefined, media);
      const image = element("img", undefined, figure); image.src = url; image.loading = "lazy";
      image.alt = `${speciesLabel(profile.taxon)} 대표 사진: ${photo.title}`;
      image.referrerPolicy = "no-referrer";
      const failed = element("p", "사진 파일을 불러오지 못했습니다.", figure); failed.hidden = true;
      const retry = element("button", "사진 다시 불러오기", figure); retry.type = "button"; retry.hidden = true;
      image.addEventListener("error", () => { image.hidden = true; failed.hidden = false; retry.hidden = false; retry.disabled = false; });
      image.addEventListener("load", () => { image.hidden = false; failed.hidden = true; retry.hidden = true; retry.disabled = false; });
      retry.addEventListener("click", () => { retry.disabled = true; failed.textContent = "사진을 다시 불러오는 중입니다."; image.src = url; });
      const caption = element("figcaption", undefined, figure);
      link("Wikimedia Commons 원본", photo.source_url, caption);
      element("span", ` · ${photo.creator} · `, caption);
      link(photo.license_name, photo.license_url, caption);
      if (photo.credit) element("div", photo.credit, caption);
    });
    if (!renderedPhotos) {
      const availability = profile.photo_availability;
      const message = availability && typeof availability.message === "string" ? availability.message : "사용 조건이 확인된 대표 사진이 없습니다.";
      const placeholder = element("p", message, media); placeholder.className = "species-photo-placeholder";
    }
    const facts = element("section", undefined, layout); element("h2", "특징 · 먹이 · 서식 환경", facts);
    element("p", "수치는 자료에 기록된 종 평균입니다. 자료마다 먹이 분류가 다를 수 있습니다. 접은 날개 길이는 날개를 펼친 폭과 다릅니다.", facts);
    if (!profile.traits.length) element("p", "이 종의 활성 형질 자료가 아직 없습니다.", facts);
    const groups = new Map();
    profile.traits.forEach((trait) => {
      const key = JSON.stringify([trait.name, trait.value, trait.unit, trait.inferred]);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(trait);
    });
    groups.forEach((sources) => {
      const trait = sources[0];
      const row = element("div", undefined, facts); row.className = "trait";
      element("strong", trait.label, row);
      const unit = trait.unit && trait.unit !== "percent" ? ` ${trait.unit}` : "";
      element("span", trait.display + unit + (trait.inferred ? " (추정값)" : ""), row);
      sources.forEach((citation) => {
        const source = element("small", undefined, row);
        link(citation.citation || citation.source_name, citation.source_url, source);
        element("span", ` · ${citation.license_name}`, source);
      });
    });
    element("p", profile.vegetation_note, facts);
    profile.warnings.forEach((warning) => element("p", warning, card));
    const details = element("details", undefined, card); element("summary", "분류 계통 · 자료 버전", details);
    element("p", `${profile.lineage.taxonomy_source} · ${profile.lineage.taxonomy_release}`, details);
    const list = element("ul", undefined, details);
    profile.lineage.items.forEach((taxon) => {
      const item = element("li", `${ranks[taxon.rank] || taxon.rank}: ${(taxon.korean_name || taxon.english_name) ? speciesLabel(taxon) + " · " : ""}${taxon.scientific_name}`, list);
      if (taxon.korean_name_source_url) link(" (국명 참고 출처)", taxon.korean_name_source_url, item);
    });
  }
  let requestId = 0;
  async function load(event) {
    if (event) event.preventDefault();
    const name = $("bird-name").value.trim(); if (!name) return;
    const species_scope = currentScope();
    const current = ++requestId; $("bird-submit").disabled = true;
    $("bird-card").hidden = true; $("bird-status").textContent = "분류·형질·사진을 확인하고 있습니다…";
    try {
      const params = species_scope === "all" ? {name} : {name, species_scope};
      const response = await fetch("/v1/taxa/profile?" + new URLSearchParams(params), {signal:AbortSignal.timeout(60000)});
      if (!response.ok) throw new Error(response.status === 404 ? (species_scope !== "all" ? "선택한 분포 범위에서 해당 종을 확인하지 못했습니다." : "활성 분류에서 해당 종을 찾지 못했습니다. 국명 또는 학명을 확인해 주세요.") : "현재 새 정보를 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.");
      const profile = await response.json(); if (current !== requestId) return;
      render(profile); $("bird-status").textContent = "출처가 확인된 정보를 표시했습니다.";
    } catch (error) {
      if (current === requestId) $("bird-status").textContent = error.name === "TimeoutError" ? "조회 시간이 초과되었습니다. 다시 시도해 주세요." : error.message;
    } finally { if (current === requestId) $("bird-submit").disabled = false; }
  }
  $("bird-form").addEventListener("submit", load);
  const scopeSelect = $("bird-scope");
  if (scopeSelect) {
    scopeSelect.addEventListener("change", () => {
      ++requestId;
      $("bird-submit").disabled = false;
      $("bird-card").replaceChildren();
      $("bird-card").hidden = true;
      $("bird-status").textContent = "분포 범위 기준을 변경했습니다. 정보 보기를 눌러 조회하세요.";
    });
  }
  const searchParams = new URLSearchParams(location.search);
  const initial = searchParams.get("name");
  if (initial) $("bird-name").value = initial.slice(0, 200);
  const initialScope = searchParams.get("species_scope");
  if (scopeSelect && scopes.includes(initialScope)) scopeSelect.value = initialScope;
  load();
})();
