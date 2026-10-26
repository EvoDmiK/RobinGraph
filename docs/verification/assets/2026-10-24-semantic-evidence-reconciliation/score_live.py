"""Artifact-only strict scoring; never makes API/provider/DB calls."""
import importlib.util,json,os,sys
from collections import Counter
from pathlib import Path
ROOT=Path.cwd()
os.environ['RG212_SCORE_ASSET_DIR']=str(ROOT/'docs/verification/assets/2026-10-23-semantic-graph-interpreter')
spec=importlib.util.spec_from_file_location('prior_strict', '/tmp/rg212-followup-checks/score-api.py');sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/verification/assets/2026-10-24-semantic-evidence-reconciliation/live-traces.json'
data=json.loads(source.read_text());out=[]
for row in data['rows']:
 case=row['case_spec'];response=row['response'];payload=(response.get('result') or {}).get('payload') or {}
 verdict=sc.audit(case,{'response':response,'request':row['request']},None,None)
 # Scope rank is separately observable in the returned taxon. The previous
 # scorer resolves name rank via catalog; verify actual response rank too.
 if case['category']=='supported' and case['expected']['kind']=='taxon_traits' and payload.get('taxon'):
  if payload['taxon'].get('rank')!=case['expected'].get('rank'):
   verdict['status']='fail';verdict['errors'].append('response taxon rank differs from expected')
 route=next((s for s in row['diagnostic_spans'] if s['name']=='graph_intent.route'),None)
 intent=route.get('outputs') if route else None;route_verdict={'status':'unverifiable','errors':['No complete same-request interpreted intent output']}
 if case['category']=='supported' and isinstance(intent,dict):
  parsed={'kind':intent.get('kind'),'names':[s['text'] for s in intent.get('species',[])],
   'rank_name':(intent.get('rank') or {}).get('text'),'habitat':intent.get('habitat'),
   'group':(intent.get('group') or {}).get('text'),'criterion':None,
   'conditions':[c[0] for c in intent.get('conditions',[])]}
  gate=(route.get('attributes') or {}).get('graph_intent.disposition')
  route_verdict=sc.plan.score(case,{'gate':gate,'parsed':parsed})
  for field in ('negation','residual','unsupported','ambiguity','unsupported_food'):
   if intent.get(field):route_verdict={'status':'fail','errors':route_verdict.get('errors',[])+['Unexpected intent restriction: '+field]}
  if case['expected']['kind']=='relation' and (intent.get('diet')!='niche' or intent.get('relation')!='same'):
   route_verdict={'status':'fail','errors':route_verdict.get('errors',[])+['Wrong relation diet or equality']}
 if case['category']=='hold':
  # Preserve API safety check; explicit executor metadata on a held question is
  # additional evidence of partial execution that must not count as safe hold.
  if payload.get('execution_summary'):
   verdict={'status':'fail','errors':['Held question returned execution_summary']}
  route_verdict={'status':'not_applicable','errors':[]}
 audit=next((s for s in row['diagnostic_spans'] if s['name']=='graph_intent.audit'),None)
 rec=next((s for s in row['diagnostic_spans'] if s['name']=='graph_intent.reconciliation'),None)
 if audit and (audit.get('outputs') or {}).get('faithful') is not True and response.get('disposition')=='answer':
  verdict={'status':'fail','errors':['Answer despite explicit negative same-request audit']}
 out.append({'id':case['id'],'category':case['category'],'api_verdict':verdict,'same_request_intent_verdict':route_verdict,
  'http_status':row['http_status'],'api_disposition':response.get('disposition'),'result_status':payload.get('status'),
  'trace_id':row['trace_id'],'tags':row['tags'],'reconciliations':(rec.get('attributes') or {}).get('evidence_reconciliations') if rec else None,
  'observed_audit':audit.get('outputs') if audit else None})
report={'source':str(source),'method':'Read saved actual API and same-request MLflow trace artifacts only. No new calls.','api_counts':{c:dict(Counter(r['api_verdict']['status'] for r in out if r['category']==c)) for c in ('supported','hold')},'intent_counts':{c:dict(Counter(r['same_request_intent_verdict']['status'] for r in out if r['category']==c)) for c in ('supported','hold')},'rows':out,'limitations':['Intent exactness is reported separately and never upgrades absent execution_summary to API execution success.','No independent database record re-query.','New cases first measurement; original three feedback-exposed regression.']}
Path('/tmp/rg-evidence-normalization-review/live-strict-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('api_counts','intent_counts')}))
for r in out:print(r['id'],r['api_verdict']['status'],r['same_request_intent_verdict']['status'],json.dumps(r['api_verdict'].get('errors',[]),ensure_ascii=False))
