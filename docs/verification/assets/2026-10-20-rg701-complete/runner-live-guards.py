import subprocess,json
from pathlib import Path
source='''import json,os,urllib.request,urllib.error
base='http://127.0.0.1:18001'
def call(path,body=None,auth=False,host=None):
 headers={}
 if body is not None:headers['Content-Type']='application/json'
 if auth:headers['Authorization']='Bearer '+os.environ['ROBINGRAPH_AVILIST_PIPELINE_TOKEN']
 if host:headers['Host']=host
 request=urllib.request.Request(base+path,data=body,headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=20) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
rows=[]
for name,path,body,auth,host,expected in [
 ('unauthenticated_stage','/verify',b'{}',False,None,401),
 ('authenticated_body_limit','/verify',b' '*65,True,None,413),
 ('public_api_isolated','/v1/search',None,False,None,404),
 ('host_guard','/health',None,False,'untrusted.invalid',400)]:
 status,result=call(path,body,auth,host)
 assert status==expected,(name,status)
 rows.append({'case':name,'status':status,'passed':True})
print(json.dumps({'target':'test','mocked':False,'passed':True,'cases':rows}))
'''
r=subprocess.check_output(['docker','--context','orbstack','exec','-i','robingraph-avilist-runner-test','python','-'],input=source,text=True)
result=json.loads(r)
Path('docs/verification/assets/2026-10-20-rg701-complete/runner-live-guards.json').write_text(json.dumps(result,indent=2)+'\n')
print('Actual runner auth/body/isolation/host guards passed:',len(result['cases']))
