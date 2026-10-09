#!/usr/bin/env python3
"""Read-only AviList -> PostgreSQL -> Neo4j -> read_traits/API coverage audit.

Run from the checkout with PYTHONPATH=src. Only the output JSON is written.
Remote credentials stay in the TEST container's existing environment. PostgreSQL
transactions are server-enforced read-only; Neo4j uses execute_read/READ_ACCESS
with fixed MATCH templates. No ingest endpoint or migration is invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ['Pica serica', 'Pica pica', 'Anas platyrhynchos', 'Struthio camelus',
           'Nycticorax nycticorax', 'Cyanopsitta spixii', '까치']

# This is sent on stdin; no script or snapshot is written inside the container.
COLLECTOR = r'''
import hashlib, inspect, json, os
from collections import defaultdict
from types import SimpleNamespace as NS
from urllib.parse import urlencode
from urllib.request import urlopen
import psycopg
from psycopg import sql
from neo4j import GraphDatabase, READ_ACCESS
from robingraph.ingest.postgres import PostgresSettings
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval import species_profile as sp
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon

p=PostgresSettings.from_environment()
# Fail closed rather than silently auditing a production PostgreSQL database.
if 'test' not in p.database.lower():
 raise SystemExit('Refusing PostgreSQL database without TEST identity')
result={'mode':'live_test_read_only','checked_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
with psycopg.connect(**p.connection_kwargs(), options='-c default_transaction_read_only=on -c statement_timeout=120000') as conn:
 conn.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(p.schema)))
 result['postgres_read_only']=conn.execute('SHOW transaction_read_only').fetchone()[0]
 rows=conn.execute("""SELECT st.pipeline_id,d.id,d.name,d.policy_status,r.id,r.release_key,r.content_sha256,st.cursor,st.version
 FROM ingest_state st JOIN source_release r ON r.id=st.active_release_id
 JOIN source_dataset d ON d.id=r.dataset_id WHERE st.pipeline_id IN ('reference-taxonomy-traits','reference-avonet')""").fetchall()
 keys=['pipeline','dataset_id','source_name','policy_status','release_id','release','sha256','cursor','version']
 result['contexts']=[dict(zip(keys,row)) for row in rows]
 ids=[c['release_id'] for c in result['contexts']]
 result['source_records']=[dict(zip(['id','release_id','external_id','record_type','policy_status','payload'],row)) for row in conn.execute(
 'SELECT id,source_release_id,external_id,record_type,license_policy_status,payload FROM source_record WHERE source_release_id=ANY(%s)',(ids,)).fetchall()]
 result['quarantine']=[dict(zip(['stage','reason','count'],row)) for row in conn.execute("""SELECT q.stage,q.reason_code,count(*) FROM quarantine_item q JOIN ingestion_run r ON r.id=q.ingestion_run_id WHERE r.source_release_id=ANY(%s) GROUP BY 1,2""",(ids,)).fetchall()]
ctx=next(c for c in result['contexts'] if c['pipeline']=='reference-taxonomy-traits' and c['policy_status']=='allowed')
concept=ctx['cursor'].get('concept_set_id',ctx['cursor'].get('taxonomy_concept_set_id'))
release=ctx['cursor']['taxonomy_release']
result.update(concept_set_id=concept,taxonomy_release=release)
ns=Neo4jSettings.from_environment()
with GraphDatabase.driver(ns.uri,auth=(ns.username,ns.password),connection_timeout=10) as driver:
 with driver.session(database=ns.database,default_access_mode=READ_ACCESS) as session:
  def query(q,**params):
   return session.execute_read(lambda tx:tx.run(q,**params).data())
  result['concept_sets']=query('MATCH (s:TaxonConceptSet {id:$concept}) RETURN s.id AS id,s.version AS version,s.snapshot_sha256 AS sha256,s.policy_status AS policy_status',concept=concept)
  result['taxa']=query("""MATCH (t:Taxon:BirdTaxon {rank:'species'})-[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:$concept}) RETURN t.id AS id,t.source_taxon_id AS sequence,t.scientific_name AS scientific_name,t.source_release AS release,t.policy_status AS policy_status,t.source_id AS source_id""",concept=concept)
  result['claims']=query("""MATCH (c:TraitClaim) OPTIONAL MATCH (c)-[:ASSERTS_ABOUT]->(t:Taxon:BirdTaxon {rank:'species'}) OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:EvidenceUnit) RETURN c{.id,.trait_name,.dataset_id,.source_release,.taxonomy_release,.source_record_id,.policy_status,.value_num,.value_text,.value_boolean,.value_json} AS claim,t.id AS taxon_id,e.policy_status AS evidence_policy,e.dataset_id AS evidence_dataset,e.source_record_id AS evidence_record,e.locator AS source_url,e.citation AS citation""")
  result['mapping_candidates']=query('MATCH (m:TaxonMappingCandidate) RETURN m.id AS id,m.dataset_id AS dataset_id,m.source_record_id AS source_record_id,m.source_scientific_name AS scientific_name,m.reason_code AS reason,m.resolution_status AS status,m.taxonomy_release AS taxonomy_release,m.profile_json AS profile_json,m.policy_status AS policy_status')
  sources=[]
  for c in result['contexts']:
   cur=c['cursor']
   if c['policy_status']=='allowed' and cur.get('concept_set_id',cur.get('taxonomy_concept_set_id'))==concept and cur.get('taxonomy_release')==release:
    sources.append({'dataset_id':c['dataset_id'],'release':cur.get('trait_release',c['release'])})
  # Same gates as TRAIT_QUERY, with taxon_id projected for one batched scan.
  q=sp.TRAIT_QUERY.replace('{id:$taxon_id}',"{rank:'species'}").replace('RETURN c{.*}', 'RETURN t.id AS taxon_id, c{.*}').replace('LIMIT 100','')
  eligible=query(q,concept_set_id=concept,taxonomy_release=release,sources=sources)
  by_taxon=defaultdict(list)
  for row in eligible: by_taxon[row.pop('taxon_id')].append(row)
  result['reader_query_rows']=len(eligible)
  contexts={c['pipeline']:NS(dataset=NS(id=c['dataset_id'],name=c['source_name']),release=NS(release_key=c['release']),cursor=c['cursor']) for c in result['contexts'] if c['policy_status']=='allowed'}
  store=NS(active_release_context=lambda pipeline:contexts.get(pipeline))
  result['reader_traits']={}
  result['reader_errors']=[]
  result['reader_limit_species']=[]
  for taxon in result['taxa']:
   tid=taxon['id']
   rows=by_taxon[tid]
   if len(rows)>100: result['reader_limit_species'].append(tid)
   # Replay the live reader against live DB rows, retaining per-species LIMIT.
   repository=NS(_run=lambda *args, _rows=rows, **kwargs:_rows[:100])
   lineage=TaxonomyLineage(taxon['scientific_name'],'AviList',release,concept,(LineageTaxon(tid,'species',taxon['scientific_name'],None),))
   try: result['reader_traits'][tid]=sp.read_traits(repository,store,lineage)
   except Exception as ex: result['reader_errors'].append({'taxon_id':tid,'error_type':type(ex).__name__})
result['reader_sha256']=hashlib.sha256(inspect.getsource(sp.read_traits).encode()).hexdigest()
result['trait_query_sha256']=hashlib.sha256(sp.TRAIT_QUERY.encode()).hexdigest()
result['api_samples']=[]
for name in ['Pica serica','Pica pica','Anas platyrhynchos','Struthio camelus','Nycticorax nycticorax','Cyanopsitta spixii','까치']:
 try:
  with urlopen('http://127.0.0.1:8000/v1/taxa/profile?'+urlencode({'name':name}),timeout=100) as response:
   obj=json.load(response)
   result['api_samples'].append({'query':name,'status':response.status,'taxon':obj.get('taxon'),'traits':obj.get('traits',[]),'warnings':obj.get('warnings',[])})
 except Exception as ex: result['api_samples'].append({'query':name,'error_type':type(ex).__name__,'status':getattr(ex,'code',None)})
print(json.dumps(result,ensure_ascii=False,separators=(',',':')))
'''


def digest(body):
    return hashlib.sha256(body).hexdigest()


def duplicate_keys(values):
    return {str(k): n for k, n in Counter(values).items() if n > 1}


def compare_taxonomy(snapshot, live):
    source = {str(r[0]): r for r in snapshot if r[1] == 'species'}
    graph = live['taxa']
    observed = {str(r['sequence']) for r in graph}
    pg = [r for r in live['source_records'] if r['record_type'] == 'taxon_concept'
          and r['payload'].get('rank') == 'species']
    source_names = {r[5].strip() for r in source.values()}
    pg_names = {r['payload'].get('scientific_name') for r in pg}
    return {
        'source_species': len(source), 'source_species_rows': sum(r[1]=='species' for r in snapshot),
        'graph_species_rows': len(graph), 'postgres_species_rows': len(pg),
        'source_duplicate_sequences': duplicate_keys(str(r[0]) for r in snapshot if r[1]=='species'),
        'source_duplicate_names': duplicate_keys(r[5].strip() for r in snapshot if r[1]=='species'),
        'graph_duplicate_ids': duplicate_keys(r['id'] for r in graph),
        'graph_duplicate_sequences': duplicate_keys(str(r['sequence']) for r in graph),
        'graph_duplicate_names': duplicate_keys(r['scientific_name'] for r in graph),
        'postgres_duplicate_names': duplicate_keys(r['payload'].get('scientific_name') for r in pg),
        'source_not_in_graph_sequences': sorted(set(source)-observed),
        'graph_not_in_source_sequences': sorted(observed-set(source)),
        'source_not_in_postgres_names': sorted(source_names-pg_names),
        'postgres_not_in_source_names': sorted(pg_names-source_names),
        'name_mismatches': [r for r in graph if str(r['sequence']) in source and r['scientific_name'] != source[str(r['sequence'])][5].strip()],
        'inactive_or_disallowed_taxa': [r['id'] for r in graph if r['release']!=live['taxonomy_release'] or r['policy_status']!='allowed'],
    }


def fetch(url, expected_hash):
    with urlopen(Request(url, headers={'User-Agent':'RobinGraph read-only coverage audit'}), timeout=120) as response:
        body = response.read(100_000_001)
    if len(body)>100_000_000 or digest(body)!=expected_hash:
        raise ValueError('Source size or pinned SHA-256 mismatch')
    return body


def source_profiles():
    """Use the existing normalizers and pinned bytes; never invent mappings."""
    sys.path.insert(0,str(ROOT))
    from scripts import generate_n8n_reference_ingest as reference
    from scripts import generate_n8n_avonet_ingest as avonet
    from scripts.load_n8n_avonet import iter_worksheet_rows, normalize_row
    point = reference.load_approved_configuration()['traits-eltontraits-v1']
    config = {'trait_url':point['endpoint_uri'], 'trait_hash':point['expected_sha256']}
    elton_body = fetch(config['trait_url'], config['trait_hash'])
    try:
        elton_text=elton_body.decode('utf-8-sig'); encoding='utf-8-sig'
    except UnicodeDecodeError:
        elton_text=elton_body.decode('cp1252'); encoding='cp1252'
    rows = list(csv.DictReader(io.StringIO(elton_text), delimiter='\t'))
    # Execute the repository's JavaScript, preserving its validation semantics.
    wrapper = "const fs=require('fs'); const data=JSON.parse(fs.readFileSync(0,'utf8')); const $input={all:()=>data.rows.map(json=>({json}))}; const $=()=>({first:()=>({json:{raw_sha256:data.hash}})}); const normalize=()=>{"+reference.NORMALIZE_ELTON+"}; process.stdout.write(JSON.stringify(normalize()[0].json));"
    normalized = json.loads(subprocess.run(['node','-e',wrapper],input=json.dumps({'rows':rows,'hash':digest(elton_body)}),text=True,capture_output=True,check=True).stdout)
    elton = []
    for p in normalized['trait_profiles']:
        traits = {}
        for name, key in [('body_mass','body_mass_g'),('nocturnal','nocturnal'),('pelagic_specialist','pelagic_specialist'),('diet_category','diet_category')]:
            if p.get(key) is not None: traits[name]=bool(p[key]) if name in ('nocturnal','pelagic_specialist') else p[key]
        for name,key in [('diet_distribution','diet_distribution'),('foraging_strata_distribution','foraging_distribution')]:
            if any(v is not None for v in p[key].values()): traits[name]=p[key]
        elton.append({'record_id':'eltontraits-record:v1:'+p['source_taxon_id'],'scientific_name':p['scientific_name'],'traits':traits})
    avonet_body = fetch(avonet.URL,avonet.SHA256)
    ac = {'release':avonet.RELEASE,'url':avonet.URL,'sheet':avonet.SHEET,'fields':avonet.FIELDS}
    ap=[]
    for row_number,row in iter_worksheet_rows(io.BytesIO(avonet_body),avonet.SHEET):
        p=normalize_row(row,row_number,ac)
        ap.append({'record_id':p['id'],'scientific_name':p['scientific_name'],'traits':{c['trait_name']:c['value_num'] if c['value_num'] is not None else c['value_text'] for c in p['claims']}})
    return {'elton':elton,'avonet':ap}, {
        'elton':{'sha256':digest(elton_body),'url':config['trait_url'],'source_rows':len(rows),'valid_rows':len(elton),'encoding':encoding,'invalid_rows':normalized['trait_invalid_rows']},
        'avonet':{'sha256':digest(avonet_body),'url':avonet.URL,'sheet':avonet.SHEET,'source_rows':len(ap)},
    }


def decode_value(claim):
    if claim.get('value_json'):
        return json.loads(claim['value_json'])
    return next((claim.get(k) for k in ('value_num','value_text','value_boolean') if claim.get(k) is not None),None)


def candidate_traits(candidate, source):
    """Decode stored unresolved profile values without assigning a target taxon."""
    profile=json.loads(candidate['profile_json'])
    if source=='avonet':
        return {c['trait_name']:decode_value(c) for c in profile['claims']}
    traits={}
    for name,key in [('body_mass','body_mass_g'),('nocturnal','nocturnal'),
                     ('pelagic_specialist','pelagic_specialist'),('diet_category','diet_category')]:
        if profile.get(key) is not None:
            traits[name]=bool(profile[key]) if name in ('nocturnal','pelagic_specialist') else profile[key]
    for name,key in [('diet_distribution','diet_distribution'),('foraging_strata_distribution','foraging_distribution')]:
        if any(value is not None for value in profile.get(key,{}).values()):
            traits[name]=profile[key]
    return traits


def gate_reasons(row, context, live):
    """Explain the fixed TRAIT_QUERY gates, independent of display transforms."""
    c=row['claim']; reasons=[]; cursor=context['cursor']
    if context.get('policy_status','allowed')!='allowed': reasons.append('dataset_policy')
    if cursor.get('concept_set_id',cursor.get('taxonomy_concept_set_id'))!=live.get('concept_set_id'):
        reasons.append('active_concept_set_mismatch')
    if cursor.get('taxonomy_release')!=live['taxonomy_release']: reasons.append('active_taxonomy_release_mismatch')
    if c.get('policy_status')!='allowed': reasons.append('claim_policy')
    if c.get('source_release')!=cursor.get('trait_release',context['release']): reasons.append('inactive_source_release')
    if c.get('taxonomy_release') not in (None,live['taxonomy_release']): reasons.append('claim_taxonomy_release')
    if row.get('evidence_policy')!='allowed': reasons.append('evidence_policy_or_missing')
    if row.get('evidence_dataset')!=c.get('dataset_id'): reasons.append('evidence_dataset_mismatch')
    if row.get('evidence_record')!=c.get('source_record_id'): reasons.append('evidence_record_mismatch')
    return reasons


def audit_traits(live, profiles, labels):
    """Classify gaps for exact current names; unresolved concepts remain separate.

    'source_absent_exact_current_name' never means biologically absent: an old
    name or pre-split species can occur in the source and needs human review.
    Source -> DB value comparisons apply only to unique exact-name mappings.
    """
    taxa=live['taxa']; contexts={c['pipeline']:c for c in live['contexts']}
    sources={'elton':contexts.get('reference-taxonomy-traits'),'avonet':contexts.get('reference-avonet')}
    graph_by_name=defaultdict(list)
    for t in taxa: graph_by_name[t['scientific_name']].append(t)
    pg_ids={r['id'] for r in live['source_records']}
    raw=defaultdict(list)
    for row in live['claims']:
        c=row['claim']; raw[(c.get('dataset_id'),row['taxon_id'],c.get('trait_name'))].append(row)
    returned={(tid,t['dataset_id'],t['name']) for tid,ts in live['reader_traits'].items() for t in ts if t.get('dataset_id')}
    transformed={(tid,c['dataset_id'],c['name']) for tid,ts in live['reader_traits'].items()
                 for t in ts for c in t.get('source_claims',[]) if c.get('dataset_id')}
    result={}
    for source,ps in profiles.items():
        ctx=sources[source]
        if ctx is None:
            result[source]={'error':'no_active_context'}; continue
        ds=ctx['dataset_id']; counts=defaultdict(Counter); gaps=[]; mismatches=[]; no_pg=[]
        matched=[]; unresolved=[]; by_name=defaultdict(list)
        for p in ps:
            by_name[p['scientific_name']].append(p)
            if p['record_id'] not in pg_ids: no_pg.append(p['record_id'])
            matches=graph_by_name[p['scientific_name']]
            if len(matches)!=1:
                unresolved.append({'scientific_name':p['scientific_name'],'record_id':p['record_id'],'reason':'exact_name_not_found' if not matches else 'ambiguous_exact_name','traits':sorted(p['traits'])})
                continue
            matched.append(p)
        all_traits=sorted({trait for p in ps for trait in p['traits']})
        for t in taxa:
            ps_for_name=by_name[t['scientific_name']]
            for trait in all_traits:
                source_values=[p for p in ps_for_name if trait in p['traits']]
                key=(ds,t['id'],trait); rows=raw[key]
                if not ps_for_name: reason='source_absent_exact_current_name'
                elif len(ps_for_name)!=1: reason='ambiguous_source_name'
                elif not source_values: reason='source_field_absent'
                elif source_values[0]['record_id'] not in pg_ids: reason='source_record_missing_postgres'
                elif not rows: reason='source_present_claim_missing_graph'
                elif (t['id'],ds,trait) in returned: reason='readable'
                elif (t['id'],ds,trait) in transformed: reason='preserved_in_reviewed_trait'
                elif trait not in labels: reason='reader_trait_not_supported'
                else: reason='graph_claim_not_returned_by_reader'
                counts[trait][reason]+=1
                if source_values and reason not in ('readable','preserved_in_reviewed_trait'):
                    gaps.append({'taxon_id':t['id'],'scientific_name':t['scientific_name'],'trait':trait,'reason':reason,
                                 'query_gate_reasons':sorted({r for row in rows for r in gate_reasons(row,ctx,live)}) if reason=='graph_claim_not_returned_by_reader' else []})
                if len(source_values)==1 and len(ps_for_name)==1 and rows:
                    values=[]
                    for row in rows:
                        try: values.append(decode_value(row['claim']))
                        except (ValueError,TypeError): values.append('__invalid_json__')
                    if source_values[0]['traits'][trait] not in values:
                        mismatches.append({'taxon_id':t['id'],'scientific_name':t['scientific_name'],'trait':trait,'source_value':source_values[0]['traits'][trait],'db_values':values})
        candidates=[c for c in live['mapping_candidates'] if c['dataset_id']==ds]
        candidate_ids={c['source_record_id'] for c in candidates}
        profiles_by_id={p['record_id']:p for p in ps}
        candidate_value_issues=[]
        for c in candidates:
            p=profiles_by_id.get(c['source_record_id'])
            if p is None: continue
            try:
                values=candidate_traits(c,source)
                if values!=p['traits']:
                    candidate_value_issues.append({'record_id':p['record_id'],'reason':'candidate_value_mismatch'})
            except (KeyError,TypeError,ValueError):
                candidate_value_issues.append({'record_id':p['record_id'],'reason':'candidate_profile_missing_or_invalid'})
        result[source]={'dataset_id':ds,'source_profile_rows':len(ps),'exact_unique_mapped_profiles':len(matched),
            'unresolved_profiles':unresolved,'postgres_missing_source_record_ids':no_pg,
            'mapping_candidate_rows':len(candidates),'mapping_candidate_reasons':dict(Counter(c['reason'] for c in candidates)),
            'candidate_profile_value_issues':candidate_value_issues,
            'candidate_duplicate_record_ids':duplicate_keys(c['source_record_id'] for c in candidates),
            'candidate_policy_counts':dict(Counter(c.get('policy_status') for c in candidates)),
            'unresolved_without_candidate':[p['record_id'] for p in unresolved if p['record_id'] not in candidate_ids],
            'candidate_without_source_profile':sorted(candidate_ids-{p['record_id'] for p in ps}),
            'coverage_by_trait':{k:dict(v) for k,v in counts.items()},'gaps':gaps,'value_mismatches':mismatches,
            'source_trait_counts':dict(Counter(trait for p in ps for trait in p['traits'])),
            'raw_graph_claim_rows':sum(len(rows) for (dataset,_,_),rows in raw.items() if dataset==ds),
            'graph_duplicate_claim_keys':[{'taxon_id':tid,'trait':trait,'rows':len({row['claim']['id'] for row in rows})} for (dataset,tid,trait),rows in raw.items() if dataset==ds and len({row['claim']['id'] for row in rows})>1],
        }
    return result


def sample_comparison(live):
    output=[]
    names={t['scientific_name']:t['id'] for t in live['taxa']}
    for api in live['api_samples']:
        name=api.get('taxon',{}).get('scientific_name') if api.get('taxon') else api['query']
        tid=names.get(name)
        raw=[r['claim'] for r in live['claims'] if r['taxon_id']==tid]
        reader=live['reader_traits'].get(tid,[])
        def canonical(ts):
            return sorted((t['name'],t.get('dataset_id',''),json.dumps(t.get('value'),sort_keys=True,ensure_ascii=False)) for t in ts)
        output.append({**api,'raw_claim_count':len(raw),'raw_trait_names':sorted({c['trait_name'] for c in raw}),
                       'reader_traits':reader,'api_equals_read_traits':canonical(api.get('traits',[]))==canonical(reader),
                       'note':'Profile may apply reviewed traits beyond read_traits; compare provenance and values.'})
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ssh',default='kimdove@192.168.219.99')
    parser.add_argument('--port',type=int,default=99)
    parser.add_argument('--control-path',default='/tmp/rg-conservation-ssh.sock')
    parser.add_argument('--container',default='robingraph-api-test',choices=['robingraph-api-test'])
    args=parser.parse_args()
    snapshot_body=args.snapshot.read_bytes(); snapshot=json.loads(snapshot_body)
    profiles,source_info=source_profiles()
    remote='docker exec -i '+shlex.quote(args.container)+' python -'
    process=subprocess.run(['ssh','-p',str(args.port),'-o','BatchMode=yes','-o','ControlPath='+args.control_path,args.ssh,remote],input=COLLECTOR,text=True,capture_output=True,timeout=900)
    if process.returncode:
        # Never echo connection exceptions, environment values, or credentials.
        raise SystemExit('TEST read-only collector failed; stderr deliberately withheld')
    live=json.loads(process.stdout)
    from robingraph.retrieval.species_profile import LABELS, read_traits, TRAIT_QUERY
    import inspect
    result={k:live[k] for k in ['mode','checked_at','postgres_read_only','contexts','concept_sets','concept_set_id','taxonomy_release','quarantine','reader_sha256','trait_query_sha256','reader_query_rows','reader_errors','reader_limit_species']}
    result.update(avilist_snapshot={'path':str(args.snapshot),'sha256':digest(snapshot_body),'source_rows':len(snapshot)},
                  source_snapshots=source_info,taxonomy=compare_taxonomy(snapshot,live),
                  traits=audit_traits(live,profiles,LABELS),samples=sample_comparison(live),
                  local_reader_matches_deployed=digest(inspect.getsource(read_traits).encode())==live['reader_sha256'],
                  local_query_matches_deployed=digest(TRAIT_QUERY.encode())==live['trait_query_sha256'],
                  qualifications=['Exact name absence is a source-taxonomy coverage gap, not proof of biological data absence.',
                    'All-species read_traits results replay live database rows through the deployed function; HTTP API was checked only for samples.',
                    'PostgreSQL payloads store source identities and selected metadata, not full trait values; values were compared with downloaded pinned originals.',
                    'Neo4j read access is a driver routing mode, not server-enforced read-only credentials; queries are fixed MATCH templates.',
                    'No automatic synonym matching or inheritance of pre-split Pica pica evidence to Pica serica.'])
    result['avilist_stored_checksum_matches']=bool(live['concept_sets']) and all(s['sha256']==digest(snapshot_body) for s in live['concept_sets'])
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'taxonomy':result['taxonomy'],'reader_errors':len(live['reader_errors']),
                     'sources':{s:{k:len(v) if isinstance(v,list) else v for k,v in data.items() if k in ['source_profile_rows','exact_unique_mapped_profiles','unresolved_profiles','postgres_missing_source_record_ids','value_mismatches']} for s,data in result['traits'].items()}},ensure_ascii=False))


if __name__=='__main__':
    main()
