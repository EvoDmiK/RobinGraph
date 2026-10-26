"""Actual TEST read-only clarification requests; candidate clicks are explicit test selections."""
import json,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent
assert json.load(urlopen('http://127.0.0.1:8000/health'))['deployment_target']=='test'
cases=json.loads((p/'independent-cases.json').read_text())['cases']
def post(question,scope='all',intent='auto'):
 start=time.perf_counter()
 request=Request('http://127.0.0.1:8000/v1/chat',data=json.dumps({'question':question,'intent':intent,
  'species_scope':scope,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'})
 with urlopen(request,timeout=90) as response:body=json.load(response)
 return {'question':question,'species_scope':scope,'intent':intent,'elapsed_ms':round((time.perf_counter()-start)*1000),'response':body}
def confirm(row,scope):
 candidates=(row['response'].get('entity_resolution') or {}).get('candidates',[])
 candidate=next((c for c in candidates if c['scientific_name']=='Anas platyrhynchos'),None)
 return post(candidate['question'],scope,candidate.get('route_intent','profile')) if candidate else None

def run(case):
 scope=case.get('scope','all');first=post(case['question'],scope);branches=[]
 choices=first['response'].get('result',{}).get('choices',[])
 if choices:
  for choice in choices:
   selected=post(choice['question'],scope);confirmed=confirm(selected,scope)
   branches.append({'choice':choice,'selected':selected,'name_confirmed':confirmed})
 else:
  confirmed=confirm(first,scope)
  if confirmed:branches.append({'name_confirmed':confirmed})
 return {'case':case,'first':first,'branches':branches}
rows=[]
with ThreadPoolExecutor(max_workers=2) as pool:
 for row in pool.map(run,cases):rows.append(row)
result={'response_mocking':False,'bird_db_writes':0,'count':len(rows),'rows':rows}
(p/'api-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(rows),'initial':[{ 'id':r['case']['id'],'disposition':r['first']['response']['disposition'],
'choices':len(r['first']['response'].get('result',{}).get('choices',[])),'name_candidates':len((r['first']['response'].get('entity_resolution') or {}).get('candidates',[]))} for r in rows]},ensure_ascii=False))
