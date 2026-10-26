"""Independent 20-case HTTP evaluator. Do not run before code freeze.

No credentials, writes, provider planning calls, or fixture substitution. Baseline
and active requests are distinct records. Reports API contract evidence, not DB
re-query proof. Questions stay in local artifacts; stdout shows IDs/counts only.
"""
import argparse,hashlib,importlib.util,json,os,time
from collections import Counter
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--cases',default='/tmp/rg212-followup-holdout.json');p.add_argument('--out',required=True);p.add_argument('--baseline-file');p.add_argument('--phase',choices=['baseline','active'],default='active');p.add_argument('--target',default='test');p.add_argument('--source-assets',default='/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-23-semantic-graph-interpreter');a=p.parse_args()
raw=Path(a.cases).read_bytes();assert hashlib.sha256(raw).hexdigest()=='31b741dde84a9a2fc42a222bd95fe19478d86d54a8befbb0d576fc5a91181790','Frozen holdout changed'
cases=json.loads(raw)['cases'];health=json.load(urlopen(a.base+'/health',timeout=10));assert health['deployment_target']==a.target and health['mode']=='neo4j'
os.environ['RG212_SCORE_ASSET_DIR']=a.source_assets
spec=importlib.util.spec_from_file_location('score_api',Path(__file__).with_name('score-api.py'));sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
baseline={x['case']['id']:x for x in json.loads(Path(a.baseline_file).read_text())['rows']} if a.baseline_file else {}

def convert(c):
 gold=c['gold'];base={'id':c['id'],'question':c['question'],'category':c['category']}
 if c['category']=='hold':expected={'expected_hold':gold['reason']}
 elif c['category']=='preserve':expected={'preserve':True}
 else:
  g=gold['supported_graph_question']
  if g['kind']=='taxon_traits':expected={'kind':'taxon_traits','taxon_name':g.get('rank_name') or next(iter(g.get('names',[])),None),'rank':gold.get('expected_taxon_rank'),'conditions':g['conditions']}
  elif g['kind'] in ('shared_diet','habitat_shared_diet'):expected={'kind':'relation','reference_taxon_name':g['names'][0],'share_basis':'trophic_niche','exclude_reference':True,**({'habitat':g['habitat']} if g.get('habitat') else {})}
  else:return None
 return {**base,'expected':expected}

def score(c,row):
 if row.get('error'):return {'status':'exception','errors':[row['error']]}
 transformed=convert(c)
 if transformed:
  verdict=sc.audit(transformed,row,None,baseline.get(c['id']))
  if c['category']=='preserve' and row['response'].get('result',{}).get('kind')=='graph_query':return {'status':'fail','errors':['general request intercepted as graph query']}
  if c['category']=='hold':
   payload=row['response'].get('result',{}).get('payload') or {}
   if payload.get('execution_summary') or payload.get('parsed') or payload.get('query_plan'):
    return {'status':'fail','errors':['held unsupported request exposes executed or accepted graph plan']}
  return verdict
 # Taxonomy requests require complete query scope. Existing result paths can
 # corroborate identities but cannot prove no omitted/extra condition. Never
 # upgrade such answers to a supported pass on text or result presence alone.
 r=row['response'];payload=(r.get('result') or {}).get('payload') or {};errors=[]
 if (r.get('result') or {}).get('kind')!='graph_query':errors.append('supported taxonomy not returned as graph_query')
 if payload.get('status') not in ('answer','empty','insufficient_data'):errors.append('taxonomy query not executed')
 return {'status':'fail' if errors else 'unverifiable','errors':errors,'limits':['Complete same-request taxonomy query contract unavailable; source paths alone are corroboration, not exact execution proof.'],'observed':{'kind':(r.get('result') or {}).get('kind'),'status':payload.get('status')}}

rows=[]
for c in cases:
 request={'question':c['question'],'intent':'auto','species_scope':'all','defer_enrichment':True,'defer_discovery':True};start=time.monotonic();row={'case':c,'request':request}
 try:
  req=Request(a.base+'/v1/chat',data=json.dumps(request).encode(),headers={'Content-Type':'application/json','User-Agent':'RobinGraph-RG212-Independent-Evaluation'})
  with urlopen(req,timeout=100) as r:row['response']=json.load(r)
 except Exception as e:row['error']=type(e).__name__+': '+str(e)[:180]
 row['elapsed_ms']=round((time.monotonic()-start)*1000)
 row['verdict']=score(c,row) if a.phase=='active' else {'status':'baseline_recorded' if not row.get('error') else 'exception'}
 rows.append(row)
 report={'phase':a.phase,'base':a.base,'health':health,'case_sha256':hashlib.sha256(raw).hexdigest(),'evaluation_type':'independent new cases first measurement unless already feedback-exposed','response_mocking':False,'bird_db_writes':0,'separate_provider_plan_calls':0,'counts':{category:dict(Counter(x['verdict']['status'] for x in rows if x['case']['category']==category)) for category in ['supported','hold','preserve']},'rows':rows}
 Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(c['id'],row['verdict']['status'],flush=True)
print(json.dumps(report['counts'],ensure_ascii=False))
