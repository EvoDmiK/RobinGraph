import json,os,urllib.request
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
base='http://127.0.0.1:8000'
def request(path,body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as response:return json.load(response)
assert request('/health')['deployment_target']=='test'
questions=[
 '청둥오리와 흰뺨검둥오리는 어떤 관계야?',
 '청둥오리와 같은 속에 속하는 새를 보여줘',
 '한국에 기록된 오리 중 청둥오리와 같은 속인 종은?',
 '참새목 중 열매를 먹고 사는 새는?',
 '숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?',
 '청둥오리와 서식지가 겹치면서 먹이가 다른 새는?',
 '숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?',
]
rows=[]
for question in questions:
 body=request('/v1/chat',{'question':question,'defer_enrichment':True,'defer_discovery':True})
 assert body['result']['kind']=='graph_query', (question,body)
 payload=body['result']['payload']
 if '같은 열매' in question:
  assert body['disposition']=='abstain' and payload['status']=='insufficient_data' and not payload['items']
 else:
  assert body['disposition']=='answer' and payload['status']=='answer' and 0<len(payload['items'])<=20, (question,body)
  assert all(item['paths'] and all(path.get('source_url','').startswith(('http://','https://')) for path in item['paths']) for item in payload['items'])
 rows.append({'question':question,'response':body})
print(json.dumps({'target':'test','read_only_retrieval':True,'rows':rows},ensure_ascii=False,indent=2))
