"""Bounded graph-relationship questions answered from fixed, read-only Cypher.

The parser is deterministic and only recognises a closed set of question
shapes; it never builds Cypher from user text. Every traversal is bound to
the active AviList concept set/release and to allowed TraitClaim/EvidenceUnit
provenance, and fails closed on mismatched or missing provenance.

Category sharing (AVONET habitat / trophic_niche, EltonTraits diet
composition) is never presented as eating the same food, co-occurrence or
predation. There is no plant-level diet data: questions about a specific
fruit are answered as insufficient data, never re-phrased into a category.
"""
from dataclasses import asdict, dataclass
import json
import math
import re
from urllib.parse import urlsplit

from .species_profile import LABELS, SOURCE_CATEGORY, VALUES, SpeciesNotFoundError, read_traits
from .species_questions import bounded_korean_name
from .species_scope import scope_matches, scope_query_parameters, with_species_scope
from .taxonomy_lineage import reference_korean_names, sourced_korean_names, with_korean_display_name

MAX_QUESTION_CHARS = 200
RESULT_LIMIT = 20
GRAPH_QUESTION_KINDS = ('common_taxonomy', 'same_genus', 'korea_same_genus', 'order_fruit', 'habitat_shared_diet',
                        'habitat_different_diet', 'specific_fruit', 'taxon_traits', 'shared_diet')
TRAIT_PIPELINES = (('reference-avonet', 'CC BY 4.0'), ('reference-taxonomy-traits', 'CC0 1.0'))
RANK_LABELS = {'order': '목', 'family': '과', 'genus': '속', 'species': '종'}
TAXON_RANKS = ('order', 'family', 'genus', 'species', 'subspecies')
TAXON_RANK_LABELS = {**RANK_LABELS, 'subspecies': '아종'}
_AVONET_TEXT = {
    'habitat': ('Forest', 'Shrubland', 'Woodland', 'Grassland', 'Rock', 'Wetland', 'Human Modified', 'Coastal',
                'Marine', 'Riverine', 'Desert'),
    'habitat_density_category': ('dense', 'semi_open', 'open'),
    'primary_lifestyle': ('Insessorial', 'Terrestrial', 'Generalist', 'Aerial', 'Aquatic'),
    'trophic_level': ('Herbivore', 'Carnivore', 'Omnivore', 'Scavenger'),
    'trophic_niche': ('Frugivore', 'Omnivore', 'Invertivore', 'Granivore', 'Herbivore terrestrial', 'Nectarivore',
                      'Aquatic predator', 'Vertivore', 'Scavenger', 'Herbivore aquatic'),
}
_AVONET_NUMBERS = {'body_mass': 'g', 'beak_depth': 'mm', 'beak_length_culmen': 'mm', 'beak_length_nares': 'mm',
                   'beak_width': 'mm', 'tarsus_length': 'mm', 'wing_length': 'mm', 'tail_length': 'mm'}
DIET_SHARE_KEYS = ('invertebrate', 'endotherm_vertebrate', 'ectotherm_vertebrate', 'fish', 'unknown_vertebrate',
                   'carrion', 'fruit', 'nectar', 'seed', 'other_plant')
# A share over several source keys: met when any of them is above 0 (= their sum is). 고기 is the three
# vertebrate components; fish and carrion stay separate keys, and diet_category VertFishScav is not 고기.
DIET_SHARE_GROUPS = {'meat': ('endotherm_vertebrate', 'ectotherm_vertebrate', 'unknown_vertebrate')}
# trait_name -> (pipeline, value kind, allowed values or unit). Only fields verified on the active TEST data.
TRAIT_CONDITIONS = {
    **{name: ('reference-avonet', 'text', values) for name, values in _AVONET_TEXT.items()},
    **{name: ('reference-avonet', 'number', unit) for name, unit in _AVONET_NUMBERS.items()},
    'diet_category': ('reference-taxonomy-traits', 'text', ('PlantSeed', 'FruiNect', 'Invertebrate', 'Omnivore',
                                                            'VertFishScav')),
    'diet_distribution': ('reference-taxonomy-traits', 'share', DIET_SHARE_KEYS + tuple(DIET_SHARE_GROUPS)),
}
CONDITION_OPS = {'text': ('eq',), 'share': ('share_gt',), 'number': ('num_gte', 'num_lte', 'num_gt', 'num_lt')}
HABITATS = {'숲': 'Forest', '산림': 'Forest', '성긴 숲': 'Woodland', '관목 지대': 'Shrubland', '관목지': 'Shrubland',
            '초지': 'Grassland', '초원': 'Grassland', '습지': 'Wetland', '해안': 'Coastal', '바다': 'Marine',
            '하천': 'Riverine', '강': 'Riverine', '사막': 'Desert', '바위 지대': 'Rock',
            '인공 환경': 'Human Modified', '도시': 'Human Modified'}
# Only "지수(ending) diet value" -> positive fruit share; Java and Python regex agree.
FRUIT_POSITIVE = r'.*"fruit"\s*:\s*(?!0+(?:\.0+)?\s*[,}])[0-9]+(?:\.[0-9]+)?\s*[,}].*'

LIMITATIONS = {
    'graph_claims_only': ('그래프에 종과 직접 연결된 형질 주장만 검색합니다. 프로필에서 분류 대응으로 복원되는 형질이나 '
                          '보충 자료(BirdBase 등)는 목록에 포함되지 않아 일부 종이 빠질 수 있습니다.'),
    'category_not_food': ('먹이를 공유한다는 것은 같은 자료의 먹이 생태 범주가 같다는 뜻입니다. 실제로 같은 먹이를 '
                          '먹거나 함께 산다는 근거는 아닙니다.'),
    'different_diet': ('서식 환경 범주가 같고 먹이 생태 범주가 다른 종입니다. 실제로 같은 장소에서 함께 살거나 '
                       '먹이 경쟁을 하지 않는다는 뜻은 아닙니다.'),
    'tree_fruit': '나무열매만 먹는 종을 구분한 자료는 없습니다. 아래 목록은 나무와 풀을 구분하지 않은 열매 먹이 범주를 참고한 결과입니다.',
    'no_plant_level_diet': '특정 식물의 열매나 먹이 식물을 종 단위로 기록한 자료가 그래프에 없습니다.',
    'frugivore_only': ("AVONET 먹이 생태 범주가 '열매 섭식(Frugivore)'인 종만 포함합니다. "
                       '열매를 일부 먹는 잡식성 종은 빠집니다.'),
    'fruit_share': ('EltonTraits 먹이 구성에서 열매 비율이 0보다 큰 종입니다. 열매가 주식이라는 뜻은 아니며 '
                    '구성비는 자료 저자가 문헌으로 정리한 10% 단위 범주값입니다.'),
    'elton_interpolated': ('EltonTraits 확실성 D1·D2(근연 분류군에서 보간한 추정값) 먹이 자료는 제외하고, '
                           '확실성 A·B·C 자료만 사용했습니다.'),
    'taxonomy_not_distance': 'AviList 분류 계층의 공통 상위 분류이며 진화적 거리나 유사도 순위가 아닙니다.',
    'korea_record': ('국내 기록은 KOS 공식목록 가-1 또는 AviList 분포 문구 근거입니다. 텃새·철새·미조 구분이나 '
                     '현재 서식을 뜻하지 않습니다.'),
    'scope_conflict': '질문의 국내 기록 조건이 선택한 종 범위와 겹치지 않습니다.',
    'target_out_of_scope': '기준 종이 선택한 종 범위에 포함되지 않습니다.',
    'context_unavailable': '활성 형질 자료의 분류 릴리스를 확인하지 못했습니다.',
    'target_trait_missing': '기준 종의 해당 형질 자료를 확인하지 못했습니다.',
    'no_food_key': ('먹이 구성은 현재 조회하는 EltonTraits 먹이 성분 자료의 10개 범주로만 확인합니다. 곡물·잎처럼 '
                    '범주와 다르게 부르는 먹이의 섭식 여부는 이 범주만으로 확인할 수 없습니다.'),
}
# Foods named in a question that no diet_distribution key is: the key(s) a user may ask instead. Guidance only;
# a food is never queried as one of these.
FOOD_GAPS = {'벌레': ('invertebrate',), '곡식': ('seed',), '곡물': ('seed',), '꿀': ('nectar',),
             '잎': ('other_plant',), '육류': ('meat',)}
# What a share answer covers, stated with every condition on that key.
SHARE_SCOPE = {'invertebrate': "원자료 범주는 ‘무척추동물’로, 곤충이 아닌 무척추동물을 먹는 경우도 포함합니다.",
               'meat': ('고기는 온혈 척추동물·변온 척추동물·기타 척추동물 성분 중 하나라도 0보다 큰 경우이며, '
                        '물고기·사체 성분은 포함하지 않습니다.')}


@dataclass(frozen=True)
class TraitCondition:
    """One AND condition on a directly asserted trait claim: ``eq`` value_text, ``share_gt`` a diet
    composition key above ``threshold`` (percent), or ``num_*`` value_num against ``threshold`` in ``unit``."""
    trait_name: str
    op: str
    value: str | None = None
    threshold: float | None = None
    unit: str | None = None
    qualifier: str | None = None   # 'tree_fruit': asked for tree fruit; the data has no tree/herb split


@dataclass(frozen=True)
class GraphQuestion:
    kind: str
    names: tuple[str, ...] = ()
    rank_name: str | None = None   # order_fruit: the order; taxon_traits: the taxon surface (None = whole catalog)
    habitat: str | None = None
    criterion: str | None = None
    group: str | None = None
    conditions: tuple[TraitCondition, ...] = ()


_KO = r'[가-힣]+?(?:\s+[가-힣]+?){0,3}'
_SCI = r'[A-Z][a-z]+\s+[a-z]+'
_NAME = rf'(?:{_KO}|{_SCI})'
_AND = r'(?:와|과|랑|이랑|하고)'
_ASK = (r'(?:\s*(?:알려\s*줘|알려\s*주세요|뭐야|뭐니|뭔가요|무엇인가요|비교해\s*줘|비교해\s*주세요|'
        r'해\s*줘|해\s*주세요|보여\s*줘|보여\s*주세요|'
        r'(?:어떤|어느)\s*(?:게|것들?|종들?|새들?)(?:이|가)?|뭐가|무엇이|'
        r'있니|있어(?:요)?|있나요|있을까(?:요)?|있습니까|있는지|알고\s*싶어(?:요)?|는|은|\?))*')
_BIRD = r'(?:새|종|새들|종들)(?:은|는|이|가|를|을)?'
_KOREA = r'(?:국내(?:에서|에)?\s*기록된|국내\s*기록(?:이\s*있는|된)?|한국(?:에서|에)?\s*기록된|국내(?:에서)?\s*관찰\s*기록이\s*있는)'
_HABITAT = '|'.join(sorted((re.escape(k) for k in HABITATS), key=len, reverse=True))
_ORDER_SCOPE = r'(?:에\s*속하는\s*)?(?:(?:새들?|종들?)\s*)?(?:중\s*(?:에서|에)?|에서)'
_PATTERNS = (
    ('common_taxonomy', rf'(?P<a>{_NAME}){_AND}\s*(?P<b>{_NAME})(?:의|은|는)?\s*'
                        rf'(?:공통\s*(?:상위\s*)?분류(?:군)?|분류(?:\s*경로)?(?:를|을)?\s*비교|분류상\s*공통점|공통된\s*분류)'
                        rf'(?:은|는|이|가|을|를)?{_ASK}'),
    ('common_taxonomy', rf'(?P<a>{_NAME}){_AND}\s*(?P<b>{_NAME})(?:은|는)?\s*(?:어떤|무슨)\s*관계(?:야|니|인가요|예요|에요|인지)?{_ASK}'),
    ('korea_same_genus', rf'(?P<a>{_NAME}){_AND}\s*같은\s*속(?:인|에\s*속하는|의)?\s*(?:{_BIRD}\s*)?(?:중(?:에서|에)?\s*)?'
                         rf'{_KOREA}\s*{_BIRD}{_ASK}'),
    ('korea_same_genus', rf'{_KOREA}\s*(?P<a>{_NAME}){_AND}\s*같은\s*속(?:인|에\s*속하는|의)?\s*{_BIRD}{_ASK}'),
    # "한국에 기록된 오리 중 ...": the group word is kept and must be confirmed by the target's lineage.
    ('korea_same_genus', rf'{_KOREA}\s*(?:(?P<group>[가-힣]{{1,10}})\s*)?중(?:에서|에)?\s*(?P<a>{_NAME}){_AND}\s*같은\s*속(?:인|에\s*속하는|의)?\s*{_BIRD}{_ASK}'),
    ('same_genus', rf'(?P<a>{_NAME}){_AND}\s*같은\s*속(?:인|에\s*속하는|의)?\s*{_BIRD}{_ASK}'),
    ('order_fruit', rf'(?P<rank>{_KO}목|[A-Z][a-z]+formes)\s*(?:{_ORDER_SCOPE})?\s*'
                    rf'(?P<criterion>과실식|열매\s*섭식|(?:나무\s*)?열매(?:를)?\s*먹고\s*사는|(?:나무\s*)?열매(?:를)?\s*먹는)\s*(?:을\s*하는\s*)?{_BIRD}{_ASK}'),
    ('specific_fruit', rf'(?P<habitat>{_HABITAT})에\s*사는\s*새\s*중(?:에|에서)?\s*(?P<a>{_NAME}){_AND}\s*같은\s*열매(?:를|을)?\s*먹는\s*{_BIRD}{_ASK}'),
    ('specific_fruit', rf'(?P<a>{_NAME}){_AND}\s*같은\s*열매(?:를|을)?\s*먹는\s*{_BIRD}{_ASK}'),
    ('specific_fruit', rf'(?P<rank>{_KO}목|[A-Z][a-z]+formes)\s*(?:{_ORDER_SCOPE})?\s*(?P<plant>[가-힣]+)\s*열매(?:를|을)?\s*먹(?:는|고\s*사는)\s*{_BIRD}{_ASK}'),
    ('habitat_shared_diet', rf'(?P<habitat>{_HABITAT})에\s*사는\s*새\s*중(?:에|에서)?\s*(?P<a>{_NAME}){_AND}\s*'
                            rf'(?:같은\s*먹이\s*범주를\s*공유하는|먹이\s*범주(?:가|를)?\s*(?:같은|공유하는)|'
                            rf'먹이(?:가|를)?\s*(?:같은|공유하는)|같은\s*먹이를\s*먹는)\s*{_BIRD}{_ASK}'),
    ('habitat_different_diet', rf'(?P<a>{_NAME}){_AND}\s*(?:서식지|서식\s*환경)(?:가|이)?\s*(?:겹치면서|같으면서|같고|겹치고)\s*'
                               rf'(?:먹이|식성|먹이\s*범주)(?:가|는|이)?\s*다른\s*{_BIRD}{_ASK}'),
)
_COMPILED = tuple((kind, re.compile(pattern)) for kind, pattern in _PATTERNS)
# Words the plant slot can capture that are not a plant name.
_NOT_PLANTS = frozenset(('중', '중에', '중에서', '에서', '의', '과실', '나무', '같은', '다른'))


# Tokens that make a captured span a phrase ("오리 중 청둥오리"), not one name.
_NAME_STOPWORDS = frozenset(('중', '중에', '중에서', '가운데', '사이'))


def _valid_name(name):
    name = name.strip()
    if re.fullmatch(_SCI, name):
        return True
    return (bool(re.fullmatch(r'[가-힣\s]+', name)) and bounded_korean_name(name)
            and not any(token in _NAME_STOPWORDS for token in name.split()))


def parse_graph_question(question):
    """Return a GraphQuestion for one of the closed question shapes, else None."""
    if not isinstance(question, str):
        return None
    normalized = question.strip().rstrip('.!?？').strip()
    if not normalized or len(normalized) > MAX_QUESTION_CHARS:
        return None
    for kind, pattern in _COMPILED:
        match = pattern.fullmatch(normalized)
        if not match:
            continue
        groups = match.groupdict()
        names = tuple(groups[key].strip() for key in ('a', 'b') if groups.get(key))
        if not all(_valid_name(name) for name in names) or len(set(names)) != len(names):
            continue
        habitat = HABITATS.get(groups['habitat'].strip()) if groups.get('habitat') else None
        criterion = groups.get('criterion')
        if criterion is not None:
            normalized_criterion = re.sub(r'\s+', '', criterion)
            criterion = ('frugivore' if normalized_criterion in ('과실식', '열매섭식')
                         else 'tree_fruit_share' if normalized_criterion.startswith('나무열매') else 'fruit_share')
        if kind == 'specific_fruit' and groups.get('plant') in _NOT_PLANTS:
            continue
        group = groups.get('group')
        group = None if group in (None, '새', '종', '새들') else group
        return GraphQuestion(kind, names, groups.get('rank'), habitat, criterion, group)
    return None


# --- provenance helpers ---------------------------------------------------

def _web_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username
    except ValueError:
        return False


def _source(name, url):
    return {'source_name': name, 'source_url': url}


def _korean_reference_names():
    return {taxon_id: {key: label[key] for key in ('name', 'scientific_name', 'english_name')}
            for taxon_id, label in sourced_korean_names().items()}


def _trait_sources(store, concept_set_id=None, taxonomy_release=None):
    """Active trait datasets for one AviList context; mismatches are dropped."""
    sources, contexts = {}, set()
    if store is None:
        return sources, None
    for pipeline, license_name in TRAIT_PIPELINES:
        context = store.active_release_context(pipeline)
        if context is None:
            continue
        cursor = context.cursor
        key = (cursor.get('concept_set_id', cursor.get('taxonomy_concept_set_id')), cursor.get('taxonomy_release'))
        if concept_set_id is not None and key != (concept_set_id, taxonomy_release):
            continue
        contexts.add(key)
        sources[pipeline] = {'dataset_id': context.dataset.id, 'source_name': context.dataset.name,
                             'release': cursor.get('trait_release', context.release.release_key),
                             'license_name': license_name}
    if len(contexts) != 1:
        return {}, None
    return sources, next(iter(contexts))


_SCOPE_PREDICATE = ("($species_scope='all' OR ($species_scope='unknown' AND coalesce($scope_known[peer.id],'')<>peer.scientific_name) "
                    "OR $scope_selected[peer.id]=peer.scientific_name)")
_PEER_NAMES = """
OPTIONAL MATCH (peer)-[:HAS_VERNACULAR_NAME]->(en:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'})
WHERE en.dataset_id=peer.dataset_id AND en.source_release=peer.source_release
WITH peer, support, lineage, min(en.name) AS english_name
WITH peer, support, lineage, english_name, $korean_reference_names[peer.id] AS reference
WITH peer, support, lineage, english_name,
     CASE WHEN reference.scientific_name=peer.scientific_name AND reference.english_name=english_name
          THEN reference.name ELSE null END AS korean_name
RETURN {taxon_id:peer.id, rank:peer.rank, scientific_name:peer.scientific_name,
        korean_name:korean_name, english_name:english_name} AS taxon, support, lineage
ORDER BY CASE WHEN $species_scope='outside' THEN CASE WHEN english_name IS NULL THEN 1 ELSE 0 END
              ELSE CASE WHEN korean_name IS NULL THEN 1 ELSE 0 END END,
         CASE WHEN $species_scope='outside' THEN coalesce(english_name,korean_name,peer.scientific_name)
              ELSE coalesce(korean_name,english_name,peer.scientific_name) END, peer.id
LIMIT $limit
"""
_CONCEPT = "MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})\n"
_PATH_GUARD = """  AND all(link IN relationships(path) WHERE link.concept_set_id=$concept_set_id)
  AND all(node IN nodes(path) WHERE node:Taxon AND node:BirdTaxon AND node.policy_status='allowed'
      AND node.source_release=$taxonomy_release AND EXISTS { MATCH (node)-[:IN_CONCEPT_SET]->(concept) })
"""
_CLAIM_GUARD = """({alias}.inferred=false OR ({alias}.inferred IS NULL AND {alias}.trait_name IN ['diet_category','diet_distribution']
       AND {alias}.certainty IN ['A','B','C'])) AND ({alias}.taxonomy_release IS NULL OR {alias}.taxonomy_release=$taxonomy_release)
  AND {ev}.dataset_id={alias}.dataset_id AND {ev}.source_record_id={alias}.source_record_id
  AND ({ev}.locator STARTS WITH 'https://' OR {ev}.locator STARTS WITH 'http://')"""

SOURCE_QUERY = _CONCEPT + "RETURN concept.snapshot_uri AS source_url, concept.title AS source_name\n"
TAXON_QUERY = _CONCEPT + """MATCH (taxon:Taxon:BirdTaxon {rank:$rank, scientific_name:$scientific_name, source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
RETURN taxon.id AS taxon_id, taxon.scientific_name AS scientific_name
LIMIT 2
"""
GENUS_PEERS_QUERY = _CONCEPT + """MATCH (genus:Taxon:BirdTaxon {id:$genus_id, rank:'genus', source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH path=(genus)-[:PARENT_OF*1..2]->(peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})
WHERE peer.id <> $target_id AND """ + _SCOPE_PREDICATE + "\n" + _PATH_GUARD + """WITH DISTINCT peer, null AS support, null AS lineage
""" + _PEER_NAMES
ORDER_TRAIT_QUERY = _CONCEPT + """MATCH (rank_taxon:Taxon:BirdTaxon {id:$order_id, rank:'order', source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH path=(rank_taxon)-[:PARENT_OF*1..4]->(peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})
WHERE """ + _SCOPE_PREDICATE + "\n" + _PATH_GUARD + """WITH concept, peer, head(collect([node IN nodes(path) | {taxon_id:node.id, rank:node.rank, scientific_name:node.scientific_name}])) AS lineage
MATCH (claim:TraitClaim {policy_status:'allowed', dataset_id:$dataset_id, source_release:$release, trait_name:$trait_name})-[:ASSERTS_ABOUT]->(peer)
MATCH (claim)-[:SUPPORTED_BY]->(evidence:EvidenceUnit {policy_status:'allowed'})
WHERE ((claim.value_text IS NOT NULL AND claim.value_text=$value_text)
       OR ($value_json_pattern IS NOT NULL AND claim.value_json =~ $value_json_pattern))
  AND """ + _CLAIM_GUARD.format(alias='claim', ev='evidence') + """
WITH peer, lineage, claim, evidence ORDER BY evidence.id
WITH peer, lineage, head(collect({trait_name:claim.trait_name, value_text:claim.value_text, value_json:claim.value_json,
     certainty:claim.certainty, source_url:evidence.locator, citation:evidence.citation})) AS first
WITH peer, lineage, [first] AS support
""" + _PEER_NAMES
HABITAT_DIET_QUERY = _CONCEPT + """MATCH (habitat:TraitClaim {policy_status:'allowed', dataset_id:$dataset_id, source_release:$release, trait_name:'habitat', value_text:$habitat})-[:ASSERTS_ABOUT]->(peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (habitat)-[:SUPPORTED_BY]->(habitatEvidence:EvidenceUnit {policy_status:'allowed'})
WHERE peer.id <> $target_id AND """ + _SCOPE_PREDICATE + "\n  AND " + _CLAIM_GUARD.format(alias='habitat', ev='habitatEvidence') + """
WITH DISTINCT peer, habitat, habitatEvidence
MATCH (niche:TraitClaim {policy_status:'allowed', dataset_id:$dataset_id, source_release:$release, trait_name:'trophic_niche'})-[:ASSERTS_ABOUT]->(peer)
MATCH (niche)-[:SUPPORTED_BY]->(nicheEvidence:EvidenceUnit {policy_status:'allowed'})
WHERE niche.value_text IS NOT NULL
  AND (($same_niche AND niche.value_text=$niche) OR (NOT $same_niche AND niche.value_text<>$niche))
  AND """ + _CLAIM_GUARD.format(alias='niche', ev='nicheEvidence') + """
WITH peer, habitat, habitatEvidence, niche, nicheEvidence ORDER BY habitatEvidence.id, nicheEvidence.id
WITH peer, head(collect([{trait_name:'habitat', value_text:habitat.value_text, value_json:null,
          source_url:habitatEvidence.locator, citation:habitatEvidence.citation},
     {trait_name:'trophic_niche', value_text:niche.value_text, value_json:null,
          source_url:nicheEvidence.locator, citation:nicheEvidence.citation}])) AS support, null AS lineage
""" + _PEER_NAMES
# shared_diet: HABITAT_DIET_QUERY without the habitat match; the niche is the target's own AVONET value.
SHARED_DIET_QUERY = _CONCEPT + """MATCH (niche:TraitClaim {policy_status:'allowed', dataset_id:$dataset_id, source_release:$release, trait_name:'trophic_niche', value_text:$niche})-[:ASSERTS_ABOUT]->(peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH (niche)-[:SUPPORTED_BY]->(nicheEvidence:EvidenceUnit {policy_status:'allowed'})
WHERE peer.id <> $target_id AND """ + _SCOPE_PREDICATE + "\n  AND " + _CLAIM_GUARD.format(alias='niche', ev='nicheEvidence') + """
WITH peer, niche, nicheEvidence ORDER BY nicheEvidence.id
WITH peer, head(collect([{trait_name:'trophic_niche', value_text:niche.value_text, value_json:null,
          source_url:nicheEvidence.locator, citation:nicheEvidence.citation}])) AS support, null AS lineage
""" + _PEER_NAMES
TAXON_BY_NAME_QUERY = _CONCEPT + """MATCH (taxon:Taxon:BirdTaxon {scientific_name:$scientific_name, source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE taxon.rank IN $ranks
RETURN taxon.id AS taxon_id, taxon.rank AS rank, taxon.scientific_name AS scientific_name
LIMIT 2
"""
# Every condition is a map parameter checked by a closed CASE; no query text comes from the question.
# `claims` keeps, per condition, every guarded claim of that trait on the peer with `ok` = it meets the
# condition, so "no data" (no claim) and "data, but not matching" stay distinguishable.
_TRAIT_PEERS = """WITH peer, lineage, [cond IN $conditions |
     [(peer)<-[:ASSERTS_ABOUT]-(c:TraitClaim)-[:SUPPORTED_BY]->(e:EvidenceUnit)
      WHERE c.policy_status='allowed' AND e.policy_status='allowed' AND c.dataset_id=cond.dataset_id
        AND c.source_release=cond.release AND c.trait_name=cond.trait_name
        AND """ + _CLAIM_GUARD.format(alias='c', ev='e') + """
      | {ok: CASE cond.op
              WHEN 'eq' THEN c.value_text = cond.value
              WHEN 'share_gt' THEN c.value_json =~ cond.pattern
              WHEN 'num_gte' THEN c.unit = cond.unit AND c.value_num >= cond.threshold
              WHEN 'num_lte' THEN c.unit = cond.unit AND c.value_num <= cond.threshold
              WHEN 'num_gt' THEN c.unit = cond.unit AND c.value_num > cond.threshold
              WHEN 'num_lt' THEN c.unit = cond.unit AND c.value_num < cond.threshold
              ELSE false END,
         evidence_id:e.id, trait_name:c.trait_name, value_text:c.value_text, value_json:c.value_json,
         value_num:c.value_num, unit:c.unit, certainty:c.certainty, source_url:e.locator, citation:e.citation}]] AS claims
WITH peer, lineage, [found IN claims | size(found) > 0] AS present,
     [found IN claims | reduce(best = null, x IN [y IN found WHERE y.ok] |
        CASE WHEN best IS NULL OR x.evidence_id < best.evidence_id THEN x ELSE best END)] AS support
WITH collect(CASE WHEN all(s IN support WHERE s IS NOT NULL) THEN {peer:peer, lineage:lineage, support:support} END) AS matched,
     count(peer) AS scoped, sum(CASE WHEN all(p IN present WHERE p) THEN 1 ELSE 0 END) AS evaluable
UNWIND (CASE WHEN size(matched) = 0 THEN [null] ELSE matched END) AS m
WITH m.peer AS peer, m.support AS support, m.lineage AS lineage,
     {scoped:scoped, evaluable:evaluable, matched:size(matched)} AS stats
""" + _PEER_NAMES.replace('support, lineage', 'support, lineage, stats')
TAXON_TRAITS_QUERY = _CONCEPT + """MATCH (root:Taxon:BirdTaxon {id:$root_id, rank:$root_rank, source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MATCH path=(root)-[:PARENT_OF*0..4]->(peer:Taxon:BirdTaxon {rank:$target_rank, source_release:$taxonomy_release, policy_status:'allowed'})
WHERE """ + _SCOPE_PREDICATE + "\n" + _PATH_GUARD + """WITH concept, peer, head(collect(CASE WHEN length(path) = 0 THEN null
     ELSE [node IN nodes(path) | {taxon_id:node.id, rank:node.rank, scientific_name:node.scientific_name}] END)) AS lineage
""" + _TRAIT_PEERS
CATALOG_TRAITS_QUERY = _CONCEPT + """MATCH (peer:Taxon:BirdTaxon {rank:'species', source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
WHERE """ + _SCOPE_PREDICATE + """
WITH peer, null AS lineage
""" + _TRAIT_PEERS


# --- answer assembly -------------------------------------------------------

def _payload(status, title, text, items=(), sources=(), limitations=(), has_more=False, **extra):
    unique_sources = []
    for source in sources:
        if source not in unique_sources:
            unique_sources.append(source)
    return {'status': status, 'title': title, 'text': text, 'items': list(items), 'sources': unique_sources,
            'limitations': list(dict.fromkeys(limitations)), 'has_more': bool(has_more), **extra}


def _object_particle(word):
    return '을' if (ord(word[-1]) - 0xAC00) % 28 else '를'


def unsupported_food_answer(question, spans):
    """No-DB insufficient_data payload for foods with no data key; nothing is queried or substituted.

    ``spans`` are the food words of ``question`` (FOOD_GAPS keys). The suggested question replaces only those
    words, so the taxon and every other condition stay as asked; it is offered only when each food has one key.
    """
    foods = list(dict.fromkeys(span.text for span in spans))
    named = '·'.join(foods)
    keys = list(dict.fromkeys(key for food in foods for key in FOOD_GAPS[food]))
    labels = '·'.join(f"‘{share_word(key)}’" for key in keys)
    text = (f'{named}만 따로 구분한 기록은 현재 조회하는 먹이 성분 자료로 확인할 수 없습니다. 자료는 {labels} 범주로 '
            f'기록돼 요청한 {named} 섭식 여부를 이 범주만으로는 확인할 수 없습니다. 범주를 바꿔 조회하지 않았습니다.')
    if all(len(FOOD_GAPS[food]) == 1 for food in foods):
        suggestion, cursor = '', 0
        for span in sorted(spans, key=lambda s: s.start):
            label = VALUES[FOOD_GAPS[span.text][0]].split(' (')[0]
            tail = question[span.end:span.end + 1]
            suggestion += question[cursor:span.start] + label
            cursor = span.end
            if tail in ('을', '를'):
                suggestion += _object_particle(label)
                cursor += 1
        suggestion += question[cursor:]
        text += f' 해당 범주로 찾으려면 “{suggestion.strip()}”처럼 질문해 주세요.'
    return _payload('insufficient_data', '먹이 자료 범위', text, limitations=[LIMITATIONS['no_food_key']],
                    paths=[], taxon=None, conditions=[], coverage=None)


def share_word(key):
    """Display of a diet composition key with its source scope (a group lists its source components)."""
    if key in DIET_SHARE_GROUPS:
        return f"{VALUES[key]} ({'·'.join(SOURCE_CATEGORY[part] for part in DIET_SHARE_GROUPS[key])})"
    return VALUES[key]


def _label(taxon):
    return (taxon.get('display_name') or taxon.get('korean_name') or taxon.get('english_name')
            or taxon.get('scientific_name'))


def _resolve_species(resolve, name):
    lineage = resolve(name)
    if lineage is None or not lineage.items or lineage.items[-1].rank != 'species':
        raise SpeciesNotFoundError(name)
    return lineage


def _taxonomy_source(repository, concept_set_id, taxonomy_release):
    rows = repository._run(SOURCE_QUERY, concept_set_id=concept_set_id, taxonomy_release=taxonomy_release)
    if len(rows) != 1 or not rows[0].get('source_name') or not _web_url(rows[0].get('source_url')):
        raise ValueError('Taxonomy provenance unavailable')
    return _source(rows[0]['source_name'], rows[0]['source_url'])


def _rank_name(item):
    korean = item.korean_name or (reference_korean_names().get(f'{item.rank}:{item.scientific_name.casefold()}') or {}).get('name')
    return f"{korean} ({item.scientific_name})" if korean and item.rank != 'species' else (
        korean or item.scientific_name)


def _group_label(item):
    korean = item.korean_name or (reference_korean_names().get(f'{item.rank}:{item.scientific_name.casefold()}') or {}).get('name')
    suffix = RANK_LABELS[item.rank]
    return korean[:-len(suffix)] if korean and korean.endswith(suffix) and len(korean) > len(suffix) else None


def _lineage_path(lineage):
    return ' > '.join(_rank_name(item) for item in lineage.items if item.rank in RANK_LABELS)


def _scoped(taxon, species_scope, concept_set_id, taxonomy_release):
    return with_species_scope(with_korean_display_name(taxon), species_scope, concept_set_id, taxonomy_release)


def _lineage_text(nodes, peer_id, root_id):
    if (not isinstance(nodes, list) or len(nodes) < 2 or not all(isinstance(node, dict) for node in nodes)
            or nodes[0].get('taxon_id') != root_id or nodes[-1].get('taxon_id') != peer_id
            or any(node.get('rank') not in RANK_LABELS or not node.get('scientific_name') for node in nodes)):
        raise ValueError('Invalid graph question lineage path')
    names = []
    for node in nodes[:-1]:
        label = (reference_korean_names().get(f"{node['rank']}:{node['scientific_name'].casefold()}") or {}).get('name')
        names.append(f"{label} ({node['scientific_name']})" if label else node['scientific_name'])
    return ' > '.join(names + [nodes[-1]['scientific_name']])


def _peer_items(rows, species_scope, concept_set_id, taxonomy_release, trait_sources=None, target_id=None,
                taxonomy_source=None, root_id=None):
    items = []
    for row in rows:
        taxon = row.get('taxon') or {}
        if taxon.get('rank') != 'species' or not taxon.get('taxon_id') or taxon['taxon_id'] == target_id:
            raise ValueError('Invalid graph question peer')
        peer = _scoped(taxon, species_scope, concept_set_id, taxonomy_release)
        if not scope_matches(peer, species_scope, concept_set_id, taxonomy_release):
            continue
        paths = []
        for support in row.get('support') or ():
            if not isinstance(support, dict) or not _web_url(support.get('source_url')):
                raise ValueError('Invalid graph question trait provenance')
            name = support.get('trait_name')
            source_name = (trait_sources or {}).get(name)
            if name == 'diet_distribution':
                fruit = _fruit_share(support.get('value_json'))
                if fruit is None:
                    raise ValueError('Diet composition does not match the fruit filter')
                text = f"{LABELS[name]}: {VALUES['fruit']} {fruit:g}% (자료의 먹이 구성비)"
                certainty = support.get('certainty')
                if certainty not in ('A', 'B', 'C'):
                    raise ValueError('Interpolated or unqualified diet composition')
                text += f' · EltonTraits 확실성 {certainty}'
            elif support.get('value_text') in VALUES and name in LABELS:
                text = f"{LABELS[name]}: {VALUES[support['value_text']]} ({support['value_text']})"
            else:
                raise ValueError('Unsupported graph question trait value')
            paths.append({'text': text, 'source_name': source_name, 'source_url': support['source_url']})
        if row.get('lineage') is not None:
            if taxonomy_source is None:
                raise ValueError('Lineage path without taxonomy provenance')
            paths.insert(0, {'text': '분류 경로: ' + _lineage_text(row['lineage'], taxon['taxon_id'], root_id),
                             **taxonomy_source})
        items.append({'taxon': peer, 'paths': paths})
    return items


def _fruit_share(value_json, key='fruit'):
    try:
        value = json.loads(value_json) if isinstance(value_json, str) else None
    except ValueError:
        return None
    amount = value.get(key) if isinstance(value, dict) else None
    if (not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount)
            or not 0 < amount <= 100):
        return None
    return amount


def _limited(rows):
    return rows[:RESULT_LIMIT], len(rows) > RESULT_LIMIT


def _common_taxonomy(repository, resolve, parsed, species_scope):
    first, second = (_resolve_species(resolve, name) for name in parsed.names)
    if (first.concept_set_id, first.taxonomy_release) != (second.concept_set_id, second.taxonomy_release):
        return _payload('insufficient_data', '공통 분류', '두 종의 분류 릴리스가 달라 공통 분류를 비교하지 못했습니다.',
                        limitations=['두 종이 서로 다른 분류 릴리스에 연결되어 있습니다.'])
    concept, release = first.concept_set_id, first.taxonomy_release
    source = _taxonomy_source(repository, concept, release)
    taxa = [_scoped(asdict(lineage.items[-1]), species_scope, concept, release) for lineage in (first, second)]
    if not all(scope_matches(taxon, species_scope, concept, release) for taxon in taxa):
        return _payload('empty', '공통 분류', '선택한 종 범위에 두 종이 모두 포함되지 않아 비교하지 않았습니다.',
                        limitations=['두 종 중 하나 이상이 선택한 종 범위 밖입니다.'])
    if first.items[-1].taxon_id == second.items[-1].taxon_id:
        return _payload('insufficient_data', '공통 분류', '두 이름이 같은 종으로 확인되어 비교하지 않았습니다.',
                        limitations=['같은 종을 두 번 입력했습니다.'], taxa=taxa)
    second_ids = {item.taxon_id for item in second.items}
    shared = [item for item in first.items if item.rank in ('order', 'family', 'genus') and item.taxon_id in second_ids]
    items = [{'taxon': taxon, 'paths': [{'text': _lineage_path(lineage), **source}]}
             for taxon, lineage in zip(taxa, (first, second))]
    title = f'{_label(taxa[0])}와 {_label(taxa[1])}의 공통 분류'
    if not shared:
        return _payload('empty', title, f'{_label(taxa[0])}와 {_label(taxa[1])}는 AviList 목·과·속 수준에서 공통 분류가 확인되지 않았습니다.',
                        items, [source], [LIMITATIONS['taxonomy_not_distance']], taxa=taxa, paths=[])
    deepest = shared[-1]
    shared_paths = [{'text': f"같은 {RANK_LABELS[item.rank]}: {_rank_name(item)}", **source} for item in shared]
    text = (f"{_label(taxa[0])}와 {_label(taxa[1])}는 같은 {RANK_LABELS[deepest.rank]}({_rank_name(deepest)})에 속합니다. "
            '아래는 AviList 분류 경로입니다.')
    return _payload('answer', title, text, items, [source], [LIMITATIONS['taxonomy_not_distance']],
                    taxa=taxa, paths=shared_paths, common_rank=deepest.rank)


def _same_genus(repository, resolve, parsed, species_scope, korea_only):
    lineage = _resolve_species(resolve, parsed.names[0])
    concept, release = lineage.concept_set_id, lineage.taxonomy_release
    target = _scoped(asdict(lineage.items[-1]), species_scope, concept, release)
    title = f"{_label(target)}와 같은 속의 {'국내 기록 ' if korea_only else ''}종"
    if not scope_matches(target, species_scope, concept, release):
        return _payload('empty', title, '기준 종이 선택한 종 범위에 포함되지 않습니다.',
                        limitations=[LIMITATIONS['target_out_of_scope']])
    if korea_only and species_scope not in ('all', 'korea'):
        return _payload('empty', title, '선택한 종 범위에서는 국내 기록 종을 찾을 수 없습니다.',
                        limitations=[LIMITATIONS['scope_conflict']], taxon=target)
    peer_scope = 'korea' if korea_only else species_scope
    group_path = None
    if parsed.group:
        confirmed = next((item for item in lineage.items if item.rank in ('order', 'family', 'genus')
                          and _group_label(item) == parsed.group), None)
        if confirmed is None:
            return _payload('insufficient_data', title,
                            f"질문의 ‘{parsed.group}’ 범위를 {_label(target)}의 분류 계통에서 확인하지 못해 답하지 않았습니다.",
                            limitations=[f"‘{parsed.group}’ 범위는 기준 종의 목·과·속 한국어 이름으로만 확인합니다."],
                            taxon=target)
        group_path = f"범위 확인: ‘{parsed.group}’ = {_rank_name(confirmed)}"
    genus = next((item for item in lineage.items if item.rank == 'genus'), None)
    if genus is None:
        return _payload('insufficient_data', title, '기준 종의 속을 확인하지 못했습니다.', taxon=target)
    source = _taxonomy_source(repository, concept, release)
    rows = repository._run(GENUS_PEERS_QUERY, concept_set_id=concept, taxonomy_release=release, genus_id=genus.taxon_id,
                           target_id=lineage.items[-1].taxon_id, korean_reference_names=_korean_reference_names(),
                           limit=RESULT_LIMIT + 1, **scope_query_parameters(peer_scope, concept, release))
    rows, has_more = _limited(rows)
    items = _peer_items(rows, peer_scope, concept, release, target_id=lineage.items[-1].taxon_id)
    for item in items:
        item['paths'] = [{'text': f"같은 속: {_rank_name(genus)}", **source}]
        if group_path:
            item['paths'].insert(0, {'text': group_path, **source})
        if korea_only:
            item['paths'] += [{'text': '국내 기록·분포 근거', 'source_name': e.get('source_title'),
                               'source_url': e.get('source_url')} for e in item['taxon']['distribution']['evidence']]
    sources = [source] + [_source(p['source_name'], p['source_url']) for item in items for p in item['paths'][1:]]
    limitations = [LIMITATIONS['korea_record']] if korea_only else []
    if not items:
        return _payload('empty', title, f"{_rank_name(genus)}에서 {'국내 기록 근거가 확인된 ' if korea_only else ''}다른 종을 찾지 못했습니다.",
                        sources=[source], limitations=limitations, taxon=target)
    text = (f"{_label(target)}와 같은 {_rank_name(genus)}에 속하면서 국내 기록 근거가 있는 종입니다." if korea_only
            else f"{_label(target)}와 같은 {_rank_name(genus)}에 속하는 종입니다. 분류상 같은 속이며 외형 유사도 순위가 아닙니다.")
    return _payload('answer', title, text, items, sources, limitations, has_more, taxon=target)


def _order(repository, rank_name, concept, release):
    if rank_name.endswith('formes'):
        scientific = rank_name
    else:
        matches = [key.split(':', 1)[1] for key, label in reference_korean_names().items()
                   if key.startswith('order:') and label.get('name') == rank_name]
        if len(matches) != 1:
            return None
        scientific = matches[0].capitalize()
    rows = repository._run(TAXON_QUERY, concept_set_id=concept, taxonomy_release=release, rank='order',
                           scientific_name=scientific)
    return rows[0] if len(rows) == 1 else None


def _order_fruit(repository, store, parsed, species_scope):
    criterion = parsed.criterion
    title = f"{parsed.rank_name} 중 {'열매 섭식 범주의' if criterion == 'frugivore' else '열매를 먹는'} 종"
    if criterion == 'tree_fruit_share':
        title += ' (나무·풀 구분 없음)'
    pipeline = 'reference-avonet' if criterion == 'frugivore' else 'reference-taxonomy-traits'
    sources, context = _trait_sources(store)
    if context is None or pipeline not in sources:
        return _payload('insufficient_data', title, '열매 먹이 자료를 확인할 수 있는 활성 형질 자료가 없습니다.',
                        limitations=[LIMITATIONS['context_unavailable']])
    concept, release = context
    order = _order(repository, parsed.rank_name, concept, release)
    if order is None:
        return _payload('insufficient_data', title, f'{parsed.rank_name}을(를) 현재 분류에서 하나의 목으로 확인하지 못했습니다.',
                        limitations=['목 이름은 AviList 학명 또는 검토된 한국어 목 이름만 사용합니다.'])
    source = sources[pipeline]
    taxonomy_source = _taxonomy_source(repository, concept, release)
    trait_name = 'trophic_niche' if criterion == 'frugivore' else 'diet_distribution'
    rows = repository._run(ORDER_TRAIT_QUERY, concept_set_id=concept, taxonomy_release=release, order_id=order['taxon_id'],
                           dataset_id=source['dataset_id'], release=source['release'], trait_name=trait_name,
                           value_text='Frugivore' if criterion == 'frugivore' else None,
                           value_json_pattern=None if criterion == 'frugivore' else FRUIT_POSITIVE,
                           korean_reference_names=_korean_reference_names(), limit=RESULT_LIMIT + 1,
                           **scope_query_parameters(species_scope, concept, release))
    rows, has_more = _limited(rows)
    items = _peer_items(rows, species_scope, concept, release, {trait_name: source['source_name']},
                        taxonomy_source=taxonomy_source, root_id=order['taxon_id'])
    limitations = ([LIMITATIONS['frugivore_only']] if criterion == 'frugivore'
                   else [LIMITATIONS['fruit_share'], LIMITATIONS['elton_interpolated']]) + [LIMITATIONS['graph_claims_only']]
    if criterion == 'tree_fruit_share':
        limitations.insert(0, LIMITATIONS['tree_fruit'])
    sources_out = [taxonomy_source] + [_source(p['source_name'], p['source_url']) for item in items for p in item['paths']]
    if not items:
        return _payload('empty', title, f'{parsed.rank_name}에서 조건에 맞는 종을 그래프에서 찾지 못했습니다.',
                        limitations=limitations)
    return _payload('answer', title, f"{parsed.rank_name}에 속하면서 {source['source_name']} 자료의 조건에 맞는 종입니다.",
                    items, sources_out, limitations, has_more, criterion=trait_name)


_SCIENTIFIC_TAXON = re.compile(r'[A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){0,2}')
_SUFFIX_RANKS = {suffix: rank for rank, suffix in RANK_LABELS.items() if rank != 'species'}
_SCIENTIFIC_RANKS = {0: ('order', 'family', 'genus'), 1: ('species',), 2: ('subspecies',)}


def checked_conditions(conditions):
    """Allowlisted, non-conflicting conditions; anything else is a caller bug (ValueError)."""
    if not isinstance(conditions, tuple) or not 1 <= len(conditions) <= 8:
        raise ValueError('taxon_traits needs 1-8 conditions')
    seen = {}
    for condition in conditions:
        spec = TRAIT_CONDITIONS.get(getattr(condition, 'trait_name', None))
        if not isinstance(condition, TraitCondition) or spec is None or condition.op not in CONDITION_OPS[spec[1]]:
            raise ValueError('Unsupported trait condition')
        if spec[1] == 'number':
            ok = (condition.value is None and condition.unit == spec[2] and isinstance(condition.threshold, (int, float))
                  and not isinstance(condition.threshold, bool) and math.isfinite(condition.threshold)
                  and condition.threshold >= 0)
        elif spec[1] == 'share':
            ok = condition.value in spec[2] and condition.threshold == 0 and condition.unit is None
        else:
            ok = condition.value in spec[2] and condition.threshold is None and condition.unit is None
        if not ok or condition.qualifier not in (None, 'tree_fruit') or (
                condition.qualifier and (condition.trait_name, condition.value) != ('diet_distribution', 'fruit')):
            raise ValueError('Invalid trait condition value')
        if spec[1] == 'text':
            if seen.setdefault(condition.trait_name, condition.value) != condition.value:
                raise ValueError('Conflicting trait conditions')
    for name in _AVONET_NUMBERS:
        lower = [c.threshold for c in conditions if c.trait_name == name and c.op in ('num_gte', 'num_gt')]
        upper = [c.threshold for c in conditions if c.trait_name == name and c.op in ('num_lte', 'num_lt')]
        if len(lower) > 1 or len(upper) > 1 or (lower and upper and lower[0] > upper[0]):
            raise ValueError('Conflicting numeric trait conditions')
    if len(set(conditions)) != len(conditions):
        raise ValueError('Duplicate trait condition')
    return conditions


_OP_WORDS = {'num_gte': '이상', 'num_lte': '이하', 'num_gt': '초과', 'num_lt': '미만'}


def condition_label(condition):
    """Korean display of one condition, from the existing profile vocabulary."""
    if condition.op == 'eq':
        return f"{LABELS[condition.trait_name]} {VALUES[condition.value]}({condition.value})"
    if condition.op == 'share_gt':
        word = '나무열매' if condition.qualifier == 'tree_fruit' else share_word(condition.value)
        return f"{LABELS[condition.trait_name]}에 {word} 포함"
    return f"{LABELS[condition.trait_name]} {condition.threshold:g}{condition.unit} {_OP_WORDS[condition.op]}"


def _condition_parameter(condition, source):
    key = (f'(?:{"|".join(DIET_SHARE_GROUPS[condition.value])})' if condition.value in DIET_SHARE_GROUPS
           else condition.value)   # a group: any of its keys above 0
    pattern = FRUIT_POSITIVE.replace('"fruit"', f'"{key}"') if condition.op == 'share_gt' else None
    return {'trait_name': condition.trait_name, 'dataset_id': source['dataset_id'], 'release': source['release'],
            'op': condition.op, 'value': condition.value, 'threshold': condition.threshold, 'unit': condition.unit,
            'pattern': pattern}


def _support_text(condition, support):
    """Re-check one returned claim against its condition; never trust the query alone."""
    if (not isinstance(support, dict) or support.get('trait_name') != condition.trait_name
            or not _web_url(support.get('source_url'))):
        raise ValueError('Invalid graph question trait provenance')
    name = condition.trait_name
    if condition.op == 'eq':
        if support.get('value_text') != condition.value or condition.value not in VALUES:
            raise ValueError('Trait value does not match the condition')
        text = f"{LABELS[name]}: {VALUES[condition.value]} ({condition.value})"
    elif condition.op == 'share_gt':
        parts = {key: _fruit_share(support.get('value_json'), key)
                 for key in DIET_SHARE_GROUPS.get(condition.value, (condition.value,))}
        parts = {key: amount for key, amount in parts.items() if amount is not None}
        amount = sum(parts.values())
        if not parts or not amount > condition.threshold:
            raise ValueError('Diet composition does not match the condition')
        if support.get('certainty') not in ('A', 'B', 'C'):
            raise ValueError('Interpolated or unqualified diet composition')
        detail = (f" ({' · '.join(f'{SOURCE_CATEGORY[key]} {value:g}%' for key, value in parts.items())})"
                  if condition.value in DIET_SHARE_GROUPS else '')
        text = (f"{LABELS[name]}: {share_word(condition.value)} {amount:g}%{detail} (자료의 먹이 구성비)"
                f" · EltonTraits 확실성 {support['certainty']}")
    else:
        amount = support.get('value_num')
        if (not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount)
                or support.get('unit') != condition.unit or not {
                    'num_gte': amount >= condition.threshold, 'num_lte': amount <= condition.threshold,
                    'num_gt': amount > condition.threshold, 'num_lt': amount < condition.threshold}[condition.op]):
            raise ValueError('Measurement does not match the condition')
        text = f"{LABELS[name]}: {amount:g} {condition.unit}"
    return text


def _taxon_candidates(repository, resolve, surface, concept, release):
    """(taxon or None, reason): the one active taxon the surface names; the rank always comes from the graph node.

    A Korean label whose explicit 목/과/속 ending contradicts its own rank (e.g. genus Cinclus labelled
    물까마귀과) is a source-quality conflict: held, never resolved to a narrower or wider taxon.
    """
    name = surface.strip()
    if _SCIENTIFIC_TAXON.fullmatch(name):
        rows = repository._run(TAXON_BY_NAME_QUERY, concept_set_id=concept, taxonomy_release=release,
                               scientific_name=name, ranks=list(TAXON_RANKS))
        allowed = _SCIENTIFIC_RANKS[name.count(' ')]
        if any(row.get('rank') not in allowed or row.get('scientific_name') != name or not row.get('taxon_id')
               for row in rows):
            return None, 'not_found'   # a rank the name shape cannot have: never guess
        if len(rows) != 1:
            return None, 'ambiguous' if rows else 'not_found'
        return {'taxon_id': rows[0]['taxon_id'], 'rank': rows[0]['rank'], 'scientific_name': name,
                'korean_name': None, 'korean_name_source_url': None}, None
    compact = re.sub(r'\s+', '', name)
    labels = []
    for key, label in reference_korean_names().items():
        rank, science = key.split(':', 1)
        if rank in ('order', 'family', 'genus') and re.sub(r'\s+', '', label.get('name') or '') == compact:
            labels.append((rank, science.capitalize(), None, label['name'], label.get('source_url')))
    for taxon_id, label in sourced_korean_names().items():
        if re.sub(r'\s+', '', label.get('name') or '') == compact:
            labels.append(('species', label['scientific_name'], taxon_id, label['name'], label.get('source_url')))
    if not labels and resolve is not None:
        try:
            lineage = resolve(name)
        except SpeciesNotFoundError:
            lineage = None
        if lineage is not None and lineage.items and lineage.items[-1].rank == 'species':
            if (lineage.concept_set_id, lineage.taxonomy_release) != (concept, release):
                return None, 'not_found'
            item = lineage.items[-1]
            labels.append(('species', item.scientific_name, item.taxon_id, item.korean_name,
                           item.korean_name_source_url))
    if len(labels) != 1:
        return None, 'ambiguous' if labels else 'not_found'
    rank, science, taxon_id, korean, url = labels[0]
    stated = _SUFFIX_RANKS.get((korean or '')[-1:])
    if stated is not None and stated != rank:
        return None, 'label_rank_conflict'
    rows = repository._run(TAXON_QUERY, concept_set_id=concept, taxonomy_release=release, rank=rank,
                           scientific_name=science)
    if len(rows) != 1 or (taxon_id is not None and rows[0].get('taxon_id') != taxon_id):
        return None, 'not_found'
    return {'taxon_id': rows[0]['taxon_id'], 'rank': rank, 'scientific_name': science, 'korean_name': korean,
            'korean_name_source_url': url}, None


def _taxon_display(taxon):
    korean = taxon.get('korean_name')
    return f"{korean} ({taxon['scientific_name']})" if korean else taxon['scientific_name']


def _taxon_traits(repository, store, resolve, parsed, species_scope):
    conditions = checked_conditions(parsed.conditions)
    summary = ', '.join(condition_label(c) for c in conditions)
    scope_label = parsed.rank_name.strip() if parsed.rank_name else '전체 조류'
    title = f"{scope_label} 중 조건에 맞는 종"
    condition_out = []
    sources, context = _trait_sources(store)
    pipelines = {TRAIT_CONDITIONS[c.trait_name][0] for c in conditions}
    if context is None or not pipelines <= set(sources):
        return _payload('insufficient_data', title, '조건 형질을 확인할 수 있는 활성 형질 자료가 없습니다.',
                        limitations=[LIMITATIONS['context_unavailable']])
    for c in conditions:
        condition_out.append({'trait_name': c.trait_name, 'label': condition_label(c), 'op': c.op, 'value': c.value,
                              'threshold': c.threshold, 'unit': c.unit,
                              'source_name': sources[TRAIT_CONDITIONS[c.trait_name][0]]['source_name']})
    concept, release = context
    taxonomy_source = _taxonomy_source(repository, concept, release)
    taxon = None
    if parsed.rank_name is not None:
        taxon, reason = _taxon_candidates(repository, resolve, parsed.rank_name, concept, release)
        if taxon is None:
            text = {'ambiguous': f"‘{scope_label}’이(가) 현재 분류에서 둘 이상의 분류군으로 확인되어 범위를 정하지 않았습니다.",
                    'label_rank_conflict': (f"‘{scope_label}’의 한국어 분류명이 가리키는 분류 단계와 자료의 실제 분류 단계가 "
                                            '서로 달라 범위를 정하지 않았습니다. 학명으로 다시 질문해 주세요.')}.get(
                reason, f"‘{scope_label}’을(를) 현재 활성 분류에서 하나의 분류군으로 확인하지 못했습니다.")
            return _payload('insufficient_data', title, text,
                            limitations=['분류군 이름은 AviList 학명, 검토된 한국어 분류명 또는 출처가 확인된 종 국명만 사용합니다. '
                                         '다른 분류 단계로 넓히거나 추측하지 않습니다.'],
                            conditions=condition_out, taxon_resolution=reason)
        title = f"{_taxon_display(taxon)} 중 조건에 맞는 종"
    self_scope = taxon is not None and taxon['rank'] in ('species', 'subspecies')
    params = dict(concept_set_id=concept, taxonomy_release=release,
                  conditions=[_condition_parameter(c, sources[TRAIT_CONDITIONS[c.trait_name][0]]) for c in conditions],
                  korean_reference_names=_korean_reference_names(), limit=RESULT_LIMIT + 1,
                  **scope_query_parameters(species_scope, concept, release))
    if taxon is None:
        rows = repository._run(CATALOG_TRAITS_QUERY, **params)
    else:
        rows = repository._run(TAXON_TRAITS_QUERY, root_id=taxon['taxon_id'], root_rank=taxon['rank'],
                               target_rank='subspecies' if taxon['rank'] == 'subspecies' else 'species', **params)
    stats = rows[0].get('stats') if rows else None
    if (not isinstance(stats, dict) or any(not isinstance(stats.get(k), int) or isinstance(stats.get(k), bool)
                                           or stats[k] < 0 for k in ('scoped', 'evaluable', 'matched'))
            or not stats['matched'] <= stats['evaluable'] <= stats['scoped']):
        raise ValueError('Invalid taxon trait statistics')
    peers = [row for row in rows if (row.get('taxon') or {}).get('taxon_id')]
    if len(peers) != min(stats['matched'], RESULT_LIMIT + 1):
        raise ValueError('Taxon trait rows disagree with statistics')
    peers, has_more = _limited(peers)
    target_rank = taxon['rank'] if self_scope else 'species'
    items = []
    for row in peers:
        found = row['taxon']
        support = row.get('support')
        if (found.get('rank') != target_rank or not isinstance(support, list) or len(support) != len(conditions)
                or (self_scope and found['taxon_id'] != taxon['taxon_id'])):
            raise ValueError('Invalid graph question peer')
        peer_taxon = _scoped(found, species_scope, concept, release)
        if not scope_matches(peer_taxon, species_scope, concept, release):
            continue
        paths = []
        for c, s in zip(conditions, support):   # a range checks one claim twice; it is shown once
            path = {'text': _support_text(c, s), 'source_name': sources[TRAIT_CONDITIONS[c.trait_name][0]]['source_name'],
                    'source_url': s['source_url']}
            if path not in paths:
                paths.append(path)
        if row.get('lineage') is not None:
            paths.insert(0, {'text': '분류 경로: ' + _lineage_text(row['lineage'], found['taxon_id'], taxon['taxon_id']),
                             **taxonomy_source})
        items.append({'taxon': peer_taxon, 'paths': paths})
    scope_paths = []
    if taxon is not None:
        scope_paths.append({'text': f"범위 확인: {_taxon_display(taxon)} · {TAXON_RANK_LABELS[taxon['rank']]}"
                                    + (' (하위 종 전체)' if not self_scope else ' (해당 분류군 자체)'), **taxonomy_source})
    scope_paths += [{'text': f"조건: {item['label']}", 'source_name': item['source_name'],
                     'source_url': None} for item in condition_out]
    limitations = ['모든 조건을 동시에 만족하는 종만 포함합니다. 조건 형질 자료가 없는 종은 결과에서 빠지며, 조건에 맞지 않는다는 뜻은 아닙니다.']
    for c in conditions:
        if c.qualifier == 'tree_fruit':
            limitations.append(LIMITATIONS['tree_fruit'])
        if c.trait_name == 'trophic_niche' and c.value == 'Frugivore':
            limitations.append(LIMITATIONS['frugivore_only'])
        elif TRAIT_CONDITIONS[c.trait_name][1] == 'text' and c.trait_name != 'diet_category':
            limitations.append('AVONET 범주값은 종마다 하나로 정리된 대표 범주입니다. 일부만 해당하는 종은 빠질 수 있습니다.')
        elif c.trait_name == 'diet_category':
            limitations += ['EltonTraits 먹이 유형은 종마다 하나로 정리된 대표 범주입니다.', LIMITATIONS['elton_interpolated']]
        elif c.op == 'share_gt':
            limitations += [LIMITATIONS['fruit_share'] if c.value == 'fruit' else
                            f"EltonTraits 먹이 구성에서 {share_word(c.value)} 비율이 0보다 큰 종입니다. 주식이라는 뜻은 아니며 "
                            '구성비는 자료 저자가 문헌으로 정리한 10% 단위 범주값입니다.', LIMITATIONS['elton_interpolated']]
            if c.value in SHARE_SCOPE:
                limitations.append(SHARE_SCOPE[c.value])
        else:
            limitations.append('AVONET 수치는 종 단위 측정 요약값이며 근연종에서 추정한 값은 제외했습니다.')
    if taxon is not None and taxon['rank'] == 'subspecies':
        limitations.append('아종 질문은 부모 종의 형질 자료로 대체하지 않습니다.')
    limitations.append(LIMITATIONS['graph_claims_only'])
    sources_out = [taxonomy_source] + [_source(p['source_name'], p['source_url']) for item in items for p in item['paths']]
    extra = {'taxon': taxon, 'conditions': condition_out, 'coverage': dict(stats), 'paths': scope_paths}
    where = _taxon_display(taxon) if taxon is not None else '전체 조류'
    traits = ', '.join(dict.fromkeys(LABELS[c.trait_name] for c in conditions))
    if stats['scoped'] == 0:
        text = ('기준 분류군이 선택한 종 범위에 포함되지 않습니다.' if self_scope
                else f'선택한 종 범위에서 {where}에 속하는 종을 찾지 못했습니다.')
        return _payload('empty', title, text, sources=[taxonomy_source],
                        limitations=[LIMITATIONS['target_out_of_scope']] if self_scope else limitations, **extra)
    if stats['evaluable'] == 0:
        if taxon is not None and taxon['rank'] == 'subspecies':
            text = (f"{where}은(는) 아종입니다. 아종 단위로 직접 연결된 {traits} 자료가 그래프에 없어 답할 수 없습니다. "
                    '부모 종의 자료로 대체하지 않았습니다.')
        elif self_scope:
            text = f"{where}의 {traits} 자료가 그래프에 없어 조건을 확인하지 못했습니다."
        else:
            text = f"{where} 범위의 {stats['scoped']}종 중 {traits} 자료가 모두 있는 종이 없어 조건을 확인하지 못했습니다."
        return _payload('insufficient_data', title, text, sources=[taxonomy_source], limitations=limitations, **extra)
    if not items:
        text = (f"{where}은(는) 조건({summary})에 맞지 않습니다." if self_scope else
                f"{where} 범위에서 조건 자료가 모두 있는 {stats['evaluable']}종 중 조건({summary})에 맞는 종을 찾지 못했습니다.")
        return _payload('empty', title, text, sources=[taxonomy_source], limitations=limitations, **extra)
    text = (f"{where}은(는) 조건({summary})에 맞습니다." if self_scope else
            f"{where} 범위에서 조건 자료가 모두 있는 {stats['evaluable']}종 중 {stats['matched']}종이 조건({summary})에 모두 맞습니다.")
    return _payload('answer', title, text, items, sources_out, limitations, has_more, **extra)


def _habitat_diet(repository, store, resolve, parsed, species_scope, same_niche):
    lineage = _resolve_species(resolve, parsed.names[0])
    concept, release = lineage.concept_set_id, lineage.taxonomy_release
    target = _scoped(asdict(lineage.items[-1]), species_scope, concept, release)
    no_habitat = parsed.kind == 'shared_diet'   # never the target's habitat added implicitly
    if no_habitat:
        title = f'{_label(target)}와 먹이 생태 범주가 같은 종'
    elif same_niche:
        title = f"{VALUES[parsed.habitat]}에 사는 새 중 {_label(target)}와 먹이 생태 범주가 같은 종"
    else:
        title = f'{_label(target)}와 서식 환경 범주가 같고 먹이 생태 범주가 다른 종'
    if not scope_matches(target, species_scope, concept, release):
        return _payload('empty', title, '기준 종이 선택한 종 범위에 포함되지 않습니다.',
                        limitations=[LIMITATIONS['target_out_of_scope']])
    sources, context = _trait_sources(store, concept, release)
    avonet = sources.get('reference-avonet')
    if context is None or avonet is None:
        return _payload('insufficient_data', title, '서식 환경과 먹이 생태 범주 자료를 확인하지 못했습니다.',
                        limitations=[LIMITATIONS['context_unavailable']], taxon=target)
    traits = [t for t in read_traits(repository, store, lineage)
              if t.get('dataset_id') == avonet['dataset_id'] and t.get('release') == avonet['release']
              and not t.get('inferred') and t.get('source_scope_kind') != 'subspecies_group'
              and isinstance(t.get('value'), str) and _web_url(t.get('source_url'))]
    niche = next((t for t in traits if t['name'] == 'trophic_niche'), None)
    habitat = None if no_habitat else parsed.habitat or next((t['value'] for t in traits if t['name'] == 'habitat'), None)
    if no_habitat and (niche is None or niche['value'] not in VALUES):
        return _payload('insufficient_data', title, f'{_label(target)}의 먹이 생태 범주 자료가 없습니다.',
                        limitations=[LIMITATIONS['target_trait_missing']], taxon=target)
    if not no_habitat and (niche is None or habitat is None or niche['value'] not in VALUES or habitat not in VALUES):
        return _payload('insufficient_data', title, f'{_label(target)}의 서식 환경 또는 먹이 생태 범주 자료가 없습니다.',
                        limitations=[LIMITATIONS['target_trait_missing']], taxon=target)
    target_paths = [{'text': f"{LABELS[t['name']]}: {VALUES[t['value']]} ({t['value']})",
                     'source_name': avonet['source_name'], 'source_url': t['source_url']}
                    for t in traits if t['name'] in (('trophic_niche',) if no_habitat else ('trophic_niche', 'habitat'))]
    common = dict(concept_set_id=concept, taxonomy_release=release, target_id=lineage.items[-1].taxon_id,
                  dataset_id=avonet['dataset_id'], release=avonet['release'], niche=niche['value'],
                  korean_reference_names=_korean_reference_names(), limit=RESULT_LIMIT + 1,
                  **scope_query_parameters(species_scope, concept, release))
    rows = (repository._run(SHARED_DIET_QUERY, **common) if no_habitat else
            repository._run(HABITAT_DIET_QUERY, habitat=habitat, same_niche=same_niche, **common))
    rows, has_more = _limited(rows)
    names = {'habitat': avonet['source_name'], 'trophic_niche': avonet['source_name']}
    items = _peer_items(rows, species_scope, concept, release, names, lineage.items[-1].taxon_id)
    limitations = [LIMITATIONS['category_not_food' if same_niche else 'different_diet'], LIMITATIONS['graph_claims_only']]
    sources_out = [_source(p['source_name'], p['source_url']) for p in target_paths] + [
        _source(p['source_name'], p['source_url']) for item in items for p in item['paths']]
    # Record the fixed query's actual scope only after it returned successfully.
    execution_summary = {
        'kind': parsed.kind, 'reference_name': lineage.items[-1].scientific_name,
        'share_basis': 'trophic_niche', 'match': 'same' if same_niche else 'different',
        'exclude_reference': True, 'habitat': habitat, 'niche_value': common['niche'],
        **{key: common[key] for key in ('target_id', 'species_scope', 'dataset_id', 'release',
                                       'concept_set_id', 'taxonomy_release')},
    }
    extra = {'taxon': target, 'paths': target_paths, 'execution_summary': execution_summary}
    if not items:
        return _payload('empty', title, '조건에 맞는 종을 그래프에서 찾지 못했습니다.', sources=sources_out,
                        limitations=limitations, **extra)
    if no_habitat:
        text = f"{_label(target)}와 같은 먹이 생태 범주({VALUES[niche['value']]})로 분류된 종입니다."
    elif same_niche:
        text = (f"{VALUES[habitat]} 서식 범주이면서 {_label(target)}와 같은 먹이 생태 범주"
                f"({VALUES[niche['value']]})로 분류된 종입니다.")
    else:
        text = (f"{_label(target)}와 같은 서식 환경 범주({VALUES[habitat]})이면서 먹이 생태 범주가 "
                f"‘{VALUES[niche['value']]}’ 범주와 다른 종입니다.")
    return _payload('answer', title, text, items, sources_out, limitations, has_more, **extra)


def graph_question_answer(repository, resolve, parsed, species_scope="all", store=None):
    """Answer one parsed graph question; raises SpeciesNotFoundError for unknown species
    and ValueError for invalid graph provenance (callers map both like other relation reads)."""
    if not isinstance(parsed, GraphQuestion) or parsed.kind not in GRAPH_QUESTION_KINDS:
        raise ValueError('Unsupported graph question')
    if species_scope not in ('all', 'korea', 'outside', 'unknown'):
        raise ValueError(f'Unsupported species_scope: {species_scope!r}')
    if parsed.kind == 'common_taxonomy':
        return _common_taxonomy(repository, resolve, parsed, species_scope)
    if parsed.kind in ('same_genus', 'korea_same_genus'):
        return _same_genus(repository, resolve, parsed, species_scope, korea_only=parsed.kind == 'korea_same_genus')
    if parsed.kind == 'specific_fruit':
        return _payload('insufficient_data', '특정 열매 공유', '특정 식물 열매를 함께 먹는다는 근거 자료가 없어 답할 수 없습니다. '
                        '먹이 생태 범주(예: 열매 섭식)가 같은 종을 원하시면 "같은 먹이 범주를 공유하는 새"로 질문해 주세요.',
                        limitations=[LIMITATIONS['no_plant_level_diet']])
    if parsed.kind == 'order_fruit':
        return _order_fruit(repository, store, parsed, species_scope)
    if parsed.kind == 'taxon_traits':
        return _taxon_traits(repository, store, resolve, parsed, species_scope)
    return _habitat_diet(repository, store, resolve, parsed, species_scope,
                         same_niche=parsed.kind in ('habitat_shared_diet', 'shared_diet'))
