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


def _reference_authority_match(avilist, assessment):
    """Normalize author initials/order notation for references only, never grades.

    Surnames, author order, year and nomenclatural parentheses stay exact.
    An assessment may omit or shorten initials, but cannot add/change them.
    """
    strict = _authority_match(avilist, assessment)
    if strict:
        return strict
    if not isinstance(avilist, str) or not isinstance(assessment, str):
        return None

    def parse(value):
        value = value.strip()
        enclosed = value.startswith('(') and value.endswith(')')
        if enclosed:
            value = value[1:-1].strip()
        if '(' in value or ')' in value:
            return None
        match = re.fullmatch(r'(.+),\s*(\d{4})', value)
        if not match:
            return None
        names = re.split(r'\s*[;&]\s*', match[1])
        authors = []
        for name in names:
            parts = [p.strip() for p in name.split(',')]
            if len(parts) not in (1, 2) or not parts[0] or re.search(r'\bet\s+al\b', parts[0], re.I):
                return None
            initials = parts[1] if len(parts) == 2 else ''
            if initials and (not any(c.isalpha() for c in initials) or any(
                    not (c.isalpha() and c.isupper() or c in '.-' or c.isspace()) for c in initials)):
                return None
            authors.append((_authority(parts[0]), ''.join(c for c in initials if c.isalpha())))
        return enclosed, match[2], authors

    left, right = parse(avilist), parse(assessment)
    if not left or not right or left[:2] != right[:2] or len(left[2]) != len(right[2]):
        return None
    for (surname, initials), (other, abbreviated) in zip(left[2], right[2]):
        if surname != other or (abbreviated and (not initials or not initials.startswith(abbreviated))):
            return None
    return 'author_initials_normalized'


def _reference_assessment_identity(name, authority, citation, url, sis):
    """Validate an archive reference, including its explicitly truncated citation.

    Truncation is accepted only for a reference with its canonical SIS/assessment
    URL and exact source name/authorship in the citation. Never invent a DOI.
    """
    if any(not isinstance(value, str) for value in (name, authority, citation, url)):
        return None
    match = re.fullmatch(r'https://www\.iucnredlist\.org/species/([1-9][0-9]*)/([1-9][0-9]*)', url)
    if not match or match[1] != _positive_id(sis) or not isinstance(citation, str):
        return None
    cited = re.findall(r'RLTS\.T([1-9][0-9]*)A([1-9][0-9]*)\.en', citation)
    if cited == [(match[1], match[2])]:
        return match[2], 'citation_doi'
    source_name = re.escape(name + ' ' + authority)
    truncated = re.fullmatch(r'BirdLife International\.? (\d{4})\. ' + source_name +
                             r'\. The IUCN Red List of Threatened Species \1:', citation)
    if not cited and truncated:
        return match[2], 'canonical_source_url_truncated_citation'
    return None


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


@lru_cache(maxsize=1)
def _birdbase_index():
    from hashlib import sha256
    try:
        raw = Path(__file__).with_name('birdbase_conservation_index.json').read_bytes()
        if sha256(raw).hexdigest() != '156b755b2433f34c00a162150118788426d4bd084dae992b976448bd2057efd4':
            return {}
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def birdbase_reference_checklist(lineage, snapshot):
    """Separate publisher crosswalk reference; never inherit a primary grade."""
    from .birdbase import source_allowed
    if not source_allowed():
        return None
    index = _birdbase_index()
    source = index.get('source')
    if not isinstance(source, dict) or not lineage.items:
        return None
    taxon = lineage.items[-1]
    records = index.get('entries')
    record = records.get(taxon.taxon_id) if isinstance(records, dict) else None
    if not isinstance(record, dict):
        return None
    pinned_sha = 'cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b'
    source_url = 'https://doi.org/10.6084/m9.figshare.27051040.v1'
    method = 'exact_unique_birdbase_avilist_v1_2025'
    if (lineage.taxonomy_source != 'AviList' or lineage.taxonomy_release != 'v2025b'
            or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'
            or taxon.rank != 'species' or index.get('schema_version') != 1
            or index.get('taxonomy_release') != lineage.taxonomy_release
            or index.get('concept_set_id') != lineage.concept_set_id
            or index.get('taxonomy_snapshot_sha256') != TAXONOMY_SHA256
            or index.get('mapping_method') != method
            or snapshot.get('snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('evidence_kind') != 'taxonomy_snapshot'
            or snapshot.get('assessment_status') != 'needs_review'
            or _taxonomy_category(snapshot.get('category_raw')) != 'NE'
            or source.get('id') != 'birdbase-v2025.1'
            or source.get('name') != 'BIRDBASE · IUCN 2024 reference'
            or source.get('release') != 'v2025.1' or source.get('url') != source_url
            or source.get('download_url') != 'https://ndownloader.figshare.com/files/55634729'
            or source.get('snapshot_sha256') != pinned_sha
            or type(source.get('data_year')) is not int or source['data_year'] != 2024
            or source.get('category_column') != '2024 IUCN Red List category'
            or source.get('publication_url') != 'https://www.nature.com/articles/s41597-025-05615-3'
            or source.get('license_name') != 'CC BY 4.0' or source.get('license_url') != LICENSE_URL
            or not isinstance(source.get('citation'), str) or source_url not in source['citation']
            or record.get('taxon_id') != taxon.taxon_id
            or record.get('scientific_name') != taxon.scientific_name
            or not _authority(taxon.authority)
            or _authority(record.get('authority')) != _authority(taxon.authority)
            or record.get('taxonomy_category_raw') != 'NE'
            or record.get('category') not in CATEGORIES
            or type(record.get('source_row')) is not int or record['source_row'] < 3
            or record.get('source_locator') != f"Data!row {record['source_row']}"):
        return None
    raw = record.get('category_raw')
    normalized = 'CR' if raw in ('CR (PE)', 'CR (PEW)') else raw
    if normalized != record['category']:
        return None
    labels = {'LC': '관심대상', 'NT': '준위협', 'VU': '취약', 'EN': '위기',
              'CR': '위급', 'EW': '야생절멸', 'EX': '절멸', 'DD': '정보부족'}
    return dict(category=record['category'], category_raw=raw, label=labels[record['category']],
        evidence_kind='published_dataset_reference', reference_evidence_type='birdbase_iucn_2024',
        assessment_status='reference_only', taxonomy_alignment='unverified', independently_verified=False,
        taxon_id=taxon.taxon_id, scientific_name=taxon.scientific_name,
        assessment_scientific_name=record.get('assessment_scientific_name'),
        source_scientific_name=record.get('source_scientific_name'),
        taxonomy_release=lineage.taxonomy_release, concept_set_id=lineage.concept_set_id,
        taxonomy_snapshot_sha256=TAXONOMY_SHA256, taxonomy_category_raw='NE',
        data_year=2024, source_id=source['id'], source_name=source['name'], source_release=source['release'],
        source_url=source_url, publication_url=source['publication_url'], snapshot_sha256=pinned_sha,
        mapping_method=method, category_column=source['category_column'],
        source_row=record['source_row'], source_locator=record['source_locator'],
        license_name=source['license_name'], license_url=LICENSE_URL, publisher=source['publisher'],
        citation=source['citation'], assessment_scope='global',
        quality_note='BIRDBASE의 명시적 AviList 종명 연결과 2024 IUCN 등급 열에 따른 참고 자료입니다. '
                     '2024는 자료 기준 연도이며 개별 평가 연도가 아닙니다. '
                     '현재 AviList 종 범위와 평가 범위의 일치는 확인되지 않았습니다.')


def best_reference_assessment(lineage, snapshot):
    """Prefer the official public checklist before a publisher dataset reference."""
    return reference_checklist(lineage, snapshot) or birdbase_reference_checklist(lineage, snapshot)


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
    identity = _reference_assessment_identity(record.get('scientific_name', ''), record.get('assessment_authority', ''), citation, record.get('assessment_reference_url'), sis)
    if (record.get('authority_match_method') == 'author_initials_normalized'
            or identity and identity[1] == 'canonical_source_url_truncated_citation') and _taxonomy_category(snapshot.get('category_raw')) != 'NE':
        return None
    if (taxon.rank != 'species' or record.get('scientific_name') != taxon.scientific_name
            or not _authority(taxon.authority)
            or _authority(record.get('authority')) != _authority(taxon.authority)
            or record.get('authority_match_method') not in ('exact', 'single_author_initials_omitted', 'author_initials_normalized')
            or _reference_authority_match(record.get('authority'), record.get('assessment_authority')) != record.get('authority_match_method')
            or _taxonomy_category(record.get('taxonomy_category_raw')) != _taxonomy_category(snapshot.get('category_raw'))
            or record.get('taxonomy_alignment') != 'unverified'
            or record.get('category') not in CATEGORIES
            or not sis or not assessment
            or record.get('assessment_reference_url') != url
            or not isinstance(citation, str)
            or identity != (assessment, record.get('assessment_identity_method', 'citation_doi'))):
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
                  assessment_identity_method=identity[1],
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
