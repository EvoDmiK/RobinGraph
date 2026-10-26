"""Append fresh first-attempt TEST evaluation and read its MLflow artifacts back."""
import os, json, subprocess, hashlib
from pathlib import Path
root = Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
out = root / 'docs/verification/assets/2026-10-26-fresh-question-families'
data = root / 'data/eval/graph_questions/question-families-v2'
state = json.loads(subprocess.check_output(['docker', '--context', 'orbstack', 'inspect', 'robingraph-api-test']))[0]
env = dict(v.split('=', 1) for v in state['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET'] == 'test'
freeze = json.loads((out / 'code-freeze.json').read_text())
assert state['Image'] == freeze['image_id']
for key, value in env.items():
    if key.startswith('MLFLOW_'):
        os.environ[key] = value
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30', MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/') == 'https://mlflow.dove-nest.com'
import mlflow
from mlflow import MlflowClient
score = json.loads((out / 'holdout-score.json').read_text())
cases = json.loads((data / 'holdout.json').read_text())['cases']
mlflow.set_experiment(experiment_id='33')
with mlflow.start_run(run_name='RG-212-question-families-v2-fresh-first-attempt') as run:
    mlflow.set_tags({'project': 'RobinGraph', 'task': 'RG-212', 'environment': 'test',
                     'evaluation_type': 'fresh_question_family_first_attempt',
                     'gold_human_reviewed': 'false', 'implementation_changed': 'false',
                     'production_changed': 'false'})
    mlflow.log_params({'case_count': len(cases), 'family_count': len({c['semantic_group_id'] for c in cases}),
                       'test_image': state['Config']['Image'], 'source_sha256': freeze['source_sha256'],
                       'holdout_sha256': hashlib.sha256((data / 'holdout.json').read_bytes()).hexdigest(),
                       'scorer_sha256': hashlib.sha256((root / 'scripts/evaluate_graph_question_families.py').read_bytes()).hexdigest()})
    for key, value in score['case_counts'].items():
        mlflow.log_metric('holdout_cases_' + key, value)
    for key, value in score['group_counts'].items():
        mlflow.log_metric('holdout_groups_' + key, value)
    for key, value in score['classifications'].items():
        mlflow.log_metric('holdout_' + key, value)
    for name in ('holdout.json', 'manifest.json', 'validation.json'):
        mlflow.log_artifact(str(data / name), 'dataset')
    for name in ('holdout-score.json', 'code-freeze.json', 'dataset-freeze.json'):
        mlflow.log_artifact(str(out / name), 'evaluation')
    mlflow.log_artifact(str(out / 'holdout-traces.json'), 'same-request-evidence')
    mlflow.log_artifact(str(root / 'scripts/evaluate_graph_question_families.py'), 'evaluator')
    run_id = run.info.run_id
client = MlflowClient()
record = client.get_run(run_id)
receipt = {'run_id': run_id, 'experiment_id': '33', 'status': record.info.status,
           'url': f'https://mlflow.dove-nest.com/#/experiments/33/runs/{run_id}',
           'metrics': record.data.metrics,
           'artifacts_read_back': {folder: [a.path for a in client.list_artifacts(run_id, folder)]
                                  for folder in ('dataset', 'evaluation', 'same-request-evidence', 'evaluator')},
           'deleted_traces': 0}
(out / 'mlflow-evaluation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': receipt['status'], 'url': receipt['url'], 'metrics': receipt['metrics']}))
