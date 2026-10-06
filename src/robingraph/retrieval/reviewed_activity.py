"""Reviewed activity descriptions; source booleans remain in provenance.

These are RobinGraph factual summaries, not taxonomic or source-data edits.
Each review is bounded to the taxonomy version in which its identity was checked.
"""

ACTIVITY_REVIEWS = {
    ('v2025b', 'Nycticorax nycticorax'): {
        'review_id': 'rg006-night-heron-2026-10-03',
        'reviewed_at': '2026-10-06',
        'value': True,
        'display': '야행성',
        'source_name': 'Cornell Lab of Ornithology · Black-crowned Night Heron Life History',
        'source_url': 'https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory',
        'citation': 'Cornell Lab of Ornithology, Life History · Food',
        'license_name': '출처 기반 독자 요약 · 원문 미재배포',
    },
    ('v2025b', 'Nycticorax caledonicus'): {
        'review_id': 'nankeen-night-heron-2026-10-06',
        'reviewed_at': '2026-10-06', 'value': True, 'display': '야행성',
        'source_name': 'BirdLife Australia · Nankeen Night-Heron',
        'source_url': 'https://birdlife.org.au/bird-profiles/nankeen-night-heron/',
        'citation': 'BirdLife Australia, Nankeen Night-Heron · Feeding',
        'license_name': '출처 기반 독자 요약 · 원문 미재배포',
    },
}


def reviewed_activity(lineage, traits):
    """Classify usual activity, excluding breeding and other exceptional periods."""
    result = [dict(trait) for trait in traits]
    review = ACTIVITY_REVIEWS.get((lineage.taxonomy_release, lineage.items[-1].scientific_name))
    if review is None:
        return result
    raw = [trait for trait in result if trait.get('name') == 'nocturnal']
    result = [trait for trait in result if trait.get('name') != 'nocturnal']
    result.append({
        **review, 'name': 'activity_pattern', 'label': '활동 시간',
        'unit': None, 'inferred': False, 'source_claims': raw,
        'review_note': '평소의 주된 활동 시간을 기준으로 판단하며 번식기 등 특별한 시기의 활동은 제외합니다. 원자료의 코드와 출처는 보존합니다.',
    })
    return result
