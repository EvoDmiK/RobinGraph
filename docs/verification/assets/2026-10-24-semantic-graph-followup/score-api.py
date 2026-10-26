"""Artifact-only API audit. Never calls the API or database."""
import argparse
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

BASE = Path(os.environ.get("RG212_SCORE_ASSET_DIR", Path(__file__).resolve().parent))
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


def relation_execution(case, payload, requested_scope="all"):
    """Inspect same-request executor metadata; never infer it from a separate plan."""
    summary = payload.get("execution_summary")
    if summary is None:
        return False, [], ["Same-request execution_summary missing; returned paths do not prove complete query scope."]
    if not isinstance(summary, dict):
        return False, ["execution_summary must be an object"], []
    expected = case["expected"]
    canonical = plan.canonical(expected["reference_taxon_name"])
    catalog = json.loads(plan.CATALOG.read_text())
    matches = [t for t in catalog["taxa"] if (t["scientific_name"], t["rank"]) == canonical]
    if len(matches) != 1:
        return False, [], ["Independent reference taxon catalog identity unavailable."]
    taxon = matches[0]
    wanted = {
        "kind": "habitat_shared_diet" if expected.get("habitat") else "shared_diet",
        "target_id": taxon["id"], "reference_name": taxon["scientific_name"],
        "species_scope": requested_scope, "share_basis": expected["share_basis"],
        "match": "same", "exclude_reference": expected["exclude_reference"],
        "habitat": expected.get("habitat"),
        "dataset_id": "avonet:figshare-article-16586228-v7:file-34480856",
        "release": "figshare-article-16586228-v7:file-34480856",
        "concept_set_id": catalog["concept_set_id"], "taxonomy_release": catalog["taxonomy_release"],
    }
    errors, limits = [], []
    for field, value in wanted.items():
        if field not in summary:
            limits.append("execution_summary field missing: " + field)
        elif summary[field] != value or (field == "exclude_reference" and summary[field] is not True):
            errors.append({"execution_field": field, "expected": value, "actual": summary[field]})
    allowed = set(wanted) | {"niche_value"}
    for field in set(summary) - allowed:
        errors.append({"unexpected_execution_field": field, "actual": summary[field]})
    niche = summary.get("niche_value")
    if "niche_value" not in summary:
        limits.append("execution_summary field missing: niche_value")
    elif not isinstance(niche, str) or not niche:
        errors.append("execution_summary niche_value must be a nonempty source category")
    target = payload.get("taxon") or {}
    if target.get("taxon_id") != taxon["id"] or target.get("scientific_name") != taxon["scientific_name"]:
        errors.append("payload target disagrees with independently resolved reference")
    def has_path(paths, field, value):
        return any("/files/34480856#" in p.get("source_url", "")
                   and ("field=" + field) == p.get("source_url", "").split("&")[-1]
                   and ("(" + value + ")") in p.get("text", "") for p in paths)
    if isinstance(niche, str) and niche:
        if not has_path(payload.get("paths", []), "Trophic.Niche", niche):
            errors.append("reference niche source path disagrees with executed niche")
        for item in payload.get("items", []):
            item_taxon = item.get("taxon") or {}
            if item_taxon.get("taxon_id") == taxon["id"]:
                errors.append("reference taxon included in peer results")
            if not has_path(item.get("paths", []), "Trophic.Niche", niche):
                errors.append("peer dietary source path missing or disagrees with executed niche")
            if expected.get("habitat") and not has_path(item.get("paths", []), "Habitat", expected["habitat"]):
                errors.append("peer habitat source path missing or disagrees with requested habitat")
    return not errors and not limits, errors, limits


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
    if expected["kind"] == "relation":
        exact_api_plan, execution_errors, execution_limits = relation_execution(
            case, payload, (row.get("request") or {}).get("species_scope", "all"))
        errors.extend(execution_errors)
        limits.extend(execution_limits)
    elif isinstance(parsed, dict):
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent / 'api-score.json')
    args = parser.parse_args()
    active = json.loads(args.active.read_text()) if args.active else load('api-active.json')
    if active is None:
        print('api-active.json not present; scorer ready')
        return
    cases = load('final-independent-cases.json')['cases']
    api_rows = {r.get('case',{}).get('id'): r for r in active['rows']}
    plan_rows = {r['case']['id']: r for r in (load('final-plans.json') or {}).get('rows',[])}
    baseline_data = json.loads(args.baseline.read_text()) if args.baseline else load('api-shadow.json')
    shadow = {r.get('case',{}).get('id'): r for r in (baseline_data or {}).get('rows',[])}
    rows = [{'id': c['id'],'category': c['category'], **audit(c,api_rows.get(c['id']),plan_rows.get(c['id']),shadow.get(c['id']))} for c in cases]
    out = {'evaluation_type': 'feedback-exposed regression', 'source': str(args.active) if args.active else str(BASE / 'api-active.json'),
           'counts': {category: dict(Counter(r['status'] for r in rows if r['category']==category)) for category in ('supported','hold','preserve')},
           'limits': ['Actual returned taxa and source records are not re-queried against DB.',
                      'No missing response kind or absent executed plan is automatically counted as supported success.'], 'rows': rows}
    args.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out['counts'],ensure_ascii=False))


if __name__ == '__main__': main()
