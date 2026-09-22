"""Generate the n8n-native RobinGraph Korean vernacular-name ingest workflow.

Source: Wikidata structured data (query.wikidata.org SPARQL endpoint), CC0
per https://www.wikidata.org/wiki/Wikidata:Licensing. See the
``korean-vernacular-wikidata-species-labels`` collection point in
``config/collection-points.json`` for the verification note and the exact
SPARQL query used to confirm the license and a sample match
(Q25348 -> "Anas platyrhynchos" -> ko "청둥오리") on 2026-09-11.

This workflow never creates a ``TaxonConceptSet`` and never writes
``ExternalTaxonConcept``. It only attaches ``VernacularName {language: 'ko'}``
nodes to ``Taxon:BirdTaxon`` nodes that already exist in the *active*
``reference-taxonomy`` concept set (see
``docs/n8n/reference-ingest.md``), matched by exact ``scientific_name``. A
Wikidata scientific name with more than one distinct Korean label, the same
Korean label shared by two different scientific names (a homonym), or a
name with zero or more than one matching ``Taxon``, is never guessed at --
it is routed to a ``VernacularNameCandidate`` for manual review instead.

Snapshot model (fixes applied after GPT-5.6 Sol's initial review, see
``docs/n8n/korean-vernacular-ingest.md``):

- ``wikidata_dataset_id`` and ``source_release`` are computed *per run* from
  the actual fetch response, not baked into ``config/collection-points.json``
  at generation time. Both are content-addressed
  (``sha256-<hash of the raw SPARQL response>``), so two runs that observe
  byte-identical Wikidata content compute the *same* id and idempotently
  ``MERGE`` the same immutable nodes; any different content gets a new id
  and never overwrites a prior snapshot's hash in place.
- ``VernacularName``/``SourceRecord`` node ids are scoped by
  ``wikidata_dataset_id``, so every snapshot's assertions are their own
  immutable nodes. Writes attach to ``Taxon`` via ``HAS_VERNACULAR_NAME``
  as each batch commits, but stay invisible to
  ``taxonomy_lineage_neo4j.py`` until ``IngestState {id:
  'korean-vernacular-names'}.active_dataset_id`` is flipped to this run's
  dataset id at ``Finalize`` -- exactly mirroring how AviList taxa under a
  new, not-yet-active ``TaxonConceptSet`` stay invisible until
  ``reference-taxonomy``'s ``IngestState`` is advanced.
- A name whose taxon is not present in a later snapshot is retired for
  free: it simply has no ``VernacularName`` node scoped to the new active
  ``wikidata_dataset_id``, so the read path (which requires that exact
  match) stops surfacing it without any explicit delete.
- ``Finalize`` only activates a snapshot under an optimistic-concurrency
  guard (the run's captured "prior" ``korean-vernacular-names`` state must
  still match reality) and only if the ``reference-taxonomy`` active
  concept set has not changed since this run resolved matches against it --
  so a concurrent stale writer can never clobber a newer activation, and a
  mid-run AviList taxonomy switch fails this run closed instead of writing
  against a taxonomy generation that is no longer current.
- Any structurally malformed SPARQL binding (missing item/taxonName/label)
  fails the run closed rather than being silently dropped.
- Every failure branch (quality gates, Start, batch load, or Finalize) now
  runs through ``MARK_FAILED_STATEMENT`` before the Discord notification.
  Once ``Start`` has flipped an ``IngestionRun`` to ``status: 'loading'``, a
  downstream failure sets it to ``'failed'`` with the same
  ``failure_reason`` the notification reports -- previously the run was
  left stuck at ``'loading'`` forever, with no durable record that it
  failed. The guard (``WHERE run.status = 'loading'``) makes this a safe
  no-op for the two branches that fail before any run exists (quality
  gates, or a Start whose own ``active_concept_set_id`` guard already
  rejected it) and never touches ``IngestState`` -- the active dataset is
  never advanced or altered on a failure path.
- ``Fetch Wikidata Korean bird labels`` now sets ``neverError`` and
  ``onError: continueRegularOutput`` (mirroring ``Fetch pinned ChecklistBank
  release`` in ``generate_n8n_reference_ingest.py``), so a non-2xx response
  *or* a connection-level failure (DNS, timeout exhaustion, refused
  connection) flows into ``Normalize Korean vernacular candidates`` as data
  instead of stopping the whole execution before any Discord notification
  or run bookkeeping can run.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

try:
    from .generate_n8n_reference_ingest import (
        boolean_if,
        code,
        compact_cypher,
        discord,
        edge,
        neo4j_node,
        node,
        node_id,
    )
except ImportError:  # pragma: no cover - exercised when run as a script
    from generate_n8n_reference_ingest import (
        boolean_if,
        code,
        compact_cypher,
        discord,
        edge,
        neo4j_node,
        node,
        node_id,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n" / "robingraph-korean-vernacular-ingest.json"
POINTS = ROOT / "config" / "collection-points.json"
SOURCES = ROOT / "config" / "source-registry.json"

COLLECTION_POINT_ID = "korean-vernacular-wikidata-species-labels"

KOREAN_VERNACULAR_LABELS = (
    "VernacularName",
    "VernacularNameCandidate",
)

# Live-verified 2026-09-11 against https://query.wikidata.org/sparql :
# Q7432 = species (taxon rank), Q5113 = Aves. Restricting the label filter to
# lang="ko" up front keeps the result set to Aves species that actually have
# a Korean label, instead of enumerating every Aves species item first.
SPARQL_QUERY = compact_cypher(
    """
    SELECT ?item ?taxonName ?itemLabel WHERE {
      ?item wdt:P105 wd:Q7432 .
      ?item wdt:P171* wd:Q5113 .
      ?item wdt:P225 ?taxonName .
      ?item rdfs:label ?itemLabel .
      FILTER(LANG(?itemLabel) = "ko")
    }
    """
)


def require_collection_point_approved(collection_point_id: str) -> dict[str, object]:
    """Return the named collection point merged with its source, or raise.

    Mirrors ``generate_n8n_reference_ingest.load_approved_configuration``'s
    fail-closed gate: a collection point (or its underlying source) that is
    disabled or not ``license_policy_status == "allowed"`` must never reach
    workflow generation. Parameterized by ID so a test can also point it at
    ``korea-nibr-species`` (still ``review_required``/``enabled: false`` as
    of this writing) and observe a real ``RuntimeError`` from the project's
    actual current registry state, not an invented one.
    """

    payload = json.loads(POINTS.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in json.loads(SOURCES.read_text(encoding="utf-8"))}
    point = next(
        (p for p in payload["collection_points"] if p["collection_point_id"] == collection_point_id),
        None,
    )
    if point is None:
        raise RuntimeError(f"unknown collection point: {collection_point_id}")
    if not point["enabled"] or point["license_policy_status"] != "allowed":
        raise RuntimeError(f"collection point is not approved: {point['collection_point_id']}")
    source = sources.get(point["source_id"])
    if source is None:
        raise RuntimeError(f"unknown source_id: {point['source_id']}")
    if not source["enabled"] or source["license_policy_status"] != "allowed":
        raise RuntimeError(f"source is not approved: {point['source_id']}")
    return {**point, "source": source}


def load_wikidata_collection_point() -> dict[str, object]:
    """Return the approved Wikidata Korean-name collection point, or raise."""

    return require_collection_point_approved(COLLECTION_POINT_ID)


def build_configuration_js(point: dict[str, object]) -> str:
    # `wikidata_dataset_id` and `source_release` are deliberately absent here:
    # Wikidata is mutable, so both are computed per run in "Normalize Korean
    # vernacular candidates" from the actual fetched content hash, never from
    # this static, generation-time collection-point config (see module
    # docstring). `point["source_release"]` is config-review metadata only
    # ("last reviewed as of this date"), not a graph-visible value.
    config = {
        "pipeline_id": "korean-vernacular-names",
        "sparql_endpoint": point["endpoint_uri"],
        "sparql_query": SPARQL_QUERY,
        "wikidata_license_uri": point["source"]["license_uri"],
        "wikidata_landing_uri": point["source"]["landing_uri"],
        "batch_size": 300,
    }
    return (
        "const now = new Date();\n"
        f"const config = {json.dumps(config, ensure_ascii=False)};\n"
        "return [{json: {...config, run_id: `n8n-korean-vernacular-${$execution.id}`, "
        "retrieved_at: now.toISOString()}}];"
    )


# Pure function, deliberately free of n8n globals ($input, $, $json) so it can
# be executed directly under plain `node` in tests with fixture arrays.
CLASSIFY_WIKIDATA_ROWS_JS = r"""
function classifyWikidataRows(bindings) {
  const qidOf = uri => String(uri || '').split('/').pop();
  const text = value => value == null ? '' : String(value).trim();
  const seenTriples = new Set();
  const byTaxonName = new Map();
  // The SPARQL query projects item/taxonName/itemLabel as mandatory
  // (none are OPTIONAL in SPARQL_QUERY), so a binding missing any of them
  // is never an expected, legitimate shape -- it signals a schema change
  // or a malformed/truncated response, and must never be dropped silently.
  let malformedRowCount = 0;
  for (const binding of bindings || []) {
    const qid = qidOf(binding.item && binding.item.value);
    const taxonName = text(binding.taxonName && binding.taxonName.value);
    const koreanName = text(binding.itemLabel && binding.itemLabel.value);
    if (!qid || !taxonName || !koreanName) {
      malformedRowCount += 1;
      continue;
    }
    const tripleKey = qid + '::' + taxonName + '::' + koreanName;
    if (seenTriples.has(tripleKey)) continue;
    seenTriples.add(tripleKey);
    const group = byTaxonName.get(taxonName) || [];
    group.push({qid, taxonName, koreanName});
    byTaxonName.set(taxonName, group);
  }
  const perTaxonClean = [];
  const conflicted = [];
  for (const [taxonName, rows] of byTaxonName) {
    const distinctNames = [...new Set(rows.map(row => row.koreanName))];
    if (distinctNames.length > 1) {
      for (const row of rows) {
        conflicted.push({
          taxon_name: taxonName,
          korean_name: row.koreanName,
          qids: [row.qid],
          reason_code: 'conflicting_korean_labels',
        });
      }
      continue;
    }
    perTaxonClean.push({
      taxon_name: taxonName,
      korean_name: distinctNames[0],
      qids: [...new Set(rows.map(row => row.qid))].sort(),
    });
  }
  // Second pass, across taxon names: the same Korean label legitimately
  // produced for two DIFFERENT scientific names (a homonym, or the same
  // casual common name misapplied to two species in Wikidata) is a real
  // ambiguity for the exact-match Korean-name lookup, even though each
  // taxon name looked "clean" on its own in the first pass. Neither taxon
  // is allowed to win arbitrarily -- both are quarantined.
  const byKoreanName = new Map();
  for (const row of perTaxonClean) {
    const group = byKoreanName.get(row.korean_name) || [];
    group.push(row);
    byKoreanName.set(row.korean_name, group);
  }
  const clean = [];
  for (const rows of byKoreanName.values()) {
    if (rows.length > 1) {
      for (const row of rows) {
        conflicted.push({
          taxon_name: row.taxon_name,
          korean_name: row.korean_name,
          qids: row.qids,
          reason_code: 'ambiguous_korean_name_across_taxa',
        });
      }
      continue;
    }
    clean.push(rows[0]);
  }
  clean.sort((a, b) => a.taxon_name.localeCompare(b.taxon_name));
  conflicted.sort((a, b) => a.taxon_name.localeCompare(b.taxon_name) || a.korean_name.localeCompare(b.korean_name));
  return {clean, conflicted, malformedRowCount};
}
"""

NORMALIZE_WIKIDATA = (
    CLASSIFY_WIKIDATA_ROWS_JS
    + r"""
const config = $('Build Korean vernacular configuration').first().json;
const hash = $('Hash Wikidata response').first().json.raw_sha256 ?? null;
// Read by name, not $input.first(): 'Read active taxonomy and Korean
// dataset state' now sits between the Hash node and this one so its output
// is guaranteed available (by name) to 'Assemble Korean vernacular quality
// gates' later -- which pushes this node's actual fetch payload off the
// positional $input chain and onto a named lookup instead.
const fetched = $('Hash Wikidata response').first().json;
// fullResponse + responseFormat 'text' surfaces the HTTP status alongside the
// body text on the same item (see 'Fetch AviList snapshot' / 'Hash AviList
// snapshot' in generate_n8n_reference_ingest.py for the established
// convention this mirrors). A non-200 must never be treated as "zero
// candidates found" -- those are different failures with different causes.
// 'Fetch Wikidata Korean bird labels' sets neverError + onError:
// continueRegularOutput, so a connection-level failure (DNS, refused,
// timeout exhaustion) never throws -- it instead lands here with an
// `error` field and no statusCode/data, exactly like the Neo4j nodes'
// onError shape checked in VERIFY_START/VERIFY_BATCHES/VERIFY_FINALIZE.
const upstreamErrorText = String(fetched.error?.message || fetched.error || fetched.message || '');
const statusCode = Number(fetched.statusCode ?? 0);
const raw = fetched.data;
let parsed = null;
let parseError = null;
if (statusCode === 200) {
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    parseError = String(error && error.message || error);
  }
}
// A well-formed SPARQL JSON Results response always carries head.vars and a
// results.bindings array, even when there are zero matches. Anything else
// (an HTML error page, a partial/cut-off body, a differently-shaped payload)
// is treated as "not a usable response" rather than silently coerced to an
// empty-but-valid result set.
const wellFormed = !!(
  parsed && parsed.head && Array.isArray(parsed.head.vars) &&
  parsed.results && Array.isArray(parsed.results.bindings)
);
const bindings = wellFormed ? parsed.results.bindings : [];
const {clean, conflicted, malformedRowCount} = classifyWikidataRows(bindings);
const fetchOk = statusCode === 200 && wellFormed;
// Content-addressed immutable identity: two runs observing byte-identical
// Wikidata content compute the exact same dataset id and source_release,
// so they idempotently MERGE the same nodes instead of one run's hash
// overwriting another's. Different content -- even fetched the same day --
// gets a different id and never touches a prior snapshot's nodes. Only
// computed on a genuinely successful, hashed fetch; a failed/malformed
// fetch has nothing meaningful to anchor an identity to.
const dateStamp = String(config.retrieved_at || '').slice(0, 10) || 'unknown-date';
const wikidataDatasetId = (fetchOk && hash) ? `wikidata-dataset:taxon-labels:sha256-${hash}` : null;
const sourceRelease = (fetchOk && hash) ? `wikidata-snapshot:${dateStamp}:sha256-${hash.slice(0, 12)}` : null;
return [{json: {
  source_sha256: hash,
  wikidata_dataset_id: wikidataDatasetId,
  source_release: sourceRelease,
  fetch_status_code: statusCode,
  fetch_ok: fetchOk,
  fetch_failure_reason: statusCode !== 200
    ? (upstreamErrorText || `Wikidata SPARQL endpoint returned HTTP ${statusCode}`)
    : (!wellFormed ? (parseError || upstreamErrorText || 'Wikidata SPARQL response was not a well-formed results document') : ''),
  source_binding_count: bindings.length,
  malformed_row_count: malformedRowCount,
  distinct_taxon_name_count: clean.length + new Set(conflicted.map(row => row.taxon_name)).size,
  clean_candidates: clean,
  conflicted_candidates: conflicted,
}}];
"""
)

# Also n8n-global-free: takes the Neo4j resolve node's per-row output.
CLASSIFY_MATCHES_JS = r"""
function classifyMatches(resolvedRows) {
  const writeRows = [];
  const candidates = [];
  let invalidRowCount = 0;
  for (const row of resolvedRows || []) {
    if (!row || typeof row.taxon_name !== 'string' || !row.taxon_name.trim()
        || typeof row.korean_name !== 'string' || !row.korean_name.trim()
        || !Array.isArray(row.qids)) {
      invalidRowCount += 1;
      continue;
    }
    const matchedIds = Array.isArray(row.matched_taxon_ids) ? row.matched_taxon_ids : [];
    if (matchedIds.length === 1) {
      writeRows.push({
        taxon_id: matchedIds[0],
        taxon_name: row.taxon_name,
        korean_name: row.korean_name,
        qids: row.qids,
      });
    } else if (matchedIds.length === 0) {
      candidates.push({
        taxon_name: row.taxon_name,
        korean_name: row.korean_name,
        qids: row.qids,
        reason_code: 'no_matching_avilist_taxon',
      });
    } else {
      candidates.push({
        taxon_name: row.taxon_name,
        korean_name: row.korean_name,
        qids: row.qids,
        reason_code: 'ambiguous_avilist_taxon_match',
      });
    }
  }
  return {writeRows, candidates, invalidRowCount};
}
"""

# Always exactly one row (no UNWIND; every MATCH is OPTIONAL), regardless of
# how many -- if any -- Wikidata candidates were parsed. Kept as a step
# separate from RESOLVE_MATCHES_STATEMENT so state bookkeeping (the active
# concept set) is
# available even when there are zero clean candidates to resolve, instead of
# being smuggled out of resolvedRows[0] (which doesn't exist when there are
# no rows). PostgreSQL supplies the optimistic-concurrency token when the
# run is opened through the internal ingest API.
RESOLVE_MATCHES_STATEMENT = compact_cypher(
    """
    MATCH (concept_set:TaxonConceptSet {id: $concept_set_id})
    WHERE concept_set.version = $taxonomy_release AND concept_set.policy_status = 'allowed'
    WITH concept_set
    UNWIND $clean_candidates AS row
    OPTIONAL MATCH (taxon:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(concept_set)
      WHERE toLower(taxon.scientific_name) = toLower(row.taxon_name)
    WITH concept_set, row, collect(taxon.id) AS matched_taxon_ids
    RETURN concept_set.id AS concept_set_id, concept_set.version AS taxonomy_release,
           row.taxon_name AS taxon_name, row.korean_name AS korean_name,
           row.qids AS qids, matched_taxon_ids
    """
)

ASSEMBLE_GATES_JS = (
    CLASSIFY_MATCHES_JS
    + r"""
function assembleGates(config, normalized, stateInfo, resolvedRows) {
  const {writeRows, candidates, invalidRowCount} = classifyMatches(resolvedRows);
  const allCandidates = [...candidates, ...normalized.conflicted_candidates];
  const reasons = [];
  // Checked first and most specifically: a failed or malformed fetch must
  // never be reported as "zero candidates" -- that phrasing would read as a
  // legitimate empty result (nothing left to do) rather than an outage.
  if (normalized.fetch_ok === false) {
    reasons.push(normalized.fetch_failure_reason || 'Wikidata SPARQL request failed');
  }
  if (normalized.fetch_ok !== false && !normalized.source_sha256) {
    reasons.push('Wikidata response was not hashed');
  }
  // Any structurally malformed row fails the run closed instead of being
  // silently skipped -- it may mean the SPARQL/Wikidata schema changed and
  // the rest of the "clean" rows are not trustworthy either.
  if (normalized.fetch_ok !== false && normalized.malformed_row_count > 0) {
    reasons.push(`${normalized.malformed_row_count} malformed Wikidata row(s) were rejected`);
  }
  if (normalized.fetch_ok !== false && !normalized.malformed_row_count && normalized.distinct_taxon_name_count === 0) {
    reasons.push('No Korean vernacular candidates parsed from the Wikidata response');
  }
  if (!stateInfo.concept_set_id) {
    reasons.push('Active AviList reference-taxonomy concept set is not available');
  }
  if ((normalized.clean_candidates || []).length > 0
      && (invalidRowCount > 0 || writeRows.length + candidates.length !== normalized.clean_candidates.length)) {
    reasons.push('Active taxonomy resolution returned incomplete or malformed rows');
  }
  if (reasons.length === 0 && writeRows.length === 0 && allCandidates.length === 0 && normalized.distinct_taxon_name_count > 0) {
    reasons.push('Korean vernacular candidates were parsed but none resolved to a write row or a candidate');
  }
  return {
    ...config,
    source_sha256: normalized.source_sha256,
    wikidata_dataset_id: normalized.wikidata_dataset_id,
    source_release: normalized.source_release,
    source_binding_count: normalized.source_binding_count,
    malformed_row_count: normalized.malformed_row_count,
    distinct_taxon_name_count: normalized.distinct_taxon_name_count,
    concept_set_id: stateInfo.concept_set_id,
    taxonomy_release: stateInfo.taxonomy_release,
    write_rows: writeRows,
    candidates: allCandidates,
    write_row_count: writeRows.length,
    candidate_count: allCandidates.length,
    ready_to_load: reasons.length === 0,
    failure_reason: reasons.join('; '),
  };
}
"""
)

ASSEMBLE_KOREAN_VERNACULAR_GATES = (
    ASSEMBLE_GATES_JS
    + r"""
const config = $('Build Korean vernacular configuration').first().json;
const normalized = $('Normalize Korean vernacular candidates').first().json;
  const stateResponse = $('Read active PostgreSQL taxonomy state').first().json;
  const stateInfo = {concept_set_id: stateResponse.cursor?.concept_set_id,
    taxonomy_release: stateResponse.cursor?.taxonomy_release};
const resolvedRows = $input.all().map(item => item.json);
return [{json: assembleGates(config, normalized, stateInfo, resolvedRows)}];
"""
)

# `$wikidata_dataset_id` is content-addressed (see NORMALIZE_WIKIDATA), so
# folding it into the VernacularName id makes every snapshot's graph writes
# immutable and idempotent. Source records, the run ledger, quarantine, and
# activation state are written only through the PostgreSQL control API.
# Re-checking
# `state.active_concept_set_id = $concept_set_id` on every batch (not just
# at Start) means even a taxonomy switch mid-run stops matching further
# taxa. The NAS community Neo4j node evaluates its query once for the first
# input item, so a Loop Over Items node explicitly feeds it one logical
# batch at a time and collects all count rows for `VERIFY_BATCHES`.
BATCH_STATEMENT = compact_cypher(
    """
    MATCH (concept_set:TaxonConceptSet {id: $concept_set_id})
    WHERE concept_set.version = $taxonomy_release AND concept_set.policy_status = 'allowed'
    CALL {
      WITH concept_set
      UNWIND $rows AS row
      MATCH (taxon:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(concept_set) WHERE taxon.id = row.taxon_id
      MERGE (vernacular:VernacularName {id: row.taxon_id + ':vernacular:ko:wikidata:' + $wikidata_dataset_id})
      SET vernacular.name = row.korean_name, vernacular.language = 'ko',
          vernacular.status = 'community-sourced', vernacular.dataset_id = $wikidata_dataset_id,
          vernacular.policy_status = 'allowed',
          vernacular.source_scientific_name_claim = row.taxon_name,
          vernacular.source_qids = row.qids, vernacular.source_release = $source_release,
          vernacular.source_record_ids = [qid IN row.qids | 'wikidata-record:' + qid + ':' + $wikidata_dataset_id],
          vernacular.retrieved_at = $retrieved_at
      MERGE (taxon)-[:HAS_VERNACULAR_NAME]->(vernacular)
      RETURN count(DISTINCT vernacular) AS loaded_vernacular_names
    }
    CALL {
      UNWIND $candidates AS row
      MERGE (candidate:VernacularNameCandidate {
        id: 'ko-vernacular-candidate:wikidata:' + row.reason_code + ':' + coalesce(row.qids[0], row.taxon_name) + ':' + $wikidata_dataset_id
      })
      SET candidate.taxon_name = row.taxon_name, candidate.proposed_name = row.korean_name,
          candidate.reason_code = row.reason_code, candidate.qids = row.qids,
          candidate.resolution_status = 'open', candidate.last_seen_run_id = $run_id,
          candidate.last_seen_at = $retrieved_at,
          candidate.dataset_id = $wikidata_dataset_id,
          candidate.source_record_ids = [qid IN row.qids | 'wikidata-record:' + qid + ':' + $wikidata_dataset_id]
      RETURN count(DISTINCT candidate) AS loaded_candidates
    }
    RETURN $batch_index AS batch_index, $batch_count AS batch_count,
           loaded_vernacular_names, loaded_candidates
    """
)

# Final graph verification is read-only. PostgreSQL performs the atomic
# optimistic activation after this query proves the reference taxonomy has
# not switched and the complete domain snapshot is present.
VERIFY_GRAPH_STATEMENT = compact_cypher(
    """
    MATCH (conceptSet:TaxonConceptSet {id: $concept_set_id})
    WHERE conceptSet.version = $taxonomy_release AND conceptSet.policy_status = 'allowed'
    OPTIONAL MATCH (vernacular:VernacularName {language: 'ko', dataset_id: $wikidata_dataset_id})
    WITH conceptSet, count(vernacular) AS graphVernacularNames
    OPTIONAL MATCH (candidate:VernacularNameCandidate {dataset_id: $wikidata_dataset_id})
    RETURN conceptSet.id AS concept_set_id,
           graphVernacularNames AS graph_vernacular_names,
           count(candidate) AS graph_candidates
    """
)


def prepare_batches_js(source_var: str) -> str:
    return dedent(
        f"""
        const source = $('{source_var}').first().json;
        const batches = [];
        for (let offset = 0; offset < source.write_rows.length; offset += source.batch_size) {{
          batches.push({{rows: source.write_rows.slice(offset, offset + source.batch_size), candidates: []}});
        }}
        for (let offset = 0; offset < source.candidates.length; offset += source.batch_size) {{
          batches.push({{rows: [], candidates: source.candidates.slice(offset, offset + source.batch_size)}});
        }}
        if (batches.length === 0) batches.push({{rows: [], candidates: []}});
        return batches.map((batch, index) => ({{json: {{
          run_id: source.run_id,
          retrieved_at: source.retrieved_at,
          source_release: source.source_release,
          wikidata_dataset_id: source.wikidata_dataset_id,
          concept_set_id: source.concept_set_id,
          source_sha256: source.source_sha256,
          expected_state_version: source.expected_state_version,
          batch_index: index,
          batch_count: batches.length,
          ...batch,
        }}}}));
        """
    ).strip()


PREPARE_BEGIN_REQUEST = r"""
const source = $input.first().json;
return [{json: {...source, ingest_request: {
  dataset: {
    id: source.wikidata_dataset_id,
    source_id: 'wikidata',
    name: 'Wikidata Korean bird labels',
    provider: 'Wikimedia Foundation / Wikidata community',
    landing_uri: source.wikidata_landing_uri,
    release_strategy: 'dated_snapshot',
    policy_status: 'allowed',
    metadata: {license_uri: source.wikidata_license_uri, taxonomy_release: source.taxonomy_release},
  },
  release: {
    id: source.source_release,
    release_key: source.source_release,
    retrieved_at: source.retrieved_at,
    content_sha256: source.source_sha256,
    raw_object_uri: source.sparql_endpoint,
    metadata: {taxonomy_release: source.taxonomy_release, concept_set_id: source.concept_set_id},
  },
  run: {
    id: source.run_id,
    pipeline_id: source.pipeline_id,
    started_at: source.retrieved_at,
    manifest: {
      orchestrator: 'n8n',
      workflow: 'korean-vernacular-wikidata',
      expected_write_rows: source.write_row_count,
      expected_candidates: source.candidate_count,
    },
  },
}}}];
"""


VERIFY_START = r"""
const expected = $('Prepare PostgreSQL ingestion run').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const stateVersion = response.state_version;
const startOk = !errorText && response.status === 'started'
  && typeof stateVersion === 'number' && Number.isSafeInteger(stateVersion) && stateVersion >= 0;
return [{json: {...expected, expected_state_version: stateVersion, start_ok: startOk,
  failure_reason: startOk ? '' : (errorText || 'PostgreSQL did not start the ingestion run')}}];
"""


PREPARE_APPEND_REQUEST = r"""
const batch = $input.first().json;
const qids = new Set();
for (const row of [...batch.rows, ...batch.candidates]) {
  for (const qid of row.qids || []) qids.add(qid);
}
const records = [...qids].sort().map(qid => ({
  id: `wikidata-record:${qid}:${batch.wikidata_dataset_id}`,
  external_id: qid,
  record_type: 'taxon_label',
  raw_object_uri: `https://www.wikidata.org/entity/${qid}`,
  raw_sha256: batch.source_sha256,
  retrieved_at: batch.retrieved_at,
  parser_version: 'korean-vernacular-v2',
  license_policy_status: 'allowed',
  payload: {qid, source_release: batch.source_release, snapshot_sha256: batch.source_sha256},
}));
const quarantine_items = batch.candidates.map(row => ({
  record_key: `${row.reason_code}:${(row.qids || []).join('+') || 'no-qid'}:${encodeURIComponent(row.korean_name || '')}`.slice(0, 200),
  stage: 'resolve',
  reason_code: row.reason_code,
  severity: 'warning',
  rule_version: 'korean-vernacular-v2',
  raw_value_redacted: {qids: row.qids || [], taxon_name: row.taxon_name, proposed_name: row.korean_name},
}));
return [{json: {...batch, ingest_request: {records, quarantine_items}}}];
"""


VERIFY_APPEND = r"""
const batch = $('Prepare PostgreSQL source batch').item.json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const appendOk = !errorText && response.status === 'appended';
return [{json: {...batch, append_ok: appendOk,
  failure_reason: appendOk ? '' : (errorText || 'PostgreSQL did not append the source batch')}}];
"""

VERIFY_BATCHES = r"""
const expected = $('Verify PostgreSQL ingestion run started').first().json;
const rows = $input.all().map(item => item.json);
const errors = rows.map(row => String(row.error?.message || row.error || row.message || '')).filter(Boolean);
// The NAS community Neo4j node serializes Cypher integer return values as
// strings. Accept only a canonical unsigned decimal spelling (or a native
// safe integer), then normalize every returned count/index before checking
// batch completeness. Number(...) alone would incorrectly accept whitespace,
// signs, decimals, exponents and booleans.
const normalizeNonNegativeSafeInteger = value => {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  if (typeof value !== 'string' || !/^(?:0|[1-9][0-9]*)$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
};
const normalizedRows = rows.map(row => ({
  row,
  batchIndex: normalizeNonNegativeSafeInteger(row?.batch_index),
  batchCount: normalizeNonNegativeSafeInteger(row?.batch_count),
  loadedVernacularNames: normalizeNonNegativeSafeInteger(row?.loaded_vernacular_names),
  loadedCandidates: normalizeNonNegativeSafeInteger(row?.loaded_candidates),
}));
const batchCount = normalizedRows.length && normalizedRows[0].batchCount !== null
  ? normalizedRows[0].batchCount
  : 0;
const validBatchRows = batchCount > 0 && normalizedRows.every(value =>
  value.row && typeof value.row === 'object'
  && value.batchCount === batchCount
  && value.batchIndex !== null && value.batchIndex < batchCount
  && value.loadedVernacularNames !== null
  && value.loadedCandidates !== null
);
const indexes = new Set(validBatchRows ? normalizedRows.map(value => value.batchIndex) : []);
const loadedVernacularNames = validBatchRows
  ? normalizedRows.reduce((sum, value) => sum + value.loadedVernacularNames, 0)
  : 0;
const loadedCandidates = validBatchRows
  ? normalizedRows.reduce((sum, value) => sum + value.loadedCandidates, 0)
  : 0;
const loadOk = !errors.length && validBatchRows && indexes.size === batchCount && rows.length === batchCount
  && loadedVernacularNames === expected.write_row_count
  && loadedCandidates === expected.candidate_count;
return [{json: {...expected,
  load_ok: loadOk,
  loaded_vernacular_names: loadedVernacularNames,
  loaded_candidates: loadedCandidates,
  failure_reason: loadOk ? '' : (errors.join('; ') || 'Korean vernacular batch counts did not match')
}}];
"""

VERIFY_GRAPH = r"""
const expected = $('Verify Korean vernacular batches').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || '');
// The Neo4j community node serializes Cypher integer return values as strings.
// Keep this parser as strict as VERIFY_BATCHES: accept only native non-negative
// safe integers or canonical unsigned decimal strings. In particular, do not
// coerce whitespace, signs, decimals, exponents, booleans, or overflow.
const normalizeNonNegativeSafeInteger = value => {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  if (typeof value !== 'string' || !/^(?:0|[1-9][0-9]*)$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
};
const graphVernacularNames = normalizeNonNegativeSafeInteger(response.graph_vernacular_names);
const graphCandidates = normalizeNonNegativeSafeInteger(response.graph_candidates);
const graphOk = !errorText
  && response.concept_set_id === expected.concept_set_id
  && graphVernacularNames !== null
  && graphCandidates !== null
  && graphVernacularNames === expected.loaded_vernacular_names
  && graphCandidates === expected.loaded_candidates;
return [{json: {...expected, graph_ok: graphOk,
  failure_reason: graphOk ? '' : (errorText || 'Neo4j domain snapshot verification failed')}}];
"""

PREPARE_FINALIZE_REQUEST = r"""
const source = $input.first().json;
const qids = new Set([...source.write_rows, ...source.candidates].flatMap(row => row.qids || []));
return [{json: {...source, ingest_request: {
  counts: {
    source_bindings: source.source_binding_count,
    source_records: qids.size,
    vernacular_names: source.loaded_vernacular_names,
    quarantine_items: source.loaded_candidates,
  },
  cursor: {source_release: source.source_release, dataset_id: source.wikidata_dataset_id},
  expected_state_version: source.expected_state_version,
}}}];
"""

# `expected` is read from 'Verify Korean vernacular batches', not 'Assemble
# Korean vernacular quality gates': the latter never carries
# loaded_vernacular_names/loaded_candidates at all -- those are only
# computed by VERIFY_BATCHES, further down the chain -- so reading it here
# would leave both fields `undefined` in every real Finalize success, with
# nothing downstream (the success Discord message, or
# manage_n8n_korean_vernacular.py's execution-evidence check) able to tell
# a meaningful run apart from an empty one. 'Verify Korean vernacular
# batches' already carries everything: it itself spreads `...expected` from
# Assemble (so run_id/source_release/wikidata_dataset_id are still present)
# plus its own correct loaded_vernacular_names/loaded_candidates, and 'Korean
# vernacular load verified?' (the IF between it and Finalize) passes items
# through unchanged.
VERIFY_FINALIZE = r"""
const expected = $('Prepare PostgreSQL finalization').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const finalizeOk = !errorText
  && response.status === 'finalized'
  && response.state_version === expected.expected_state_version + 1;
return [{json: {...expected,
  finalize_ok: finalizeOk,
  loaded_vernacular_names: expected.loaded_vernacular_names,
  loaded_candidates: expected.loaded_candidates,
  failure_reason: finalizeOk ? '' : (errorText ||
    'PostgreSQL activation was refused because a concurrent run advanced the state version')
}}];
"""

# A plain passthrough, but under a name every failure branch can be read
# back from by identity. All four failure branches (quality gates, Start,
# batch load, Finalize) converge here before 'Mark Korean vernacular run
# failed' wipes $json down to that Neo4j write's own return columns (same
# reason every VERIFY_* step above re-merges with a named upstream lookup).
# Reading a *fixed* node name (rather than $input) is what lets
# RECORD_FAILURE_JS recover the right context afterwards regardless of
# which of the four branches actually failed -- each carries its own
# failure_reason (from 'Assemble Korean vernacular quality gates' itself
# for a pre-Start failure, or from the relevant VERIFY_* step for a
# batch/Finalize failure), and this node is the one stable place to name.
CAPTURE_FAILURE_CONTEXT_JS = r"""
return [{json: $input.first().json}];
"""

# `...expected` is spread *first* so MARK_FAILED_STATEMENT's own return
# columns never clobber `expected.failure_reason`. `expected` is read from
# 'Capture Korean vernacular failure context', not 'Assemble Korean
# vernacular quality gates': the latter's own failure_reason is only ever
# non-empty for a pre-Start (quality-gates) failure -- for a batch or
# Finalize failure it is still '' (quality gates passed, that is why Start
# ran at all), so reading it directly here would silently report "Unknown
# failure" downstream instead of the real, later-computed reason.
# `run_marked_failed` is purely observational (true only when a 'loading'
# run existed and was just flipped to 'failed'); nothing downstream
# branches on it, so a quality-gates-before-Start failure (where no run
# exists to mark) still reaches the same notification/stop path.
RECORD_FAILURE_JS = r"""
const expected = $('Capture Korean vernacular failure context').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const runMarkedFailed = !errorText
  && response.status === 'failed';
return [{json: {...expected, run_marked_failed: runMarkedFailed}}];
"""


def ingest_api_node(
    name: str, path_expression: str, position: tuple[int, int], *, method: str = "POST"
) -> dict[str, object]:
    """Build an authenticated internal control-plane request without embedding secrets."""

    return node(
        name,
        "n8n-nodes-base.httpRequest",
        4.4,
        {
            "method": method,
            "url": f"={{{{ $env.ROBINGRAPH_INGEST_API_URL + {path_expression} }}}}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "={{ 'Bearer ' + $env.ROBINGRAPH_INGEST_INTERNAL_TOKEN }}",
                    }
                ]
            },
            "sendBody": method != "GET",
            # n8n HTTP Request 4.4 forces `useStream: true` for raw bodies,
            # even when Response Format is JSON.  Use its native JSON-body
            # mode so it serializes the object and parses FastAPI's JSON
            # response before handing it to the verification Code node.
            "contentType": "json",
            "specifyBody": "json",
            "jsonBody": "={{ $json.ingest_request }}",
            "options": {"response": {"response": {"neverError": True, "responseFormat": "json"}}},
        },
        position,
        onError="continueRegularOutput",
        retryOnFail=True,
        maxTries=3,
        waitBetweenTries=2000,
        notes=(
            "Calls the private PostgreSQL ingest API. Base URL and bearer token are read from "
            "n8n environment variables; no credential value is stored in this workflow."
        ),
    )


def main() -> None:
    point = load_wikidata_collection_point()
    build_config = build_configuration_js(point)

    resolve_matches = neo4j_node(
        "Resolve active concept set and match candidates", RESOLVE_MATCHES_STATEMENT, (760, -180)
    )
    resolve_matches["alwaysOutputData"] = True

    nodes: list[dict[str, object]] = [
        node("Manual Trigger", "n8n-nodes-base.manualTrigger", 1, {}, (-1160, -80)),
        node(
            "Schedule Trigger — 1st of month 04:00 KST",
            "n8n-nodes-base.scheduleTrigger",
            1.2,
            {"rule": {"interval": [{"field": "cronExpression", "expression": "0 4 1 * *"}]}},
            (-1160, 80),
        ),
        code(
            "Build Korean vernacular configuration",
            build_config,
            (-940, 0),
            notes=(
                "Generated from the enabled, allowed korean-vernacular-wikidata-species-labels "
                "collection point. Re-generate after changing config/collection-points.json."
            ),
        ),
        node(
            "Fetch Wikidata Korean bird labels",
            "n8n-nodes-base.httpRequest",
            4.4,
            {
                "url": "={{ $json.sparql_endpoint }}",
                "sendQuery": True,
                "queryParameters": {
                    "parameters": [
                        {"name": "query", "value": "={{ $json.sparql_query }}"},
                        {"name": "format", "value": "json"},
                    ]
                },
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Accept", "value": "application/sparql-results+json"},
                        {
                            "name": "User-Agent",
                            "value": "RobinGraph-korean-vernacular-ingest/1.0 (https://github.com/; contact via project maintainer)",
                        },
                    ]
                },
                "options": {
                    "response": {
                        "response": {"fullResponse": True, "neverError": True, "responseFormat": "text"}
                    },
                    "timeout": 120000,
                },
            },
            (-700, 0),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
            onError="continueRegularOutput",
        ),
        node(
            "Hash Wikidata response",
            "n8n-nodes-base.crypto",
            2,
            {
                "action": "hash",
                "binaryData": False,
                "type": "SHA256",
                # `?? ''`, not `$json.data` directly: 'Fetch Wikidata Korean
                # bird labels' has neverError + onError: continueRegularOutput
                # (see module docstring), so a connection-level failure hands
                # this node an item with an `error` field and no `data` at
                # all. Hashing `undefined` would throw here -- one node past
                # where the resilience was added -- and abort the execution
                # before Normalize/Notify ever see it. The Crypto node passes
                # every existing json field through untouched alongside the
                # computed hash, so `error` (and the missing `statusCode`)
                # still reach 'Normalize Korean vernacular candidates' intact.
                "value": "={{ $json.data ?? '' }}",
                "dataPropertyName": "raw_sha256",
                "encoding": "hex",
            },
            (-460, 0),
        ),
        ingest_api_node(
            "Read active PostgreSQL taxonomy state",
            "'/internal/v1/ingest/active/reference-taxonomy-traits'",
            (-340, 0),
            method="GET",
        ),
        code("Normalize Korean vernacular candidates", NORMALIZE_WIKIDATA, (-220, 0)),
        code(
            "Attach active taxonomy context",
            "const source=$input.first().json,state=$('Read active PostgreSQL taxonomy state').first().json; "
            "return [{json:{...source,concept_set_id:state.cursor?.concept_set_id,taxonomy_release:state.cursor?.taxonomy_release}}];",
            (20, 0),
        ),
        resolve_matches,
        code("Assemble Korean vernacular quality gates", ASSEMBLE_KOREAN_VERNACULAR_GATES, (1000, 0)),
        boolean_if("Korean vernacular quality gates passed?", "={{ $json.ready_to_load }}", (1240, 0)),
        code("Prepare PostgreSQL ingestion run", PREPARE_BEGIN_REQUEST, (1480, -180)),
        ingest_api_node(
            "Start PostgreSQL ingestion run", "'/internal/v1/ingest/begin'", (1720, -180)
        ),
        code("Verify PostgreSQL ingestion run started", VERIFY_START, (1960, -180)),
        boolean_if("PostgreSQL ingestion run started?", "={{ $json.start_ok }}", (2200, -180)),
        code(
            "Prepare Korean vernacular batches",
            prepare_batches_js("Verify PostgreSQL ingestion run started"),
            (2440, -180),
        ),
        node(
            "Loop Over Korean vernacular batches",
            "n8n-nodes-base.splitInBatches",
            3,
            {"batchSize": 1, "options": {}},
            (2680, -180),
        ),
        code("Prepare PostgreSQL source batch", PREPARE_APPEND_REQUEST, (2920, -180)),
        ingest_api_node(
            "Append PostgreSQL source batch",
            "('/internal/v1/ingest/' + $json.run_id + '/append')",
            (3160, -180),
        ),
        code("Verify PostgreSQL source batch appended", VERIFY_APPEND, (3400, -180)),
        boolean_if("PostgreSQL source batch appended?", "={{ $json.append_ok }}", (3640, -180)),
        neo4j_node("Upsert Korean vernacular names batch", BATCH_STATEMENT, (3880, -180)),
        code("Verify Korean vernacular batches", VERIFY_BATCHES, (4120, -180)),
        boolean_if("Korean vernacular load verified?", "={{ $json.load_ok }}", (4360, -180)),
        neo4j_node("Verify Korean vernacular graph snapshot", VERIFY_GRAPH_STATEMENT, (4600, -180)),
        code("Check Korean vernacular graph snapshot", VERIFY_GRAPH, (4840, -180)),
        boolean_if("Korean vernacular graph verified?", "={{ $json.graph_ok }}", (5080, -180)),
        code("Prepare PostgreSQL finalization", PREPARE_FINALIZE_REQUEST, (5320, -180)),
        ingest_api_node(
            "Finalize PostgreSQL ingestion run",
            "('/internal/v1/ingest/' + $json.run_id + '/finalize')",
            (5560, -180),
        ),
        code("Verify Korean vernacular release finalized", VERIFY_FINALIZE, (5800, -180)),
        boolean_if("Korean vernacular release finalized?", "={{ $json.finalize_ok }}", (6040, -180)),
        # Discord nodes, like `generate_n8n_reference_ingest.py`'s "Notify
        # reference *" pair: `discord()` sets `onError: continueRegularOutput`,
        # so a workflow whose Discord credential is not (yet) wired -- this
        # pipeline's notifications are optional, see
        # `docs/n8n/korean-vernacular-ingest.md` -- fails that single node
        # and keeps going, instead of aborting the whole run. `deploy_n8n_reference_ingest.build_deployment`
        # only requires a Discord credential to be *available* when this
        # workflow is deployed with `discord_required=True`; the
        # korean-vernacular deploy path passes `discord_required=False`.
        discord(
            "Notify Korean vernacular success",
            "={{ '✅ **RobinGraph Korean vernacular-name ingest succeeded**\\nRun: ' + $json.run_id + "
            "'\\nVernacularName nodes: ' + $json.loaded_vernacular_names + ', review candidates: ' + "
            "$json.loaded_candidates + '\\nActive reference-taxonomy release: ' + $json.taxonomy_release + "
            "'\\nActive Wikidata dataset: ' + $json.wikidata_dataset_id }}",
            (6280, -280),
        ),
        code("Capture Korean vernacular failure context", CAPTURE_FAILURE_CONTEXT_JS, (1720, 220)),
        code(
            "Prepare PostgreSQL run failure",
            "return [{json: {...$input.first().json, ingest_request: {reason: String($input.first().json.failure_reason || 'Unknown failure').slice(0, 4000)}}}];",
            (1960, 220),
        ),
        ingest_api_node(
            "Mark PostgreSQL ingestion run failed",
            "('/internal/v1/ingest/' + $json.run_id + '/fail')",
            (2200, 220),
        ),
        code("Record Korean vernacular run failure", RECORD_FAILURE_JS, (2440, 220)),
        discord(
            "Notify Korean vernacular failure",
            "={{ '❌ **RobinGraph Korean vernacular-name ingest blocked or failed**\\nRun: ' + "
            "String($json.run_id || 'not-started') + '\\nReason: ' + "
            "String($json.failure_reason || 'Unknown failure').slice(0, 1500) + "
            # A separate signal from the failure reason itself: this Discord
            # node's own onError: continueRegularOutput means it still fires
            # even if 'Mark PostgreSQL ingestion run failed' could not reach
            # the control API at all (DB/API down, not just the original failure).
            # An operator seeing 'not recorded' here knows the IngestionRun
            # may still show 'loading' in PostgreSQL and needs a manual look,
            # instead of assuming the failure was already durably bookkept.
            "'\\nRun bookkeeping: ' + ($json.run_marked_failed "
            "? 'marked failed in PostgreSQL' "
            ": 'not recorded in PostgreSQL (no run was loading, or the bookkeeping request itself failed)') }}",
            (2680, 220),
        ),
        node(
            "Fail Korean vernacular execution",
            "n8n-nodes-base.stopAndError",
            1,
            {
                "errorMessage": (
                    "RobinGraph Korean vernacular-name ingest failed; inspect the preceding "
                    "quality or Neo4j verification node."
                )
            },
            (2920, 220),
        ),
        node("Korean vernacular ingest finished", "n8n-nodes-base.noOp", 1, {}, (6520, -180)),
    ]

    connections = {
        "Manual Trigger": {"main": [[edge("Build Korean vernacular configuration")]]},
        "Schedule Trigger — 1st of month 04:00 KST": {
            "main": [[edge("Build Korean vernacular configuration")]]
        },
        "Build Korean vernacular configuration": {"main": [[edge("Fetch Wikidata Korean bird labels")]]},
        "Fetch Wikidata Korean bird labels": {"main": [[edge("Hash Wikidata response")]]},
        "Hash Wikidata response": {"main": [[edge("Read active PostgreSQL taxonomy state")]]},
        "Read active PostgreSQL taxonomy state": {
            "main": [[edge("Normalize Korean vernacular candidates")]]
        },
        "Normalize Korean vernacular candidates": {
            "main": [[edge("Attach active taxonomy context")]]
        },
        "Attach active taxonomy context": {
            "main": [[edge("Resolve active concept set and match candidates")]]
        },
        "Resolve active concept set and match candidates": {
            "main": [[edge("Assemble Korean vernacular quality gates")]]
        },
        "Assemble Korean vernacular quality gates": {
            "main": [[edge("Korean vernacular quality gates passed?")]]
        },
        "Korean vernacular quality gates passed?": {
            "main": [
                [edge("Prepare PostgreSQL ingestion run")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Prepare PostgreSQL ingestion run": {"main": [[edge("Start PostgreSQL ingestion run")]]},
        "Start PostgreSQL ingestion run": {"main": [[edge("Verify PostgreSQL ingestion run started")]]},
        "Verify PostgreSQL ingestion run started": {
            "main": [[edge("PostgreSQL ingestion run started?")]]
        },
        "PostgreSQL ingestion run started?": {
            "main": [
                [edge("Prepare Korean vernacular batches")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Prepare Korean vernacular batches": {
            "main": [[edge("Loop Over Korean vernacular batches")]]
        },
        "Loop Over Korean vernacular batches": {
            "main": [
                # n8n 2.15 splitInBatches output 0 fires after every item has
                # returned to this node; output 1 carries the current loop item.
                # Sending these the other way round verifies before any
                # write and can leave every batch unprocessed.
                [edge("Verify Korean vernacular batches")],
                [edge("Prepare PostgreSQL source batch")],
            ]
        },
        "Prepare PostgreSQL source batch": {"main": [[edge("Append PostgreSQL source batch")]]},
        "Append PostgreSQL source batch": {
            "main": [[edge("Verify PostgreSQL source batch appended")]]
        },
        "Verify PostgreSQL source batch appended": {
            "main": [[edge("PostgreSQL source batch appended?")]]
        },
        "PostgreSQL source batch appended?": {
            "main": [
                [edge("Upsert Korean vernacular names batch")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Upsert Korean vernacular names batch": {
            "main": [[edge("Loop Over Korean vernacular batches")]]
        },
        "Verify Korean vernacular batches": {"main": [[edge("Korean vernacular load verified?")]]},
        "Korean vernacular load verified?": {
            "main": [
                [edge("Verify Korean vernacular graph snapshot")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Verify Korean vernacular graph snapshot": {
            "main": [[edge("Check Korean vernacular graph snapshot")]]
        },
        "Check Korean vernacular graph snapshot": {
            "main": [[edge("Korean vernacular graph verified?")]]
        },
        "Korean vernacular graph verified?": {
            "main": [
                [edge("Prepare PostgreSQL finalization")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Prepare PostgreSQL finalization": {
            "main": [[edge("Finalize PostgreSQL ingestion run")]]
        },
        "Finalize PostgreSQL ingestion run": {
            "main": [[edge("Verify Korean vernacular release finalized")]]
        },
        "Verify Korean vernacular release finalized": {
            "main": [[edge("Korean vernacular release finalized?")]]
        },
        "Korean vernacular release finalized?": {
            "main": [
                [edge("Notify Korean vernacular success")],
                [edge("Capture Korean vernacular failure context")],
            ]
        },
        "Notify Korean vernacular success": {"main": [[edge("Korean vernacular ingest finished")]]},
        "Capture Korean vernacular failure context": {
            "main": [[edge("Prepare PostgreSQL run failure")]]
        },
        "Prepare PostgreSQL run failure": {
            "main": [[edge("Mark PostgreSQL ingestion run failed")]]
        },
        "Mark PostgreSQL ingestion run failed": {
            "main": [[edge("Record Korean vernacular run failure")]]
        },
        "Record Korean vernacular run failure": {"main": [[edge("Notify Korean vernacular failure")]]},
        "Notify Korean vernacular failure": {"main": [[edge("Fail Korean vernacular execution")]]},
    }

    schema_names: list[str] = []
    for index, label in enumerate(KOREAN_VERNACULAR_LABELS):
        name = f"Ensure {label} ID constraint"
        schema_names.append(name)
        item = neo4j_node(
            name,
            f"CREATE CONSTRAINT robingraph_korean_vernacular_{label.lower()}_id IF NOT EXISTS "
            f"FOR (node:{label}) REQUIRE node.id IS UNIQUE",
            (-1380 + (index % 4) * 260, -420 + (index // 4) * 170),
        )
        item["onError"] = "stopWorkflow"
        nodes.append(item)
    for trigger in ("Manual Trigger", "Schedule Trigger — 1st of month 04:00 KST"):
        connections[trigger] = {"main": [[edge(schema_names[0])]]}
    for index, name in enumerate(schema_names):
        next_name = (
            schema_names[index + 1]
            if index + 1 < len(schema_names)
            else "Build Korean vernacular configuration"
        )
        connections[name] = {"main": [[edge(next_name)]]}

    workflow = {
        "id": node_id("korean-vernacular-workflow-id"),
        "name": "RobinGraph — Korean vernacular-name ingest from Wikidata (inactive until verified)",
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Asia/Seoul",
            "saveManualExecutions": True,
            "saveExecutionProgress": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "none",
            "callerPolicy": "workflowsFromSameOwner",
            "concurrency": 1,
        },
        "versionId": node_id("korean-vernacular-workflow-version-v1"),
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
