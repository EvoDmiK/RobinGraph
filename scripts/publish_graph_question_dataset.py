"""Package existing TEST questions; --publish registers them in MLflow without rerunning tests."""
import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/eval/graph_questions/taxonomic-regression-v1'
SOURCES = [
    ('taxonomic_matrix', '2026-10-22-taxonomic-coverage/independent-cases.json',
     '2026-10-22-taxonomic-coverage/independent-api-broad-final.json', 'template_generated'),
    ('natural_language', '2026-10-22-taxonomic-coverage/natural/independent-cases.json',
     '2026-10-22-taxonomic-coverage/natural/independent-api-natural-public-final.json', 'agent_authored'),
    ('prior_regression', '2026-10-22-taxonomic-trait-generalization/independent-cases.json',
     '2026-10-22-taxonomic-trait-generalization/independent-api-public.json', 'agent_authored'),
]
ASSETS = ROOT / 'docs/verification/assets'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records, observations, sources = [], [], []
    for suite, cases_path, results_path, origin in SOURCES:
        source, results = ASSETS / cases_path, ASSETS / results_path
        cases = json.loads(source.read_text())['cases']
        receipt = json.loads(results.read_text())
        actual = {row['case']['id']: row for row in receipt['rows']}
        assert len(actual) == len(cases) and receipt['passed'] == len(cases)
        sources.append(dict(suite=suite, cases_path=str(source.relative_to(ROOT)),
                            cases_sha256=sha(source), results_path=str(results.relative_to(ROOT)),
                            results_sha256=sha(results), count=len(cases)))
        for case in cases:
            question = case['question']
            expectations = {key: case[key] for key in ('taxon', 'rank', 'conditions', 'outcome')}
            records.append(dict(inputs={'question': question}, expectations=expectations,
                                tags=dict(case_id=case['id'], suite=suite, origin=origin,
                                          human_reviewed='false', evaluation_role='regression',
                                          implementation_feedback_exposed='true',
                                          source_path=str(source.relative_to(ROOT)))))
            row = actual[case['id']]
            assert row['case']['question'] == question and not row['errors']
            body = row['response']; payload = body['result'].get('payload', {})
            observations.append(dict(case_id=case['id'], suite=suite, question=question,
                                     response_status=payload.get('status'), disposition=body['disposition'],
                                     coverage=payload.get('coverage'), passed=not row['errors'],
                                     result_source=str(results.relative_to(ROOT))))
    assert len(records) == 496 and len({r['inputs']['question'] for r in records}) == 496
    assert Counter(r['tags']['suite'] for r in records) == {
        'taxonomic_matrix': 432, 'natural_language': 20, 'prior_regression': 44}
    for filename, rows in [('questions.jsonl', records), ('observations.jsonl', observations)]:
        (OUTPUT / filename).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))
    with (OUTPUT / 'questions.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=['case_id', 'suite', 'question', 'taxon', 'rank',
                                                   'conditions', 'outcome', 'origin', 'human_reviewed'])
        writer.writeheader()
        for record in records:
            e, t = record['expectations'], record['tags']
            writer.writerow(dict(case_id=t['case_id'], suite=t['suite'], question=record['inputs']['question'],
                                 taxon=e['taxon'], rank=e['rank'], conditions=json.dumps(e['conditions'], ensure_ascii=False),
                                 outcome=e['outcome'], origin=t['origin'], human_reviewed=t['human_reviewed']))
    manifest = dict(name='robingraph-taxonomic-regression-v1', version='2026-10-22-v1',
                    records=len(records), suites=dict(Counter(r['tags']['suite'] for r in records)),
                    ranks=dict(Counter(str(r['expectations']['rank']) for r in records)),
                    trait_counts=dict(Counter(c['trait_name'] for r in records for c in r['expectations']['conditions'])),
                    sources=sources, human_reviewed=False, evaluation_role='regression',
                    limitations=['Previously exposed during implementation feedback; not an unseen holdout.',
                                 '432 matrix questions use reviewed fixed phrases, not independent natural language.',
                                 'Agent expectations are not human-reviewed gold. Observations are stored separately.',
                                 'No tests rerun by this upload; observed results reference prior TEST receipts.',
                                 'Query outcome allows answer, empty, or insufficient_data depending on direct evidence.'],
                    files={name:sha(OUTPUT/name) for name in ('questions.jsonl','questions.csv','observations.jsonl')})
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    assert len(list(csv.DictReader((OUTPUT/'questions.csv').open(encoding='utf-8-sig')))) == len(records)
    return records, manifest


def publish(records, manifest, env_file):
    if env_file:
        from dotenv import dotenv_values
        for key, value in dotenv_values(env_file).items():
            if key.startswith('MLFLOW_') and value is not None:
                os.environ[key] = value
    os.environ['MLFLOW_HTTP_REQUEST_TIMEOUT'] = '30'
    os.environ['MLFLOW_HTTP_REQUEST_MAX_RETRIES'] = '0'
    import mlflow
    from mlflow import MlflowClient
    from mlflow.genai.datasets import create_dataset, get_dataset, search_datasets
    assert mlflow.get_tracking_uri().rstrip('/') == 'https://mlflow.dove-nest.com'
    client = MlflowClient()
    experiment = client.get_experiment_by_name('robingraph-test')
    assert experiment and experiment.lifecycle_stage == 'active'
    digest = manifest['files']['questions.jsonl']
    name = manifest['name']+'-'+digest[:12]
    existing = search_datasets(experiment_ids=[experiment.experiment_id], filter_string=f"name = '{name}'")
    assert len(existing) <= 1
    dataset = existing[0] if existing else create_dataset(name=name, experiment_id=experiment.experiment_id,
        tags={'project':'RobinGraph','version':manifest['version'],'human_reviewed':'false',
              'evaluation_role':'regression','content_sha256':digest})
    dataset.merge_records(records)
    reread = get_dataset(dataset_id=dataset.dataset_id).to_df()
    actual = {row['inputs']['question']:row['expectations'] for row in reread.to_dict('records')}
    expected = {row['inputs']['question']:row['expectations'] for row in records}
    assert actual == expected, 'Server dataset readback differs from inputs/expectations'
    with mlflow.start_run(experiment_id=experiment.experiment_id, run_name=name+'-publish',
                          tags={'dataset_id':dataset.dataset_id,'dataset_sha256':digest,
                                'purpose':'dataset-publication','human_reviewed':'false',
                                'tests_rerun':'false','production_changed':'false'}) as run:
        for suite, count in manifest['suites'].items():
            mlflow.log_metric('records_'+suite, count)
        mlflow.log_metric('records_total', len(records))
        for filename in (*manifest['files'], 'manifest.json'):
            mlflow.log_artifact(str(OUTPUT/filename), artifact_path='dataset')
        for filename in (*manifest['files'], 'manifest.json'):
            downloaded = Path(client.download_artifacts(run.info.run_id, 'dataset/'+filename))
            assert sha(downloaded) == sha(OUTPUT/filename), 'Artifact readback digest mismatch'
        receipt = dict(tracking_uri=mlflow.get_tracking_uri(), experiment_id=experiment.experiment_id,
                       dataset_name=name, dataset_id=dataset.dataset_id, records=len(reread),
                       run_id=run.info.run_id, content_sha256=digest, native_readback_verified=True,
                       artifact_readback_verified=True, human_reviewed=False, tests_rerun=False,
                       run_url=f'https://mlflow.dove-nest.com/#/experiments/{experiment.experiment_id}/runs/{run.info.run_id}')
        (OUTPUT/'publish-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
        mlflow.log_artifact(str(OUTPUT/'publish-receipt.json'), artifact_path='dataset')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--env-file',type=Path)
    args=parser.parse_args()
    records,manifest=package()
    if args.publish:
        publish(records,manifest,args.env_file)
    else:
        print(json.dumps({'records':len(records),'suites':manifest['suites'],'output':str(OUTPUT)},ensure_ascii=False))
