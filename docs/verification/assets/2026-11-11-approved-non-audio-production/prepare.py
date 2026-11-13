from pathlib import Path
import subprocess,tarfile,io,shutil,json,hashlib,re
root=Path('/Volumes/OrcaRoot/orca/workspaces/RobinGraph/dev-codex')
work=Path('/tmp/robingraph-approved-prod-20261111')
base='5056ccba9e75a891cc133a6f371b49deb5dbc598'
candidate=work/'candidate'
assert not candidate.exists(),'Keep previous candidate immutable'
parts=['src','scripts','config','data','n8n','pyproject.toml','uv.lock','Dockerfile','README.md','.python-version','.dockerignore']
archive=subprocess.check_output(['git','archive',base,*parts],cwd=root)
candidate.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tar: tar.extractall(candidate,filter='data')
changed=subprocess.check_output(['git','diff','--name-only',base,'--','src'],cwd=root,text=True).splitlines()
changed+=['src/robingraph/retrieval/external_cache.py','src/robingraph/api/static/explore.html','src/robingraph/api/static/explore.js','src/robingraph/api/static/explore.css']
for name in changed:
 if any(word in name for word in ('audio','recordings')): continue
 target=candidate/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(root/name,target)
def edit(name,fn):
 p=candidate/name;s=p.read_text();t=fn(s);assert s!=t,name;p.write_text(t)
def cut(s,start,end):
 assert s.count(start)==1 and s.count(end)==1,(start,end)
 a=s.index(start);b=s.index(end,a);return s[:a]+s[b:]
edit('src/robingraph/api/drf/application.py',lambda s:cut(s.replace('    audio_service=None,\n',''),'    if audio_service is not None:\n','    return DjangoApiApplication(').replace('build_urlconf(service, ingest, schema, audio_service=audio_service)','build_urlconf(service, ingest, schema)'))
edit('src/robingraph/api/drf/urls.py',lambda s:cut(s,'    if audio_service is not None:\n','    if ingest is not None:\n').replace(', *, audio_service=None', '').replace(', audio_service=audio_service',''))
edit('src/robingraph/api/drf/views.py',lambda s:cut(s,'class AudioReviewUIView(RobinGraphView):\n','class FaviconView(RobinGraphView):\n'))
def service(s):
 s='\n'.join(line for line in s.split('\n') if not any('"'+n+'"' in line and ':' in line for n in ('audio-review.html','audio-review.js','audio-review.css')))
 s=cut(s,'    def audio_review_ui(self)', '    def explore_ui(self)')
 # Drop the now-empty selector branch after asset allow-list removal.
 s=s.replace('            names = ("audio-review.html", "audio-review.js", "audio-review.css", "styles.css")\n','')
 return s
edit('src/robingraph/api/services.py',service)
def cli(s):
 s=s.replace('    from .retrieval.recordings import read_recordings\n','')
 s=cut(s,'    audio_service = None\n','    summarize_notes = ')
 return '\n'.join(line for line in s.split('\n') if 'recordings=audio_service.' not in line and 'audio_service=audio_service,' not in line)
edit('src/robingraph/cli.py',cli)
def profile(s):
 s=s.replace('recordings=None, ','')
 s=cut(s,'    def recording_stage(lineage):\n','    def trait_stage(lineage):\n')
 s='\n'.join(line for line in s.split('\n') if "'recordings':state['audio']" not in line and "'recording_availability':state['audio']" not in line)
 return s.replace(" + state['audio']['warnings']",'').replace(' audio=RunnableLambda(recording_stage),','')
edit('src/robingraph/retrieval/species_profile.py',profile)
def js(s):
 s=cut(s,'  var recordingSourcesSequence = 0;\n','  var DISPOSITION_LABELS = ')
 s=cut(s,'    var audioControls = doc.createElement("section");\n','    // A photo-only update leaves notes intact;')
 return '\n'.join(line for line in s.split('\n') if not any(x in line for x in ('stopRecordings','stopSpeciesRecordings','sanitizeAudioUrl:','renderRecordings(fresh)','back.appendChild(audioArea)')))
edit('src/robingraph/api/static/chat.js',js)
edit('src/robingraph/api/static/styles.css',lambda s:s[:s.index('\n.species-recording {')]+ '\n')
# Audio routes, provider metadata and review/collection modules are absent from the production baseline.
assert not list((candidate/'src').rglob('*audio*'))
assert not list((candidate/'src').rglob('*recordings*'))
for name in ('src/robingraph/api/services.py','src/robingraph/api/drf/urls.py','src/robingraph/cli.py','src/robingraph/api/static/chat.js'):
 s=(candidate/name).read_text()
 assert not any(x in s for x in ('AudioService','audio-review','recording_stage','renderRecordings','sanitizeAudioUrl')),name
manifest={str(p.relative_to(candidate)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(candidate.rglob('*')) if p.is_file()}
summary={'production_base_revision_pending_live_confirmation':base,'source_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),'audio_feature_excluded':True,'files':manifest}
(work/'candidate-manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='files'}))
