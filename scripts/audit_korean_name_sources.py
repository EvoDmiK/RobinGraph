"""Audit every active species against reviewed names and pinned Korean source extracts.

Read-only: no names are translated or automatically promoted from Wikidata.
The inventory must come from audit_active_species_names.py, not a sample.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from robingraph.retrieval.taxonomy_lineage import sourced_korean_names, with_korean_display_name


def audit(inventory: dict, source_dir: Path) -> dict:
    rows = inventory['rows']
    if len({r['taxon_id'] for r in rows}) != len(rows):
        raise ValueError('Inventory contains duplicate species IDs')
    labels = sourced_korean_names()
    by_science = {r['scientific_name']: r for r in rows}
    snapshot = json.loads((Path(__file__).resolve().parents[1] / 'src/robingraph/retrieval/species_ko_names.json').read_text())
    rejected = {(v['scientific_name'], v['name']): v['reason'] for v in snapshot['supplemental_rejected_candidates']}
    used_names = {v['name']: k for k, v in labels.items()}
    defects, pending = [], []
    rendered = 0
    for row in rows:
        label = labels.get(row['taxon_id'])
        view = with_korean_display_name(row)
        rendered += bool(view.get('korean_name'))
        if label and view.get('korean_name') != label['name']:
            defects.append({'taxon_id': row['taxon_id'], 'scientific_name': row['scientific_name'],
                            'expected_name': label['name'], 'actual_name': view.get('korean_name'),
                            'english_name': row.get('english_name'), 'expected_english': label['english_name']})
        if not view.get('korean_name') and row.get('graph_korean'):
            candidates = []
            for name in sorted({n['name'] for n in row['graph_korean'] if n.get('name')}):
                reason = ('non_korean_label' if not re.search('[가-힣]', name) else
                          'conflicts_with_reviewed_other_species' if name in used_names and used_names[name] != row['taxon_id'] else
                          'independent_source_review_required')
                candidates.append({'name': name, 'reason': reason})
            pending.append({'taxon_id': row['taxon_id'], 'scientific_name': row['scientific_name'],
                            'english_name': row.get('english_name'), 'candidates': candidates})
    source_results = {}
    sources = [('kos-2025-species.json', lambda r: (r['scientific_name'], r['name'].strip())),
               ('ioc-rows.json', lambda r: (r.get('D'), (r.get('AP') or '').strip())),
               ('zoo-names.json', lambda r: (r['scientific_name'], r['name'].strip()))]
    for filename, extract in sources:
        path = source_dir / filename
        records = json.loads(path.read_text())
        decisions = []
        for record in records:
            science, name = extract(record)
            if not science or not name or name == 'Korean':
                continue
            target = by_science.get(science)
            crosswalk = next((v for v in labels.values() if v.get('source_scientific_name') == science and v['name'] == name), None)
            existing = labels.get(target['taxon_id']) if target else None
            state = ('reviewed_exact' if existing and existing['name'] == name else
                     'reviewed_crosswalk' if crosswalk else
                     'no_exact_active_species' if not target else
                     'existing_reviewed_name_preserved' if existing else
                     'conflicts_with_reviewed_other_species' if name in used_names else
                     'previously_reviewed_rejection' if (science, name) in rejected else
                     'unreviewed_source_candidate')
            decisions.append({'scientific_name': science, 'name': name, 'decision': state, 'previous_review_reason': rejected.get((science, name))})
        source_results[filename] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                   'counts': dict(Counter(r['decision'] for r in decisions)), 'records': decisions}
    return {'species_count': len(rows), 'reviewed_name_count': len(labels), 'rendered_korean_count': rendered,
            'english_fallback_count': len(rows)-rendered, 'reviewed_display_defects': defects,
            'unreviewed_graph_species_count': len(pending),
            'unreviewed_graph_candidate_reasons': dict(Counter(c['reason'] for r in pending for c in r['candidates'])),
            'unreviewed_graph_species': pending, 'source_audit': source_results,
            'limits': ['DB graph candidates may span snapshots; candidates are deduplicated by name per species.',
                       'Unreviewed graph labels are not verified Korean names; conflicts and non-Korean labels are retained for review.',
                       'This checks the supplied full DB inventory and three pinned source extracts, not every Korean-language publication.',
                       'No biological traits, conservation grades, name-search HTTP results, or production deployment are tested here.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.inventory.read_text()), args.source_dir)
    report['inventory_sha256'] = hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k.endswith('_count') or k=='reviewed_display_defects'}, ensure_ascii=False))
    if report['reviewed_display_defects']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
