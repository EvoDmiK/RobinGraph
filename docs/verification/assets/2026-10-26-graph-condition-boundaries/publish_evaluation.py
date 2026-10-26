"""Append TEST regression and separately frozen fresh evaluation; keep all earlier evidence."""
import os, json, subprocess, hashlib
from pathlib import Path
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
out=root/'docs/verification/assets/2026-10-26-graph-condition-boundaries'
data=root/'data/eval/graph_questions/question-families-v3'
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
with mlflow.start_run(run_name='RG-212-condition-boundary-fix-regression-and-fresh') as run:
 mlflow.set_tags({'project':'RobinGraph','task':'RG-212','environment':'test','evaluation_type':'feedback_regression_and_separate_fresh','gold_human_reviewed':'false','production_changed':'false'})
 mlflow.log_params({'test_image':s['Config']['Image'],'source_sha256':freeze['source_sha256'],'regression_cases':36,'fresh_cases':24,'fresh_sha256':hashlib.sha256((data/'holdout.json').read_bytes()).hexdigest()})
 for split,name in (('regression','regression.json'),('fresh','holdout.json')):
  score=json.loads((out/f'{split}-score.json').read_text())
  for k,v in score['case_counts'].items():mlflow.log_metric(split+'_cases_'+k,v)
  for k,v in score['group_counts'].items():mlflow.log_metric(split+'_groups_'+k,v)
  for k,v in score['classifications'].items():mlflow.log_metric(split+'_'+k,v)
  mlflow.log_artifact(str(data/name),'datasets')
  mlflow.log_artifact(str(out/f'{split}-score.json'),'evaluation')
  mlflow.log_artifact(str(out/f'{split}-traces.json'),'same-request-evidence')
 for name in ('manifest.json','validation.json'):mlflow.log_artifact(str(data/name),'datasets')
 for name in ('code-freeze.json','unit-full.log','unit-numeric-boundary-failure.log','unit-initial.log','predicate-denial-final-independent.log','regression-root-verification.json','fresh-root-verification.json','independent-predicate-denial-final-signoff.json','task-source-scope.json','predicate-denial-safety-finding.json','original-failures-comparison.json','health-final.json','final-runtime-check.json'):mlflow.log_artifact(str(out/name),'verification')
 mlflow.log_artifact(str(root/'scripts/evaluate_graph_question_families.py'),'evaluator')
 mlflow.log_artifact(str(root/'docs/verification/assets/2026-10-26-fresh-question-families/holdout-score.json'),'original-first-attempt')
 for attempt in ('regression-attempt1','regression-attempt2','regression-attempt3'):
  for name in ('regression-score.json','regression-traces.json'):
   mlflow.log_artifact(str(out/attempt/name),'previous-feedback-attempt/'+attempt)
 runid=run.info.run_id
client=MlflowClient();record=client.get_run(runid)
receipt={'run_id':runid,'experiment_id':'33','url':f'https://mlflow.dove-nest.com/#/experiments/33/runs/{runid}','status':record.info.status,'metrics':record.data.metrics,'artifacts_read_back':{folder:[a.path for a in client.list_artifacts(runid,folder)] for folder in ('datasets','evaluation','same-request-evidence','verification','evaluator','original-first-attempt','previous-feedback-attempt')},'deleted_traces':0}
(out/'mlflow-evaluation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'url':receipt['url'],'status':receipt['status'],'metrics':receipt['metrics']}))
