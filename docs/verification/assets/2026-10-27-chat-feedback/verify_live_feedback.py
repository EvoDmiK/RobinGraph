"""Read actual TEST feedback by browser response trace ID; never re-post a rating."""
from pathlib import Path
import json, os, subprocess
from datetime import datetime
from robingraph.tracing import redact

out=Path(__file__).resolve().parent
state=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(item.split('=',1) for item in state['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='test' and env['MLFLOW_EXPERIMENT_ID']=='33'
for key,value in env.items():
    if key.startswith('MLFLOW_'):os.environ[key]=value
from mlflow import MlflowClient
client=MlflowClient(); assert client.get_experiment('33').name=='robingraph-test'
results=json.loads((out/'browser-results.json').read_text()); rows=[]
results['rows'].append(json.loads((out/'keyboard-results.json').read_text()))
for result in results['rows']:
    trace=client.get_trace(result['trace_id']); assert str(trace.info.experiment_id)=='33'
    roots=[s for s in trace.data.spans if s.name=='POST /v1/chat' and s.parent_id is None]
    assert len(roots)==1 and roots[0].inputs['request']['question']==result['question']
    assert roots[0].outputs==redact(result['response'])
    assessments=[a for a in trace.info.assessments if a.name=='user_feedback'
                 and a.source.source_type=='HUMAN' and a.source.source_id=='robingraph-web']
    assert len(assessments)==1 and assessments[0].feedback.value==result['rating']
    assessment=assessments[0]
    for key,value in {'validation_phase':'chat_feedback_acceptance','automated_test_feedback':'true'}.items():
        client.set_trace_tag(trace.info.trace_id,key,value)
    rows.append({'trace_id':trace.info.trace_id,'experiment_id':'33','question':result['question'],
        'rating':assessment.feedback.value,'assessment_id':assessment.assessment_id,
        'source_type':assessment.source.source_type,'source_id':assessment.source.source_id,
        'matching_assessments':len(assessments),'root_outputs_match':True,
        'response_reason':trace.info.tags.get('response_reason'),'failure_stage':trace.info.tags.get('failure_stage')})
# Preserve earlier development and harness feedback separately from final acceptance cases.
start=json.loads((out/'test-window.json').read_text())['since_ms']
prior=[]
for trace in client.search_traces(locations=['33'],filter_string=f'timestamp_ms >= {start-10000}',max_results=100,include_spans=True):
    if trace.info.trace_id in {r['trace_id'] for r in rows}:continue
    assessments=[a for a in trace.info.assessments if a.name=='user_feedback' and a.source.source_id=='robingraph-web']
    if assessments:
        roots=[s for s in trace.data.spans if s.name=='POST /v1/chat' and s.parent_id is None]
        prior.append({'trace_id':trace.info.trace_id,'question':roots[0].inputs['request']['question'],
                      'ratings':[a.feedback.value for a in assessments],'source':'prior_test_window_feedback_not_acceptance'})
(out/'assessment-readback.json').write_text(json.dumps({'rows':rows,'prior_test_window_records':prior,
    'new_chat_requests':0,'new_feedback_posts':0,'production_experiment_50_untouched':True,
    'automated_test_feedback_not_human_gold':True},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'matched':len(rows),'one_assessment_per_final_trace':True,'prior_test_window_records':len(prior),'experiment_id':'33'}))
