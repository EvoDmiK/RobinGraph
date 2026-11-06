"""Actual TEST DB reads in an isolated Python process; serving app remains unchanged."""
import importlib.util,json,sys
from pathlib import Path
base=Path('/tmp/rg-taxonomic-stage1')
for n in ('graph_questions','graph_intent_schema','graph_condition_extractor'):
 name='robingraph.retrieval.'+n;spec=importlib.util.spec_from_file_location(name,base/(n+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
from robingraph.retrieval.graph_questions import graph_question_answer
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate,to_graph_question
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
store=IngestionStore(PostgresSettings.from_environment());rows=[]
def resolve(name):raise AssertionError('These exact taxonomy names need no vector or species fallback')
with Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment()) as repo:
 for q in ['까마귀과면서 열매를 먹는 새는 어떤 종이 있어?','Corvidae 중 열매를 먹는 새는?','Corvus 중 열매를 먹는 새는?','Corvus corone 중 열매를 먹는 새는?','Corvus corone corone 중 열매를 먹는 새는?']:
  i=extract_graph_intent(q);assert execution_gate(q,i)=='answer',(q,execution_gate(q,i));parsed=to_graph_question(q,i);out=graph_question_answer(repo,resolve,parsed,store=store);rows.append({'question':q,'response':out})
assert rows[0]['response']['status']=='answer' and rows[0]['response']['items']
assert rows[-1]['response']['status']=='insufficient_data' and '부모 종' in rows[-1]['response']['text']
print(json.dumps({'scope':'Stage 1: exact user reproduction, canonical family/genus/species/subspecies; actual TEST Neo4j/Postgres, isolated Python only','public_app_replaced':False,'bird_db_writes':0,'rows':rows},ensure_ascii=False))
