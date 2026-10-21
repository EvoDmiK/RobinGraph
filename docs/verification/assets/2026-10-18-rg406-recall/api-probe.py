import json,urllib.request,os
base=os.getenv('RG406_BASE','http://127.0.0.1:8000')
results=[]
for q,scope in [('높은산앵무아','outside'),('청둥오리아','korea'),('타조아','unknown'),('천둥오리','korea'),('청둥오리아','outside')]:
 request=urllib.request.Request(base+'/v1/chat',data=json.dumps({'question':q+'에 대해 알려줘','intent':'profile','species_scope':scope}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=180) as response:d=json.load(response)
 results.append({'query':q,'scope':scope,'disposition':d['disposition'],'resolution':d.get('resolution') or d.get('entity_resolution'),'result':d.get('result')})
print(json.dumps(results,ensure_ascii=False,indent=2))
