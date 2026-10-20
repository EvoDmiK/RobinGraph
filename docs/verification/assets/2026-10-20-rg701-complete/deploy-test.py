from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,uuid
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
base=Path('/Users/kimdove/robingraph-test')
assets=root/'docs/verification/assets/2026-10-20-rg701-complete'
old=(base/'current').resolve(strict=True)
assert old.parent==base/'releases'
def docker(*args):
 return subprocess.check_output(['docker','--context','orbstack',*args],text=True)
prior=json.loads(docker('inspect','robingraph-api-test'))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=test' in prior['Config']['Env']
files=[root/n for n in ['pyproject.toml','uv.lock','Dockerfile']]
for folder in ['src','scripts','config','data','n8n']:
 files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and not any(part.endswith('.egg-info') for part in p.parts))
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
image='robingraph-api:test-rg701-django-only-'+digest[:12]
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
with (base/'rg701-build.log').open('w') as log:
 subprocess.run(['docker','--context','orbstack','build','--platform','linux/arm64','--build-arg','VCS_REF='+revision,
  '--label','org.robingraph.test.source-sha256='+digest,'-t',image,'.'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
absence=json.loads(docker('run','--rm','--network','none',image,'python','-c',"import importlib.util,json; result={name:importlib.util.find_spec(name) is None for name in ('fastapi','starlette')}; assert all(result.values()); print(json.dumps(result))"))
(assets/'image-packages.json').write_text(json.dumps(absence,indent=2)+'\n')
# A fixture smoke is isolated from every DB and does not replace the TEST app.
name='rg701-fixture-smoke'
try:
 subprocess.run(['docker','--context','orbstack','run','-d','--name',name,'--network','none','--read-only','--tmpfs','/tmp',image],check=True,stdout=subprocess.DEVNULL)
 for _ in range(45):
  result=subprocess.run(['docker','--context','orbstack','exec',name,'python','-c',
   "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'))['mode']=='fixture'; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if result.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Isolated Django fixture smoke failed')
finally:
 subprocess.run(['docker','--context','orbstack','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
release=base/'releases'/('rg701-django-only-'+digest[:12]+'-'+uuid.uuid4().hex[:6])
shutil.copytree(old,release);release.chmod(0o700)
env=release/'.env.nas.test'
env.write_text('\n'.join('ROBINGRAPH_IMAGE='+image if line.startswith('ROBINGRAPH_IMAGE=') else line for line in env.read_text().splitlines())+'\n');env.chmod(0o600)
receipt={'image':image,'source_sha256':digest,'file_sha256':hashes,'base_revision':revision,
 'previous_image':prior['Config']['Image'],'previous_release':str(old),'release':str(release),
 'state':'prepared','target':'test','uncommitted_source_snapshot':True,'production_changed':False,'fixture_network_none_smoke':True,'physical_reboot_tested':False}
def save():
 text=json.dumps(receipt,indent=2)+'\n';(release/'RELEASE.json').write_text(text);(assets/'test-release.json').write_text(text)
def switch(path):
 link=base/('.rg701-current-'+uuid.uuid4().hex);link.symlink_to(path);os.replace(link,base/'current')
save();switch(release)
try:
 subprocess.run([str(base/'manage.sh'),'start'],check=True,stdout=subprocess.DEVNULL)
 for _ in range(45):
  current=json.loads(docker('inspect','robingraph-api-test'))[0]
  if current['State'].get('Health',{}).get('Status')=='healthy':break
  time.sleep(2)
 else:raise RuntimeError('TEST health timeout')
 subprocess.run([str(base/'manage.sh'),'verify'],check=True,stdout=subprocess.DEVNULL)
 receipt['state']='verified';save()
except Exception:
 receipt['state']='rollback_started';save();switch(old)
 subprocess.run([str(base/'manage.sh'),'start'],check=True,stdout=subprocess.DEVNULL)
 receipt['state']='rolled_back';save();raise
print(json.dumps({k:v for k,v in receipt.items() if k!='file_sha256'}))
