"""Replay current conservation reader over a previously captured read-only TEST DB export.

This is actual DB-row replay, not one live HTTP request per species. Run with
PYTHONPATH=src python <this file> --rows <json> --avilist <pinned json> --output <json>.
The input export contains public taxonomy metadata only, never credentials.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from robingraph.retrieval.conservation import TAXONOMY_SHA256
from robingraph.retrieval.species_profile import read_conservation
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('rows', 'avilist', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    raw = args.avilist.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == TAXONOMY_SHA256
    source = {f'avilist-taxon:v2025b:{r[0]}': r for r in json.loads(raw) if r[1] == 'species'}
    rows_bytes = args.rows.read_bytes()
    rows = json.loads(rows_bytes)
    assert len(rows) == len(source) == len({r['taxon_id'] for r in rows}) == 11131
    assert {r['taxon_id'] for r in rows} == source.keys()
    statuses, refs, raw_categories = Counter(), Counter(), Counter()
    results, issues, normalized = [], [], []
    for row in rows:
        original = source[row['taxon_id']]
        expected = (original[5], original[6], original[15].strip(), original[16])
        actual = tuple(row[k] for k in ('scientific_name', 'authority', 'category_raw', 'assessment_reference_url'))
        if expected != actual or row['snapshot_sha256'] != TAXONOMY_SHA256:
            issues.append({'taxon_id': row['taxon_id'], 'error': 'stored_source_mismatch'})
        if original[15] != row['category_raw'] and original[15].strip() == row['category_raw']:
            normalized.append(row['taxon_id'])
        class Repository:
            def _run(self, query, **params):
                assert params['taxon_id'] == row['taxon_id']
                return [row]
        lineage = TaxonomyLineage(row['scientific_name'], 'AviList', 'v2025b',
            'rg:concept-set:avilist-v2025b', (LineageTaxon(row['taxon_id'], 'species', row['scientific_name'], row['authority']),))
        result = read_conservation(Repository(), lineage)
        statuses[result['assessment_status']] += 1
        raw_categories[row['category_raw']] += 1
        ref = result.get('reference_assessment')
        if row['category_raw'] == 'NE' and result['assessment_status'] != 'manual_override':
            if result.get('label') == '미평가':
                issues.append({'taxon_id': row['taxon_id'], 'error': 'false_not_evaluated_label'})
            if result.get('category') is not None:
                issues.append({'taxon_id': row['taxon_id'], 'error': 'false_effective_ne_category'})
        if ref:
            refs[ref['category']] += 1
            assert ref['assessment_status'] == 'reference_only'
            assert ref['independently_verified'] is False
            assert ref['scientific_name'] == row['scientific_name']
            assert result['assessment_status'] != 'linked_checklist'
            if row['category_raw'] == 'NE':
                assert result['category'] is None
        results.append({'taxon_id': row['taxon_id'], 'scientific_name': row['scientific_name'],
            'taxonomy_category_raw': row['category_raw'], 'category': result['category'],
            'label': result['label'], 'status': result['assessment_status'],
            'reference_category': ref['category'] if ref else None,
            'reference_url': ref['assessment_reference_url'] if ref else None})
    report = {'method': 'current reader replay over read-only actual TEST DB rows; not 11131 HTTP calls',
        'taxonomy_sha256': TAXONOMY_SHA256, 'rows_sha256': hashlib.sha256(rows_bytes).hexdigest(),
        'total_species': len(rows), 'raw_categories': dict(raw_categories), 'statuses': dict(statuses),
        'reference_categories': dict(refs), 'reference_total': sum(refs.values()),
        'normalized_source_whitespace': normalized, 'issues': issues, 'species': results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'species'}, ensure_ascii=False))
    assert not issues


if __name__ == '__main__':
    main()
