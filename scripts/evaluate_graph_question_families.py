"""Score saved API/trace artifacts by complete meaning, equivalence family and contrast.

No network, database or application imports. A separately sampled model plan is never
execution evidence. Optional taxonomy catalog resolves trace surface aliases only.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

CONDITION_FIELDS = ('trait_name', 'op', 'value', 'threshold', 'unit', 'qualifier')


def conditions(values):
    if not isinstance(values, list) or not all(isinstance(c, dict) for c in values):
        raise ValueError('conditions must be a list of objects')
    result = []
    for value in values:
        normalized = {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                      for k, v in value.items() if k in CONDITION_FIELDS and v is not None}
        result.append(json.dumps(normalized, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return sorted(result)  # AND order is irrelevant; duplicates are retained.


def canonical(name, catalog):
    if name is None:
        return None
    found = {r['scientific_name'] for r in catalog.get('taxa', [])
             if isinstance(name, str) and name.casefold().strip() in
             {v.casefold().strip() for v in (r.get('scientific_name'), r.get('korean_name')) if isinstance(v, str)}}
    return next(iter(found)) if len(found) == 1 else name


def expected_signature(expected):
    if expected.get('kind') == 'relation':
        return {'kind': 'habitat_shared_diet' if expected.get('habitat') else 'shared_diet',
                'reference': expected['reference_taxon_name'], 'habitat': expected.get('habitat'),
                'basis': expected['share_basis'], 'match': 'same',
                'exclude_reference': expected['exclude_reference'],
                'species_scope': expected.get('species_scope', 'all')}
    return {'kind': 'taxon_traits', 'taxon': expected['taxon_name'], 'rank': expected['rank'],
            'conditions': conditions(expected['conditions'])}


def api_signature(payload, expected, catalog):
    """(observed meaning, errors, missing evidence). Missing evidence cannot pass."""
    errors, missing = [], []
    if expected['kind'] == 'relation':
        summary = payload.get('execution_summary')
        if not isinstance(summary, dict):
            return None, [], ['same-request execution_summary missing']
        required = ('kind', 'reference_name', 'target_id', 'species_scope', 'share_basis', 'match',
                    'exclude_reference', 'habitat', 'niche_value', 'dataset_id', 'release',
                    'concept_set_id', 'taxonomy_release')
        missing += ['execution_summary.' + k for k in required if k not in summary]
        for key in ('niche_value', 'dataset_id', 'release', 'concept_set_id', 'taxonomy_release'):
            if key in summary and (not isinstance(summary[key], str) or not summary[key]):
                errors.append('invalid execution_summary.' + key)
        if summary.get('exclude_reference') is not True:
            errors.append('reference exclusion must be boolean true')
        target = payload.get('taxon') or {}
        if target.get('scientific_name') != summary.get('reference_name') or target.get('taxon_id') != summary.get('target_id'):
            errors.append('reference payload and executor disagree')
        known = [r for r in catalog.get('taxa', []) if r['scientific_name'] == expected['reference_taxon_name']]
        if len(known) == 1 and known[0]['id'] != summary.get('target_id'):
            errors.append('executor reference identity differs from catalog')
        for key in ('concept_set_id', 'taxonomy_release'):
            if catalog.get(key) is not None and catalog[key] != summary.get(key):
                errors.append('executor taxonomy context differs from catalog: ' + key)
        if any((i.get('taxon') or {}).get('taxon_id') == summary.get('target_id') for i in payload.get('items', [])):
            errors.append('reference species included in peers')
        return {'kind': summary.get('kind'), 'reference': summary.get('reference_name'),
                'habitat': summary.get('habitat'), 'basis': summary.get('share_basis'),
                'match': summary.get('match'), 'exclude_reference': summary.get('exclude_reference'),
                'species_scope': summary.get('species_scope')}, errors, missing
    taxon = payload.get('taxon') or {}
    if expected['taxon_name'] is None and expected['rank'] is None:
        if 'taxon' not in payload:
            missing.append('explicit whole-catalog taxon')
        elif payload['taxon'] is not None:
            errors.append('whole-catalog execution must have null taxon')
        coverage = payload.get('coverage')
        if not isinstance(coverage, dict) or any(k not in coverage for k in ('scoped', 'evaluable', 'matched')):
            missing.append('whole-catalog execution coverage')
        elif (not all(isinstance(coverage[k], int) and not isinstance(coverage[k], bool)
                      for k in ('scoped', 'evaluable', 'matched')) or
              not 0 <= coverage['matched'] <= coverage['evaluable'] <= coverage['scoped']):
            errors.append('invalid whole-catalog execution coverage')
    else:
        missing += ['taxon.' + k for k in ('scientific_name', 'rank') if not taxon.get(k)]
    if 'conditions' not in payload:
        missing.append('conditions')
    return {'kind': 'taxon_traits', 'taxon': taxon.get('scientific_name'), 'rank': taxon.get('rank'),
            'conditions': conditions(payload.get('conditions', []))}, errors, missing


def route_signature(intent, expected, catalog):
    """Use original per-request route output when available, including all semantic fields."""
    errors = []
    if any(intent.get(k) for k in ('negation', 'residual', 'unsupported', 'ambiguity', 'unsupported_food')):
        errors.append('same-request route retains unresolved restrictions')
    if expected['kind'] == 'relation':
        names = intent.get('species', [])
        if len(names) != 1:
            errors.append('relation needs exactly one reference')
        if intent.get('diet') != 'niche' or intent.get('relation') != 'same':
            errors.append('relation basis or equality changed')
        return {'kind': intent.get('kind'), 'reference': canonical(names[0].get('text'), catalog) if len(names) == 1 else None,
                'habitat': intent.get('habitat'), 'basis': 'trophic_niche', 'match': 'same',
                'exclude_reference': True, 'species_scope': expected.get('species_scope', 'all')}, errors
    if intent.get('kind') != 'taxon_traits' or intent.get('species') or intent.get('habitat') or intent.get('group'):
        errors.append('same-request trait query kind or extra scope changed')
    name = canonical((intent.get('rank') or {}).get('text'), catalog)
    # Route rank is a span name, not an explicit taxonomic level; the API verifies rank.
    return {'kind': 'taxon_traits', 'taxon': name, 'rank': expected['rank'],
            'conditions': conditions([c[0] for c in intent.get('conditions', [])])}, errors



def canonical_route_signature(plan, expected, catalog):
    errors = []
    if any(plan.get(k) for k in ('criterion', 'group')):
        errors.append('canonical route adds an unexpected restriction')
    if expected['kind'] == 'relation':
        names = plan.get('names', [])
        wanted_conditions = ([{'trait_name': 'habitat', 'op': 'eq', 'value': expected['habitat']}]
                             if expected.get('habitat') else [])
        if plan.get('kind') != 'shared_diet' or len(names) != 1 or plan.get('rank_name'):
            errors.append('canonical relation kind or reference changed')
        if conditions(plan.get('conditions', [])) != conditions(wanted_conditions):
            errors.append('canonical relation habitat conditions changed')
        if plan.get('habitat') not in (None, expected.get('habitat')):
            errors.append('canonical relation adds habitat')
        return {'kind': 'habitat_shared_diet' if expected.get('habitat') else 'shared_diet',
                'reference': canonical(names[0], catalog) if len(names) == 1 else None,
                'habitat': expected.get('habitat'), 'basis': 'trophic_niche', 'match': 'same',
                'exclude_reference': True, 'species_scope': expected.get('species_scope', 'all')}, errors
    if plan.get('kind') != 'taxon_traits' or plan.get('names') or plan.get('habitat'):
        errors.append('canonical trait query adds names or changes kind')
    return {'kind': 'taxon_traits', 'taxon': canonical(plan.get('rank_name'), catalog),
            'rank': expected['rank'], 'conditions': conditions(plan.get('conditions', []))}, errors


def assess(case, row, catalog):
    base = {'id': case['id'], 'group': case['semantic_group_id'], 'role': case['role']}
    if row is None or not isinstance(row.get('response'), dict):
        return {**base, 'status': 'missing', 'classification': 'missing_response', 'errors': ['response missing'], 'observed_signature': None}
    response = row['response']; result = response.get('result') or {}; payload = result.get('payload') or {}
    tags = row.get('tags') or {}; errors, missing = [], []; observed = None
    if row.get('http_status', 200) != 200:
        errors.append('HTTP status is not 200')
    route = next((s for s in row.get('diagnostic_spans', []) if s.get('name') == 'graph_intent.route'), None)
    intent = route.get('outputs') if route else None
    if case['category'] == 'supported':
        wanted = expected_signature(case['expected'])
        if result.get('kind') != 'graph_query' or payload.get('status') not in ('answer', 'empty', 'insufficient_data'):
            errors.append('supported question has no graph result')
        elif response.get('disposition') != ('answer' if payload['status'] == 'answer' else 'abstain'):
            errors.append('API disposition disagrees with graph status')
        observed, execution_errors, absent = api_signature(payload, case['expected'], catalog)
        errors += execution_errors; missing += absent
        if not absent and observed != wanted:
            errors.append({'executed_meaning_mismatch': {'expected': wanted, 'actual': observed}})
        attributes = (route or {}).get('attributes') or {}
        canonical_plan = attributes.get('canonical_plan', attributes.get('graph_intent.canonical_plan'))
        if isinstance(canonical_plan, str):
            canonical_plan = json.loads(canonical_plan)
        whole_catalog = (case['expected']['kind'] == 'taxon_traits' and
                         case['expected']['taxon_name'] is None and case['expected']['rank'] is None)
        if whole_catalog:
            if not isinstance(canonical_plan, dict) or any(k not in canonical_plan for k in ('rank_name', 'names', 'group')):
                missing.append('explicit same-request whole-catalog canonical plan')
            elif canonical_plan['rank_name'] is not None or canonical_plan['names'] != [] or canonical_plan['group'] is not None:
                errors.append('whole-catalog canonical scope is not unrestricted')
        if isinstance(canonical_plan, dict):
            parsed, route_errors = canonical_route_signature(canonical_plan, case['expected'], catalog)
            errors += route_errors
            if isinstance(intent, dict) and any(intent.get(k) for k in ('negation', 'residual', 'unsupported', 'ambiguity', 'unsupported_food')):
                errors.append('same-request route retains unresolved restrictions')
            if parsed != wanted:
                errors.append({'same_request_canonical_mismatch': {'expected': wanted, 'actual': parsed}})
        elif isinstance(intent, dict):
            parsed, route_errors = route_signature(intent, case['expected'], catalog)
            errors += route_errors
            if parsed != wanted:
                errors.append({'same_request_route_mismatch': {'expected': wanted, 'actual': parsed}})
        if payload.get('taxon_resolution') in ('not_found', 'ambiguous'):
            errors.append('taxon could not be resolved')
        if (row.get('request') or {}).get('species_scope', 'all') != case['expected'].get('species_scope', 'all'):
            errors.append('request species scope differs from expected')
        if tags.get('response_reason') in ('upstream_error', 'interpretation_error', 'handler_unavailable'):
            errors.append('upstream failure cannot establish supported execution')
        classification = ('name_resolution_failure' if payload.get('taxon_resolution') in ('not_found', 'ambiguous') else
                          'upstream_failure' if tags.get('response_reason') in ('upstream_error', 'interpretation_error', 'handler_unavailable') else
                          'false_hold' if errors and response.get('disposition') in ('clarify', 'abstain') else
                          'wrong_plan' if errors else 'unverifiable_execution' if missing else
                          'supported_source_no_data' if payload.get('status') == 'insufficient_data' else
                          'supported_no_matching_results' if payload.get('status') == 'empty' else 'supported_answer')
    else:
        if response.get('disposition') not in ('clarify', 'abstain') or payload.get('status') == 'answer' or payload.get('execution_summary'):
            errors.append('held question answered or returned executor summary')
        hold = case.get('expected_hold_class')
        if hold == 'negated_condition':
            if tags.get('response_reason') != 'negated_conditions':
                errors.append('negative condition not identified')
            prompt = result.get('prompt')
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append('clarification prompt missing')
        elif hold == 'unsupported_specific_food':
            if payload.get('status') != 'insufficient_data' or not isinstance(intent, dict) or not (intent.get('kind') == 'specific_fruit' or intent.get('unsupported_food')):
                errors.append('specific food data gap not distinguished from generic hold')
        else:
            errors.append('unsupported or missing expected_hold_class')
        classification = hold if not errors else ('unsafe_answer' if response.get('disposition') == 'answer' else 'wrong_hold_reason')
        observed = {'hold': classification}
    status = 'fail' if errors else 'unverifiable' if missing else 'pass'
    return {**base, 'status': status, 'classification': classification, 'errors': errors, 'missing_evidence': missing,
            'observed_signature': observed, 'trace_id': row.get('trace_id'), 'api_disposition': response.get('disposition'),
            'api_status': payload.get('status'), 'tags': tags}


def evaluate(cases, rows, catalog=None):
    observations = {}; duplicates = []
    for row in rows:
        key = row.get('case') if isinstance(row.get('case'), str) else (row.get('case') or {}).get('id')
        if key in observations:
            duplicates.append(key)
        observations[key] = row
    if duplicates:
        raise ValueError('Multiple observations for case IDs; score attempts separately: ' + ', '.join(duplicates))
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case IDs in dataset')
    results = []
    for case in cases:
        try:
            results.append(assess(case, observations.get(case['id']), catalog or {}))
        except (ValueError, TypeError, KeyError, IndexError) as error:
            results.append({'id': case['id'], 'group': case['semantic_group_id'], 'role': case['role'],
                            'status': 'fail', 'classification': 'malformed_evidence',
                            'errors': [type(error).__name__], 'observed_signature': None})
    by_group = defaultdict(list)
    for item in results:
        by_group[item['group']].append(item)
    groups = []
    for key, members in by_group.items():
        equivalents = [r for r in members if r['role'] == 'equivalent']; contrasts = [r for r in members if r['role'] == 'contrast']
        equivalent = len(equivalents) == 2 and all(r['status'] == 'pass' for r in equivalents) and equivalents[0]['observed_signature'] == equivalents[1]['observed_signature']
        contrast = equivalent and len(contrasts) == 1 and contrasts[0]['status'] == 'pass' and contrasts[0]['observed_signature'] != equivalents[0]['observed_signature']
        groups.append({'group': key, 'status': 'pass' if equivalent and contrast else 'fail',
                       'equivalent_pair_exact': equivalent, 'contrast_distinguished': bool(contrast)})
    return {'case_counts': dict(Counter(r['status'] for r in results)),
            'classifications': dict(Counter(r['classification'] for r in results)),
            'group_counts': dict(Counter(r['status'] for r in groups)), 'groups': groups, 'rows': results,
            'limits': ['Saved same-request evidence only; no independent database re-query.',
                       'Model-authored gold; not human reviewed.', 'Exact-plan source no-data is separate from answer and name failure.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True); parser.add_argument('--responses', type=Path, required=True)
    parser.add_argument('--catalog', type=Path); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); dataset = json.loads(args.cases.read_text()); responses = json.loads(args.responses.read_text())
    report = evaluate(dataset['cases'], responses['rows'], json.loads(args.catalog.read_text()) if args.catalog else {})
    report.update(split=dataset['split'], source=str(args.responses), cases_sha256=hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                  responses_sha256=hashlib.sha256(args.responses.read_bytes()).hexdigest())
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('case_counts', 'classifications', 'group_counts')}))


if __name__ == '__main__':
    main()
