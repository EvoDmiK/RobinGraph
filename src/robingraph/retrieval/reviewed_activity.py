"""Reviewed activity descriptions; source booleans remain in provenance.

These are RobinGraph factual summaries, not taxonomic or source-data edits.
Each review is bounded to the taxonomy version in which its identity was checked.
"""

ACTIVITY_REVIEWS = {
    ('v2025b', 'Nycticorax nycticorax'): {
        'review_id': 'rg006-night-heron-2026-10-03',
        'reviewed_at': '2026-10-03',
        'value': 'evening_to_early_morning_with_breeding_daytime',
        'display': '주로 저녁부터 이른 아침에 먹이를 찾으며, 번식기에는 낮에도 활동합니다.',
        'source_name': 'Cornell Lab of Ornithology · Black-crowned Night Heron Life History',
        'source_url': 'https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory',
        'citation': 'Cornell Lab of Ornithology, Life History · Food',
        'license_name': '출처 기반 독자 요약 · 원문 미재배포',
    },
}


def reviewed_activity(lineage, traits):
    """Preserve raw claims and add a qualified, independently reviewed fact."""
    result = [dict(trait) for trait in traits]
    review = ACTIVITY_REVIEWS.get((lineage.taxonomy_release, lineage.items[-1].scientific_name))
    if review is None:
        return result
    raw = [trait for trait in result if trait.get('name') == 'nocturnal']
    result = [trait for trait in result if trait.get('name') != 'nocturnal']
    result.append({
        **review, 'name': 'activity_pattern', 'label': '활동 시간',
        'unit': None, 'inferred': False, 'source_claims': raw,
        'review_note': '활동 시간은 별도 출처를 검토해 설명했습니다. 원자료의 야행성 코드와 출처는 검토 기록에 보존합니다.',
    })
    return result
