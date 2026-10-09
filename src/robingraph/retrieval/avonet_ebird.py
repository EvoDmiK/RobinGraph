"""Source-pinned author-published eBird aggregates for verified concept gaps."""
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path

from .trait_mapping import FIELDS, PINS, active_provenance

ARTIFACT_SHA256 = '3b9995a9576ec7ca13cc25ed66aba83143d40c7d66058a062f714883f07aca2c'
SHEET = 'AVONET2_eBird'


@lru_cache(maxsize=1)
def supplement_index():
    try:
        raw = Path(__file__).with_name('avonet_ebird_supplement.json').read_bytes()
        if sha256(raw).hexdigest() != ARTIFACT_SHA256:
            return {}
        data = json.loads(raw)
        expected = {
            'schema_version': 1, 'taxonomy_release': PINS['taxonomy'][0],
            'taxonomy_sha256': PINS['taxonomy'][1], 'source_release': PINS['avonet'][0],
            'source_sha256': PINS['avonet'][1], 'source_url': PINS['avonet'][2],
            'license_name': PINS['avonet'][3], 'source_sheet': SHEET,
        }
        if any(data.get(k) != v for k, v in expected.items()):
            return {}
        entries = data['entries']
        result = {str(e['target_sequence']): e for e in entries}
        return result if len(result) == len(entries) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def supplement_traits(lineage, traits, context, labels, display):
    """Fill absent fields; pin taxonomy and active allowed source before use.

    The evidence is a packaged extract of a hash-verified workbook sheet. It does
    not pretend to have been ingested into either DB. Source inferred fields
    stay inferred and reference species are always carried in the source note.
    """
    result = list(traits)
    if not lineage.items or not active_provenance(context, 'avonet', lineage):
        return result
    target = lineage.items[-1]
    if (target.rank != 'species' or lineage.taxonomy_source != 'AviList'
            or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'):
        return result
    prefix = 'avilist-taxon:v2025b:'
    if not target.taxon_id.startswith(prefix):
        return result
    entry = supplement_index().get(target.taxon_id[len(prefix):])
    if not entry or entry['target_name'] != target.scientific_name:
        return result
    existing = {t.get('name') for t in result}
    result.extend(t for t in entry_traits(entry, target, labels, display) if t['name'] not in existing)
    return result


def entry_traits(entry, target, labels, display):
    """Normalize an attributable author-published source row without averaging."""
    result = []
    sheet = entry.get('source_sheet', SHEET)
    inferred = {s.strip().lower() for s in (entry['inferred_fields'] or '').split(';')}
    source_url = PINS['avonet'][2] + '#sheet=' + sheet + '&row=' + str(entry['source_row'])
    for name, (field, unit, inferred_label) in FIELDS.items():
        if name not in labels:
            continue
        raw = entry['values'].get(field)
        if raw is None or raw in ('NA', ''):
            continue
        if unit:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value) or value <= 0:
                continue
        else:
            value = {'1': 'dense', '2': 'semi_open', '3': 'open'}.get(raw) if name == 'habitat_density_category' else raw
            if not value:
                continue
        is_inferred = bool(inferred_label and inferred_label.lower() in inferred)
        taxonomy_label = 'eBird' if sheet == SHEET else 'BirdLife'
        morphology_count = int(float(entry['sample_size']))
        note = '저자가 ' + taxonomy_label + ' 분류로 집계한 AVONET 원자료'
        note += '; 형태측정 대상 총 ' + str(morphology_count) + '개체(개별 형질의 유효 표본수나 체중 문헌의 표본수가 아닙니다)'

        if is_inferred:
            note += '; 저자 추정값; 참조 종: ' + str(entry['reference_species'])
        if name == 'body_mass':
            note += '; 체중 출처: ' + str(entry['mass_source'])
            if entry['mass_reference'] not in (None, 'NA', ''):
                note += '; ' + entry['mass_reference']
        result.append({
            'name': name, 'label': labels[name], 'value': value, 'display': display(name, value),
            'unit': unit, 'inferred': is_inferred,
            'summary_statistic': ('species_estimate' if is_inferred else 'species_mean') if unit else 'species_category',
            'dataset_id': 'avonet-ebird:' + PINS['avonet'][0], 'release': PINS['avonet'][0],
            'source_name': 'AVONET · eBird 분류 집계', 'source_url': source_url + '&field=' + field,
            'citation': 'Tobias et al. (2022), AVONET; Figshare 16586228 v7, ' + sheet,
            'license_name': PINS['avonet'][3], 'source_field': field, 'source_note': note,
            'evidence_kind': 'packaged_source_extract', 'source_snapshot_sha256': PINS['avonet'][1],
            'source_record_id': None, 'source_morphology_sample_size': morphology_count,
            'taxonomy_alignment': {'status': 'accepted', 'method': 'avibase_id_unique',
                'source_scientific_name': entry['source_name'], 'target_scientific_name': target.scientific_name,
                'reason': None},
            'mapping_provenance': {'source_sheet': sheet, 'source_row': entry['source_row'],
                'avibase_id': entry.get('avibase_id', entry.get('source_avibase_id')), 'taxonomy_snapshot_sha256': PINS['taxonomy'][1],
                'extract_sha256': ARTIFACT_SHA256, 'source_inference': entry['inference'],
                'source_reference_species': entry['reference_species']},
        })
    return result
