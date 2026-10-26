"""Independent read-only check of API result scope and every original condition."""
import json,math,sys
from collections import defaultdict
from pathlib import Path
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
p=Path(sys.argv[1]); report=json.loads((p/('independent-api-'+sys.argv[2]+'.json')).read_text())
inventory=json.loads((p/'inventory.json').read_text());parents=defaultdict(set)
for edge in inventory['parent_edges']:parents[edge['child']].add(edge['parent'])
taxa={t['id']:t for t in inventory['taxa']};science={t['scientific_name']:t['id'] for t in inventory['taxa']}
ids=sorted({item['taxon']['taxon_id'] for row in report['rows'] if row['response'] for item in row['response']['result'].get('payload',{}).get('items',[])})
store=IngestionStore(PostgresSettings.from_environment());sources=[]
for pipeline in ('reference-avonet','reference-taxonomy-traits'):
 c=store.active_release_context(pipeline);assert c
 sources.append(dict(dataset_id=c.dataset.id,release=c.cursor.get('trait_release',c.release.release_key)))
with Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment()) as repo:
 claims=repo._run("""MATCH (ctx:TaxonConceptSet {id:$concept,version:$release,policy_status:'allowed'})<-[:IN_CONCEPT_SET]-(t:Taxon:BirdTaxon {source_release:$release,policy_status:'allowed'})<-[:ASSERTS_ABOUT]-(c:TraitClaim {policy_status:'allowed'})-[:SUPPORTED_BY]->(e:EvidenceUnit {policy_status:'allowed'}) WHERE c.trait_name IN $fields AND any(s IN $sources WHERE s.dataset_id=c.dataset_id AND s.release=c.source_release) AND (c.taxonomy_release IS NULL OR c.taxonomy_release=$release) AND e.dataset_id=c.dataset_id AND e.source_record_id=c.source_record_id AND (e.locator STARTS WITH 'https://' OR e.locator STARTS WITH 'http://') RETURN t.id AS taxon_id,c{.trait_name,.inferred,.certainty,.value_text,.value_num,.value_json,.unit} AS claim,e.locator AS source_url""",fields=sorted({c['trait_name'] for r in report['rows'] for c in r['case']['conditions']}),sources=sources,concept=inventory['concept_set_id'],release=inventory['taxonomy_release'])
by=defaultdict(list)
for row in claims:by[(row['taxon_id'],row['claim']['trait_name'])].append(row['claim'])
def in_scope(taxon,root):
 if taxon==root:return True
 seen=set();todo=list(parents[taxon])
 while todo:
  node=todo.pop()
  if node==root:return True
  if node not in seen:seen.add(node);todo+=list(parents[node])
 return False

def supports(claim,condition):
 if not (claim.get('inferred') is False or (claim.get('inferred') is None and condition['trait_name'] in ('diet_category','diet_distribution') and claim.get('certainty') in ('A','B','C'))):return False
 value=condition['value'];op=condition['op']
 if op=='eq':return claim.get('value_text')==value
 if op=='share_gt':
  key,threshold=next(iter(value.items()));raw=claim.get('value_json')
  try:amount=json.loads(raw).get(key)
  except (ValueError,TypeError,AttributeError):return False
  return type(amount) in (int,float) and math.isfinite(amount) and threshold<amount<=100 and claim.get('certainty') in ('A','B','C')
 amount=claim.get('value_num')
 if type(amount) not in (int,float) or not math.isfinite(amount) or claim.get('unit')!=condition['unit']:return False
 return {'gte':amount>=value,'lte':amount<=value,'gt':amount>value,'lt':amount<value}[op]
def eligible(claim):
 return claim.get('inferred') is False or (claim.get('inferred') is None and claim['trait_name'] in ('diet_category','diet_distribution') and claim.get('certainty') in ('A','B','C'))
errors=[];checked=0;counts_checked=0;scope_cache={}
for row in report['rows']:
 case=row['case']; response=row['response']
 if case['outcome'] not in ('query','empty') or not response:continue
 root=science.get(case['taxon']) if case['taxon'] else None
 if root not in scope_cache:
  scope_cache[root]=([root] if root and taxa[root]['rank'] in ('species','subspecies') else [tid for tid,t in taxa.items() if t['rank']=='species' and (root is None or in_scope(tid,root))])
 scope=scope_cache[root]
 evaluable=[tid for tid in scope if all(any(eligible(c) for c in by[(tid,condition['trait_name'])]) for condition in case['conditions'])]
 expected=[tid for tid in evaluable if all(any(supports(c,condition) for c in by[(tid,condition['trait_name'])]) for condition in case['conditions'])]
 payload=response['result'].get('payload',{}); actual_ids=[x['taxon']['taxon_id'] for x in payload.get('items',[])]
 expected_stats={'scoped':len(scope),'evaluable':len(evaluable),'matched':len(expected)}
 if payload.get('coverage')!=expected_stats:errors.append([case['id'],'coverage_mismatch',payload.get('coverage'),expected_stats])
 expected_status='answer' if expected else ('insufficient_data' if scope and not evaluable else 'empty')
 if payload.get('status')!=expected_status:errors.append([case['id'],'status_mismatch',payload.get('status'),expected_status])
 if len(actual_ids)!=min(20,len(expected)) or not set(actual_ids)<=set(expected):errors.append([case['id'],'result_membership_mismatch'])
 if bool(payload.get('has_more'))!=(len(expected)>20):errors.append([case['id'],'pagination_mismatch'])
 counts_checked+=1

for row in report['rows']:
 case=row['case']
 if not row['response']:continue
 for item in row['response']['result'].get('payload',{}).get('items',[]):
  tid=item['taxon']['taxon_id'];root=science.get(case['taxon']) if case['taxon'] else None
  if root and not in_scope(tid,root):errors.append([case['id'],tid,'outside_taxon_scope'])
  if root and case['rank'] in ('species','subspecies') and tid!=root:errors.append([case['id'],tid,'self_scope_broadened'])
  for condition in case['conditions']:
   checked+=1
   if not any(supports(c,condition) for c in by[(tid,condition['trait_name'])]):errors.append([case['id'],tid,'missing_condition_support',condition['trait_name']])
print(json.dumps({'scope':'Actual TEST direct claim and ancestry verification, independent of production filter query','unique_returned_taxa':len(ids),'checked_condition_supports':checked,'checked_exact_scope_and_match_counts':counts_checked,'errors':errors,'passed':not errors,'bird_db_writes':0}));assert not errors
