"""Actual public TEST API alias equivalence and unsupported-condition checks."""
import json,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent
phase=sys.argv[1]
base='https://robingraph-test.dove-nest.com'
rows=[]
cached=json.loads((p/(phase+'.json')).read_text())['rows'] if len(sys.argv)>2 and sys.argv[2]=='recheck' else None
def post(q):
 if cached is not None:
  row=cached.pop(0);assert row['question']==q;rows.append(row);return row['response']
 start=time.perf_counter()
 req=Request(base+'/v1/chat',data=json.dumps({'question':q,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 RobinGraph-Regression'})
 body=json.load(urlopen(req,timeout=35))
 rows.append({'question':q,'response':body,'elapsed_ms':round((time.perf_counter()-start)*1000,2)})
 return body

def signature(r):
 d=r['result'].get('payload',{})
 return {k:d.get(k) for k in ('status','taxon','conditions','coverage','items','has_more')}
checks=[]
for taxon in ('참새목','까마귀과','Corvus','청둥오리','Anas platyrhynchos platyrhynchos'):
 for alias,raw in (('곤충','무척추동물'),('고기','척추동물')):
  question=f'{taxon} 중에서 {alias}을 먹는 새는?' if alias=='곤충' else f'{taxon} 중에서 {alias}를 먹는 새는?'
  raw_q=f'{taxon} 중에서 {raw}을 먹는 새는?'
  a,b=post(question),post(raw_q)
  data=a['result'].get('payload',{})
  errors=[]
  expected_taxon={'참새목':('Passeriformes','order'),'까마귀과':('Corvidae','family'),'Corvus':('Corvus','genus'),'청둥오리':('Anas platyrhynchos','species'),'Anas platyrhynchos platyrhynchos':('Anas platyrhynchos platyrhynchos','subspecies')}[taxon]
  actual_taxon=data.get('taxon') or {}
  if (actual_taxon.get('scientific_name'),actual_taxon.get('rank'))!=expected_taxon:errors.append('wrong_taxon_scope')
  if a['result']['kind']!='graph_query' or data.get('status') not in ('answer','empty','insufficient_data') or not data.get('conditions'):errors.append('not_queried')
  if signature(a)!=signature(b):errors.append('alias_differs_from_original_category')
  if data.get('status')=='answer':
   text=' '.join([data.get('text',''),*data.get('limitations',[])])
   required=('원자료','무척추동물') if alias=='곤충' else ('온혈 척추동물','변온 척추동물','기타 척추동물','물고기·사체 성분은 포함하지 않습니다')
   if any(word not in text for word in required):errors.append('raw_scope_not_explained')
  checks.append({'question':question,'errors':errors})
for q,expected in (
 ('까마귀과 중 곤충을 먹는 새는?','query'),
 ('까마귀과면서 곤충을 먹는 새는 어떤 종이 있어?','query'),
 ('까마귀과 중에서 곤충을 안 먹는 새는?','clarify'),
 ('까마귀과 중에서 곤충을 먹는 빨간 새는?','clarify'),
 ('까마귀과 중에서 곤충을 먹으면서 경쟁하는 새는?','clarify'),
 ('까마귀과 중에서 곡물을 먹는 새는?','guidance'),
 ('까마귀과 중에서 잎을 먹는 새는?','guidance'),
 ('까마귀과 중에서 물고기를 먹는 새는?','query'),
 ('까마귀과 중에서 사체를 먹는 새는?','query'),
 ('까마귀과 중에서 열매를 먹는 새는?','query'),
 ('까마귀과 중에서 씨앗을 먹는 새는?','query'),
 ('숲에 살면서 곤충을 먹는 새는?','query'),
 ('매목 중에서 고기를 먹는 새는?','query'),
 ('매목 중에서 고기를 안 먹는 새는?','clarify'),
 ):
 r=post(q);d=r['result'].get('payload',{});errors=[]
 if expected=='query' and (r['result']['kind']!='graph_query' or d.get('status') not in ('answer','empty','insufficient_data') or not d.get('conditions')):errors.append('supported_query_failed')
 if expected=='clarify' and r['disposition']!='clarify':errors.append('unsupported_condition_ignored')
 if expected=='guidance' and (d.get('status')!='insufficient_data' or d.get('items')):errors.append('food_gap_guard_failed')
 checks.append({'question':q,'expected':expected,'errors':errors})
report={'phase':phase,'base':base,'response_mocking':False,'http_calls':len(rows),'checks':checks,'passed':sum(not x['errors'] for x in checks),'total':len(checks),'rows':rows}
(p/(phase+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('rows','checks')},ensure_ascii=False))
print(json.dumps([x for x in checks if x['errors']],ensure_ascii=False))
if any(x['errors'] for x in checks):sys.exit(1)
