"""Rank active birds by explicit taxonomy and independently sourced ecology."""
from dataclasses import asdict

from .ecological_relations import _web_url
from .species_profile import VALUES, SpeciesNotFoundError, read_traits
from .taxonomy_lineage import with_korean_display_name

WEIGHTS = {'same_genus': 50, 'same_family': 30, 'same_habitat': 10, 'same_trophic_niche': 10}
METHOD = 'taxonomy-ecology-v1'

SOURCE_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id,version:$taxonomy_release,policy_status:'allowed'})
MATCH (target:Taxon:BirdTaxon {id:$target_id,rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
RETURN concept.snapshot_uri AS source_url, concept.title AS source_name
"""

# No name filter or LIMIT is allowed here: every active species is scored first.
CANDIDATES_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id,version:$taxonomy_release,policy_status:'allowed'})
MATCH (target:Taxon:BirdTaxon {id:$target_id,rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
OPTIONAL MATCH (family:Taxon:BirdTaxon {id:$family_id,rank:'family',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
OPTIONAL MATCH familyPath=(family)-[:PARENT_OF*1..2]->(familyPeer:Taxon:BirdTaxon {rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})
WHERE all(link IN relationships(familyPath) WHERE link.concept_set_id=$concept_set_id)
  AND all(node IN nodes(familyPath) WHERE node:Taxon AND node:BirdTaxon AND node.policy_status='allowed' AND node.source_release=$taxonomy_release
    AND EXISTS { MATCH (node)-[:IN_CONCEPT_SET]->(concept) })
WITH concept,target,collect(DISTINCT familyPeer.id) AS family_ids
OPTIONAL MATCH (genus:Taxon:BirdTaxon {id:$genus_id,rank:'genus',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
OPTIONAL MATCH (genus)-[genusLink:PARENT_OF]->(genusPeer:Taxon:BirdTaxon {rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE genusLink.concept_set_id=$concept_set_id
WITH concept,target,family_ids,collect(DISTINCT genusPeer.id) AS genus_ids
MATCH (peer:Taxon:BirdTaxon {rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE peer.id <> target.id
RETURN DISTINCT peer.id AS taxon_id,peer.scientific_name AS scientific_name,
       peer.id IN family_ids AS same_family,
       (peer.id IN family_ids AND peer.id IN genus_ids) AS same_genus
"""

ECOLOGY_QUERY = """
UNWIND $categories AS originCategory
MATCH (concept:TaxonConceptSet {id:$concept_set_id,version:$taxonomy_release,policy_status:'allowed'})
MATCH (target:Taxon:BirdTaxon {id:$target_id,rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (origin:TraitClaim {policy_status:'allowed'})-[:ASSERTS_ABOUT]->(target)
MATCH (origin)-[:SUPPORTED_BY]->(originEvidence:EvidenceUnit {policy_status:'allowed'})
WHERE origin.trait_name=originCategory.trait_name AND origin.value_text=originCategory.value
  AND origin.dataset_id=originCategory.dataset_id AND origin.source_release=originCategory.release
  AND origin.inferred=false AND (origin.taxonomy_release IS NULL OR origin.taxonomy_release=$taxonomy_release)
  AND originEvidence.dataset_id=origin.dataset_id AND originEvidence.source_record_id=origin.source_record_id
MATCH (claim:TraitClaim {policy_status:'allowed'})-[:ASSERTS_ABOUT]->(peer:Taxon:BirdTaxon {rank:'species',source_release:$taxonomy_release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (claim)-[:SUPPORTED_BY]->(evidence:EvidenceUnit {policy_status:'allowed'})
WHERE peer.id<>target.id AND claim.trait_name=origin.trait_name AND claim.value_text=origin.value_text
  AND claim.dataset_id=origin.dataset_id AND claim.source_release=origin.source_release
  AND claim.inferred=false AND (claim.taxonomy_release IS NULL OR claim.taxonomy_release=$taxonomy_release)
  AND evidence.dataset_id=claim.dataset_id AND evidence.source_record_id=claim.source_record_id
RETURN DISTINCT peer.id AS taxon_id,claim.trait_name AS trait_name,claim.value_text AS value,
       claim.dataset_id AS dataset_id,claim.source_release AS release,
       evidence.locator AS source_url,evidence.citation AS citation
ORDER BY taxon_id,trait_name,source_url
"""

NAMES_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id,version:$taxonomy_release,policy_status:'allowed'})
MATCH (peer:Taxon:BirdTaxon {source_release:$taxonomy_release,rank:'species',policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE peer.id IN $taxon_ids
OPTIONAL MATCH (peer)-[:HAS_VERNACULAR_NAME]->(ko:VernacularName {language:'ko',policy_status:'allowed'})
WHERE ko.dataset_id=$korean_dataset_id AND ko.name =~ '.*[가-힣].*'
WITH peer,min(ko.name) AS korean_name
OPTIONAL MATCH (peer)-[:HAS_VERNACULAR_NAME]->(en:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'})
WHERE en.dataset_id=peer.dataset_id AND en.source_release=peer.source_release
RETURN peer.id AS taxon_id,korean_name,min(en.name) AS english_name
"""


def similar_species(repository, store, resolve, name):
    lineage = resolve(name)
    if lineage is None or not lineage.items or lineage.items[-1].rank != 'species':
        raise SpeciesNotFoundError(name)
    target = lineage.items[-1]
    family = next((item for item in lineage.items if item.rank == 'family'), None)
    genus = next((item for item in lineage.items if item.rank == 'genus'), None)
    context = dict(concept_set_id=lineage.concept_set_id,taxonomy_release=lineage.taxonomy_release,target_id=target.taxon_id)
    sources = repository._run(SOURCE_QUERY, **context)
    if len(sources)!=1 or not sources[0].get('source_name') or not _web_url(sources[0].get('source_url')):
        raise ValueError('Taxonomy provenance unavailable')
    source = sources[0]
    rows = repository._run(CANDIDATES_QUERY, **context,
                           family_id=family.taxon_id if family else None,
                           genus_id=genus.taxon_id if genus else None)
    candidates = {}
    for row in rows:
        taxon_id, scientific_name = row.get('taxon_id'), row.get('scientific_name')
        if not taxon_id or not scientific_name or taxon_id==target.taxon_id or taxon_id in candidates:
            raise ValueError('Invalid active candidate projection')
        same_family = row.get('same_family') is True
        same_genus = same_family and row.get('same_genus') is True
        candidates[taxon_id] = {'taxon_id':taxon_id,'rank':'species','scientific_name':scientific_name,
                                'same_family':same_family,'same_genus':same_genus,'ecology':{}}
    categories = []
    category_sources = {}
    for trait in read_traits(repository,store,lineage):
        if (trait.get('name') in ('habitat','trophic_niche') and isinstance(trait.get('value'),str)
                and trait['value'] in VALUES and trait.get('inferred') is False and _web_url(trait.get('source_url'))):
            descriptor = {key:trait[key] for key in ('dataset_id','release')}
            descriptor.update(trait_name=trait['name'],value=trait['value'])
            if descriptor not in categories:
                categories.append(descriptor)
                category_sources[(trait['name'],trait['value'],trait['dataset_id'],trait['release'])] = trait
    if categories:
        for row in repository._run(ECOLOGY_QUERY, **context, categories=categories):
            candidate = candidates.get(row.get('taxon_id'))
            if candidate is None:
                raise ValueError('Ecology claim targets a non-active candidate')
            trait_name = row.get('trait_name')
            descriptor = dict(trait_name=trait_name,value=row.get('value'),dataset_id=row.get('dataset_id'),release=row.get('release'))
            if descriptor not in categories or not _web_url(row.get('source_url')):
                raise ValueError('Invalid ecological evidence')
            key = 'same_habitat' if trait_name=='habitat' else 'same_trophic_niche'
            origin = category_sources[(row['trait_name'],row['value'],row['dataset_id'],row['release'])]
            candidate['ecology'].setdefault(key, {'source_url':row['source_url'],'citation':row.get('citation'),
                'source_name':origin['source_name'], 'target_source_url':origin['source_url'],
                'target_citation':origin.get('citation'),'dataset_id':row['dataset_id'],
                'release':row['release'],'value':row['value'],'display':origin.get('display')})
    ranked = []
    for candidate in candidates.values():
        reasons = []
        if candidate['same_family']:
            reasons.append({'key':'same_family','label':'같은 과','points':WEIGHTS['same_family'],
                            'ancestor':asdict(family),**source})
        if candidate['same_genus']:
            reasons.append({'key':'same_genus','label':'같은 속','points':WEIGHTS['same_genus'],
                            'ancestor':asdict(genus),**source})
        for key,label in (('same_habitat','같은 서식 환경 범주'),('same_trophic_niche','같은 먹이 생태 범주')):
            if key in candidate['ecology']:
                reasons.append({'key':key,'label':label,'points':WEIGHTS[key],**candidate['ecology'][key]})
        score = sum(reason['points'] for reason in reasons)
        if score:
            ranked.append((score,candidate,reasons))
    ranked.sort(key=lambda item:(-item[0],item[1]['scientific_name'],item[1]['taxon_id']))
    top = ranked[:3]
    names = repository._run(NAMES_QUERY, concept_set_id=lineage.concept_set_id,
                            taxonomy_release=lineage.taxonomy_release,
                            taxon_ids=[candidate['taxon_id'] for _,candidate,_ in top],
                            korean_dataset_id=repository._korean_dataset_id()) if top else []
    selected_ids = {candidate['taxon_id'] for _,candidate,_ in top}
    if any(row.get('taxon_id') not in selected_ids for row in names) or len({row.get('taxon_id') for row in names})!=len(names):
        raise ValueError('Invalid selected species name projection')
    labels = {row['taxon_id']:row for row in names}
    items = []
    for position,(score,candidate,reasons) in enumerate(top,1):
        name_row = labels.get(candidate['taxon_id'],{})
        items.append(with_korean_display_name({'taxon_id':candidate['taxon_id'],'rank':'species',
                      'scientific_name':candidate['scientific_name'],
                      'korean_name':name_row.get('korean_name'),'english_name':name_row.get('english_name'),
                      'similarity_score':score,'similarity_rank':position,'similarity_reasons':reasons}))
    return {'taxon':asdict(target),'taxonomy_source':lineage.taxonomy_source,
            'taxonomy_release':lineage.taxonomy_release,'concept_set_id':lineage.concept_set_id,
            'ranking':{'method':METHOD,'candidate_scope':'active_species','scanned_count':len(candidates),
                       'eligible_count':len(ranked),'limit':3,'weights':WEIGHTS.copy(),
                       'tie_break':'scientific_name,taxon_id'},
            'groups':[{'rank':'similarity','label':'그래프 유사도 상위 3종','items':items,
                       'has_more':len(ranked)>3,'source_url':source['source_url'],'source_name':source['source_name']}],
            'note':'분류 관계와 출처가 확인된 생태 범주의 규칙 점수입니다. 외형·유전 유사도나 확률을 뜻하지 않습니다.'}
