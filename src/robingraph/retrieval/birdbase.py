"""Pinned BIRDBASE literature compilation; explicit author AviList crosswalk."""
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path

from robingraph.ingest.collection_points import default_config_root
from robingraph.ingest.validation import validate_source_registry_record
from .trait_mapping import PINS

SOURCE_ID = 'traits-birdbase-v2025-1'
SOURCE_URL = 'https://ndownloader.figshare.com/files/55634729'
SOURCE_SHA256 = 'cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b'
SOURCE_RELEASE = 'figshare-27051040-v1:file-55634729'
ARTIFACT_SHA256 = 'e891b76cc809f843ba38758d713f3427d396d073037911c01ca1d758b30ca7ab'
HABITAT_LABELS = {'Artificial': '인공·변형 환경', 'Bamboo': '대나무 숲', 'Coastal': '해안', 'Desert': '사막',
                  'Forest': '숲', 'Grassland': '초지', 'Plains': '평원', 'Riparian': '하천 주변', 'Rocky': '바위 지대',
                  'Savanna': '사바나', 'Sea': '바다', 'Shrub': '관목 지대', 'Wetland': '습지', 'Woodland': '성긴 숲'}
DIET_LABELS = {'Beeswax': '밀랍', 'Carnivore': '육식', 'Fish': '물고기', 'Fruit': '열매', 'Herbivore': '초식',
               'Invertebrate': '무척추동물', 'Nectar': '꽃꿀', 'Omnivore': '잡식', 'Ovivore': '알',
               'Plant': '식물', 'Scavenger': '사체 섭식', 'Seed': '씨앗', 'Vertebrate': '척추동물'}


@lru_cache(maxsize=2)
def _registry_allowed(path, modified, size):
    try:
        records = json.loads(Path(path).read_text())
        entries = [r for r in records if isinstance(r, dict) and r.get('source_id') == SOURCE_ID]
        if len(entries) != 1: return False
        entry = entries[0]
        return (not validate_source_registry_record(entry) and entry.get('enabled') is True
                and entry.get('license_policy_status') == 'allowed'
                and entry.get('license_name') == 'CC BY 4.0'
                and entry.get('license_uri') == 'https://creativecommons.org/licenses/by/4.0/'
                and entry.get('landing_uri') == 'https://doi.org/10.6084/m9.figshare.27051040.v1')
    except (OSError, ValueError, TypeError):
        return False


def source_allowed():
    path = default_config_root() / 'source-registry.json'
    try:
        stat = path.stat()
        return _registry_allowed(str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return False


@lru_cache(maxsize=1)
def birdbase_index():
    try:
        raw = Path(__file__).with_name('birdbase_traits.json').read_bytes()
        if sha256(raw).hexdigest() != ARTIFACT_SHA256: return {}
        data = json.loads(raw)
        expected = {'schema_version': 1, 'source_id': SOURCE_ID, 'source_url': SOURCE_URL,
                    'source_release': SOURCE_RELEASE, 'source_sha256': SOURCE_SHA256, 'license_name': 'CC BY 4.0',
                    'taxonomy_release': PINS['taxonomy'][0], 'taxonomy_sha256': PINS['taxonomy'][1],
                    'source_taxonomy_field': 'AviList v1 2025'}
        if any(data.get(k) != v for k, v in expected.items()): return {}
        result = {entry['target_sequence']: entry for entry in data['entries']}
        return result if len(result) == len(data['entries']) == 11131 else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def birdbase_traits(lineage, traits, labels):
    result = list(traits)
    if (not lineage.items or lineage.taxonomy_source != 'AviList'
            or lineage.taxonomy_release != 'v2025b' or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'
            or not source_allowed()): return result
    target = lineage.items[-1]; prefix = 'avilist-taxon:v2025b:'
    if target.rank != 'species' or not target.taxon_id.startswith(prefix): return result
    entry = birdbase_index().get(target.taxon_id[len(prefix):])
    if not entry or entry['target_name'] != target.scientific_name: return result
    existing = {t.get('name') for t in result if t.get('source_scope_kind') != 'subspecies_group'}
    row_url = SOURCE_URL + '#sheet=Data&row=' + str(entry['source_row'])
    fields = [('body_mass', 'Average Mass', entry['body_mass']), ('habitat', 'Primary Habitat', entry['habitat']),
              ('diet_category', 'Primary Diet', entry['diet_category'])]
    for name, field, value in fields:
        if name in existing or name not in labels or value in (None, '', 'No Information'): continue
        inferred = name == 'diet_category' and entry['diet_literature'] == 0
        if name == 'body_mass':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0: continue
            text = format(value, '.2f').rstrip('0').rstrip('.')
            label = labels[name] + ' · 문헌 범위 평균'
            statistic = 'literature_bounds_mean'
            note = '문헌의 암컷·수컷·성별 미구분 최소·최대값을 저자가 평균한 값이며, 측정 개체 전체의 표본 평균이 아닙니다.'
            bound_labels = {'Female MinMass': '암컷 최소', 'Female MaxMass': '암컷 최대', 'Male MinMass': '수컷 최소', 'Male MaxMass': '수컷 최대', 'Unsexed MinMass': '성별 미구분 최소', 'Unsexed MaxMass': '성별 미구분 최대'}
            bounds = [bound_labels[key] + ' ' + format(amount, '.4g') + ' g' for key, amount in entry['mass_bounds'].items() if isinstance(amount, (int, float)) and not isinstance(amount, bool)]
            if bounds: note += ' 문헌 원값: ' + ' · '.join(bounds) + '.'
        else:
            translations = HABITAT_LABELS if name == 'habitat' else DIET_LABELS
            if value not in translations: continue
            text = translations[value]; label = labels[name]; statistic = 'literature_category'
            note = '문헌과 저자 관찰을 종합한 원저자 분류 범주입니다.'
            if inferred: note += ' Diet_Lit=0: 원저자가 보간한 먹이 정보입니다.'
            elif name == 'diet_category': note += ' Diet_Lit=1: 발표된 먹이 문헌에 근거합니다.'
        note += ' 분류 연결은 원저자의 AviList 대응열에 근거합니다. 원자료 문헌 코드: ' + entry['source_references']
        result.append({
            'name': name, 'label': label, 'value': value, 'display': text, 'unit': 'g' if name == 'body_mass' else None,
            'inferred': inferred, 'summary_statistic': statistic, 'source_field': field,
            'source_id': SOURCE_ID, 'dataset_id': 'birdbase:' + SOURCE_RELEASE, 'release': SOURCE_RELEASE,
            'source_name': 'BIRDBASE v2025.1 · 문헌 종합', 'source_url': row_url + '&field=' + field,
            'citation': 'Şekercioğlu et al. (2025), BIRDBASE; doi:10.1038/s41597-025-05615-3; Figshare 27051040 v1',
            'license_name': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'source_note': note, 'source_references': entry['source_references'],
            'source_mass_bounds': entry['mass_bounds'] if name == 'body_mass' else None,
            'source_diet_literature': entry['diet_literature'] if name == 'diet_category' else None,
            'evidence_kind': 'packaged_source_extract', 'source_record_id': None, 'source_snapshot_sha256': SOURCE_SHA256,
            'taxonomy_alignment': {'status': 'accepted', 'method': 'author_avilist_column',
                'source_scientific_name': entry['source_name'], 'target_scientific_name': target.scientific_name,
                'source_taxonomy_field': 'AviList v1 2025', 'reason': None},
            'mapping_provenance': {'source_sheet': 'Data', 'source_row': entry['source_row'],
                'source_taxonomy_field': 'AviList v1 2025', 'source_taxonomy_value': entry['target_name'],
                'source_avilist_family': entry['target_family'], 'target_avibase_id': entry['target_avibase_id'],
                'taxonomy_snapshot_sha256': PINS['taxonomy'][1], 'extract_sha256': ARTIFACT_SHA256,
                'species_set_equality_count': 11131},
        })
    return result
