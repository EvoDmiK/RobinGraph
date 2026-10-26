"""Small TEST cold/warm sampling, not a load or peak-resource test."""
import json, subprocess, threading, time, urllib.request
from pathlib import Path
p=Path(__file__).resolve().parent
receipt=json.loads((p/'test-release.json').read_text());assert receipt['graph_intent_mode']=='active'
docker=['docker','--context','orbstack']; name='robingraph-api-test'
def stats():
 return json.loads(subprocess.check_output(docker+['stats','--no-stream','--format','{{json .}}',name],text=True))
subprocess.run(docker+['restart',name],check=True,stdout=subprocess.DEVNULL)
for _ in range(40):
 try:
  h=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2))
  if h['deployment_target']=='test' and h['mode']=='neo4j':break
 except Exception:pass
 time.sleep(.5)
else:raise RuntimeError('TEST unhealthy')
rows=[]; samples=[]; done=threading.Event()
def monitor():
 while not done.is_set():
  samples.append({'elapsed_seconds':round(time.perf_counter()-started,3),'docker_stats':stats()})
started=time.perf_counter();thread=threading.Thread(target=monitor);thread.start()
try:
 for i in range(6):
  req=urllib.request.Request('http://127.0.0.1:8000/v1/chat',data=json.dumps({'question':'열매 먹는 참새목 새를 찾아 줘','defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'})
  t=time.perf_counter(); d=json.load(urllib.request.urlopen(req,timeout=30));assert d['disposition']=='answer' and d['result']['payload']['items']
  rows.append({'phase':'cold' if i==0 else 'warm','elapsed_ms':round((time.perf_counter()-t)*1000,3),'item_count':len(d['result']['payload']['items'])})
finally:done.set();thread.join()
report={'scope':'TEST active, one cold then five warm sequential identical read-only questions; sampled container CPU/memory, not peak or load capacity','response_mocking':False,'bird_db_writes':0,'prototype_cache':'process memory only; no answer cache','rows':rows,'resource_samples':samples,'final_snapshot':stats(),'production_changed':False}
(p/'runtime-benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'requests':len(rows),'resource_samples':len(samples),'latencies_ms':[r['elapsed_ms'] for r in rows]}))
