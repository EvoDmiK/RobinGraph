"""Actual TEST calls followed by same-request MLflow trace/tag inspection; no mocks."""
import os,json,subprocess,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
out=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-24-semantic-evidence-reconciliation')
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(v.split('=',1) for v in s['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='test'
assert env['ROBINGRAPH_GRAPH_INTERPRETER']=='semantic'
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
from mlflow import MlflowClient
c=MlflowClient()
case_specs=json.loads((out/'final-cases.json').read_text())['cases']
cases=[(x['id'],{'question':x['question']},None) for x in case_specs]
resume='--resume' in sys.argv
rows=json.loads((out/'final-traces.json').read_text())['rows'] if resume else []
for label,body,want in cases:
 if any(r['case']==label for r in rows):continue
 body={**body,'defer_enrichment':True,'defer_discovery':True};start=int(time.time()*1000)-1000
 if resume:
  pending=json.loads((out/'final-pending.json').read_text());assert pending['case']==label
  response=pending['response'];http=pending['http_status'];start=pending['search_start_ms']
 else:
  with urlopen(Request('http://127.0.0.1:8000/v1/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=90) as r:
   response=json.load(r);http=r.status
 (out/'final-pending.json').write_text(json.dumps({'case':label,'search_start_ms':start,'http_status':http,'response':response},ensure_ascii=False)+'\n')
 found=None
 for attempt in range(45):
  traces=c.search_traces(locations=['33'],filter_string=f'timestamp_ms >= {start}',max_results=50,include_spans=True)
  found=next((t for t in traces if any(s.name=='POST /v1/chat' and body['question'] in json.dumps(s.inputs,ensure_ascii=False) for s in t.data.spans)),None)
  if found and found.info.tags.get('response_api_disposition')==response['disposition'] and all(k in found.info.tags for k in ('response_reason','failure_stage')):break
  found=None
  time.sleep(2)
 assert found is not None,label+' missing trace'
 tags={k:found.info.tags.get(k) for k in ('response_disposition','response_reason','failure_stage','response_api_disposition','route_method','selected_intent')}
 reason=tags['response_reason'];stage=tags['failure_stage']
 # The actual returned disposition, not SDK trace state OK, decides whether this was answered.
 assert tags['response_api_disposition']==response['disposition'],label
 if response['disposition']!='answer':assert reason not in (None,'none','unknown') and stage not in (None,'none','unknown'),(label,tags)
 else:assert (reason,stage)==('none','none'),(label,tags)
 if want:assert reason==want,(label,tags)
 filtered=c.search_traces(locations=['33'],filter_string=f"timestamp_ms >= {start} AND tags.response_reason = '{reason}' AND tags.failure_stage = '{stage}'",max_results=50,include_spans=False)
 assert found.info.trace_id in [t.info.trace_id for t in filtered],label+' tag search failed'
 children=[{'name':p.name,'span_id':p.span_id,'parent_id':p.parent_id,'inputs':p.inputs,'outputs':p.outputs,'attributes':{k:v for k,v in p.attributes.items() if k.startswith('graph_intent.') or k in ('reason','stage','rejection_detail','selected_interpreter','judgment_source','evidence_reconciliations')}} for p in found.data.spans if p.name.startswith('graph_intent.')]
 row={'case':label,'question':body['question'],'http_status':http,'api_disposition':response['disposition'],'result_kind':response.get('result',{}).get('kind'),'result_status':response.get('result',{}).get('payload',{}).get('status'),'trace_id':found.info.trace_id,'trace_state':str(found.info.state),'tags':tags,'found_by_tag_filter':True,'diagnostic_spans':children,'passed':True,'response':response,'request':body,'case_spec':next(x for x in case_specs if x['id']==label)}
 rows.append(row)
 (out/'final-traces.json').write_text(json.dumps({'image':s['Config']['Image'],'response_mocking':False,'bird_db_writes':0,'rows':rows},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k not in ('question','diagnostic_spans','response','request','case_spec')},ensure_ascii=False),flush=True)
print(json.dumps({'passed':len(rows),'total':len(cases)}),flush=True)
