"""One-time explicit TEST->Production name-vector operator. No target spoofing."""
if not __debug__:raise SystemExit("Optimized execution is forbidden")
from pathlib import Path
import argparse,hashlib,json,os,runpy,subprocess,uuid
ROOT=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
ASSETS=ROOT/'docs/verification/assets/2026-10-21-name-vector-promotion'
PRIVATE=Path('/Users/kimdove/robingraph-test/backups')/('name-vector-promotion-20261021-'+uuid.uuid4().hex[:8])
COMMON=Path('/tmp/rg-name-promotion/common.py').read_text()
nas=runpy.run_path('/tmp/rg701-complete/nas-readonly.py')['nas']
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
def private(name,value):
 path=PRIVATE/name
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False)
 return path

def test(code):
 return json.loads(subprocess.check_output(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-'],input=COMMON+'\n'+code,text=True))
def production(code):
 wrapped="""if not __debug__:raise SystemExit("Optimized remote execution is forbidden")
import json,subprocess
c=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=prod' in c['Config']['Env']
values=dict(item.split('=',1) for item in c['Config']['Env'])
from pathlib import Path
env_path=Path(c['Config']['Labels']['com.docker.compose.project.working_dir'])/'.env.nas.prod'
import os
render_env=dict(os.environ,ROBINGRAPH_ENV_FILE=str(env_path),ROBINGRAPH_DEPLOY_TARGET='prod')
configured=json.loads(subprocess.check_output(['docker','compose','--env-file',str(env_path),'-f',str(env_path.parent/'compose.nas.yml'),'config','--format','json'],env=render_env,stderr=subprocess.PIPE))['services']['api']['environment']
for name in ('NEO4J_URI','NEO4J_DATABASE','ROBINGRAPH_PG_HOST','ROBINGRAPH_PG_PORT','ROBINGRAPH_PG_DATABASE','ROBINGRAPH_PG_USERNAME'):
 default={'NEO4J_DATABASE':'neo4j','ROBINGRAPH_PG_PORT':'5432'}.get(name)
 assert values.get(name,default)==configured.get(name,default), 'Container and persisted Production config differ: '+name
print(subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=CODE,text=True))
""".replace('CODE',repr(COMMON+'\n'+code))
 return json.loads(nas(wrapped))

def plan():
 ASSETS.mkdir(parents=True,exist_ok=True);PRIVATE.mkdir(parents=True,mode=0o700,exist_ok=False)
 source=test("s=snapshot('test');validate_source(s);print(json.dumps(s))")
 private('test-export.json',source)
 target=production("print(json.dumps(snapshot('prod')))")
 private('production-before.json',target)
 verification=production('source='+repr(source)+"\ntarget=snapshot('prod')\nassert digest(target)=="+repr(digest(target))+"\nvalidate_source(source)\nreport=validate_destination(source,target)\nprobe=probe_model(source)\nprint(json.dumps({'plan':report,'model_probe':probe}))")
 receipt={'operator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'validation_sha256':hashlib.sha256(COMMON.encode()).hexdigest(),'operation':'TEST reviewed name vectors -> Production','target':'prod','source_count':len(source['inventory']),'profile':source['profile'],'context':source['context'],'fingerprint':source['fingerprint'],'source_sha256':digest(source),'destination_before_sha256':digest(target),'private_backup':str(PRIVATE),'compatibility':verification,'production_written':False,'destination_identity_sha256':digest(target['connection_identity']),'source_endpoint_equals_destination':source['endpoint_sha256']==target['endpoint_sha256'],'source_taxon_count':source['taxon_count'],'destination_taxon_count':target['taxon_count']}
 (ASSETS/'plan.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

def apply():
 receipt=json.loads((ASSETS/'plan.json').read_text())
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==receipt['operator_sha256'] and hashlib.sha256(COMMON.encode()).hexdigest()==receipt['validation_sha256'], 'Operator changed after reviewed preflight'
 source=json.loads((Path(receipt['private_backup'])/'test-export.json').read_text())
 before=json.loads((Path(receipt['private_backup'])/'production-before.json').read_text())
 identity=before['connection_identity'];assert digest(identity)==receipt['destination_identity_sha256']
 assert digest(source)==receipt['source_sha256']
 current_source=test("print(json.dumps(snapshot('test')))")
 assert digest(current_source)==receipt['source_sha256'], 'TEST source changed since review'
 operation=Path(receipt['private_backup']).name
 payload=COMMON+'\nPINNED_PRODUCTION_IDENTITY='+repr(identity)+'\nsource='+repr(source)+'\nresult=apply_source(source,'+repr(receipt['destination_before_sha256'])+')\nprint(json.dumps(result))'
 backup_code=COMMON+"\nprint(json.dumps(snapshot('prod')))"
 wrapped="""if not __debug__:raise SystemExit("Optimized remote execution is forbidden")
import json,subprocess,os,hashlib
from pathlib import Path
c=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=prod' in c['Config']['Env']
values=dict(item.split('=',1) for item in c['Config']['Env'])
from pathlib import Path
env_path=Path(c['Config']['Labels']['com.docker.compose.project.working_dir'])/'.env.nas.prod'
import os
render_env=dict(os.environ,ROBINGRAPH_ENV_FILE=str(env_path),ROBINGRAPH_DEPLOY_TARGET='prod')
configured=json.loads(subprocess.check_output(['docker','compose','--env-file',str(env_path),'-f',str(env_path.parent/'compose.nas.yml'),'config','--format','json'],env=render_env,stderr=subprocess.PIPE))['services']['api']['environment']
for name in ('NEO4J_URI','NEO4J_DATABASE','ROBINGRAPH_PG_HOST','ROBINGRAPH_PG_PORT','ROBINGRAPH_PG_DATABASE','ROBINGRAPH_PG_USERNAME'):
 default={'NEO4J_DATABASE':'neo4j','ROBINGRAPH_PG_PORT':'5432'}.get(name)
 assert values.get(name,default)==configured.get(name,default), 'Container and persisted Production config differ: '+name
base=Path(c['Config']['Labels']['com.docker.compose.project.working_dir'])/'.name-vector-promotions'
base.mkdir(mode=0o700,exist_ok=True);base.chmod(0o700)
lock=base/'promotion.lock';fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(OPERATION)
try:
 folder=base/OPERATION;folder.mkdir(mode=0o700,exist_ok=False)
 before=subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=BACKUP_CODE,text=True)
 value=json.loads(before)
 assert hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()==EXPECTED
 with os.fdopen(os.open(folder/'production-before.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(before)
 result=json.loads(subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=PAYLOAD,text=True))
 result['nas_backup_directory']=str(folder)
 with os.fdopen(os.open(folder/'receipt.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(result,f)
 print(json.dumps(result))
finally:
 if lock.read_text()==OPERATION:lock.unlink()
"""
 for key,value in [('OPERATION',operation),('BACKUP_CODE',backup_code),('EXPECTED',receipt['destination_before_sha256']),('PAYLOAD',payload)]:
  wrapped=wrapped.replace(key,repr(value))
 result=json.loads(nas(wrapped))
 (ASSETS/'apply.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))

if __name__=='__main__':
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--plan',action='store_true');group.add_argument('--apply',action='store_true');args=parser.parse_args()
 plan() if args.plan else apply()
