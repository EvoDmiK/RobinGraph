"""Attributed species facts independent of older, broader Pica pica datasets."""
from copy import deepcopy

HKBWS_URL = 'https://avifauna.hkbws.org.hk/species/0260/033600'
MASS_URL = 'https://www.nature.com/articles/s41598-025-13894-4'
MASS_DATA_URL = ('https://media.springernature.com/original/springer-static/esm/'
                 'art%3A10.1038%2Fs41598-025-13894-4/MediaObjects/41598_2025_13894_MOESM2_ESM.xlsx')
MASS_SHA256 = '32b8d981cf09216ff9b5ae2a009ecb559e7c30ca8a722b2b831068c2be34bf3d'
OBSERVATIONS = dict(
    source_name='Hong Kong Bird Watching Society · Oriental Magpie',
    source_url=HKBWS_URL, source_id='reviewed-hkbws-pica-serica',
    citation='Pang, Leven & Carey (2023), The Avifauna of Hong Kong · Oriental Magpie, version 1.0',
    release='2024-01-10', source_release='2024-01-10',
    license_name='출처 기반 독자 요약 · 원문 미재배포',
    source_scope='홍콩 종 계정과 현지 관찰 기록', reviewed_at='2026-10-09')
MASS = dict(
    source_name='Scientific Reports · Pica serica 한국 조사 표본',
    source_url=MASS_URL, source_id='reviewed-chae-2025-pica-serica',
    citation='Chae et al. (2025), doi:10.1038/s41598-025-13894-4 · Supplementary Information 2, sheet1 weight; 115개체 평균 집계',
    release='2025', source_release='2025', license_name='CC BY 4.0',
    license_url='https://creativecommons.org/licenses/by/4.0/',
    source_scope='한국 5개 지역·2008년 3월·2년차 이상 115개체', sample_size=115,
    data_url=MASS_DATA_URL, source_snapshot_sha256=MASS_SHA256, reviewed_at='2026-10-09')


def _matches(lineage):
    if not lineage.items:
        return False
    taxon = lineage.items[-1]
    return (lineage.taxonomy_source == 'AviList' and lineage.taxonomy_release == 'v2025b'
            and lineage.concept_set_id == 'rg:concept-set:avilist-v2025b'
            and taxon.taxon_id == 'avilist-taxon:v2025b:20193'
            and taxon.scientific_name == 'Pica serica' and taxon.rank == 'species')


def reviewed_magpie_traits(lineage, traits):
    """Fill missing facts only, keeping existing active claims unchanged."""
    result = list(traits)
    if not _matches(lineage):
        return result
    existing = {trait.get('name') for trait in result if not trait.get('inferred')}
    records = [
        dict(name='body_mass', label='체중', value=220.64, display='220.64', unit='g',
             summary_statistic='sample_mean', inferred=False, **MASS),
        dict(name='habitat', label='서식 환경', value='Human Modified',
             display='마을·농경지·개방된 습지', unit=None, inferred=False, **OBSERVATIONS),
        dict(name='diet_category', label='먹이 유형', value='Omnivore',
             display='잡식', unit=None, inferred=False, **OBSERVATIONS),
        dict(name='primary_lifestyle', label='주 생활 방식', value='Terrestrial',
             display='땅에서 먹이 탐색·나무와 전선에 앉기', unit=None, inferred=False, **OBSERVATIONS),
    ]
    replacements = {record['name'] for record in records if record['name'] not in existing}
    result = [trait for trait in result if trait.get('name') not in replacements]
    result.extend(deepcopy(record) for record in records if record['name'] in replacements)
    return result


def reviewed_magpie_notes(lineage):
    """Original Korean factual summaries, without reproducing source prose."""
    if not _matches(lineage):
        return {}
    texts = {
        'appearance':[
            '검은색과 흰색 깃털, 길게 뻗은 꼬리가 눈에 띕니다. 몸길이는 약 46~50 cm로 소개됩니다.',
            '날개와 꼬리의 검은 깃털은 빛을 받으면 청록색이나 자주색 광택을 띱니다.',
        ],
        'fun_facts':[
            '홍콩 관찰 기록에서는 번식기에는 주로 혼자 또는 짝으로 보이며, 가을부터 공동 잠자리에 모이는 모습이 기록됐습니다.',
            '홍콩에서는 나무뿐 아니라 조명탑·송전탑 같은 인공 구조물에도 둥지를 만든 기록이 있습니다.',
        ],
    }
    return {key:[{'text':text, **deepcopy(OBSERVATIONS)} for text in values]
            for key, values in texts.items()}
