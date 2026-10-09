#!/usr/bin/env python3
"""Build original BIRDBASE values using the authors' explicit AviList mapping.

The whole named AviList species set and AviList-family column must agree with
our pinned taxonomy. No generic-name fuzzy match, ancestor inference, invented
averages, or conversion of ordinal diet weights to measured percentages occurs.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import build_trait_crosswalk as base
from robingraph.retrieval.trait_mapping import PINS

SOURCE_SHA256 = 'cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b'
SOURCE_URL = 'https://ndownloader.figshare.com/files/55634729'
SOURCE_RELEASE = 'figshare-27051040-v1:file-55634729'
OUTPUT = ROOT / 'src/robingraph/retrieval/birdbase_traits.json'
MASS_FIELDS = ('Female MinMass', 'Female MaxMass', 'Male MinMass', 'Male MaxMass', 'Unsexed MinMass', 'Unsexed MaxMass')


def build(avilist, rows, *, require_complete=True):
    targets = {r['Scientific_name']: r for r in avilist if r['Taxon_rank'] == 'species'}
    selected = [r for r in rows if r.get('AviList v1 2025')]
    counts = Counter(r['AviList v1 2025'] for r in selected)
    if any(v != 1 for v in counts.values()): raise ValueError('Ambiguous BIRDBASE AviList rows')
    if require_complete and set(counts) != set(targets): raise ValueError('BIRDBASE and pinned AviList species sets differ')
    entries = []
    for row in selected:
        name = row['AviList v1 2025']; target = targets.get(name)
        if target is None: continue
        if row['Family AviList v1 2025'] != target['Family']: raise ValueError('AviList family mismatch: ' + name)
        if row['Diet_Lit'] not in (0, 1): raise ValueError('Unknown diet provenance flag')
        entries.append({
            'target_name': name, 'target_sequence': str(target['Sequence']), 'target_avibase_id': target['AvibaseID'].lower(),
            'target_family': target['Family'], 'source_row': row['_row'],
            'source_name': row['Latin (BirdLife > IOC > Clements>AviList)'],
            'source_species_id': row['IOC 15.1'], 'source_references': row['Source'],
            'body_mass': row['Average Mass'], 'mass_bounds': {key: row[key] for key in MASS_FIELDS},
            'habitat': row['Primary Habitat'], 'diet_category': row['Primary Diet'], 'diet_literature': row['Diet_Lit'],
            'source_diet_weights': {key: row[key] for key in ('IN-Wt', 'FR-Wt', 'NE-Wt', 'SE-Wt', 'VE-Wt', 'FI-Wt', 'SC-Wt', 'PL-Wt', 'MS-Wt')},
        })
    return {'schema_version': 1, 'source_id': 'traits-birdbase-v2025-1', 'source_url': SOURCE_URL,
            'source_release': SOURCE_RELEASE, 'source_sha256': SOURCE_SHA256, 'license_name': 'CC BY 4.0',
            'taxonomy_release': PINS['taxonomy'][0], 'taxonomy_sha256': PINS['taxonomy'][1],
            'source_taxonomy': 'AviList v1 2025', 'source_taxonomy_field': 'AviList v1 2025',
            'policy': 'Explicit author AviList column, whole species set equality and AviList family equality. Exact author values only, no unit/sample-average reinterpretation. Diet_Lit=0 stays inferred. No Information stays absent. Ordinal diet weights and traces are not percentages.',
            'entries': sorted(entries, key=lambda e: int(e['target_sequence']))}


def main():
    import openpyxl
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True); p.add_argument('--avilist', type=Path, required=True)
    p.add_argument('--output', type=Path, default=OUTPUT); p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_SHA256: raise ValueError('BIRDBASE source hash mismatch')
    if hashlib.sha256(args.avilist.read_bytes()).hexdigest() != PINS['taxonomy'][1]: raise ValueError('AviList source hash mismatch')
    w = openpyxl.load_workbook(args.source, read_only=True, data_only=True)
    cells = w['Data'].iter_rows(values_only=True); next(cells); header = next(cells)
    rows = [{**dict(zip(header, row)), '_row': number} for number, row in enumerate(cells, start=3) if row[2]]
    if len(rows) != 11589: raise ValueError('Unexpected BIRDBASE row count')
    payload = build(base.read_avilist(args.avilist), rows); w.close()
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if args.check:
        if args.output.read_bytes() != raw: raise ValueError('Extract differs from source')
    else: args.output.write_bytes(raw)
    print(json.dumps({'entries': len(payload['entries']), 'sha256': hashlib.sha256(raw).hexdigest(), 'checked': args.check}))


if __name__ == '__main__': main()
