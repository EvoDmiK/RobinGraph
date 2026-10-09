import concurrent.futures,json,subprocess,sys
from pathlib import Path
from urllib.parse import urlencode
labels=json.loads(Path('src/robingraph/retrieval/species_ko_names.json').read_text())['labels']
traits=json.loads(Path('docs/verification/assets/2026-10-09-trait503-source-resolution.json').read_text())['species']
baseline=json.loads(Path('docs/verification/assets/2026-10-09-resolution-baseline.json').read_text())
requested={r['taxon_id'] for r in baseline['conservation']}
reference_index=json.loads(Path('src/robingraph/retrieval/birdbase_conservation_index.json').read_text())['entries']
primary_refs=json.loads(Path('src/robingraph/retrieval/conservation_index.json').read_text())['references']
refs=[r for tid,r in reference_index.items() if tid in requested and tid not in primary_refs and r.get('category')]
cases={}
def add(tid,science,query=None,**checks):
 cases[tid]={'taxon_id':tid,'scientific_name':science,'query':query or science,**checks}
for name in ['박새','까치','까마귀','큰부리까마귀','오색방울새','사랑앵무','흰목딱새','프르제발스키되새']:
 for tid,r in labels.items():
  if r['name']==name:add(tid,r['scientific_name'],name,korean=name)
for disposition in sorted({r['disposition'] for r in traits}):
 for inference in [None,'YES','NO']:
  subset=[r for r in traits if r['disposition']==disposition and r['source_inference']==inference]
  for r in subset[:2]:add(r['taxon_id'],r['scientific_name'],has_traits=True)
for category in sorted({r['category'] for r in refs}):
 r=next(r for r in refs if r['category']==category)
 add(r['taxon_id'],r['scientific_name'],reference_category=category)
def check(case):
 result=dict(case)
 try:
  raw=subprocess.run(['curl','-fsS','--max-time','100',sys.argv[1]+'/v1/taxa/profile?'+urlencode({'name':case['query']})],capture_output=True,text=True,check=True)
  p=json.loads(raw.stdout);t=p.get('taxon',{});c=p.get('conservation') or {};ref=c.get('reference_assessment') or {};ts=p.get('traits') or []
  result.update(actual_id=t.get('taxon_id'),actual_scientific_name=t.get('scientific_name'),actual_korean=t.get('korean_name'),trait_count=len(ts),conservation=c,traits=ts)
  issues=[]
  if t.get('taxon_id')!=case['taxon_id'] or t.get('scientific_name')!=case['scientific_name']:issues.append('identity')
  if case.get('korean') and t.get('korean_name')!=case['korean']:issues.append('Korean name')
  if case.get('has_traits') and not ts:issues.append('empty traits')
  if case.get('reference_category') and ref.get('category')!=case['reference_category']:issues.append('reference category')
  if case['query']=='박새':
   mass=next(x for x in ts if x['name']=='body_mass')
   if mass['value']!=16.55 or mass.get('summary_statistic')!='literature_bounds_mean':issues.append('Parus mass scope')
  if case['query']=='까치':
   mass=next(x for x in ts if x['name']=='body_mass')
   if mass['value']!=220.64 or mass.get('summary_statistic')!='sample_mean':issues.append('Pica study priority')
  result.update(ok=not issues,issues=issues)
 except Exception as e:result.update(ok=False,error=type(e).__name__)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,cases.values()))
Path(sys.argv[2]).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'actual_http_requests':len(results),'failures':[{k:v for k,v in r.items() if k not in ['conservation','traits']} for r in results if not r['ok']]},ensure_ascii=False))
sys.exit(any(not r['ok'] for r in results))
