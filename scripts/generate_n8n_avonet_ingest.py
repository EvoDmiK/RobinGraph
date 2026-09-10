"""Generate a pinned, inactive AVONET species-trait workflow (no remote writes)."""
from __future__ import annotations

import json
from pathlib import Path

try:
    from .generate_n8n_reference_ingest import code, node, edge, neo4j_node, compact_cypher
except ImportError:
    from generate_n8n_reference_ingest import code, node, edge, neo4j_node, compact_cypher

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n/robingraph-avonet-ingest.json"
SHA256 = "eb645e83dddb40f1654a3e8d721998dbca76eff540231b7b809267c1e96f8d3e"
RELEASE = "figshare-article-16586228-v7:file-34480856"
URL = "https://ndownloader.figshare.com/files/34480856"
SHEET = "AVONET1_BirdLife"
ROW_COUNT = 11009
SOURCE_CLAIM_COUNT = 143004
MATCHED_PROFILE_COUNT = 9879
LOADED_CLAIM_COUNT = 128331
MAPPING_CANDIDATE_COUNT = 1130

# Species means, not raw specimen measurements. Habitat density is a category,
# not measured vegetation density; wing length must never be labelled wingspan.
FIELDS = [
    ["Beak.Length_Culmen", "beak_length_culmen", "mm", "Beak Culmen"],
    ["Beak.Length_Nares", "beak_length_nares", "mm", "Beak Nares"],
    ["Beak.Width", "beak_width", "mm", "Beak Width"],
    ["Beak.Depth", "beak_depth", "mm", "Beak Depth"],
    ["Tarsus.Length", "tarsus_length", "mm", "Tarsus Length"],
    ["Wing.Length", "wing_length", "mm", "Wing Length"],
    ["Tail.Length", "tail_length", "mm", "Tail Length"],
    ["Mass", "body_mass", "g", "Body Mass"],
    ["Habitat", "habitat", None, None],
    ["Habitat.Density", "habitat_density_category", None, None],
    ["Trophic.Level", "trophic_level", None, None],
    ["Trophic.Niche", "trophic_niche", None, None],
    ["Primary.Lifestyle", "primary_lifestyle", None, None],
]

NORMALIZE_JS = r"""
const config = $('Build AVONET configuration').first().json;
const hash = $('Hash AVONET snapshot').first().json.raw_sha256;
if (hash !== config.sha256) throw new Error('AVONET snapshot SHA-256 mismatch');
const rows = $input.all().map(x => x.json);
if (rows.length !== config.expected_rows) throw new Error('AVONET row count mismatch');
const text = x => x == null || String(x).trim() === '' || String(x).trim() === 'NA' ? null : String(x).trim();
const seen = new Set();
const profiles = rows.map((raw, index) => {
  const scientific_name = text(raw.Species1), sequence = text(raw.Sequence);
  if (!scientific_name || seen.has(scientific_name)) throw new Error('Missing or duplicate species identity');
  seen.add(scientific_name);
  if (!['YES', 'NO'].includes(raw.Inference)) throw new Error('Invalid inference flag');
  const inferred = (text(raw['Traits.inferred']) || '').toLowerCase().split(';').map(x => x.trim());
  const id = 'avonet:' + config.release + ':' + encodeURIComponent(scientific_name);
  const profile = {id, scientific_name, sequence, row_number: index + 2,
    source_uri: config.url + '#sheet=' + config.sheet + '&row=' + (index + 2),
    inference_raw: raw.Inference, inferred_fields_raw: text(raw['Traits.inferred']),
    reference_species: text(raw['Reference.species']), avibase_id: text(raw['Avibase.ID1']),
    sample_size: Number(raw['Total.individuals']), mass_source: text(raw['Mass.Source']),
    mass_references: text(raw['Mass.Refs.Other']), claims: []};
  if (!Number.isInteger(profile.sample_size) || profile.sample_size < 0) throw new Error('Invalid sample size');
  for (const [field, trait, unit, inferredName] of config.fields) {
    if (!Object.prototype.hasOwnProperty.call(raw, field)) throw new Error('Missing required column: ' + field);
    const value = text(raw[field]);
    if (value == null) continue;
    let value_num = null, value_text = null;
    if (unit) {
      value_num = Number(value);
      if (!Number.isFinite(value_num) || value_num <= 0) throw new Error('Invalid measurement: ' + field);
    } else if (field === 'Habitat.Density') {
      value_text = {'1': 'dense', '2': 'semi_open', '3': 'open'}[value];
      if (!value_text) throw new Error('Invalid habitat density code');
    } else value_text = value;
    profile.claims.push({id: id + ':' + trait, trait_name: trait, source_field: field,
      value_num, value_text, unit, raw_value: value,
      inferred: !!inferredName && inferred.includes(inferredName.toLowerCase()),
      evidence_kind: 'literature_dataset', summary_statistic: unit ? 'species_mean' : 'species_category'});
  }
  return profile;
});
if (!profiles.every(p => p.claims.length)) throw new Error('Empty trait profile');
const claim_count = profiles.reduce((n,p) => n+p.claims.length,0);
if (claim_count !== config.expected_source_claims) throw new Error('AVONET source claim count mismatch');
return [{json: {...config, profiles, claim_count}}];
"""

BATCH_JS = r"""
const data = $input.first().json;
const batch_count = Math.ceil(data.profiles.length / data.batch_size);
return Array.from({length: batch_count}, (_, i) => ({json: {
  ...data, profiles: data.profiles.slice(i*data.batch_size,(i+1)*data.batch_size),
  batch_index: i, batch_count
}}));
"""

# Every input profile produces exactly one record and either a unique taxon
# mapping or an unresolved candidate. All writes in a batch are atomic.
BATCH_CYPHER = compact_cypher("""
MATCH (state:IngestState {id:'reference-taxonomy'})
WHERE state.active_release = $taxonomy_release
MATCH (concept:TaxonConceptSet {id:state.active_concept_set_id})
WHERE concept.version=$taxonomy_release AND concept.snapshot_sha256=$taxonomy_sha256
  AND EXISTS {
    MATCH (concept)-[:FROM_DATASET]->(td:SourceDataset)-[:LICENSED_UNDER]->(tl:License)
    WHERE td.version=$taxonomy_release AND td.policy_status='allowed'
      AND td.snapshot_sha256=$taxonomy_sha256 AND tl.policy_status='allowed'
      AND tl.license_uri='https://creativecommons.org/licenses/by/4.0/'
  }
MERGE (dataset:SourceDataset {id:$dataset_id})
SET dataset.source_id='avonet', dataset.name='AVONET Supplementary dataset 1',
    dataset.source_release=$release, dataset.source_uri=$url, dataset.version=$release,
    dataset.snapshot_uri=$url, dataset.snapshot_sha256=$sha256,
    dataset.landing_uri='https://doi.org/10.6084/m9.figshare.16586228.v7',
    dataset.provider='AVONET', dataset.policy_status='allowed',
    dataset.raw_sha256=$sha256, dataset.license_policy_status='allowed', dataset.enabled=true
MERGE (license:License {id:'https://creativecommons.org/licenses/by/4.0/'})
SET license.uri='https://creativecommons.org/licenses/by/4.0/',
    license.license_uri='https://creativecommons.org/licenses/by/4.0/', license.name='CC BY 4.0',
    license.policy_status='allowed'
MERGE (dataset)-[:LICENSED_UNDER]->(license)
MERGE (run:IngestionRun {id:$run_id})
SET run.status='loading', run.source_id='avonet', run.source_release=$release,
    run.taxonomy_release=$taxonomy_release, run.retrieved_at=$retrieved_at
WITH concept, dataset, run
UNWIND $profiles AS row
OPTIONAL MATCH (taxon:Taxon)-[:IN_CONCEPT_SET]->(concept)
WHERE taxon.source_release=$taxonomy_release AND taxon.rank='species' AND taxon.scientific_name=row.scientific_name
WITH dataset, run, row, collect(DISTINCT taxon) AS taxa
MERGE (record:SourceRecord {id:row.id})
SET record.record_type='trait_profile', record.external_id=row.sequence,
    record.scientific_name_raw=row.scientific_name, record.raw_uri=row.source_uri,
    record.raw_hash=$sha256, record.retrieved_at=$retrieved_at,
    record.source_sheet=$sheet, record.source_row=row.row_number,
    record.inference_raw=row.inference_raw, record.inferred_fields_raw=row.inferred_fields_raw,
    record.reference_species=row.reference_species, record.sample_size=row.sample_size,
    record.mass_source=row.mass_source, record.mass_references=row.mass_references,
    record.avibase_id=row.avibase_id
MERGE (record)-[:IN_DATASET]->(dataset)
MERGE (run)-[:INGESTED]->(record)
CALL {
  WITH run, row, taxa, record
  WITH run, row, record, taxa[0] AS taxon WHERE size(taxa)=1
  MERGE (mapping:TaxonMappingClaim {id:row.id+':mapping:'+$taxonomy_release})
  SET mapping.method='exact_scientific_name_unique_in_avilist_species',
      mapping.resolution_status='accepted_automatic', mapping.taxonomy_release=$taxonomy_release
  MERGE (record)-[:HAS_MAPPING_CLAIM]->(mapping)
  MERGE (mapping)-[:PROPOSES_TAXON]->(taxon)
  WITH run,row,record,taxon
  UNWIND row.claims AS value
  MERGE (evidence:EvidenceUnit {id:value.id+':evidence'})
  SET evidence.evidence_type='literature_dataset_row', evidence.locator=row.source_uri+'&field='+value.source_field,
      evidence.citation='Tobias et al. (2022), AVONET; Figshare 16586228 v7', evidence.accessed_at=$retrieved_at
  MERGE (evidence)-[:FROM_RECORD]->(record)
  MERGE (claim:TraitClaim {id:value.id+':taxonomy:'+$taxonomy_release})
  SET claim.trait_name=value.trait_name, claim.value_num=value.value_num,
      claim.value_text=value.value_text, claim.unit=value.unit, claim.raw_value=value.raw_value,
      claim.source_field=value.source_field, claim.source_release=$release, claim.source_id='avonet',
      claim.taxonomy_release=$taxonomy_release, claim.inferred=value.inferred,
      claim.evidence_kind=value.evidence_kind, claim.summary_statistic=value.summary_statistic,
      claim.retrieved_at=$retrieved_at
  MERGE (claim)-[:ASSERTS_ABOUT]->(taxon)
  MERGE (claim)-[:SUPPORTED_BY]->(evidence)
  MERGE (run)-[:INGESTED]->(claim)
  RETURN count(*) AS loaded_claims
}
CALL {
  WITH run,row,taxa,record
  WITH run,row,record,taxa WHERE size(taxa)<>1
  MERGE (candidate:TaxonMappingCandidate {id:row.id+':candidate:'+$taxonomy_release})
  SET candidate.source_scientific_name=row.scientific_name,
      candidate.source_taxonomy='HBW-BirdLife v5', candidate.taxonomy_release=$taxonomy_release,
      candidate.resolution_status='open', candidate.reason_code=CASE WHEN size(taxa)=0 THEN 'no_exact_match' ELSE 'ambiguous_exact_match' END,
      candidate.profile_json=row.profile_json
  MERGE (record)-[:HAS_MAPPING_CANDIDATE]->(candidate)
  MERGE (run)-[:QUARANTINED]->(candidate)
  RETURN count(*) AS loaded_candidates
}
RETURN $batch_index AS batch_index, $batch_count AS batch_count,
       count(*) AS loaded_profiles, sum(loaded_claims) AS loaded_claims,
       sum(loaded_candidates) AS loaded_candidates,
       sum(CASE WHEN size(taxa)=1 THEN 1 ELSE 0 END) AS matched_profiles,
       sum(CASE WHEN size(taxa)=1 THEN size(row.claims) ELSE 0 END) AS expected_claims
""")

VERIFY_JS = r"""
const expected = $('Normalize AVONET species').first().json;
const rows = $input.all().map(x=>x.json);
const count = Math.ceil(expected.expected_rows/expected.batch_size);
if (rows.length !== count) throw new Error('Missing batch results');
const indices = new Set();
let profiles=0, claims=0, candidates=0, matched=0;
for (const row of rows) {
  if (row.error || !Number.isInteger(row.batch_index) || row.batch_index<0 || row.batch_index>=count || indices.has(row.batch_index) || row.batch_count!==count) throw new Error('Invalid batch acknowledgement');
  indices.add(row.batch_index);
  const wanted=Math.min(expected.batch_size,expected.expected_rows-row.batch_index*expected.batch_size);
  if (row.loaded_profiles!==wanted || row.loaded_claims!==row.expected_claims || row.matched_profiles+row.loaded_candidates!==wanted) throw new Error('Batch count mismatch');
  for (const key of ['loaded_profiles','loaded_claims','loaded_candidates','matched_profiles','expected_claims']) if (!Number.isInteger(row[key]) || row[key]<0) throw new Error('Invalid count');
  profiles+=row.loaded_profiles; claims+=row.loaded_claims; candidates+=row.loaded_candidates; matched+=row.matched_profiles;
}
if (profiles!==expected.expected_rows || matched!==expected.expected_matched_profiles ||
    claims!==expected.expected_loaded_claims || candidates!==expected.expected_mapping_candidates)
  throw new Error('AVONET mapping quality gate failed');
const {profiles: unused, ...config}=expected;
return [{json:{...config, loaded_profiles:profiles, loaded_claims:claims, loaded_candidates:candidates, matched_profiles:matched}}];
"""

FINALIZE_CYPHER = compact_cypher("""
MATCH (taxonomy:IngestState {id:'reference-taxonomy'}) WHERE taxonomy.active_release=$taxonomy_release
  AND EXISTS {
    MATCH (cs:TaxonConceptSet {id:taxonomy.active_concept_set_id})-[:FROM_DATASET]->(td:SourceDataset)-[:LICENSED_UNDER]->(tl:License)
    WHERE cs.version=$taxonomy_release AND cs.snapshot_sha256=$taxonomy_sha256
      AND td.version=$taxonomy_release AND td.policy_status='allowed'
      AND td.snapshot_sha256=$taxonomy_sha256 AND tl.policy_status='allowed'
      AND tl.license_uri='https://creativecommons.org/licenses/by/4.0/'
  }
MATCH (run:IngestionRun {id:$run_id}) WHERE run.status='loading'
CALL { WITH run MATCH (run)-[:INGESTED]->(r:SourceRecord) RETURN count(DISTINCT r) AS profiles }
CALL { WITH run MATCH (run)-[:INGESTED]->(c:TraitClaim) RETURN count(DISTINCT c) AS claims }
CALL { WITH run MATCH (run)-[:QUARANTINED]->(c:TaxonMappingCandidate) RETURN count(DISTINCT c) AS candidates }
WITH run, profiles, claims, candidates
WHERE profiles=$loaded_profiles AND claims=$loaded_claims AND candidates=$loaded_candidates
MERGE (state:IngestState {id:'reference-avonet'})
SET state.active_release=$release, state.taxonomy_release=$taxonomy_release,
    state.last_successful_run_id=$run_id, state.last_successful_at=datetime()
SET run.status='succeeded',run.profile_count=profiles,run.trait_claim_count=claims,
    run.mapping_candidate_count=candidates,run.completed_at=datetime()
RETURN run.id AS finalized_run_id, state.active_release AS active_release, run.status AS status
""")


def configuration() -> dict:
    points = json.loads((ROOT / 'config/collection-points.json').read_text(encoding='utf8'))['collection_points']
    sources = json.loads((ROOT / 'config/source-registry.json').read_text(encoding='utf8'))
    point = next(p for p in points if p['collection_point_id'] == 'traits-avonet')
    source = next(s for s in sources if s['source_id'] == point['source_id'])
    taxonomy = next(p for p in points if p['collection_point_id'] == 'taxonomy-avilist-v2025b')
    taxonomy_source = next(s for s in sources if s['source_id'] == taxonomy['source_id'])
    if any(not x['enabled'] or x['license_policy_status'] != 'allowed' for x in [point, source, taxonomy, taxonomy_source]):
        raise ValueError('AVONET source and collection point must both be allowed and enabled')
    if taxonomy['source_release'] != 'v2025b' or not taxonomy['expected_sha256']:
        raise ValueError('AVONET requires pinned AviList v2025b')
    if point['expected_sha256'] != SHA256 or point['endpoint_uri'] != URL or point['source_release'] != RELEASE:
        raise ValueError('AVONET collection point differs from verified snapshot')
    if source['license_uri'] != 'https://creativecommons.org/licenses/by/4.0/':
        raise ValueError('AVONET license mismatch')
    return dict(url=URL, sha256=SHA256, release=RELEASE, sheet=SHEET,
                expected_rows=ROW_COUNT, taxonomy_release='v2025b', batch_size=100,
                expected_source_claims=SOURCE_CLAIM_COUNT,
                expected_matched_profiles=MATCHED_PROFILE_COUNT,
                expected_loaded_claims=LOADED_CLAIM_COUNT,
                expected_mapping_candidates=MAPPING_CANDIDATE_COUNT,
                taxonomy_sha256=taxonomy['expected_sha256'],
                dataset_id='avonet:'+RELEASE, fields=FIELDS)


def build_workflow(config: dict | None = None) -> dict:
    config = configuration() if config is None else config
    build = 'const config = '+json.dumps(config)+';\nreturn [{json:{...config, run_id:"avonet:"+$execution.id, retrieved_at:new Date().toISOString()}}];'
    nodes = [
        node('Manual Trigger','n8n-nodes-base.manualTrigger',1,{},(0,0)),
        code('Build AVONET configuration',build,(200,0)),
        node('Fetch AVONET snapshot','n8n-nodes-base.httpRequest',4.4,{'url':'={{ $json.url }}','options':{'timeout':180000,'response':{'response':{'responseFormat':'file','outputPropertyName':'data'}}}},(400,0)),
        node('Hash AVONET snapshot','n8n-nodes-base.crypto',2,{'action':'hash','binaryData':True,'binaryPropertyName':'data','type':'SHA256','dataPropertyName':'raw_sha256','encoding':'hex'},(600,-100)),
        node('Extract AVONET species sheet','n8n-nodes-base.extractFromFile',1.1,{'operation':'xlsx','binaryPropertyName':'data','options':{'sheetName':SHEET,'headerRow':True,'includeEmptyCells':True,'rawData':False,'readAsString':False}},(600,100)),
        code('Restore AVONET snapshot binary', "const item=$('Fetch AVONET snapshot').first(); if (!item.binary?.data) throw new Error('AVONET snapshot binary missing'); return [{json:$input.first().json,binary:item.binary}];",(700,0)),
        code('Normalize AVONET species',NORMALIZE_JS,(1000,0)),
        code('Build AVONET batches',BATCH_JS.replace('data.profiles.slice(i*data.batch_size,(i+1)*data.batch_size)', 'data.profiles.slice(i*data.batch_size,(i+1)*data.batch_size).map(p=>({...p,profile_json:JSON.stringify(p)}))'),(1200,0)),
        neo4j_node('Upsert AVONET batches',BATCH_CYPHER,(1400,0)),
        code('Verify AVONET batches',VERIFY_JS,(1600,0)),
        neo4j_node('Finalize AVONET release',FINALIZE_CYPHER,(1800,0)),
        code('Verify AVONET release',"const row=$input.first().json; const cfg=$('Build AVONET configuration').first().json; if(row.finalized_run_id!==cfg.run_id || row.active_release!==cfg.release || row.status!=='succeeded') throw new Error('AVONET finalization failed'); return $input.all();",(2000,0)),
    ]
    connections = {}
    def connect(a,b,index=0): connections.setdefault(a,{'main':[[]]})['main'][0].append(edge(b,index))
    connect('Manual Trigger','Build AVONET configuration')
    connect('Build AVONET configuration','Fetch AVONET snapshot')
    connect('Fetch AVONET snapshot','Hash AVONET snapshot')
    # Crypto v2 may remove the hashed binary; restore one item, never row fanout.
    connect('Hash AVONET snapshot','Restore AVONET snapshot binary')
    connect('Restore AVONET snapshot binary','Extract AVONET species sheet')
    chain=['Extract AVONET species sheet','Normalize AVONET species','Build AVONET batches','Upsert AVONET batches','Verify AVONET batches','Finalize AVONET release','Verify AVONET release']
    for a,b in zip(chain,chain[1:]): connect(a,b)
    return {'id':'robingraph-avonet-ingest','name':'RobinGraph — AVONET morphology and ecology reference ingest','active':False,'nodes':nodes,'connections':connections,'settings':{'executionOrder':'v1','timezone':'Asia/Seoul','concurrency':1},'pinData':{},'tags':[]}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build_workflow(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(OUTPUT)
