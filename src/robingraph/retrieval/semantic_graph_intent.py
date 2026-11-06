"""Structured (LLM) interpretation of graph questions, verified fail-closed (contract rg-semantic-v1).

Kinds interpreted here: ``taxon_traits`` (the existing trait fields on a taxon of any rank) and ``shared_diet``
(same AVONET trophic_niche as one species). A shared_diet with one explicit habitat condition becomes the existing
``habitat_shared_diet``; no habitat is ever added. The other existing kinds (common_taxonomy, same_genus,
korea_same_genus, habitat_different_diet, specific_fruit) stay lexical-only. Incomplete order_fruit with residual
conditions may become taxon_traits; a complete order_fruit stays lexical. The provider proposes a JSON
object; nothing it says is trusted on its own:

A. the existing lexical extractor runs first, and its negation/unsupported/residency/scope cues and the
   season, period and superlative cues below veto the provider call. Explicit entity/equality exclusions may
   reach the provider, but execution requires proof that the plan already enforces the same restriction;
B. every surface must be original text and every value one of the existing canonical values; the provider
   maps a phrase to its value (synonyms included), but a number, unit or comparison in the text must
   agree exactly with the condition, and every number in the question must belong to a condition;
C. any unresolved text or unknown relation the provider reports is a clarify;
D. every known vocabulary word in the question (the extractor's trait, measure and habitat surfaces) must sit
   in a span whose value it can mean, so a recognised condition can never be dropped or re-labelled.
   Unknown wording also requires the transport's independent semantic audit; that audit remains probabilistic. There is no fixed sentence grammar.

A failed check yields a GraphIntent the gate turns into a clarify. No Cypher is built here.
"""
from copy import deepcopy
import re
import unicodedata

from .. import tracing

from .graph_condition_extractor import (
    _ASKS, _BARE, _COMMON, _COPULAR_DENIAL, _DOCUMENT_REQUEST, _EAT, _GENUS, _HABITAT_SUBJECT, _KOREA, _MEASURES, _NEGATION, _NICHE_DIFFERENT,
    _NICHE_SAME,
    _NUM, _OPS, _RESIDENCY, _SAME_HABITAT, _SCIENTIFIC, _SHARE_WORDS, _TRAIT_LABELS, _UNIT, _UNITS, _UNSUPPORTED, GROUP_WORDS,
    _FILLER, _PUNCT, _op, _pattern, _taxon_names, _tokens, _trait_surfaces, _valid_name, extract_graph_intent)
from .graph_intent_schema import GraphIntent, Span, execution_gate, span_of, validate_intent
from .graph_questions import CONDITION_OPS, TAXON_RANKS, TRAIT_CONDITIONS, TraitCondition, checked_conditions
from .species_profile import LABELS, VALUES
from .species_questions import _DIET_WORD, bounded_korean_name

SOURCE = 'semantic'
KINDS = ('taxon_traits', 'shared_diet', 'none')
SEMANTIC_KIND_FAMILIES = {'taxon_traits': ('taxon_traits', 'order_fruit'),
                          'shared_diet': ('shared_diet', 'habitat_shared_diet')}
# Season, activity time and superlative asks have no supported query field.
VETO_CUES = (r'겨울|여름|(?<![가-힣])봄|가을|번식기|월동|\d+\s*월(?![가-힣])|가장|제일|최고|'
             r'야행성|주행성|박명성|활동\s*(?:시간|시기)|(?<![가-힣])(?:밤|낮|새벽)(?:에|만|동안)')
# Trait sources a question may name as the data it means (provenance scope, not a document request). A named
# source restricts every condition to its own pipeline; any other source or literature request stays a veto/unresolved.
TRAIT_SOURCES = ((r'avonet', 'reference-avonet', 'AVONET'),   # matched case-insensitively
                 (r'elton\s*traits?|엘튼\s*트레이츠', 'reference-taxonomy-traits', 'EltonTraits'))
_SOURCE_SCOPE = (r'(?:' + '|'.join(p for p, _, _ in TRAIT_SOURCES) + r')\s*(?:의\s*)?(?:자료|데이터|기록|출처)?\s*'
                 r'(?:기준(?:으로)?|에서|에|로|상|으로)?')
_VETOES = (_NEGATION, *(pattern for _, pattern in _UNSUPPORTED), _RESIDENCY, _KOREA, _DOCUMENT_REQUEST, _COMMON,
           _GENUS, VETO_CUES)
_SAME_HABITAT_CUES = (_SAME_HABITAT,
    r'(?:서식지|서식\s*환경|사는\s*곳)(?:가|는|이|은|도)?\s*(?:같|동일|겹)')
_OP_WORD = _OPS
_RANGE = r'~|에서|부터|사이|까지'
# A completed comparison may be nominalised, quoted, or followed by a case particle.
_PREDICATE_TAIL = r'(?:이라는|이라고|이고|이며|이다|입니다|이면서|인|라는|라고|으로|로|의|은|는|이|가|을|를|에서|에|고|지)'
_SHARE_ZERO = r'(?<![\d.])0(?:\.0+)?\s*%?\s*(?:(?:퍼센트|프로)\s*)?(?:초과|넘(?:는|게|고)|보다\s*(?:크|많|높|큰|많은|높은)\S*)'


def _known_words():
    """(pattern, {(trait, value), ...}) for the extractor's vocabulary: value surfaces, measure names, habitats."""
    meanings = {}
    for name, (_, kind, spec) in TRAIT_CONDITIONS.items():
        if kind == 'number':
            continue
        surfaces = dict(_trait_surfaces(name))
        if name == 'diet_distribution':
            surfaces.update(_SHARE_WORDS)
        for word, value in surfaces.items():
            meanings.setdefault(word, set()).add((name, value))
    for word, name in _MEASURES.items():
        if name is not None:
            meanings.setdefault(word, set()).add((name, None))
    # Longest first, so 성긴 숲 is one word and not also 숲.
    return tuple((re.compile(r'(?<![가-힣])' + _pattern(word)), found)
                 for word, found in sorted(meanings.items(), key=lambda item: -len(item[0])))


_KNOWN = _known_words()
_HOLD = GraphIntent(None, ambiguity=('other',), source=SOURCE)
_KEYS = {'kind', 'taxon', 'species', 'conditions', 'relation_text', 'unresolved', 'unknown_relation'}
_CONDITION_KEYS = {'trait_name', 'op', 'value', 'threshold', 'unit', 'surface'}


class SemanticIntentError(ValueError):
    """The provider failed or returned something that is not the contract's JSON object."""

    def __init__(self, message, *, reason=None, original_spans=()):
        super().__init__(message)
        self.reason = reason
        self.original_spans = tuple(original_spans)


class _Reject(Exception):
    def __init__(self, message, spans=()):
        super().__init__(message)
        self.spans = tuple(spans)


_NULLABLE = {'type': 'STRING', 'nullable': True}
SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'kind': {'type': 'STRING', 'enum': list(KINDS)},
        'taxon': {**_NULLABLE, 'description': 'taxon_traits 전용: 조건을 적용할 분류군 원문(목·과·속·종·아종 모두). 없으면 null.'},
        'species': {**_NULLABLE, 'description': 'shared_diet 전용: 먹이 생태 범주를 비교할 기준 종 원문. taxon_traits에서는 항상 null.'},
        'conditions': {'type': 'ARRAY', 'description': '질문의 모든 형질 조건. shared_diet의 서식지도 이 배열의 habitat eq 조건으로 기록합니다.', 'items': {'type': 'OBJECT', 'properties': {
            'trait_name': {'type': 'STRING', 'enum': list(TRAIT_CONDITIONS)},
            'op': {'type': 'STRING', 'enum': sorted({op for ops in CONDITION_OPS.values() for op in ops})},
            'value': {**_NULLABLE, 'description': '범주 또는 먹이 코드. 수치 비교에서는 null이며 숫자는 threshold에 둡니다.'},
            'threshold': {'type': 'NUMBER', 'nullable': True, 'description': '수치 비교의 단위 환산된 기준값. value=null이어도 이 값에 수치 조건이 보존됩니다.'}, 'unit': _NULLABLE,
            'surface': {'type': 'STRING', 'description': '현재 질문의 연속된 원문 부분문자열. 글자·조사·띄어쓰기·어미를 보정하거나 정규화하지 않습니다. 분리된 라벨과 값을 가상 문장으로 합치지 않습니다.'}}, 'required': ['trait_name', 'op', 'surface']}},
        'relation_text': _NULLABLE,
        'unresolved': {'type': 'ARRAY', 'items': {'type': 'STRING'},
            'description': '원문에서 실제로 요구하지만 지원하지 못한 생물학적·관계 검색 제약만. 조회 요청·기록 확인·코드 설명·명시적으로 적용하지 않는 차원은 제약으로 만들지 않습니다. 그 외 부정·지역·추가 조건은 보존합니다.'},
        'unknown_relation': {'type': 'BOOLEAN'},
    },
    'required': ['kind', 'conditions', 'unresolved', 'unknown_relation'],
}
INSTRUCTIONS = """새 그래프 질문 하나를 JSON으로만 해석합니다. 답을 만들지 말고 질문의 구조만 기록합니다.
- kind: taxon_traits(분류군이나 새 전체에서 형질 조건으로 찾기), shared_diet(한 종과 먹이 생태 범주가 같은 새), none(그 외).
- shared_diet에 서식지가 명시되면(예: 숲에 사는 새 중) conditions에 habitat eq 조건 하나만 넣습니다. 기준 종의 서식지를 짐작해 넣지 않습니다.
- 먼저 원문을 실제 검색 제약과 질문을 표현하는 말투로 구분합니다. 조회·기록 확인·설명 요청은 새 생물학적 조건이 아닙니다. 어떤 차원을 검색 조건에 적용하지 않는다는 말은 그 차원의 생물학적 부정 조건과 다릅니다. 실제 조건의 부정·지역·추가 관계는 반드시 보존합니다.
- taxon, species, relation_text, 각 조건의 surface는 현재 질문에 존재하는 연속된 원문 부분문자열이어야 합니다. 동의어·문장 순서·조사·띄어쓰기·어미를 정규화하거나 전형적인 문장으로 다시 쓰지 않습니다. 반환 전 각 문자열이 실제 원문 부분문자열인지 확인합니다. 이름을 만들거나 고치지 않습니다.
- 조건의 field와 값이 여러 문장에 나뉘면 질문 전체의 명시된 field 문맥으로 trait_name을 선택하되 surface는 실제 연속된 근거 구절만 복사합니다. 다른 문장의 라벨·값·어미를 가상으로 이어 붙이지 않습니다. 형질 이름이 불명확하거나 서로 모순되면 그 제약을 unresolved로 보존합니다.
- taxon_traits는 범위가 목·과·속이든 종·아종이든 항상 taxon에 넣고 species는 null입니다. species는 shared_diet의 기준 종에만 씁니다.
- 출처: 질문이 vocabulary.sources의 지원 출처(AVONET, EltonTraits)를 자료 범위로 말하면(예: "AVONET 기준", "EltonTraits 자료에서") 문서 검색 요구가 아닌 출처 한정이므로 unresolved에 넣지 않습니다. 그 출처의 형질 조건만 씁니다. 다른 출처·논문·관찰 기록·문헌 요청은 unresolved입니다. "기록된/자료가 있는 종을 찾아줘"처럼 조건 없이 조회를 뜻하는 말투도 제약이 아닙니다.
- share_gt는 비율이 0보다 크다는 뜻입니다. "0%보다 많은", "0 초과"처럼 0 초과 비교는 같은 조건이며, 0이 아닌 비율 기준(예: 50% 이상)은 지원하지 않으므로 unresolved입니다.
- "종/아종 기록에서", "종의 자료를 확인" 같은 조회 대상 소개는 별도 문헌 검색이 아닙니다. 조건에 해당하는 원문만 conditions로 넣고 나머지 단순 조회 문구를 unresolved로 넣지 않습니다.
- 학명은 하나의 범위입니다. 같은 소명이 반복되더라도 학명이 세 단어이면 아종 전체 세 단어를 taxon에 복사합니다. 두 단어로 줄이거나 세 번째 단어를 미해결 조건으로 분리하지 않습니다.
- shared_diet의 실행 계약은 기준 종 자신을 제외한 다른 종을 찾는 것입니다. 질문에 같은 기준 이름이 여러 번 나와도 하나의 기준 종이며, "다른 새/종/조류"는 먹이 범주가 다르다는 의미가 아닙니다. 기준 종 자신을 빼달라는 말은 이 기본 동작이며 unresolved가 아닙니다.
- 수치 조건을 다시 강조한 문장도 읽습니다. 엄격한 초과/미만 경계의 같은 수치를 제외하는 문장은 이미 그 조건에 포함됩니다. 다른 수치를 제외하거나 포함 조건의 경계를 제외하는 뜻으로 고치지 않습니다. 먹이 비중 0 초과가 별도 문장에 있어도 동일한 한 먹이 조건의 재진술입니다. surface에는 원래 단일 조건 구절을 쓰고, 중복 강조·제외 문장을 합쳐 복사하지 않습니다.
- 조건은 vocabulary의 trait_name·op·value·unit 값만 씁니다. 숫자는 vocabulary 단위(g, mm)로 환산한 threshold입니다.
- 먹는다·먹기도 한다·조금이라도 먹는다는 조건은 diet_distribution share_gt threshold=0입니다. 대표 먹이 생태(trophic_niche)나 먹이 유형(diet_category)으로 바꾸지 않습니다. 영양 단계라는 명시가 있으면 trophic_level입니다.
- taxon/species에는 조사만 빼고 원문 이름을 복사합니다. 한국어 분류군 이름 자체의 목·과·속은 절대로 떼지 않습니다. 학명 뒤에 별도 단어로 붙은 분류 수준(속·종·아종)만 이름에서 뺍니다.
- shared_diet의 relation_text는 "같은 먹이 생태를 가진"처럼 같은 먹이 생태 범주를 말하는 구절입니다. 같은 먹이를 먹는다는 뜻은 shared_diet가 아닙니다.
- 실제 검색 제약 중 해석하지 못한 생물학적 부정·지역·계절·순위·지원하지 않는 관계는 빼지 말고 unresolved에 원문 그대로 넣거나 unknown_relation=true로 표시합니다.
- 범주 코드 자체를 확인하는 질문에서 비중·비율 차원을 적용하지 말라는 명시적 설명은 그 범주 eq 조건을 부정하지 않습니다. 범주를 비중으로 바꾸거나 요청하지 않은 비율 조건을 추가하지 않습니다. 반면 실제 비율 비교·그 범주가 아님·다른 조건 제외는 별도 제약으로 보존합니다.
- unresolved에는 지원하지 않는 실제 검색 제약만 넣습니다. 요청·강조·대화 어미·문장 순서·범위를 지정하는 말투는 미지원 조건이 아닙니다.
- 구체적인 형질 조건이나 공통 분류·속·먹이 관계가 없는 일반적인 두 종 비교·설명도 기존 비교 라우터의 대상입니다. 비교라는 말만으로 shared_diet나 unresolved를 만들지 않습니다.
- 기본 종 정보, 인사, 사용 안내, 비조류 요청은 kind=none, conditions=[], unresolved=[], unknown_relation=false입니다. 그래프 검색 제약이 있으나 해석이 불확실한 경우에만 unresolved에 남깁니다.
- 관계 근거 relation_text는 원문 구절이며 단어 순서가 달라도 같은 먹이 생태 범주라는 의미를 담으면 됩니다. 필요하면 기준 종 이름을 포함하는 긴 구절도 허용됩니다."""


def _vocabulary():
    traits = {}
    for name, (_, kind, spec) in TRAIT_CONDITIONS.items():
        entry = {'label': LABELS[name], 'ops': list(CONDITION_OPS[kind])}
        if kind == 'number':
            entry['unit'] = spec
        else:
            entry['values'] = {value: VALUES[value] for value in spec}
        traits[name] = entry
    sources = {label: sorted(n for n, spec in TRAIT_CONDITIONS.items() if spec[0] == pipeline)
               for _, pipeline, label in TRAIT_SOURCES}
    return {'kinds': list(KINDS), 'ranks': list(TAXON_RANKS), 'traits': traits, 'sources': sources}


CONTRACT = {'version': 'rg-semantic-v1', 'instructions': INSTRUCTIONS, 'schema': SCHEMA, 'vocabulary': _vocabulary()}

# (kind, question, intent): retrieval prototypes with their intent, written for this module (no holdout text).
_EXAMPLES = (
    ('shared_diet', '까치랑 같은 먹이 생태를 가진 새를 알려줘',
     {'kind': 'shared_diet', 'species': '까치', 'relation_text': '같은 먹이 생태를 가진'}),
    ('shared_diet', '직박구리와 먹이 범주가 같은 종은 뭐야',
     {'kind': 'shared_diet', 'species': '직박구리', 'relation_text': '먹이 범주가 같은'}),
    ('shared_diet', '청둥오리하고 식성이 동일한 새들',
     {'kind': 'shared_diet', 'species': '청둥오리', 'relation_text': '식성이 동일한'}),
    ('shared_diet', '왜가리와 같은 먹이 습성의 새 보여줘',
     {'kind': 'shared_diet', 'species': '왜가리', 'relation_text': '같은 먹이 습성의'}),
    ('taxon_traits', '까마귀과 중 영양 단계가 잡식인 새',
     {'kind': 'taxon_traits', 'taxon': '까마귀과', 'conditions': [
         {'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Omnivore', 'surface': '영양 단계가 잡식인'}]}),
    ('taxon_traits', '참새목에서 몸무게가 100g 이상인 새',
     {'kind': 'taxon_traits', 'taxon': '참새목', 'conditions': [
         {'trait_name': 'body_mass', 'op': 'num_gte', 'threshold': 100, 'unit': 'g', 'surface': '몸무게가 100g 이상인'}]}),
    ('taxon_traits', '오리과 새 중 꼬리 길이가 10cm 미만인 종',
     {'kind': 'taxon_traits', 'taxon': '오리과', 'conditions': [
         {'trait_name': 'tail_length', 'op': 'num_lt', 'threshold': 100, 'unit': 'mm', 'surface': '꼬리 길이가 10cm 미만인'}]}),
    ('taxon_traits', 'Corvus 속에서 숲에 사는 새',
     {'kind': 'taxon_traits', 'taxon': 'Corvus', 'conditions': [
         {'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'surface': '숲에 사는'}]}),
    ('taxon_traits', '백로과 중 먹이 생태 범주가 수생동물 포식인 새',
     {'kind': 'taxon_traits', 'taxon': '백로과', 'conditions': [
         {'trait_name': 'trophic_niche', 'op': 'eq', 'value': 'Aquatic predator',
          'surface': '먹이 생태 범주가 수생동물 포식인'}]}),
    ('taxon_traits', '도요목 중 물고기를 먹는 새',
     {'kind': 'taxon_traits', 'taxon': '도요목', 'conditions': [
         {'trait_name': 'diet_distribution', 'op': 'share_gt', 'value': 'fish', 'threshold': 0, 'surface': '물고기를 먹는'}]}),
    ('taxon_traits', '주 생활 방식이 지상 생활이고 서식지 밀도 범주가 개방형인 새',
     {'kind': 'taxon_traits', 'conditions': [
         {'trait_name': 'primary_lifestyle', 'op': 'eq', 'value': 'Terrestrial', 'surface': '주 생활 방식이 지상 생활이고'},
         {'trait_name': 'habitat_density_category', 'op': 'eq', 'value': 'open', 'surface': '서식지 밀도 범주가 개방형인'}]}),
    ('taxon_traits', '매과에서 먹이 유형이 고기·물고기·사체인 새',
     {'kind': 'taxon_traits', 'taxon': '매과', 'conditions': [
         {'trait_name': 'diet_category', 'op': 'eq', 'value': 'VertFishScav', 'surface': '먹이 유형이 고기·물고기·사체인'}]}),
    ('taxon_traits', 'Anas platyrhynchos의 부리 너비가 20mm 초과인지',
     {'kind': 'taxon_traits', 'taxon': 'Anas platyrhynchos', 'conditions': [
         {'trait_name': 'beak_width', 'op': 'num_gt', 'threshold': 20, 'unit': 'mm', 'surface': '부리 너비가 20mm 초과인지'}]}),
)
SEMANTIC_PROTOTYPES = tuple((kind, question) for kind, question, _ in _EXAMPLES)
_EXAMPLE_INTENTS = {question: intent for _, question, intent in _EXAMPLES}


def _lexical_decides(question, lexical):
    """True when the extractor's result stands: executable, or blocked by something the provider must not clear."""
    if execution_gate(question, lexical) == 'answer' or lexical.unsupported_food:
        return True
    # Spans that only look like a veto are blanked before the vetoes are re-checked on the original text: a supported
    # source named as the data scope (AVONET 기준), "no restriction" scope talk (분류 제한 없이) and a canonical
    # value whose wording overlaps an unsupported word (수생동물 포식). Every other negation/unsupported word still vetoes.
    blanked = _blank(question)
    # Only recognised exclusion clauses may reach the provider; _build proves each one redundant.
    chars = list(blanked)
    for span, _ in _exclusions(question):
        chars[span.start:span.end] = ' ' * (span.end - span.start)
    blanked = ''.join(chars)
    if lexical.negation and re.search(_NEGATION, blanked) or lexical.unsupported and any(
            re.search(pattern, blanked) for _, pattern in _UNSUPPORTED):
        return True
    # A vague or unread condition ('other') is the provider's to read; a name or kind conflict is not.
    if set(lexical.ambiguity) & {'name_ambiguous', 'group_unresolved', 'kind_tie'}:
        return True
    other_birds = (lexical.kind == 'habitat_different_diet' and lexical.habitat is None
                   and re.search(r'(?:같|동일|일치|공유|비슷|유사)[가-힣]*\s+다른\s+(?:새|종|조류)', question)
                   and any(slot == 'relation' for slot, _ in lexical.evidence)
                   and all(re.match(r'다른\s+(?:새|종|조류)(?:들)?(?=[은는이가을를도\s.!?]|$)',
                                    question[span.start:])
                           for slot, span in lexical.evidence if slot == 'relation'))
    if lexical.kind == 'order_fruit' and (not lexical.residual or lexical.ambiguity):
        return True
    supported = {kind for contract_kind in KINDS for kind in SEMANTIC_KIND_FAMILIES.get(contract_kind, ())}
    if lexical.kind is not None and lexical.kind not in supported and not other_birds:
        return True   # the other existing kinds stay lexical-only
    return any(re.search(pattern, blanked) for pattern in _VETOES)


# Lifting the taxonomic scope only (분류 제한 없이, 목·과·속 구분 없이): no taxon, not a negated condition.
# Any other "… 없이" (먹이 조건 없이) stays a negation veto.
_SCOPE_META = (r'(?<![가-힣])(?:분류군?|분류\s*수준|(?:목|과|속|종)(?:\s*[·,/]?\s*(?:목|과|속|종))*)\s*(?:의\s*)?'
               r'(?:제한|구분|상관)\s*없이')


# Explicit absence of a dimension restriction is query framing, not biological negation.
_META_DIMENSIONS = {k: v for k, v in {**_MEASURES, **_TRAIT_LABELS,
    '서식지': 'habitat', '서식 환경': 'habitat', '사는 곳': 'habitat'}.items() if v is not None}
_META_DIMENSION_CODES = {re.sub(r'\s+', '', k): v for k, v in _META_DIMENSIONS.items()}
_UNRESTRICTED = re.compile(r'(?<![가-힣])(?P<dimension>'
    + '|'.join(_pattern(k) for k in sorted(_META_DIMENSIONS, key=len, reverse=True))
    + r')(?:은|는|이|가)?\s*제한(?:은|는|을|를)?\s*'
      r'(?:두지\s*않(?:을게|겠습니다|겠다|고)|하지\s*말고|없(?:이|어|다))(?=\s|[.!?,]|$)')
_DISCOURSE = re.compile(r'(?<![가-힣])(?:자료|데이터|목록)(?:을|를)?\s*(?:펼쳐서|살펴보고|읽어서|보여\s*줘)(?=\s|[.!?,]|$)')
# Ratio dimensions may be explicitly omitted from query configuration, never from a biological NOT predicate.
_RATE_DIMENSION = r'(?:(?:먹이(?:별)?\s*)?(?:구성\s*)?(?:비율|비중)|구성비)'
_RATE_TARGET = r'(?:(?:검색|조회)\s*)?(?:조건|제한|수치)'
_RATE_SETTING = (r'(?<![가-힣])(?:(?:이번\s*)?(?:검색|조회)\s*설정에서는?\s*)?'
                 + _RATE_DIMENSION + r'(?:은|는|이|가|을|를)?\s*(?:차원(?:은|는|이|가|을|를)?\s*)?'
                 r'(?:(?:에\s*관한\s*)?' + _RATE_TARGET + r'(?:은|는|이|가|을|를|에|으로|로)?\s*)?')
_RATE_PROHIBIT = r'(?:넣|적용하|사용하)지\s*(?:마세요|마|말아\s*(?:주세요|줘)|않(?:아|아요|습니다|을게|겠다|겠어))'
_RATE_MEANING = (r'(?:(?:뜻하는|의미하는)\s*(?:건|것은|것이)'
                 r'|(?:걸러|넣어|적용해|사용해)\s*달라는\s*뜻(?:은|이)?)\s*' + _COPULAR_DENIAL)
_RATE_META = re.compile(_RATE_SETTING + r'(?:' + _RATE_PROHIBIT + r'|' + _RATE_MEANING + r')(?=\s|[.!?,]|$)')

_RECORD_REQUEST = r'기록(?:되어|돼)\s*있(?:는지|는가)\s*확인해\s*(?:줘|주세요)'


def _field_spans(surface):
    """Prefer complete field labels over contained labels such as habitat inside habitat density."""
    labels = {**{name: name for name in TRAIT_CONDITIONS},
              **{label: name for name, label in LABELS.items() if name in TRAIT_CONDITIONS},
              **_MEASURES, **_TRAIT_LABELS}
    matches = [(match.start(), match.end(), name) for label, name in labels.items()
               for match in re.finditer(_pattern(label) + r'(?=\s|[은는이가을를의와과랑:=：·,]|하고|$)', surface.strip())]
    chosen = []
    for start, end, name in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[0])):
        if any(start < stop and begin < end for begin, stop, _ in chosen):
            continue
        chosen.append((start, end, name))
    return [(start, end, {name for a, b, name in matches if (a, b) == (start, end)})
            for start, end, _ in chosen]


def _record_field_matches(surface, trait):
    """Only an explicit, longest original field label proves a record-query predicate's dimension."""
    fields = _field_spans(surface)
    return len(fields) == 1 and fields[0][0] == 0 and fields[0][2] == {trait}



_RECORD_STATE = r'기록(?:되어|돼)\s*있(?:는지|는가|습니다|다|음)(?=\s|[.!?,]|$)'
_RECORD_CONTEXT = r'기록\s*값|' + _RECORD_STATE


def _original_record_assignment(question, item):
    """Recover a unique typed categorical assignment; neither a value alone nor a request verb proves a field."""
    if re.search(r'(?:확인|조회|검색)하지\s*(?:마|말)', question):
        return None  # A positive recorded state does not override a prohibited read request.
    trait, value, text = item.get('trait_name'), item.get('value'), item.get('surface', '').strip()
    spec = TRAIT_CONDITIONS.get(trait)
    if not spec or spec[1] in ('number', 'share') or item.get('op') != 'eq' or not isinstance(value, str):
        return None
    aliases = {value} | {word for word, code in _trait_surfaces(trait).items() if code == value}
    value_pattern = r'(?:' + '|'.join(_pattern(alias) for alias in sorted(aliases, key=len, reverse=True)) + r')(?![A-Za-z0-9_])'
    if len(list(re.finditer(value_pattern, question))) != 1:
        return None
    assignments = []
    leading = len(question) - len(question.lstrip())
    for start, end, fields in _field_spans(question.lstrip()):
        start, end = start + leading, end + leading
        if start and re.match(r'\w', question[start - 1]):
            continue
        if fields != {trait}:
            continue
        # Record-value copula, or an explicit positive recorded state: no request-verb grammar.
        for pattern in (r'\s*기록\s*값(?:이|가|은|는)?\s*' + value_pattern
                        + r'(?:(?:인지|인|이다|입니다)(?=\s|[.!?,]|$)|(?=\s+조건(?:으로|인|을|이|은)?(?=\s|[.!?,]|$)))',
                        r'(?:이|가|은|는)?\s*' + value_pattern + r'(?:으)?로(?=\s*' + _RECORD_STATE + r')'):
            match = re.match(pattern, question[end:])
            if match:
                assignments.append(Span(question[start:end + match.end()], start, end + match.end()))
    if len(assignments) != 1 or not _record_field_matches(assignments[0].text, trait):
        return None
    evidence = assignments[0]
    original = span_of(question, text)
    if original is not None:
        # Expand only a unique original short suffix containing the same value within this proved field assignment.
        if (question.count(text) == 1 and evidence.start <= original.start and original.end <= evidence.end
                and re.search(value_pattern, text)):
            return evidence
        return None
    fields = _field_spans(text)
    if (len(fields) == 1 and fields[0][0] == 0 and fields[0][2] == {trait}
            and re.fullmatch(r'(?:이|가|은|는)?\s*' + value_pattern + r'인', text[fields[0][1]:])):
        return evidence
    return None


def _meta_spans(question):
    return [Span(m.group(), m.start(), m.end()) for pattern in (_UNRESTRICTED, _DISCOURSE, _RATE_META)
            for m in pattern.finditer(question)]


def _blank(question):
    spans = [m.span() for pattern in (_SOURCE_SCOPE, _SCOPE_META) for m in re.finditer(pattern, question, re.I)]
    spans += [(span.start, span.end) for span in _meta_spans(question)]
    # Only an explicitly labelled canonical niche value may shadow a predation keyword.
    # A predator noun or a predation/avoidance request must retain its veto.
    niche_labels = [label for label, name in _TRAIT_LABELS.items() if name == 'trophic_niche']
    for pattern, meanings in _KNOWN:
        if not any(name == 'trophic_niche' for name, _ in meanings):
            continue
        for match in pattern.finditer(question):
            before, after = question[:match.start()], question[match.end():]
            if re.match(r'(?:인|이고|이며|이다|입니다)(?=\s|새|종|[,.?!]|$)', after):
                spans.append(match.span())
    chars = list(question)
    for start, end in spans:
        chars[start:end] = ' ' * (end - start)
    return ''.join(chars)


def _text(raw, key):
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SemanticIntentError(f'{key} must be a string or null')
    return value


def _span(question, text):
    span = span_of(question, text.strip()) if text is not None else None
    if text is not None and span is None:
        raise _Reject('surface not in question')
    return span


def _numbers_agree(question, pairs, restatements=()):
    """Each numeric condition matches a number+unit in its own surface, with the written comparison; every
    number in the question belongs to a numeric condition surface."""
    numeric = [(c, span) for c, span in pairs if TRAIT_CONDITIONS[c.trait_name][1] == 'number']
    for span in dict.fromkeys(span for _, span in numeric):
        conditions = [c for c, s in numeric if s == span]
        written = [(float(n), u) for n, u in re.findall(rf'({_NUM})\s*({_UNIT})?', span.text)]
        values = []
        for number, unit in written:
            unit = unit or next((u for n, u in written if u), None)   # 100~200g: the unit is written once
            if unit is None:
                return False
            values.append((_UNITS[unit][0], round(number * _UNITS[unit][1], 6)))
        if sorted(values) != sorted((c.unit, c.threshold) for c in conditions):
            return False
        if (span.end < len(question) and re.match(r'[가-힣]', question[span.end:])
                and re.search(r'(?:' + _OPS + r')$', span.text)
                and not re.match(_PREDICATE_TAIL + r'(?=\s|[,.!?]|$)',
                                 question[span.end:])):
            return False  # a comparator prefix must not consume the beginning of another content word
        ops = [_op(m) for m in re.findall(_OP_WORD, span.text)]
        if len(conditions) == 1 and ops != [conditions[0].op]:
            return False   # the comparison must be written and agree
        if len(conditions) == 2 and not ops and (not re.search(_RANGE, span.text)
                                                 or sorted(c.op for c in conditions) != ['num_gte', 'num_lte']):
            return False
        if len(conditions) == 2 and ops and sorted(ops) != sorted(c.op for c in conditions):
            return False
        if len(conditions) > 2:
            return False
    covered = [span for _, span in numeric] + list(restatements)
    for span in dict.fromkeys(span for c, span in pairs if TRAIT_CONDITIONS[c.trait_name][1] == 'share'):
        # share_gt is "above 0": a number in its surface must be that 0 with a strictly-greater comparison.
        zeros = [m.span() for m in re.finditer(_SHARE_ZERO, span.text)]
        if not all(any(a <= m.start() and m.end() <= b for a, b in zeros) for m in re.finditer(_NUM, span.text)):
            return False
        covered.append(span)
    # A separately stated positive-share threshold refers unambiguously to the sole share condition.
    if sum(TRAIT_CONDITIONS[c.trait_name][1] == 'share' for c, _ in pairs) == 1:
        covered += [Span(m.group(), m.start(), m.end()) for m in re.finditer(
            rf'(?<![가-힣])먹이\s*(?:비중|비율)(?:은|는|이|가)?\s*{_SHARE_ZERO}', question)]
    return all(any(s.start <= m.start() and m.end() <= s.end for s in covered)
               for m in re.finditer(_NUM, question))


# A request/command form (골라줘, 보여 줄래, 찾아 주세요) is how the user asks, never a condition's own wording.
_REQUEST = re.compile(r'.*(?:줘|줘요|주세요|줄래|줄래요|주실래요|봐|봐요|볼래|해요|해)')


def _supported(condition, span):
    """The surface is the condition's own wording: a known word of its (trait, value), or, for a synonym the
    vocabulary lacks, at least one content word and no request form. Numbers are checked by _numbers_agree;
    which field a synonym means is the separate semantic audit's to verify."""
    if re.search(r'지\s*(?:마(?:세요|십시오)?(?=\s|[.!?,]|$)|말(?:아|고|자)|않)', span.text):
        return False  # A prohibited/negative assignment is not positive equality evidence.
    if TRAIT_CONDITIONS[condition.trait_name][1] == 'number':
        return True
    if (isinstance(condition.value, str) and _record_field_matches(span.text, condition.trait_name)
            and re.search(r'(?<!\w)' + re.escape(condition.value) + r'(?![A-Za-z0-9_])', span.text)):
        return True  # An explicitly typed canonical value is its own evidence even beside request wording.
    if any(pattern.search(span.text) and (condition.trait_name, condition.value) in meanings
           for pattern, meanings in _KNOWN):
        return True
    words = [w for w in (_PUNCT.sub('', token) for token in span.text.split()) if w]
    return not any(_REQUEST.fullmatch(w) for w in words) and any(not _FILLER.fullmatch(w) for w in words)


# What may follow a name inside its token: nothing, or particles only (까마귀과로, 참새목에서는) — never a verb
# or another noun (모아 + 줘, 목 + 록).
_NAME_TAIL = re.compile(r'(?:이면서|면서|이고|이며|이자|에서|에게|에|으로|로|의|은|는|이|가|을|를|와|과|랑|이랑|하고|처럼|'
                        r'도|만|까지|부터|보다|중|들)*')


def _named_taxa(question, pairs=()):
    """Spans of every catalog taxon name (pinned order/family/genus labels, source-checked species, a *목 order) and
    every scientific name in the question, when the rest of its token is particles only; longest name per token."""
    higher, species = _taxon_names()
    # Only checked, typed condition evidence can consume an English enum that resembles a scientific name.
    values = [(span.start + m.start(), span.start + m.end()) for condition, span in pairs
              if TRAIT_CONDITIONS[condition.trait_name][1] == 'text'
              for m in re.finditer(r'(?<![A-Za-z0-9_])' + re.escape(condition.value) + r'(?![A-Za-z0-9_])', span.text)]
    found = [(m.start(1), m.end(1)) for m in re.finditer(_SCIENTIFIC, question)
             if m.group(1) in higher or m.group(1) in species
             or not any(start <= m.start(1) and m.end(1) <= end for start, end in values)]
    for start, end in _tokens(question):
        token = question[start:end]
        # Object + vowel-final connective + auxiliary request is a verb phrase, not a bare taxon.
        if (re.search(r'[가-힣]+(?:을|를|만)\s+$', question[:start]) and token.endswith(('아', '어', '여'))
                and re.match(r'\s+(?:줘(?:요)?|주세요|줄래(?:요)?)(?=[\s.!?]|$)', question[end:])):
            continue
        lead = len(token) - len(re.sub(r'^\W+', '', token))
        start, token = start + lead, re.sub(r'\W+$', '', token[lead:])
        for cut in range(len(token), 1, -1):
            stem, rest = token[:cut], token[cut:]
            if ((stem in higher or stem in species or re.fullmatch(r'[가-힣]+목', stem)) and _NAME_TAIL.fullmatch(re.sub(r'\W', '', rest))
                    and not re.match(r'\s*열매', question[start + cut:])):   # 마가목 열매: a plant
                found.append((start, start + cut))
                break
    return found


def _taxa_kept(question, names, pairs=()):
    """Every named taxon remains in a plan name span, including repeated mentions of the identical name."""
    return all(any(n.start <= s and e <= n.end or question[s:e] == n.text for n in names)
               for s, e in _named_taxa(question, pairs))


# These forms express entity exclusion or numeric equality exclusion, never an arbitrary negated predicate.
_REMOVE = r'(?:말고|제외(?:하고|한|해(?:요)?|해\s*주세요)?|빼(?:고|\s*줘(?:요)?|\s*주세요)|뺀)(?=[\s,.!?]|$)'
_EQUAL_EXCLUSION = re.compile(
    rf'(?<![\w.])(?P<number>{_NUM})\s*(?P<unit>{_UNIT})\s*(?:인|와\s*같은|에\s*해당하는)\s*'
    rf'(?:(?:기록|경우|것|새|종)(?:은|는|을|를)?\s*)?{_REMOVE}')


def _exclusions(question):
    """Original exclusion spans with their explicit subject; recognition alone never authorises execution."""
    spans = []
    for start, end in _named_taxa(question):
        match = re.match(rf'(?:을|를|은|는)?\s*(?:자신(?:은|는|을|를)?\s*)?{_REMOVE}', question[end:])
        if match:
            stop = end + match.end()
            spans.append((Span(question[start:stop], start, stop), question[start:end]))
    for match in _EQUAL_EXCLUSION.finditer(question):
        unit, factor = _UNITS[match['unit']]
        spans.append((Span(match.group(), match.start(), match.end()),
                      (unit, round(float(match['number']) * factor, 6))))
    return spans


def _checked_exclusions(question, kind, names, pairs):
    """Prove exclusion adds nothing: the same reference entity, or an already strict numeric bound."""
    spans = []
    numeric = [c for c, _ in pairs if TRAIT_CONDITIONS[c.trait_name][1] == 'number']
    for span, subject in _exclusions(question):
        if isinstance(subject, str):
            valid = kind == 'shared_diet' and len(names) == 1 and subject == names[0].text
        else:
            valid = (kind == 'taxon_traits' and len({c.trait_name for c in numeric}) == 1
                     and any(c.op in ('num_gt', 'num_lt') and (c.unit, c.threshold) == subject for c in numeric))
        if not valid:
            raise _Reject('exclusion is not implied by the plan', (span,))
        spans.append(span)
    return spans


def _taxon_span(question, text):
    """The taxon's span; a rank word copied after a scientific name (Corvus 속) is left out of the name."""
    span = _span(question, text)
    if span is not None:
        bare = re.fullmatch(r'([A-Z][a-z]+(?: [a-z]+){0,2})\s*(?:속|과|목|종|아종)', span.text)
        if bare:
            span = Span(bare.group(1), span.start, span.start + len(bare.group(1)))
    return span


def _relation_span(question, text, species):
    """Recover only an omitted exact reference name + particle; the evidence remains a unique original span."""
    direct = span_of(question, text.strip())
    if direct is not None:
        return direct
    matches = []
    for gap in re.finditer(r'\s+', text.strip()):
        left, right = text.strip()[:gap.start()], text.strip()[gap.end():]
        pattern = re.escape(left) + r'\s+' + re.escape(species) + r'(?:와|과|랑|이랑|하고)\s+' + re.escape(right)
        matches += [Span(m.group(), m.start(), m.end()) for m in re.finditer(pattern, question)]
    if len(matches) != 1:
        raise _Reject('relation surface not uniquely present in question')
    return matches[0]


def _known_words_agree(question, pairs, names, relation_span=None):
    """Every known vocabulary word lies in a name span or in a condition span whose (trait, value) it can mean."""
    taken = []
    meta = _meta_spans(question)
    for pattern, meanings in _KNOWN:
        for match in pattern.finditer(question):
            if any(span.start <= match.start() and match.end() <= span.end for span in meta):
                continue
            if any(s <= match.start() < e for s, e in taken):
                continue   # part of a longer known word
            taken.append((match.start(), match.end()))
            if any(n.start <= match.start() and match.end() <= n.end for n in names):
                continue
            if (relation_span is not None and relation_span.start <= match.start()
                    and match.end() <= relation_span.end and ('trophic_niche', None) in meanings):
                continue
            inside = [(c, span) for c, span in pairs if span.start <= match.start() and match.end() <= span.end]
            used = [(c, span) for c, span in inside
                    if (c.trait_name, c.value) in meanings or (c.trait_name, None) in meanings]
            if not used:
                return False
            # A bare word several traits share (잡식) needs its trait named in the span, as in the extractor.
            if len(_BARE.get(match.group().replace('  ', ' '), ())) > 1 and not any(
                    re.search(_pattern(label), span.text) for c, span in used
                    for label, name in {**_TRAIT_LABELS, LABELS[c.trait_name]: c.trait_name}.items()
                    if name == c.trait_name):
                return False
    return True


def _conditions(question, raw):
    items = raw.get('conditions', [])
    if not isinstance(items, list):
        raise SemanticIntentError('conditions must be a list')
    pairs = []
    for item in items:
        if not isinstance(item, dict) or not {'trait_name', 'op', 'surface'} <= set(item) <= _CONDITION_KEYS:
            raise SemanticIntentError('bad condition object')
        threshold = item.get('threshold')
        if threshold is not None and (isinstance(threshold, bool) or not isinstance(threshold, (int, float))):
            raise _Reject('bad threshold')
        if not all(isinstance(item.get(k), (str, type(None))) for k in ('trait_name', 'op', 'value', 'unit', 'surface')):
            raise _Reject('bad condition field')
        if item['trait_name'] not in TRAIT_CONDITIONS:
            raise _Reject('unknown trait')
        if TRAIT_CONDITIONS[item['trait_name']][1] == 'share' and threshold is None:
            threshold = 0   # a share condition is always "above 0"
        condition = TraitCondition(item['trait_name'], item['op'], item.get('value'),
                                   None if threshold is None else float(threshold), item.get('unit'))
        pairs.append((condition, _span(question, item['surface'])))
    try:
        if pairs:
            checked_conditions(tuple(c for c, _ in pairs))
    except ValueError:
        raise _Reject('condition not allowed') from None
    return pairs


def _name_ok(text):
    compact = text.replace(' ', '')
    return (_valid_name(text) and compact not in GROUP_WORDS
            and (not re.match(r'[가-힣]', text) or bounded_korean_name(text)))


def _build(question, raw, trace=tracing.NOOP_SPAN):
    kind = raw.get('kind')
    if kind not in KINDS:
        raise SemanticIntentError('unknown kind')
    unresolved = raw.get('unresolved', [])
    if not isinstance(unresolved, list) or not all(isinstance(t, str) for t in unresolved) \
            or not isinstance(raw.get('unknown_relation', False), bool):
        raise SemanticIntentError('bad unresolved/unknown_relation')
    taxon, species, relation = _text(raw, 'taxon'), _text(raw, 'species'), _text(raw, 'relation_text')
    pairs = _conditions(question, raw)
    for condition, span in pairs:
        if TRAIT_CONDITIONS[condition.trait_name][1] in ('number', 'share'):
            continue
        fields = {name for _, _, names in _field_spans(span.text) for name in names}
        same_span = {c.trait_name for c, evidence in pairs if evidence == span}
        if fields and (condition.trait_name not in fields or not fields <= same_span):
            raise _Reject('explicit original field differs from planned condition')
        possible = {name for name, (_, kind, values) in TRAIT_CONDITIONS.items()
                    if kind not in ('number', 'share') and condition.value in values}
        if not fields and len(possible) > 1:
            context = {name for _, _, names in _field_spans(_blank(question)) for name in names} & possible
            if context != {condition.trait_name}:
                raise _Reject('shared enum value lacks an unambiguous original field')
    if re.search(_RECORD_CONTEXT, question) and any(
            not _record_field_matches(span.text, condition.trait_name) for condition, span in pairs):
        raise _Reject('record predicate field is not proved by its original label')
    if re.search(_COPULAR_DENIAL, _blank(question)):
        raise _Reject('explicit denial of a proposed predicate')
    unrestricted = {_META_DIMENSION_CODES[re.sub(r'\s+', '', m['dimension'])]
                    for m in _UNRESTRICTED.finditer(question)}
    if (any(c.trait_name in unrestricted for c, _ in pairs)
            or kind == 'shared_diet' and 'trophic_niche' in unrestricted):
        raise _Reject('condition on explicitly unrestricted dimension')
    if _RATE_META.search(question) and not (
            any(c.trait_name == 'diet_category' and c.op == 'eq' for c, _ in pairs)
            and not any(TRAIT_CONDITIONS[c.trait_name][1] == 'share' for c, _ in pairs)):
        raise _Reject('ratio explanation is not proved by an explicit category condition')
    if unresolved or raw.get('unknown_relation'):
        reason = 'unsupported_relation' if raw.get('unknown_relation') else 'unresolved_conditions'
        tracing.note_outcome(reason, 'plan_validation')
        trace.set_attributes({'reason': reason, 'unresolved_count': len(unresolved),
                              'unknown_relation': raw.get('unknown_relation', False)})
        residual = tuple(s for s in (span_of(question, t.strip()) for t in unresolved) if s is not None)
        if not residual and raw.get('unknown_relation') and relation is not None:
            residual = tuple(s for s in (span_of(question, relation.strip()),) if s is not None)
        return GraphIntent(None, residual=residual, ambiguity=() if residual else ('other',), source=SOURCE)
    if kind == 'none':
        if taxon is not None or species is not None or relation is not None or pairs or _exclusions(question):
            tracing.note_outcome('plan_validation_rejected', 'plan_validation')
            trace.set_attributes({'reason': 'plan_validation_rejected',
                                  'rejection_detail': 'none retains slots or exclusions'})
            return _HOLD
        return GraphIntent(None, source=SOURCE)
    if kind == 'taxon_traits' and taxon is None and species is not None:
        taxon, species = species, None   # a species/subspecies scope is a taxon here (checked the same way)
    if kind == 'taxon_traits':
        if species is not None or relation is not None or not pairs:
            raise _Reject('taxon_traits slots')
        rank = _taxon_span(question, taxon)
        if rank is not None and (rank.text.replace(' ', '') in GROUP_WORDS or not (
                _valid_name(rank.text) or re.fullmatch(r'[가-힣]+목|[A-Z][a-z]+(?: [a-z]+){0,2}', rank.text))):
            raise _Reject('bad taxon')
        names = [rank] if rank is not None else []
        intent = GraphIntent('taxon_traits', rank=rank, conditions=tuple(pairs), source=SOURCE)
    else:
        # shared_diet: no condition, or one explicit habitat (-> the existing habitat_shared_diet query).
        if (taxon is not None or species is None or relation is None or len(pairs) > 1
                or any((c.trait_name, c.op) != ('habitat', 'eq') for c, _ in pairs)):
            raise _Reject('shared_diet slots')
        if any(re.search(pattern, question) for pattern in _SAME_HABITAT_CUES):
            raise _Reject('habitat relation')
        name, phrase = _span(question, species), _relation_span(question, relation, species)
        spans = [name, phrase] + [span for _, span in pairs]
        # Same diet *category*: the phrase names diet/ecology and sameness; "eats the same food" never is one.
        if (not _name_ok(name.text) or not re.search(_DIET_WORD, phrase.text)
                or not re.search(r'같|동일|일치|공유|비슷|유사', phrase.text) or re.search(_EAT, question)):
            raise _Reject('shared_diet evidence')
        names = [name]
        evidence = (('diet', phrase), ('relation', phrase))
        if pairs:
            (habitat, habitat_span), = pairs
            intent = GraphIntent('habitat_shared_diet', species=(name,), diet='niche', habitat=habitat.value,
                                 relation='same', evidence=evidence + (('habitat', habitat_span),), source=SOURCE)
        else:
            intent = GraphIntent('shared_diet', species=(name,), diet='niche', relation='same', evidence=evidence,
                                 source=SOURCE)
    # Condition and taxon surfaces are disjoint (a range's two conditions share one); each condition is its own
    # wording; every taxon the question names stays in the plan.
    spans = list(dict.fromkeys([span for _, span in pairs] + (names if kind == 'taxon_traits' else [])))
    if any(a.start < b.end and b.start < a.end for i, a in enumerate(spans) for b in spans[i + 1:]):
        raise _Reject('overlapping surfaces')
    named = {pipeline for pattern, pipeline, _ in TRAIT_SOURCES if re.search(pattern, question, re.I)}
    if named and (any(TRAIT_CONDITIONS[c.trait_name][0] not in named for c, _ in pairs)
                  or kind == 'shared_diet' and named != {'reference-avonet'}):
        raise _Reject('condition outside the named source')
    if kind == 'shared_diet' and named - {'reference-avonet'}:
        raise _Reject('shared diet is AVONET trophic_niche only')   # not vacuous when there are no conditions
    if not all(_supported(c, span) for c, span in pairs) or not _taxa_kept(question, names, pairs):
        missing = tuple(Span(question[s:e], s, e) for s, e in _named_taxa(question, pairs)
                        if not any(n.start <= s and e <= n.end or question[s:e] == n.text for n in names))
        raise _Reject('condition without its own support, or a named taxon left out', missing)
    restatements = _checked_exclusions(question, kind, names, pairs)
    if not _numbers_agree(question, pairs, restatements):
        spans = tuple(Span(m.group(), m.start(), m.end()) for m in re.finditer(rf'{_NUM}\s*(?:{_UNIT})?', question))
        raise _Reject('numbers or known words disagree', spans)
    if not _known_words_agree(question, pairs, names, phrase if kind == 'shared_diet' else None):
        raise _Reject('numbers or known words disagree')
    if validate_intent(question, intent):
        raise _Reject('invalid intent')
    return intent


def reconcile_graph_plan(question, raw):
    """Recover unique original evidence and proved redundant exclusions before the independent audit.

    Predicates and values stay unchanged. A dropped Korean rank suffix may only restore the uniquely
    recorded catalog scope. If the resulting plan fails any existing local check,
    keep the original proposal, including all unresolved constraints.
    """
    if (not isinstance(question, str) or not isinstance(raw, dict) or not set(raw) <= _KEYS
            or raw.get('kind') not in KINDS or raw.get('unknown_relation', False) is not False
            or not all(isinstance(raw.get(key), (str, type(None))) for key in ('taxon', 'species', 'relation_text'))):
        return raw, []
    items, unresolved = raw.get('conditions', []), raw.get('unresolved', [])
    if (not isinstance(items, list) or not all(isinstance(item, dict) and isinstance(item.get('surface'), str) for item in items)
            or not isinstance(unresolved, list) or not all(isinstance(t, str) for t in unresolved)):
        return raw, []
    lexical = extract_graph_intent(question)
    if _lexical_decides(question, lexical):
        return raw, []
    candidate = {**raw, 'conditions': [dict(item) for item in items]}
    changes = []
    taxon, rank = raw.get('taxon'), lexical.rank
    if (raw.get('kind') == 'taxon_traits' and raw.get('species') is None and isinstance(taxon, str)
            and re.fullmatch(r'[가-힣]+', taxon) and rank is not None and rank.text in _taxon_names()[0]
            and rank.text in {taxon + suffix for suffix in ('목', '과', '속')}
            and _named_taxa(question) == [(rank.start, rank.end)] and question.count(taxon) == 1):
        candidate['taxon'] = rank.text
        changes.append({'field': 'taxon', 'rule': 'rank_suffix', 'before': taxon, 'after': rank.text})
    for index, item in enumerate(candidate['conditions']):
        text = item.get('surface')
        if not isinstance(text, str):
            continue
        evidence = _original_record_assignment(question, item)
        if evidence is not None and evidence.text != text:
            item['surface'] = evidence.text
            changes.append({'field': f'conditions[{index}].surface', 'rule': 'positive_record_equality',
                            'before': text, 'after': evidence.text})
            text = evidence.text
        if span_of(question, text.strip()) is not None:
            continue
        # A numeric predicate keeps its exact operand/comparator; only a copular query ending may vary.
        spec = TRAIT_CONDITIONS.get(item.get('trait_name'))
        operators = list(re.finditer(_OPS, text.strip()))
        if spec and spec[1] == 'number' and len(operators) == 1:
            operator = operators[0]
            prefix, ending = text.strip()[:operator.end()], text.strip()[operator.end():]
            functional = r'(?:' + _PREDICATE_TAIL + r'|이라는\s*조건)'
            matches = [] if not re.fullmatch(functional, ending) else list(re.finditer(
                r'(?<!\w)' + re.escape(prefix).replace(r'\ ', r'\s*')
                + r'(?=(?:' + functional + r')?(?:\s|[,.!?]|$))', question))
            if len(matches) == 1:
                item['surface'] = matches[0].group()
                changes.append({'field': f'conditions[{index}].surface', 'rule': 'numeric_copular_ending',
                                'before': text, 'after': item['surface']})
                continue
        # '조건' introduces the same filter; recover its grammatical tail, not a changed biological role.
        scaffold = re.fullmatch(r'(.+\s조건)(?:인|으로|이고|이며)', text.strip())
        matches = [] if scaffold is None else list(re.finditer(
            r'(?<!\w)' + re.escape(scaffold[1]) + r'(?:으로|인|이고|이며)(?=\s|[,.!?]|$)', question))
        if len(matches) == 1:
            item['surface'] = matches[0].group()
            changes.append({'field': f'conditions[{index}].surface', 'rule': 'query_condition_ending',
                            'before': text, 'after': item['surface']})
            continue
        # Only the ending of the same positive existence predicate may change; its content stays verbatim.
        ending = re.fullmatch(r'(.+\s있)(?:어(?:요)?|다|습니다)', text.strip())
        matches = [] if ending is None else list(re.finditer(
            r'(?<!\w)' + re.escape(ending[1]) + r'(?:고|으며|는)(?=\s|[,.!?]|$)', question))
        if len(matches) == 1:
            item['surface'] = matches[0].group()
            changes.append({'field': f'conditions[{index}].surface', 'rule': 'predicate_ending',
                            'before': text, 'after': item['surface']})
    text, species = raw.get('relation_text'), raw.get('species')
    if (raw.get('kind') == 'shared_diet' and isinstance(text, str) and isinstance(species, str)
            and span_of(question, text.strip()) is None):
        omitted = re.fullmatch(r'(.+?)\s*(?:\.{3}|…)\s*((?:와|과|랑|이랑|하고)\s+.+)', text.strip())
        matches = [] if omitted is None or len(re.findall(r'\.{3}|…', text)) != 1 else list(re.finditer(
            r'(?<!\w)' + re.escape(omitted[1].rstrip()) + r'\s+' + re.escape(species)
            + r'\s*' + re.escape(omitted[2]) + r'(?=\s|[,.!?]|$)', question))
        if len(matches) == 1:
            candidate['relation_text'] = matches[0].group()
            changes.append({'field': 'relation_text', 'rule': 'exact_reference_placeholder',
                            'before': text, 'after': candidate['relation_text']})
        particle = re.fullmatch(r'(?:와|과|랑|이랑|하고)\s+(.+)', text.strip())
        matches = [] if particle is None else list(re.finditer(
            r'(?<!\w)' + re.escape(species) + r'(?:와|과|랑|이랑|하고)\s+'
            + re.escape(particle[1]) + r'(?=\s|[,.!?]|$)', question))
        if len(matches) == 1:
            candidate['relation_text'] = matches[0].group()
            changes.append({'field': 'relation_text', 'rule': 'reference_particle',
                            'before': text, 'after': candidate['relation_text']})
    if (raw.get('kind') == 'shared_diet' and isinstance(text, str) and isinstance(species, str)
            and re.search(_DIET_WORD, text) and not re.search(r'같|동일|일치|공유|비슷|유사', text)
            and len(list(re.finditer(r'(?<!\w)' + re.escape(text.strip()), question))) == 1):
        pattern = (r'(?<!\w)' + re.escape(text.strip()) + r'\s+' + re.escape(species)
                   + r'(?:와|과|랑|이랑|하고)\s+(?:같은|동일한|일치하는|비슷한|유사한)(?=\s|[,.!?]|$)')
        matches = list(re.finditer(pattern, question))
        if len(matches) == 1:
            candidate['relation_text'] = matches[0].group()
            changes.append({'field': 'relation_text', 'rule': 'reference_relation',
                            'before': text, 'after': candidate['relation_text']})
    for index, item in enumerate(candidate['conditions']):
        spec = TRAIT_CONDITIONS.get(item.get('trait_name'))
        surface = item.get('surface', '')
        if not spec or spec[1] != 'number' or span_of(question, surface.strip()) is None:
            continue
        written = list(re.finditer(rf'({_NUM})\s*({_UNIT})', surface))
        if len(written) != 1 or len(list(re.finditer(_NUM, surface))) != 1:
            continue
        match = written[0]
        unit, factor = _UNITS[match[2]]
        normalized = round(float(match[1]) * factor, 6)
        if (unit == spec[2] and item.get('unit') == match[2] and item.get('unit') != unit
                and not isinstance(item.get('threshold'), bool) and item.get('threshold') == normalized):
            before = item['unit']
            item['unit'] = unit
            changes.append({'field': f'conditions[{index}].unit', 'rule': 'original_numeric_unit',
                            'before': before, 'after': unit})
    if (re.search(_RECORD_CONTEXT, question) and any(
            not _record_field_matches(item['surface'], item.get('trait_name')) for item in candidate['conditions'])):
        return raw, []
    token = tracing.begin_outcome()
    try:
        framing = set()
        record_frames = []
        rank_frames = []
        scope = candidate.get('taxon') if candidate.get('kind') == 'taxon_traits' else candidate.get('species')
        if isinstance(scope, str):
            matches = list(re.finditer(r'(?<!\w)' + re.escape(scope) + r'\s+(?P<rank>목|과|속|아종|종)의(?=\s)', question))
            rank_word = ({1: '속', 2: '종', 3: '아종'}.get(len(scope.split()))
                         if re.fullmatch(r'[A-Z][a-z]+(?: [a-z]+){0,2}', scope) else
                         '종' if scope in _taxon_names()[1] else
                         scope[-1] if scope in _taxon_names()[0] else None)
            if (len(matches) == 1 and matches[0]['rank'] == rank_word
                    and question.count(rank_word + '의') == 1):
                framing.add(matches[0]['rank'] + '의')
                rank_frames.append(Span(matches[0].group(), matches[0].start(), matches[0].end()))
        # Only a positive record-check request immediately attached to retained condition evidence is framing.
        for item in candidate['conditions']:
            surface = item.get('surface', '')
            span = span_of(question, surface.strip())
            if span is not None and _record_field_matches(surface, item.get('trait_name')):
                match = re.match(r'\s*(' + _RECORD_REQUEST + r')(?=\s|[.!?,]|$)', question[span.end:])
                if match and question.count(match[1]) == 1:
                    framing.add(match[1])
                    record_frames.append(Span(match[1], span.end + match.start(1), span.end + match.end(1)))
        # Unresolved segmentation is irrelevant: only the union of checked source evidence and framing may cover it.
        retained = [span for condition, span in _conditions(question, candidate)
                    if question.count(span.text) == 1 and _record_field_matches(span.text, condition.trait_name)]
        coverage = rank_frames + retained + record_frames if record_frames else []
        for text in unresolved:
            fragment = text.strip().rstrip('.!?')
            source = span_of(question, fragment) if fragment else None
            if (source is not None and question.count(fragment) == 1 and coverage
                    and all(char.isspace() or unicodedata.category(char).startswith('P')
                            or any(frame.start <= offset < frame.end for frame in coverage)
                            for offset, char in enumerate(question[source.start:source.end], source.start))):
                framing.add(fragment)
        meta = {span.text for span in _meta_spans(question)}
        meta |= framing
        # The denial of a ratio condition is redundant only for an explicit category, never a share query.
        category_only = any(item.get('trait_name') == 'diet_category' and item.get('op') == 'eq'
                            for item in candidate['conditions']) and not any(
                                TRAIT_CONDITIONS.get(item.get('trait_name'), ('', ''))[1] == 'share'
                                for item in candidate['conditions'])
        if not category_only:
            meta -= {m.group() for m in _RATE_META.finditer(question)}
        kept = [text for text in unresolved if text.strip().rstrip('.!?') not in meta]
        if len(kept) != len(unresolved):
            candidate['unresolved'] = kept
            changes.append({'field': 'unresolved', 'rule': 'explicit_query_framing', 'before': unresolved, 'after': kept})
        unresolved = candidate.get('unresolved', [])
        kept = [text for text in unresolved if not (
            re.fullmatch(rf'(?:{_ASKS}|\s)+', text.rstrip('.!?'))
            and re.search(r'(?:줘|줄래|주세요|주실래요|궁금해요|궁금해|궁금합니다|싶어요|싶어)$', text.rstrip('.!?'))
            and question.count(text.rstrip('.!?')) == 1
            and re.search(r'(?<!\w)' + re.escape(text) + r'[.!?]*\s*$', question))]
        if len(kept) != len(unresolved):
            candidate['unresolved'] = kept
            changes.append({'field': 'unresolved', 'rule': 'terminal_request',
                            'before': unresolved, 'after': kept})
        unresolved = candidate.get('unresolved', [])
        if unresolved and raw.get('kind') in ('taxon_traits', 'shared_diet'):
            pairs = _conditions(question, candidate)
            names = [name] if (name := _taxon_span(question, candidate.get('taxon') if raw['kind'] == 'taxon_traits' else candidate.get('species'))) is not None else []
            redundant = {span.text for span in _checked_exclusions(question, raw['kind'], names, pairs)}
            kept = [text for text in unresolved if text.strip().rstrip('.!?') not in redundant]
            if len(kept) != len(unresolved):
                candidate['unresolved'] = kept
                changes.append({'field': 'unresolved', 'rule': 'strict_bound_restatement',
                                'before': unresolved, 'after': kept})
        if changes and execution_gate(question, _build(question, candidate)) == 'answer':
            return candidate, changes
    except (SemanticIntentError, _Reject):
        pass
    finally:
        tracing.end_outcome(token)
    return raw, []


def interpret(question, provider, examples=()):
    """GraphIntent (source='semantic') from ``provider(question, examples, CONTRACT)``; fail-closed.

    Raises SemanticIntentError when the provider fails or its output is not the contract's object.
    """
    token = tracing.begin_outcome()
    try:
        raw = provider(question, list(examples), CONTRACT)
    except Exception as error:
        if not tracing.collected_outcome():
            tracing.note_outcome('interpretation_error', 'interpretation')
        spans = tuple(s for s in getattr(error, 'original_spans', ())
                      if isinstance(s, Span) and 0 <= s.start < s.end <= len(question)
                      and question[s.start:s.end] == s.text)[:3]
        reason = getattr(error, 'reason', None)
        raise SemanticIntentError(f'provider failed ({type(error).__name__})',
                                  reason=reason if reason == 'semantic_audit_rejected' else None,
                                  original_spans=spans) from error
    finally:
        outcome = tracing.collected_outcome()
        tracing.end_outcome(token)
        if token is not None and outcome:
            tracing.note_outcome(outcome.get('reason'), outcome.get('stage', 'interpretation'))
    with tracing.span('graph_intent.validation', attributes={'stage': 'plan_validation'}) as trace:
        trace.set_inputs(raw)
        try:
            if not isinstance(raw, dict) or 'kind' not in raw or not set(raw) <= _KEYS:
                raise SemanticIntentError('provider output is not the contract object')
            return _build(question, raw, trace)
        except SemanticIntentError as error:
            tracing.note_outcome('invalid_plan', 'plan_validation')
            trace.set_attributes({'reason': 'invalid_plan', 'rejection_detail': str(error)})
            raise
        except _Reject as error:
            tracing.note_outcome('plan_validation_rejected', 'plan_validation')
            trace.set_attributes({'reason': 'plan_validation_rejected', 'rejection_detail': str(error)})
            residual = tuple(s for s in error.spans if isinstance(s, Span)
                             and 0 <= s.start < s.end <= len(question) and question[s.start:s.end] == s.text)
            return GraphIntent(None, residual=residual, source=SOURCE) if residual else _HOLD


def verified_semantic_examples():
    """Reviewed local plans that still pass the executable contract; not cached answers or DB evidence."""
    examples = []
    token = tracing.begin_outcome()
    try:
        for kind, question, plan in _EXAMPLES:
            if kind not in KINDS or plan.get('kind') != kind:
                continue
            full = {'conditions': [], 'unresolved': [], 'unknown_relation': False, **deepcopy(plan)}
            try:
                intent = _build(question, full)
            except (SemanticIntentError, _Reject):
                continue
            if execution_gate(question, intent) == 'answer':
                examples.append({'question': question, 'kind': kind, 'intent': full})
    finally:
        tracing.end_outcome(token)
    return tuple(examples)


def original_issue_spans(question, plan, issues):
    """Only original plan fragments explicitly mentioned in the model's audit issues, never its explanation."""
    if not isinstance(plan, dict) or not isinstance(issues, list):
        return ()
    fragments = [plan.get(key) for key in ('taxon', 'species', 'relation_text')]
    if isinstance(plan.get('unresolved'), list):
        fragments += plan['unresolved']
    if isinstance(plan.get('conditions'), list):
        fragments += [item.get('surface') for item in plan['conditions'] if isinstance(item, dict)]
    spans = []
    for fragment in fragments:
        if (isinstance(fragment, str) and fragment.strip() and any(
                isinstance(issue, str) and fragment in issue for issue in issues)):
            span = span_of(question, fragment.strip())
            if span is not None and span not in spans:
                spans.append(span)
    return tuple(spans[:3])


def _examples(question, retrieve):
    if retrieve is None:
        return []
    try:
        verified = {row['question']: row for row in verified_semantic_examples()}
        found = retrieve(question, limit=5)
        examples = []
        for row in found or ():
            example = (verified.get(row.get('question')) if isinstance(row, dict)
                       and isinstance(row.get('question'), str) else None)
            if example is not None and row.get('kind') == example['kind'] and example not in examples:
                examples.append(example)
            if len(examples) == 5:
                break
        return examples
    except Exception:
        return []


def graph_intent_handler(question, *, provider, retrieve=None):
    """The extractor's intent when it decides the question, else the verified semantic intent."""
    with tracing.span('graph_intent.selection') as trace:
        lexical = extract_graph_intent(question)
        if not isinstance(question, str) or not question.strip() or _lexical_decides(question, lexical):
            trace.set_attribute('selected_interpreter', 'lexical')
            return lexical
        trace.set_attribute('selected_interpreter', 'semantic')
        proposed = interpret(question, provider, _examples(question, retrieve))
        if execution_gate(question, proposed) == 'not_graph' and lexical.kind is not None:
            trace.set_attribute('selected_interpreter', 'lexical')
            return lexical
        return proposed
