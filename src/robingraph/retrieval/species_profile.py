"""Sourced species cards, composed with LangChain's LCEL runnables."""
from dataclasses import asdict
from functools import lru_cache
from html.parser import HTMLParser
import json
import re
import time
from urllib.parse import urlencode, urlsplit, unquote
from urllib.request import Request, urlopen

from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

class SpeciesNotFoundError(LookupError):
    """The requested name is not a species in the active taxonomy."""


TRAIT_QUERY = """
MATCH (t:Taxon:BirdTaxon {id:$taxon_id})-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept_set_id})
MATCH (c:TraitClaim {policy_status:'allowed'})-[:ASSERTS_ABOUT]->(t)
MATCH (c)-[:SUPPORTED_BY]->(e:EvidenceUnit {policy_status:'allowed'})
WHERE any(s IN $sources WHERE c.dataset_id=s.dataset_id AND c.source_release=s.release)
  AND (c.taxonomy_release IS NULL OR c.taxonomy_release=$taxonomy_release)
  AND e.dataset_id=c.dataset_id AND e.source_record_id=c.source_record_id
RETURN c{.*} AS claim, e.locator AS source_url, e.citation AS citation
ORDER BY c.trait_name, c.dataset_id
LIMIT 100
"""

LABELS = {
    'body_mass':'체중', 'beak_length_culmen':'부리 길이 (전체)',
    'beak_length_nares':'부리 길이 (콧구멍 기준)', 'beak_width':'부리 너비',
    'beak_depth':'부리 높이', 'tarsus_length':'다리 길이 (부척)',
    'wing_length':'접은 날개 길이', 'tail_length':'꼬리 길이',
    'habitat':'서식 환경', 'habitat_density_category':'서식지 밀도 범주',
    'primary_lifestyle':'주 생활 방식', 'trophic_niche':'먹이 생태 범주',
    'trophic_level':'영양 단계', 'diet_category':'먹이 유형',
    'diet_distribution':'먹이 구성', 'foraging_strata_distribution':'먹이 활동 위치',
    'nocturnal':'야행성',
}
VALUES = {'Wetland':'습지', 'Aquatic':'수생', 'Herbivore aquatic':'수생 초식',
          'open':'개방형', 'dense':'밀집형', 'semi_open':'반개방형',
          'Omnivore':'잡식', 'Herbivore':'초식', 'Carnivore':'육식',
          'invertebrate':'무척추동물', 'endotherm_vertebrate':'온혈 척추동물',
          'ectotherm_vertebrate':'변온 척추동물', 'fish':'물고기',
          'unknown_vertebrate':'기타 척추동물', 'carrion':'사체', 'fruit':'열매',
          'nectar':'꽃꿀', 'seed':'씨앗', 'other_plant':'기타 식물',
          'ground':'지면', 'understory':'하층', 'midhigh':'중상층',
          'canopy':'수관', 'aerial':'공중', 'water':'수면', 'pelagic':'외해',
          'below_water_surface':'수중', 'around_water_surface':'수면 주변'}


def read_traits(repository, store, lineage):
    sources = []
    for pipeline, license_name in [('reference-taxonomy-traits','CC0 1.0'), ('reference-avonet','CC BY 4.0')]:
        context = store.active_release_context(pipeline)
        if context is None:
            continue
        cursor = context.cursor
        concept = cursor.get('concept_set_id', cursor.get('taxonomy_concept_set_id'))
        if concept != lineage.concept_set_id or cursor.get('taxonomy_release') != lineage.taxonomy_release:
            continue
        sources.append({'dataset_id':context.dataset.id,
                        'release':cursor.get('trait_release', context.release.release_key),
                        'license_name':license_name, 'source_name':context.dataset.name})
    if not sources:
        return []
    rows = repository._run(TRAIT_QUERY, taxon_id=lineage.items[-1].taxon_id,
                           concept_set_id=lineage.concept_set_id,
                           taxonomy_release=lineage.taxonomy_release, sources=sources)
    traits = []
    for row in rows:
        claim = row['claim']
        name = claim.get('trait_name')
        source = next((s for s in sources if s['dataset_id'] == claim.get('dataset_id')
                       and s['release'] == claim.get('source_release')), None)
        if name not in LABELS or source is None:
            continue
        value = next((claim.get(k) for k in ('value_num','value_text','value_boolean')
                      if claim.get(k) is not None), None)
        if claim.get('value_json'):
            value = json.loads(claim['value_json'])
        if value is None:
            continue
        if isinstance(value, dict):
            display = ' · '.join(f'{VALUES.get(k,k)} {v}%' for k,v in value.items() if isinstance(v,(int,float)) and v > 0)
        elif isinstance(value, bool):
            display = '예' if value else '아니요'
        else:
            display = VALUES.get(str(value), str(value))
        traits.append({'name':name, 'label':LABELS[name], 'value':value, 'display':display,
                       'unit':claim.get('unit'), 'inferred':bool(claim.get('inferred')),
                       'summary_statistic':claim.get('summary_statistic'),
                       'source_url':row['source_url'], 'citation':row['citation'], **source})
    return traits


class PlainText(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(text)
    def handle_data(self, data):
        self.parts.append(data)
    def __str__(self):
        return ''.join(self.parts).strip()


def _json_get(base, parameters):
    request = Request(base + '?' + urlencode(parameters), headers={
        'User-Agent':'RobinGraph/0.1 (https://github.com/EvoDmiK/RobinGraph)',
        'Accept':'application/json'})
    with urlopen(request, timeout=15) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Oversized Wikimedia response')
    return json.loads(data)


def _photo(info):
    metadata = info.get('extmetadata', {})
    def field(key):
        return str(PlainText(str(metadata.get(key, {}).get('value', ''))))
    license_code = field('License').lower()
    if not re.fullmatch(r'(?:cc-by(?:-sa)?-(?:2\.0|2\.5|3\.0|4\.0)|cc0|pd)', license_code):
        return None
    if field('Restrictions') or not info.get('mime','').startswith('image/'):
        return None
    image_url = info.get('thumburl', '')
    source_url = info.get('descriptionurl', '')
    if urlsplit(image_url).scheme != 'https' or urlsplit(image_url).hostname not in ('upload.wikimedia.org','thumb.wikimedia.org'):
        return None
    if urlsplit(source_url).scheme != 'https' or urlsplit(source_url).hostname != 'commons.wikimedia.org':
        return None
    license_url = field('LicenseUrl')
    if license_code.startswith('cc-by'):
        expected = 'https://creativecommons.org/licenses/' + license_code.removeprefix('cc-').rsplit('-',1)[0] + '/' + license_code.rsplit('-',1)[1]
        if license_url.rstrip('/') != expected:
            return None
    creator = field('Artist')
    if not creator or not field('LicenseShortName'):
        return None
    return {'image_url':image_url, 'source_url':source_url, 'creator':creator,
            'credit':field('Credit'), 'license_name':field('LicenseShortName'), 'license_url':license_url,
            'title':field('ObjectName') or 'Wikimedia Commons 사진'}


@lru_cache(maxsize=128)
def _licensed_images(scientific_name, hour):
    # ponytail: hourly bounded metadata cache; shared cache only if traffic warrants it.
    query = 'SELECT ?item ?image WHERE { ?item wdt:P225 ' + json.dumps(scientific_name) + '; wdt:P105 wd:Q7432; wdt:P18 ?image. FILTER NOT EXISTS { ?other wdt:P225 ' + json.dumps(scientific_name) + '; wdt:P105 wd:Q7432. FILTER (?other != ?item) } } LIMIT 2'
    bindings = _json_get('https://query.wikidata.org/sparql', {'query':query, 'format':'json'})['results']['bindings']
    if len({r['item']['value'] for r in bindings}) != 1:
        return []
    images = []
    for row in bindings[:2]:
        path = urlsplit(row['image']['value'])
        if path.hostname != 'commons.wikimedia.org' or not path.path.startswith('/wiki/Special:FilePath/'):
            continue
        filename = unquote(path.path.removeprefix('/wiki/Special:FilePath/'))
        data = _json_get('https://commons.wikimedia.org/w/api.php', {
            'action':'query', 'format':'json', 'prop':'imageinfo', 'titles':'File:' + filename,
            'iiprop':'url|extmetadata|mime', 'iiurlwidth':640})
        for page in data.get('query',{}).get('pages',{}).values():
            for info in page.get('imageinfo',[])[:1]:
                photo = _photo(info)
                if photo:
                    images.append(photo)
    return images


def licensed_images(scientific_name):
    return _licensed_images(scientific_name, int(time.time() // 3600))


def create_species_flow(resolve, traits, photos=licensed_images):
    """Resolve once, collect independent sources, then assemble a sourced response."""
    def resolve_species(query):
        lineage = resolve(query)
        if lineage is None or not lineage.items or lineage.items[-1].rank != 'species':
            raise SpeciesNotFoundError('Species not found')
        return lineage
    def image_stage(lineage):
        try:
            return {'images':photos(lineage.items[-1].scientific_name), 'warnings':[]}
        except Exception:
            return {'images':[], 'warnings':['사진 제공처를 현재 조회할 수 없습니다.']}
    def assemble(state):
        lineage = state['lineage']
        return {'taxon':asdict(lineage.items[-1]), 'lineage':asdict(lineage),
                'traits':state['traits'], **state['media'],
                'vegetation_note':'구체적인 식물·식생 목록은 아직 수집되지 않았습니다.'}
    return (RunnableLambda(resolve_species)
            | RunnableParallel(lineage=RunnablePassthrough(), traits=RunnableLambda(traits), media=RunnableLambda(image_stage))
            | RunnableLambda(assemble))
