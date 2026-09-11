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
    "SourceRecord",
    "SourceDataset",
    "License",
    "IngestionRun",
    "IngestState",
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
    ? `Wikidata SPARQL endpoint returned HTTP ${statusCode}`
    : (!wellFormed ? (parseError || 'Wikidata SPARQL response was not a well-formed results document') : ''),
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
  for (const row of resolvedRows || []) {
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
  return {writeRows, candidates};
}
"""

# Always exactly one row (no UNWIND; every MATCH is OPTIONAL), regardless of
# how many -- if any -- Wikidata candidates were parsed. Kept as a step
# separate from RESOLVE_MATCHES_STATEMENT so state bookkeeping (the active
# concept set, and the optimistic-concurrency token for Finalize) is
# available even when there are zero clean candidates to resolve, instead of
# being smuggled out of resolvedRows[0] (which doesn't exist when there are
# no rows). `expected_prior_run_id` defaults to '' (never null) so Finalize's
# `WHERE currentRunId = $expected_prior_run_id` guard has a stable, coalesced
# value to compare against on both sides.
READ_STATE_STATEMENT = compact_cypher(
    """
    OPTIONAL MATCH (taxState:IngestState {id: 'reference-taxonomy'})
    OPTIONAL MATCH (conceptSet:TaxonConceptSet {id: taxState.active_concept_set_id})
    OPTIONAL MATCH (koreanState:IngestState {id: 'korean-vernacular-names'})
    RETURN conceptSet.id AS concept_set_id, taxState.active_release AS taxonomy_release,
           coalesce(koreanState.last_successful_run_id, '') AS expected_prior_run_id
    """
)

RESOLVE_MATCHES_STATEMENT = compact_cypher(
    """
    MATCH (state:IngestState {id: 'reference-taxonomy'})
    MATCH (concept_set:TaxonConceptSet {id: state.active_concept_set_id})
    WITH concept_set, state
    UNWIND $clean_candidates AS row
    OPTIONAL MATCH (taxon:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(concept_set)
      WHERE toLower(taxon.scientific_name) = toLower(row.taxon_name)
    WITH concept_set, state, row, collect(taxon.id) AS matched_taxon_ids
    RETURN concept_set.id AS concept_set_id, state.active_release AS taxonomy_release,
           row.taxon_name AS taxon_name, row.korean_name AS korean_name,
           row.qids AS qids, matched_taxon_ids
    """
)

ASSEMBLE_GATES_JS = (
    CLASSIFY_MATCHES_JS
    + r"""
function assembleGates(config, normalized, stateInfo, resolvedRows) {
  const {writeRows, candidates} = classifyMatches(resolvedRows);
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
    expected_prior_run_id: stateInfo.expected_prior_run_id,
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
const stateInfo = $('Read active taxonomy and Korean dataset state').first().json;
const resolvedRows = $input.all().map(item => item.json);
return [{json: assembleGates(config, normalized, stateInfo, resolvedRows)}];
"""
)

# Re-affirms `state.active_concept_set_id = $concept_set_id` (captured at
# resolve time) rather than trusting that value blindly: if the
# reference-taxonomy AviList pipeline flipped its active concept set in the
# window between resolve and start, this MATCH's WHERE fails, the whole
# query returns zero rows, and no IngestionRun/SourceDataset/License is ever
# created for a run that would otherwise write against a taxonomy
# generation that is no longer current.
START_STATEMENT = compact_cypher(
    """
    MATCH (state:IngestState {id: 'reference-taxonomy'}) WHERE state.active_concept_set_id = $concept_set_id
    MATCH (concept_set:TaxonConceptSet {id: $concept_set_id})
    MERGE (run:IngestionRun {id: $run_id})
    SET run.pipeline_id = $pipeline_id, run.started_at = $retrieved_at,
        run.status = 'loading', run.source_release = $source_release,
        run.wikidata_dataset_id = $wikidata_dataset_id,
        run.source_sha256 = $source_sha256, run.taxonomy_release = $taxonomy_release,
        run.expected_write_rows = $write_row_count, run.expected_candidates = $candidate_count
    MERGE (dataset:SourceDataset {id: $wikidata_dataset_id})
    SET dataset.name = 'Wikidata taxon labels', dataset.provider = 'Wikimedia Foundation / Wikidata community',
        dataset.version = $source_release, dataset.landing_uri = $wikidata_landing_uri,
        dataset.snapshot_uri = $sparql_endpoint, dataset.snapshot_sha256 = $source_sha256,
        dataset.policy_status = 'allowed'
    MERGE (license:License {id: $wikidata_license_uri})
    SET license.license_uri = $wikidata_license_uri, license.policy_status = 'allowed'
    MERGE (dataset)-[:LICENSED_UNDER]->(license)
    RETURN run.id AS started_run_id, run.status AS run_status
    """
)

# `$wikidata_dataset_id` is content-addressed (see NORMALIZE_WIKIDATA), so
# folding it into both the VernacularName id and the SourceRecord id makes
# every snapshot's writes their own immutable nodes: re-running against
# identical content MERGEs the same nodes (idempotent), while different
# content never overwrites a prior snapshot's hash in place. All of a row's
# `qids` get their own SourceRecord (not just qids[0]), so provenance is
# never dropped for a name asserted by more than one Wikidata item. The
# `HAS_VERNACULAR_NAME` edge is created immediately as each batch commits,
# but stays invisible to reads until Finalize activates this dataset id in
# `IngestState {id: 'korean-vernacular-names'}.active_dataset_id` -- writes
# are staged-by-construction, not by any separate staging label. Re-checking
# `state.active_concept_set_id = $concept_set_id` on every batch (not just
# at Start) means even a taxonomy switch mid-run stops matching further
# taxa; the pre-existing count verification in `VERIFY_BATCHES` (comparing
# totals against `write_row_count`/`candidate_count`) already catches the
# resulting shortfall and fails the run closed.
BATCH_STATEMENT = compact_cypher(
    """
    MATCH (run:IngestionRun {id: $run_id}) WHERE run.status = 'loading'
    MATCH (state:IngestState {id: 'reference-taxonomy'}) WHERE state.active_concept_set_id = $concept_set_id
    MATCH (dataset:SourceDataset {id: $wikidata_dataset_id})
    MATCH (concept_set:TaxonConceptSet {id: $concept_set_id})
    CALL {
      WITH run, dataset, concept_set
      UNWIND $rows AS row
      MATCH (taxon:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(concept_set) WHERE taxon.id = row.taxon_id
      MERGE (vernacular:VernacularName {id: row.taxon_id + ':vernacular:ko:wikidata:' + $wikidata_dataset_id})
      SET vernacular.name = row.korean_name, vernacular.language = 'ko',
          vernacular.status = 'community-sourced', vernacular.dataset_id = $wikidata_dataset_id,
          vernacular.source_scientific_name_claim = row.taxon_name,
          vernacular.source_qids = row.qids, vernacular.source_release = $source_release,
          vernacular.retrieved_at = $retrieved_at
      MERGE (taxon)-[:HAS_VERNACULAR_NAME]->(vernacular)
      MERGE (run)-[:INGESTED]->(vernacular)
      WITH vernacular, dataset, row
      UNWIND row.qids AS qid
      MERGE (record:SourceRecord {id: 'wikidata-record:' + qid + ':' + $wikidata_dataset_id})
      SET record.record_type = 'taxon_label', record.external_id = qid,
          record.raw_uri = 'https://www.wikidata.org/entity/' + qid,
          record.raw_hash = $source_sha256, record.retrieved_at = $retrieved_at
      MERGE (record)-[:IN_DATASET]->(dataset)
      MERGE (vernacular)-[:FROM_RECORD]->(record)
      RETURN count(DISTINCT vernacular) AS loaded_vernacular_names
    }
    CALL {
      WITH run, dataset
      UNWIND $candidates AS row
      MERGE (candidate:VernacularNameCandidate {
        id: 'ko-vernacular-candidate:wikidata:' + row.reason_code + ':' + coalesce(row.qids[0], row.taxon_name) + ':' + $wikidata_dataset_id
      })
      SET candidate.taxon_name = row.taxon_name, candidate.proposed_name = row.korean_name,
          candidate.reason_code = row.reason_code, candidate.qids = row.qids,
          candidate.resolution_status = 'open', candidate.last_seen_run_id = $run_id,
          candidate.last_seen_at = $retrieved_at
      MERGE (run)-[:QUARANTINED]->(candidate)
      WITH candidate, dataset, row
      UNWIND row.qids AS qid
      MERGE (record:SourceRecord {id: 'wikidata-record:' + qid + ':' + $wikidata_dataset_id})
      SET record.record_type = 'taxon_label', record.external_id = qid,
          record.raw_uri = 'https://www.wikidata.org/entity/' + qid,
          record.raw_hash = $source_sha256, record.retrieved_at = $retrieved_at
      MERGE (record)-[:IN_DATASET]->(dataset)
      MERGE (record)-[:HAS_VERNACULAR_CANDIDATE]->(candidate)
      RETURN count(DISTINCT candidate) AS loaded_candidates
    }
    RETURN $batch_index AS batch_index, $batch_count AS batch_count,
           loaded_vernacular_names, loaded_candidates
    """
)

# Activation is the single atomic step that makes a snapshot visible to
# reads (see taxonomy_lineage_neo4j.py's active_dataset_id gate) and is
# guarded twice, both fail-closed:
#
# 1. `state.active_concept_set_id = $concept_set_id` -- the same
#    mid-run-taxonomy-switch guard as Start/Batch, checked one more time at
#    the last possible moment before anything durable (IngestState) changes.
# 2. `currentRunId = $expected_prior_run_id` -- optimistic concurrency. Each
#    run captures the *prior* korean-vernacular-names run id at "Read active
#    taxonomy and Korean dataset state" (near the start of its execution).
#    If another run finalizes first, `korean-vernacular-names.
#    last_successful_run_id` changes before this run reaches Finalize, this
#    WHERE no longer matches, and the query returns zero rows -- this run's
#    own writes (already content-addressed and therefore harmless even if
#    never activated) are simply never pointed at by IngestState. A stale,
#    slower writer can never clobber a newer activation.
#
# Retiring a name that dropped out of the new snapshot needs no explicit
# delete: once `active_dataset_id` flips away from the taxon's old
# dataset-scoped VernacularName id, the read path's exact-dataset-id match
# stops finding it.
FINALIZE_STATEMENT = compact_cypher(
    """
    MATCH (run:IngestionRun {id: $run_id}) WHERE run.status = 'loading'
    MATCH (taxState:IngestState {id: 'reference-taxonomy'}) WHERE taxState.active_concept_set_id = $concept_set_id
    OPTIONAL MATCH (koreanState:IngestState {id: 'korean-vernacular-names'})
    WITH run, coalesce(koreanState.last_successful_run_id, '') AS currentRunId
    WHERE currentRunId = $expected_prior_run_id
    SET run.status = 'succeeded', run.finished_at = datetime(),
        run.loaded_vernacular_names = $loaded_vernacular_names,
        run.loaded_candidates = $loaded_candidates
    MERGE (state:IngestState {id: 'korean-vernacular-names'})
    SET state.active_release = $source_release, state.active_dataset_id = $wikidata_dataset_id,
        state.taxonomy_release = $taxonomy_release,
        state.last_successful_run_id = $run_id, state.last_successful_at = datetime(),
        state.loaded_vernacular_names = $loaded_vernacular_names,
        state.loaded_candidates = $loaded_candidates
    RETURN run.id AS finalized_run_id, run.status AS run_status,
           state.active_release AS active_release, state.active_dataset_id AS active_dataset_id
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
          batch_index: index,
          batch_count: batches.length,
          ...batch,
        }}}}));
        """
    ).strip()


VERIFY_START = r"""
const expected = $('Assemble Korean vernacular quality gates').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || '');
const startOk = !errorText && response.started_run_id === expected.run_id && response.run_status === 'loading';
return [{json: {...expected, start_ok: startOk, failure_reason: startOk ? '' : (errorText || 'Neo4j did not start the ingestion run')}}];
"""

VERIFY_BATCHES = r"""
const expected = $('Assemble Korean vernacular quality gates').first().json;
const rows = $input.all().map(item => item.json);
const errors = rows.map(row => String(row.error?.message || row.error || row.message || '')).filter(Boolean);
const indexes = new Set(rows.map(row => Number(row.batch_index)).filter(Number.isInteger));
const batchCount = rows.length ? Number(rows[0].batch_count) : 0;
const loadedVernacularNames = rows.reduce((sum, row) => sum + Number(row.loaded_vernacular_names || 0), 0);
const loadedCandidates = rows.reduce((sum, row) => sum + Number(row.loaded_candidates || 0), 0);
const loadOk = !errors.length && batchCount > 0 && indexes.size === batchCount && rows.length === batchCount
  && loadedVernacularNames === expected.write_row_count
  && loadedCandidates === expected.candidate_count;
return [{json: {...expected,
  load_ok: loadOk,
  loaded_vernacular_names: loadedVernacularNames,
  loaded_candidates: loadedCandidates,
  failure_reason: loadOk ? '' : (errors.join('; ') || 'Korean vernacular batch counts did not match')
}}];
"""

VERIFY_FINALIZE = r"""
const expected = $('Assemble Korean vernacular quality gates').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || '');
const finalizeOk = !errorText
  && response.finalized_run_id === expected.run_id
  && response.run_status === 'succeeded'
  && response.active_release === expected.source_release
  && response.active_dataset_id === expected.wikidata_dataset_id;
return [{json: {...expected,
  finalize_ok: finalizeOk,
  loaded_vernacular_names: expected.loaded_vernacular_names,
  loaded_candidates: expected.loaded_candidates,
  failure_reason: finalizeOk ? '' : (errorText ||
    'korean-vernacular-names activation was refused: either the reference-taxonomy ' +
    'active concept set changed since this run resolved matches, or a concurrent run ' +
    'already activated a newer snapshot first (lost the optimistic-concurrency race)')
}}];
"""


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
                    "response": {"response": {"fullResponse": True, "responseFormat": "text"}},
                    "timeout": 120000,
                },
            },
            (-700, 0),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
        ),
        node(
            "Hash Wikidata response",
            "n8n-nodes-base.crypto",
            2,
            {
                "action": "hash",
                "binaryData": False,
                "type": "SHA256",
                "value": "={{ $json.data }}",
                "dataPropertyName": "raw_sha256",
                "encoding": "hex",
            },
            (-460, 0),
        ),
        neo4j_node(
            "Read active taxonomy and Korean dataset state", READ_STATE_STATEMENT, (-340, 0)
        ),
        code("Normalize Korean vernacular candidates", NORMALIZE_WIKIDATA, (-220, 0)),
        resolve_matches,
        code("Assemble Korean vernacular quality gates", ASSEMBLE_KOREAN_VERNACULAR_GATES, (1000, 0)),
        boolean_if("Korean vernacular quality gates passed?", "={{ $json.ready_to_load }}", (1240, 0)),
        neo4j_node("Start Korean vernacular ingestion run", START_STATEMENT, (1480, -180)),
        code("Verify Korean vernacular run started", VERIFY_START, (1720, -180)),
        boolean_if("Korean vernacular ingestion run started?", "={{ $json.start_ok }}", (1960, -180)),
        code(
            "Prepare Korean vernacular batches",
            prepare_batches_js("Assemble Korean vernacular quality gates"),
            (2200, -180),
        ),
        neo4j_node("Upsert Korean vernacular names batch", BATCH_STATEMENT, (2440, -180)),
        code("Verify Korean vernacular batches", VERIFY_BATCHES, (2680, -180)),
        boolean_if("Korean vernacular load verified?", "={{ $json.load_ok }}", (2920, -180)),
        neo4j_node("Finalize Korean vernacular active release", FINALIZE_STATEMENT, (3160, -180)),
        code("Verify Korean vernacular release finalized", VERIFY_FINALIZE, (3400, -180)),
        boolean_if("Korean vernacular release finalized?", "={{ $json.finalize_ok }}", (3640, -180)),
        status_node(
            "Notify Korean vernacular success",
            r"""
            const message = '✅ RobinGraph Korean vernacular-name ingest succeeded\n' +
              'Run: ' + $json.run_id +
              '\nVernacularName nodes: ' + $json.loaded_vernacular_names +
              ', review candidates: ' + $json.loaded_candidates +
              '\nActive reference-taxonomy release: ' + $json.taxonomy_release +
              '\nActive Wikidata dataset: ' + $json.wikidata_dataset_id;
            console.log(message);
            return [{json: {...$json, notification_message: message}}];
            """,
            (3880, -280),
        ),
        status_node(
            "Notify Korean vernacular failure",
            r"""
            const message = '❌ RobinGraph Korean vernacular-name ingest blocked or failed\n' +
              'Run: ' + String($json.run_id || 'not-started') +
              '\nReason: ' + String($json.failure_reason || 'Unknown failure').slice(0, 1500);
            console.log(message);
            return [{json: {...$json, notification_message: message}}];
            """,
            (1720, 220),
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
            (1960, 220),
        ),
        node("Korean vernacular ingest finished", "n8n-nodes-base.noOp", 1, {}, (4120, -180)),
    ]

    connections = {
        "Manual Trigger": {"main": [[edge("Build Korean vernacular configuration")]]},
        "Schedule Trigger — 1st of month 04:00 KST": {
            "main": [[edge("Build Korean vernacular configuration")]]
        },
        "Build Korean vernacular configuration": {"main": [[edge("Fetch Wikidata Korean bird labels")]]},
        "Fetch Wikidata Korean bird labels": {"main": [[edge("Hash Wikidata response")]]},
        "Hash Wikidata response": {"main": [[edge("Read active taxonomy and Korean dataset state")]]},
        "Read active taxonomy and Korean dataset state": {
            "main": [[edge("Normalize Korean vernacular candidates")]]
        },
        "Normalize Korean vernacular candidates": {
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
                [edge("Start Korean vernacular ingestion run")],
                [edge("Notify Korean vernacular failure")],
            ]
        },
        "Start Korean vernacular ingestion run": {"main": [[edge("Verify Korean vernacular run started")]]},
        "Verify Korean vernacular run started": {
            "main": [[edge("Korean vernacular ingestion run started?")]]
        },
        "Korean vernacular ingestion run started?": {
            "main": [
                [edge("Prepare Korean vernacular batches")],
                [edge("Notify Korean vernacular failure")],
            ]
        },
        "Prepare Korean vernacular batches": {"main": [[edge("Upsert Korean vernacular names batch")]]},
        "Upsert Korean vernacular names batch": {"main": [[edge("Verify Korean vernacular batches")]]},
        "Verify Korean vernacular batches": {"main": [[edge("Korean vernacular load verified?")]]},
        "Korean vernacular load verified?": {
            "main": [
                [edge("Finalize Korean vernacular active release")],
                [edge("Notify Korean vernacular failure")],
            ]
        },
        "Finalize Korean vernacular active release": {
            "main": [[edge("Verify Korean vernacular release finalized")]]
        },
        "Verify Korean vernacular release finalized": {
            "main": [[edge("Korean vernacular release finalized?")]]
        },
        "Korean vernacular release finalized?": {
            "main": [
                [edge("Notify Korean vernacular success")],
                [edge("Notify Korean vernacular failure")],
            ]
        },
        "Notify Korean vernacular success": {"main": [[edge("Korean vernacular ingest finished")]]},
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
