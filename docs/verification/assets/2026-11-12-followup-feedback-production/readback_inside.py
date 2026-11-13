"""Read exact browser trace IDs; tag only these automated acceptance traces."""
import json,os,time
from pathlib import Path
os.environ.setdefault('MLFLOW_HTTP_REQUEST_MAX_RETRIES','2');os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT','10')
import mlflow
from robingraph.tracing import redact
spec=json.loads(Path('/tmp/rg213-rg603-browser-results.json').read_text())
assert spec['origin']=='https://robingraph.dove-nest.com' and spec['not_human_gold'] and spec['automated_verification']
assert os.environ['ROBINGRAPH_DEPLOY_TARGET']=='prod' and os.environ['MLFLOW_EXPERIMENT_ID']=='50'
expected={v['trace_id']:v for v in spec['votes']};rows=[]
assert len(expected)==3 and len(spec['rows'])==12
ids=[r['trace_id'] for r in spec['rows']];assert len(ids)==len(set(ids))
def masks(value):
 if isinstance(value,dict):
  for key,item in value.items():
   if key=='followup_context':assert item in (None,'[redacted]'),'Unmasked followup capability'
   else:masks(item)
 elif isinstance(value,list):
  for item in value:masks(item)
for result in spec['rows']:
 trace=None
 for attempt in range(8):
  trace=mlflow.get_trace(result['trace_id'],silent=True)
  if trace is not None and any(s.name=='POST /v1/chat' and s.parent_id is None for s in trace.data.spans):break
  time.sleep(1)
 assert trace is not None,'Trace missing'
 assert str(trace.info.experiment_id)=='50','Wrong experiment'
 roots=[s for s in trace.data.spans if s.parent_id is None];assert len(roots)==1 and roots[0].name=='POST /v1/chat'
 root=roots[0];assert root.inputs['request']['question']==result['request']['question']
 assert root.outputs==redact(result['response']),'Trace response mismatch for '+result['label']
 for span in trace.data.spans:masks(span.inputs);masks(span.outputs)
 assessments=[a for a in trace.info.assessments if a.name=='user_feedback' and a.source.source_type=='HUMAN' and a.source.source_id=='robingraph-web']
 vote=expected.get(result['trace_id'])
 if vote:
  assert len(assessments)==1 and assessments[0].feedback.value==vote['rating'],'Assessment mismatch'
 else:assert not assessments,'Unexpected assessment on non-voted test trace'
 context={k:v for span in trace.data.spans for k,v in span.attributes.items() if k.startswith('graph_followup.')}
 followup=result['response'].get('followup')
 if followup:
  assert context.get('graph_followup.status')==followup['status'],'Followup trace status mismatch'
  if followup.get('reason'):assert context.get('graph_followup.reason')==followup['reason']
 for key,value in {'validation_phase':'production_followup_feedback_acceptance','automated_test_feedback':'true','verification_run':spec['run_id']}.items():mlflow.set_trace_tag(trace.info.trace_id,key,value)
 verified=mlflow.get_trace(trace.info.trace_id,silent=True)
 assert verified.info.tags.get('verification_run')==spec['run_id']
 rows.append({'label':result['label'],'trace_id':trace.info.trace_id,'experiment_id':'50','question':result['request']['question'],'root_request_matches':True,'root_output_matches':True,'tokens_masked':True,'followup_status':followup.get('status') if followup else None,'followup_reason':followup.get('reason') if followup else None,'followup_trace_attributes_match':True,'rating':vote['rating'] if vote else None,'assessment_id':assessments[0].assessment_id if assessments else None,'matching_assessments':len(assessments),'verification_tag_readback':True})
print(json.dumps({'passed':True,'run_id':spec['run_id'],'experiment_id':'50','experiment_name':'robingraph-prod','rows':rows,'trace_count':len(rows),'assessment_count':sum(r['matching_assessments'] for r in rows),'automated_feedback_not_human_gold':True,'new_chat_requests_during_readback':0,'new_feedback_posts_during_readback':0,'writes_only_test_trace_tags':True},ensure_ascii=False))
