from pathlib import Path
import runpy,json
nas=runpy.run_path('/tmp/rg701-complete/nas-readonly.py')['nas']
code='''import json,urllib.request
base='http://127.0.0.1:8000'
with urllib.request.urlopen(base+'/health') as r:assert json.load(r)['deployment_target']=='prod'
rows=[]
cases=[('Anas platyrhynchos','korea','answer','Anas platyrhynchos',None),('흰뺨 검둥 오리','korea','answer','Anas zonorhyncha',None),('천둥오리','korea','clarify','Anas platyrhynchos','vector'),('Keaa','outside','clarify','Nestor notabilis','vector')]
for mention,scope,expected,science,method in cases:
 payload={'filters':{'kind':'profile','name':mention},'question':mention,'intent':'profile','species_scope':scope,'defer_enrichment':True,'defer_discovery':True}
 request=urllib.request.Request(base+'/v1/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=180) as response:
  assert response.status==200;result=json.load(response)
 assert result['disposition']==expected,(mention,result['disposition'])
 resolution=result.get('entity_resolution') or {}
 assert science in json.dumps(result),(mention,science)
 if method:assert resolution.get('method')==method,(mention,resolution)
 rows.append({'query':mention,'scope':scope,'disposition':result['disposition'],'method':resolution.get('method'),'expected_scientific_name':science,'passed':True})
payload={'question':'흰뺨 검둥 오리','intent':'profile','species_scope':'korea','defer_enrichment':True,'defer_discovery':True}
request=urllib.request.Request(base+'/v1/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=180) as response:bare=json.load(response)
assert bare['disposition']=='clarify' and bare.get('entity_resolution') is None
print(json.dumps({'target':'prod','response_mocking':False,'cases':rows,'passed':True,'additional_contract_observation':{'question':'흰뺨 검둥 오리','without_explicit_name_filter':'clarify_before_name_resolution','explicit_name_filter':'answer','initial_verification_expectation_corrected':True}}))
'''
outer="""import json,subprocess
c=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=prod' in c['Config']['Env']
print(subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=CODE,text=True))
""".replace('CODE',repr(code))
result=json.loads(nas(outer))
Path('docs/verification/assets/2026-10-21-name-vector-promotion/live-api.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('Actual Production API regression passed:',len(result['cases']))
