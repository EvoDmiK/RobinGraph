#!/usr/bin/env python3
"""Compare full deployed-reader audits against the requested immutable subsets.

Inputs are evidence files, never database credentials. No network or writes
outside the explicit output file. This does not perform HTTP/browser tests.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def compare(before, after, subsets):
    old = {r['id']: r for r in before['species']}
    new = {r['id']: r for r in after['species']}
    if len(old) != len(before['species']) or len(new) != len(after['species']) or old.keys() != new.keys():
        raise ValueError('Species identity set changed or contains duplicates')
    lookup = {r['expected_id']: r for r in after['korean_lookups']}
    rows = []
    for subset, members in subsets.items():
        for row in members:
            tid = row['taxon_id']
            prior, current = old[tid], new[tid]
            if current['scientific_name'] != row['scientific_name']:
                raise ValueError('Baseline scientific identity changed: ' + tid)
            conservation = current.get('conservation') or {}
            reference = conservation.get('reference_assessment') or {}
            if subset == 'names':
                match = lookup.get(tid)
                status = 'verified_name_lookup_passed' if match and match.get('ok') else 'unresolved_or_failed_lookup'
            elif subset == 'traits':
                status = 'traits_available' if current['trait_count'] else 'no_linked_trait'
            else:
                status = 'primary_assessment' if conservation.get('category') else 'reference_assessment' if reference.get('category') else 'no_linked_assessment'
            rows.append({'subset': subset, 'taxon_id': tid, 'scientific_name': current['scientific_name'],
                         'status': status, 'before_trait_count': prior['trait_count'], 'after_trait_count': current['trait_count'],
                         'alignment': current['alignment'], 'category': conservation.get('category'),
                         'reference_category': reference.get('category'), 'assessment_status': conservation.get('assessment_status')})
    regressions = []
    for tid, prior in old.items():
        current = new[tid]
        missing = set(prior['trait_names']) - set(current['trait_names'])
        oldc, newc = prior.get('conservation') or {}, current.get('conservation') or {}
        oldgrade = oldc.get('category') or (oldc.get('reference_assessment') or {}).get('category')
        newgrade = newc.get('category') or (newc.get('reference_assessment') or {}).get('category')
        if missing or (oldgrade and not newgrade):
            regressions.append({'taxon_id': tid, 'lost_trait_names': sorted(missing), 'lost_grade': oldgrade if not newgrade else None})
    return {'mode': 'comparison of live DB/deployed-reader evidence; not HTTP or browser test',
            'species_count': len(new), 'requested_counts': {k: len(v) for k, v in subsets.items()},
            'requested_unique_species': len({r['taxon_id'] for r in rows}),
            'dispositions': {k: dict(Counter(r['status'] for r in rows if r['subset'] == k)) for k in subsets},
            'runtime_errors': after['errors'], 'korean_lookup_total': len(lookup),
            'korean_lookup_failures': [r for r in after['korean_lookups'] if not r.get('ok')],
            'trait_field_or_grade_regressions': regressions, 'species': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'baseline', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    inputs = {key: getattr(args, key).read_bytes() for key in ('before', 'after', 'baseline')}
    result = compare(*(json.loads(inputs[key]) for key in ('before', 'after', 'baseline')))
    result['input_sha256'] = {key: sha256(value).hexdigest() for key, value in inputs.items()}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'species'}, ensure_ascii=False))
    return int(bool(result['runtime_errors'] or result['korean_lookup_failures'] or result['trait_field_or_grade_regressions']))


if __name__ == '__main__':
    raise SystemExit(main())
