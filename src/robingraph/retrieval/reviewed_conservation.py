"""Pinned expert references: display evidence, never independent IUCN assessments."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re

ARTIFACT_SHA256 = '9a753a26d0da68b5044bfe6565984428b07951e54dc7d6fc83ccb615f3c3801e'
TAXONOMY_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
CORNELL_URL = 'https://www.birds.cornell.edu/clementschecklist/updates-and-corrections-october-2024/'


def record_digest(record):
    content = {key: value for key, value in record.items() if key != 'record_sha256'}
    return sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def valid_record(record):
    if not isinstance(record, dict):
        return False
    if (record.get('record_sha256') != record_digest(record)
            or record.get('evidence_kind') != 'reviewed_expert_reference'
            or record.get('reference_evidence_type') != 'hkbws_species_account'
            or record.get('assessment_status') != 'reference_only'
            or record.get('independently_verified') is not False
            or record.get('category') not in ('LC', 'NT', 'VU', 'EN', 'CR', 'EW', 'EX', 'DD')
            or record.get('category_raw') != record.get('category')
            or record.get('assessment_year') is not None or record.get('assessment_id') is not None
            or record.get('sis_id') is not None
            or record.get('source_id') != 'hkbws-avifauna'
            or record.get('publisher') != 'Hong Kong Bird Watching Society'
            or record.get('source_name') != 'Hong Kong Bird Watching Society · The Avifauna of Hong Kong'
            or not re.fullmatch(r'https://avifauna\.hkbws\.org\.hk/species/[0-9]{4}/[0-9]{6}', record.get('source_url', ''))
            or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', record.get('source_updated_at', ''))
            or record.get('source_release') != record.get('source_updated_at')
            or record.get('snapshot_kind') != 'reviewed_source_excerpt'
            or record.get('taxonomy_release') != 'v2025b'
            or record.get('concept_set_id') != 'rg:concept-set:avilist-v2025b'
            or record.get('taxonomy_snapshot_sha256') != TAXONOMY_SHA256):
        return False
    for key in ('source_excerpt', 'source_scientific_name',
                'source_scope_note', 'source_note', 'scientific_name', 'authority', 'citation'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            return False
    assessment_name = record.get('assessment_scientific_name')
    if assessment_name is None:
        if record.get('assessment_name_basis') != 'not_identified_by_source':
            return False
    elif not isinstance(assessment_name, str) or not assessment_name.strip():
        return False
    if record.get('snapshot_sha256') != sha256(record['source_excerpt'].encode()).hexdigest():
        return False
    if record.get('taxonomy_alignment') == 'exact_source_name':
        return (record.get('mapping_method') == 'reviewed_exact_source_name'
                and record['source_scientific_name'] == record['scientific_name'])
    excerpt = record.get('taxonomic_evidence_excerpt')
    return (record.get('taxonomy_alignment') == 'partial_scope'
            and record.get('mapping_method') == 'documented_related_concept'
            and record.get('taxonomic_evidence_url') == CORNELL_URL
            and record.get('taxonomic_evidence_release') == 'Clements-2024'
            and isinstance(excerpt, str) and bool(excerpt.strip())
            and record.get('taxonomic_evidence_sha256') == sha256(excerpt.encode()).hexdigest())


@lru_cache(maxsize=1)
def reviewed_index():
    try:
        raw = Path(__file__).with_name('reviewed_conservation_references.json').read_bytes()
        if sha256(raw).hexdigest() != ARTIFACT_SHA256:
            return {}
        data = json.loads(raw)
        if data.get('schema_version') != 1 or not isinstance(data.get('records'), list):
            return {}
        index = {}
        for record in data['records']:
            if not valid_record(record) or record.get('taxon_id') in index:
                return {}
            index[record['taxon_id']] = record
        return index
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def reviewed_reference_assessment(lineage, snapshot):
    if not lineage.items:
        return None
    taxon = lineage.items[-1]
    record = reviewed_index().get(taxon.taxon_id)
    if (not record or not valid_record(record) or taxon.rank != 'species'
            or taxon.scientific_name != record['scientific_name'] or taxon.authority != record['authority']
            or lineage.taxonomy_source != 'AviList'
            or lineage.taxonomy_release != record['taxonomy_release']
            or lineage.concept_set_id != record['concept_set_id']
            or snapshot.get('snapshot_sha256') != TAXONOMY_SHA256
            or snapshot.get('evidence_kind') != 'taxonomy_snapshot'
            or snapshot.get('assessment_status') != 'needs_review'
            or str(snapshot.get('category_raw', '')).strip().upper() != record['taxonomy_category_raw']):
        return None
    # Fresh dict protects the reviewed artifact from consumers mutating payloads.
    return dict(record)
