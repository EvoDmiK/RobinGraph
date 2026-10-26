"""Read-only actual TEST API evaluation; preserves full response evidence."""
import json,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
p=Path(__file__).resolve().parent
phase=sys.argv[1]
cases=json.loads((p/'final-independent-cases.json').read_text())['cases']
if phase=='shadow':cases=[c for c in cases if c['category']=='preserve']
assert json.load(urlopen('http://127.0.0.1:8000/health'))['deployment_target']=='test'
def run(c):
 start=time.perf_counter()
 try:
  req=Request('http://127.0.0.1:8000/v1/chat',data=json.dumps({'question':c['question'],'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'})
  with urlopen(req,timeout=90) as r:body=json.load(r)
  return {'case':c,'response':body,'elapsed_ms':round((time.perf_counter()-start)*1000)}
 except Exception as e:return {'case':c,'error':type(e).__name__+': '+str(e)[:200]}
rows=[]
with ThreadPoolExecutor(max_workers=2) as pool:
 for row in pool.map(run,cases):rows.append(row)
(p/('api-'+phase+'.json')).write_text(json.dumps({'phase':phase,'response_mocking':False,'bird_db_writes':0,'rows':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'phase':phase,'count':len(rows),'rows':[{'id':r['case']['id'],'disposition':r.get('response',{}).get('disposition'),'kind':r.get('response',{}).get('result',{}).get('kind'),'error':r.get('error')} for r in rows]},ensure_ascii=False))
