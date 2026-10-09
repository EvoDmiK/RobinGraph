#!/usr/bin/env python3
"""Audit all active species using live DB rows and deployed readers.
Run inside the configured API container: python - < scripts/audit_active_species_runtime.py
No DB writes. Trait/conservation queries are batched then replayed through the
runtime readers; accepted candidate recovery uses real DB queries. Korean name
lookups execute the actual repository path. This is not an all-species HTTP test.
JSON goes to stdout; credentials are never serialized.
"""
import json,collections,datetime,os,sys
from types import SimpleNamespace as NS
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage,LineageTaxon,sourced_korean_names
from robingraph.retrieval import species_profile as sp
store=IngestionStore(PostgresSettings.from_environment())
contexts={p:store.active_release_context(p) for p in ['reference-taxonomy-traits','reference-avonet']}
ctx=contexts['reference-taxonomy-traits'];cur=ctx.cursor
concept=cur.get('concept_set_id',cur.get('taxonomy_concept_set_id'));release=cur['taxonomy_release']
repo=Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment(),active_taxonomy_context=lambda:(concept,release))
taxa=repo._run("MATCH (t:Taxon {rank:'species',policy_status:'allowed'})-[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:$concept}) RETURN t.id AS id,t.scientific_name AS scientific_name,t.authority AS authority",concept=concept)
sources=[{'dataset_id':c.dataset.id,'release':c.cursor.get('trait_release',c.release.release_key)} for c in contexts.values() if c]
q=sp.TRAIT_QUERY.replace('{id:$taxon_id}',"{rank:'species'}").replace('RETURN c{.*}','RETURN t.id AS tid, c{.*}').replace('LIMIT 100','')
traits=collections.defaultdict(list)
for r in repo._run(q,concept_set_id=concept,taxonomy_release=release,sources=sources):traits[r.pop('tid')].append(r)
q=sp.CONSERVATION_QUERY.replace('id:$taxon_id, ', '').replace('RETURN t.iucn','RETURN t.id AS tid, t.iucn')
conservation=collections.defaultdict(list)
for r in repo._run(q,concept_set_id=concept,taxonomy_release=release):conservation[r.pop('tid')].append(r)
real_run=repo._run
store.active_release_context=lambda p:contexts.get(p)
results=[];errors=[]
detail_ids=set(os.environ.get('ROBINGRAPH_AUDIT_DETAIL_IDS','').split(',')) - {''}
for t in taxa:
 tid=t['id'];lineage=TaxonomyLineage(t['scientific_name'],'AviList',release,concept,(LineageTaxon(tid,'species',t['scientific_name'],t['authority']),))
 def run(query,**params):
  if query==sp.TRAIT_QUERY:return traits[tid][:100]
  if query==sp.CONSERVATION_QUERY:return conservation[tid]
  return real_run(query,**params)
 adapter=NS(_run=run)
 try:
  ts=sp.read_traits(adapter,store,lineage);cs=sp.read_conservation(adapter,lineage)
  result={**t,'trait_names':sorted({v['name'] for v in ts}),'trait_count':len(ts),'alignment':dict(collections.Counter(v.get('taxonomy_alignment',{}).get('status','none') for v in ts)), 'conservation':cs}
  if tid in detail_ids: result['traits']=ts
  results.append(result)
 except Exception as e:errors.append({'id':tid,'type':type(e).__name__})
 if (len(results)+len(errors)) % 1000 == 0:
  print('Audited species: '+str(len(results)+len(errors)),file=sys.stderr,flush=True)
ko=[]
for tid,label in sourced_korean_names().items():
 try:
  found=repo.lineage_for_korean_name(label['name']);actual=found.items[-1] if found and found.items else None
  ko.append({'query':label['name'],'expected_id':tid,'actual_id':actual.taxon_id if actual else None,'ok':bool(actual and actual.taxon_id==tid and actual.scientific_name==label['scientific_name'])})
 except Exception as e:ko.append({'query':label['name'],'ok':False,'error':type(e).__name__})
 if len(ko) % 100 == 0: print('Audited Korean lookups: '+str(len(ko)),file=sys.stderr,flush=True)
print(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'live DB batch rows replayed through deployed readers; actual Korean lineage queries','species_count':len(taxa),'errors':errors,'species':results,'korean_lookups':ko},ensure_ascii=False))
repo.close()
