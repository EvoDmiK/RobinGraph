import hashlib,json,os,math
if not __debug__:raise SystemExit("Optimized execution is forbidden for this guarded operator")
from pathlib import Path
from neo4j import GraphDatabase
import psycopg
from robingraph.embeddings import JinaEmbeddingClient
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval import taxon_name_vectors_neo4j as module

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()

def environment(expected):
 assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')==expected, 'Wrong deployment target'
 p=PostgresSettings.from_environment();n=Neo4jSettings.from_environment()
 assert p.schema=='ingest', 'Unexpected ingest schema'
 if expected=='test':
  assert (p.host,p.port,p.database,p.username)==('192.168.219.99',5433,'robingraph_test','robingraph_test_app')
  assert n.uri=='bolt://192.168.219.98:7687'
 else:
  assert expected=='prod' and p.database=='robingraph' and n.uri=='bolt://neo4j:7687'
  identity=dict(pg_host=p.host,pg_port=p.port,pg_database=p.database,pg_username=p.username,neo4j_uri=n.uri,neo4j_database=n.database)
  pinned=globals().get('PINNED_PRODUCTION_IDENTITY')
  if pinned is not None:assert identity==pinned, 'Production connection identity changed'
 return p,n

def reviewed(expected):
 p,n=environment(expected);store=IngestionStore(p)
 def context():
  active=store.active_release_context('reference-taxonomy-traits')
  assert active is not None, 'No active reviewed taxonomy'
  return module._context((active.cursor.get('concept_set_id'),active.cursor.get('taxonomy_release')))
 before=context()
 taxonomy=Neo4jTaxonomyLineageRepository(n,lambda:store.active_dataset_id('korean-vernacular-names'),context)
 try:inventory=module._inventory(taxonomy.reviewed_name_candidates())
 finally:taxonomy.close()
 assert context()==before, 'Taxonomy changed during inventory read'
 client=JinaEmbeddingClient.from_env()
 return p,n,before,inventory,client

def snapshot(expected):
 p,n,context,inventory,client=reviewed(expected)
 with psycopg.connect(**p.connection_kwargs()) as c:
  c.execute('SET TRANSACTION READ ONLY')
  states=c.execute('select pipeline_id,active_release_id,last_successful_run_id,cursor,version from ingest.ingest_state order by pipeline_id').fetchall()
 with GraphDatabase.driver(n.uri,auth=(n.username,n.password)) as driver:
  with driver.session(database=n.database,default_access_mode='READ') as s:
   entries=s.run('MATCH (n:TaxonNameVectorEntry) RETURN properties(n) AS properties,labels(n) AS labels,[(n)-[:NAME_VECTOR_OF]->(t)|{id:t.id,scientific_name:t.scientific_name}] AS targets ORDER BY n.key').data()
   for entry in entries:
    entry['labels']=sorted(entry['labels'])
    entry['targets']=sorted(entry['targets'],key=lambda target:(target['id'],target['scientific_name']))
   catalogs=s.run('MATCH (n:TaxonNameVectorCatalog) RETURN properties(n) AS properties,labels(n) AS labels ORDER BY n.id').data()
   schema=s.run(module._SHOW_INDEX,name=module.INDEX_NAME).data()
   constraint=s.run(module._SHOW_CONSTRAINT,name=module.CONSTRAINT_NAME).data()
   feature_count=s.run('MATCH(n:TaxonNameVector) RETURN count(n) AS count').single()['count']
   taxa=s.run('MATCH(n:Taxon) RETURN properties(n) AS properties ORDER BY n.id').data()
 profile=list(module._profile(client.profile))
 return {'target':expected,'connection_identity':dict(pg_host=p.host,pg_port=p.port,pg_database=p.database,pg_username=p.username,neo4j_uri=n.uri,neo4j_database=n.database),'context':list(context),'inventory':inventory,'profile':profile,
  'endpoint_sha256':hashlib.sha256(client.settings.endpoint.encode()).hexdigest(),
  'fingerprint':module.catalog_fingerprint(inventory,tuple(profile),context),
  'feature_count':feature_count,'entries':entries,'catalogs':catalogs,'schema':schema,'constraint':constraint,
  'taxon_count':len(taxa),'taxon_properties_sha256':digest(taxa),'ingest_states_sha256':digest(states),
  'module_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}

def validate_source(source):
 assert source['target']=='test'
 assert set(source['catalogs'][0]['labels'])=={'TaxonNameVectorCatalog'} if len(source['catalogs'])==1 else False
 inventory=module._inventory(source['inventory']);context=tuple(source['context']);profile=tuple(source['profile'])
 fingerprint=module.catalog_fingerprint(inventory,profile,context)
 assert source['fingerprint']==fingerprint and len(source['catalogs'])==1
 catalog=source['catalogs'][0]['properties']
 assert catalog==dict(id=module.CATALOG_ID,fingerprint=fingerprint,model=profile[0],dimensions=profile[1],normalized=profile[2],concept_set_id=context[0],taxonomy_release=context[1],count=len(inventory),index_name=module.INDEX_NAME)
 expected={row['taxon_id']:row for row in inventory};vectors={}
 active=[e for e in source['entries'] if module.FEATURE_LABEL in e['labels']]
 assert len(active)==len(inventory)==source['feature_count']
 assert len(source['schema'])==1 and len(source['constraint'])==1
 class RecordedSchema:
  def run(self,query,**_):
   rows=source['schema'] if query==module._SHOW_INDEX else source['constraint']
   class Result:
    def data(self):return rows
   return Result()
 assert module._index_state(RecordedSchema(),profile[1],require_online=True)=='compatible'
 assert module._constraint_state(RecordedSchema())=='compatible'
 for e in active:
  p=e['properties'];row=expected.get(p['taxon_id']);assert row is not None
  assert set(e['labels'])=={module.FEATURE_LABEL,module.ENTRY_LABEL}
  assert all(p.get(k)==v for k,v in row.items()) and p['text_hash']==module._text_hash(row['text'])
  assert p['key']==module._entry_key(p['taxon_id'],profile,context)
  assert (p['model'],p['dimensions'],p['normalized'],p['concept_set_id'],p['taxonomy_release'],p['catalog_fingerprint'])==(*profile,*context,fingerprint)
  assert e['targets']==[{'id':p['taxon_id'],'scientific_name':p['scientific_name']}]
  assert p['taxon_id'] not in vectors
  module._vector(p['name_vector'],profile[1])
  assert abs(math.hypot(*p['name_vector'])-1)<1e-6
  vectors[p['taxon_id']]=p['name_vector']
 assert set(vectors)==set(expected)
 return vectors

def validate_destination(source,target):
 assert target['target']=='prod'
 for key in ('context','inventory','profile','fingerprint','module_sha256'):
  assert source[key]==target[key], 'Source and destination differ: '+key
 assert target['feature_count']==0 and not target['entries'] and not target['catalogs'], 'Destination is not empty; do not overwrite'
 # Existing repository validates dimensions, index type, allowed concept and taxon links.
 _,n,context,inventory,client=reviewed('prod')
 with module.Neo4jTaxonNameVectorRepository(n) as repository:
  plan=repository.index_names(inventory,client,context,dry_run=True)
 assert plan['to_embed']==len(inventory) and plan['stale']==0
 return plan

def probe_model(source):
 vectors=validate_source(source)
 _,_,_,inventory,client=reviewed('prod')
 chosen=[inventory[i] for i in sorted({0,len(inventory)//2,len(inventory)-1})]
 fresh=client.embed_documents([row['text'] for row in chosen])
 assert len(fresh)==len(chosen)
 scores=[]
 for row,vector in zip(chosen,fresh):
  old=module._vector(vectors[row['taxon_id']],source['profile'][1]);new=module._vector(vector,source['profile'][1])
  cosine=sum(a*b for a,b in zip(old,new));assert cosine>0.99999, 'Production model differs from exported embeddings'
  scores.append(cosine)
 return {'texts':len(chosen),'cosines':scores,'purpose':'compatibility validation only; copied catalog is not regenerated'}

def apply_source(source,expected_before):
 assert globals().get('PINNED_PRODUCTION_IDENTITY') is not None, 'Explicit reviewed Production identity required before writes'
 before=snapshot('prod')
 assert digest(before)==expected_before, 'Production changed since reviewed preflight'
 vectors=validate_source(source);validate_destination(source,before)
 probe=probe_model(source)
 _,settings,context,inventory,client=reviewed('prod')
 class Cached:
  profile=client.profile
  calls=0
  def embed_documents(self,texts):
   assert list(texts)==[row['text'] for row in inventory], 'Concurrent destination changes; refuse partial or reordered import'
   self.calls+=1
   return [vectors[row['taxon_id']] for row in inventory]
 cache=Cached()
 with module.Neo4jTaxonNameVectorRepository(settings) as repository:
  result=repository.index_names(inventory,cache,context,dry_run=False)
  assert cache.calls==1 and result['embedded']==len(inventory)
  queries=[]
  for name in ('Anas platyrhynchos','Anas zonorhyncha','Nestor notabilis'):
   row=next(item for item in inventory if item['scientific_name']==name)
   hits=repository.search(vectors[row['taxon_id']],client.profile,context,inventory,limit=5)
   assert any(hit['taxon_id']==row['taxon_id'] and hit['score']>0.9999 for hit in hits), 'Actual vector self-query failed'
   scoped=repository.search(vectors[row['taxon_id']],client.profile,context,inventory,limit=1,eligible_taxon_ids=[row['taxon_id']])
   assert len(scoped)==1 and scoped[0]['taxon_id']==row['taxon_id']
   queries.append({'scientific_name':name,'global_self_match':True,'scoped_match':True})
 after=snapshot('prod')
 check=dict(after,target='test');copied=validate_source(check)
 max_difference=max(abs(a-b) for key in vectors for a,b in zip(vectors[key],copied[key]))
 assert max_difference<1e-12, 'Copied vectors differ beyond floating-point unit normalization'
 assert set(copied)==set(vectors)
 for key in ('taxon_count','taxon_properties_sha256','ingest_states_sha256','context','inventory','profile','fingerprint','module_sha256'):
  assert after[key]==before[key], 'Unrelated state changed: '+key
 return {'state':'verified','target':'prod','count':len(inventory),'fingerprint':source['fingerprint'],
  'profile':source['profile'],'context':source['context'],'repository_result':result,'cache_calls':cache.calls,
  'external_embedding_calls_for_copy':0,'compatibility_probe':probe,'max_vector_component_difference':max_difference,
  'actual_vector_queries':queries,'taxon_count':after['taxon_count'],'taxon_properties_unchanged':True,
  'ingest_states_unchanged':True,'schema':after['schema'],'constraint':after['constraint'],
  'destination_after_sha256':digest(after),'automatic_rollback_performed':False}
