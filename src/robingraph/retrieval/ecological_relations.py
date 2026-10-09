"""Read-only ecological similarity, scoped to one approved trait dataset/release."""
from dataclasses import asdict
from urllib.parse import urlsplit

from .species_profile import LABELS, VALUES, SpeciesNotFoundError, read_traits
from .taxonomy_lineage import sourced_korean_names, with_korean_display_name


PEERS_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MATCH (target:Taxon:BirdTaxon {id:$target_id,rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (origin:TraitClaim {policy_status:'allowed',dataset_id:$dataset_id,source_release:$release,trait_name:$trait_name,value_text:$value})-[:ASSERTS_ABOUT]->(target)
MATCH (origin)-[:SUPPORTED_BY]->(originEvidence:EvidenceUnit {policy_status:'allowed'})
WHERE origin.inferred=false
  AND (origin.taxonomy_release IS NULL OR origin.taxonomy_release=$taxonomy_release)
  AND originEvidence.dataset_id=origin.dataset_id AND originEvidence.source_record_id=origin.source_record_id
WITH DISTINCT concept
MATCH (claim:TraitClaim {policy_status:'allowed',dataset_id:$dataset_id,source_release:$release,trait_name:$trait_name,value_text:$value})-[:ASSERTS_ABOUT]->(peer:Taxon:BirdTaxon {rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (claim)-[:SUPPORTED_BY]->(evidence:EvidenceUnit {policy_status:'allowed'})
WHERE peer.id <> $target_id AND claim.inferred=false
  AND (claim.taxonomy_release IS NULL OR claim.taxonomy_release=$taxonomy_release)
  AND evidence.dataset_id=claim.dataset_id AND evidence.source_record_id=claim.source_record_id
  AND (evidence.locator STARTS WITH 'https://' OR evidence.locator STARTS WITH 'http://')
WITH peer, evidence ORDER BY evidence.id
WITH peer, head(collect(evidence)) AS evidence
OPTIONAL MATCH (peer)-[:HAS_VERNACULAR_NAME]->(en:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'})
WHERE en.dataset_id=peer.dataset_id AND en.source_release=peer.source_release
WITH peer,evidence,min(en.name) AS english_name
WITH peer,evidence,english_name,$korean_reference_names[peer.id] AS reference
WITH peer,evidence,english_name,
     CASE WHEN reference.scientific_name=peer.scientific_name AND reference.english_name=english_name
          THEN reference.name ELSE null END AS korean_name
RETURN {taxon_id:peer.id,rank:peer.rank,scientific_name:peer.scientific_name,
        korean_name:korean_name,english_name:english_name} AS taxon,
       evidence.locator AS source_url,evidence.citation AS citation
ORDER BY CASE WHEN korean_name IS NULL THEN 1 ELSE 0 END,
         coalesce(korean_name,english_name,peer.scientific_name),peer.id
LIMIT 4
"""


def _web_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username
    except ValueError:
        return False


def ecological_relations(repository, store, resolve, name):
    lineage = resolve(name)
    if lineage is None or not lineage.items or lineage.items[-1].rank != 'species':
        raise SpeciesNotFoundError(name)
    target = lineage.items[-1]
    groups, seen = [], set()
    korean_reference_names = {taxon_id: {key: label[key] for key in ('name', 'scientific_name', 'english_name')}
                              for taxon_id, label in sourced_korean_names().items()}
    for trait in read_traits(repository, store, lineage):
        kind, value = trait['name'], trait['value']
        if (kind not in ('habitat', 'trophic_niche') or not isinstance(value, str)
                or value not in VALUES or trait.get('inferred') or trait.get('source_scope_kind') == 'subspecies_group'
                or not _web_url(trait.get('source_url'))):
            continue
        key = (kind, value, trait['dataset_id'], trait['release'])
        if key in seen:
            continue
        seen.add(key)
        source = {k: trait[k] for k in ('source_name','source_url','citation','dataset_id','release','license_name')}
        rows = repository._run(
            PEERS_QUERY, concept_set_id=lineage.concept_set_id,
            taxonomy_release=lineage.taxonomy_release, target_id=target.taxon_id,
            dataset_id=trait['dataset_id'], release=trait['release'],
            trait_name=kind, value=value, korean_reference_names=korean_reference_names,
        )
        items = []
        for row in rows:
            peer = with_korean_display_name(row.get('taxon', {}))
            if (peer.get('rank') != 'species' or not peer.get('taxon_id')
                    or peer['taxon_id'] == target.taxon_id
                    or not _web_url(row.get('source_url'))):
                raise ValueError('Invalid ecological relationship provenance')
            items.append({**peer, 'evidence': {**source, 'source_url':row['source_url'], 'citation':row.get('citation')}})
        items.sort(key=lambda peer: (not bool(peer.get('korean_name')),
                   peer.get('korean_name') or peer.get('english_name') or peer['scientific_name'], peer['taxon_id']))
        groups.append({'relation':kind, 'label':f'같은 {LABELS[kind]}의 새',
                       'value':value, 'display':VALUES[value], 'source':source,
                       'items':items[:3], 'has_more':len(items)>3})
    return {'taxon':asdict(target), 'taxonomy_source':lineage.taxonomy_source,
            'taxonomy_release':lineage.taxonomy_release,
            'concept_set_id':lineage.concept_set_id, 'groups':groups,
            'note':'같은 자료의 생태 분류값을 공유하는 종입니다. 가까운 계통이나 실제 공존·먹이 관계를 뜻하지 않습니다.'}
