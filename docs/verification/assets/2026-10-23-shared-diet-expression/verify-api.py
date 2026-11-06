"""Read-only public TEST paraphrase equivalence and condition-preservation checks."""
import json,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent;rows=[];checks=[]
cached=json.loads((p/'after.json').read_text())['rows'] if '--recheck' in sys.argv else None
def post(question):
 if cached is not None:
  row=cached.pop(0);assert row['question']==question;rows.append(row);return row['response']
 start=time.perf_counter()
 req=Request('https://robingraph-test.dove-nest.com/v1/chat',data=json.dumps({'question':question,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 RobinGraph-Regression'})
 body=json.load(urlopen(req,timeout=35));rows.append({'question':question,'response':body,'elapsed_ms':round((time.perf_counter()-start)*1000,2)})
 return body
baselines=json.loads((p/'canonical-before.json').read_text())
for old in baselines:
 name=old['question'].split('와 먹이')[0]
 canonical=post(old['question']);qa=canonical['result'].get('question_answer',{})
 checks.append({'question':old['question'],'passed':canonical['disposition']==old['response']['disposition'] and qa==old['response']['result'].get('question_answer',{})})
 for q in (f'{name}랑 같은 먹이 생태를 가진 새를 알려줘',f'{name}와 같은 먹이 범주를 공유하는 새는?',f'{name}와 식성이 같은 새는?'):
  r=post(q);answer=r['result'].get('question_answer',{});groups=(answer.get('relations') or {}).get('groups',[])
  ok=r['result']['kind']=='profile' and r['disposition']==canonical['disposition'] and answer==qa and all(g['relation']=='trophic_niche' for g in groups)
  checks.append({'question':q,'passed':ok})
for q in ('까치랑 같은 먹이를 먹는 새','까치와 먹이 경쟁하는 새','숲에 사는 까치와 먹이가 같은 새는?',
          '숲에서 사는 까치와 같은 먹이 생태를 가진 새','까치와 같은 먹이 생태를 가지지 않은 새',
          '까치와 같은 먹이 생태를 가진 숲에 사는 새'):
 r=post(q);answer=r['result'].get('question_answer',{})
 if q=='숲에 사는 까치와 먹이가 같은 새는?':
  payload=r['result'].get('payload',{})
  ok=r['result']['kind']=='graph_query' and r['disposition']=='abstain' and payload.get('status')=='insufficient_data' and payload.get('taxon',{}).get('scientific_name')=='Pica serica' and '숲' in payload.get('title','')
 else:ok=r['disposition']=='clarify' and answer.get('topic')!='ecological_related'
 checks.append({'question':q,'passed':ok})
for food,count in (('곤충',98),('고기',68)):
 q=f'까마귀과 중에서 {food}{"을" if food=="곤충" else "를"} 먹는 새는?';r=post(q);d=r['result'].get('payload',{})
 checks.append({'question':q,'passed':r['disposition']=='answer' and d.get('coverage',{}).get('matched')==count})
report={'base':'https://robingraph-test.dove-nest.com','response_mocking':False,'http_calls':len(rows),'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'rows':rows}
(p/'after.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('rows','checks')},ensure_ascii=False));print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False));assert all(c['passed'] for c in checks)
