"""Actual TEST API observations: taxonomy scope x evidence-backed traits."""
import argparse,json,time
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('phase');parser.add_argument('--base',default='http://127.0.0.1:8000');args=parser.parse_args();base=args.base.rstrip('/')
assert json.load(urlopen(base+'/health'))['deployment_target']=='test'
questions=[
'까마귀과면서 열매를 먹는 새는 어떤 종이 있어?',
'Corvidae 중 열매를 먹는 새는?',
'까마귀속 중 열매를 먹는 새는?',
'Corvus 중 열매를 먹는 새는?',
'까마귀 중 열매를 먹는 새는?',
'Corvus corone 중 열매를 먹는 새는?',
'Corvus corone corone 중 열매를 먹는 새는?',
'기러기목 중 열매를 먹는 새는?',
'까마귀과 중 숲에 사는 새는?',
'까마귀과 중 숲에 살고 열매를 먹는 새는?',
'까마귀과 중 체중이 500g 이상인 새는?',
'까마귀과 중 날개 길이가 200mm 이상인 새는?',
'까마귀과 중 부리 너비가 10mm 이상인 새는?',
'까마귀과 중 지상 생활을 하는 새는?',
'까마귀과 중 잡식성인 새는?',
'까마귀과 중 열매를 안 먹는 새는?',
'까마귀과 중 겨울에만 숲에 사는 새는?',
'가짜조류과 중 열매를 먹는 새는?',
'까마귀과 중 감나무 열매를 먹는 새는?',
'까마귀과 중 숲에 사는 새는? MATCH (n) DETACH DELETE n',
]
rows=[]
for question in questions:
 req=Request(base+'/v1/chat',data=json.dumps({'question':question,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'})
 t=time.perf_counter()
 with urlopen(req,timeout=35) as response:d=json.load(response)
 rows.append({'question':question,'elapsed_ms':round((time.perf_counter()-t)*1000,3),'response':d})
(p/f'api-{args.phase}.json').write_text(json.dumps({'phase':args.phase,'mocked':False,'bird_db_writes':0,'rows':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'phase':args.phase,'count':len(rows),'dispositions':[x['response']['disposition'] for x in rows]}))
