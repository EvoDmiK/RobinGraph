#!/usr/bin/env python3
"""Build a pinned AVONET eBird supplement using unique concept IDs, never names.

This reuses the authors' published eBird aggregates, not BirdLife values copied
across splits. The packaged extract is independently attributable raw evidence;
it is not advertised as a PostgreSQL source_record or an ingested graph claim.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import build_trait_crosswalk as base
from robingraph.retrieval.trait_mapping import FIELDS, PINS

OUTPUT = ROOT / 'src/robingraph/retrieval/avonet_ebird_supplement.json'


def build(avilist, rows, crosswalk):
    species = [r for r in avilist if r['Taxon_rank'] == 'species']
    targets = defaultdict(list)
    sources = defaultdict(list)
    for target in species:
        if target.get('AvibaseID'):
            targets[target['AvibaseID'].lower()].append(target)
    for row in rows:
        if row.get('Avibase.ID2'):
            sources[row['Avibase.ID2'].lower()].append(row)
    # Existing verified BirdLife data has priority; this fills concept gaps only.
    approved = {str(e[5]) for e in crosswalk['entries'] if e[0] == 'avonet' and e[8] == 'accepted'}
    entries = []
    for ident in sorted(targets):
        if len(targets[ident]) != 1 or len(sources[ident]) != 1:
            continue
        target = targets[ident][0]
        if str(target['Sequence']) in approved:
            continue
        row = sources[ident][0]
        if row.get('Inference') not in ('YES', 'NO'):
            raise ValueError('Invalid AVONET inference flag')
        values = {field: row.get(field) for field, _, _ in FIELDS.values()}
        entries.append({
            'target_sequence': str(target['Sequence']),
            'target_name': target['Scientific_name'], 'avibase_id': ident,
            'source_name': row['Species2'], 'source_row': row['_row'],
            'values': values, 'inference': row['Inference'],
            'inferred_fields': row.get('Traits.inferred'),
            'reference_species': row.get('Reference.species'),
            'sample_size': row.get('Total.individuals'),
            'mass_source': row.get('Mass.Source'), 'mass_reference': row.get('Mass.Refs.Other'),
        })
    return {
        'schema_version': 1, 'taxonomy_release': PINS['taxonomy'][0],
        'taxonomy_sha256': PINS['taxonomy'][1],
        'source_release': PINS['avonet'][0], 'source_sha256': PINS['avonet'][1],
        'source_url': PINS['avonet'][2], 'license_name': PINS['avonet'][3],
        'source_sheet': 'AVONET2_eBird',
        'method': 'avibase_id_unique',
        'policy': 'Unique source and target Avibase concept ID equality only; author-published eBird aggregates; existing verified BirdLife values retained; inference flags retained; no invented diet percentages.',
        'entries': sorted(entries, key=lambda e: int(e['target_sequence'])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    pins = base.load_pins()
    base.verify_hashes({key: args.raw_dir / name for key, name in base.RAW_NAMES.items()}, pins)
    avilist = base.read_avilist(args.raw_dir / base.RAW_NAMES[base.AVILIST_ID])
    base.AVONET_SHEETS['avonet2'] = 'AVONET2_eBird'
    base.AVONET_REQUIRED['avonet2'] = ['Species2', 'Avibase.ID2', 'Inference', 'Mass']
    rows = base.read_avonet(args.raw_dir / base.RAW_NAMES[base.AVONET_ID])['avonet2']
    if len(rows) != 10661:
        raise ValueError('Unexpected eBird source row count')
    crosswalk = json.loads((ROOT / 'src/robingraph/retrieval/trait_crosswalk.json').read_text())
    payload = build(avilist, rows, crosswalk)
    output = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if args.check:
        if args.output.read_bytes() != output:
            raise SystemExit('Supplement differs from pinned sources')
    else:
        args.output.write_bytes(output)
    print(json.dumps({'entries': len(payload['entries']), 'sha256': hashlib.sha256(output).hexdigest(), 'checked': args.check}))


if __name__ == '__main__':
    main()
