"""Append final independent verification and reviewed docs to the existing evaluation run."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

root = Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
out = root / 'docs/verification/assets/2026-10-26-record-query-followup'
state = json.loads(subprocess.check_output(['docker', '--context', 'orbstack', 'inspect', 'robingraph-api-test']))[0]
env = dict(value.split('=', 1) for value in state['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET'] == 'test'
for key, value in env.items():
    if key.startswith('MLFLOW_'):
        os.environ[key] = value
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30', MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/') == 'https://mlflow.dove-nest.com'
from mlflow import MlflowClient

client = MlflowClient()
run_id = json.loads((out / 'mlflow-evaluation.json').read_text())['run_id']
assert client.get_run(run_id).info.status == 'FINISHED'
paths = [out / name for name in (
    'independent-final-metrics.json', 'independent-port-recovery-verification.json',
    'independent-source-review.json', 'final-runtime-check.json', 'evaluation-context.json',
    'root-readback-score-provenance.json', 'writer-vault-sync.json',
    'regression-score.json', 'followup-score.json', 'fresh-score.json', 'recheck-score.json')]
paths.append(root / 'docs/work-log/2026-10-26-record-query-followup.md')
assert all(path.is_file() for path in paths)
receipt = []
with tempfile.TemporaryDirectory(prefix='rg-final-readback-') as folder:
    for path in paths:
        client.log_artifact(run_id, str(path), 'final-readback')
        remote = Path(client.download_artifacts(run_id, 'final-readback/' + path.name, folder))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(remote.read_bytes()).hexdigest() == digest
        receipt.append({'artifact': 'final-readback/' + path.name, 'sha256': digest, 'readback_matches': True})
client.set_tag(run_id, 'fresh8_group_design', 'equivalent_pairs_only_no_contrast')
client.set_tag(run_id, 'first_blind8', '5/8')
client.set_tag(run_id, 'feedback_recheck8', '8/8')
client.set_tag(run_id, 'RG212_status', 'in_progress')
assert client.get_run(run_id).info.status == 'FINISHED'
(out / 'mlflow-final-readback.json').write_text(json.dumps({'run_id': run_id,
    'status': 'FINISHED', 'artifacts': receipt, 'new_chat_requests': 0, 'deleted_traces': 0}, indent=2) + '\n')
print(json.dumps({'run_id': run_id, 'readback_verified_artifacts': len(receipt), 'new_chat_requests': 0}))
