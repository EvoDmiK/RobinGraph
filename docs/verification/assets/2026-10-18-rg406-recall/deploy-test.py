from pathlib import Path
import hashlib,json,subprocess,tempfile,shutil,os,time
base=Path('/Users/kimdove/robingraph-test');old=(base/'current').resolve();files=[Path('src/robingraph/retrieval')/n for n in ['taxon_name_resolution.py','taxon_name_vectors_neo4j.py']];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();image='robingraph-api:test-rg406-recall-'+digest[:12]
prior=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
assert 'ROBINGRAPH_DEPLOY_TARGET=test' in prior['Config']['Env']
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 lines=['FROM '+prior['Config']['Image']]
 for source in files:
  (p/source.name).write_bytes(source.read_bytes())
  lines.append('COPY --chown=10001:10001 '+source.name+' /app/'+str(source))
 lines.append('LABEL org.robingraph.test.patch-sha256="'+digest+'"')
 (p/'Dockerfile').write_text('\n'.join(lines)+'\n')
 subprocess.run(['docker','--context','orbstack','build','-t',image,d],check=True,stdout=subprocess.DEVNULL)
release=base/'releases'/('rg406-recall-'+digest[:12]);shutil.copytree(old,release);release.chmod(0o700)
env=release/'.env.nas.test';raw=env.read_text();env.write_text('\n'.join('ROBINGRAPH_IMAGE='+image if line.startswith('ROBINGRAPH_IMAGE=') else line for line in raw.splitlines())+'\n');env.chmod(0o600)
receipt={'image':image,'base_image':prior['Config']['Image'],'base_revision':prior['Config']['Labels']['org.opencontainers.image.revision'],'patch_sha256':digest,'file_sha256':hashes,'previous_release':str(old),'state':'prepared','target':'test','uncommitted_runtime_patch':True}
def switch(path):
 link=base/'.scope-current';link.unlink(missing_ok=True);link.symlink_to(path);os.replace(link,base/'current')
switch(release)
try:
 subprocess.run([str(base/'manage.sh'),'start'],check=True)
 for _ in range(50):
  p=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
  if p['State'].get('Health',{}).get('Status')=='healthy':break
  time.sleep(2)
 else:raise RuntimeError('TEST health timeout')
 subprocess.run([str(base/'manage.sh'),'verify'],check=True,stdout=subprocess.DEVNULL)
 receipt['state']='verified'
except Exception:
 switch(old);subprocess.run([str(base/'manage.sh'),'start'],check=True);raise
(release/'RELEASE.json').write_text(json.dumps(receipt,indent=2)+'\n')
Path('docs/verification/assets/2026-10-18-rg406-recall/test-release.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('TEST deployed and API verified:',image)
