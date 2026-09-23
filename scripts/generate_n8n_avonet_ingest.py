"""Generate a pinned, inactive AVONET species-trait workflow (no remote writes)."""
from __future__ import annotations

import json
from pathlib import Path

try:
    from .generate_n8n_reference_ingest import code, node, edge, neo4j_node, compact_cypher, ingest_api_node
except ImportError:
    from generate_n8n_reference_ingest import code, node, edge, neo4j_node, compact_cypher, ingest_api_node

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
const {profiles, ingest_request, ...context} = data;
return Array.from({length: batch_count}, (_, i) => ({json: {
  ...context, profiles: profiles.slice(i*data.batch_size,(i+1)*data.batch_size)
    .map(profile => ({...profile, profile_json: JSON.stringify(profile)})),
  batch_index: i, batch_count
}}));
"""

# Every input profile produces exactly one record and either a unique taxon
# mapping or an unresolved candidate. All writes in a batch are atomic.
BATCH_CYPHER = compact_cypher("""
MATCH (concept:TaxonConceptSet {id:$taxonomy_concept_set_id})
WHERE concept.version=$taxonomy_release AND concept.snapshot_sha256=$taxonomy_sha256
  AND concept.policy_status='allowed'
WITH concept
UNWIND $profiles AS row
OPTIONAL MATCH (taxon:Taxon {
  source_release:$taxonomy_release,
  rank:'species',
  scientific_name:row.scientific_name
})-[:IN_CONCEPT_SET]->(concept)
WITH row, collect(DISTINCT taxon) AS taxa
CALL {
  WITH row, taxa
  WITH row, taxa[0] AS taxon WHERE size(taxa)=1
  MERGE (mapping:TaxonMappingClaim {id:row.id+':mapping:'+$taxonomy_release})
  SET mapping.method='exact_scientific_name_unique_in_avilist_species',
      mapping.resolution_status='accepted_automatic', mapping.taxonomy_release=$taxonomy_release,
      mapping.dataset_id=$dataset_id, mapping.source_record_id=row.id, mapping.policy_status='allowed'
  MERGE (mapping)-[:PROPOSES_TAXON]->(taxon)
  WITH row,taxon
  UNWIND row.claims AS value
  MERGE (evidence:EvidenceUnit {id:value.id+':evidence'})
  SET evidence.evidence_type='literature_dataset_row', evidence.locator=row.source_uri+'&field='+value.source_field,
      evidence.citation='Tobias et al. (2022), AVONET; Figshare 16586228 v7', evidence.accessed_at=$retrieved_at,
      evidence.dataset_id=$dataset_id, evidence.source_record_id=row.id, evidence.policy_status='allowed'
  MERGE (claim:TraitClaim {id:value.id+':taxonomy:'+$taxonomy_release})
  SET claim.trait_name=value.trait_name, claim.value_num=value.value_num,
      claim.value_text=value.value_text, claim.unit=value.unit, claim.raw_value=value.raw_value,
      claim.source_field=value.source_field, claim.source_release=$release, claim.source_id='avonet',
      claim.taxonomy_release=$taxonomy_release, claim.inferred=value.inferred,
      claim.evidence_kind=value.evidence_kind, claim.summary_statistic=value.summary_statistic,
      claim.retrieved_at=$retrieved_at, claim.dataset_id=$dataset_id,
      claim.source_record_id=row.id, claim.policy_status='allowed'
  MERGE (claim)-[:ASSERTS_ABOUT]->(taxon)
  MERGE (claim)-[:SUPPORTED_BY]->(evidence)
  RETURN count(*) AS loaded_claims
}
CALL {
  WITH row,taxa
  WITH row,taxa WHERE size(taxa)<>1
  MERGE (candidate:TaxonMappingCandidate {id:row.id+':candidate:'+$taxonomy_release})
  SET candidate.source_scientific_name=row.scientific_name,
      candidate.source_taxonomy='HBW-BirdLife v5', candidate.taxonomy_release=$taxonomy_release,
      candidate.resolution_status='open', candidate.reason_code=CASE WHEN size(taxa)=0 THEN 'no_exact_match' ELSE 'ambiguous_exact_match' END,
      candidate.profile_json=row.profile_json, candidate.dataset_id=$dataset_id,
      candidate.source_record_id=row.id, candidate.policy_status='allowed',
      candidate.last_seen_run_id=$run_id, candidate.last_seen_at=$retrieved_at
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
const numericKeys = ['batch_index','batch_count','loaded_profiles','loaded_claims','loaded_candidates','matched_profiles','expected_claims'];
const rows = $input.all().map(x => {
  const row = {...x.json};
  for (const key of numericKeys) row[key] = Number(row[key]);
  return row;
});
const count = Math.ceil(expected.expected_rows/expected.batch_size);
if (rows.length !== count) throw new Error('Missing batch results');
const indices = new Set();
let profiles=0, claims=0, candidates=0, matched=0;
for (const row of rows) {
  if (row.error || !Number.isInteger(row.batch_index) || row.batch_index<0 || row.batch_index>=count || indices.has(row.batch_index) || row.batch_count!==count) throw new Error('Invalid batch acknowledgement');
  indices.add(row.batch_index);
  const wanted=Math.min(expected.batch_size,expected.expected_rows-row.batch_index*expected.batch_size);
  if (row.loaded_profiles!==wanted || row.loaded_claims!==row.expected_claims || row.matched_profiles+row.loaded_candidates!==wanted) throw new Error('Batch count mismatch');
  for (const key of numericKeys.slice(2)) if (!Number.isInteger(row[key]) || row[key]<0) throw new Error('Invalid count');
  profiles+=row.loaded_profiles; claims+=row.loaded_claims; candidates+=row.loaded_candidates; matched+=row.matched_profiles;
}
if (profiles!==expected.expected_rows || matched!==expected.expected_matched_profiles ||
    claims!==expected.expected_loaded_claims || candidates!==expected.expected_mapping_candidates)
  throw new Error('AVONET mapping quality gate failed');
const {profiles: unused, ...config}=expected;
return [{json:{...config, loaded_profiles:profiles, loaded_claims:claims, loaded_candidates:candidates, matched_profiles:matched}}];
"""

PREPARE_BEGIN_JS = r"""
const source=$input.first().json;
return [{json:{...source,ingest_request:{
  dataset:{id:source.dataset_id,source_id:'avonet',name:'AVONET Supplementary dataset 1',
    provider:'AVONET',landing_uri:'https://doi.org/10.6084/m9.figshare.16586228.v7',
    release_strategy:'versioned',policy_status:'allowed',metadata:{license_uri:'https://creativecommons.org/licenses/by/4.0/'}},
  release:{id:source.source_release,release_key:source.release,retrieved_at:source.retrieved_at,
    content_sha256:source.sha256,raw_object_uri:source.url,
    metadata:{sheet:source.sheet,taxonomy_release:source.taxonomy_release,taxonomy_concept_set_id:source.taxonomy_concept_set_id}},
  run:{id:source.run_id,pipeline_id:source.pipeline_id,started_at:source.retrieved_at,
    manifest:{orchestrator:'n8n',workflow:'avonet',expected_profiles:source.expected_rows,expected_claims:source.expected_loaded_claims}}
}}}];
"""

VERIFY_BEGIN_JS = r"""
const source=$('Prepare PostgreSQL AVONET run').first().json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
const ok=!errorText&&response.status==='started'&&Number.isSafeInteger(response.state_version)&&response.state_version>=0;
return [{json:{...source,expected_state_version:response.state_version,start_ok:ok,
  failure_reason:ok?'':(errorText||'PostgreSQL did not start AVONET run')}}];
"""

PREPARE_APPEND_JS = r"""
const batch=$input.first().json;
const records=batch.profiles.map(row=>({id:row.id,external_id:String(row.sequence||row.scientific_name),
  record_type:'trait_profile',raw_object_uri:row.source_uri,raw_sha256:batch.sha256,
  retrieved_at:batch.retrieved_at,parser_version:'avonet-v2',license_policy_status:'allowed',
  payload:{scientific_name:row.scientific_name,row_number:row.row_number,sheet:batch.sheet,
    inference_raw:row.inference_raw,inferred_fields_raw:row.inferred_fields_raw,
    reference_species:row.reference_species,sample_size:row.sample_size,avibase_id:row.avibase_id}}));
return [{json:{...batch,ingest_request:{records,quarantine_items:[]}}}];
"""

VERIFY_APPEND_JS = r"""
const batch=$('Prepare PostgreSQL AVONET source batch').item.json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
if(errorText||response.status!=='appended')throw new Error(errorText||'PostgreSQL AVONET append failed');
return [{json:batch}];
"""

PREPARE_FINALIZE_JS = r"""
const source=$input.first().json;
return [{json:{...source,ingest_request:{counts:{source_records:source.loaded_profiles,
  trait_claims:source.loaded_claims,mapping_candidates:source.loaded_candidates},
  cursor:{taxonomy_release:source.taxonomy_release,taxonomy_concept_set_id:source.taxonomy_concept_set_id},
  expected_state_version:source.expected_state_version}}}];
"""

VERIFY_FINALIZE_JS = r"""
const source=$('Prepare PostgreSQL AVONET finalization').first().json,response=$input.first().json;
const errorText=String(response.error?.message||response.error||response.message||response.detail||'');
if(errorText||response.status!=='finalized'||response.state_version!==source.expected_state_version+1)
  throw new Error(errorText||'PostgreSQL AVONET activation failed');
return [{json:{...source,finalize_ok:true}}];
"""

FINALIZE_CYPHER = compact_cypher("""
MATCH (concept:TaxonConceptSet {id:$taxonomy_concept_set_id})
WHERE concept.version=$taxonomy_release AND concept.snapshot_sha256=$taxonomy_sha256
  AND concept.policy_status='allowed'
CALL { MATCH (c:TraitClaim {dataset_id:$dataset_id, policy_status:'allowed'}) RETURN count(c) AS claims }
CALL { MATCH (c:TaxonMappingCandidate {dataset_id:$dataset_id, policy_status:'allowed'}) RETURN count(c) AS candidates }
WITH claims, candidates WHERE claims=$loaded_claims AND candidates=$loaded_candidates
RETURN $run_id AS finalized_run_id, $release AS active_release, 'domain_verified' AS status
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
                pipeline_id='reference-avonet', source_release='avonet-release:sha256-'+SHA256,
                expected_rows=ROW_COUNT, taxonomy_release='v2025b',
                taxonomy_concept_set_id='rg:concept-set:avilist-v2025b', batch_size=100,
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
        code('Prepare PostgreSQL AVONET run',PREPARE_BEGIN_JS,(1200,0)),
        ingest_api_node('Start PostgreSQL AVONET run',"'/internal/v1/ingest/begin'",(1400,0)),
        code('Verify PostgreSQL AVONET run started',VERIFY_BEGIN_JS,(1600,0)),
        code('Build AVONET batches',BATCH_JS,(1800,0)),
        node('Loop Over AVONET batches','n8n-nodes-base.splitInBatches',3,{'batchSize':1,'options':{}},(2000,0)),
        code('Prepare PostgreSQL AVONET source batch',PREPARE_APPEND_JS,(2200,100)),
        ingest_api_node('Append PostgreSQL AVONET source batch',"('/internal/v1/ingest/'+$json.run_id+'/append')",(2400,100)),
        code('Verify PostgreSQL AVONET source batch',VERIFY_APPEND_JS,(2600,100)),
        neo4j_node('Upsert AVONET batches',BATCH_CYPHER,(2800,100)),
        code('Verify AVONET batches',VERIFY_JS,(2800,-100)),
        neo4j_node('Verify AVONET domain release',FINALIZE_CYPHER,(3000,-100)),
        code('Verify AVONET domain counts',"const row=$input.first().json; const cfg=$('Verify AVONET batches').first().json; if(row.finalized_run_id!==cfg.run_id || row.active_release!==cfg.release || row.status!=='domain_verified') throw new Error('AVONET domain verification failed'); return [{json:cfg}];",(3200,-100)),
        code('Prepare PostgreSQL AVONET finalization',PREPARE_FINALIZE_JS,(3400,-100)),
        ingest_api_node('Finalize PostgreSQL AVONET release',"('/internal/v1/ingest/'+$json.run_id+'/finalize')",(3600,-100)),
        code('Verify AVONET release',VERIFY_FINALIZE_JS,(3800,-100)),
    ]
    connections = {}
    def connect(a,b,index=0): connections.setdefault(a,{'main':[[]]})['main'][0].append(edge(b,index))
    connect('Manual Trigger','Build AVONET configuration')
    connect('Build AVONET configuration','Fetch AVONET snapshot')
    connect('Fetch AVONET snapshot','Hash AVONET snapshot')
    # Crypto v2 may remove the hashed binary; restore one item, never row fanout.
    connect('Hash AVONET snapshot','Restore AVONET snapshot binary')
    connect('Restore AVONET snapshot binary','Extract AVONET species sheet')
    chain=['Extract AVONET species sheet','Normalize AVONET species','Prepare PostgreSQL AVONET run',
           'Start PostgreSQL AVONET run','Verify PostgreSQL AVONET run started',
           'Build AVONET batches','Loop Over AVONET batches']
    for a,b in zip(chain,chain[1:]): connect(a,b)
    # n8n 2.15 splitInBatches emits completion on output 0 and the current
    # item on output 1. The community Neo4j node evaluates only one input
    # item, so explicitly feed every batch through it before verification.
    connections['Loop Over AVONET batches']={'main':[
        [edge('Verify AVONET batches')],
        [edge('Prepare PostgreSQL AVONET source batch')],
    ]}
    connect('Prepare PostgreSQL AVONET source batch','Append PostgreSQL AVONET source batch')
    connect('Append PostgreSQL AVONET source batch','Verify PostgreSQL AVONET source batch')
    connect('Verify PostgreSQL AVONET source batch','Upsert AVONET batches')
    connect('Upsert AVONET batches','Loop Over AVONET batches')
    connect('Verify AVONET batches','Verify AVONET domain release')
    connect('Verify AVONET domain release','Verify AVONET domain counts')
    connect('Verify AVONET domain counts','Prepare PostgreSQL AVONET finalization')
    connect('Prepare PostgreSQL AVONET finalization','Finalize PostgreSQL AVONET release')
    connect('Finalize PostgreSQL AVONET release','Verify AVONET release')
    return {'id':'robingraph-avonet-ingest','name':'RobinGraph — AVONET morphology and ecology reference ingest','active':False,'nodes':nodes,'connections':connections,'settings':{'executionOrder':'v1','timezone':'Asia/Seoul','concurrency':1,'saveExecutionProgress':False},'pinData':{},'tags':[]}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build_workflow(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(OUTPUT)
