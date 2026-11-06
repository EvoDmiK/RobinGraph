"""Artifact-only API audit. Never calls the API or database."""
import importlib.util
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('plan_scorer', BASE / 'score-plans.py')
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


def load(name):
    path = BASE / name
    return json.loads(path.read_text()) if path.exists() else None


def fingerprint(response):
    return { 'selected_intent': response.get('selected_intent'),
             'disposition': response.get('disposition'),
             'kind': (response.get('result') or {}).get('kind') }


def audit(case, row, plan_row, baseline):
    errors, limits = [], []
    if not row:
        return {'status': 'missing', 'errors': ['API row missing']}
    response = row.get('response')
    if row.get('error') or not isinstance(response, dict):
        return {'status': 'exception', 'errors': [row.get('error') or 'response missing']}
    expected = case['expected']
    result = response.get('result') or {}
    payload = result.get('payload') or {}
    kind, status = result.get('kind'), payload.get('status')
    if case['category'] == 'preserve':
        if not baseline:
            return {'status': 'unverifiable', 'errors': ['matching shadow baseline missing']}
        before, after = fingerprint(baseline['response']), fingerprint(response)
        return {'status': 'pass' if before == after else 'fail', 'errors': [] if before == after else [{'expected': before, 'actual': after}]}
    if case['category'] == 'hold':
        if kind == 'graph_query' and (status == 'answer' or response.get('disposition') == 'answer'):
            errors.append('unsafe graph_query answer')
        if response.get('disposition') not in ('clarify', 'abstain'):
            errors.append('hold requires explicit clarify/abstain')
        return {'status': 'fail' if errors else 'pass', 'errors': errors,
                'limits': ['Response proves no graph answer; internal DB read execution is not observable.']}
    if kind != 'graph_query':
        errors.append({'expected_kind': 'graph_query', 'actual_kind': kind})
    if status not in ('answer', 'empty', 'insufficient_data'):
        errors.append({'unexpected_status': status})
    corroboration = None
    if plan_row and isinstance(plan_row.get('result'), dict):
        verdict = plan.score(case, plan_row['result'])
        if verdict['status'] != 'pass':
            corroboration = {'separate_provider_plan_mismatch': verdict}
    else:
        corroboration = 'matching separate semantic plan missing'
    # A separately sampled provider plan cannot establish what this API request
    # executed. Only an echoed query plan/conditions can close that gap exactly.
    parsed = payload.get('parsed') or payload.get('query_plan')
    exact_api_plan = False
    if isinstance(parsed, dict):
        verdict = plan.score(case, {'gate': 'answer', 'parsed': parsed})
        exact_api_plan = verdict['status'] == 'pass'
        if not exact_api_plan: errors.append({'api_plan_mismatch': verdict})
    elif expected['kind'] == 'taxon_traits' and 'conditions' in payload:
        actual_scope = payload.get('taxon') or {}
        name = actual_scope.get('scientific_name') or actual_scope.get('korean_name')
        exact_api_plan = (plan.canonical(name) == plan.canonical(expected.get('taxon_name')) and
                          plan.conditions([{k:v for k,v in c.items() if k in ('trait_name','op','value','threshold','unit','qualifier')} for c in payload['conditions']]) == plan.conditions(expected['conditions']))
        if not exact_api_plan: errors.append('API echoed scope/conditions mismatch')
    else:
        limits.append('API has no machine-readable complete executed scope/conditions; separate provider plan is corroboration only.')
    text = '\n'.join([payload.get('title',''), payload.get('text','')] +
                     [p.get('text','') for p in payload.get('paths',[])] +
                     [p.get('text','') for i in payload.get('items',[]) for p in i.get('paths',[])])
    if expected['kind'] == 'relation':
        reference = expected['reference_taxon_name']
        canonical = plan.canonical(reference)
        if reference not in text and canonical[0] not in text:
            errors.append('relation title/paths do not identify reference taxon')
        if not expected.get('habitat') and any(term in payload.get('title','') for term in ('숲','습지','하천','서식지')):
            errors.append('unexpected implicit habitat restriction in relation title')
        for item in payload.get('items',[]):
            taxon = item.get('taxon') or {}
            if plan.canonical(taxon.get('scientific_name') or taxon.get('korean_name')) == canonical:
                errors.append('reference taxon included among results')
        if status == 'answer' and payload.get('items'):
            for item in payload['items']:
                paths = json.dumps(item.get('paths',[]),ensure_ascii=False)
                if not any(term in paths for term in ('먹이','trophic_niche','생태')):
                    errors.append('relation item lacks dietary relation evidence path')
                    break
    return {'status': 'fail' if errors else ('pass' if exact_api_plan else 'unverifiable'),
            'errors': errors, 'limits': limits, 'observed': {'kind': kind,'status': status,'disposition': response.get('disposition')},
            'source_empty_allowed': status in ('empty','insufficient_data') and exact_api_plan,
            'raw_api_conditions': payload.get('conditions'), 'separate_plan_corroboration': corroboration}


def main():
    active = load('api-active.json')
    if active is None:
        print('api-active.json not present; scorer ready')
        return
    cases = load('final-independent-cases.json')['cases']
    api_rows = {r.get('case',{}).get('id'): r for r in active['rows']}
    plan_rows = {r['case']['id']: r for r in (load('final-plans.json') or {}).get('rows',[])}
    shadow = {r.get('case',{}).get('id'): r for r in (load('api-shadow.json') or {}).get('rows',[])}
    rows = [{'id': c['id'],'category': c['category'], **audit(c,api_rows.get(c['id']),plan_rows.get(c['id']),shadow.get(c['id']))} for c in cases]
    out = {'evaluation_type': 'feedback-exposed regression', 'source': 'api-active.json',
           'counts': {category: dict(Counter(r['status'] for r in rows if r['category']==category)) for category in ('supported','hold','preserve')},
           'limits': ['Actual returned taxa and source records are not re-queried against DB.',
                      'No missing response kind or absent executed plan is automatically counted as supported success.'], 'rows': rows}
    (BASE/'api-score.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out['counts'],ensure_ascii=False))


if __name__ == '__main__': main()
