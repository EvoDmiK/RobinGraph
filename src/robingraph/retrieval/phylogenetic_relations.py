"""Pinned phylogenetic synthesis clades; no inferred dates or genetic scores.

Depth compares shared supported ancestors along one target's path only. Peers
sharing an ancestor remain tied, irrespective of the lengths of their paths.
"""
from functools import lru_cache
import json
from pathlib import Path

INDEX_PATH = Path(__file__).with_name('species_phylogeny.json')
METHOD = 'phylogeny-topology-v1'


@lru_cache(maxsize=1)
def _load_index():
    if not INDEX_PATH.exists():
        return None
    index = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    if index.get('method') != METHOD or index.get('schema_version') != 1:
        raise ValueError('Unsupported phylogeny index')
    return index


def phylogeny_metadata(taxonomy_release=None, concept_set_id=None):
    index = _load_index()
    if (index is None
            or (taxonomy_release is not None and taxonomy_release != index['taxonomy_release'])
            or (concept_set_id is not None and concept_set_id != index['concept_set_id'])):
        return {'available': False, 'method': METHOD}
    return {'available': True, 'method': METHOD,
            'taxonomy_release': index['taxonomy_release'],
            'concept_set_id': index['concept_set_id'],
            **index['provenance'], 'coverage': dict(index['coverage'])}


def phylogenetic_relations(taxonomy_release, target_taxon_id,
                          target_scientific_name, candidates, concept_set_id=None):
    """Return supported MRCA reasons for exactly mapped active candidates.

    Absent targets, old releases, and changed identities yield no tree evidence.
    Caller decides how to present taxonomy fallback and incomplete coverage.
    """
    index = _load_index()
    if (index is None or taxonomy_release != index['taxonomy_release']
            or (concept_set_id is not None and concept_set_id != index['concept_set_id'])):
        return {}
    taxa = index['taxa']
    target = taxa.get(target_taxon_id)
    if target is None or target['scientific_name'] != target_scientific_name:
        return {}
    target_path = target['ancestors']
    result = {}
    rows = candidates.values() if isinstance(candidates, dict) else candidates
    for candidate in rows:
        taxon_id = candidate.get('taxon_id')
        peer = taxa.get(taxon_id)
        if (taxon_id == target_taxon_id or peer is None
                or peer['scientific_name'] != candidate.get('scientific_name')):
            continue
        ancestor = None
        depth = None
        for position, (a, b) in enumerate(zip(target_path, peer['ancestors'])):
            if a != b:
                break
            node = index['nodes'].get(str(a))
            if node and node.get('supporting_sources'):
                ancestor, depth = a, position
        if ancestor is None:
            continue
        node = index['nodes'][str(ancestor)]
        result[taxon_id] = {
            'key': 'phylogenetic_clade', 'label': '출처가 확인된 계통 합성 공통 조상',
            'points': 0, 'shared_ancestor_depth': depth,
            'shared_ancestor_id': node['source_node_id'],
            'supporting_sources': list(node['supporting_sources']),
            'supporting_study_count':len({s.split('@')[0] for s in node['supporting_sources']}),
            'supporting_studies':[index.get('sources', {}).get(s, {}) for s in node['supporting_sources']],
            'conflicting_sources': list(node.get('conflicting_sources', [])),
            'support_type': 'input_phylogeny_clade',
            'mapping_method': peer['mapping_method'],
            **index['provenance'],
        }
    return result
