"""Evaluate the immutable published regression dataset against the deployed TEST API."""
import argparse
import copy
import hashlib
import json
import os
import statistics
import subprocess
import time
from threading import Lock
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/eval/graph_questions/taxonomic-regression-v1'
BASE = 'https://robingraph-test.dove-nest.com'


def condition(value, expected=False):
    op, v, threshold = value['op'], value.get('value'), value.get('threshold')
    if expected and op.startswith('share_'):
        v, threshold = next(iter(v.items()))
    elif expected and op in ('gte', 'lte', 'gt', 'lt'):
        op, v, threshold = 'num_'+op, None, v
    return value['trait_name'], op, v, threshold, value.get('unit')


def contract(case, response):
    if not response or 'result' not in response:
        return ['request_or_response_error']
    e = case['expectations']; p = response['result'].get('payload', {})
    status = p.get('status'); errors = []
    if e['outcome'] == 'hold':
        if response.get('disposition') != 'clarify' and status != 'insufficient_data':
            errors.append('unsafe_execution_of_held_condition')
        if status == 'answer':
            errors.append('held_condition_answered')
    elif e['outcome'] == 'insufficient':
        if status != 'insufficient_data':
            errors.append('expected_explicit_insufficient')
    else:
        if response['result'].get('kind') != 'graph_query' or status not in ('answer', 'empty', 'insufficient_data'):
            errors.append('supported_query_not_executed')
        taxon = p.get('taxon')
        if e['taxon'] and (not taxon or (taxon.get('rank'), taxon.get('scientific_name')) != (e['rank'], e['taxon'])):
            errors.append('taxon_scope_mismatch')
        if e['taxon'] is None and taxon is not None:
            errors.append('catalog_scope_changed')
        if sorted(map(condition, p.get('conditions', [])), key=repr) != sorted(
                (condition(c, True) for c in e['conditions']), key=repr):
            errors.append('original_conditions_changed_or_lost')
        if e['outcome'] == 'empty' and status != 'empty':
            errors.append('expected_empty_not_no_data')
    if case['tags']['case_id'] == 'IT-001' and (status != 'answer' or not p.get('items')):
        errors.append('original_user_failure_not_fixed')
    if e['rank'] == 'subspecies' and e['outcome'] == 'insufficient':
        if '아종' not in p.get('text', '') or '부모 종' not in p.get('text', ''):
            errors.append('subspecies_limit_not_explained')
    return errors


def fingerprint(response):
    p = response.get('result', {}).get('payload', {})
    return dict(response_status=p.get('status'), disposition=response.get('disposition'), coverage=p.get('coverage'))


def image():
    d = json.loads(subprocess.check_output(['docker', 'inspect', 'robingraph-api-test']))[0]
    assert 'ROBINGRAPH_DEPLOY_TARGET=test' in d['Config']['Env']
    assert 'ROBINGRAPH_GRAPH_INTENT_MODE=active' in d['Config']['Env']
    assert d['State']['Health']['Status'] == 'healthy'
    return dict(image=d['Config']['Image'], image_id=d['Image'], started_at=d['State']['StartedAt'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    for key, value in dotenv_values(args.env_file).items():
        if key.startswith('MLFLOW_') and value is not None:
            os.environ[key] = value
    os.environ.update(MLFLOW_GENAI_EVAL_MAX_WORKERS='4', MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS='4',
                      MLFLOW_HTTP_REQUEST_TIMEOUT='30', MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
    import mlflow
    from mlflow.genai.datasets import get_dataset
    from mlflow.genai.scorers import scorer
    assert mlflow.get_tracking_uri().rstrip('/') == 'https://mlflow.dove-nest.com'
    publication = json.loads((DATA/'publish-receipt.json').read_text())
    records = [json.loads(line) for line in (DATA/'questions.jsonl').read_text().splitlines()]
    assert hashlib.sha256((DATA/'questions.jsonl').read_bytes()).hexdigest() == publication['content_sha256']
    cases = {r['inputs']['question']:r for r in records}; assert len(cases) == 496
    manifest = json.loads((DATA/'manifest.json').read_text())
    # Validate the scorer against archived responses and a condition-deletion mutation before live calls.
    for source in manifest['sources']:
        old = json.loads((ROOT/source['results_path']).read_text())
        assert all(not contract(cases[row['case']['question']], row['response']) for row in old['rows'])
    good = next(row for row in old['rows'] if row['case']['id'] == 'IT-001')
    bad = copy.deepcopy(good['response']); bad['result']['payload']['conditions'] = []
    assert 'original_conditions_changed_or_lost' in contract(cases[good['case']['question']], bad)
    native = get_dataset(dataset_id=publication['dataset_id'])
    server = {r['inputs']['question']:r['expectations'] for r in native.to_df().to_dict('records')}
    assert server == {q:r['expectations'] for q,r in cases.items()}
    request = Request(BASE+'/health', headers={'User-Agent':'Mozilla/5.0 RobinGraph-Evaluation'})
    health = json.load(urlopen(request, timeout=20))
    assert health['deployment_target'] == 'test' and health['mode'] == 'neo4j'
    before = image()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'docs/verification/assets'/('2026-10-22-dataset-evaluation-'+stamp)
    out.mkdir(parents=True, exist_ok=False)
    baseline = {r['question']:r for r in map(json.loads,(DATA/'observations.jsonl').read_text().splitlines())}
    cache, rows = {}, []
    request_lock = Lock()

    @mlflow.trace(name='regression.predict')
    def predict(question: str) -> dict:
        with request_lock:
            if question in cache:
                return cache[question]  # MLflow's preflight can invoke the first input again.
            assert question in cases
            started = time.perf_counter(); response = None; error = None
            try:
                req = Request(BASE+'/v1/chat', data=json.dumps(dict(question=question, defer_enrichment=True,
                              defer_discovery=True)).encode(), headers={'Content-Type':'application/json',
                              'User-Agent':'Mozilla/5.0 RobinGraph-Evaluation'})
                response = json.load(urlopen(req, timeout=35))
            except Exception as exc:
                error = dict(type=type(exc).__name__, http_status=exc.code if isinstance(exc, HTTPError) else None)
            elapsed = round((time.perf_counter()-started)*1000, 3)
            errors = contract(cases[question], response)
            previous = {k:baseline[question].get(k) for k in ('response_status','disposition','coverage')}
            current = fingerprint(response or {})
            row = dict(case=cases[question], response=response, elapsed_ms=elapsed, request_error=error,
                       errors=errors, baseline=previous, current=current, baseline_changed=current != previous)
            rows.append(row)
            with (out/'results.jsonl').open('a') as stream:
                stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            cache[question] = dict(response=response, elapsed_ms=elapsed)
            if len(rows)%25 == 0:
                print(json.dumps({'completed':len(rows),'failed':sum(bool(r['errors']) for r in rows)}), flush=True)
            return cache[question]

    @scorer(name='regression_contract')
    def regression_contract(inputs: dict, outputs: dict, expectations: dict) -> bool:
        assert expectations['contract'] == cases[inputs['question']]['expectations']
        return not contract(cases[inputs['question']], outputs['response'])

    @scorer(name='baseline_consistent')
    def baseline_consistent(inputs: dict, outputs: dict) -> bool:
        old = {k:baseline[inputs['question']].get(k) for k in ('response_status','disposition','coverage')}
        return fingerprint(outputs['response'] or {}) == old

    @scorer(name='api_latency_ms', aggregations=['mean','median','p90'])
    def api_latency_ms(outputs: dict) -> float:
        return outputs['elapsed_ms']

    with mlflow.start_run(experiment_id='33', run_name='taxonomic-regression-496-'+stamp,
                         tags={'dataset_id':publication['dataset_id'], 'dataset_sha256':publication['content_sha256'],
                               'purpose':'live-test-regression-evaluation','human_reviewed':'false',
                               'evaluation_role':'regression','test_image':before['image'],
                               'production_changed':'false'}) as run:
        (out/'run.json').write_text(json.dumps(dict(run_id=run.info.run_id, target=BASE,
            dataset_id=publication['dataset_id'], before=before), indent=2)+'\n')
        # MLflow assessment values reject top-level None; preserve them inside the contract object.
        eval_data = native.to_df()
        eval_data['expectations'] = eval_data['expectations'].map(lambda e: {'contract': e})
        result = mlflow.genai.evaluate(data=eval_data, predict_fn=predict,
                                      scorers=[regression_contract, baseline_consistent, api_latency_ms])
        assert len(rows) == len(cases) and set(cache) == set(cases)
        assert image() == before, 'TEST app changed during evaluation'
        failures = [dict(case_id=r['case']['tags']['case_id'],question=r['case']['inputs']['question'],errors=r['errors'])
                    for r in rows if r['errors']]
        suites = {}
        for suite in manifest['suites']:
            selected = [r for r in rows if r['case']['tags']['suite'] == suite]
            suites[suite] = dict(count=len(selected), passed=sum(not r['errors'] for r in selected))
        summary = dict(run_id=run.info.run_id,dataset_id=publication['dataset_id'],count=len(rows),
            passed=len(rows)-len(failures),failures=failures,baseline_changed=sum(r['baseline_changed'] for r in rows),
            suites=suites,latency_ms=dict(mean=statistics.mean(r['elapsed_ms'] for r in rows),
                median=statistics.median(r['elapsed_ms'] for r in rows)),
            image=before,api_target=BASE,response_mocking=False,concurrency=1,mlflow_workers=4,
            new_db_oracle_run=False,human_reviewed=False,dataset_modified=False,production_changed=False,
            limitations=['Regression questions already exposed during implementation; not unseen accuracy.',
                         'Contract and prior coverage comparison; fresh biological evidence audit not performed.',
                         'Sequential API latency includes public network; not load-test or isolated Neo4j latency.'],
            run_url=f'https://mlflow.dove-nest.com/#/experiments/33/runs/{run.info.run_id}')
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        result.result_df.to_json(out/'mlflow-eval-results.json',orient='records',force_ascii=False)
        mlflow.log_metric('regression_pass_rate',summary['passed']/summary['count'])
        mlflow.log_metric('regression_failures',len(failures))
        mlflow.log_metric('baseline_changed_count',summary['baseline_changed'])
        for suite, counts in suites.items():
            mlflow.log_metric(suite+'_pass_rate',counts['passed']/counts['count'])
        mlflow.log_artifacts(str(out),artifact_path='regression')
        print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
