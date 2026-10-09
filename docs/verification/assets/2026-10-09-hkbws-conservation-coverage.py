"""Reconcile preserved HKBWS factual rows with a supplied read-only runtime replay.

No network or database writes. Example:
python3 docs/verification/assets/2026-10-09-hkbws-conservation-coverage.py \
  --source-facts docs/verification/assets/2026-10-09-hkbws-conservation-coverage.json \
  --runtime RUNTIME_REPLAY.json \
  --unresolved docs/verification/assets/2026-10-09-unresolved-conservation-review.json \
  --output RECOMPUTED_COVERAGE.json

Source facts were reviewed from official page search-cache fragments; this
script repeats the reconciliation, not acquisition of the external website.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def reconcile(source, runtime, unresolved):
    all_current = {r['taxon']['scientific_name']: r for r in runtime['species']}
    if len(all_current) != len(runtime['species']):
        raise ValueError('Runtime contains duplicate scientific names')
    original = [r for r in unresolved['species'] if not r.get('selected_reference_source')]
    indexed = []
    categories = {'EX', 'EW', 'CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'NE'}
    for old in source['hkbws_list_comparison']:
        row = {k: old.get(k) for k in ('list_number', 'source_scientific_name',
            'source_url', 'source_updated_at', 'source_release', 'source_acquisition',
            'category_raw')}
        name = row['source_scientific_name']
        raw = row['category_raw']
        grade = raw if raw in categories else None
        live = all_current.get(name)
        conservation = live['conservation'] if live else {}
        reference = conservation.get('reference_assessment') or {}
        displayed = conservation.get('category') or reference.get('category')
        row.update(category=grade, blank_category_not_inferred=not bool(grade),
            exact_current_scientific_name=name if live else None,
            current_taxon_id=live['taxon']['taxon_id'] if live else None,
            current_display_category=displayed,
            current_category_source_id=conservation.get('source_id') if conservation.get('category') else reference.get('source_id'),
            current_primary_category=conservation.get('category'),
            category_conflict=bool(grade and displayed and grade != displayed),
            taxonomy_alignment='unverified', assessment_year=None)
        indexed.append(row)
    numbers = [r['list_number'] for r in indexed]
    if sorted(numbers) != list(range(1, 585)):
        raise ValueError('Preserved source must contain exactly list rows 1..584')
    by_name = {r['source_scientific_name']: r for r in indexed}
    coverage = []
    for row in original:
        name = row['scientific_name']
        exact = by_name.get(name)
        decision = re.sub(r'<[^>]+>', ' ', row.get('taxonomy_decision_text') or '')
        candidates = [r for n, r in by_name.items() if n != name and
            re.search(r'(?<![A-Za-z])' + re.escape(n) + r'(?![A-Za-z])', decision)]
        coverage.append(dict(taxon_id=row['taxon_id'], scientific_name=name,
            exact_hkbws_list_match=exact,
            official_taxonomy_decision_named_hkbws_candidates=candidates,
            match_status='exact_name_in_hkbws_list' if exact else
                'official_decision_named_candidate' if candidates else 'not_matched_in_hkbws_2024_list',
            candidate_does_not_assign_grade=True))
    conflicts = []
    prior_conflicts = {r['source_scientific_name']: r for r in source['category_conflicts']}
    for row in indexed:
        if row['category_conflict']:
            old = prior_conflicts.get(row['source_scientific_name'])
            item = dict(row)
            if old and (old['category'], old['current_display_category']) == (row['category'], row['current_display_category']):
                for key in ('current_runtime_evidence', 'pinned_gbif_record', 'resolution',
                            'gbif_citation_assessment_year', 'gbif_citation_assessment_id'):
                    if key in old:
                        item[key] = old[key]
            conflicts.append(item)
    counts = dict(hkbws_list_rows=len(indexed), current_species_replayed=len(all_current),
        original_unresolved_species=len(coverage),
        list_exact_current_name=sum(bool(r['exact_current_scientific_name']) for r in indexed),
        list_name_not_exact_current_name=sum(not r['exact_current_scientific_name'] for r in indexed),
        list_explicit_category=sum(bool(r['category']) for r in indexed),
        list_blank_or_noncategory=sum(not r['category'] for r in indexed),
        explicit_category_exact_current=sum(bool(r['category'] and r['exact_current_scientific_name']) for r in indexed),
        category_conflicts=len(conflicts),
        unresolved_match_status=dict(Counter(r['match_status'] for r in coverage)),
        conflict_resolution=dict(Counter(r.get('resolution', {}).get('status', 'unresolved') for r in conflicts)))
    return indexed, coverage, conflicts, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-facts', 'runtime', 'unresolved', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    source, runtime, unresolved = read(args.source_facts), read(args.runtime), read(args.unresolved)
    indexed, coverage, conflicts, counts = reconcile(source, runtime, unresolved)
    result = {k: v for k, v in source.items() if k not in ('hkbws_list_comparison',
        'original_unresolved_305_coverage', 'category_conflicts', 'counts', 'runtime_input_sha256')}
    result.update(hkbws_list_comparison=indexed, original_unresolved_305_coverage=coverage,
        category_conflicts=conflicts, counts=counts,
        runtime_input_sha256=hashlib.sha256(args.runtime.read_bytes()).hexdigest())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
