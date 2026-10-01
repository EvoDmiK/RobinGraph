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

CONSERVATION_QUERY = """
MATCH (t:Taxon:BirdTaxon {id:$taxon_id, rank:'species'})-[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:$concept_set_id, policy_status:'allowed'})
WHERE t.source_release=$taxonomy_release AND s.version=$taxonomy_release
RETURN t.iucn_red_list_category_raw AS category_raw,
       s.title AS source_name, s.snapshot_uri AS source_url,
       s.version AS source_release
"""

CONSERVATION_LABELS = {
    'LC':'관심대상', 'NT':'준위협', 'VU':'취약', 'EN':'위기',
    'CR':'위급', 'EW':'야생절멸', 'EX':'절멸', 'DD':'정보부족', 'NE':'미평가',
}


def unconfirmed_conservation():
    return {'category':None, 'category_raw':None, 'label':'확인되지 않음',
            'source_name':None, 'source_url':None, 'source_release':None}


def read_conservation(repository, lineage):
    """Read the resolved taxonomy snapshot, never imply a live IUCN assessment."""
    rows = repository._run(CONSERVATION_QUERY, taxon_id=lineage.items[-1].taxon_id,
                           concept_set_id=lineage.concept_set_id,
                           taxonomy_release=lineage.taxonomy_release)
    if len(rows) != 1:
        return unconfirmed_conservation()
    row = rows[0]
    result = unconfirmed_conservation()
    for key in ('source_name', 'source_url', 'source_release'):
        value = row.get(key)
        result[key] = value.strip() if isinstance(value, str) and value.strip() else None
    if (result['source_release'] != lineage.taxonomy_release
            or not result['source_name'] or not result['source_url']
            or urlsplit(result['source_url']).scheme not in ('https', 'http')
            or not urlsplit(result['source_url']).hostname):
        return unconfirmed_conservation()
    raw = row.get('category_raw')
    if isinstance(raw, str):
        result['category_raw'] = raw
        code = raw.strip().upper()
        if re.fullmatch(r'CR\s*\(PEW?\)', code):
            code = 'CR'
        if code in CONSERVATION_LABELS:
            result.update(category=code, label=CONSERVATION_LABELS[code])
    return result


def species_summary(taxon, traits):
    """Brief Korean description using only attributed card fields."""
    fields = {}
    for trait in traits:
        if not isinstance(trait, dict) or not trait.get('source_url') or not trait.get('source_name'):
            continue
        name = trait.get('name')
        display = trait.get('display')
        if name in ('habitat', 'primary_lifestyle', 'diet_category', 'trophic_niche', 'body_mass') and isinstance(display, str) and display.strip():
            fields.setdefault(name, trait)
    sentences = []
    environment = [f"{LABELS[key]}은 {fields[key]['display']}" for key in ('habitat', 'primary_lifestyle') if key in fields]
    if environment:
        sentences.append('이며, '.join(environment) + '입니다.')
    diet = fields.get('diet_category') or fields.get('trophic_niche')
    if diet:
        sentences.append(f"먹이 정보는 ‘{diet['display']}’입니다.")
    weight = fields.get('body_mass')
    if weight:
        statistic = '평균 ' if weight.get('summary_statistic') == 'mean' else ''
        unit = f" {weight['unit']}" if weight.get('unit') else ''
        sentences.append(f"{statistic}체중은 {weight['display']}{unit}입니다.")
    if not sentences:
        return '출처가 있는 서식 환경·먹이·생활 방식·체중 정보를 아직 확인하지 못했습니다.'
    name = taxon.get('korean_name') or taxon.get('scientific_name')
    return (f'{name}의 ' if name else '') + ' '.join(sentences)
VALUES = {'PlantSeed':'식물·씨앗', 'FruiNect':'열매·꽃꿀',
          'Invertebrate':'무척추동물', 'VertFishScav':'척추동물·물고기·사체',
          'Forest':'숲', 'Shrubland':'관목 지대', 'Woodland':'성긴 숲',
          'Grassland':'초지', 'Rock':'바위 지대', 'Human Modified':'인공·변형 환경',
          'Coastal':'해안', 'Marine':'바다', 'Riverine':'하천', 'Desert':'사막',
          'Insessorial':'나무 위 생활', 'Aerial':'공중 생활', 'Terrestrial':'지상 생활',
          'Generalist':'다양한 생활 방식', 'Wetland':'습지', 'Aquatic':'수생', 'Herbivore aquatic':'수생 초식',
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


def species_sections(taxon, traits, notes):
    """Small attributed sections shared by every species chat response."""
    fields = {}
    for trait in traits:
        if isinstance(trait, dict) and trait.get('source_name') and trait.get('source_url') and trait.get('display'):
            fields.setdefault(trait.get('name'), trait)
    def fact(name):
        trait = fields.get(name)
        if trait is None:
            return None
        unit = f" {trait['unit']}" if trait.get('unit') else ''
        prefix = '평균 ' if trait.get('summary_statistic') == 'mean' else ''
        return {'text':f"{prefix}{LABELS[name]}: {trait['display']}{unit}",
                **{key:trait.get(key) for key in ('source_name', 'source_url', 'license_name', 'license_url')}}
    basic = [{'text':'학명: ' + taxon['scientific_name']}] if taxon.get('scientific_name') else []
    weight = fact('body_mass')
    if weight:
        basic.append(weight)
    appearance = notes.get('appearance', [])
    if not appearance:
        appearance = [value for name in ('beak_length_culmen', 'wing_length', 'tail_length') if (value := fact(name))]
    ecology = [value for name in ('habitat', 'primary_lifestyle', 'diet_category') if (value := fact(name))]
    if 'diet_category' not in fields and (diet := fact('trophic_niche')):
        ecology.append(diet)
    return [{'key':key, 'title':title, 'items':items, 'empty_text':empty}
            for key,title,items,empty in (
                ('basic', '기본 정보', basic, '확인된 기본 정보가 없습니다.'),
                ('appearance', '외관 특징', appearance, '깃털 색과 생김새를 설명할 자료를 아직 확인하지 못했습니다.'),
                ('ecology', '생활과 먹이', ecology, '서식 환경과 먹이 자료를 아직 확인하지 못했습니다.'),
                ('fun_facts', '재미있는 사실', notes.get('fun_facts', []), '출처로 확인할 수 있는 재미있는 사실을 아직 찾지 못했습니다.'),
            )]


def create_species_flow(resolve, traits, photos=licensed_images, conservation=None, notes=None):
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
    def trait_stage(lineage):
        try:
            return {'traits':traits(lineage), 'warnings':[]}
        except Exception:
            return {'traits':[], 'warnings':['종 특성 제공처를 현재 조회할 수 없습니다.']}
    def conservation_stage(lineage):
        try:
            value = conservation(lineage) if conservation is not None else None
            return {'conservation':value or unconfirmed_conservation(), 'warnings':[]}
        except Exception:
            return {'conservation':unconfirmed_conservation(),
                    'warnings':['보전 상태를 현재 확인할 수 없습니다.']}
    def notes_stage(lineage):
        try:
            value = notes(lineage) if notes is not None else {}
            return {'notes':value or {}, 'warnings':[]}
        except Exception:
            return {'notes':{}, 'warnings':['외관 특징과 재미있는 사실의 추가 자료를 현재 조회할 수 없습니다.']}
    def assemble(state):
        lineage = state['lineage']
        taxon = asdict(lineage.items[-1])
        return {'taxon':taxon, 'lineage':asdict(lineage),
                'traits':state['traits']['traits'], 'images':state['media']['images'],
                'conservation':state['conservation']['conservation'],
                'summary':species_summary(taxon, state['traits']['traits']),
                'sections':species_sections(taxon, state['traits']['traits'], state['notes']['notes']),
                'warnings':state['traits']['warnings'] + state['media']['warnings'] + state['conservation']['warnings'] + state['notes']['warnings'],
                'vegetation_note':'구체적인 식물·식생 목록은 아직 수집되지 않았습니다.'}
    return (RunnableLambda(resolve_species)
            | RunnableParallel(lineage=RunnablePassthrough(), traits=RunnableLambda(trait_stage), media=RunnableLambda(image_stage), conservation=RunnableLambda(conservation_stage), notes=RunnableLambda(notes_stage))
            | RunnableLambda(assemble))
