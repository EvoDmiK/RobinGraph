import os,json,subprocess,time,sys
from pathlib import Path
out=Path(sys.argv[1]); source=json.loads((out/'public-production.json').read_text())
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
for x in s['Config']['Env']:
 k,v=x.split('=',1)
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_MAX_RETRIES='0',MLFLOW_HTTP_REQUEST_TIMEOUT='20')
from mlflow import MlflowClient
c=MlflowClient();e=c.get_experiment('50');assert e.name=='robingraph-prod'
rows=[]
for row in source['rows']:
 found=None
 for attempt in range(20):
  ts=c.search_traces(locations=['50'],filter_string=f'timestamp_ms >= {row["start_ms"]-10000}',max_results=100,include_spans=True)
  found=next((t for t in ts if any(p.name=='POST /v1/chat' and isinstance(p.inputs,dict) and isinstance(p.inputs.get('request'),dict) and p.inputs['request'].get('question')==row['question'] for p in t.data.spans)),None)
  if found and found.info.tags.get('response_api_disposition')==row['response'].get('disposition'):break
  found=None;time.sleep(2)
 assert found,'Missing production trace'
 for k,v in {'validation_phase':'postdeployment_public','source_snapshot':'6a95918a5533','jenkins_build':'RobinGraph-PROD/9'}.items():c.set_trace_tag(found.info.trace_id,k,v)
 roots=[p for p in found.data.spans if p.name=='POST /v1/chat']
 rows.append({'question':row['question'],'trace_id':found.info.trace_id,'experiment_id':found.info.experiment_id,'tags':dict(found.info.tags),'span_names':[p.name for p in found.data.spans],'root_inputs':roots[0].inputs,'root_outputs':roots[0].outputs,'http_disposition':row['response'].get('disposition')})
 (out/'production-traces.json').write_text(json.dumps({'experiment_id':'50','experiment_name':e.name,'rows':rows},ensure_ascii=False,indent=2))
print(json.dumps({'matched':len(rows),'experiment_id':'50','trace_ids':[r['trace_id'] for r in rows]}))
