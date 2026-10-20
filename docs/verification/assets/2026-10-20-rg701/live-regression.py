import json,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
base='http://127.0.0.1:8000'
def req(path,body=None):
 r=Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urlopen(r,timeout=90) as response:
  assert response.status==200
  return json.load(response)
assert req('/health')['deployment_target']=='test'
rows=[]
for mention,science,scope,disposition in [('Kea','Nestor notabilis','outside','answer'),('Kea','Nestor notabilis','all','answer'),('Keaa','Nestor notabilis','outside','clarify'),('Anas platyrhynchos','Anas platyrhynchos','korea','answer')]:
 result=req('/v1/chat',{'question':mention,'intent':'profile','species_scope':scope,'defer_enrichment':True,'defer_discovery':True})
 assert result['disposition']==disposition,(mention,result['disposition'])
 assert science in json.dumps(result),(mention,science)
 rows.append({'mention':mention,'scope':scope,'expected_disposition':disposition,'scientific_name':science,'passed':True})
lineage=req('/v1/taxa/lineage?'+urlencode({'scientific_name':'Anas platyrhynchos'}))
assert lineage.get('lineage')
rows.append({'endpoint':'lineage','passed':True})
Path(sys.argv[1]).write_text(json.dumps({'target':'test','base':base,'passed':True,'rows':rows},indent=2)+'\n')
print('Live TEST API regression passed:',len(rows))
