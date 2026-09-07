"""Generate the n8n-native RobinGraph GBIF operational-ingest workflow."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n" / "robingraph-operational-ingest.json"


def node_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"robingraph:n8n:native-gbif-ingest:{name}"))


def node(
    name: str,
    node_type: str,
    type_version: float | int,
    parameters: dict[str, object],
    position: tuple[int, int],
    **extra: object,
) -> dict[str, object]:
    return {
        "parameters": parameters,
        "id": node_id(name),
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": list(position),
        **extra,
    }


def code(name: str, js_code: str, position: tuple[int, int], **extra: object) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.code",
        2,
        {"mode": "runOnceForAllItems", "jsCode": dedent(js_code).strip()},
        position,
        **extra,
    )


def boolean_if(name: str, expression: str, position: tuple[int, int]) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.if",
        2.3,
        {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": node_id(f"{name}:condition"),
                        "leftValue": expression,
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        position,
    )


def discord(name: str, message: str, position: tuple[int, int]) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.discord",
        2,
        {
            "authentication": "webhook",
            "operation": "sendLegacy",
            "content": message,
            "options": {"username": "RobinGraph Operations", "wait": True},
        },
        position,
        onError="continueRegularOutput",
        notes=(
            "Map the RobinGraph Operations Discord Webhook credential after import. "
            "The webhook URL must remain only in n8n's credential store."
        ),
    )


def edge(target: str, index: int = 0) -> dict[str, object]:
    return {"node": target, "type": "main", "index": index}


BUILD_CONFIGURATION = r"""
const state = $getWorkflowStaticData('global');
const now = new Date();
const endDate = now.toISOString().slice(0, 10);
const fallbackStart = new Date(now);
fallbackStart.setUTCDate(fallbackStart.getUTCDate() - 30);
const startDate = state.last_successful_event_date || fallbackStart.toISOString().slice(0, 10);

return [{
  json: {
    run_id: `n8n-${$execution.id}`,
    pipeline_id: 'gbif-occurrence-kr-aves',
    retrieved_at: now.toISOString(),
    event_date_start: startDate,
    event_date_end: endDate,
    source_release: `gbif-live-${endDate}`,
    country: 'KR',
    aves_taxon_key: 212,
    page_size: 300,
    max_pages: 20,
    maximum_rejected_ratio: 0.25,
    neo4j_query_url: 'http://REPLACE_WITH_NEO4J_HOST:7474/db/neo4j/query/v2'
  }
}];
"""


NORMALIZE_GBIF = r"""
const config = $('Build run configuration').first().json;
const inputItems = $input.all();
const pages = inputItems.map(item => {
  const value = item.json;
  const body = value.body ?? value;
  return {...body, __status: Number(value.statusCode ?? 200), __raw_sha256: value.raw_sha256 ?? null};
}).filter(page => Array.isArray(page.results));
const pageErrors = inputItems.filter(item => {
  const value = item.json;
  const body = value.body ?? value;
  const status = Number(value.statusCode ?? 200);
  return status < 200 || status >= 300 || !Array.isArray(body.results);
});
const rawRecords = pages.flatMap(page => page.results.map(raw => ({raw, pageHash: page.__raw_sha256})));
const lastPage = pages.at(-1);
const truncated = Boolean(lastPage && lastPage.endOfRecords !== true && pages.length >= config.max_pages);

const allowedLicense = value => {
  const normalized = String(value || '').toLowerCase().replace(/^https:/, 'http:').replace(/legalcode\/?$/, '');
  return [
    'http://creativecommons.org/publicdomain/zero/1.0/',
    'http://creativecommons.org/licenses/by/3.0/',
    'http://creativecommons.org/licenses/by/4.0/'
  ].includes(normalized);
};
const datePrecision = value => {
  const text = String(value || '');
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return 'instant';
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return 'day';
  if (/^\d{4}-\d{2}$/.test(text)) return 'month';
  if (/^\d{4}$/.test(text)) return 'year';
  return 'unknown';
};
const coordinateIssueCodes = new Set([
  'ZERO_COORDINATE', 'COORDINATE_INVALID', 'COORDINATE_OUT_OF_RANGE',
  'COUNTRY_COORDINATE_MISMATCH', 'COORDINATE_REPROJECTION_FAILED'
]);
const seen = new Set();
const observations = [];
const media = [];
const quarantine = [];

for (const {raw, pageHash} of rawRecords) {
  const externalId = String(raw.gbifID ?? raw.key ?? 'missing');
  if (seen.has(externalId)) continue;
  seen.add(externalId);
  const issues = Array.isArray(raw.issues) ? raw.issues : [];
  const lat = Number(raw.decimalLatitude);
  const lon = Number(raw.decimalLongitude);
  const taxonKey = raw.acceptedTaxonKey ?? raw.taxonKey;
  const reasons = [];
  if (!allowedLicense(raw.license)) reasons.push('license_not_allowed');
  if (!externalId || externalId === 'missing') reasons.push('missing_external_id');
  if (!pageHash) reasons.push('missing_raw_page_sha256');
  if (!taxonKey || !raw.scientificName) reasons.push('missing_taxon_identity');
  if (!raw.eventDate) reasons.push('missing_event_date');
  if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
    reasons.push('invalid_or_missing_public_coordinate');
  }
  if (issues.some(issue => coordinateIssueCodes.has(issue))) reasons.push('unsafe_coordinate_issue');
  if (String(raw.occurrenceStatus || '').toUpperCase() !== 'PRESENT') reasons.push('not_present');
  if (String(raw.countryCode || '').toUpperCase() !== config.country) reasons.push('country_mismatch');
  if (raw.individualCount != null && (!Number.isInteger(Number(raw.individualCount)) || Number(raw.individualCount) < 0)) {
    reasons.push('invalid_individual_count');
  }
  if (reasons.length) {
    quarantine.push({
      external_id: externalId,
      reason_codes: reasons,
      stage: 'validate',
      source_uri: externalId === 'missing' ? null : `https://api.gbif.org/v1/occurrence/${externalId}`
    });
    continue;
  }

  const generalized = Boolean(raw.informationWithheld || raw.dataGeneralizations || issues.includes('COORDINATE_ROUNDED'));
  const placeLabel = raw.locality || raw.stateProvince || raw.countryCode || 'Republic of Korea';
  const observationId = `gbif-observation:${externalId}`;
  observations.push({
    id: observationId,
    external_id: externalId,
    occurrence_id: String(raw.occurrenceID || externalId),
    event_id: raw.eventID == null ? null : String(raw.eventID),
    external_taxon_id: `gbif-taxon:${taxonKey}`,
    external_taxon_key: String(taxonKey),
    scientific_name: String(raw.acceptedScientificName || raw.scientificName),
    scientific_name_raw: String(raw.scientificName),
    taxon_rank: String(raw.taxonRank || raw.rank || 'UNKNOWN').toLowerCase(),
    observed_at: String(raw.eventDate),
    event_date_precision: datePrecision(raw.eventDate),
    count: raw.individualCount == null ? null : Number(raw.individualCount),
    basis: String(raw.basisOfRecord || 'UNKNOWN').toLowerCase(),
    lat,
    lon,
    coordinate_uncertainty_m: raw.coordinateUncertaintyInMeters == null ? null : Number(raw.coordinateUncertaintyInMeters),
    geodetic_datum: raw.geodeticDatum == null ? null : String(raw.geodeticDatum),
    sensitivity: generalized ? 'generalized' : 'public',
    place_id: `gbif-place:${raw.countryCode || 'KR'}:${raw.stateProvince || 'unknown'}`,
    place_name: String(placeLabel),
    dataset_id: `gbif-dataset:${raw.datasetKey || 'unknown'}`,
    dataset_key: String(raw.datasetKey || 'unknown'),
    publisher_key: raw.publishingOrgKey == null ? null : String(raw.publishingOrgKey),
    license_uri: String(raw.license),
    source_record_key: `gbif:${config.source_release}:${externalId}`,
    source_release: config.source_release,
    raw_uri: `https://api.gbif.org/v1/occurrence/${externalId}`,
    raw_sha256: pageHash,
    source_updated_at: raw.lastInterpreted == null ? null : String(raw.lastInterpreted),
    retrieved_at: config.retrieved_at,
    issues
  });
  for (const [index, asset] of (Array.isArray(raw.media) ? raw.media : []).entries()) {
    if (!allowedLicense(asset.license)) continue;
    const assetId = String(asset.identifier || asset.references || `${externalId}:${index}`);
    media.push({
      id: `gbif-media:${assetId}`,
      observation_id: observationId,
      media_type: String(asset.type || 'unknown').toLowerCase(),
      format: asset.format == null ? null : String(asset.format),
      landing_uri: String(asset.references || raw.references || `https://www.gbif.org/occurrence/${externalId}`),
      asset_uri: asset.identifier == null ? null : String(asset.identifier),
      creator: asset.creator == null ? null : String(asset.creator),
      publisher: asset.publisher == null ? null : String(asset.publisher),
      attribution: String(asset.rightsHolder || asset.creator || asset.publisher || 'See source'),
      license_uri: String(asset.license),
      retrieved_at: config.retrieved_at
    });
  }
}

const rejectedRatio = rawRecords.length ? quarantine.length / rawRecords.length : 1;
const failureReasons = [];
if (!pages.length) failureReasons.push('GBIF returned no valid page objects');
if (pageErrors.length) failureReasons.push(`${pageErrors.length} GBIF page request(s) failed`);
if (!rawRecords.length) failureReasons.push('GBIF returned zero records for the configured window');
if (!observations.length) failureReasons.push('No records passed validation');
if (rejectedRatio > config.maximum_rejected_ratio) failureReasons.push(`Rejected ratio ${rejectedRatio.toFixed(3)} exceeds gate`);
if (truncated) failureReasons.push(`Result exceeded ${config.max_pages * config.page_size} records; narrow the date window`);

return [{json: {
  ...config,
  fetch_ok: pages.length > 0 && pageErrors.length === 0,
  ready_to_load: failureReasons.length === 0,
  failure_reason: failureReasons.join('; '),
  page_count: pages.length,
  source_count: rawRecords.length,
  observation_count: observations.length,
  media_count: media.length,
  quarantine_count: quarantine.length,
  rejected_ratio: rejectedRatio,
  truncated,
  observations,
  media,
  quarantine
}}];
"""


NEO4J_STATEMENT = " ".join(
    dedent(
        """
        MERGE (run:IngestionRun {id: $run_id})
        SET run.pipeline_id = $pipeline_id, run.started_at = $retrieved_at,
            run.source_release = $source_release, run.status = 'loading',
            run.source_count = $source_count, run.quarantine_count = $quarantine_count
        WITH run
        CALL {
          WITH run
          UNWIND $observations AS row
          MERGE (dataset:SourceDataset {id: row.dataset_id})
          SET dataset.name = 'GBIF occurrence dataset', dataset.provider = 'GBIF',
              dataset.dataset_key = row.dataset_key, dataset.version = row.source_release,
              dataset.landing_uri = 'https://www.gbif.org/dataset/' + row.dataset_key,
              dataset.policy_status = 'allowed'
          MERGE (license:License {id: row.license_uri})
          SET license.license_uri = row.license_uri, license.policy_status = 'allowed'
          MERGE (dataset)-[:LICENSED_UNDER]->(license)
          MERGE (source:SourceRecord {id: row.source_record_key})
          SET source.external_id = row.external_id, source.record_type = 'observation',
              source.raw_uri = row.raw_uri, source.raw_hash = row.raw_sha256,
              source.retrieved_at = row.retrieved_at, source.source_updated_at = row.source_updated_at,
              source.issues = row.issues
          MERGE (source)-[:IN_DATASET]->(dataset)
          MERGE (taxon:ExternalTaxonConcept {id: row.external_taxon_id})
          SET taxon.provider = 'GBIF Backbone', taxon.external_key = row.external_taxon_key,
              taxon.scientific_name = row.scientific_name, taxon.rank = row.taxon_rank
          MERGE (place:Place {id: row.place_id})
          SET place.name = row.place_name, place.country_code = 'KR', place.place_type = 'gbif_admin_area'
          MERGE (observation:Observation {id: row.id})
          SET observation.occurrence_id = row.occurrence_id, observation.event_id = row.event_id,
              observation.scientific_name_raw = row.scientific_name_raw,
              observation.observed_at = row.observed_at,
              observation.event_date_precision = row.event_date_precision,
              observation.count = row.count, observation.basis = row.basis,
              observation.lat = row.lat, observation.lon = row.lon,
              observation.coordinate_uncertainty_m = row.coordinate_uncertainty_m,
              observation.geodetic_datum = row.geodetic_datum,
              observation.sensitivity = row.sensitivity,
              observation.source_record_key = row.source_record_key,
              observation.ingestion_run_id = $run_id
          MERGE (observation)-[:IDENTIFIED_AS]->(taxon)
          MERGE (observation)-[:WITHIN]->(place)
          MERGE (observation)-[:FROM_RECORD]->(source)
          MERGE (run)-[:INGESTED]->(observation)
          MERGE (evidence:EvidenceUnit {id: 'gbif-evidence:' + row.external_id})
          SET evidence.evidence_type = 'observation', evidence.locator = row.raw_uri,
              evidence.accessed_at = row.retrieved_at
          MERGE (evidence)-[:FROM_RECORD]->(source)
          RETURN count(*) AS loaded_observations
        }
        CALL {
          WITH run
          UNWIND $media AS row
          MATCH (observation:Observation {id: row.observation_id})
          MERGE (asset:MediaAsset {id: row.id})
          SET asset.media_type = row.media_type, asset.format = row.format,
              asset.landing_uri = row.landing_uri, asset.asset_uri = row.asset_uri,
              asset.creator = row.creator, asset.publisher = row.publisher,
              asset.attribution = row.attribution, asset.license_uri = row.license_uri,
              asset.redistribution_allowed = true, asset.retrieved_at = row.retrieved_at
          MERGE (observation)-[:HAS_MEDIA]->(asset)
          MERGE (run)-[:INGESTED]->(asset)
          RETURN count(*) AS loaded_media
        }
        CALL {
          WITH run
          UNWIND $quarantine AS row
          MERGE (item:QuarantineRecord {id: $pipeline_id + ':' + row.external_id + ':' + row.stage})
          ON CREATE SET item.first_seen_run_id = $run_id, item.first_seen_at = $retrieved_at
          SET item.external_id = row.external_id, item.stage = row.stage,
              item.reason_codes = row.reason_codes, item.source_uri = row.source_uri,
              item.last_seen_run_id = $run_id, item.last_seen_at = $retrieved_at,
              item.resolution_status = 'open'
          MERGE (run)-[:QUARANTINED]->(item)
          RETURN count(*) AS loaded_quarantine
        }
        SET run.status = 'succeeded', run.finished_at = datetime(),
            run.observation_count = loaded_observations, run.media_count = loaded_media
        MERGE (state:IngestState {id: $pipeline_id})
        SET state.active_release = $source_release, state.last_successful_run_id = $run_id,
            state.last_successful_at = datetime(), state.event_date_end = $event_date_end
        RETURN loaded_observations, loaded_media, loaded_quarantine, state.active_release
        """
    ).split()
)


ASSESS_NEO4J = r"""
const expected = $('Normalize, validate and deduplicate GBIF').first().json;
const response = $input.first().json;
const statusCode = Number(response.statusCode ?? response.status ?? 0);
const body = response.body ?? response;
const fields = body?.data?.fields || [];
const values = body?.data?.values?.[0] || [];
const result = Object.fromEntries(fields.map((field, index) => [field, values[index]]));
const serverErrors = Array.isArray(body?.errors) ? body.errors : [];
const errorText = String(response.error?.message || body?.error?.message || body?.message || serverErrors[0]?.message || '');
const loadOk = statusCode === 202 && serverErrors.length === 0
  && Number(result.loaded_observations) === expected.observation_count
  && Number(result.loaded_media) === expected.media_count
  && Number(result.loaded_quarantine) === expected.quarantine_count
  && result.active_release === expected.source_release;
return [{json: {
  ...expected,
  load_ok: loadOk,
  loaded_observations: Number(result.loaded_observations || 0),
  loaded_media: Number(result.loaded_media || 0),
  loaded_quarantine: Number(result.loaded_quarantine || 0),
  failure_reason: loadOk ? '' : (errorText || `Neo4j verification failed (HTTP ${statusCode || 'unknown'})`)
}}];
"""


PERSIST_CURSOR = r"""
const result = $input.first().json;
if (!result.load_ok) throw new Error('Refusing to advance the cursor before a verified Neo4j load');
const state = $getWorkflowStaticData('global');
state.last_successful_event_date = result.event_date_end;
state.last_successful_run_id = result.run_id;
return [{json: result}];
"""


def main() -> None:
    nodes: list[dict[str, object]] = [
        node("Manual Trigger", "n8n-nodes-base.manualTrigger", 1, {}, (-960, -120)),
        node(
            "Schedule Trigger — daily 02:00 KST",
            "n8n-nodes-base.scheduleTrigger",
            1.2,
            {"rule": {"interval": [{"field": "cronExpression", "expression": "0 2 * * *"}]}},
            (-960, 120),
        ),
        code(
            "Build run configuration",
            BUILD_CONFIGURATION,
            (-680, 0),
            notes=(
                "Edit neo4j_query_url before the first run. The workflow defaults to a thirty-day window "
                "and advances its cursor only after a verified atomic load."
            ),
        ),
        node(
            "Fetch GBIF Korea Aves pages",
            "n8n-nodes-base.httpRequest",
            4.5,
            {
                "url": (
                    "https://api.gbif.org/v1/occurrence/search"
                    "?license=CC0_1_0&license=CC_BY_4_0"
                ),
                "sendQuery": True,
                "queryParameters": {
                    "parameters": [
                        {"name": "country", "value": "={{ $('Build run configuration').first().json.country }}"},
                        {"name": "taxon_key", "value": "={{ $('Build run configuration').first().json.aves_taxon_key }}"},
                        {"name": "has_coordinate", "value": "true"},
                        {"name": "occurrence_status", "value": "present"},
                        {"name": "event_date", "value": "={{ $('Build run configuration').first().json.event_date_start + ',' + $('Build run configuration').first().json.event_date_end }}"},
                        {"name": "limit", "value": "={{ $('Build run configuration').first().json.page_size }}"},
                    ]
                },
                "options": {
                    "pagination": {
                        "pagination": {
                            "paginationMode": "updateAParameterInEachRequest",
                            "parameters": {
                                "parameters": [
                                    {
                                        "type": "qs",
                                        "name": "offset",
                                        "value": "={{ $pageCount * $('Build run configuration').first().json.page_size }}",
                                    }
                                ]
                            },
                            "paginationCompleteWhen": "other",
                            "completeExpression": "={{ $response.body.endOfRecords === true }}",
                            "limitPagesFetched": True,
                            "maxRequests": 20,
                            "requestInterval": 200,
                        }
                    },
                    "response": {
                        "response": {"fullResponse": True, "neverError": True, "responseFormat": "json"}
                    },
                    "timeout": 120000,
                },
            },
            (-400, 0),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
            onError="continueRegularOutput",
            notes="Calls the public GBIF API directly. Pagination is capped at 6,000 records per run.",
        ),
        node(
            "Hash each raw GBIF page",
            "n8n-nodes-base.crypto",
            2,
            {
                "action": "hash",
                "binaryData": False,
                "type": "SHA256",
                "value": "={{ JSON.stringify($json.body ?? $json) }}",
                "dataPropertyName": "raw_sha256",
                "encoding": "hex",
            },
            (-150, 0),
            notes="Hashes every raw API page before normalization. Only the hash and source record URI are persisted.",
        ),
        code("Normalize, validate and deduplicate GBIF", NORMALIZE_GBIF, (110, 0)),
        boolean_if("Quality gates passed?", "={{ $json.ready_to_load }}", (410, 0)),
        node(
            "Atomic upsert to Neo4j Query API",
            "n8n-nodes-base.httpRequest",
            4.5,
            {
                "method": "POST",
                "url": "={{ $('Build run configuration').first().json.neo4j_query_url }}",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
                "sendBody": True,
                "contentType": "json",
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ statement: "
                    + json.dumps(NEO4J_STATEMENT)
                    + ", parameters: $json, txMetadata: { app: 'RobinGraph n8n', run_id: $json.run_id }, "
                    "maxExecutionTime: 120 }) }}"
                ),
                "options": {
                    "response": {
                        "response": {"fullResponse": True, "neverError": True, "responseFormat": "json"}
                    },
                    "timeout": 150000,
                },
            },
            (700, -140),
            onError="continueRegularOutput",
            notes=(
                "Map a generic HTTP Basic Auth credential for Neo4j. This single Query API request is an "
                "implicit transaction: any Cypher failure rolls back the whole batch."
            ),
        ),
        code("Verify Neo4j response counts", ASSESS_NEO4J, (990, -140)),
        boolean_if("Atomic load verified?", "={{ $json.load_ok }}", (1270, -140)),
        code("Advance n8n cursor", PERSIST_CURSOR, (1540, -260)),
        discord(
            "Notify success",
            "={{ '✅ **RobinGraph GBIF ingest succeeded**\\nRun: ' + $json.run_id + "
            "'\\nWindow: ' + $json.event_date_start + ' → ' + $json.event_date_end + "
            "'\\nSource: ' + $json.source_count + ', loaded: ' + $json.loaded_observations + "
            "', media: ' + $json.loaded_media + ', quarantine: ' + $json.loaded_quarantine }}",
            (1810, -260),
        ),
        discord(
            "Notify failure",
            "={{ '❌ **RobinGraph GBIF ingest blocked or failed**\\nRun: ' + $json.run_id + "
            "'\\nReason: ' + String($json.failure_reason || 'Unknown failure').slice(0, 1500) + "
            "'\\nSource: ' + Number($json.source_count || 0) + ', valid: ' + "
            "Number($json.observation_count || 0) + ', quarantine: ' + Number($json.quarantine_count || 0) }}",
            (1540, 180),
        ),
        node(
            "Fail execution",
            "n8n-nodes-base.stopAndError",
            1,
            {"errorMessage": "RobinGraph native ingest failed; inspect the preceding quality or Neo4j response node."},
            (1810, 180),
        ),
        node("Finished", "n8n-nodes-base.noOp", 1, {}, (2080, -60)),
    ]

    connections = {
        "Manual Trigger": {"main": [[edge("Build run configuration")]]},
        "Schedule Trigger — daily 02:00 KST": {"main": [[edge("Build run configuration")]]},
        "Build run configuration": {"main": [[edge("Fetch GBIF Korea Aves pages")]]},
        "Fetch GBIF Korea Aves pages": {"main": [[edge("Hash each raw GBIF page")]]},
        "Hash each raw GBIF page": {"main": [[edge("Normalize, validate and deduplicate GBIF")]]},
        "Normalize, validate and deduplicate GBIF": {"main": [[edge("Quality gates passed?")]]},
        "Quality gates passed?": {
            "main": [[edge("Atomic upsert to Neo4j Query API")], [edge("Notify failure")]]
        },
        "Atomic upsert to Neo4j Query API": {"main": [[edge("Verify Neo4j response counts")]]},
        "Verify Neo4j response counts": {"main": [[edge("Atomic load verified?")]]},
        "Atomic load verified?": {"main": [[edge("Advance n8n cursor")], [edge("Notify failure")]]},
        "Advance n8n cursor": {"main": [[edge("Notify success")]]},
        "Notify success": {"main": [[edge("Finished")]]},
        "Notify failure": {"main": [[edge("Fail execution")]]},
    }

    workflow = {
        "id": node_id("workflow-id"),
        "name": "RobinGraph — native GBIF ingest to Neo4j (inactive until credentials verified)",
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
        "versionId": node_id("workflow-version-v2"),
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
