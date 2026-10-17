"""Read-only HTTP checks against an already running TEST application."""
import json,sys,urllib.request,urllib.parse
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'
def request(path,params=None,payload=None):
    url=base+path+('?' +urllib.parse.urlencode(params) if params else '')
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)
rows=[]
for science,scope,expected in [('Anas platyrhynchos','korea','korea'),('Anas platyrhynchos','outside',None),('Nestor notabilis','outside','outside'),('Nestor notabilis','korea',None),('Struthio camelus','unknown','unknown'),('Struthio camelus','outside',None),('Saxicola maurus','korea','korea')]:
    body=request('/v1/chat',payload={'question':science+'에 대해 알려줘','species_scope':scope,'defer_enrichment':True,'defer_discovery':True})
    taxon=(body.get('result',{}).get('profile') or {}).get('taxon',{})
    passed=body.get('disposition')==('answer' if expected else 'abstain')
    if expected:passed=passed and taxon.get('scientific_name')==science and taxon.get('distribution',{}).get('status')==expected
    if science=='Nestor notabilis' and expected:passed=passed and taxon.get('display_name')=='Kea'
    rows.append(dict(request='chat',science=science,species_scope=scope,passed=passed,disposition=body.get('disposition'),display_name=taxon.get('display_name')))
for endpoint in ['related','similar','ecological-related']:
    body=request('/v1/taxa/'+endpoint,{'name':'Anas platyrhynchos','species_scope':'korea'})
    items=[item for group in body.get('groups',[]) for item in group.get('items',[])]
    rows.append(dict(request=endpoint,item_count=len(items),passed=bool(items) and all(item.get('distribution',{}).get('status')=='korea' for item in items)))
body=request('/v1/taxa/profile',{'name':'Nestor notabilis','species_scope':'outside'})
rows.append(dict(request='profile',passed=body.get('taxon',{}).get('display_name')=='Kea'))
body=request('/v1/chat',payload={'question':'청둥오리에 대해 일고 깊어','species_scope':'korea','defer_enrichment':True,'defer_discovery':True})
rows.append(dict(request='jev_typo',passed=body.get('disposition')=='answer' and (body.get('result',{}).get('profile') or {}).get('taxon',{}).get('scientific_name')=='Anas platyrhynchos'))
result=dict(passed=all(r['passed'] for r in rows),scope='Actual running NAS TEST HTTP application and real DB/provider',rows=rows)
print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
