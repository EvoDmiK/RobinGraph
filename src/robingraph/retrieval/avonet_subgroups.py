"""Explicitly scoped subordinate concept evidence; never parent species means."""
from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from .avonet_ebird import entry_traits
from .trait_mapping import active_provenance, PINS

ARTIFACT_SHA256 = '9920f900c7365ab3c3e178f6f349ecfa741328512f2992badc00f9e752225a22'
EBIRD_SHA256 = '5a6c29b6a48db107b20f8bd1bc6f468ef652a51ccae299b1102350459d73b909'
EBIRD_URL = 'https://cornell.box.com/s/zjci66divvqnz00k98r7pmmb6kpc69zs'


@lru_cache(maxsize=1)
def subgroup_index():
    try:
        raw = Path(__file__).with_name('avonet_subgroup_supplement.json').read_bytes()
        if sha256(raw).hexdigest() != ARTIFACT_SHA256: return {}
        data = json.loads(raw)
        if (data.get('schema_version') != 1 or data.get('taxonomy_release') != PINS['taxonomy'][0]
                or data.get('taxonomy_sha256') != PINS['taxonomy'][1]
                or data.get('source_sha256') != PINS['avonet'][1]
                or data.get('source_release') != PINS['avonet'][0]
                or data.get('source_url') != PINS['avonet'][2]
                or data.get('license_name') != PINS['avonet'][3]
                or data.get('relationship_source', {}).get('sha256') != EBIRD_SHA256
                or data['relationship_source'].get('url') != EBIRD_URL): return {}
        index = defaultdict(list); seen = set()
        for entry in data['entries']:
            key = (entry['target_sequence'], entry['source_avibase_id'])
            if key in seen: return {}
            seen.add(key); index[entry['target_sequence']].append(entry)
        return dict(index)
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def subgroup_traits(lineage, traits, context, labels, display):
    result = list(traits)
    if not lineage.items or not active_provenance(context, 'avonet', lineage): return result
    target = lineage.items[-1]
    prefix = 'avilist-taxon:v2025b:'
    if (target.rank != 'species' or lineage.taxonomy_source != 'AviList'
            or not target.taxon_id.startswith(prefix)
            or lineage.concept_set_id != 'rg:concept-set:avilist-v2025b'): return result
    entries = subgroup_index().get(target.taxon_id[len(prefix):], [])
    # Compute this ONCE: do not let the first subgroup mask other distinct ones.
    existing = {t.get('name') for t in result}
    for entry in entries:
        if entry['target_name'] != target.scientific_name: continue
        for trait in entry_traits(entry, target, labels, display):
            if trait['name'] in existing: continue
            numeric = trait['unit'] is not None
            scope = entry['subgroup_name']
            trait.update({
                'label': labels[trait['name']] + ' · 아종군 자료',
                'source_name': 'AVONET · 아종군 범위 참고 자료',
                'dataset_id': 'avonet-subgroup:' + PINS['avonet'][0],
                'source_scope_kind': 'subspecies_group', 'source_scope': scope,
                'source_scope_english_name': entry['subgroup_english_name'],
                'summary_statistic': ('subgroup_estimate' if trait['inferred'] else 'subgroup_mean') if numeric else 'subgroup_category',
                'source_note': trait['source_note'] + '; 자료 범위: ' + scope + '; 현재 종 전체의 평균이나 전체 분포를 뜻하지 않습니다.',
                'taxonomy_alignment': {'status': 'reference_subgroup', 'method': 'ebird_issf_report_as',
                    'source_scientific_name': entry['source_name'], 'target_scientific_name': target.scientific_name,
                    'subgroup_scientific_name': scope, 'reason': 'subordinate_concept_not_species_average'},
                'mapping_provenance': {**trait['mapping_provenance'], 'extract_sha256': ARTIFACT_SHA256,
                    'relationship_source_url': EBIRD_URL, 'relationship_source_sha256': EBIRD_SHA256,
                    'relationship_source_release': 'eBird-v2025', 'relationship_source_sheet': 'full_sparse',
                    'subgroup_code': entry['subgroup_code'], 'parent_code': entry['parent_code'],
                    'source_avibase_id': entry['source_avibase_id'], 'target_avibase_id': entry['target_avibase_id']},
            })
            result.append(trait)
    return result
