#!/usr/bin/env python3
"""Resolve every baseline-empty taxon against all three AVONET taxonomies.

Evidence audit only: broad species-complex and subordinate data are distinct
from matching species data. This script does not invent values or write a DB.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json

import build_trait_crosswalk as base
from build_avonet_subgroup_supplement import EBIRD_SHA256, EBIRD_URL, concept

ROOT = Path(__file__).resolve().parents[1]


def audit(baseline, avilist, sheets, taxonomy, exact, subordinate):
    empty = [r for r in baseline['species'] if not r['trait_names']]
    avilist_byname = {r['Scientific_name']: r for r in avilist if r['Taxon_rank'] == 'species'}
    children = defaultdict(list); parent = None
    for row in avilist:
        if row['Taxon_rank'] == 'species': parent = row['Scientific_name']
        elif row['Taxon_rank'] == 'subspecies': children[parent].append(row)
    recovered = {e['target_name']: e for e in exact['entries']}
    bounded = defaultdict(list)
    for e in subordinate['entries']: bounded[e['target_name']].append(e)
    broad = defaultdict(list)
    for row in taxonomy:
        if row['category'] in ('slash', 'spuh'): broad[concept(row['bio_concept_code'])].append(row)
    rows = []
    for item in sorted(empty, key=lambda r: r['scientific_name']):
        name = item['scientific_name']; target = avilist_byname[name]
        direct = []; subsets = []; broader = []
        for key, column, id_column in [('avonet1', 'Species1', 'Avibase.ID1'), ('avonet2', 'Species2', 'Avibase.ID2'), ('avonet3', 'Species3', None)]:
            for source in sheets[key]:
                ident = concept(source.get(id_column)) if id_column else None
                if source[column] == name:
                    direct.append({'sheet': key, 'source_name': name, 'source_row': source['_row'], 'source_concept_id': ident,
                                   'concept_id_equal': bool(ident and ident == concept(target['AvibaseID']))})
                if not ident: continue
                for child in children[name]:
                    if child['AvibaseID'] and concept(child['AvibaseID']) == ident:
                        subsets.append({'sheet': key, 'source_name': source[column], 'source_row': source['_row'],
                                        'current_subspecies': child['Scientific_name'], 'avibase_id': child['AvibaseID']})
                for group in broad[ident]:
                    parts = (group['sci_name'] or '').split('/')
                    if not parts or ' ' not in parts[0]: continue
                    genus = parts[0].split()[0]
                    members = [part if ' ' in part else genus + ' ' + part for part in parts]
                    if name in members:
                        broader.append({'sheet': key, 'source_name': source[column], 'source_row': source['_row'],
                                        'source_avibase_id': ident, 'broader_group': group['sci_name'],
                                        'members': members, 'category': group['category']})
        entry = recovered.get(name)
        disposition = ('recovered_exact_concept_ebird' if entry else 'bounded_subgroup_reference_only' if bounded[name]
                       else 'broader_multi_species_source_not_assignable' if broader else 'same_name_source_concept_not_equal' if direct
                       else 'subspecies_only_source_scope' if subsets else 'no_direct_name_or_subspecies_concept_source')
        rows.append({'taxon_id': item['taxon_id'], 'scientific_name': name, 'target_avibase_id': target['AvibaseID'],
                     'disposition': disposition, 'source_inference': entry['inference'] if entry else None,
                     'source_reference_species': entry['reference_species'] if entry else None,
                     'exact_name_rows': direct, 'subspecies_rows': subsets,
                     'subgroup_evidence': [{k: e[k] for k in ('source_sheet', 'source_name', 'subgroup_name', 'source_row', 'source_avibase_id', 'target_avibase_id')} for e in bounded[name]],
                     'broader_source_evidence': broader, 'avilist_decision_summary': target['Decision_summary']})
    return {'total': len(rows), 'disposition_counts': dict(Counter(r['disposition'] for r in rows)),
            'recovered_source_inference': dict(Counter(r['source_inference'] for r in rows if r['disposition'] == 'recovered_exact_concept_ebird')),
            'source_sheets_checked': ['AVONET1_BirdLife', 'AVONET2_eBird', 'AVONET3_BirdTree'],
            'additional_relationship_source': {'url': EBIRD_URL, 'sha256': EBIRD_SHA256, 'sheet': 'full_sparse', 'release': 'eBird-v2025'},
            'policy': 'AVONET3 has no concept IDs. Broad complexes do not establish values for each member. Scoped subgroups are never parent species means. No direct source candidate is not proof that no other literature exists.',
            'species': rows}


def main():
    import openpyxl
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir', type=Path, required=True); p.add_argument('--ebird', type=Path, required=True)
    p.add_argument('--baseline', type=Path, default=ROOT/'docs/verification/assets/2026-10-09-active-species-runtime-audit.json')
    p.add_argument('--output', type=Path, default=ROOT/'docs/verification/assets/2026-10-09-trait503-source-resolution.json')
    args = p.parse_args()
    if hashlib.sha256(args.ebird.read_bytes()).hexdigest() != EBIRD_SHA256: raise ValueError('eBird hash mismatch')
    base.verify_hashes({key: args.raw_dir / name for key, name in base.RAW_NAMES.items()}, base.load_pins())
    avilist = base.read_avilist(args.raw_dir / base.RAW_NAMES[base.AVILIST_ID])
    base.AVONET_SHEETS['avonet2'] = 'AVONET2_eBird'; base.AVONET_REQUIRED['avonet2'] = ['Species2', 'Avibase.ID2']
    sheets = base.read_avonet(args.raw_dir / base.RAW_NAMES[base.AVONET_ID])
    w = openpyxl.load_workbook(args.ebird, read_only=True, data_only=True)
    cells = w['full_sparse'].iter_rows(values_only=True); header = next(cells)
    keys = ['category', 'species_code', 'bio_concept_code', 'sci_name', 'report_as', 'primary_com_name']
    taxonomy = [{key: row[header.index(key)] for key in keys} for row in cells]; w.close()
    retrieval = ROOT / 'src/robingraph/retrieval'
    result = audit(json.loads(args.baseline.read_text()), avilist, sheets, taxonomy,
                   json.loads((retrieval/'avonet_ebird_supplement.json').read_text()),
                   json.loads((retrieval/'avonet_subgroup_supplement.json').read_text()))
    # Preserve the AVONET-only diagnosis, then apply the independently published
    # AviList-aware BIRDBASE source. No empty source value is manufactured.
    birdbase = json.loads((retrieval / 'birdbase_traits.json').read_text())
    bb_index = {e['target_name']: e for e in birdbase['entries']}
    result['avonet_disposition_counts'] = result['disposition_counts']
    for row in result['species']:
        row['avonet_disposition'] = row['disposition']
        e = bb_index.get(row['scientific_name'])
        if e is not None:
            row['birdbase_evidence'] = {key: e[key] for key in ('source_row', 'source_name', 'source_references',
                'target_name', 'target_family', 'body_mass', 'mass_bounds', 'habitat', 'diet_category', 'diet_literature')}
            if row['disposition'] != 'recovered_exact_concept_ebird' and e['habitat']:
                row['disposition'] = 'recovered_author_avilist_birdbase'
    result['disposition_counts'] = dict(Counter(r['disposition'] for r in result['species']))
    result['birdbase_source'] = {key: birdbase[key] for key in ('source_url', 'source_release', 'source_sha256', 'license_name', 'source_taxonomy_field')}
    result['verification_scope'] = 'Pinned published source and mapping audit; actual TEST/Production read_traits coverage is independently measured by the runtime audit.'
    result['baseline_sha256'] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['disposition_counts']))


if __name__ == '__main__': main()
