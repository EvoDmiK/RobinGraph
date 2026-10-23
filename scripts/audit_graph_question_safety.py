"""Strict reason audit of the hold/insufficient taxon-trait cases in an evaluation result file.

Reads root's evaluation ``results.jsonl`` (one row per question: ``case.tags.case_id``,
``case.expectations``, ``response``) or an older ``independent-api-*.json`` report (``rows`` with
``case.id``). It makes no API or DB call and never edits expectations. Each of the 18 non-executing
cases must be held for its documented reason (criteria taken from the real TEST responses of
2026-10-22): a passing status alone is not enough.

    python scripts/audit_graph_question_safety.py RESULTS [--out audit.json] [--selfcheck]

Exit code 1 when any case fails, a case is missing, or a self-check mutation is not caught.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

CLARIFY = ('CT-017', 'CT-018', 'CT-019', 'CT-020', 'IT-034', 'IT-035', 'IT-036', 'IT-037', 'IT-038', 'IT-039',
           'IT-040', 'IT-041')
AMBIGUOUS = ('IT-043', 'IT-044', 'CT-016')          # a name naming two taxa: never resolved, nothing queried
SUBSPECIES = ('CT-011', 'IT-011')                    # direct subspecies claims only, never the parent species
SPECIFIC_PLANT = ('IT-042',)
RULES = {**{i: 'clarify' for i in CLARIFY}, **{i: 'ambiguous_taxon' for i in AMBIGUOUS},
         **{i: 'subspecies_no_data' for i in SUBSPECIES}, **{i: 'specific_plant' for i in SPECIFIC_PLANT}}
SUBSPECIES_LIMIT = '아종 질문은 부모 종의 형질 자료로 대체하지 않습니다.'
PLANT_LIMIT = '특정 식물의 열매나 먹이 식물을 종 단위로 기록한 자료가 그래프에 없습니다.'


def load_rows(path):
    """(case_id, expectations, question, response) for every row of either result format."""
    text = Path(path).read_text(encoding='utf-8')
    try:
        whole = json.loads(text)
    except ValueError:
        whole = None   # JSON Lines
    if isinstance(whole, dict) and 'rows' in whole:
        rows = []
        for row in whole['rows']:
            case = row['case']
            expectations = {k: case.get(k) for k in ('taxon', 'rank', 'conditions', 'outcome')}
            rows.append((case['id'], expectations, case['question'], row.get('response')))
        return rows
    rows = []
    for line in text.splitlines():
        if line.strip():
            row = json.loads(line)
            case = row['case']
            rows.append((case['tags']['case_id'], case['expectations'], case['inputs']['question'], row.get('response')))
    return rows


def _expected_condition(condition):
    op, value, threshold = condition['op'], condition['value'], None
    if op.startswith('share_'):
        value, threshold = next(iter(value.items()))
    elif op in ('gte', 'lte', 'gt', 'lt'):
        op, threshold, value = 'num_' + op, value, None
    return condition['trait_name'], op, value, threshold, condition['unit']


def _actual_condition(condition):
    return (condition.get('trait_name'), condition.get('op'), condition.get('value'), condition.get('threshold'),
            condition.get('unit'))


def _graph_payload(response, errors):
    result = (response or {}).get('result') or {}
    if result.get('kind') != 'graph_query' or not isinstance(result.get('payload'), dict):
        errors.append('not_a_graph_query_payload')
        return {}
    payload = result['payload']
    if response.get('disposition') != 'abstain':
        errors.append('disposition_not_abstain')
    if payload.get('status') != 'insufficient_data':
        errors.append('status_not_insufficient_data')
    if payload.get('items') != []:
        errors.append('items_returned')
    if payload.get('has_more') is not False:
        errors.append('has_more_not_false')
    return payload


def audit_case(case_id, expectations, response):
    """Errors for one case; an empty list means it was held for its documented reason."""
    rule = RULES.get(case_id)
    errors = []
    if expectations.get('outcome') not in ('hold', 'insufficient'):
        errors.append('expectation_outcome_not_hold_or_insufficient')
    if not isinstance(response, dict):
        return rule, errors + ['no_response']
    if rule == 'clarify':
        result = response.get('result') or {}
        if response.get('disposition') != 'clarify' or result.get('kind') != 'clarify':
            errors.append('held_condition_executed_or_answered')
        if 'payload' in result:
            errors.append('graph_payload_present')
    elif rule == 'ambiguous_taxon':
        payload = _graph_payload(response, errors)
        if payload.get('taxon_resolution') != 'ambiguous':
            errors.append('reason_not_ambiguous_taxon')
        if payload.get('taxon') is not None:
            errors.append('ambiguous_name_resolved_to_a_taxon')
        if payload.get('coverage') is not None:
            errors.append('trait_query_ran_for_unresolved_taxon')
    elif rule == 'subspecies_no_data':
        payload = _graph_payload(response, errors)
        taxon = payload.get('taxon') or {}
        if (taxon.get('rank'), taxon.get('scientific_name')) != ('subspecies', expectations.get('taxon')):
            errors.append('subspecies_not_resolved_exactly')
        if payload.get('taxon_resolution') is not None:
            errors.append('reason_is_resolution_failure')
        if payload.get('coverage') != {'scoped': 1, 'evaluable': 0, 'matched': 0}:
            errors.append('coverage_not_subspecies_itself_without_claims')
        expected = sorted((_expected_condition(c) for c in expectations.get('conditions') or ()), key=repr)
        if sorted((_actual_condition(c) for c in payload.get('conditions') or ()), key=repr) != expected or not expected:
            errors.append('original_conditions_changed_or_lost')
        text = payload.get('text') or ''
        if '아종' not in text or '부모 종' not in text or SUBSPECIES_LIMIT not in (payload.get('limitations') or ()):
            errors.append('parent_species_substitution_not_excluded')
    elif rule == 'specific_plant':
        payload = _graph_payload(response, errors)
        if PLANT_LIMIT not in (payload.get('limitations') or ()):
            errors.append('reason_not_no_plant_level_diet')
        if payload.get('coverage') is not None or payload.get('taxon') is not None or payload.get('conditions'):
            errors.append('specific_plant_reinterpreted_as_trait_query')
    else:
        errors.append('unmapped_non_executing_case')
    return rule, errors


def audit(rows):
    cases, seen = [], set()
    for case_id, expectations, question, response in rows:
        if case_id not in RULES and expectations.get('outcome') not in ('hold', 'insufficient'):
            continue
        rule, errors = audit_case(case_id, expectations, response)
        seen.add(case_id)
        cases.append({'id': case_id, 'question': question, 'rule': rule, 'passed': not errors, 'errors': errors})
    missing = sorted(set(RULES) - seen)
    return {'audited': len(cases), 'expected_ids': len(RULES), 'missing': missing,
            'failed': [c['id'] for c in cases if not c['passed']],
            'passed': not missing and all(c['passed'] for c in cases), 'cases': cases}


def _payload(response):
    return response['result']['payload']


def _mutations():
    """(name, case_id, function mutating a deep-copied response) covering the three failure families."""
    def executed_without_condition(r):
        r.update(disposition='answer', result={'kind': 'graph_query', 'payload': {
            'status': 'answer', 'items': [{'taxon': {'taxon_id': 'x', 'rank': 'species'}, 'paths': []}],
            'conditions': [], 'coverage': {'scoped': 5, 'evaluable': 5, 'matched': 1}, 'has_more': False}})
    return (
        # reason misclassified
        ('ambiguous_reported_as_not_found', 'IT-043', lambda r: _payload(r).update(taxon_resolution='not_found')),
        ('subspecies_reported_as_resolution_failure', 'CT-011', lambda r: _payload(r).update(taxon_resolution='not_found')),
        ('plant_reported_as_generic_insufficient', 'IT-042', lambda r: _payload(r).update(limitations=[])),
        ('hold_turned_insufficient', 'IT-036', lambda r: r.update(disposition='abstain', result={
            'kind': 'graph_query', 'payload': {'status': 'insufficient_data', 'items': [], 'has_more': False}})),
        # node resolution failure or substitution
        ('subspecies_resolved_to_parent_species', 'IT-011', lambda r: _payload(r)['taxon'].update(
            rank='species', scientific_name='Corvus corone')),
        ('subspecies_taxon_missing', 'CT-011', lambda r: _payload(r).update(taxon=None)),
        ('ambiguous_name_resolved', 'CT-016', lambda r: _payload(r).update(
            taxon={'rank': 'family', 'scientific_name': 'Psophiidae'}, coverage={'scoped': 3, 'evaluable': 3, 'matched': 0})),
        ('subspecies_parent_claims_counted', 'IT-011', lambda r: _payload(r).update(
            coverage={'scoped': 1, 'evaluable': 1, 'matched': 1})),
        # condition deleted or held condition executed
        ('subspecies_condition_deleted', 'CT-011', lambda r: _payload(r).update(conditions=[])),
        ('held_condition_dropped_and_executed', 'CT-018', executed_without_condition),
        ('negation_dropped_and_executed', 'IT-034', executed_without_condition),
        ('plant_rewritten_as_fruit_query', 'IT-042', lambda r: _payload(r).update(
            conditions=[{'trait_name': 'diet_distribution', 'op': 'share_gt', 'value': 'fruit', 'threshold': 0, 'unit': None}],
            coverage={'scoped': 135, 'evaluable': 100, 'matched': 76})),
        ('items_returned_for_ambiguous', 'IT-044', lambda r: _payload(r).update(items=[{'taxon': {}, 'paths': []}])),
    )


def selfcheck(rows):
    """The unmodified rows must pass; every mutation must be caught on its case."""
    baseline = audit(rows)
    by_id = {row[0]: row for row in rows}
    results = []
    for name, case_id, mutate in _mutations():
        if case_id not in by_id:
            results.append({'mutation': name, 'case': case_id, 'caught': False, 'reason': 'case_missing'})
            continue
        case_id_, expectations, question, response = by_id[case_id]
        mutated = copy.deepcopy(response)
        mutate(mutated)
        _, errors = audit_case(case_id, expectations, mutated)
        results.append({'mutation': name, 'case': case_id, 'caught': bool(errors), 'errors': errors})
    return {'baseline_passed': baseline['passed'], 'mutations': len(results),
            'caught': sum(r['caught'] for r in results), 'passed': baseline['passed'] and all(r['caught'] for r in results),
            'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('results', nargs='+', help='results.jsonl or independent-api-*.json (several are merged)')
    parser.add_argument('--out', help='write the JSON report here as well as stdout')
    parser.add_argument('--selfcheck', action='store_true', help='also prove the audit catches mutated responses')
    args = parser.parse_args(argv)
    rows = [row for path in args.results for row in load_rows(path)]
    report = {'inputs': args.results, 'api_calls': 0, 'db_calls': 0, 'expectations_modified': False, **audit(rows)}
    if args.selfcheck:
        report['selfcheck'] = selfcheck(rows)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if report['passed'] and (not args.selfcheck or report['selfcheck']['passed']) else 1


if __name__ == '__main__':
    sys.exit(main())
