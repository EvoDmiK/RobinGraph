"""Generate the n8n-native RobinGraph GBIF operational-ingest workflow."""

from __future__ import annotations

import json
import re
from pathlib import Path
from textwrap import dedent
from uuid import NAMESPACE_URL, uuid5

try:
    from .generate_n8n_reference_ingest import ingest_api_node
except ImportError:
    from generate_n8n_reference_ingest import ingest_api_node


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
    dataset_id: 'gbif-occurrence-kr-aves',
    country: 'KR',
    aves_taxon_key: 212,
    page_size: 300,
    max_pages: 20,
    maximum_rejected_ratio: 0.25
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
const taxonById = new Map();
const taxonLinkById = new Map();

const addTaxon = (key, rank, scientificName, details = {}) => {
  if (key == null || !scientificName) return null;
  const externalKey = String(key);
  const id = `gbif-taxon:${externalKey}`;
  const existing = taxonById.get(id) || {};
  taxonById.set(id, {
    ...existing,
    id,
    external_key: externalKey,
    provider: 'GBIF Backbone',
    rank: String(rank || 'UNKNOWN').toLowerCase(),
    scientific_name: String(scientificName),
    canonical_name: details.canonical_name == null ? (existing.canonical_name ?? null) : String(details.canonical_name),
    authorship: details.authorship == null ? (existing.authorship ?? null) : String(details.authorship),
    taxonomic_status: details.taxonomic_status == null ? (existing.taxonomic_status ?? null) : String(details.taxonomic_status).toLowerCase(),
    vernacular_name_raw: details.vernacular_name_raw == null ? (existing.vernacular_name_raw ?? null) : String(details.vernacular_name_raw),
    source_uri: `https://www.gbif.org/species/${externalKey}`,
    retrieved_at: config.retrieved_at
  });
  return id;
};

const addTaxonLink = (parentId, childId) => {
  if (!parentId || !childId || parentId === childId) return;
  const id = `${parentId}->${childId}`;
  taxonLinkById.set(id, {id, parent_id: parentId, child_id: childId});
};

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
  const hierarchy = [
    [raw.kingdomKey, 'kingdom', raw.kingdom],
    [raw.phylumKey, 'phylum', raw.phylum],
    [raw.classKey, 'class', raw.class],
    [raw.orderKey, 'order', raw.order],
    [raw.familyKey, 'family', raw.family],
    [raw.genusKey, 'genus', raw.genus],
    [raw.speciesKey, 'species', raw.species]
  ];
  const hierarchyIds = hierarchy
    .map(([key, rank, name]) => addTaxon(key, rank, name, {canonical_name: name}))
    .filter(Boolean);
  for (let index = 1; index < hierarchyIds.length; index += 1) {
    addTaxonLink(hierarchyIds[index - 1], hierarchyIds[index]);
  }
  const acceptedTaxonId = addTaxon(taxonKey, raw.taxonRank || raw.rank, raw.acceptedScientificName || raw.scientificName, {
    canonical_name: raw.species || raw.genericName || null,
    authorship: raw.scientificNameAuthorship,
    taxonomic_status: raw.taxonomicStatus,
    vernacular_name_raw: raw.vernacularName
  });
  addTaxonLink(hierarchyIds.at(-1), acceptedTaxonId);
  observations.push({
    id: observationId,
    external_id: externalId,
    occurrence_id: String(raw.occurrenceID || externalId),
    event_id: raw.eventID == null ? null : String(raw.eventID),
    external_taxon_id: acceptedTaxonId,
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
const birdTaxa = [...taxonById.values()];
const taxonLinks = [...taxonLinkById.values()];
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
  taxon_count: birdTaxa.length,
  taxon_link_count: taxonLinks.length,
  media_count: media.length,
  quarantine_count: quarantine.length,
  rejected_ratio: rejectedRatio,
  truncated,
  observations,
  bird_taxa: birdTaxa,
  taxon_links: taxonLinks,
  media,
  quarantine
}}];
"""


NEO4J_STATEMENT = " ".join(
    dedent(
        """
        CALL {
          MERGE (concept_set:TaxonConceptSet {id: 'rg:concept-set:gbif-current'})
          SET concept_set.title = 'GBIF taxonomic backbone', concept_set.version = 'mutable-current',
              concept_set.source_uri = 'https://www.gbif.org/species/search',
              concept_set.retrieved_at = $retrieved_at,
              concept_set.dataset_id = $dataset_id, concept_set.policy_status = 'allowed'
          WITH concept_set
          UNWIND $bird_taxa AS row
          MERGE (taxon:ExternalTaxonConcept {id: row.id})
          SET taxon:BirdTaxon,
              taxon.provider = row.provider, taxon.external_key = row.external_key,
              taxon.scientific_name = row.scientific_name, taxon.canonical_name = row.canonical_name,
              taxon.authorship = row.authorship, taxon.rank = row.rank,
              taxon.taxonomic_status = row.taxonomic_status,
              taxon.vernacular_name_raw = row.vernacular_name_raw,
              taxon.source_uri = row.source_uri, taxon.retrieved_at = row.retrieved_at,
              taxon.dataset_id = $dataset_id, taxon.policy_status = 'allowed'
          MERGE (scientific_name:ScientificName {id: 'gbif-scientific-name:' + row.external_key})
          SET scientific_name.full_name = row.scientific_name,
              scientific_name.canonical = row.canonical_name,
              scientific_name.authorship = row.authorship,
              scientific_name.nomenclatural_code = 'ICZN'
          MERGE (taxon)-[:HAS_ACCEPTED_NAME]->(scientific_name)
          MERGE (taxon)-[:IN_CONCEPT_SET]->(concept_set)
          RETURN count(*) AS loaded_taxa
        }
        CALL {
          UNWIND $taxon_links AS row
          MATCH (parent:ExternalTaxonConcept {id: row.parent_id})
          MATCH (child:ExternalTaxonConcept {id: row.child_id})
          MERGE (parent)-[:PARENT_OF {provider: 'GBIF'}]->(child)
          RETURN count(*) AS loaded_taxon_links
        }
        CALL {
          UNWIND $observations AS row
          WITH row
          MATCH (taxon:ExternalTaxonConcept {id: row.external_taxon_id})
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
              observation.ingestion_run_id = $run_id,
              observation.dataset_id = $dataset_id,
              observation.source_dataset_id = row.dataset_id,
              observation.source_record_id = row.source_record_key,
              observation.source_uri = row.raw_uri,
              observation.source_retrieved_at = row.retrieved_at,
              observation.source_updated_at = row.source_updated_at,
              observation.license_uri = row.license_uri,
              observation.policy_status = 'allowed'
          MERGE (observation)-[:IDENTIFIED_AS]->(taxon)
          MERGE (observation)-[:WITHIN]->(place)
          MERGE (evidence:EvidenceUnit {id: 'gbif-evidence:' + row.external_id})
          SET evidence.evidence_type = 'observation', evidence.locator = row.raw_uri,
              evidence.accessed_at = row.retrieved_at, evidence.dataset_id = $dataset_id,
              evidence.source_record_id = row.source_record_key, evidence.policy_status = 'allowed'
          MERGE (observation)-[:SUPPORTED_BY]->(evidence)
          RETURN count(*) AS loaded_observations
        }
        CALL {
          UNWIND $media AS row
          MATCH (observation:Observation {id: row.observation_id})
          MERGE (asset:MediaAsset {id: row.id})
          SET asset.media_type = row.media_type, asset.format = row.format,
              asset.landing_uri = row.landing_uri, asset.asset_uri = row.asset_uri,
              asset.creator = row.creator, asset.publisher = row.publisher,
              asset.attribution = row.attribution, asset.license_uri = row.license_uri,
              asset.redistribution_allowed = true, asset.retrieved_at = row.retrieved_at,
              asset.dataset_id = $dataset_id, asset.policy_status = 'allowed'
          MERGE (observation)-[:HAS_MEDIA]->(asset)
          RETURN count(*) AS loaded_media
        }
        RETURN loaded_taxa, loaded_taxon_links, loaded_observations, loaded_media,
               'domain_verified' AS status
        """
    ).split()
)


# The community node calls graph.query(cypherQuery) without a parameters argument.
# Substitute only placeholders in the trusted template, never in external values.
CYPHER_LITERAL_JS = r"""
const literal = value => {
  if (value === null) return 'null';
  if (typeof value === 'string') return "'" + value.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/[\u0000-\u001f\u007f]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')) + "'";
  if (typeof value === 'boolean') return String(value);
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (Array.isArray(value)) return '[' + value.map(literal).join(',') + ']';
  if (typeof value === 'object' && value !== null) return '{' + Object.entries(value).map(([key, val]) => {
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) throw new Error('Invalid Cypher map key');
    return key + ':' + literal(val);
  }).join(',') + '}';
  throw new Error('Unsupported Cypher value');
};
"""


def community_cypher_expression() -> str:
    keys = sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", NEO4J_STATEMENT)))
    return "={{ (() => { " + CYPHER_LITERAL_JS + "const values = {" + ",".join(
        json.dumps(key) + ": literal($json[" + json.dumps(key) + "])" for key in keys
    ) + "}; return " + json.dumps(NEO4J_STATEMENT) + r".replace(/\$([A-Za-z_][A-Za-z0-9_]*)/g, (_, key) => values[key]); })() }}"


ASSESS_NEO4J = r"""
const expected = $('Normalize, validate and deduplicate GBIF').first().json;
const response = $input.first().json;
const result = response;
const errorText = String(response.error?.message || response.error || response.message || '');
const loadOk = !errorText
  && Number(result.loaded_taxa) === expected.taxon_count
  && Number(result.loaded_taxon_links) === expected.taxon_link_count
  && Number(result.loaded_observations) === expected.observation_count
  && Number(result.loaded_media) === expected.media_count
  && result.status === 'domain_verified';
return [{json: {
  ...expected,
  load_ok: loadOk,
  loaded_taxa: Number(result.loaded_taxa || 0),
  loaded_taxon_links: Number(result.loaded_taxon_links || 0),
  loaded_observations: Number(result.loaded_observations || 0),
  loaded_media: Number(result.loaded_media || 0),
  loaded_quarantine: expected.quarantine_count,
  failure_reason: loadOk ? '' : (errorText || 'Neo4j domain result counts do not match')
}}];
"""


PREPARE_BEGIN = r"""
const source=$input.first().json;
return [{json:{...source,ingest_request:{
  dataset:{id:source.dataset_id,source_id:'gbif',name:'GBIF Korea Aves occurrence feed',provider:'GBIF',
    landing_uri:'https://www.gbif.org/occurrence/search',release_strategy:'dated_snapshot',
    policy_status:'allowed',metadata:{country:source.country,taxon_key:source.aves_taxon_key}},
  release:{id:'gbif-release:'+source.source_release,release_key:source.source_release,
    retrieved_at:source.retrieved_at,raw_object_uri:'https://api.gbif.org/v1/occurrence/search',
    metadata:{event_date_start:source.event_date_start,event_date_end:source.event_date_end,page_count:source.page_count}},
  run:{id:source.run_id,pipeline_id:source.pipeline_id,started_at:source.retrieved_at,
    manifest:{orchestrator:'n8n',workflow:'gbif-operational',source_count:source.source_count}}
}}}];
"""


VERIFY_BEGIN = r"""
const source=$('Prepare PostgreSQL GBIF run').first().json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
if(errorText||response.status!=='started'||!Number.isSafeInteger(response.state_version))
  throw new Error(errorText||'PostgreSQL did not start GBIF run');
return [{json:{...source,expected_state_version:response.state_version}}];
"""


BUILD_SOURCE_BATCHES = r"""
const source=$input.first().json;
const records=source.observations.map(row=>({id:row.source_record_key,external_id:row.external_id,
  record_type:'observation',raw_object_uri:row.raw_uri,raw_sha256:row.raw_sha256,
  retrieved_at:row.retrieved_at,source_updated_at:row.source_updated_at,
  parser_version:'gbif-occurrence-v2',license_policy_status:'allowed',
  payload:{occurrence_id:row.occurrence_id,event_id:row.event_id,scientific_name:row.scientific_name,
    observed_at:row.observed_at,dataset_key:row.dataset_key,issues:row.issues}}));
const quarantineItems=source.quarantine.flatMap(item=>item.reason_codes.map(reason=>({
  record_key:'gbif:'+source.source_release+':'+item.external_id,stage:item.stage,reason_code:reason,
  severity:reason==='license_not_allowed'?'blocked':'error',rule_version:'gbif-operational-v2',
  raw_value_redacted:item.source_uri
})));
const count=Math.max(1,Math.ceil(records.length/500),Math.ceil(quarantineItems.length/500));
const {observations, quarantine, ingest_request, ...context}=source;
return Array.from({length:count},(_,batch_index)=>({json:{...context,batch_index,batch_count:count,
  ingest_request:{records:records.slice(batch_index*500,(batch_index+1)*500),
    quarantine_items:quarantineItems.slice(batch_index*500,(batch_index+1)*500)}}}))
  .filter(item=>item.json.ingest_request.records.length||item.json.ingest_request.quarantine_items.length);
"""


VERIFY_APPEND = r"""
const batch=$('Build PostgreSQL GBIF source batches').item.json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
if(errorText||response.status!=='appended')throw new Error(errorText||'PostgreSQL GBIF append failed');
return [{json:batch}];
"""


RESTORE_DOMAIN_PAYLOAD = r"""
const source=$('Verify PostgreSQL GBIF run started').first().json;
return [{json:source}];
"""


PREPARE_FINALIZE = r"""
const source=$input.first().json;
const expectedStateVersion=$('Verify PostgreSQL GBIF run started').first().json.expected_state_version;
return [{json:{...source,ingest_request:{counts:{source_records:source.observation_count,
  quarantined:source.quarantine_count,taxa:source.loaded_taxa,taxon_links:source.loaded_taxon_links,
  observations:source.loaded_observations,media:source.loaded_media},
  cursor:{event_date_end:source.event_date_end},expected_state_version:expectedStateVersion},
  expected_state_version:expectedStateVersion}}];
"""


VERIFY_FINALIZE = r"""
const source=$('Prepare PostgreSQL GBIF finalization').first().json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
if(errorText||response.status!=='finalized'||response.state_version!==source.expected_state_version+1)
  throw new Error(errorText||'PostgreSQL GBIF activation failed');
return [{json:{...source,finalize_ok:true}}];
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
                "Select the Neo4j credential before the first run. The workflow defaults to a thirty-day window "
                "and advances its cursor only after a verified atomic load."
            ),
        ),
        node(
            "Fetch GBIF Korea Aves pages",
            "n8n-nodes-base.httpRequest",
            4.4,
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
        code("Prepare PostgreSQL GBIF run", PREPARE_BEGIN, (650, -140)),
        ingest_api_node("Start PostgreSQL GBIF run", "'/internal/v1/ingest/begin'", (880, -140)),
        code("Verify PostgreSQL GBIF run started", VERIFY_BEGIN, (1110, -140)),
        code("Build PostgreSQL GBIF source batches", BUILD_SOURCE_BATCHES, (1340, -140)),
        node(
            "Loop Over PostgreSQL GBIF source batches",
            "n8n-nodes-base.splitInBatches",
            3,
            {"batchSize": 1, "options": {}},
            (1570, -140),
        ),
        ingest_api_node(
            "Append PostgreSQL GBIF source batch",
            "('/internal/v1/ingest/'+$json.run_id+'/append')",
            (1800, 20),
        ),
        code("Verify PostgreSQL GBIF source batch", VERIFY_APPEND, (2030, 20)),
        code("Restore GBIF domain payload", RESTORE_DOMAIN_PAYLOAD, (1800, -260)),
        node(
            "Atomic upsert to Neo4j",
            "n8n-nodes-neo4j.neo4j",
            1,
            {
                "resource": "graphDb",
                "operation": "executeQuery",
                "cypherQuery": community_cypher_expression(),
            },
            (2030, -260),
            credentials={"neo4jApi": {"id": "DvmTD1qB0Kb7TRml", "name": "Neo4j"}},
            onError="continueRegularOutput",
            alwaysOutputData=True,
            notes="Execute one atomic Cypher statement using the Neo4j credential. Values are escaped as Cypher literals because this community node has no query parameter input.",
        ),
        code("Verify Neo4j response counts", ASSESS_NEO4J, (2260, -260)),
        boolean_if("Atomic load verified?", "={{ $json.load_ok }}", (2490, -260)),
        code("Prepare PostgreSQL GBIF finalization", PREPARE_FINALIZE, (2720, -380)),
        ingest_api_node(
            "Finalize PostgreSQL GBIF release",
            "('/internal/v1/ingest/'+$json.run_id+'/finalize')",
            (2950, -380),
        ),
        code("Verify PostgreSQL GBIF release", VERIFY_FINALIZE, (3180, -380)),
        code("Advance n8n cursor", PERSIST_CURSOR, (3410, -380)),
        discord(
            "Notify success",
            "={{ '✅ **RobinGraph GBIF ingest succeeded**\\nRun: ' + $json.run_id + "
            "'\\nWindow: ' + $json.event_date_start + ' → ' + $json.event_date_end + "
            "'\\nSource: ' + $json.source_count + ', birds: ' + $json.loaded_taxa + "
            "', observations: ' + $json.loaded_observations + "
            "', media: ' + $json.loaded_media + ', quarantine: ' + $json.loaded_quarantine }}",
            (3640, -380),
        ),
        discord(
            "Notify failure",
            "={{ '❌ **RobinGraph GBIF ingest blocked or failed**\\nRun: ' + $json.run_id + "
            "'\\nReason: ' + String($json.failure_reason || 'Unknown failure').slice(0, 1500) + "
            "'\\nSource: ' + Number($json.source_count || 0) + ', valid: ' + "
            "Number($json.observation_count || 0) + ', quarantine: ' + Number($json.quarantine_count || 0) }}",
            (2720, 180),
        ),
        node(
            "Fail execution",
            "n8n-nodes-base.stopAndError",
            1,
            {"errorMessage": "RobinGraph native ingest failed; inspect the preceding quality or Neo4j response node."},
            (2950, 180),
        ),
        node("Finished", "n8n-nodes-base.noOp", 1, {}, (3870, -100)),
    ]

    connections = {
        "Manual Trigger": {"main": [[edge("Build run configuration")]]},
        "Schedule Trigger — daily 02:00 KST": {"main": [[edge("Build run configuration")]]},
        "Build run configuration": {"main": [[edge("Fetch GBIF Korea Aves pages")]]},
        "Fetch GBIF Korea Aves pages": {"main": [[edge("Hash each raw GBIF page")]]},
        "Hash each raw GBIF page": {"main": [[edge("Normalize, validate and deduplicate GBIF")]]},
        "Normalize, validate and deduplicate GBIF": {"main": [[edge("Quality gates passed?")]]},
        "Quality gates passed?": {"main": [[edge("Prepare PostgreSQL GBIF run")], [edge("Notify failure")]]},
        "Prepare PostgreSQL GBIF run": {"main": [[edge("Start PostgreSQL GBIF run")]]},
        "Start PostgreSQL GBIF run": {"main": [[edge("Verify PostgreSQL GBIF run started")]]},
        "Verify PostgreSQL GBIF run started": {"main": [[edge("Build PostgreSQL GBIF source batches")]]},
        "Build PostgreSQL GBIF source batches": {"main": [[edge("Loop Over PostgreSQL GBIF source batches")]]},
        "Loop Over PostgreSQL GBIF source batches": {
            "main": [[edge("Restore GBIF domain payload")], [edge("Append PostgreSQL GBIF source batch")]]
        },
        "Append PostgreSQL GBIF source batch": {"main": [[edge("Verify PostgreSQL GBIF source batch")]]},
        "Verify PostgreSQL GBIF source batch": {"main": [[edge("Loop Over PostgreSQL GBIF source batches")]]},
        "Restore GBIF domain payload": {"main": [[edge("Atomic upsert to Neo4j")]]},
        "Atomic upsert to Neo4j": {"main": [[edge("Verify Neo4j response counts")]]},
        "Verify Neo4j response counts": {"main": [[edge("Atomic load verified?")]]},
        "Atomic load verified?": {"main": [[edge("Prepare PostgreSQL GBIF finalization")], [edge("Notify failure")]]},
        "Prepare PostgreSQL GBIF finalization": {"main": [[edge("Finalize PostgreSQL GBIF release")]]},
        "Finalize PostgreSQL GBIF release": {"main": [[edge("Verify PostgreSQL GBIF release")]]},
        "Verify PostgreSQL GBIF release": {"main": [[edge("Advance n8n cursor")]]},
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
            "saveExecutionProgress": False,
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
