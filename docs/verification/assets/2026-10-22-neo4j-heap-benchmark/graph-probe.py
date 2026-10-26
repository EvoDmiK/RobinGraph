import json,os,time,math,statistics,hashlib
from collections import defaultdict
from neo4j import GraphDatabase,Query
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.graph_questions import parse_graph_question,graph_question_answer
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
n=Neo4jSettings.from_environment();p=PostgresSettings.from_environment()
assert n.uri=='bolt://192.168.219.98:7687' and p.database=='robingraph_test'
store=IngestionStore(p)
def context():
 c=store.active_release_context('reference-taxonomy-traits');return c.cursor['concept_set_id'],c.cursor['taxonomy_release']
class Probe(Neo4jTaxonomyLineageRepository):
 def __init__(self,*a):super().__init__(*a);self.timings=[]
 def _run(self,query,**params):
  start=time.perf_counter()
  with self._driver.session(database=n.database,default_access_mode='READ') as s:
   result=s.run(Query(query,timeout=20),**params);rows=result.data();meta=result.consume()
  self.timings.append({'wall_ms':(time.perf_counter()-start)*1000,'server_available_ms':meta.result_available_after,'server_consumed_ms':meta.result_consumed_after})
  return rows
r=Probe(n,lambda:store.active_dataset_id('korean-vernacular-names'),context)
def resolve(name):return r.lineage_for_korean_name(name)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def stat(v):
 v=sorted(v);return {'n':len(v),'p50_ms':round(statistics.median(v),3),'p95_ms':round(v[math.ceil(.95*len(v))-1],3),'max_ms':round(max(v),3)}
qs=['청둥오리와 흰뺨검둥오리는 어떤 관계야?','청둥오리와 같은 속에 속하는 새를 보여줘','한국에 기록된 오리 중 청둥오리와 같은 속인 종은?','참새목 중 열매를 먹고 사는 새는?','청둥오리와 서식지가 겹치면서 먹이가 다른 새는?','숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?']
rows={q:{'wall':[],'db':[],'server':[],'queries':[],'hashes':set(),'first_call_ms':None} for q in qs}
try:
 for repeat in range(21):
  # Rotate order to reduce fixed sequence effects. First complete round excluded.
  for q in qs[repeat%len(qs):]+qs[:repeat%len(qs)]:
   r.timings=[];start=time.perf_counter();a=graph_question_answer(r,resolve,parse_graph_question(q),store=store);elapsed=(time.perf_counter()-start)*1000
   x=rows[q]
   assert a['status']=='answer',(q,a['status'])
   if repeat==0:x['first_call_ms']=round(elapsed,3);continue
   x['wall'].append(elapsed);x['db'].append(sum(t['wall_ms'] for t in r.timings));x['server'].append(sum((t['server_available_ms'] or 0)+(t['server_consumed_ms'] or 0) for t in r.timings));x['queries'].append(len(r.timings));x['hashes'].add(digest(a));x['result_count']=len(a.get('items',[]))
 out=[]
 for q,x in rows.items():
  assert len(x['hashes'])==1,'Unstable answer'
  out.append({'question':q,'kind':parse_graph_question(q).kind,'first_observed_call_ms':x['first_call_ms'],'warm_total_including_pg_and_python':stat(x['wall']),'neo4j_roundtrip_sum':stat(x['db']),'neo4j_reported_duration_sum':stat(x['server']),'cypher_queries_per_answer':sorted(set(x['queries'])),'answer_stable':True,'result_count':x['result_count']})
 print(json.dumps({'target':'test','repeats':20,'concurrency':1,'warmup_rounds_excluded':1,'scope':'actual current graph relationship repository; sequential; PG reads and Python included in total; no HTTP/Jev/embedding','rows':out},ensure_ascii=False,indent=2))
finally:r.close()
