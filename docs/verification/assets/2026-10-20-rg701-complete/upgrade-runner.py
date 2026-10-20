"""TEST-only, reviewed source-preserving Django runner upgrade with rollback."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,uuid
ROOT=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
BASE=Path('/Users/kimdove/robingraph-test/pipelines/n8n-avilist-test')
ASSETS=ROOT/'docs/verification/assets/2026-10-20-rg701-complete'
ENV=BASE/'compose.env'

def docker(*args, input=None):
 return subprocess.check_output(['docker','--context','orbstack',*args],input=input,text=True)
def compose(*args):
 subprocess.run(['docker','--context','orbstack','compose','--env-file',str(ENV),'-f',str(ROOT/'compose.avilist-test.yml'),*args],check=True,stdout=subprocess.DEVNULL)
def atomic(path,data):
 part=path.with_name(path.name+'.migration-'+uuid.uuid4().hex)
 part.write_bytes(data);part.chmod(0o600);os.replace(part,path)
def healthy():
 for _ in range(45):
  d=json.loads(docker('inspect','robingraph-avilist-runner-test'))[0]
  if d['State'].get('Health',{}).get('Status')=='healthy': return
  if not d['State']['Running']:raise RuntimeError('TEST runner stopped')
  time.sleep(1)
 raise RuntimeError('TEST runner health timeout')
def probe():
 source="""import json,os,urllib.request,urllib.error
r=urllib.request.Request('http://127.0.0.1:18001/verify',data=b'{}',headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['ROBINGRAPH_AVILIST_PIPELINE_TOKEN']})
try:
 with urllib.request.urlopen(r,timeout=90) as response: print(json.dumps({'http':response.status,'body':json.load(response)}))
except urllib.error.HTTPError as error: print(json.dumps({'http':error.code,'body':json.load(error)}))
"""
 return json.loads(docker('exec','-i','robingraph-avilist-runner-test','python','-',input=source))

app=json.loads(docker('inspect','robingraph-api-test'))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=test' in app['Config']['Env']
image_tag=app['Config']['Image'];assert image_tag.startswith('robingraph-api:test-rg701-django-only-')
image=app['Image']  # Pin the running, tested image ID rather than a mutable tag.
old=json.loads(docker('inspect','robingraph-avilist-runner-test'))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=test' in old['Config']['Env']
old_env=ENV.read_bytes()
required=('ROBINGRAPH_AVILIST_IMAGE','ROBINGRAPH_AVILIST_CODE_DIR','ROBINGRAPH_AVILIST_STATE_DIR','ROBINGRAPH_AVILIST_APPROVAL_DIR')
lines=old_env.decode().splitlines()
values={}
for name in required:
 matches=[line.split('=',1)[1] for line in lines if line.startswith(name+'=')]
 assert len(matches)==1, 'Missing or duplicated runner selector: '+name
 values[name]=matches[0]
mounts={m['Destination']:m for m in old['Mounts']}
for dest,selector,writable in [('/code','ROBINGRAPH_AVILIST_CODE_DIR',False),('/state','ROBINGRAPH_AVILIST_STATE_DIR',True),('/review','ROBINGRAPH_AVILIST_APPROVAL_DIR',False)]:
 assert Path(mounts[dest]['Source']).resolve()==Path(values[selector]).resolve()
 assert mounts[dest]['RW']==writable
assert Path(values['ROBINGRAPH_AVILIST_STATE_DIR']).resolve()==BASE/'state'
assert Path(values['ROBINGRAPH_AVILIST_APPROVAL_DIR']).resolve()==BASE/'review'
rollback_env=('\n'.join('ROBINGRAPH_AVILIST_IMAGE='+old['Image'] if line.startswith('ROBINGRAPH_AVILIST_IMAGE=') else line for line in lines)+'\n').encode()
old_probe=probe();assert old_probe['http']==200 and old_probe['body']['status']=='verified'
old_code=(BASE/'state/review-package/code.json').read_bytes()
old_approval=(BASE/'review/approval.json').read_bytes()
key=app['Config']['Labels']['org.robingraph.test.source-sha256']
release=json.loads((ASSETS/'test-release.json').read_text())
assert release['source_sha256']==key and release['image']==image_tag and release['state']=='verified'
for name,expected in release['file_sha256'].items():
 if any(part.endswith('.egg-info') for part in Path(name).parts): continue
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected, 'Reviewed source changed: '+name
backup=BASE/'backups'/('django-only-'+key[:12]+'-'+uuid.uuid4().hex[:6]);backup.mkdir(parents=True,mode=0o700)
for name,data in [('compose.env',old_env),('code.json',old_code),('approval.json',old_approval)]:atomic(backup/name,data)
code=BASE/'code-releases'/('django-only-'+key[:12]);code.mkdir(parents=True,exist_ok=False)
for name in ['src','scripts','config','data']:
 shutil.copytree(ROOT/name,code/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
expected_copy={name:value for name,value in release['file_sha256'].items() if Path(name).parts[0] in ('src','scripts','config','data') and not any(part.endswith('.egg-info') for part in Path(name).parts)}
actual_copy={str(path.relative_to(code)):hashlib.sha256(path.read_bytes()).hexdigest() for path in code.rglob('*') if path.is_file()}
assert actual_copy==expected_copy, 'Copied file set or bytes differ from tested image source receipt'
assert not (code/'src/robingraph/api/app.py').exists()
assert not (code/'src/robingraph/api/ingest_router.py').exists()
new=[]
for line in old_env.decode().splitlines():
 if line.startswith('ROBINGRAPH_AVILIST_IMAGE='):line='ROBINGRAPH_AVILIST_IMAGE='+image
 if line.startswith('ROBINGRAPH_AVILIST_CODE_DIR='):line='ROBINGRAPH_AVILIST_CODE_DIR='+str(code)
 new.append(line)
receipt={'target':'test','image':image,'image_tag':image_tag,'image_source_sha256':key,'previous_image':old['Config']['Image'],'previous_image_id':old['Image'],'baseline_probe':old_probe,'code_directory':str(code),'backup_directory':str(backup),'state':'prepared','production_changed':False}
def save(): (ASSETS/'runner-upgrade.json').write_text(json.dumps(receipt,indent=2)+'\n')
save()
try:
 atomic(ENV,('\n'.join(new)+'\n').encode());compose('up','-d','runner');healthy()
 failure=probe();assert (failure['http'],failure['body'].get('error'))==(409,'code_changed')
 receipt['old_binding_probe']=failure;receipt['state']='old_binding_rejected';save()
 # Re-fetch and rebuild the exact reviewed data under the new code before any rebind.
 verify="""from pathlib import Path
import json,hashlib,os,tempfile
from datetime import datetime,timezone
from scripts import run_avilist_pipeline as runner,serve_avilist_pipeline as service
from robingraph.ingest.avilist_pipeline import validate_approval
import importlib.util
assert importlib.util.find_spec('fastapi') is None and importlib.util.find_spec('starlette') is None
_,root,approval_path=service._check_startup(os.environ,runner)
package=root/service.PACKAGE
previous=json.loads((package/service.CODE_FILE).read_bytes())
current=service._code_fingerprint(runner)
assert set(current)=={'runner','core','builder','service','django_asgi'}
assert all(previous[name]==current[name] for name in ('runner','core','builder'))
with tempfile.TemporaryDirectory(prefix='.django-review-',dir=root) as directory:
 candidate=Path(directory)/'review-package'
 runner.prepare(None,candidate)
 assert service._same_package(candidate,package)
 manifest,bundle,approval=runner.load_review(candidate,approval_path)
 assert runner.digest(manifest)==approval['manifest_sha256']
 assert runner.digest(bundle)==approval['bundle_sha256']
 fresh={**approval,'reviewer_type':'agent','reviewer':'Codex Django transport migration review',
  'reviewed_at':datetime.now(timezone.utc).isoformat(),
  'rationale':'Source-preserving Django-only migration: pinned official source re-fetched, manifest and bundle byte-identical, native contract/auth/body/hash gates independently reviewed and tested. TEST only; no domain projection.'}
 validate_approval(manifest,bundle,fresh)
 print(json.dumps({'old_fingerprint':previous,'new_fingerprint':current,'approval':fresh,
  'manifest_sha256':runner.digest(manifest),'bundle_sha256':runner.digest(bundle),
  'source_sha256':hashlib.sha256((candidate/'source.json').read_bytes()).hexdigest(),
  'source_refetched':True,'package_byte_identical':True,'legacy_packages_absent':True}))
"""
 prepared=json.loads(docker('exec','-i','robingraph-avilist-runner-test','python','-',input=verify))
 atomic(backup/'new-review.json',json.dumps(prepared,indent=2).encode())
 receipt.update({k:v for k,v in prepared.items() if k not in ('approval','source_sha256')})
 receipt['pinned_source_sha256']=prepared['source_sha256']
 reviewed={'service':'dd2fc90717cdc3de35b65e8a99aaa5ca91f5dd51c89d6091447135605b55622e',
           'django_asgi':'986eae572e951e637d1656d736a9794c67c452853aec14f97f9e01992a13566f'}
 assert all(prepared['new_fingerprint'][name]==value for name,value in reviewed.items())
 receipt['reviewed_transport_fingerprint']=reviewed
 receipt['reviewer_type']='agent';receipt['reviewed_at']=prepared['approval']['reviewed_at']
 compose('stop','runner')
 assert json.loads(docker('inspect','robingraph-avilist-runner-test'))[0]['State']['Running'] is False
 # A stopped runner cannot consume either half of this two-file operator update.
 atomic(BASE/'review/approval.json',json.dumps(prepared['approval'],sort_keys=True,separators=(',',':')).encode())
 atomic(BASE/'state/review-package/code.json',json.dumps(prepared['new_fingerprint'],sort_keys=True,separators=(',',':')).encode())
 receipt['state']='reviewed_binding_installed';save()
 compose('up','-d','runner');healthy()
 after=probe();assert (after['http'],after['body'].get('status'))==(200,'verified')
 assert after['body']['manifest_sha256']==prepared['manifest_sha256']
 receipt['new_binding_probe']=after;receipt['state']='verified';save()
 print(json.dumps({k:v for k,v in receipt.items() if k not in ('old_fingerprint','new_fingerprint')}))
except Exception:
 errors=[]
 def attempt(label,action):
  try:return action()
  except Exception as failure:errors.append({'step':label,'type':type(failure).__name__});return None
 receipt['state']='rollback_started'
 attempt('audit_before',save)
 attempt('stop_new',lambda:compose('stop','runner'))
 def stopped():
  assert json.loads(docker('inspect','robingraph-avilist-runner-test'))[0]['State']['Running'] is False
  return True
 safely_stopped=attempt('confirm_stopped',stopped)
 restored_ok=False
 if safely_stopped:
  before_errors=len(errors)
  attempt('restore_approval',lambda:atomic(BASE/'review/approval.json',old_approval))
  attempt('restore_code_binding',lambda:atomic(BASE/'state/review-package/code.json',old_code))
  attempt('restore_environment',lambda:atomic(ENV,rollback_env))
  def confirm_restored():
   assert (BASE/'review/approval.json').read_bytes()==old_approval
   assert (BASE/'state/review-package/code.json').read_bytes()==old_code
   assert ENV.read_bytes()==rollback_env
   return True
  restored_ok=attempt('confirm_restored',confirm_restored) and len(errors)==before_errors
  if restored_ok: attempt('start_previous',lambda:compose('up','-d','runner'))
 def verify_rollback():
  healthy()
  restored=json.loads(docker('inspect','robingraph-avilist-runner-test'))[0]
  assert restored['Image']==old['Image']
  restored_mounts={m['Destination']:m for m in restored['Mounts']}
  for dest in ('/code','/state','/review'):
   assert restored_mounts[dest]['Source']==mounts[dest]['Source'] and restored_mounts[dest]['RW']==mounts[dest]['RW']
  assert 'ROBINGRAPH_DEPLOY_TARGET=test' in restored['Config']['Env']
  check=probe();assert check['http']==200 and check['body']['status']=='verified'
  return True
 verified=attempt('verify_previous',verify_rollback) if restored_ok else False
 receipt['state']='rolled_back' if verified else 'rollback_unverified'
 receipt['rollback_errors']=errors
 attempt('audit_after',save)
 print(json.dumps({'state':receipt['state'],'rollback_verified':bool(verified),'errors':errors}))
 raise
