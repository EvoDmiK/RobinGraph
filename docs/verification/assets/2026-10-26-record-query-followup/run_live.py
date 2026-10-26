"""One actual TEST request per case; preserve first responses and same-request MLflow evidence."""
import os,json,subprocess,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
out=root/'docs/verification/assets/2026-10-26-record-query-followup'
split=sys.argv[1]
assert split in ('regression','fresh','followup','recheck')
cases_path=root/'data/eval/graph_questions/question-families-v6'/({'fresh':'holdout.json','recheck':'holdout.json','followup':'feedback12.json'}.get(split,'regression.json'))
cases=json.loads(cases_path.read_text())['cases']
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(v.split('=',1) for v in s['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='test' and env['ROBINGRAPH_GRAPH_INTERPRETER']=='semantic'
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
from mlflow import MlflowClient
c=MlflowClient()
path=out/f'{split}-traces.json'
rows=json.loads(path.read_text())['rows'] if path.exists() else []
def run_case(case):
 label=case['id'];body=case['request']
 pending_path=out/f'{split}-pending-{label}.json'
 if pending_path.exists():
  pending=json.loads(pending_path.read_text());response=pending['response'];http=pending['http_status'];start=pending['search_start_ms'];elapsed=pending['elapsed_seconds']
 else:
  start=int(time.time()*1000)-1000;t=time.monotonic()
  try:
   with urlopen(Request('http://127.0.0.1:8000/v1/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=120) as r:response=json.load(r);http=r.status
  except HTTPError as error:response=json.load(error);http=error.code
  elapsed=round(time.monotonic()-t,3)
  pending_path.write_text(json.dumps({'case':label,'search_start_ms':start,'http_status':http,'response':response,'elapsed_seconds':elapsed},ensure_ascii=False)+'\n')
 found=None
 for attempt in range(30):
  traces=c.search_traces(locations=['33'],filter_string=f'timestamp_ms >= {start - 10000}',max_results=50,include_spans=True)
  found=next((t for t in traces if any(p.name=='POST /v1/chat' and isinstance(p.inputs,dict) and isinstance(p.inputs.get('request'),dict) and p.inputs['request'].get('question') == body['question'] for p in t.data.spans)),None)
  if found and found.info.tags.get('response_api_disposition')==response.get('disposition') and all(k in found.info.tags for k in ('response_reason','failure_stage')):break
  found=None;time.sleep(2)
 tags={k:found.info.tags.get(k) for k in ('response_disposition','response_reason','failure_stage','response_api_disposition','route_method','selected_intent')} if found else {}
 children=[{'name':p.name,'span_id':p.span_id,'parent_id':p.parent_id,'inputs':p.inputs,'outputs':p.outputs,'attributes':{k:v for k,v in p.attributes.items() if k.startswith('graph_intent.') or k in ('reason','stage','rejection_detail','selected_interpreter','judgment_source','evidence_reconciliations')}} for p in found.data.spans if p.name.startswith('graph_intent.') or p.name=='POST /v1/chat'] if found else []
 row={'case':label,'http_status':http,'trace_id':found.info.trace_id if found else None,'tags':tags,'diagnostic_spans':children,'response':response,'request':body,'elapsed_seconds':elapsed}
 print(json.dumps({'case':label,'disposition':response.get('disposition'),'reason':tags.get('response_reason'),'trace_id':row['trace_id'],'elapsed_seconds':elapsed}),flush=True)
 return row
from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=4) as pool:
 futures=[pool.submit(run_case,case) for case in cases if not any(r['case']==case['id'] for r in rows)]
 for future in as_completed(futures):
  rows.append(future.result())
  rows.sort(key=lambda row:row['case'])
  path.write_text(json.dumps({'image':s['Config']['Image'],'response_mocking':False,'bird_db_writes':0,'concurrency':4,'rows':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'saved':len(rows),'total':len(cases)}),flush=True)
