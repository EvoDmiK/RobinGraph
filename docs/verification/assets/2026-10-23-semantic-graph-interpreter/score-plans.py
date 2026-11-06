"""Independent plan scorer; reads evaluation artifacts and taxonomy only."""
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATALOG = BASE.parent / '2026-10-23-diet-display-alias/inventory.json'
taxa = json.loads(CATALOG.read_text())['taxa']
aliases = {}
for taxon in taxa:
    for name in (taxon.get('korean_name'), taxon.get('scientific_name')):
        if name:
            aliases.setdefault(name.casefold().strip(), set()).add((taxon['scientific_name'], taxon['rank']))


def canonical(name):
    if name is None:
        return None
    matches = aliases.get(name.casefold().strip(), set())
    return next(iter(matches)) if len(matches) == 1 else ('UNRESOLVED_OR_AMBIGUOUS', name)


def conditions(items):
    # Preserve every semantic field, including unknown non-null fields. Ordering
    # is immaterial for AND, while duplicate conditions remain observable.
    normalized = []
    for item in items or []:
        item = {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                for k, v in item.items() if v is not None}
        normalized.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
    return Counter(normalized)


def difference(errors, field, expected, actual):
    if expected != actual:
        errors.append({'field': field, 'expected': expected, 'actual': actual})


def score(case, result):
    if not isinstance(result, dict) or result.get('error') or result.get('exception'):
        return {'status': 'exception', 'errors': [result], 'execution_scope': 'execution unknown; exception is not evidence of execution'}
    expected = case['expected']
    parsed = result.get('parsed')
    errors = []
    if 'preserve' in expected:
        return {'status': 'needs_api_verification', 'errors': [],
                'reason': '일반 응답 보존은 실제 API 응답 비교가 필요함',
                'observed_gate': result.get('gate'), 'observed_parsed': parsed}
    if 'expected_hold' in expected:
        if parsed is not None:
            errors.append({'field': 'parsed', 'expected': None, 'actual': parsed})
        if result.get('gate') not in ('clarify', 'abstain', 'hold', 'unsupported', 'reject'):
            errors.append({'field': 'gate', 'expected': 'explicit non-executing hold', 'actual': result.get('gate')})
        for key in ('executed', 'execution', 'execution_result', 'query_result'):
            if result.get(key):
                errors.append({'field': key, 'expected': 'no execution', 'actual': result[key]})
        return {'status': 'fail' if errors else 'pass', 'errors': errors,
                'execution_scope': 'plan artifact only; actual API/DB execution not observed'}
    difference(errors, 'gate', 'answer', result.get('gate'))
    if not isinstance(parsed, dict):
        errors.append({'field': 'parsed', 'expected': expected, 'actual': parsed})
        return {'status': 'fail', 'errors': errors}
    if expected['kind'] == 'taxon_traits':
        difference(errors, 'kind', 'taxon_traits', parsed.get('kind'))
        target = canonical(expected.get('taxon_name'))
        names = parsed.get('names') or []
        rank_name = parsed.get('rank_name')
        actual_targets = ([rank_name] if rank_name else []) + names
        difference(errors, 'taxon_scope', [] if target is None else [target],
                   [canonical(n) for n in actual_targets])
        if target is not None:
            difference(errors, 'rank', expected.get('rank', expected.get('taxon_rank')), target[1])
        wanted, actual = conditions(expected.get('conditions')), conditions(parsed.get('conditions'))
        if wanted != actual:
            errors.append({'field': 'conditions', 'missing': list((wanted-actual).elements()),
                           'extra': list((actual-wanted).elements())})
        for key in ('habitat', 'criterion', 'group'):
            if parsed.get(key) is not None:
                errors.append({'field': key, 'expected': None, 'actual': parsed[key]})
    else:
        habitat = expected.get('habitat')
        difference(errors, 'kind', 'habitat_shared_diet' if habitat else 'shared_diet', parsed.get('kind'))
        difference(errors, 'reference_taxon', [canonical(expected['reference_taxon_name'])],
                   [canonical(n) for n in parsed.get('names', [])])
        difference(errors, 'habitat', habitat, parsed.get('habitat'))
        difference(errors, 'conditions', {}, dict(conditions(parsed.get('conditions'))))
        for key in ('rank_name', 'criterion', 'group'):
            if parsed.get(key) is not None:
                errors.append({'field': key, 'expected': None, 'actual': parsed[key]})
        # shared_diet kinds encode trophic_niche and exclusion in GraphQuestion;
        # their actual executor behavior still requires API/DB validation.
        if expected.get('share_basis') != 'trophic_niche' or expected.get('exclude_reference') is not True:
            errors.append({'field': 'expected_relation_contract', 'actual': expected})
    return {'status': 'fail' if errors else 'pass', 'errors': errors}


def main():
    source = BASE / 'final-plans.json'
    if not source.exists():
        print('final-plans.json not present; scorer ready')
        return
    data = json.loads(source.read_text())
    cases = json.loads((BASE / 'final-independent-cases.json').read_text())['cases']
    by_id = {r['case']['id']: r for r in data['rows']}
    rows = []
    for case in cases:
        row = by_id.get(case['id'])
        verdict = ({'status': 'exception', 'errors': [row.get('error') or row.get('exception')], 'execution_scope': 'unknown'} if row.get('error') or row.get('exception') else score(case, row.get('result'))) if row else {'status': 'fail', 'errors': [{'field': 'row', 'expected': 'present', 'actual': 'missing'}]}
        rows.append({'id': case['id'], 'category': case['category'], **verdict})
    supported = [r for r in rows if r['category'] == 'supported']
    hold = [r for r in rows if r['category'] == 'hold']
    out = {'source': source.name, 'primary_metric': 'supported_plan_exact_semantics',
           'supported_pass': sum(r['status']=='pass' for r in supported), 'supported_total': len(supported),
           'hold_pass': sum(r['status']=='pass' for r in hold), 'hold_total': len(hold),
           'preserve_needs_api_verification': sum(r['status']=='needs_api_verification' for r in rows),
           'limitations': ['No actual API/DB execution is established by plan artifacts.',
                          'shared_diet/habitat_shared_diet map to trophic_niche equality excluding reference; executor semantics require separate verification.'],
           'unexpected_ids': sorted(set(by_id)-{c['id'] for c in cases}), 'rows': rows}
    (BASE / 'final-score.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','limitations')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
