from pathlib import Path
import subprocess,json
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
source=(root/'src/robingraph/retrieval/graph_questions.py').read_text()
program='''import os,json,sys,types
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
settings=Neo4jSettings.from_environment();pg=PostgresSettings.from_environment()
assert settings.uri=='bolt://192.168.219.98:7687' and pg.database=='robingraph_test'
store=IngestionStore(pg)
def context():
 c=store.active_release_context('reference-taxonomy-traits');return c.cursor['concept_set_id'],c.cursor['taxonomy_release']
r=Neo4jTaxonomyLineageRepository(settings,lambda:store.active_dataset_id('korean-vernacular-names'),context)
def resolve(name):
 if any('가'<=c<='힣' for c in name):return r.lineage_for_korean_name(name)
 return r.lineage_for_scientific_name(name) or r.lineage_for_english_name(name)
m=types.ModuleType('robingraph.retrieval.graph_questions');m.__package__='robingraph.retrieval';sys.modules[m.__name__]=m
exec(SOURCE,m.__dict__)
qs=QUESTIONS
rows=[]
for q in qs:
 p=m.parse_graph_question(q)
 try: answer=m.graph_question_answer(r,resolve,p,store=store) if p else None
 except Exception as e:answer={'error':type(e).__name__,'detail':str(e)}
 rows.append({'question':q,'parsed':str(p),'answer':answer})
r.close()
print(json.dumps({'target':'test','read_only':True,'rows':rows},ensure_ascii=False,indent=2))
'''.replace('SOURCE',repr(source)).replace('QUESTIONS',repr(['청둥오리와 흰뺨검둥오리는 어떤 관계야?','청둥오리와 같은 속에 속하는 새를 보여줘','한국에 기록된 오리 중 청둥오리와 같은 속인 종은?','참새목 중 열매를 먹고 사는 새는?','숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?','청둥오리와 서식지가 겹치면서 먹이가 다른 새는?','숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?']))
r=subprocess.run(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-'],input=program,text=True,capture_output=True,check=True)
out=root/'docs/verification/assets/2026-10-22-graph-relationship-qa/predeploy-retrieval.json';out.write_text(r.stdout)
d=json.loads(r.stdout)
for x in d['rows']:
 a=x['answer']; print(x['question'],a.get('status') if a else None,len(a.get('items',[])) if a else 0,a.get('error') if a else None)
