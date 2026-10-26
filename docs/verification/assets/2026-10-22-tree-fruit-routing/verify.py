import json,urllib.request
from pathlib import Path
base='http://127.0.0.1:8000'
def post(q):
 r=urllib.request.Request(base+'/v1/chat',data=json.dumps({'question':q}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=60) as response:
  assert response.status==200
  return json.load(response)
rows=[]
for q,specific in [('참새목 새 중에서 나무열매를 먹는 새는?',False),('참새목 새 중 에서 나무 열매를 먹는 새는?',False),('참새목 새중에서 열매를 먹는 새는?',False),('참새목 중 열매를 먹고 사는 새는?',False),('참새목 새 중에서 감나무 열매를 먹는 새는?',True),('숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?',True)]:
 d=post(q);p=d['result']['payload'];assert d['result']['kind']=='graph_query'
 assert d['disposition']==('abstain' if specific else 'answer'),(q,d['disposition'])
 assert p['status']==('insufficient_data' if specific else 'answer')
 if not specific:assert len(p['items'])>0 and '특정 열매 공유'!=p['title']
 if not specific and '나무' in q:
  assert '나무·풀 구분 없음' in p['title'] and any('나무와 풀' in x for x in p['limitations'])
 rows.append({'question':q,'disposition':d['disposition'],'status':p['status'],'title':p['title'],'item_count':len(p.get('items',[])),'passed':True})
Path(__file__).with_name('actual-api.json').write_text(json.dumps({'base':base,'response_mocking':False,'rows':rows},ensure_ascii=False,indent=2)+'\n');print('Actual TEST API:',len(rows),'passed')
