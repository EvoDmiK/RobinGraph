"""Bounded exploration of shared AviList ancestors, with snapshot provenance."""
from dataclasses import asdict
from urllib.parse import urlsplit

from .species_profile import SpeciesNotFoundError
from .taxonomy_lineage import sourced_korean_names
from .taxonomy_lineage_neo4j import _parse_lineage_items

SOURCE_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
RETURN concept.snapshot_uri AS source_url, concept.title AS source_name
"""

RELATED_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MATCH (parent:Taxon:BirdTaxon {id:$parent_id, rank:$rank, source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH path=(parent)-[:PARENT_OF*1..2]->(peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})
WHERE peer.id <> $target_id
  AND all(link IN relationships(path) WHERE link.concept_set_id=$concept_set_id)
  AND all(node IN nodes(path) WHERE node:Taxon AND node:BirdTaxon AND node.policy_status='allowed' AND node.source_release=$taxonomy_release
      AND EXISTS { MATCH (node)-[:IN_CONCEPT_SET]->(concept) })
  AND ($excluded_genus IS NULL OR NOT EXISTS {
      MATCH (genus:Taxon:BirdTaxon {id:$excluded_genus})-[r:PARENT_OF]->(peer)
      WHERE r.concept_set_id=$concept_set_id
  })
WITH DISTINCT concept, peer
OPTIONAL MATCH (peer)-[:HAS_VERNACULAR_NAME]->(english:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'})
WHERE english.dataset_id=peer.dataset_id AND english.source_release=peer.source_release
WITH concept,peer,min(english.name) AS english_name
WITH concept,peer,english_name,$korean_reference_names[peer.id] AS reference
WITH concept,peer,english_name,
     CASE WHEN reference.scientific_name=peer.scientific_name AND reference.english_name=english_name
          THEN reference.name ELSE null END AS korean_name
RETURN {taxon_id:peer.id, rank:peer.rank, scientific_name:peer.scientific_name,
        authority:peer.authority, korean_name:korean_name,
        english_name:english_name} AS taxon,
       concept.snapshot_uri AS source_url, concept.title AS source_name
ORDER BY CASE WHEN korean_name IS NULL THEN 1 ELSE 0 END,
         coalesce(korean_name,english_name,peer.scientific_name),peer.id
LIMIT 13
"""


def related_species(repository, resolve, name):
    lineage = resolve(name)
    if lineage is None or not lineage.items or lineage.items[-1].rank != 'species':
        raise SpeciesNotFoundError('Species not found')
    target = lineage.items[-1]
    genus = next((item for item in lineage.items if item.rank == 'genus'), None)
    sources = repository._run(SOURCE_QUERY, concept_set_id=lineage.concept_set_id,
                              taxonomy_release=lineage.taxonomy_release)
    if len(sources) != 1 or not sources[0].get('source_name'):
        raise ValueError('Taxonomy provenance unavailable')
    source = sources[0]
    url = urlsplit(source.get('source_url') or '')
    if url.scheme not in ('https', 'http') or not url.hostname:
        raise ValueError('Taxonomy provenance unavailable')
    korean_reference_names = {taxon_id: {key: label[key] for key in ('name', 'scientific_name', 'english_name')}
                              for taxon_id, label in sourced_korean_names().items()}
    groups = []
    for rank, label in [('genus', '같은 속의 새'), ('family', '같은 과의 다른 속 새')]:
        ancestor = next((item for item in lineage.items if item.rank == rank), None)
        rows = [] if ancestor is None else repository._run(
            RELATED_QUERY, concept_set_id=lineage.concept_set_id,
            taxonomy_release=lineage.taxonomy_release, parent_id=ancestor.taxon_id,
            target_id=target.taxon_id, rank=rank,
            excluded_genus=genus.taxon_id if rank == 'family' and genus else None,
            korean_reference_names=korean_reference_names)
        groups.append({'rank':rank, 'label':label, 'ancestor':asdict(ancestor) if ancestor else None,
                       'items':[asdict(item) for item in _parse_lineage_items([r['taxon'] for r in rows[:12]])],
                       'has_more':len(rows) > 12,
                       'source_url':source['source_url'], 'source_name':source['source_name']})
    return {'taxon':asdict(target), 'taxonomy_source':lineage.taxonomy_source,
            'taxonomy_release':lineage.taxonomy_release, 'concept_set_id':lineage.concept_set_id,
            'groups':groups, 'name_filter':'licensed_names',
            'note':'한국어 이름을 우선하며 없으면 영어 이름을 표시합니다. 같은 속·과에 속한다는 분류 관계입니다. 진화적 거리나 계통상 가장 가까운 종을 뜻하지 않습니다.'}
