#!/usr/bin/env python3
"""Extract explicitly subordinate source concepts via pinned eBird report_as.

This builds reference observations, never parent species averages. Requires
openpyxl only at build time to read Cornell's multilingual taxonomy workbook.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import build_trait_crosswalk as base
from robingraph.retrieval.trait_mapping import FIELDS, PINS

EBIRD_SHA256 = '5a6c29b6a48db107b20f8bd1bc6f468ef652a51ccae299b1102350459d73b909'
EBIRD_URL = 'https://cornell.box.com/s/zjci66divvqnz00k98r7pmmb6kpc69zs'
OUTPUT = ROOT / 'src/robingraph/retrieval/avonet_subgroup_supplement.json'


def concept(value):
    return (value or '').replace('avibase-avibase-', 'avibase-').lower()


def build(avilist, taxonomy, source_sheets):
    targets = defaultdict(list); species = defaultdict(list); subordinate = defaultdict(list)
    for row in avilist:
        if row['Taxon_rank'] == 'species': targets[concept(row['AvibaseID'])].append(row)
    for row in taxonomy:
        if row['category'] == 'species': species[row['species_code']].append(row)
        elif row['category'] == 'issf': subordinate[concept(row['bio_concept_code'])].append(row)
    selected = {}
    # Prefer the authors' eBird sheet within the SAME source concept; retain all
    # distinct subordinate groups. Never choose one subgroup to represent others.
    for sheet, name_col, id_col in [('AVONET2_eBird', 'Species2', 'Avibase.ID2'), ('AVONET1_BirdLife', 'Species1', 'Avibase.ID1')]:
        source_ids = defaultdict(list)
        for row in source_sheets[sheet]: source_ids[concept(row[id_col])].append(row)
        for ident, sources in source_ids.items():
            if len(sources) != 1 or len(subordinate[ident]) != 1: continue
            subgroup = subordinate[ident][0]
            parents = species[subgroup['report_as']]
            if len(parents) != 1: continue
            parent = parents[0]
            matches = targets[concept(parent['bio_concept_code'])]
            if len(matches) != 1: continue
            target = matches[0]; key = (str(target['Sequence']), ident)
            if key in selected: continue
            row = sources[0]
            selected[key] = {
                'target_sequence': str(target['Sequence']), 'target_name': target['Scientific_name'],
                'target_avibase_id': concept(target['AvibaseID']), 'source_avibase_id': ident,
                'source_name': row[name_col], 'source_row': row['_row'], 'source_sheet': sheet,
                'subgroup_name': subgroup['sci_name'], 'subgroup_english_name': subgroup['primary_com_name'],
                'subgroup_code': subgroup['species_code'], 'parent_code': parent['species_code'],
                'values': {field: row.get(field) for field, _, _ in FIELDS.values()},
                'inference': row['Inference'], 'inferred_fields': row.get('Traits.inferred'),
                'reference_species': row.get('Reference.species'), 'sample_size': row.get('Total.individuals'),
                'mass_source': row.get('Mass.Source'), 'mass_reference': row.get('Mass.Refs.Other'),
            }
    return {
        'schema_version': 1, 'taxonomy_release': PINS['taxonomy'][0], 'taxonomy_sha256': PINS['taxonomy'][1],
        'source_release': PINS['avonet'][0], 'source_sha256': PINS['avonet'][1],
        'source_url': PINS['avonet'][2], 'license_name': PINS['avonet'][3],
        'relationship_source': {'release': 'eBird-v2025', 'url': EBIRD_URL, 'sha256': EBIRD_SHA256,
                                'sheet': 'full_sparse', 'fields': ['category', 'bio_concept_code', 'report_as', 'species_code']},
        'policy': 'Only unique source concept -> eBird category issf -> report_as species -> identical AviList species concept; subordinate observations do not represent whole species means. All distinct subgroups retained; eBird sheet preferred within same concept. Only missing primary fields supplemented.',
        'entries': [selected[k] for k in sorted(selected)],
    }


def main():
    import openpyxl
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True); p.add_argument('--ebird', type=Path, required=True)
    p.add_argument('--output', type=Path, default=OUTPUT); p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if hashlib.sha256(args.ebird.read_bytes()).hexdigest() != EBIRD_SHA256: raise ValueError('eBird hash mismatch')
    base.verify_hashes({key: args.raw_dir / name for key, name in base.RAW_NAMES.items()}, base.load_pins())
    avilist = base.read_avilist(args.raw_dir / base.RAW_NAMES[base.AVILIST_ID])
    base.AVONET_SHEETS['avonet2'] = 'AVONET2_eBird'; base.AVONET_REQUIRED['avonet2'] = ['Species2', 'Avibase.ID2']
    rows = base.read_avonet(args.raw_dir / base.RAW_NAMES[base.AVONET_ID])
    w = openpyxl.load_workbook(args.ebird, read_only=True, data_only=True)
    cells = w['full_sparse'].iter_rows(values_only=True); header = next(cells)
    keys = ['category', 'species_code', 'bio_concept_code', 'sci_name', 'report_as', 'primary_com_name']
    taxonomy = [{key: row[header.index(key)] for key in keys} for row in cells]; w.close()
    payload = build(avilist, taxonomy, {'AVONET1_BirdLife': rows['avonet1'], 'AVONET2_eBird': rows['avonet2']})
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if args.check:
        if args.output.read_bytes() != raw: raise ValueError('Subgroup extract differs from source')
    else: args.output.write_bytes(raw)
    print(json.dumps({'entries': len(payload['entries']), 'species': len({e['target_sequence'] for e in payload['entries']}), 'sha256': hashlib.sha256(raw).hexdigest(), 'checked': args.check}))


if __name__ == '__main__': main()
