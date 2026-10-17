#!/usr/bin/env python3
"""Build the release-scoped Korea (KR) species distribution bundle.

Positive (`korea`) evidence comes from exactly two pinned sources:
- KOS 2025 한국조류목록 v2.1 official list category 가-1 (wild record in Korea),
  as already bound to AviList species in species_ko_names.json;
- AviList v2025b range text that names Korea or the Korean Peninsula, read
  from the species row or, when the species row has no range, a direct
  subspecies row. Every north qualifier, negation, past, introduced, vagrant
  or surrounding-waters ambiguity fails closed.

`outside` is only a short manual review of New Zealand island endemics whose
exact source wording is pinned. Absence of Korea text, a missing Korean name
or KOS 가-2 (North Korea only) never yields a status: those stay unknown.
No seasonal/residency status is derived from any source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL = ROOT / 'src' / 'robingraph' / 'retrieval'
AVILIST_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
KOS_SHA256 = 'b660e125a35abc00df77aa61f3ba24997de7fe1d213ef1350ceacfe08466ba7a'
TAXONOMY_RELEASE = 'v2025b'
CONCEPT_SET_ID = 'rg:concept-set:avilist-v2025b'
AVILIST_SOURCE = {
    'id': 'avilist-v2025b', 'title': 'AviList v2025b (Explorer JSON)',
    'url': 'https://explore.avilist.org/data/avilist-2025b.json',
    'landing_url': 'https://www.avilist.org/checklist/v2025b/', 'sha256': AVILIST_SHA256,
    'license_name': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
    'field': 'range (column 13) of species and direct subspecies rows'}
KOS_CATEGORY_DEFINITIONS = {
    '가-1': '야생에서 관찰되었으며, 기록의 근거가 명확한 종',
    '가-2': '남한의 기록은 없으나, 북한에는 서식하거나 기록의 근거가 명확한 종'}
KOS_USE_NOTE = '본 목록은 이용자가 형식을 변경하는 등 자유롭게 가공하여 사용 가능합니다.'

# Manual review (Claude agent, 2026-10-17; not an independent human review):
# current, non-historical ranges limited to New Zealand islands, with no
# Korea text, no KOS label and no subspecies rows. Wording changes fail.
REVIEWED_OUTSIDE = (
    ('28', 'Apteryx maxima', 'montane forest of northwestern South Island (New Zealand)'),
    ('32', 'Apteryx rowi', 'Okarito Forest (west coast of South Island, New Zealand)'),
    ('33', 'Apteryx mantelli', 'North Island (New Zealand)'),
    ('11283', 'Nestor notabilis', 'mountains of South Island (New Zealand)'),
    ('12333', 'Xenicus gilviventris', 'high mountains of South Island (New Zealand)'),
    ('20393', 'Callaeas wilsoni', 'North and Great Barrier islands (New Zealand)'),
)
OUTSIDE_REVIEW = ('Claude agent manual review 2026-10-17 of exact AviList range wording: current range '
                  'restricted to New Zealand islands; not an independent human review.')

KOREA_MENTION = re.compile(r'\bKorea\w*')
ALLOWED_QUALIFIERS = {'south', 'southern', 'southeastern', 'southwestern', 's', 'se', 'sw'}
DIRECTIONAL = re.compile(r'^(?:north\w*|south\w*|east\w*|west\w*|central|[nsew]{1,2}|far|inland|coastal|peninsular)$')
UNCERTAIN_TEXT = re.compile(
    r'\b(?:former\w*|extinct\w*|extirpat\w*|historic\w*|once|introduc\w*|feral|escape\w*|releas\w*|'
    r'vagrant\w*|accidental\w*|casual\w*|possibl\w*|probabl\w*|perhaps|unconfirmed|uncertain\w*|'
    r'not|absent|except\w*|exclud\w*|no\s+longer)\b|\?', re.IGNORECASE)
MARINE_TEXT = re.compile(r'\b(?:waters?|seas?|ocean\w*|offshore|strait\w*|pelagic)\b', re.IGNORECASE)


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def taxon_id(sequence):
    return f'avilist-taxon:{TAXONOMY_RELEASE}:{sequence}'


def korea_text_review(text):
    """Return (accepted, reasons) for one AviList range string; fail closed."""
    if not isinstance(text, str) or not KOREA_MENTION.search(text):
        return False, ['no_korea_text']
    reasons = []
    if UNCERTAIN_TEXT.search(text):
        reasons.append('negation_past_introduced_or_uncertain_wording')
    for clause in text.split(';'):
        mentions = list(KOREA_MENTION.finditer(clause))
        if mentions and MARINE_TEXT.search(clause):
            reasons.append('surrounding_waters_ambiguous')
        for mention in mentions:
            word = mention.group(0)
            after = clause[mention.end():].lstrip().lower()
            if word == 'Korean' and not after.startswith('peninsula'):
                reasons.append('ambiguous_korean_mention')
            elif word not in ('Korea', 'Korean'):
                reasons.append('ambiguous_korean_mention')
            before = clause[:mention.start()].rstrip()
            previous = re.findall(r"[A-Za-z.]+$", before)
            qualifier = previous[0].rstrip('.').lower() if previous and not before.endswith(',') else ''
            if qualifier.startswith('north') or qualifier in ('n', 'ne', 'nw'):
                reasons.append('north_qualified')
            elif qualifier and DIRECTIONAL.match(qualifier) and qualifier not in ALLOWED_QUALIFIERS:
                reasons.append('non_south_directional_qualifier')
    reasons = sorted(set(reasons))
    return not reasons, reasons


def avilist_rows(content):
    rows = json.loads(content)
    species, current = {}, None
    for row in rows:
        if row[1] == 'species':
            current = row
            species[row[0]] = {'row': row, 'subspecies': []}
        elif row[1] == 'subspecies':
            if current is None or not row[5].startswith(current[5] + ' '):
                raise ValueError(f'Subspecies {row[5]} is not under its parent species row')
            species[current[0]]['subspecies'].append(row)
    return species


def avilist_evidence(row, rank):
    return {'source_id': AVILIST_SOURCE['id'], 'source_url': AVILIST_SOURCE['url'],
            'source_title': AVILIST_SOURCE['title'], 'source_taxon_id': taxon_id(row[0]),
            'source_rank': rank, 'source_scientific_name': row[5], 'source_text': row[13],
            'source_text_sha256': sha256(row[13]), 'source_sha256': AVILIST_SHA256}


def build(avilist_content, names, ko_names_sha256=None, generator_sha256=None):
    if sha256(avilist_content) != AVILIST_SHA256:
        raise ValueError('AviList snapshot changed; review the release before building')
    if (names.get('taxonomy_release') != TAXONOMY_RELEASE or names.get('concept_set_id') != CONCEPT_SET_ID
            or names.get('source_sha256') != KOS_SHA256):
        raise ValueError('KOS label bundle release or snapshot mismatch')
    species = avilist_rows(avilist_content)
    by_id = {taxon_id(sequence): entry['row'] for sequence, entry in species.items()}
    kos_source = {'id': 'kos-2025-v2.1', 'title': names['source_title'], 'url': names['source_url'],
                  'download_url': names['source_download_url'], 'sha256': KOS_SHA256, 'as_of': '2025-05',
                  'source_taxonomy': 'IOC World Bird List v15.1', 'license_name': None, 'use_note': KOS_USE_NOTE,
                  'sheet': '공식목록', 'category_definitions': KOS_CATEGORY_DEFINITIONS,
                  'crosswalk': 'species_ko_names.json exact AviList taxon ID and scientific name'}
    taxa, unknown_audit, rejected_text = {}, {}, {}

    def add(tid, status, evidence):
        row = by_id[tid]
        entry = taxa.setdefault(tid, {'scientific_name': row[5], 'status': status, 'evidence': []})
        if entry['status'] != status:
            raise ValueError(f'Conflicting distribution status for {tid}')
        entry['evidence'].append(evidence)

    kos_ga2 = set()
    for tid, label in sorted(names['labels'].items()):
        if label.get('source_sheet') != '공식목록' or label.get('source_title') != names['source_title']:
            continue
        row = by_id.get(tid)
        if row is None or row[5] != label['scientific_name']:
            raise ValueError(f'KOS label {tid} does not match the pinned AviList species')
        category = label.get('category')
        if category == '가-2':
            kos_ga2.add(tid)
            unknown_audit[tid] = {'scientific_name': row[5], 'reasons': ['kos_ga2_north_korea_only']}
            continue
        if category != '가-1':
            raise ValueError(f'Unexpected KOS category for {tid}')
        add(tid, 'korea', {
            'source_id': kos_source['id'], 'source_url': kos_source['url'], 'source_title': kos_source['title'],
            'source_taxon_id': f"kos-2025-v2.1:공식목록:row-{label['source_row']}", 'source_rank': 'species',
            'source_scientific_name': label['source_scientific_name'], 'source_text': None,
            'category': category, 'category_definition': KOS_CATEGORY_DEFINITIONS[category],
            'source_sha256': KOS_SHA256, 'geography_basis': 'kos_official_list_wild_record_korea'})

    for sequence, entry in species.items():
        tid, row = taxon_id(sequence), entry['row']
        candidates = [(row, 'species')] if row[13] else [(sub, 'subspecies') for sub in entry['subspecies']]
        for source_row, rank in candidates:
            accepted, reasons = korea_text_review(source_row[13])
            if reasons == ['no_korea_text']:
                continue
            evidence = {**avilist_evidence(source_row, rank), 'geography_basis': 'avilist_range_names_korea'}
            if not accepted:
                rejected_text.setdefault(tid, {'scientific_name': row[5], 'rows': []})['rows'].append(
                    {**evidence, 'geography_basis': None, 'reasons': reasons})
            elif tid in kos_ga2:
                unknown_audit[tid]['reasons'].append('avilist_korea_text_conflicts_with_kos_ga2')
                unknown_audit[tid].setdefault('rows', []).append(evidence)
            else:
                add(tid, 'korea', evidence)

    for sequence, science, text in REVIEWED_OUTSIDE:
        tid, entry = taxon_id(sequence), species.get(sequence)
        if (entry is None or entry['row'][5] != science or entry['row'][13] != text or entry['subspecies']
                or KOREA_MENTION.search(text) or tid in taxa
                or names['labels'].get(tid, {}).get('source_sheet') == '공식목록'):
            raise ValueError(f'Reviewed outside taxon {science} no longer matches its review')
        add(tid, 'outside', {**avilist_evidence(entry['row'], 'species'),
                             'geography_basis': 'avilist_range_reviewed_outside_kr', 'review': OUTSIDE_REVIEW})

    for tid, entry in taxa.items():
        bases = {item['geography_basis'] for item in entry['evidence']}
        entry['basis'] = ('reviewed_source_range_outside_kr' if entry['status'] == 'outside'
                          else 'source_record_and_range_korea' if len(bases) > 1
                          else 'source_record_korea' if 'kos_official_list_wild_record_korea' in bases
                          else 'source_range_korea')
    korea = [entry for entry in taxa.values() if entry['status'] == 'korea']
    counts = {
        'active_species': len(species),
        'korea': len(korea),
        'korea_kos_only': sum(entry['basis'] == 'source_record_korea' for entry in korea),
        'korea_avilist_only': sum(entry['basis'] == 'source_range_korea' for entry in korea),
        'korea_both': sum(entry['basis'] == 'source_record_and_range_korea' for entry in korea),
        'outside': sum(entry['status'] == 'outside' for entry in taxa.values()),
        'unknown': len(species) - len(taxa),
        'kos_ga2_unknown': len(kos_ga2),
        'avilist_korea_text_rejected_species': len(rejected_text),
        'avilist_korea_text_rejected_rows': sum(len(item['rows']) for item in rejected_text.values()),
    }
    return {
        'schema_version': 1, 'taxonomy_release': TAXONOMY_RELEASE, 'concept_set_id': CONCEPT_SET_ID,
        'geographic_scope': 'KR',
        'generator': {'path': 'scripts/build_species_distribution.py', 'sha256': generator_sha256},
        'inputs': {'avilist_sha256': AVILIST_SHA256,
                   'species_ko_names': {'path': 'src/robingraph/retrieval/species_ko_names.json',
                                        'sha256': ko_names_sha256}},
        'scope_note': ('국명·번역·로고와 독립적으로 출처의 지리 문구와 KOS 범주만 검토했습니다. '
                       'korea는 계절과 무관한 국내 야생 기록·분포 근거이며 텃새·정착·현재 서식을 뜻하지 않습니다.'),
        'policy': ('korea = KOS 가-1 wild record or AviList range naming Korea/Korean Peninsula without north, '
                   'negation, past, introduced, vagrant or surrounding-waters ambiguity; any season, not residency. '
                   'outside = manually reviewed source range outside KR; not proof of no vagrant or captive record. '
                   'Everything else, including KOS 가-2 (North Korea only), is unknown, not outside. '
                   'seasonal_status is never derived.'),
        'sources': {AVILIST_SOURCE['id']: AVILIST_SOURCE, kos_source['id']: kos_source},
        'counts': counts,
        'taxa': dict(sorted(taxa.items(), key=lambda item: int(item[0].rsplit(':', 1)[1]))),
        'unknown_audit': dict(sorted(unknown_audit.items())),
        'rejected_korea_text': dict(sorted(rejected_text.items())),
    }


def render(bundle):
    return json.dumps(bundle, ensure_ascii=False, indent=1) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--avilist', type=Path, required=True)
    parser.add_argument('--ko-names', type=Path, default=RETRIEVAL / 'species_ko_names.json')
    parser.add_argument('--output', type=Path, default=RETRIEVAL / 'species_distribution.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    ko_names = args.ko_names.read_bytes()
    bundle = build(args.avilist.read_bytes(), json.loads(ko_names), sha256(ko_names),
                   sha256(Path(__file__).read_bytes()))
    text = render(bundle)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding='utf-8') != text:
            print('species distribution bundle is stale', file=sys.stderr)
            return 1
    else:
        args.output.write_text(text, encoding='utf-8')
    print(json.dumps(bundle['counts'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
