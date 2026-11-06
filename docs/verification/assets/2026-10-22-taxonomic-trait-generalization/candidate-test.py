"""Build and launch an isolated, loopback-only TEST candidate; public TEST unchanged."""
from pathlib import Path
import subprocess,json,time,hashlib
from urllib.request import urlopen
p=Path(__file__).resolve().parent;root=p.parents[3];docker=['docker','--context','orbstack'];name='robingraph-taxonomic-candidate'
files=sorted(f for f in (root/'src').rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc' and not any(x.endswith('.egg-info') for x in f.parts))
hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();tag='robingraph-api:test-taxonomic-candidate-'+digest[:12]
with (p/'candidate-build.log').open('w') as log:
 subprocess.run(docker+['build','--platform','linux/arm64','-t',tag,'.'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in hashes.items()),'Source changed during build; retry stable snapshot'
# This exact named disposable QA container is owned by this script.
subprocess.run(docker+['rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(docker+['run','-d','--name',name,'--read-only','--tmpfs','/tmp','--cpus','2','--memory','1g','--env-file','/Users/kimdove/robingraph-test/current/.env.nas.test','-e','ROBINGRAPH_DEPLOY_TARGET=test','-e','ROBINGRAPH_GRAPH_INTENT_MODE=active','-e','ROBINGRAPH_MLFLOW_TRACING=false','-p','127.0.0.1::8000',tag,'robingraph','serve-neo4j','--host','0.0.0.0','--port','8000'],check=True,stdout=subprocess.DEVNULL)
state=json.loads(subprocess.check_output(docker+['inspect',name],text=True))[0];port=state['NetworkSettings']['Ports']['8000/tcp'][0]['HostPort'];base='http://127.0.0.1:'+port
for _ in range(40):
 try:
  health=json.load(urlopen(base+'/health',timeout=2))
  if health['deployment_target']=='test' and health['mode']=='neo4j':break
 except Exception:pass
 time.sleep(.5)
else:raise RuntimeError('Candidate health failed')
report={'image':tag,'source_sha256':digest,'file_sha256':hashes,'base':base,'container':name,'public_test_unchanged':True,'production_changed':False,'mode':'active','tracing':False,'state':'ready'}
(p/'candidate-release.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='file_sha256'}))
