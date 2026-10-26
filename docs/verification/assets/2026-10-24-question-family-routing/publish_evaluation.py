"""Append a versioned evaluation run to TEST MLflow; no trace deletion or runtime changes."""
import os,json,subprocess,hashlib
from pathlib import Path
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex');out=root/'docs/verification/assets/2026-10-24-question-family-routing';data=root/'data/eval/graph_questions/question-families-v1'
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(v.split('=',1) for v in s['Config']['Env']);assert env['ROBINGRAPH_DEPLOY_TARGET']=='test'
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
import mlflow
mlflow.set_experiment(experiment_id='33')
with mlflow.start_run(run_name='RG-212-question-families-v1-first-attempt') as run:
 mlflow.set_tags({'project':'RobinGraph','task':'RG-212','environment':'test','evaluation_type':'question_family_first_attempt','gold_human_reviewed':'false','production_changed':'false'})
 mlflow.log_params({'example_pool_size':13,'tuning_groups':2,'holdout_groups':6,'test_image':s['Config']['Image'],'holdout_sha256':hashlib.sha256((data/'holdout.json').read_bytes()).hexdigest()})
 for split in ('tuning','holdout'):
  score=json.loads((out/f'{split}-score.json').read_text())
  for k,v in score['case_counts'].items():mlflow.log_metric(split+'_cases_'+k,v)
  for k,v in score['group_counts'].items():mlflow.log_metric(split+'_groups_'+k,v)
  for k,v in score['classifications'].items():mlflow.log_metric(split+'_'+k,v)
  mlflow.log_artifact(str(data/f'{split}.json'),'datasets')
  mlflow.log_artifact(str(out/f'{split}-score.json'),'evaluation')
  mlflow.log_artifact(str(out/f'{split}-traces.json'),'same-request-evidence')
 for name in ('manifest.json','validation.json'):mlflow.log_artifact(str(data/name),'datasets')
 mlflow.log_artifact(str(out/'code-freeze.json'),'evaluation')
 mlflow.log_artifact(str(root/'scripts/evaluate_graph_question_families.py'),'evaluator')
 runid=run.info.run_id
from mlflow import MlflowClient
client=MlflowClient();record=client.get_run(runid)
artifacts={folder:[a.path for a in client.list_artifacts(runid,folder)] for folder in ('datasets','evaluation','same-request-evidence','evaluator')}
receipt={'run_id':runid,'experiment_id':'33','url':f'https://mlflow.dove-nest.com/#/experiments/33/runs/{runid}','status':record.info.status,'metrics':record.data.metrics,'artifacts_read_back':artifacts,'deleted_traces':0}
(out/'mlflow-evaluation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
