"""Read-only candidate checks on NAS; keep the live app and domain data unchanged."""
import base64,json,os,re,subprocess,tempfile,time
from pathlib import Path
image=os.environ['CANDIDATE_IMAGE']; revision=os.environ['CANDIDATE_REVISION']
assert re.fullmatch(r'ghcr.io/evodmik/robingraph@sha256:[a-f0-9]{64}',image)
assert re.fullmatch(r'[a-f0-9]{40}',revision)
def inspect(name): return json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
old=inspect('robingraph-api');env=dict(x.split('=',1) for x in old['Config']['Env']);assert env['ROBINGRAPH_DEPLOY_TARGET']=='prod'
name='robingraph-completed-preflight-'+os.environ['BUILD_NUMBER']
with tempfile.TemporaryDirectory(prefix='rg-preflight-') as temporary:
 root=Path(temporary); auth=root/'auth';auth.mkdir(mode=0o700); docker_env=dict(os.environ,DOCKER_CONFIG=str(auth),DOCKER_CONTEXT='default',DOCKER_HOST='unix:///var/run/docker.sock')
 subprocess.run(['docker','login','ghcr.io','--username',os.environ['GHCR_USERNAME'],'--password-stdin'],input=os.environ['GHCR_TOKEN'],text=True,capture_output=True,check=True,env=docker_env)
 subprocess.run(['docker','pull','--platform','linux/amd64',image],check=True,stdout=subprocess.DEVNULL,env=docker_env)
 img=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True))[0]
 assert img['Architecture']=='amd64' and img['Config']['Labels']['org.opencontainers.image.revision']==revision
 env.update(ROBINGRAPH_GRAPH_INTENT_MODE='active',ROBINGRAPH_GRAPH_INTERPRETER='lexical')
 assert all('\n' not in v for v in env.values())
 private=root/'candidate.env';private.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n');private.chmod(0o600)
 networks=list(old['NetworkSettings']['Networks']);assert networks
 try:
  subprocess.run(['docker','create','--name',name,'--network',networks[0],'--env-file',str(private),'--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges',image,*old['Config']['Cmd']],check=True,stdout=subprocess.DEVNULL)
  for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
  subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
  for attempt in range(45):
   check=subprocess.run(['docker','exec',name,'python','-c',"import urllib.request,json;d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'));assert d['status']=='ok' and d['deployment_target']=='prod'"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   if check.returncode==0:break
   time.sleep(2)
  else:raise RuntimeError('Candidate readiness failed')
  subprocess.run(['docker','exec','-i',name,'python','-c',"import sys;from pathlib import Path;Path('/tmp/evaluate.py').write_bytes(sys.stdin.buffer.read())"],input=Path('release-evaluate.py').read_bytes(),check=True)
  subprocess.run(['docker','exec','-i',name,'python','-c',"import sys;from pathlib import Path;Path('/tmp/cases.json').write_bytes(sys.stdin.buffer.read())"],input=Path('release-cases.json').read_bytes(),check=True)
  result=subprocess.run(['docker','exec',name,'python','/tmp/evaluate.py','--base','http://127.0.0.1:8000','--cases','/tmp/cases.json','--out','/tmp/candidate.json','--target','prod'])
  Path('production-candidate.json').write_bytes(subprocess.check_output(['docker','exec',name,'cat','/tmp/candidate.json']))
  current=inspect('robingraph-api');assert current['Id']==old['Id'] and current['State']['StartedAt']==old['State']['StartedAt']
  Path('candidate-summary.json').write_text(json.dumps({'image':image,'revision':revision,'live_container_unchanged':True,'runtime':{'graph_intent_mode':'active','graph_interpreter':'lexical'},'evaluation_exit':result.returncode,'published_ports':False,'db_change_commands':False},indent=2)+'\n')
  if result.returncode:raise RuntimeError('Candidate regression failures; inspect archived results')
 finally:
  subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
