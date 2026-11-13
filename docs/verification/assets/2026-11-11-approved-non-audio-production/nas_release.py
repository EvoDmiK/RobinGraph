"""Approved non-audio snapshot: read-only candidate preflight, then guarded app-only promotion."""
import json,os,subprocess,tempfile,time,sys,hashlib,importlib.util
from pathlib import Path
IMAGE=os.environ['IMMUTABLE_IMAGE'];SOURCE=os.environ['RELEASE_SOURCE_SHA'];BASE=os.environ['RELEASE_BASE_REVISION']
def inspect(name,image=False):return json.loads(subprocess.check_output(['docker',*(['image','inspect'] if image else ['inspect']),name]))[0]
old=inspect('robingraph-api');env=dict(x.split('=',1) for x in old['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='prod'
assert old['Id']=='4ac6fc9a208fb7318a8fb1f0208a936931ef10456a938e220d859dba76f518ab','Production changed since approved preflight'
assert old['Config']['Image']=='ghcr.io/evodmik/robingraph@sha256:963b4836ccf77155a8ca94efa105e66c60f799d05e75f6ae6c5b6ce710b05edc'
root=Path(old['Config']['Labels']['com.docker.compose.project.working_dir'])
# Registry credentials stay inside Jenkins binding and an ephemeral Docker config.
with tempfile.TemporaryDirectory(prefix='rg-approved-registry-') as tmp:
 auth=Path(tmp)/'auth';auth.mkdir(mode=0o700)
 denv=dict(os.environ,DOCKER_CONFIG=str(auth),DOCKER_CONTEXT='default',DOCKER_HOST='unix:///var/run/docker.sock')
 subprocess.run(['docker','login','ghcr.io','--username',os.environ['GHCR_USERNAME'],'--password-stdin'],input=os.environ['GHCR_TOKEN'],text=True,capture_output=True,check=True,env=denv)
 subprocess.run(['docker','pull','--platform','linux/amd64',IMAGE],env=denv,check=True,stdout=subprocess.DEVNULL)
 img=inspect(IMAGE,True);labels=img['Config'].get('Labels',{})
 assert img['Architecture']=='amd64' and labels['org.opencontainers.image.revision']==BASE
 assert labels['org.robingraph.source.sha256']==SOURCE
if os.environ['RELEASE_ACTION']=='preflight':
 name='robingraph-approved-no-audio-'+os.environ['BUILD_NUMBER']
 with tempfile.TemporaryDirectory(prefix='rg-approved-candidate-') as tmp:
  settings=Path(tmp)/'candidate.env';settings.touch(mode=0o600)
  candidate_env=dict(env,ROBINGRAPH_MLFLOW_TRACING='false')
  assert all('\n' not in v for v in candidate_env.values())
  settings.write_text('\n'.join(k+'='+v for k,v in candidate_env.items())+'\n')
  networks=list(old['NetworkSettings']['Networks']);assert networks
  try:
   subprocess.run(['docker','create','--name',name,'--network',networks[0],'--env-file',str(settings),'--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges',IMAGE,*old['Config']['Cmd']],check=True,stdout=subprocess.DEVNULL)
   for n in networks[1:]:subprocess.run(['docker','network','connect',n,name],check=True)
   subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
   for _ in range(60):
    r=subprocess.run(['docker','exec',name,'python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if r.returncode==0:break
    time.sleep(2)
   else:raise RuntimeError('Production-data candidate startup failed')
   result=subprocess.check_output(['docker','exec','-i',name,'python','-'],input=Path('verify_release.py').read_bytes())
   Path('production-candidate.json').write_bytes(result)
   assert inspect('robingraph-api')['Id']==old['Id']
  finally:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 print('Production-data candidate passed; live app unchanged.')
 sys.exit(0)
assert os.environ['RELEASE_ACTION']=='deploy'
preflight=json.loads(Path('production-candidate.json').read_text());assert preflight['passed'] and preflight['source_sha256']==SOURCE
spec=importlib.util.spec_from_file_location('deploy_helper','deploy_registry_prod.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
previous,context_root,env_path,original_env,values=helper.production_context();assert context_root==root
compose=root/'compose.nas.yml';original_compose=compose.read_bytes()
assert b'robingraph-prod-species-cache' not in original_compose
record_dir=root/'.registry-deployments';record_dir.mkdir(mode=0o700,exist_ok=True);record_dir.chmod(0o700)
backup=record_dir/('non-audio-'+SOURCE[:12]+'-'+str(time.time_ns()));backup.mkdir(mode=0o700)
for name,data in [('compose.previous',original_compose),('env.previous',original_env)]:
 fd=os.open(backup/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as h:h.write(data)
volume='robingraph-prod-species-cache'
known=subprocess.check_output(['docker','volume','ls','--format','{{.Name}}'],text=True).splitlines()
if volume not in known:subprocess.run(['docker','volume','create','--label','org.robingraph.target=prod',volume],check=True,stdout=subprocess.DEVNULL)
v=json.loads(subprocess.check_output(['docker','volume','inspect',volume]))[0]
assert v.get('Labels',{}).get('org.robingraph.target')=='prod'
subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','0:0','--mount','type=volume,source='+volume+',target=/cache','--entrypoint','sh',IMAGE,'-c','chown 10001:10001 /cache && chmod 700 /cache'],check=True)
text=original_compose.decode();assert text.count('  api:\n')==1 and text.count('\nvolumes:\n')==1
text=text.replace('  api:\n','  api:\n    volumes:\n      - type: volume\n        source: approved-species-cache\n        target: /var/lib/robingraph/species-cache\n',1)
text=text.replace('\nvolumes:\n','\nvolumes:\n  approved-species-cache:\n    external: true\n    name: '+volume+'\n',1)
assert 'ROBINGRAPH_SPECIES_CACHE_ROOT' not in values
compose_env=dict(os.environ,ROBINGRAPH_DEPLOY_TARGET='prod',ROBINGRAPH_COMPOSE_PROJECT=old['Config']['Labels']['com.docker.compose.project'],ROBINGRAPH_API_CONTAINER='robingraph-api',ROBINGRAPH_ENV_FILE=str(env_path),ROBINGRAPH_API_MODE=values['ROBINGRAPH_API_MODE'],ROBINGRAPH_EDGE_NETWORK=values.get('ROBINGRAPH_EDGE_NETWORK','robingraph-edge'))
receipt={'source_sha256':SOURCE,'base_revision':BASE,'image':IMAGE,'audio_excluded':True,'cache_volume':volume,'backup':str(backup),'previous_id':old['Id'],'previous_image':old['Config']['Image'],'state':'prepared','domain_db_writes':False}
def save():
 (backup/'release.json').write_text(json.dumps(receipt,indent=2)+'\n');Path('production-release.json').write_text(json.dumps(receipt,indent=2)+'\n')
def check_live():
 result=subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=Path('verify_release.py').read_bytes());Path('production-live.json').write_bytes(result)
 p=inspect('robingraph-api');assert p['Config']['Image']==IMAGE
 settings=dict(x.split('=',1) for x in p['Config']['Env']);assert settings['ROBINGRAPH_SPECIES_CACHE_ROOT']=='/var/lib/robingraph/species-cache'
 for k in ['NEO4J_URI','ROBINGRAPH_PG_HOST','ROBINGRAPH_PG_DATABASE','ROBINGRAPH_GRAPH_INTENT_MODE','ROBINGRAPH_GRAPH_INTERPRETER','MLFLOW_EXPERIMENT_ID','MLFLOW_EXPERIMENT_NAME','ROBINGRAPH_DJANGO_SECRET_KEY']:
  assert settings.get(k)==env.get(k),'Runtime value changed: '+k
 assert any(m.get('Name')==volume and m['Destination']=='/var/lib/robingraph/species-cache' for m in p['Mounts'])
 subprocess.run(['docker','exec','robingraph-api','python','-c',"from pathlib import Path;p=Path('/var/lib/robingraph/species-cache/.write-check');p.write_text('ok');assert p.read_text()=='ok';p.unlink()"],check=True)
 return p
save()
try:
 compose.write_text(text);env_path.write_bytes(original_env.rstrip()+b'\nROBINGRAPH_SPECIES_CACHE_ROOT=/var/lib/robingraph/species-cache\n');env_path.chmod(0o600)
 model=json.loads(subprocess.check_output(['docker','compose','--env-file',str(env_path),'-f',str(compose),'config','--format','json'],env=compose_env))
 api=model['services']['api'];assert api['container_name']=='robingraph-api';assert len(api.get('volumes',[]))==1
 assert api['volumes'][0]['target']=='/var/lib/robingraph/species-cache'
 helper.remote_deploy({'image':IMAGE,'revision':BASE,'registry_user':os.environ['GHCR_USERNAME'],'registry_token':os.environ['GHCR_TOKEN']})
 live=check_live();receipt.update(state='verified',container_id=live['Id'],started_at=live['State']['StartedAt'],health=live['State']['Health']['Status'],runtime_preserved=True,cache_write_verified=True);save()
except Exception:
 compose.write_bytes(original_compose);env_path.write_bytes(original_env);env_path.chmod(0o600)
 receipt['state']='rollback_started';save()
 rollback_env=dict(compose_env,ROBINGRAPH_IMAGE=old['Config']['Image'])
 subprocess.run(['docker','compose','--env-file',str(env_path),'-f',str(compose),'up','-d','--no-build','--no-deps','api'],env=rollback_env,check=True)
 for _ in range(60):
  p=inspect('robingraph-api')
  if p['State'].get('Health',{}).get('Status')=='healthy':break
  time.sleep(2)
 else:raise RuntimeError('Rollback health failed')
 assert p['Config']['Image']==old['Config']['Image'];receipt['state']='rolled_back';save();raise
print(json.dumps(receipt))
