"""Accepted subspecies navigation in the active AviList graph, not name guessing."""
from dataclasses import asdict
from urllib.parse import urlsplit
from .species_profile import SpeciesNotFoundError
from .taxonomy_lineage_neo4j import _parse_lineage_items
from .taxonomy_lineage import with_korean_display_name

SUBSPECIES_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MATCH (parent:Taxon:BirdTaxon {id:$parent_id, rank:'species', policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (parent)-[link:PARENT_OF {concept_set_id:$concept_set_id}]->(child:Taxon:BirdTaxon {rank:'subspecies', policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE parent.source_release=$taxonomy_release AND child.source_release=$taxonomy_release
  AND ($child_id IS NULL OR child.id=$child_id)
OPTIONAL MATCH (child)-[:HAS_VERNACULAR_NAME]->(en:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'})
WHERE en.dataset_id=child.dataset_id AND en.source_release=child.source_release
WITH concept,child,min(en.name) AS english
RETURN {taxon_id:child.id,rank:child.rank,scientific_name:child.scientific_name,
        authority:child.authority,english_name:english} AS taxon,
       child.range_text AS range_text, concept.snapshot_uri AS source_url,
       concept.title AS source_name
ORDER BY child.scientific_name,child.id
LIMIT 201
"""

# Independent Korean summaries of the pinned AviList range statements.
# These describe distribution, not an inferred diagnostic plumage feature.
REVIEWED_RANGES = {
    ('v2025b','Anas platyrhynchos conboschas'): '분포 차이: 그린란드 남서부 해안에 분포하는 아종입니다.',
    ('v2025b','Anas platyrhynchos platyrhynchos'): '분포 차이: 북반구의 넓은 지역에서 번식하고, 겨울에는 더 남쪽 지역으로 이동하는 아종입니다.',
}


REVIEWED_RANGE_RAW = {'Anas platyrhynchos platyrhynchos': 'breeds Holarctic, from Iceland and Spain eastward through eastern Russia, and Alaska through Greenland and southward to northern Baja California and mid-Atlantic US states; winters to North Africa, India, and southern China, and central Mexico and Cuba; widely introduced elsewhere, often hybridizing with local congeners', 'Anas platyrhynchos conboschas': 'coastal southwestern Greenland'}

def _rows(repository,lineage,child_id=None):
    parent=next((t for t in reversed(lineage.items) if t.rank=='species'),None)
    if parent is None:
        raise SpeciesNotFoundError('Parent species not found')
    rows=repository._run(SUBSPECIES_QUERY,parent_id=parent.taxon_id,
        concept_set_id=lineage.concept_set_id,taxonomy_release=lineage.taxonomy_release,child_id=child_id)
    for row in rows:
        url=row.get('source_url') or ''
        if urlsplit(url).scheme not in ('http','https') or not urlsplit(url).hostname or not row.get('source_name'):
            raise ValueError('Subspecies snapshot provenance is missing')
    return parent,rows


def subspecies_for(repository,resolve,name):
    lineage=resolve(name)
    if lineage is None or not lineage.items or lineage.items[-1].rank not in ('species','subspecies'):
        raise SpeciesNotFoundError('Species not found')
    parent,rows=_rows(repository,lineage)
    taxa=[]
    for row in rows[:200]:
        taxon=with_korean_display_name(asdict(_parse_lineage_items([row['taxon']])[0]))
        if (lineage.concept_set_id=='rg:concept-set:avilist-v2025b'
                and taxon.get('english_name_source_url')
                and row.get('range_text')==REVIEWED_RANGE_RAW.get(taxon['scientific_name'])):
            taxon['description']=REVIEWED_RANGES.get((lineage.taxonomy_release,taxon['scientific_name']))
        taxa.append(taxon)
    if len({t['taxon_id'] for t in taxa})!=len(taxa):
        raise ValueError('Duplicate subspecies targets')
    return {'parent_species':{'taxon':asdict(parent)},'subspecies':taxa,
            'taxonomy_release':lineage.taxonomy_release,'concept_set_id':lineage.concept_set_id,
            'has_more':len(rows)>200,'source_url':rows[0]['source_url'] if rows else None,
            'source_name':rows[0]['source_name'] if rows else None}


def subspecies_metadata(repository,lineage):
    target=lineage.items[-1]
    parent,rows=_rows(repository,lineage,target.taxon_id)
    if len(rows)!=1 or rows[0]['taxon']['taxon_id']!=target.taxon_id:
        raise ValueError('Subspecies parent relation is not confirmed')
    row=rows[0]
    expected_id={'Anas platyrhynchos conboschas':'avilist-taxon:v2025b:546',
                 'Anas platyrhynchos platyrhynchos':'avilist-taxon:v2025b:545'}.get(target.scientific_name)
    reviewed_identity=(lineage.concept_set_id=='rg:concept-set:avilist-v2025b' and target.taxon_id==expected_id)
    summary=REVIEWED_RANGES.get((lineage.taxonomy_release,target.scientific_name)) if reviewed_identity else None
    display=with_korean_display_name(asdict(target))
    items=[{'text':f'{display.get("korean_name") or display.get("english_name") or target.scientific_name}은(는) {parent.korean_name or parent.english_name or parent.scientific_name}에 속하는 아종입니다.',
            'source_name':row['source_name'],'source_url':row['source_url'],'license_name':'CC BY 4.0'}]
    if summary and row.get('range_text')==REVIEWED_RANGE_RAW.get(target.scientific_name):
        items.append({'text':summary,'source_name':row['source_name'],'source_url':row['source_url'],
                      'license_name':'CC BY 4.0','reviewed_at':'2026-10-03','source_range':row['range_text']})
    else:
        items.append({'text':'이 아종만의 외관 차이와 한국어 분포 설명은 아직 검토되지 않았습니다.'})
    return {'section':{'key':'subspecies_taxonomy','title':'아종과 소속 종','items':items},
            'source_url':row['source_url'],'source_name':row['source_name'],'range_raw':row.get('range_text')}
