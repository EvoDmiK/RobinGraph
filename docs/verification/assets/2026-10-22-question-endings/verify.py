import json,urllib.request
from pathlib import Path
base='http://127.0.0.1:8000'
endings=['?', ' 어떤게 있어?', ' 어떤 게 있어?', ' 어떤 것이 있나요?', ' 어떤 것들이 있어요?', ' 뭐가 있어?', ' 어떤 종이 있을까?', ' 어떤 새들이 있습니까?', ' 알려줘', ' 알려 주세요', ' 보여줘', ' 알고 싶어요']
cases=[('참새목 새 중에서 '+food+'를 먹는 새는'+tail,False,food.startswith('나무')) for food in ['열매','나무 열매'] for tail in endings]
cases += [('참새목 새 중에서 감나무 열매를 먹는 새는 어떤게 있어?',True,False),('숲에 사는 새 중 직박구리랑 같은 열매를 먹는 새는 어떤 게 있어?',True,False),('참새목 새중에서 열매를 먹는 새는?',False,False),('참새목 새 중에서 나무열매를 먹는 새는?',False,True)]
rows=[]
for q,specific,tree in cases:
 req=urllib.request.Request(base+'/v1/chat',data=json.dumps({'question':q}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as response:
  assert response.status==200;d=json.load(response)
 assert d['result']['kind']=='graph_query',(q,d)
 assert d['disposition']==('abstain' if specific else 'answer'),(q,d['disposition'])
 p=d['result']['payload']
 if not specific:assert len(p['items'])>0
 if tree:assert '나무·풀 구분 없음' in p['title']
 rows.append({'question':q,'disposition':d['disposition'],'kind':d['result']['kind'],'status':p['status'],'title':p['title'],'item_count':len(p.get('items',[])),'passed':True})
Path(__file__).with_name('actual-api.json').write_text(json.dumps({'base':base,'mocked':False,'rows':rows},ensure_ascii=False,indent=2)+'\n');print('Actual TEST API:',len(rows),'passed')
