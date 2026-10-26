import os,json,time,statistics,math
from neo4j import GraphDatabase,Query
from robingraph.retrieval import taxon_name_vectors_neo4j as m
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test' and os.environ['NEO4J_URI']=='bolt://192.168.219.98:7687'
def stat(v):
 v=sorted(v);return {'n':len(v),'p50_ms':round(statistics.median(v),3),'p95_ms':round(v[math.ceil(.95*len(v))-1],3),'max_ms':round(max(v),3)}
with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD'])) as d:
 with d.session(database=os.getenv('NEO4J_DATABASE','neo4j'),default_access_mode='READ') as s:
  c=s.run(Query('MATCH(c:TaxonNameVectorCatalog {id:$id}) RETURN properties(c) AS c',timeout=10),id=m.CATALOG_ID).single()['c']
  vectors=s.run(Query('MATCH(n:TaxonNameVector) WHERE n.scientific_name IN $names RETURN n.scientific_name AS name,n.taxon_id AS id,n.name_vector AS vector',timeout=10),names=['Anas platyrhynchos','Anas zonorhyncha','Nestor notabilis']).data();assert len(vectors)==3
  base=dict(catalog_id=m.CATALOG_ID,fingerprint=c['fingerprint'],model=c['model'],dimensions=c['dimensions'],normalized=c['normalized'],concept_set_id=c['concept_set_id'],release=c['taxonomy_release'],index_name=m.INDEX_NAME,limit=5)
  rows=[]
  for v in vectors:
   samples=[]
   for i in range(21):
    start=time.perf_counter();hits=s.run(Query(m._SEARCH,timeout=10),**base,vector=v['vector']).data();elapsed=(time.perf_counter()-start)*1000
    assert hits and hits[0]['taxon_id']==v['id'] and all(0<=h['score']<=1 for h in hits)
    if i:samples.append(elapsed)
   rows.append({'scientific_name':v['name'],'self_match_all_calls':True,'neo4j_roundtrip':stat(samples)})
  print(json.dumps({'target':'test','catalog_count':c['count'],'scope':'existing stored name vectors, application fixed Cypher only, no embedding and no full repository preflight; warm sequential concurrency1','rows':rows},indent=2))
