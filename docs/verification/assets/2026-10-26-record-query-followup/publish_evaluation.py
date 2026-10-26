"""Append TEST regression and separately frozen fresh evaluation; keep all earlier evidence."""
import os, json, subprocess, hashlib
from pathlib import Path
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
out=root/'docs/verification/assets/2026-10-26-record-query-followup'
data=root/'data/eval/graph_questions/question-families-v6'
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(v.split('=',1) for v in s['Config']['Env']);assert env['ROBINGRAPH_DEPLOY_TARGET']=='test'
freeze=json.loads((out/'code-freeze.json').read_text());assert s['Config']['Image']==freeze['image']
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
import mlflow
from mlflow import MlflowClient
mlflow.set_experiment(experiment_id='33')
with mlflow.start_run(run_name='RG-212-record-query-followup-regression-and-fresh') as run:
 mlflow.set_tags({'project':'RobinGraph','task':'RG-212','environment':'test','evaluation_type':'feedback_regression_first_blind_and_exposed_recheck','gold_human_reviewed':'false','production_changed':'false','recheck8_feedback_exposed':'true'})
 mlflow.log_params({'test_image':s['Config']['Image'],'source_sha256':freeze['source_sha256'],'regression_cases':84,'fresh_cases':8,'feedback_cases':12,'fresh_sha256':hashlib.sha256((data/'holdout.json').read_bytes()).hexdigest()})
 first_freeze=json.loads((out/'phase3-first-evaluations/code-freeze.json').read_text())
 mlflow.log_params({'first_blind8_image':first_freeze['image'],'first_blind8_source_sha256':first_freeze['source_sha256']})
 for split,name in (('regression','regression.json'),('fresh','holdout.json'),('followup','feedback12.json'),('recheck','holdout.json')):
  score=json.loads((out/f'{split}-score.json').read_text())
  for k,v in score['case_counts'].items():mlflow.log_metric(split+'_cases_'+k,v)
  for k,v in score['group_counts'].items():mlflow.log_metric(split+'_groups_'+k,v)
  for k,v in score['classifications'].items():mlflow.log_metric(split+'_'+k,v)
  mlflow.log_artifact(str(data/name),'datasets')
  mlflow.log_artifact(str(out/f'{split}-score.json'),'evaluation')
  mlflow.log_artifact(str(out/f'{split}-traces.json'),'same-request-evidence')
 for name in ('manifest.json','validation.json'):mlflow.log_artifact(str(data/name),'datasets')
 for name in ('code-freeze.json','unit-full.log','independent-final-signoff.json','regression-root-verification.json','fresh-root-verification.json','health-final.json','final-runtime-check.json','resolved-four.json'):
  mlflow.log_artifact(str(out/name),'verification')
 for name in ('app-changes.patch','fruit-unit-initial.log','fruit-unit.log','final-guards.log','final-prior-guards.log','backend.patch','record-fragments.patch','record-coverage.patch','record-field-proof.patch','local-union-safety-finding.json','independent-union-safety-failure.log','field-proof-final-guards.log','field-proof-prior-guards.log','field-proof-permanent-tests.log'):
  mlflow.log_artifact(str(out/name),'implementation')
 mlflow.log_artifact(str(root/'scripts/evaluate_graph_question_families.py'),'evaluator')
 for extra in ('record-assignment.patch','record-assignment-results.json','record-assignment-unit.log','record-assignment-boundaries-initial.log','record-assignment-all-guards.log','independent-source-review.json'):
  if (out/extra).exists(): mlflow.log_artifact(str(out/extra),'implementation')
 for name in ('regression-score.json','regression-traces.json','code-freeze.json','independent-phase2-attempt1-signoff.json','family-comparison.json'):
  if (out/'phase2-attempt1'/name).exists(): mlflow.log_artifact(str(out/'phase2-attempt1'/name),'phase2-attempt1')
 for split in ('regression','fresh'):
  for suffix in ('score','traces'):
   mlflow.log_artifact(str(out/'phase2-attempt2'/f'{split}-{suffix}.json'),'phase2-attempt2')
 for name in ('code-freeze.json','regression-score.json','fresh-score.json','fresh-traces.json','manifest.json'):
  mlflow.log_artifact(str(out/'phase3-first-evaluations'/name),'phase3-first-evaluations')
 for name in ('gold-label-adjudication.json','adjudication-label-ambiguity-peer.json','followup-root-verification.json','recheck-root-verification.json'):
  if (out/name).exists(): mlflow.log_artifact(str(out/name),'verification')
 for name in ('evaluation-context.json','root-readback-score-provenance.json','port-proxy-recovery.json','independent-port-recovery-verification.json'):
  mlflow.log_artifact(str(out/name),'verification')
 for split in ('regression','fresh'):
  mlflow.log_artifact(str(root/'docs/verification/assets/2026-10-26-graph-condition-boundaries'/f'{split}-score.json'),'previous-evaluation')
 for split in ('regression','fresh'):
  for suffix in ('score','traces'):
   mlflow.log_artifact(str(out/'phase1-first-evaluations'/f'{split}-{suffix}.json'),'phase1-first-evaluations')
 for attempt in ('regression-attempt1','regression-attempt2'):
  for name in ('regression-score.json','regression-traces.json'):
   mlflow.log_artifact(str(out/attempt/name),'previous-feedback-attempt/'+attempt)
 runid=run.info.run_id
client=MlflowClient();record=client.get_run(runid)
receipt={'run_id':runid,'experiment_id':'33','url':f'https://mlflow.dove-nest.com/#/experiments/33/runs/{runid}','status':record.info.status,'metrics':record.data.metrics,'artifacts_read_back':{folder:[a.path for a in client.list_artifacts(runid,folder)] for folder in ('datasets','evaluation','same-request-evidence','verification','evaluator','implementation','previous-evaluation','previous-feedback-attempt','phase1-first-evaluations','phase2-attempt1','phase2-attempt2','phase3-first-evaluations')},'deleted_traces':0}
(out/'mlflow-evaluation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'url':receipt['url'],'status':receipt['status'],'metrics':receipt['metrics']}))
