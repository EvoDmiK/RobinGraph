"""Read existing traces by ID to preserve exact root request matching; no chat requests."""
import os,json,subprocess,sys
from pathlib import Path
out=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-26-record-query-followup')
split=sys.argv[1];assert split in ('regression','fresh','followup','recheck')
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(x.split('=',1) for x in s['Config']['Env']);assert env['ROBINGRAPH_DEPLOY_TARGET']=='test'
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='2')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
from mlflow import MlflowClient
client=MlflowClient();path=out/f'{split}-traces.json';artifact=json.loads(path.read_text());ids=[]
for row in artifact['rows']:
 trace=client.get_trace(row['trace_id']);roots=[p for p in trace.data.spans if p.name=='POST /v1/chat']
 assert len(roots)==1,row['case'];root=roots[0]
 assert root.inputs['request']['question']==row['request']['question'],row['case']
 assert trace.info.tags['response_api_disposition']==row['response']['disposition'],row['case']
 if not any(p['name']=='POST /v1/chat' for p in row['diagnostic_spans']):
  row['diagnostic_spans'].append({'name':root.name,'span_id':root.span_id,'parent_id':root.parent_id,'inputs':root.inputs,'outputs':root.outputs,'attributes':{k:v for k,v in root.attributes.items() if k in ('http.route','http.status_code','robingraph.disposition')}})
 row['exact_root_question_verified']=True;ids.append(row['trace_id'])
assert len(ids)==len(set(ids))
path.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
(out/f'{split}-root-verification.json').write_text(json.dumps({'cases':len(ids),'unique_trace_ids':len(set(ids)),'exact_root_request_match':True,'read_only_trace_calls':len(ids),'new_api_calls':0},indent=2)+'\n')
print(json.dumps({'verified':len(ids),'new_api_calls':0}))
