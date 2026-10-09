"""Release-scoped public checklist evidence; no live API or inferred grades."""
from functools import lru_cache
import json
from pathlib import Path
import re

DATASET_KEY = '19491596-35ae-4a91-9a98-85cf505f1bd3'
SOURCE_URL = f'https://www.gbif.org/dataset/{DATASET_KEY}'
SOURCE_SHA256 = '2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d'
TAXONOMY_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
METHOD = 'exact_avilist_birdlife_sis_and_scientific_name'
LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
PUBLISHER = 'International Union for Conservation of Nature'
CATEGORIES = frozenset(('LC', 'NT', 'VU', 'EN', 'CR', 'EW', 'EX', 'DD'))


def manual_magpie_override(lineage, snapshot):
    """User-requested display correction, separate from assessment evidence."""
    taxon = lineage.items[-1]
    if (lineage.taxonomy_source != 'AviList' or lineage.taxonomy_release != 'v2025b'
            or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'
            or taxon.taxon_id != 'avilist-taxon:v2025b:20193'
            or taxon.rank != 'species' or taxon.scientific_name != 'Pica serica'
            or snapshot.get('evidence_kind') != 'taxonomy_snapshot'
            or snapshot.get('assessment_status') != 'needs_review'
            or snapshot.get('category') != 'NE'
            or snapshot.get('snapshot_sha256') != TAXONOMY_SHA256):
        return None
    reason = ('까치의 앱 표시 등급은 LC입니다. '
              '원자료의 NE와 평가 종 범위 확인 필요 상태는 별도로 보존합니다.')
    return dict(category='LC', category_raw='LC', label='관심대상',
                source_id='robingraph-manual-pica-serica', source_name='RobinGraph 보전 등급 표시',
                source_release='2026-10-09', source_url=None,
                evidence_kind='manual_override', assessment_status='manual_override',
                independently_verified=False, taxon_id=taxon.taxon_id,
                scientific_name=taxon.scientific_name,
                taxonomy_release=lineage.taxonomy_release, concept_set_id=lineage.concept_set_id,
                taxonomy_category_raw=snapshot['category_raw'],
                original_snapshot=dict(snapshot), override_reason=reason, quality_note=reason)


@lru_cache(maxsize=1)
def _index():
    try:
        value = json.loads(Path(__file__).with_name('conservation_index.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _authority(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def _taxonomy_category(value):
    # The ingest trims source cells; preserve qualifiers while comparing cells.
    return value.strip().upper() if isinstance(value, str) else None


def _authority_match(avilist, assessment):
    """Accept exact authorship or a single author's omitted initials only.

    Years and nomenclatural parentheses are never removed. Multi-author
    notation is eligible only for the exact comparison above this parser.
    """
    if _authority(avilist) and _authority(avilist) == _authority(assessment):
        return 'exact'
    if not isinstance(avilist, str) or not isinstance(assessment, str):
        return None
    left, right = avilist.strip(), assessment.strip()
    enclosed = left.startswith('(') and left.endswith(')')
    if enclosed != (right.startswith('(') and right.endswith(')')):
        return None
    if enclosed:
        left, right = left[1:-1].strip(), right[1:-1].strip()
    if any(character in left + right for character in '();&'):
        return None
    full = re.fullmatch(r'([^,]+),\s*([^,]+),\s*([0-9]{4})', left)
    abbreviated = re.fullmatch(r'([^,]+),\s*([0-9]{4})', right)
    if not full or not abbreviated:
        return None
    surname, initials, year = full.groups()
    initials = initials.strip()
    if (not any(character.isalpha() for character in initials)
            or any(not (character.isalpha() and character.isupper()
                        or character in '.-' or character.isspace()) for character in initials)
            or not surname.strip() or re.search(r'\bet\s+al\b', surname, re.IGNORECASE)
            or _authority(surname) != _authority(abbreviated[1]) or year != abbreviated[2]):
        return None
    return 'single_author_initials_omitted'


def _positive_id(value):
    # bool is an int in Python, but never a source identifier.
    return str(value) if not isinstance(value, bool) and re.fullmatch(r'[1-9][0-9]*', str(value)) else None


def linked_checklist(lineage, snapshot):
    """Upgrade only an exact active AviList concept with pinned source evidence.

    Missing/stale/corrupt bundles leave the existing taxonomy evidence intact.
    A matching name alone, an NE row, or another species' grade cannot upgrade it.
    """
    index = _index()
    source = index.get('source')
    if not isinstance(source, dict):
        return None
    if (index.get('schema_version') != 1
            or index.get('taxonomy_release') != lineage.taxonomy_release
            or index.get('concept_set_id') != lineage.concept_set_id
            or lineage.taxonomy_source != 'AviList'
            or index.get('mapping_method') != METHOD
            or index.get('taxonomy_snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('evidence_kind') != 'taxonomy_snapshot'
            or snapshot.get('category') not in CATEGORIES
            or source.get('dataset_key') != DATASET_KEY
            or source.get('url') != SOURCE_URL
            or source.get('release') != '2026-1'
            or source.get('snapshot_sha256') != SOURCE_SHA256
            or source.get('license_name') != 'CC BY 4.0'
            or source.get('license_url') != LICENSE_URL
            or source.get('publisher') != PUBLISHER
            or not isinstance(source.get('citation'), str)
            or 'https://doi.org/10.15468/0qnb58' not in source['citation']):
        return None
    taxon = lineage.items[-1]
    records = index.get('taxa')
    record = records.get(taxon.taxon_id) if isinstance(records, dict) else None
    if not isinstance(record, dict):
        return None
    sis_id, assessment_id = (_positive_id(record.get(key)) for key in ('sis_id', 'assessment_id'))
    reference = f'https://datazone.birdlife.org/species/factsheet/{sis_id}'
    assessment_url = f'https://www.iucnredlist.org/species/{sis_id}/{assessment_id}'
    citation = record.get('assessment_citation')
    if (taxon.rank != 'species' or record.get('scientific_name') != taxon.scientific_name
            or not _authority(taxon.authority)
            or _authority(record.get('authority')) != _authority(taxon.authority)
            or record.get('authority_match_method') not in ('exact', 'single_author_initials_omitted')
            or _authority_match(record.get('authority'), record.get('assessment_authority')) != record.get('authority_match_method')
            or _taxonomy_category(record.get('taxonomy_category_raw')) != _taxonomy_category(snapshot.get('category_raw'))
            or record.get('category') not in CATEGORIES
            or not sis_id or not assessment_id
            or record.get('mapping_reference_url') != reference
            or snapshot.get('assessment_reference_url') != reference
            or record.get('assessment_reference_url') != assessment_url
            or not isinstance(citation, str)
            or re.findall(r'RLTS\.T([1-9][0-9]*)A([1-9][0-9]*)\.en', citation) != [(sis_id, assessment_id)]):
        return None
    year = record.get('assessment_year')
    if year is not None:
        years = re.findall(r'The IUCN Red List of Threatened Species (\d{4}):', citation)
        doi_years = re.findall(r'IUCN\.UK\.(\d{4})-', citation)
        if (type(year) is not int or len(years) != 1 or years != doi_years
                or int(years[0]) != year):
            return None
    result = {
        'category':record['category'], 'category_raw':record['category'],
        'source_name':'IUCN Red List · GBIF public checklist',
        'source_url':SOURCE_URL, 'source_id':'gbif-iucn-2026-1', 'source_release':'2026-1',
        'evidence_kind':'red_list_checklist', 'assessment_status':'linked_checklist',
        'independently_verified':False, 'assessment_scope':'global',
        'sis_id':sis_id, 'assessment_id':assessment_id,
        'assessment_reference_url':assessment_url, 'assessment_citation':citation,
        'snapshot_sha256':SOURCE_SHA256, 'mapping_method':METHOD,
        'taxonomy_release':lineage.taxonomy_release, 'concept_set_id':lineage.concept_set_id,
        'taxonomy_category_raw':record['taxonomy_category_raw'],
        'authority_match_method':record['authority_match_method'],
        'license_name':'CC BY 4.0', 'license_url':LICENSE_URL,
        'publisher':PUBLISHER, 'citation':source['citation'],
        'published_at':source.get('published_at'),
        'quality_note':'IUCN의 GBIF 공개 평가목록에 연결된 세계 등급입니다. '
                       '자료 버전과 개별 평가 연도는 다르며, 실시간 조회나 평가 원문 전체의 독립 검증은 아닙니다.',
    }
    if year is not None:
        result['assessment_year'] = year
    return result


def reference_checklist(lineage, snapshot):
    """Return a separate published same-name reference, never this concept's grade.

    Conservative authorship matching and structural source checks do not prove
    biological concept equivalence, particularly for AviList NE concepts.
    """
    index = _index()
    source = index.get('source')
    if not isinstance(source, dict):
        return None
    if (lineage.taxonomy_release != 'v2025b'
            or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'
            or index.get('schema_version') != 1
            or index.get('taxonomy_release') != lineage.taxonomy_release
            or index.get('concept_set_id') != lineage.concept_set_id
            or lineage.taxonomy_source != 'AviList'
            or index.get('mapping_method') != METHOD
            or index.get('taxonomy_snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('evidence_kind') != 'taxonomy_snapshot'
            or snapshot.get('assessment_status') not in ('needs_review', 'snapshot_only')
            or source.get('dataset_key') != DATASET_KEY
            or source.get('url') != SOURCE_URL
            or source.get('release') != '2026-1'
            or source.get('snapshot_sha256') != SOURCE_SHA256
            or source.get('license_name') != 'CC BY 4.0'
            or source.get('license_url') != LICENSE_URL
            or source.get('publisher') != PUBLISHER
            or not isinstance(source.get('citation'), str)
            or 'https://doi.org/10.15468/0qnb58' not in source['citation']):
        return None
    taxon = lineage.items[-1]
    references = index.get('references')
    record = references.get(taxon.taxon_id) if isinstance(references, dict) else None
    if not isinstance(record, dict):
        return None
    sis, assessment = (_positive_id(record.get(key)) for key in ('sis_id', 'assessment_id'))
    citation = record.get('assessment_citation')
    url = f'https://www.iucnredlist.org/species/{sis}/{assessment}'
    if (taxon.rank != 'species' or record.get('scientific_name') != taxon.scientific_name
            or not _authority(taxon.authority)
            or _authority(record.get('authority')) != _authority(taxon.authority)
            or record.get('authority_match_method') not in ('exact', 'single_author_initials_omitted')
            or _authority_match(record.get('authority'), record.get('assessment_authority')) != record.get('authority_match_method')
            or _taxonomy_category(record.get('taxonomy_category_raw')) != _taxonomy_category(snapshot.get('category_raw'))
            or record.get('taxonomy_alignment') != 'unverified'
            or record.get('category') not in CATEGORIES
            or not sis or not assessment
            or record.get('assessment_reference_url') != url
            or not isinstance(citation, str)
            or re.findall(r'RLTS\.T([1-9][0-9]*)A([1-9][0-9]*)\.en', citation) != [(sis, assessment)]):
        return None
    year = record.get('assessment_year')
    if year is not None:
        years = re.findall(r'The IUCN Red List of Threatened Species (\d{4}):', citation)
        doi_years = re.findall(r'IUCN\.UK\.(\d{4})-', citation)
        if type(year) is not int or len(years) != 1 or years != doi_years or int(years[0]) != year:
            return None
    labels = {'LC':'관심대상', 'NT':'준위협', 'VU':'취약', 'EN':'위기',
              'CR':'위급', 'EW':'야생절멸', 'EX':'절멸', 'DD':'정보부족'}
    result = dict(category=record['category'], label=labels[record['category']],
                  assessment_status='reference_only', evidence_kind='red_list_checklist_reference',
                  scientific_name=record['scientific_name'], assessment_authority=record['assessment_authority'],
                  authority_match_method=record['authority_match_method'], sis_id=sis, assessment_id=assessment,
                  assessment_reference_url=url, assessment_citation=citation,
                  source_name='IUCN Red List · GBIF public checklist', source_url=SOURCE_URL,
                  source_id='gbif-iucn-2026-1', source_release='2026-1',
                  snapshot_sha256=SOURCE_SHA256, taxonomy_snapshot_sha256=TAXONOMY_SHA256,
                  taxonomy_release=lineage.taxonomy_release, concept_set_id=lineage.concept_set_id,
                  taxonomy_category_raw=record['taxonomy_category_raw'],
                  taxonomy_alignment='unverified', independently_verified=False,
                  assessment_scope='global', license_name='CC BY 4.0', license_url=LICENSE_URL,
                  publisher=PUBLISHER, published_at=source.get('published_at'),
                  quality_note='동일 학명과 명명자의 IUCN 공개 참고 평가입니다. '
                               '현재 AviList 종 범위와 평가 범위의 일치는 확인되지 않았으며, '
                               '현재 종의 보전 등급으로 확정하지 않습니다.')
    if year is not None:
        result['assessment_year'] = year
    return result
