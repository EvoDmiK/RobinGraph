"""Actual TEST API scope preservation for a new two-condition taxonomy query."""
from pathlib import Path
from urllib.request import Request,urlopen
import json
p=Path(__file__).resolve().parent;rows=[]
for scope in ('all','korea','outside','unknown'):
 req=Request('http://127.0.0.1:8000/v1/chat',data=json.dumps({'question':'까마귀과 중 숲에 살고 열매를 먹는 새는?','species_scope':scope,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'});d=json.load(urlopen(req,timeout=35));out=d['result'].get('payload',{});assert out.get('status') in ('answer','empty','insufficient_data')
 assert out.get('taxon',{}).get('scientific_name')=='Corvidae' and len(out.get('conditions',[]))==2
 if scope!='all':assert all(x['taxon']['distribution']['status']==scope for x in out.get('items',[]))
 if scope=='outside':assert all(x['taxon']['display_name']==(x['taxon'].get('english_name') or x['taxon'].get('korean_name') or x['taxon']['scientific_name']) for x in out.get('items',[]))
 rows.append({'scope':scope,'response':d})
(p/'scope-api.json').write_text(json.dumps({'response_mocking':False,'count':4,'passed':4,'rows':rows},ensure_ascii=False,indent=2)+'\n');print('4 scope requests passed')
