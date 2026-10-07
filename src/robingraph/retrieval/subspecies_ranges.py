"""Offline Korean distribution reviews bound to exact AviList identities and text."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


def range_hash(raw):
    return sha256(raw.strip().encode('utf-8')).hexdigest()


@lru_cache(maxsize=1)
def range_reviews():
    data = json.loads(Path(__file__).with_name('subspecies_range_reviews.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported subspecies range review schema')
    return data['reviews']


def reviewed_range(taxon, lineage, raw):
    """Never carry a review across changed identity, release, or source wording."""
    review = range_reviews().get(taxon['taxon_id'])
    if not raw:
        return None, 'missing-source'
    if not review:
        return None, 'pending-review'
    expected = dict(scientific_name=taxon['scientific_name'],
                    taxonomy_release=lineage.taxonomy_release,
                    concept_set_id=lineage.concept_set_id,
                    source_sha256=range_hash(raw))
    if any(review.get(key) != value for key, value in expected.items()):
        return None, 'stale-review'
    status = review.get('status')
    if status != 'reviewed':
        return None, status if status in ('pending-review', 'conflict', 'translation-failed') else 'invalid-review'
    if not all(isinstance(review.get(key), str) and review[key].strip()
               for key in ('description', 'caption', 'reviewer', 'review_method')):
        return None, 'invalid-review'
    return review, 'reviewed'
