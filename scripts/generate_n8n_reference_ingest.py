"""Generate the n8n-native RobinGraph taxonomy and trait ingest workflow."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from textwrap import dedent
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n" / "robingraph-reference-ingest.json"
POINTS = ROOT / "config" / "collection-points.json"
SOURCES = ROOT / "config" / "source-registry.json"

# MERGE must use indexed stable IDs when loading tens of thousands of claims.
REFERENCE_LABELS = (
    "Taxon", "TaxonConceptSet", "ScientificName", "VernacularName",
    "ExternalIdentifier",
    "EvidenceUnit", "TraitClaim", "TaxonMappingClaim", "TaxonMappingCandidate",
)


def node_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"robingraph:n8n:reference-ingest:{name}"))


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


def edge(target: str, index: int = 0) -> dict[str, object]:
    return {"node": target, "type": "main", "index": index}


def merge(name: str, position: tuple[int, int]) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.merge",
        3.2,
        {"mode": "combine", "combineBy": "combineAll", "options": {}},
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
            "Map the RobinGraph Operations Discord credential after import. "
            "The webhook URL must remain only in n8n's credential store."
        ),
    )


def load_approved_configuration() -> dict[str, dict[str, object]]:
    payload = json.loads(POINTS.read_text(encoding="utf-8"))
    sources = {
        row["source_id"]: row
        for row in json.loads(SOURCES.read_text(encoding="utf-8"))
    }
    wanted = {
        "taxonomy-avilist-v2025b",
        "taxonomy-checklistbank-release",
        "traits-eltontraits-v1",
    }
    selected: dict[str, dict[str, object]] = {}
    for point in payload["collection_points"]:
        point_id = point["collection_point_id"]
        if point_id not in wanted:
            continue
        source = sources[point["source_id"]]
        if not point["enabled"] or point["license_policy_status"] != "allowed":
            raise RuntimeError(f"collection point is not approved: {point_id}")
        if not source["enabled"] or source["license_policy_status"] != "allowed":
            raise RuntimeError(f"source is not approved: {point['source_id']}")
        selected[point_id] = {**point, "source": source}
    if set(selected) != wanted:
        raise RuntimeError(f"missing approved collection points: {sorted(wanted - set(selected))}")
    return selected


def build_configuration_js(points: dict[str, dict[str, object]]) -> str:
    avi = points["taxonomy-avilist-v2025b"]
    col = points["taxonomy-checklistbank-release"]
    elton = points["traits-eltontraits-v1"]
    dataset_match = re.search(r"dataset-(\d+)", str(col["source_release"]))
    doi_match = re.search(r"doi-(.+)$", str(col["source_release"]))
    version = str(col["source_release"]).split(":", 1)[0]
    if not dataset_match or not doi_match:
        raise RuntimeError("ChecklistBank source_release must pin dataset and DOI")
    bundle_sha256 = hashlib.sha256(
        f"{avi['expected_sha256']}:{elton['expected_sha256']}:{col['source_release']}".encode()
    ).hexdigest()
    config = {
        "pipeline_id": "reference-taxonomy-traits",
        "dataset_id": "reference-bundle:avilist-v2025b:eltontraits-v1",
        "source_release": f"reference-bundle:sha256-{bundle_sha256}",
        "bundle_sha256": bundle_sha256,
        "taxonomy_release": avi["source_release"],
        "taxonomy_url": avi["endpoint_uri"],
        "taxonomy_hash": avi["expected_sha256"],
        "taxonomy_expected_rows": 33684,
        "taxonomy_dataset_id": "avilist-dataset:v2025b",
        "taxonomy_concept_set_id": "rg:concept-set:avilist-v2025b",
        "taxonomy_license_uri": avi["source"]["license_uri"],
        "taxonomy_landing_uri": avi["source"]["landing_uri"],
        "checklistbank_dataset_key": int(dataset_match.group(1)),
        "checklistbank_version": version,
        "checklistbank_doi": doi_match.group(1),
        "checklistbank_metadata_url": f"https://api.checklistbank.org/dataset/{dataset_match.group(1)}",
        "checklistbank_search_url": col["endpoint_uri"],
        "checklistbank_license_uri": col["source"]["license_uri"],
        "trait_release": elton["source_release"],
        "trait_url": elton["endpoint_uri"],
        "trait_hash": elton["expected_sha256"],
        "trait_expected_rows": 9995,
        "trait_expected_valid_rows": 9993,
        "trait_dataset_id": "eltontraits-dataset:v1",
        "trait_license_uri": elton["source"]["license_uri"],
        "trait_landing_uri": elton["source"]["landing_uri"],
        "minimum_exact_match_ratio": 0.70,
        # The ingest API accepts at most 500 records per append. Keep each
        # graph batch within that bound and avoid copying the assembled source
        # arrays through later Code nodes.
        "taxonomy_batch_size": 500,
        "trait_claim_batch_size": 500,
        "mapping_candidate_batch_size": 500,
    }
    return (
        "const now = new Date();\n"
        f"const config = {json.dumps(config, ensure_ascii=False)};\n"
        "return [{json: {...config, run_id: `n8n-reference-${$execution.id}`, "
        "retrieved_at: now.toISOString()}}];"
    )


NORMALIZE_AVILIST = r"""
const config = $('Build reference configuration').first().json;
const hash = $('Hash AviList snapshot').first().json.raw_sha256 ?? null;
const ranks = new Set(['order', 'family', 'genus', 'species', 'subspecies']);
const columns = [
  'Sequence', 'Taxon_rank', 'Order', 'Family', 'Family_English_name',
  'Scientific_name', 'Authority', 'Bibliographic_details', 'English_name_AviList',
  'English_name_Clements_v2025', 'English_name_BirdLife_v10', 'Proposal_number',
  'Decision_summary', 'Range', 'Extinct_or_possibly_extinct', 'IUCN_Red_List_Category',
  'BirdLife_DataZone_URL', 'Species_code_Cornell_Lab', 'Birds_of_the_World_URL',
  'AvibaseID', 'Gender_of_genus', 'Type_species_of_genus', 'Type_locality',
  'Title_of_original_description', 'Original_description_URL', 'Protonym'
];
const inputs = $input.all().map(item => item.json);
let sourceRows = inputs;
if (inputs.length === 1 && typeof inputs[0].data === 'string') sourceRows = JSON.parse(inputs[0].data);
const rows = sourceRows.map(raw => {
  if (!Array.isArray(raw)) return raw;
  const mapped = {};
  for (let position = 0; position < columns.length; position += 1) {
    mapped[columns[position]] = raw[position] ?? null;
  }
  return mapped;
}).filter(row => ranks.has(String(row.Taxon_rank || '').toLowerCase()));
const taxa = [];
const links = [];
const identifiers = [];
const last = {order: null, family: null, genus: null, species: null};
const speciesNameCounts = new Map();
const text = value => value == null || String(value).trim() === '' ? null : String(value).trim();
const rankParent = {order: null, family: 'order', genus: 'family', species: 'genus', subspecies: 'species'};

for (const raw of rows) {
  const rank = String(raw.Taxon_rank).toLowerCase();
  const sequence = text(raw.Sequence);
  const scientificName = text(raw.Scientific_name);
  if (!sequence || !scientificName) continue;
  const id = `avilist-taxon:${config.taxonomy_release}:${sequence}`;
  const parentRank = rankParent[rank];
  const parentId = parentRank ? last[parentRank] : null;
  taxa.push({
    id,
    sequence,
    rank,
    scientific_name: scientificName,
    authority: text(raw.Authority),
    order_name: text(raw.Order),
    family_name: text(raw.Family),
    family_english_name: text(raw.Family_English_name),
    english_name: text(raw.English_name_AviList),
    range_text: text(raw.Range),
    extinct_status: text(raw.Extinct_or_possibly_extinct),
    iucn_red_list_category_raw: text(raw.IUCN_Red_List_Category),
    birdlife_url: text(raw.BirdLife_DataZone_URL),
    birds_of_the_world_url: text(raw.Birds_of_the_World_URL),
    source_record_id: `avilist-record:${config.taxonomy_release}:${sequence}`,
    source_uri: config.taxonomy_url,
    retrieved_at: config.retrieved_at
  });
  if (parentId) links.push({parent_id: parentId, child_id: id});
  for (const [scheme, value] of [
    ['avibase', text(raw.AvibaseID)],
    ['cornell-lab-species-code', text(raw.Species_code_Cornell_Lab)]
  ]) {
    if (value) identifiers.push({
      id: `external-id:${scheme}:${value}`,
      taxon_id: id,
      scheme,
      value
    });
  }
  if (rank === 'species') speciesNameCounts.set(scientificName, (speciesNameCounts.get(scientificName) || 0) + 1);
  if (rank === 'order') {
    last.order = id; last.family = null; last.genus = null; last.species = null;
  } else if (rank === 'family') {
    last.family = id; last.genus = null; last.species = null;
  } else if (rank === 'genus') {
    last.genus = id; last.species = null;
  } else if (rank === 'species') {
    last.species = id;
  }
}

const duplicateSpeciesNames = [...speciesNameCounts.values()].filter(count => count > 1).length;
return [{json: {
  taxonomy_sha256: hash,
  taxonomy_source_row_count: rows.length,
  taxonomy_taxon_count: taxa.length,
  taxonomy_link_count: links.length,
  taxonomy_identifier_count: identifiers.length,
  taxonomy_duplicate_species_names: duplicateSpeciesNames,
  taxa,
  taxon_links: links,
  taxon_identifiers: identifiers
}}];
"""


NORMALIZE_ELTON = r"""
const hash = $('Hash EltonTraits snapshot').first().json.raw_sha256 ?? null;
const sourceRows = $input.all().map(item => item.json).filter(row => Object.prototype.hasOwnProperty.call(row, 'Scientific'));
const text = value => value == null || String(value).trim() === '' ? null : String(value).trim();
const optionalNumber = (value, field, reasons) => {
  if (value == null || String(value).trim() === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    reasons.push(`invalid_${field}`);
    return null;
  }
  return parsed;
};
const distribution = (raw, fields, name, reasons, warnings) => {
  const values = {};
  const known = [];
  for (const [key, sourceField] of Object.entries(fields)) {
    const value = optionalNumber(raw[sourceField], `${name}_${key}`, reasons);
    values[key] = value;
    if (value != null) {
      if (value < 0 || value > 100) reasons.push(`out_of_range_${name}_${key}`);
      known.push(value);
    }
  }
  if (known.length) {
    const total = known.reduce((sum, value) => sum + value, 0);
    if (total < 99 || total > 101) {
      reasons.push(`invalid_${name}_sum`);
    } else if (Math.abs(total - 100) > 1e-6) {
      warnings.push(`${name}_total:${total}`);
    }
  }
  return values;
};
const profiles = [];
const invalid = [];
const seenSourceTaxonIds = new Set();
for (const raw of sourceRows) {
  const sourceTaxonId = text(raw.SpecID);
  const scientificName = text(raw.Scientific);
  if (!sourceTaxonId || !scientificName) {
    invalid.push({source_taxon_id: sourceTaxonId, scientific_name: scientificName, reason: 'missing_source_identity'});
    continue;
  }
  if (seenSourceTaxonIds.has(sourceTaxonId)) {
    invalid.push({source_taxon_id: sourceTaxonId, scientific_name: scientificName, reason: 'duplicate_source_taxon_id'});
    continue;
  }
  seenSourceTaxonIds.add(sourceTaxonId);
  const reasons = [];
  const distributionWarnings = [];
  const bodyMass = optionalNumber(raw['BodyMass-Value'], 'body_mass', reasons);
  if (bodyMass != null && bodyMass <= 0) reasons.push('invalid_body_mass');
  const nocturnal = optionalNumber(raw.Nocturnal, 'nocturnal', reasons);
  if (nocturnal != null && nocturnal !== 0 && nocturnal !== 1) reasons.push('invalid_nocturnal');
  const pelagicSpecialist = optionalNumber(raw.PelagicSpecialist, 'pelagic_specialist', reasons);
  if (pelagicSpecialist != null && pelagicSpecialist !== 0 && pelagicSpecialist !== 1) reasons.push('invalid_pelagic_specialist');
  const dietDistribution = distribution(raw, {
    invertebrate: 'Diet-Inv', endotherm_vertebrate: 'Diet-Vend',
    ectotherm_vertebrate: 'Diet-Vect', fish: 'Diet-Vfish',
    unknown_vertebrate: 'Diet-Vunk', carrion: 'Diet-Scav',
    fruit: 'Diet-Fruit', nectar: 'Diet-Nect', seed: 'Diet-Seed', other_plant: 'Diet-PlantO'
  }, 'diet_distribution', reasons, distributionWarnings);
  const foragingDistribution = distribution(raw, {
    below_water_surface: 'ForStrat-watbelowsurf', around_water_surface: 'ForStrat-wataroundsurf',
    ground: 'ForStrat-ground', understory: 'ForStrat-understory',
    mid_high: 'ForStrat-midhigh', canopy: 'ForStrat-canopy', aerial: 'ForStrat-aerial'
  }, 'foraging_distribution', reasons, distributionWarnings);
  if (reasons.length) {
    invalid.push({source_taxon_id: sourceTaxonId, scientific_name: scientificName, reason: reasons.join(',')});
    continue;
  }
  profiles.push({
    source_taxon_id: sourceTaxonId,
    scientific_name: scientificName,
    source_taxonomy: text(raw.Taxo),
    body_mass_g: bodyMass,
    body_mass_source: text(raw['BodyMass-Source']),
    body_mass_spec_level: text(raw['BodyMass-SpecLevel']),
    nocturnal,
    pelagic_specialist: pelagicSpecialist,
    diet_category: text(raw['Diet-5Cat']),
    diet_source: text(raw['Diet-Source']),
    diet_certainty: text(raw['Diet-Certainty']),
    diet_distribution: dietDistribution,
    foraging_distribution: foragingDistribution,
    distribution_warnings: distributionWarnings,
    foraging_source: text(raw['ForStrat-Source']),
    foraging_spec_level: text(raw['ForStrat-SpecLevel'])
  });
}
return [{json: {
  trait_sha256: hash,
  trait_source_row_count: sourceRows.length,
  trait_valid_row_count: profiles.length,
  trait_invalid_row_count: invalid.length,
  trait_invalid_rows: invalid,
  trait_profiles: profiles
}}];
"""


VALIDATE_CHECKLISTBANK = r"""
const config = $('Build reference configuration').first().json;
const response = $input.first().json;
const body = response.body ?? response;
const status = Number(response.statusCode ?? 200);
const releaseOk = status >= 200 && status < 300
  && Number(body.key) === Number(config.checklistbank_dataset_key)
  && String(body.version || '') === config.checklistbank_version
  && String(body.doi || '') === config.checklistbank_doi
  && String(body.origin || '') === 'release';
return [{json: {
  checklistbank_release_ok: releaseOk,
  checklistbank_status: status,
  checklistbank_key: body.key ?? null,
  checklistbank_version: body.version ?? null,
  checklistbank_doi: body.doi ?? null,
  checklistbank_title: body.title ?? null,
  checklistbank_failure_reason: releaseOk ? '' : 'Pinned ChecklistBank release metadata did not match'
}}];
"""


ASSEMBLE_REFERENCE = r"""
const config = $('Build reference configuration').first().json;
const input = $input.first().json;
const speciesByName = new Map();
for (const taxon of input.taxa || []) {
  if (taxon.rank !== 'species') continue;
  const list = speciesByName.get(taxon.scientific_name) || [];
  list.push(taxon);
  speciesByName.set(taxon.scientific_name, list);
}
const claims = [];
const candidates = [];
let exactMatches = 0;
const addClaim = (profile, taxon, traitName, values) => claims.push({
  id: `trait-claim:eltontraits-v1:${profile.source_taxon_id}:${traitName}`,
  trait_name: traitName,
  taxon_id: taxon.id,
  source_taxon_id: profile.source_taxon_id,
  source_scientific_name: profile.scientific_name,
  source_record_id: `eltontraits-record:v1:${profile.source_taxon_id}`,
  evidence_id: `eltontraits-evidence:v1:${profile.source_taxon_id}`,
  source_uri: `${config.trait_url}#SpecID=${encodeURIComponent(profile.source_taxon_id)}`,
  value_num: null,
  value_text: null,
  value_boolean: null,
  value_json: null,
  unit: null,
  source_note: null,
  certainty: null,
  ...values
});

for (const profile of input.trait_profiles || []) {
  const matches = speciesByName.get(profile.scientific_name) || [];
  if (matches.length !== 1) {
    candidates.push({
      id: `taxon-mapping-candidate:eltontraits-v1:${profile.source_taxon_id}`,
      source_taxon_id: profile.source_taxon_id,
      source_scientific_name: profile.scientific_name,
      source_taxonomy: profile.source_taxonomy,
      profile_json: JSON.stringify(profile),
      reason_code: matches.length ? 'ambiguous_exact_name' : 'exact_name_not_found',
      suggested_lookup_uri: `${config.checklistbank_search_url}?q=${encodeURIComponent(profile.scientific_name)}`,
      source_record_id: `eltontraits-record:v1:${profile.source_taxon_id}`,
      source_uri: `${config.trait_url}#SpecID=${encodeURIComponent(profile.source_taxon_id)}`
    });
    continue;
  }
  exactMatches += 1;
  const taxon = matches[0];
  if (profile.body_mass_g != null) addClaim(profile, taxon, 'body_mass', {
    value_num: profile.body_mass_g, unit: 'g', source_note: profile.body_mass_source,
    certainty: profile.body_mass_spec_level
  });
  if (profile.nocturnal != null) addClaim(profile, taxon, 'nocturnal', {
    value_boolean: profile.nocturnal === 1
  });
  if (profile.pelagic_specialist != null) addClaim(profile, taxon, 'pelagic_specialist', {
    value_boolean: profile.pelagic_specialist === 1
  });
  if (profile.diet_category != null) addClaim(profile, taxon, 'diet_category', {
    value_text: profile.diet_category, source_note: profile.diet_source, certainty: profile.diet_certainty
  });
  if (Object.values(profile.diet_distribution).some(value => value != null)) addClaim(profile, taxon, 'diet_distribution', {
    value_json: JSON.stringify(profile.diet_distribution), unit: 'percent',
    source_note: [profile.diet_source, ...(profile.distribution_warnings || []).filter(warning => warning.startsWith('diet_distribution_total:'))].filter(Boolean).join('; ') || null,
    certainty: profile.diet_certainty
  });
  if (Object.values(profile.foraging_distribution).some(value => value != null)) addClaim(profile, taxon, 'foraging_strata_distribution', {
    value_json: JSON.stringify(profile.foraging_distribution), unit: 'percent',
    source_note: [profile.foraging_source, ...(profile.distribution_warnings || []).filter(warning => warning.startsWith('foraging_distribution_total:'))].filter(Boolean).join('; ') || null,
    certainty: profile.foraging_spec_level
  });
}

const validTraitRows = Number(input.trait_valid_row_count || 0);
const matchRatio = validTraitRows ? exactMatches / validTraitRows : 0;
const reasons = [];
if (input.taxonomy_sha256 !== config.taxonomy_hash) reasons.push('AviList SHA-256 mismatch');
if (Number(input.taxonomy_source_row_count) !== config.taxonomy_expected_rows) reasons.push('AviList row count mismatch');
if (Number(input.taxonomy_taxon_count) !== config.taxonomy_expected_rows) reasons.push('AviList valid taxon count mismatch');
if (Number(input.taxonomy_duplicate_species_names) !== 0) reasons.push('AviList species names are not unique');
if (input.trait_sha256 !== config.trait_hash) reasons.push('EltonTraits SHA-256 mismatch');
if (Number(input.trait_source_row_count) !== config.trait_expected_rows) reasons.push('EltonTraits row count mismatch');
if (validTraitRows !== config.trait_expected_valid_rows) reasons.push('EltonTraits valid row count mismatch');
if (input.checklistbank_release_ok !== true) reasons.push(input.checklistbank_failure_reason || 'ChecklistBank release mismatch');
if (matchRatio < config.minimum_exact_match_ratio) reasons.push(`Exact trait mapping ratio ${matchRatio.toFixed(4)} below gate`);
if (!claims.length) reasons.push('No trait claims were produced');

return [{json: {
  ...config,
  ready_to_load: reasons.length === 0,
  failure_reason: reasons.join('; '),
  taxonomy_sha256: input.taxonomy_sha256,
  trait_sha256: input.trait_sha256,
  taxonomy_taxon_count: Number(input.taxonomy_taxon_count || 0),
  taxonomy_link_count: Number(input.taxonomy_link_count || 0),
  taxonomy_identifier_count: Number(input.taxonomy_identifier_count || 0),
  trait_source_row_count: Number(input.trait_source_row_count || 0),
  trait_valid_row_count: validTraitRows,
  trait_invalid_row_count: Number(input.trait_invalid_row_count || 0),
  trait_exact_match_count: exactMatches,
  trait_exact_match_ratio: matchRatio,
  trait_claim_count: claims.length,
  mapping_candidate_count: candidates.length,
  taxa: input.taxa,
  taxon_links: input.taxon_links,
  taxon_identifiers: input.taxon_identifiers,
  trait_claims: claims,
  mapping_candidates: candidates
}}];
"""


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


def compact_cypher(statement: str) -> str:
    return " ".join(dedent(statement).split())


def ingest_api_node(
    name: str,
    path_expression: str,
    position: tuple[int, int],
    *,
    method: str = "POST",
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "method": method,
        "url": f"={{{{ $env.ROBINGRAPH_INGEST_API_URL + {path_expression} }}}}",
        "sendHeaders": True,
        "headerParameters": {"parameters": [{
            "name": "Authorization",
            "value": "={{ 'Bearer ' + $env.ROBINGRAPH_INGEST_INTERNAL_TOKEN }}",
        }]},
        "options": {"response": {"response": {"neverError": True, "responseFormat": "json"}}},
    }
    if method != "GET":
        parameters.update({
            "sendBody": True,
            "contentType": "json",
            "specifyBody": "json",
            "jsonBody": "={{ $json.ingest_request }}",
        })
    return node(
        name, "n8n-nodes-base.httpRequest", 4.4, parameters, position,
        onError="continueRegularOutput", retryOnFail=True, maxTries=3,
        waitBetweenTries=2000,
        notes="Authenticated PostgreSQL ingest control-plane request; secrets stay in n8n environment variables.",
    )


START_STATEMENT = compact_cypher(
    """
    MERGE (concept_set:TaxonConceptSet {id: $taxonomy_concept_set_id})
    SET concept_set.title = 'AviList global avian checklist',
        concept_set.version = $taxonomy_release, concept_set.source_uri = $taxonomy_landing_uri,
        concept_set.snapshot_uri = $taxonomy_url, concept_set.snapshot_sha256 = $taxonomy_sha256,
        concept_set.retrieved_at = $retrieved_at,
        concept_set.dataset_id = $dataset_id, concept_set.policy_status = 'allowed',
        concept_set.source_record_ids = []
    RETURN concept_set.id AS initialized_concept_set_id
    """
)


TAXONOMY_BATCH_STATEMENT = compact_cypher(
    """
    MATCH (concept_set:TaxonConceptSet {id: $taxonomy_concept_set_id})
    CALL {
      WITH concept_set
      UNWIND $taxa AS row
      MERGE (taxon:Taxon {id: row.id})
      SET taxon:BirdTaxon, taxon.source_id = 'avilist-v2025b',
          taxon.source_release = $taxonomy_release, taxon.source_taxon_id = row.sequence,
          taxon.rank = row.rank, taxon.scientific_name = row.scientific_name,
          taxon.authority = row.authority, taxon.order_name = row.order_name,
          taxon.family_name = row.family_name, taxon.family_english_name = row.family_english_name,
          taxon.range_text = row.range_text, taxon.extinct_status = row.extinct_status,
          taxon.iucn_red_list_category_raw = row.iucn_red_list_category_raw,
          taxon.birdlife_url = row.birdlife_url,
          taxon.birds_of_the_world_url = row.birds_of_the_world_url,
          taxon.retrieved_at = row.retrieved_at,
          taxon.dataset_id = $dataset_id, taxon.source_record_id = row.source_record_id,
          taxon.policy_status = 'allowed'
      MERGE (scientific_name:ScientificName {id: row.id + ':scientific-name'})
      SET scientific_name.full_name = row.scientific_name,
          scientific_name.authorship = row.authority, scientific_name.nomenclatural_code = 'ICZN'
      MERGE (taxon)-[:HAS_ACCEPTED_NAME]->(scientific_name)
      FOREACH (_ IN CASE WHEN row.english_name IS NULL THEN [] ELSE [1] END |
        MERGE (vernacular:VernacularName {id: row.id + ':vernacular:en:avilist'})
        SET vernacular.name = row.english_name, vernacular.language = 'en',
            vernacular.status = 'source-preferred', vernacular.source_release = $taxonomy_release,
            vernacular.dataset_id = $dataset_id, vernacular.source_record_id = row.source_record_id,
            vernacular.policy_status = 'allowed'
        MERGE (taxon)-[:HAS_VERNACULAR_NAME]->(vernacular)
      )
      MERGE (taxon)-[:IN_CONCEPT_SET]->(concept_set)
      RETURN count(*) AS loaded_taxa
    }
    CALL {
      UNWIND $identifiers AS row
      MATCH (taxon:Taxon {id: row.taxon_id})
      MERGE (identifier:ExternalIdentifier {id: row.id})
      SET identifier.scheme = row.scheme, identifier.value = row.value
      MERGE (taxon)-[:HAS_EXTERNAL_IDENTIFIER]->(identifier)
      RETURN count(*) AS loaded_identifiers
    }
    CALL {
      UNWIND $links AS row
      MATCH (parent:Taxon {id: row.parent_id})
      MATCH (child:Taxon {id: row.child_id})
      MERGE (parent)-[:PARENT_OF {concept_set_id: $taxonomy_concept_set_id}]->(child)
      RETURN count(*) AS loaded_taxon_links
    }
    RETURN $batch_index AS batch_index, $batch_count AS batch_count,
           loaded_taxa, loaded_identifiers, loaded_taxon_links
    """
)


TRAIT_BATCH_STATEMENT = compact_cypher(
    """
    CALL {
      UNWIND $claims AS row
      MATCH (taxon:Taxon {id: row.taxon_id})
      MERGE (evidence:EvidenceUnit {id: row.evidence_id})
      SET evidence.evidence_type = 'literature_dataset_row', evidence.locator = row.source_uri,
          evidence.accessed_at = $retrieved_at,
          evidence.citation = 'Wilman et al. (2014), EltonTraits 1.0',
          evidence.dataset_id = $dataset_id, evidence.source_record_id = row.source_record_id,
          evidence.policy_status = 'allowed'
      MERGE (mapping:TaxonMappingClaim {id: 'eltontraits-mapping:v1:' + row.source_taxon_id})
      SET mapping.method = 'exact_scientific_name_unique_in_avilist_species',
          mapping.source_scientific_name = row.source_scientific_name,
          mapping.source_taxon_id = row.source_taxon_id,
          mapping.resolution_status = 'accepted_automatic', mapping.confidence = 1.0,
          mapping.taxonomy_release = $taxonomy_release,
          mapping.dataset_id = $dataset_id, mapping.source_record_id = row.source_record_id,
          mapping.policy_status = 'allowed'
      MERGE (mapping)-[:PROPOSES_TAXON]->(taxon)
      MERGE (claim:TraitClaim {id: row.id})
      SET claim.trait_name = row.trait_name, claim.value_num = row.value_num,
          claim.value_text = row.value_text, claim.value_boolean = row.value_boolean,
          claim.value_json = row.value_json, claim.unit = row.unit,
          claim.source_note = row.source_note, claim.certainty = row.certainty,
          claim.source_release = $trait_release, claim.retrieved_at = $retrieved_at,
          claim.dataset_id = $dataset_id, claim.source_record_id = row.source_record_id,
          claim.policy_status = 'allowed'
      MERGE (claim)-[:ASSERTS_ABOUT]->(taxon)
      MERGE (claim)-[:SUPPORTED_BY]->(evidence)
      RETURN count(*) AS loaded_trait_claims
    }
    CALL {
      UNWIND $candidates AS row
      MERGE (candidate:TaxonMappingCandidate {id: row.id})
      SET candidate.source_taxon_id = row.source_taxon_id,
          candidate.source_scientific_name = row.source_scientific_name,
          candidate.source_taxonomy = row.source_taxonomy,
          candidate.profile_json = row.profile_json,
          candidate.reason_code = row.reason_code,
          candidate.suggested_lookup_uri = row.suggested_lookup_uri,
          candidate.resolution_status = 'open', candidate.last_seen_run_id = $run_id,
          candidate.last_seen_at = $retrieved_at,
          candidate.dataset_id = $dataset_id, candidate.source_record_id = row.source_record_id,
          candidate.policy_status = 'allowed'
      RETURN count(*) AS loaded_mapping_candidates
    }
    RETURN $batch_index AS batch_index, $batch_count AS batch_count,
           loaded_trait_claims, loaded_mapping_candidates
    """
)


FINALIZE_STATEMENT = compact_cypher(
    """
    MATCH (concept_set:TaxonConceptSet {id: $taxonomy_concept_set_id})
    CALL {
      WITH concept_set
      MATCH (external:ExternalTaxonConcept:BirdTaxon)
      MATCH (taxon:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(concept_set)
      WHERE external.rank = taxon.rank AND external.scientific_name = taxon.scientific_name
      MERGE (mapping:TaxonMappingClaim {id: 'gbif-avilist-exact:' + external.id + ':' + taxon.id})
      SET mapping.method = 'exact_scientific_name_and_rank', mapping.confidence = 1.0,
          mapping.resolution_status = 'candidate', mapping.taxonomy_release = $taxonomy_release,
          mapping.created_by_run_id = $run_id
      MERGE (external)-[:HAS_MAPPING_CLAIM]->(mapping)
      MERGE (mapping)-[:PROPOSES_TAXON]->(taxon)
      RETURN count(*) AS gbif_mapping_claims
    }
    RETURN $run_id AS finalized_run_id, $taxonomy_release AS taxonomy_active_release,
           $trait_release AS trait_active_release, gbif_mapping_claims
    """
)


def community_cypher_expression(statement: str, *, source_node: str | None = None) -> str:
    keys = sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", statement)))
    source = "$json" if source_node is None else "$(" + json.dumps(source_node) + ").item.json"
    values = ",".join(
        json.dumps(key) + ": literal(" + source + "[" + json.dumps(key) + "])" for key in keys
    )
    return (
        "={{ (() => { "
        + CYPHER_LITERAL_JS
        + "const values = {"
        + values
        + "}; return "
        + json.dumps(statement)
        + r".replace(/\$([A-Za-z_][A-Za-z0-9_]*)/g, (_, key) => values[key]); })() }}"
    )


PREPARE_BEGIN_REQUEST = r"""
const expected = $('Assemble claims and quality gates').first().json;
const {taxa, taxon_identifiers, taxon_links, trait_claims, mapping_candidates, ...context} = expected;
return [{json: {...context, ingest_request: {
  dataset: {
    id: expected.dataset_id,
    source_id: 'reference-taxonomy-traits',
    name: 'AviList and EltonTraits approved reference bundle',
    provider: 'AviList Core Team / Wilman et al. / Catalogue of Life',
    landing_uri: expected.taxonomy_landing_uri,
    release_strategy: 'versioned',
    policy_status: 'allowed',
    metadata: {
      taxonomy_dataset_id: expected.taxonomy_dataset_id,
      trait_dataset_id: expected.trait_dataset_id,
      taxonomy_license_uri: expected.taxonomy_license_uri,
      trait_license_uri: expected.trait_license_uri,
      checklistbank_license_uri: expected.checklistbank_license_uri,
    },
  },
  release: {
    id: expected.source_release,
    release_key: expected.source_release,
    retrieved_at: expected.retrieved_at,
    content_sha256: expected.bundle_sha256,
    raw_object_uri: expected.taxonomy_url,
    metadata: {
      concept_set_id: expected.taxonomy_concept_set_id,
      taxonomy_release: expected.taxonomy_release,
      taxonomy_sha256: expected.taxonomy_sha256,
      trait_release: expected.trait_release,
      trait_sha256: expected.trait_sha256,
      checklistbank_dataset_key: expected.checklistbank_dataset_key,
    },
  },
  run: {
    id: expected.run_id,
    pipeline_id: expected.pipeline_id,
    started_at: expected.retrieved_at,
    manifest: {
      orchestrator: 'n8n', workflow: 'reference-taxonomy-traits',
      expected_taxa: expected.taxonomy_taxon_count,
      expected_trait_claims: expected.trait_claim_count,
      expected_mapping_candidates: expected.mapping_candidate_count,
    },
  },
}}}];
"""


VERIFY_POSTGRES_START = r"""
const expected = $('Prepare PostgreSQL reference run').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const version = response.state_version;
const startOk = !errorText && response.status === 'started'
  && Number.isSafeInteger(version) && version >= 0;
return [{json: {...expected, expected_state_version: version, start_ok: startOk,
  failure_reason: startOk ? '' : (errorText || 'PostgreSQL did not start the reference run')}}];
"""


VERIFY_START = r"""
const expected = $('Verify PostgreSQL reference run started').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || '');
const startOk = !errorText && response.initialized_concept_set_id === expected.taxonomy_concept_set_id;
return [{json: {...expected, start_ok: startOk,
  failure_reason: startOk ? '' : (errorText || 'Neo4j did not initialize the reference domain projection')}}];
"""


PREPARE_TAXONOMY_BATCHES = r"""
const source = $('Assemble claims and quality gates').first().json;
const size = source.taxonomy_batch_size;
const batches = [];
for (let offset = 0; offset < source.taxa.length; offset += size) {
  const taxa = source.taxa.slice(offset, offset + size);
  const ids = new Set(taxa.map(row => row.id));
  batches.push({
    taxa,
    identifiers: source.taxon_identifiers.filter(row => ids.has(row.taxon_id)),
    links: source.taxon_links.filter(row => ids.has(row.child_id))
  });
}
return batches.map((batch, index) => ({json: {
  run_id: source.run_id,
  dataset_id: source.dataset_id,
  retrieved_at: source.retrieved_at,
  taxonomy_release: source.taxonomy_release,
  taxonomy_concept_set_id: source.taxonomy_concept_set_id,
  taxonomy_dataset_id: source.taxonomy_dataset_id,
  taxonomy_sha256: source.taxonomy_sha256,
  batch_index: index,
  batch_count: batches.length,
  ...batch
}}));
"""


PREPARE_TAXONOMY_APPEND = r"""
const batch = $input.first().json;
const records = batch.taxa.map(row => ({
  id: row.source_record_id,
  external_id: String(row.sequence),
  record_type: 'taxon_concept',
  raw_object_uri: row.source_uri,
  raw_sha256: batch.taxonomy_sha256,
  retrieved_at: row.retrieved_at,
  parser_version: 'reference-taxonomy-v3',
  license_policy_status: 'allowed',
  payload: {
    source_id: 'avilist', scientific_name: row.scientific_name,
    rank: row.rank, taxonomy_release: batch.taxonomy_release,
  },
}));
return [{json: {...batch, ingest_request: {records, quarantine_items: []}}}];
"""


VERIFY_TAXONOMY_APPEND = r"""
const batch = $('Prepare PostgreSQL taxonomy source batch').item.json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const appendOk = !errorText && response.status === 'appended';
return [{json: {...batch, append_ok: appendOk,
  failure_reason: appendOk ? '' : (errorText || 'PostgreSQL did not append the taxonomy source batch')}}];
"""


VERIFY_TAXONOMY_BATCHES = r"""
const expected = $('Assemble claims and quality gates').first().json;
const {taxa, taxon_identifiers, taxon_links, trait_claims, mapping_candidates, ...context} = expected;
const rows = $input.all().map(item => item.json);
const errors = rows.map(row => String(row.error?.message || row.error || row.message || '')).filter(Boolean);
const indexes = new Set(rows.map(row => Number(row.batch_index)).filter(Number.isInteger));
const batchCount = rows.length ? Number(rows[0].batch_count) : 0;
const loadedTaxa = rows.reduce((sum, row) => sum + Number(row.loaded_taxa || 0), 0);
const loadedLinks = rows.reduce((sum, row) => sum + Number(row.loaded_taxon_links || 0), 0);
const loadedIdentifiers = rows.reduce((sum, row) => sum + Number(row.loaded_identifiers || 0), 0);
const taxonomyLoadOk = !errors.length && batchCount > 0 && indexes.size === batchCount && rows.length === batchCount
  && loadedTaxa === expected.taxonomy_taxon_count
  && loadedLinks === expected.taxonomy_link_count
  && loadedIdentifiers === expected.taxonomy_identifier_count;
return [{json: {...context,
  taxonomy_load_ok: taxonomyLoadOk,
  loaded_taxa: loadedTaxa,
  loaded_taxon_links: loadedLinks,
  loaded_taxon_identifiers: loadedIdentifiers,
  failure_reason: taxonomyLoadOk ? '' : (errors.join('; ') || 'Taxonomy batch counts did not match')
}}];
"""


PREPARE_TRAIT_BATCHES = r"""
const source = $('Assemble claims and quality gates').first().json;
const batches = [];
for (let offset = 0; offset < source.trait_claims.length; offset += source.trait_claim_batch_size) {
  batches.push({claims: source.trait_claims.slice(offset, offset + source.trait_claim_batch_size), candidates: []});
}
for (let offset = 0; offset < source.mapping_candidates.length; offset += source.mapping_candidate_batch_size) {
  batches.push({claims: [], candidates: source.mapping_candidates.slice(offset, offset + source.mapping_candidate_batch_size)});
}
return batches.map((batch, index) => ({json: {
  run_id: source.run_id,
  dataset_id: source.dataset_id,
  retrieved_at: source.retrieved_at,
  taxonomy_release: source.taxonomy_release,
  trait_release: source.trait_release,
  trait_dataset_id: source.trait_dataset_id,
  trait_sha256: source.trait_sha256,
  batch_index: index,
  batch_count: batches.length,
  ...batch
}}));
"""


PREPARE_TRAIT_APPEND = r"""
const batch = $input.first().json;
const byRecord = new Map();
for (const row of [...batch.claims, ...batch.candidates]) {
  if (!byRecord.has(row.source_record_id)) byRecord.set(row.source_record_id, row);
}
const records = [...byRecord.values()].map(row => ({
  id: row.source_record_id,
  // The shared reference release also contains AviList sequence numbers.
  // Namespace EltonTraits ids so PostgreSQL's release/external-id key is unique.
  external_id: `eltontraits:${row.source_taxon_id}`,
  record_type: 'trait_profile',
  raw_object_uri: row.source_uri,
  raw_sha256: batch.trait_sha256,
  retrieved_at: batch.retrieved_at,
  parser_version: 'reference-traits-v3',
  license_policy_status: 'allowed',
  payload: {
    source_id: 'eltontraits', scientific_name: row.source_scientific_name,
    trait_release: batch.trait_release,
  },
}));
const quarantine_items = batch.candidates.map(row => ({
  record_key: row.source_record_id.slice(0, 200),
  stage: 'resolve', reason_code: row.reason_code, severity: 'warning',
  rule_version: 'reference-traits-v3',
  raw_value_redacted: {source_taxon_id: row.source_taxon_id, scientific_name: row.source_scientific_name},
}));
return [{json: {...batch, ingest_request: {records, quarantine_items}}}];
"""


VERIFY_TRAIT_APPEND = r"""
const batch = $('Prepare PostgreSQL trait source batch').item.json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const appendOk = !errorText && response.status === 'appended';
return [{json: {...batch, append_ok: appendOk,
  failure_reason: appendOk ? '' : (errorText || 'PostgreSQL did not append the trait source batch')}}];
"""


VERIFY_TRAIT_BATCHES = r"""
const expected = $('Assemble claims and quality gates').first().json;
const {taxa, taxon_identifiers, taxon_links, trait_claims, mapping_candidates, ...context} = expected;
const rows = $input.all().map(item => item.json);
const errors = rows.map(row => String(row.error?.message || row.error || row.message || '')).filter(Boolean);
const indexes = new Set(rows.map(row => Number(row.batch_index)).filter(Number.isInteger));
const batchCount = rows.length ? Number(rows[0].batch_count) : 0;
const loadedClaims = rows.reduce((sum, row) => sum + Number(row.loaded_trait_claims || 0), 0);
const loadedCandidates = rows.reduce((sum, row) => sum + Number(row.loaded_mapping_candidates || 0), 0);
const traitLoadOk = !errors.length && batchCount > 0 && indexes.size === batchCount && rows.length === batchCount
  && loadedClaims === expected.trait_claim_count
  && loadedCandidates === expected.mapping_candidate_count;
return [{json: {...context,
  trait_load_ok: traitLoadOk,
  loaded_trait_claims: loadedClaims,
  loaded_mapping_candidates: loadedCandidates,
  failure_reason: traitLoadOk ? '' : (errors.join('; ') || 'Trait batch counts did not match')
}}];
"""


VERIFY_DOMAIN_FINALIZE = r"""
const expected = $('Verify trait batches').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || '');
const finalizeOk = !errorText
  && response.finalized_run_id === expected.run_id
  && response.taxonomy_active_release === expected.taxonomy_release
  && response.trait_active_release === expected.trait_release;
return [{json: {...expected,
  domain_finalize_ok: finalizeOk,
  loaded_taxa: expected.taxonomy_taxon_count,
  loaded_trait_claims: expected.trait_claim_count,
  loaded_mapping_candidates: expected.mapping_candidate_count,
  gbif_mapping_claims: Number(response.gbif_mapping_claims || 0),
  failure_reason: finalizeOk ? '' : (errorText || 'Reference domain finalization failed')
}}];
"""


PREPARE_FINALIZE_REQUEST = r"""
const source = $input.first().json;
return [{json: {...source, ingest_request: {
  counts: {
    source_records: source.taxonomy_taxon_count + source.trait_valid_row_count,
    taxa: source.loaded_taxa,
    taxon_links: source.loaded_taxon_links,
    trait_claims: source.loaded_trait_claims,
    mapping_candidates: source.loaded_mapping_candidates,
    gbif_mapping_claims: source.gbif_mapping_claims,
  },
  cursor: {
    concept_set_id: source.taxonomy_concept_set_id,
    taxonomy_release: source.taxonomy_release,
    trait_release: source.trait_release,
  },
  expected_state_version: source.expected_state_version,
}}}];
"""


VERIFY_FINALIZE = r"""
const expected = $('Prepare PostgreSQL reference finalization').first().json;
const response = $input.first().json;
const errorText = String(response.error?.message || response.error || response.message || response.detail || '');
const finalizeOk = !errorText && response.status === 'finalized'
  && response.state_version === expected.expected_state_version + 1;
return [{json: {...expected,
  finalize_ok: finalizeOk,
  failure_reason: finalizeOk ? '' : (errorText || 'PostgreSQL reference activation failed')
}}];
"""


def neo4j_node(
    name: str, statement: str, position: tuple[int, int], *, source_node: str | None = None
) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-neo4j.neo4j",
        1,
        {
            "resource": "graphDb",
            "operation": "executeQuery",
            "cypherQuery": community_cypher_expression(statement, source_node=source_node),
        },
        position,
        credentials={"neo4jApi": {"id": "DvmTD1qB0Kb7TRml", "name": "Neo4j"}},
        onError="continueRegularOutput",
        alwaysOutputData=True,
        notes=(
            "Uses the Neo4j community node. External values are encoded as Cypher literals and substituted "
            "only into a fixed query template because this node version has no parameter input."
        ),
    )


def main() -> None:
    points = load_approved_configuration()
    build_config = build_configuration_js(points)
    nodes: list[dict[str, object]] = [
        node("Manual Trigger", "n8n-nodes-base.manualTrigger", 1, {}, (-1380, -80)),
        node(
            "Schedule Trigger — Sunday 03:00 KST",
            "n8n-nodes-base.scheduleTrigger",
            1.2,
            {"rule": {"interval": [{"field": "cronExpression", "expression": "0 3 * * 0"}]}},
            (-1380, 80),
        ),
        code(
            "Build reference configuration",
            build_config,
            (-1160, 0),
            notes="Generated from enabled, allowed collection points. Re-generate after changing pinned releases or hashes.",
        ),
        node(
            "Fetch AviList snapshot",
            "n8n-nodes-base.httpRequest",
            4.4,
            {
                "url": "={{ $json.taxonomy_url }}",
                "options": {
                    "response": {"response": {"fullResponse": True, "responseFormat": "text"}},
                    "timeout": 180000,
                },
            },
            (-930, -360),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
        ),
        node(
            "Hash AviList snapshot",
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
            (-690, -470),
        ),
        code("Normalize AviList taxonomy", NORMALIZE_AVILIST, (-210, -360)),
        node(
            "Fetch EltonTraits snapshot",
            "n8n-nodes-base.httpRequest",
            4.4,
            {
                "url": "={{ $json.trait_url }}",
                "options": {
                    "response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}},
                    "timeout": 180000,
                },
            },
            (-930, 0),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
        ),
        node(
            "Hash EltonTraits snapshot",
            "n8n-nodes-base.crypto",
            2,
            {
                "action": "hash",
                "binaryData": True,
                "binaryPropertyName": "data",
                "type": "SHA256",
                "dataPropertyName": "raw_sha256",
                "encoding": "hex",
            },
            (-690, -80),
        ),
        node(
            "Extract EltonTraits TSV",
            "n8n-nodes-base.extractFromFile",
            1.1,
            {
                "operation": "csv",
                "binaryPropertyName": "data",
                "options": {
                    "delimiter": "\t",
                    "encoding": "latin1",
                    "headerRow": True,
                    "includeEmptyCells": True,
                    "relaxQuotes": True,
                },
            },
            (-690, 80),
        ),
        code("Restore EltonTraits snapshot binary", "const item = $('Fetch EltonTraits snapshot').first(); if (!item.binary?.data) throw new Error('EltonTraits snapshot binary missing'); return [{json: $input.first().json, binary: item.binary}];", (-550, -40)),
        code("Normalize EltonTraits", NORMALIZE_ELTON, (-210, 0)),
        node(
            "Fetch pinned ChecklistBank release",
            "n8n-nodes-base.httpRequest",
            4.4,
            {
                "url": "={{ $json.checklistbank_metadata_url }}",
                "options": {
                    "response": {"response": {"fullResponse": True, "neverError": True, "responseFormat": "json"}},
                    "timeout": 120000,
                },
            },
            (-690, 330),
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=5000,
            onError="continueRegularOutput",
        ),
        code("Validate ChecklistBank release", VALIDATE_CHECKLISTBANK, (-450, 330)),
        merge("Join taxonomy and traits", (40, -160)),
        merge("Join approved reference sources", (270, 0)),
        code("Assemble claims and quality gates", ASSEMBLE_REFERENCE, (510, 0)),
        boolean_if("Reference quality gates passed?", "={{ $json.ready_to_load }}", (760, 0)),
        code("Prepare PostgreSQL reference run", PREPARE_BEGIN_REQUEST, (1010, -180)),
        ingest_api_node("Start PostgreSQL reference run", "'/internal/v1/ingest/begin'", (1250, -180)),
        code("Verify PostgreSQL reference run started", VERIFY_POSTGRES_START, (1490, -180)),
        boolean_if("PostgreSQL reference run started?", "={{ $json.start_ok }}", (1730, -180)),
        neo4j_node("Initialize reference domain projection", START_STATEMENT, (1970, -180)),
        code("Verify reference domain initialized", VERIFY_START, (2210, -180)),
        boolean_if("Reference domain initialized?", "={{ $json.start_ok }}", (2450, -180)),
        code("Prepare taxonomy batches", PREPARE_TAXONOMY_BATCHES, (2690, -300)),
        node(
            "Loop Over taxonomy batches",
            "n8n-nodes-base.splitInBatches",
            3,
            {"batchSize": 1, "options": {}},
            (2930, -300),
        ),
        code("Prepare PostgreSQL taxonomy source batch", PREPARE_TAXONOMY_APPEND, (3170, -300)),
        ingest_api_node(
            "Append PostgreSQL taxonomy source batch",
            "('/internal/v1/ingest/' + $json.run_id + '/append')",
            (3410, -300),
        ),
        boolean_if("PostgreSQL taxonomy source batch appended?", "={{ $json.status === 'appended' }}", (3650, -300)),
        neo4j_node(
            "Upsert AviList taxonomy batch", TAXONOMY_BATCH_STATEMENT, (3890, -300),
            source_node="Prepare PostgreSQL taxonomy source batch",
        ),
        code("Verify taxonomy batches", VERIFY_TAXONOMY_BATCHES, (3890, -300)),
        boolean_if("Taxonomy load verified?", "={{ $json.taxonomy_load_ok }}", (4130, -300)),
        code("Prepare trait batches", PREPARE_TRAIT_BATCHES, (4370, -380)),
        node(
            "Loop Over trait batches",
            "n8n-nodes-base.splitInBatches",
            3,
            {"batchSize": 1, "options": {}},
            (4610, -380),
        ),
        code("Prepare PostgreSQL trait source batch", PREPARE_TRAIT_APPEND, (4850, -380)),
        ingest_api_node(
            "Append PostgreSQL trait source batch",
            "('/internal/v1/ingest/' + $json.run_id + '/append')",
            (5090, -380),
        ),
        boolean_if("PostgreSQL trait source batch appended?", "={{ $json.status === 'appended' }}", (5330, -380)),
        neo4j_node(
            "Upsert EltonTraits batch", TRAIT_BATCH_STATEMENT, (5570, -380),
            source_node="Prepare PostgreSQL trait source batch",
        ),
        code("Verify trait batches", VERIFY_TRAIT_BATCHES, (5570, -380)),
        boolean_if("Trait load verified?", "={{ $json.trait_load_ok }}", (5810, -380)),
        neo4j_node("Finalize reference domain projection", FINALIZE_STATEMENT, (6050, -460)),
        code("Verify reference domain finalization", VERIFY_DOMAIN_FINALIZE, (6290, -460)),
        boolean_if("Reference domain finalized?", "={{ $json.domain_finalize_ok }}", (6530, -460)),
        code("Prepare PostgreSQL reference finalization", PREPARE_FINALIZE_REQUEST, (6770, -460)),
        ingest_api_node(
            "Finalize PostgreSQL reference release",
            "('/internal/v1/ingest/' + $json.run_id + '/finalize')",
            (7010, -460),
        ),
        code("Verify active reference releases", VERIFY_FINALIZE, (7250, -460)),
        boolean_if("Reference release finalized?", "={{ $json.finalize_ok }}", (7490, -460)),
        discord(
            "Notify reference success",
            "={{ '✅ **RobinGraph reference ingest succeeded**\\nRun: ' + $json.run_id + "
            "'\\nAviList taxa: ' + $json.loaded_taxa + ', EltonTraits claims: ' + $json.loaded_trait_claims + "
            "'\\nExact trait matches: ' + $json.trait_exact_match_count + ' (' + "
            "($json.trait_exact_match_ratio * 100).toFixed(1) + '%), review candidates: ' + "
            "$json.loaded_mapping_candidates + '\\nGBIF mapping candidates: ' + $json.gbif_mapping_claims }}",
            (7730, -540),
        ),
        discord(
            "Notify reference failure",
            "={{ '❌ **RobinGraph reference ingest blocked or failed**\\nRun: ' + String($json.run_id || 'not-started') + "
            "'\\nReason: ' + String($json.failure_reason || 'Unknown failure').slice(0, 1500) + "
            "'\\nAviList taxa: ' + Number($json.taxonomy_taxon_count || 0) + ', trait claims: ' + "
            "Number($json.trait_claim_count || 0) + ', review candidates: ' + Number($json.mapping_candidate_count || 0) }}",
            (7010, 180),
        ),
        node(
            "Fail reference execution",
            "n8n-nodes-base.stopAndError",
            1,
            {"errorMessage": "RobinGraph reference ingest failed; inspect the preceding quality or Neo4j verification node."},
            (7250, 180),
        ),
        node("Reference ingest finished", "n8n-nodes-base.noOp", 1, {}, (7970, -460)),
    ]

    connections = {
        "Manual Trigger": {"main": [[edge("Build reference configuration")]]},
        "Schedule Trigger — Sunday 03:00 KST": {"main": [[edge("Build reference configuration")]]},
        "Build reference configuration": {
            "main": [[
                edge("Fetch AviList snapshot"),
                edge("Fetch EltonTraits snapshot"),
                edge("Fetch pinned ChecklistBank release"),
            ]]
        },
        "Fetch AviList snapshot": {"main": [[edge("Hash AviList snapshot")]]},
        # Keep the compact Explorer JSON as one text item. Expanding 33,684
        # rows into n8n items exhausts the small NAS worker before normalization.
        "Hash AviList snapshot": {"main": [[edge("Normalize AviList taxonomy")]]},
        "Fetch EltonTraits snapshot": {"main": [[edge("Hash EltonTraits snapshot")]]},
        "Hash EltonTraits snapshot": {"main": [[edge("Restore EltonTraits snapshot binary")]]},
        "Restore EltonTraits snapshot binary": {"main": [[edge("Extract EltonTraits TSV")]]},
        "Extract EltonTraits TSV": {"main": [[edge("Normalize EltonTraits")]]},
        "Fetch pinned ChecklistBank release": {"main": [[edge("Validate ChecklistBank release")]]},
        "Normalize AviList taxonomy": {"main": [[edge("Join taxonomy and traits", 0)]]},
        "Normalize EltonTraits": {"main": [[edge("Join taxonomy and traits", 1)]]},
        "Join taxonomy and traits": {"main": [[edge("Join approved reference sources", 0)]]},
        "Validate ChecklistBank release": {"main": [[edge("Join approved reference sources", 1)]]},
        "Join approved reference sources": {"main": [[edge("Assemble claims and quality gates")]]},
        "Assemble claims and quality gates": {"main": [[edge("Reference quality gates passed?")]]},
        "Reference quality gates passed?": {
            "main": [[edge("Prepare PostgreSQL reference run")], [edge("Notify reference failure")]]
        },
        "Prepare PostgreSQL reference run": {"main": [[edge("Start PostgreSQL reference run")]]},
        "Start PostgreSQL reference run": {"main": [[edge("Verify PostgreSQL reference run started")]]},
        "Verify PostgreSQL reference run started": {"main": [[edge("PostgreSQL reference run started?")]]},
        "PostgreSQL reference run started?": {
            "main": [[edge("Initialize reference domain projection")], [edge("Notify reference failure")]]
        },
        "Initialize reference domain projection": {"main": [[edge("Verify reference domain initialized")]]},
        "Verify reference domain initialized": {"main": [[edge("Reference domain initialized?")]]},
        "Reference domain initialized?": {
            "main": [[edge("Prepare taxonomy batches")], [edge("Notify reference failure")]]
        },
        "Prepare taxonomy batches": {"main": [[edge("Loop Over taxonomy batches")]]},
        "Loop Over taxonomy batches": {
            "main": [
                [edge("Verify taxonomy batches")],
                [edge("Prepare PostgreSQL taxonomy source batch")],
            ]
        },
        "Prepare PostgreSQL taxonomy source batch": {"main": [[edge("Append PostgreSQL taxonomy source batch")]]},
        "Append PostgreSQL taxonomy source batch": {"main": [[edge("PostgreSQL taxonomy source batch appended?")]]},
        "PostgreSQL taxonomy source batch appended?": {
            "main": [[edge("Upsert AviList taxonomy batch")], [edge("Notify reference failure")]]
        },
        "Upsert AviList taxonomy batch": {"main": [[edge("Loop Over taxonomy batches")]]},
        "Verify taxonomy batches": {"main": [[edge("Taxonomy load verified?")]]},
        "Taxonomy load verified?": {
            "main": [[edge("Prepare trait batches")], [edge("Notify reference failure")]]
        },
        "Prepare trait batches": {"main": [[edge("Loop Over trait batches")]]},
        "Loop Over trait batches": {
            "main": [
                [edge("Verify trait batches")],
                [edge("Prepare PostgreSQL trait source batch")],
            ]
        },
        "Prepare PostgreSQL trait source batch": {"main": [[edge("Append PostgreSQL trait source batch")]]},
        "Append PostgreSQL trait source batch": {"main": [[edge("PostgreSQL trait source batch appended?")]]},
        "PostgreSQL trait source batch appended?": {
            "main": [[edge("Upsert EltonTraits batch")], [edge("Notify reference failure")]]
        },
        "Upsert EltonTraits batch": {"main": [[edge("Loop Over trait batches")]]},
        "Verify trait batches": {"main": [[edge("Trait load verified?")]]},
        "Trait load verified?": {
            "main": [[edge("Finalize reference domain projection")], [edge("Notify reference failure")]]
        },
        "Finalize reference domain projection": {"main": [[edge("Verify reference domain finalization")]]},
        "Verify reference domain finalization": {"main": [[edge("Reference domain finalized?")]]},
        "Reference domain finalized?": {
            "main": [[edge("Prepare PostgreSQL reference finalization")], [edge("Notify reference failure")]]
        },
        "Prepare PostgreSQL reference finalization": {"main": [[edge("Finalize PostgreSQL reference release")]]},
        "Finalize PostgreSQL reference release": {"main": [[edge("Verify active reference releases")]]},
        "Verify active reference releases": {"main": [[edge("Reference release finalized?")]]},
        "Reference release finalized?": {
            "main": [[edge("Notify reference success")], [edge("Notify reference failure")]]
        },
        "Notify reference success": {"main": [[edge("Reference ingest finished")]]},
        "Notify reference failure": {"main": [[edge("Fail reference execution")]]},
    }

    # Each schema statement runs separately: Neo4j does not allow multiple
    # CREATE CONSTRAINT statements in one driver query. Stop on schema errors
    # before downloading data or starting an ingestion run.
    schema_names = []
    for index, label in enumerate(REFERENCE_LABELS):
        name = f"Ensure {label} ID constraint"
        schema_names.append(name)
        item = neo4j_node(
            name,
            f"CREATE CONSTRAINT robingraph_reference_{label.lower()}_id IF NOT EXISTS "
            f"FOR (node:{label}) REQUIRE node.id IS UNIQUE",
            (-1600 + (index % 7) * 260, -950 + (index // 7) * 170),
        )
        item["onError"] = "stopWorkflow"
        nodes.append(item)
    name = "Ensure reference taxon name index"
    schema_names.append(name)
    item = neo4j_node(
        name,
        "CREATE INDEX robingraph_reference_taxon_name IF NOT EXISTS "
        "FOR (node:Taxon) ON (node.source_release, node.rank, node.scientific_name)",
        (220, -610),
    )
    item["onError"] = "stopWorkflow"
    nodes.append(item)
    for trigger in ("Manual Trigger", "Schedule Trigger — Sunday 03:00 KST"):
        connections[trigger] = {"main": [[edge(schema_names[0])]]}
    for index, name in enumerate(schema_names):
        next_name = schema_names[index + 1] if index + 1 < len(schema_names) else "Build reference configuration"
        connections[name] = {"main": [[edge(next_name)]]}

    workflow = {
        "id": node_id("workflow-id"),
        "name": "RobinGraph — AviList and EltonTraits reference ingest (inactive until verified)",
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Asia/Seoul",
            "saveManualExecutions": True,
            # The assembled reference snapshot is large. Persisting the full
            # execution after every node makes each batch rewrite hundreds of
            # megabytes of n8n run data and stalls long reference loads.
            "saveExecutionProgress": False,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "none",
            "callerPolicy": "workflowsFromSameOwner",
            "concurrency": 1,
        },
        "versionId": node_id("workflow-version-v1"),
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
