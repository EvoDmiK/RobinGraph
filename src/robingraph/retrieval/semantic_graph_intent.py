"""Structured (LLM) interpretation of graph questions, verified fail-closed (contract rg-semantic-v1).

Kinds interpreted here: ``taxon_traits`` (the existing trait fields on a taxon of any rank) and ``shared_diet``
(same AVONET trophic_niche as one species). A shared_diet with one explicit habitat condition becomes the existing
``habitat_shared_diet``; no habitat is ever added. The other existing kinds (common_taxonomy, same_genus,
korea_same_genus, order_fruit, habitat_different_diet, specific_fruit) stay lexical-only. The provider proposes a JSON
object; nothing it says is trusted on its own:

A. the existing lexical extractor runs first, and its negation/unsupported/residency/scope cues and the
   season, period and superlative cues below veto the provider call;
B. every surface must be original text and every value one of the existing canonical values; the provider
   maps a phrase to its value (synonyms included), but a number, unit or comparison in the text must
   agree exactly with the condition, and every number in the question must belong to a condition;
C. any unresolved text or unknown relation the provider reports is a clarify;
D. every known vocabulary word in the question (the extractor's trait, measure and habitat surfaces) must sit
   in a span whose value it can mean, so a recognised condition can never be dropped or re-labelled.
   Unknown wording also requires the transport's independent semantic audit; that audit remains probabilistic. There is no fixed sentence grammar.

A failed check yields a GraphIntent the gate turns into a clarify. No Cypher is built here.
"""
import re

from .graph_condition_extractor import (
    _BARE, _COMMON, _DOCUMENT_REQUEST, _EAT, _GENUS, _HABITAT_SUBJECT, _KOREA, _MEASURES, _NEGATION, _NICHE_DIFFERENT,
    _NICHE_SAME,
    _NUM, _RESIDENCY, _SAME_HABITAT, _SCIENTIFIC, _SHARE_WORDS, _TRAIT_LABELS, _UNIT, _UNITS, _UNSUPPORTED, GROUP_WORDS,
    _FILLER, _PUNCT, _op, _pattern, _taxon_names, _tokens, _trait_surfaces, _valid_name, extract_graph_intent)
from .graph_intent_schema import GraphIntent, Span, execution_gate, span_of, validate_intent
from .graph_questions import CONDITION_OPS, TAXON_RANKS, TRAIT_CONDITIONS, TraitCondition, checked_conditions
from .species_profile import LABELS, VALUES
from .species_questions import _DIET_WORD, bounded_korean_name

SOURCE = 'semantic'
KINDS = ('taxon_traits', 'shared_diet', 'none')
# Season, period and superlative asks have no field; the provider is never asked about them.
VETO_CUES = r'겨울|여름|(?<![가-힣])봄|가을|번식기|월동|\d+\s*월(?![가-힣])|가장|제일|최고'
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
_OP_WORD = r'이상|이하|초과|미만|넘는|넘고|넘으며|보다\s*(?:큰|무거운|긴|넓은|높은|두꺼운|작은|가벼운|짧은|좁은|낮은|얇은)'
_RANGE = r'~|에서|부터|사이|까지'
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


class _Reject(Exception):
    pass


_NULLABLE = {'type': 'STRING', 'nullable': True}
SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'kind': {'type': 'STRING', 'enum': list(KINDS)},
        'taxon': {**_NULLABLE, 'description': 'taxon_traits 전용: 조건을 적용할 분류군 원문(목·과·속·종·아종 모두). 없으면 null.'},
        'species': {**_NULLABLE, 'description': 'shared_diet 전용: 먹이 생태 범주를 비교할 기준 종 원문. taxon_traits에서는 항상 null.'},
        'conditions': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
            'trait_name': {'type': 'STRING', 'enum': list(TRAIT_CONDITIONS)},
            'op': {'type': 'STRING', 'enum': sorted({op for ops in CONDITION_OPS.values() for op in ops})},
            'value': _NULLABLE, 'threshold': {'type': 'NUMBER', 'nullable': True}, 'unit': _NULLABLE,
            'surface': {'type': 'STRING'}}, 'required': ['trait_name', 'op', 'surface']}},
        'relation_text': _NULLABLE,
        'unresolved': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'unknown_relation': {'type': 'BOOLEAN'},
    },
    'required': ['kind', 'conditions', 'unresolved', 'unknown_relation'],
}
INSTRUCTIONS = """새 그래프 질문 하나를 JSON으로만 해석합니다. 답을 만들지 말고 질문의 구조만 기록합니다.
- kind: taxon_traits(분류군이나 새 전체에서 형질 조건으로 찾기), shared_diet(한 종과 먹이 생태 범주가 같은 새), none(그 외).
- shared_diet에 서식지가 명시되면(예: 숲에 사는 새 중) conditions에 habitat eq 조건 하나만 넣습니다. 기준 종의 서식지를 짐작해 넣지 않습니다.
- taxon, species, relation_text, 각 조건의 surface는 질문 원문을 글자 그대로 복사합니다. 이름을 만들거나 고치지 않습니다.
- taxon_traits는 범위가 목·과·속이든 종·아종이든 항상 taxon에 넣고 species는 null입니다. species는 shared_diet의 기준 종에만 씁니다.
- 출처: 질문이 vocabulary.sources의 지원 출처(AVONET, EltonTraits)를 자료 범위로 말하면(예: "AVONET 기준", "EltonTraits 자료에서") 문서 검색 요구가 아닌 출처 한정이므로 unresolved에 넣지 않습니다. 그 출처의 형질 조건만 씁니다. 다른 출처·논문·관찰 기록·문헌 요청은 unresolved입니다. "기록된/자료가 있는 종을 찾아줘"처럼 조건 없이 조회를 뜻하는 말투도 제약이 아닙니다.
- share_gt는 비율이 0보다 크다는 뜻입니다. "0%보다 많은", "0 초과"처럼 0 초과 비교는 같은 조건이며, 0이 아닌 비율 기준(예: 50% 이상)은 지원하지 않으므로 unresolved입니다.
- "종/아종 기록에서", "종의 자료를 확인" 같은 조회 대상 소개는 별도 문헌 검색이 아닙니다. 조건에 해당하는 원문만 conditions로 넣고 나머지 단순 조회 문구를 unresolved로 넣지 않습니다.
- 학명이 세 단어이면 아종 전체 세 단어를 taxon에 복사합니다. 두 단어로 줄이거나 세 번째 단어를 미해결 조건으로 분리하지 않습니다.
- shared_diet는 기준 종 자신을 제외한 다른 종을 찾습니다. 기준 종 자신을 빼달라는 말은 이 기본 동작이며 unresolved가 아닙니다.
- 조건은 vocabulary의 trait_name·op·value·unit 값만 씁니다. 숫자는 vocabulary 단위(g, mm)로 환산한 threshold입니다.
- 먹는다·먹기도 한다·조금이라도 먹는다는 조건은 diet_distribution share_gt threshold=0입니다. 대표 먹이 생태(trophic_niche)나 먹이 유형(diet_category)으로 바꾸지 않습니다. 영양 단계라는 명시가 있으면 trophic_level입니다.
- taxon/species에는 조사와 분류 수준 접미사를 빼고 원문 이름만 복사합니다. 학명 뒤의 속·종·아종은 이름에 넣지 않습니다.
- shared_diet의 relation_text는 "같은 먹이 생태를 가진"처럼 같은 먹이 생태 범주를 말하는 구절입니다. 같은 먹이를 먹는다는 뜻은 shared_diet가 아닙니다.
- 해석하지 못한 말, 부정, 지역·계절·순위, 지원하지 않는 관계는 빼지 말고 unresolved에 원문 그대로 넣거나 unknown_relation=true로 표시합니다.
- unresolved에는 지원하지 않는 실제 검색 제약만 넣습니다. 요청·강조·대화 어미·문장 순서·범위를 지정하는 말투는 미지원 조건이 아닙니다.
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
    if lexical.negation and re.search(_NEGATION, blanked) or lexical.unsupported and any(
            re.search(pattern, blanked) for _, pattern in _UNSUPPORTED):
        return True
    # A vague or unread condition ('other') is the provider's to read; a name or kind conflict is not.
    if set(lexical.ambiguity) & {'name_ambiguous', 'group_unresolved', 'kind_tie'}:
        return True
    if lexical.kind not in (None, 'taxon_traits', 'habitat_shared_diet'):
        return True   # the other existing kinds stay lexical-only
    return any(re.search(pattern, blanked) for pattern in _VETOES)


# Lifting the taxonomic scope only (분류 제한 없이, 목·과·속 구분 없이): no taxon, not a negated condition.
# Any other "… 없이" (먹이 조건 없이) stays a negation veto.
_SCOPE_META = (r'(?<![가-힣])(?:분류군?|분류\s*수준|(?:목|과|속|종)(?:\s*[·,/]?\s*(?:목|과|속|종))*)\s*(?:의\s*)?'
               r'(?:제한|구분|상관)\s*없이')


def _blank(question):
    spans = [m.span() for pattern in (_SOURCE_SCOPE, _SCOPE_META) for m in re.finditer(pattern, question, re.I)]
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


def _numbers_agree(question, pairs):
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
    covered = [span for _, span in numeric]
    for span in dict.fromkeys(span for c, span in pairs if TRAIT_CONDITIONS[c.trait_name][1] == 'share'):
        # share_gt is "above 0": a number in its surface must be that 0 with a strictly-greater comparison.
        zeros = [m.span() for m in re.finditer(_SHARE_ZERO, span.text)]
        if not all(any(a <= m.start() and m.end() <= b for a, b in zeros) for m in re.finditer(_NUM, span.text)):
            return False
        covered.append(span)
    return all(any(s.start <= m.start() and m.end() <= s.end for s in covered)
               for m in re.finditer(_NUM, question))


# A request/command form (골라줘, 보여 줄래, 찾아 주세요) is how the user asks, never a condition's own wording.
_REQUEST = re.compile(r'.*(?:줘|줘요|주세요|줄래|줄래요|주실래요|봐|봐요|볼래|해요|해)')


def _supported(condition, span):
    """The surface is the condition's own wording: a known word of its (trait, value), or, for a synonym the
    vocabulary lacks, at least one content word and no request form. Numbers are checked by _numbers_agree;
    which field a synonym means is the separate semantic audit's to verify."""
    if TRAIT_CONDITIONS[condition.trait_name][1] == 'number':
        return True
    if any(pattern.search(span.text) and (condition.trait_name, condition.value) in meanings
           for pattern, meanings in _KNOWN):
        return True
    words = [w for w in (_PUNCT.sub('', token) for token in span.text.split()) if w]
    return not any(_REQUEST.fullmatch(w) for w in words) and any(not _FILLER.fullmatch(w) for w in words)


# What may follow a name inside its token: nothing, or particles only (까마귀과로, 참새목에서는) — never a verb
# or another noun (모아 + 줘, 목 + 록).
_NAME_TAIL = re.compile(r'(?:이면서|면서|이고|이며|이자|에서|에게|에|으로|로|의|은|는|이|가|을|를|와|과|랑|이랑|하고|처럼|'
                        r'도|만|까지|부터|보다|중|들)*')


def _named_taxa(question):
    """Spans of every catalog taxon name (pinned order/family/genus labels, source-checked species, a *목 order) and
    every scientific name in the question, when the rest of its token is particles only; longest name per token."""
    higher, species = _taxon_names()
    found = [(m.start(1), m.end(1)) for m in re.finditer(_SCIENTIFIC, question)]
    for start, end in _tokens(question):
        token = question[start:end]
        lead = len(token) - len(re.sub(r'^\W+', '', token))
        start, token = start + lead, re.sub(r'\W+$', '', token[lead:])
        for cut in range(len(token), 1, -1):
            stem, rest = token[:cut], token[cut:]
            if ((stem in higher or stem in species or re.fullmatch(r'[가-힣]+목', stem)) and _NAME_TAIL.fullmatch(re.sub(r'\W', '', rest))
                    and not re.match(r'\s*열매', question[start + cut:])):   # 마가목 열매: a plant
                found.append((start, start + cut))
                break
    return found


def _taxa_kept(question, names):
    """No named taxon is dropped: each one lies inside the plan's taxon or species span."""
    return all(any(n.start <= s and e <= n.end for n in names) for s, e in _named_taxa(question))


def _taxon_span(question, text):
    """The taxon's span; a rank word copied after a scientific name (Corvus 속) is left out of the name."""
    span = _span(question, text)
    if span is not None:
        bare = re.fullmatch(r'([A-Z][a-z]+(?: [a-z]+){0,2})\s*(?:속|과|목|종|아종)', span.text)
        if bare:
            span = Span(bare.group(1), span.start, span.start + len(bare.group(1)))
    return span


def _known_words_agree(question, pairs, names, relation_span=None):
    """Every known vocabulary word lies in a name span or in a condition span whose (trait, value) it can mean."""
    taken = []
    for pattern, meanings in _KNOWN:
        for match in pattern.finditer(question):
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


def _build(question, raw):
    kind = raw.get('kind')
    if kind not in KINDS:
        raise SemanticIntentError('unknown kind')
    unresolved = raw.get('unresolved', [])
    if not isinstance(unresolved, list) or not all(isinstance(t, str) for t in unresolved) \
            or not isinstance(raw.get('unknown_relation', False), bool):
        raise SemanticIntentError('bad unresolved/unknown_relation')
    taxon, species, relation = _text(raw, 'taxon'), _text(raw, 'species'), _text(raw, 'relation_text')
    pairs = _conditions(question, raw)
    if unresolved or raw.get('unknown_relation'):
        residual = tuple(s for s in (span_of(question, t.strip()) for t in unresolved) if s is not None)
        return GraphIntent(None, residual=residual, ambiguity=() if residual else ('other',), source=SOURCE)
    if kind == 'none':
        if taxon is not None or species is not None or relation is not None or pairs:
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
        name, phrase = _span(question, species), _span(question, relation)
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
    if not all(_supported(c, span) for c, span in pairs) or not _taxa_kept(question, names):
        raise _Reject('condition without its own support, or a named taxon left out')
    if not _numbers_agree(question, pairs) or not _known_words_agree(
            question, pairs, names, phrase if kind == 'shared_diet' else None):
        raise _Reject('numbers or known words disagree')
    if validate_intent(question, intent):
        raise _Reject('invalid intent')
    return intent


def interpret(question, provider, examples=()):
    """GraphIntent (source='semantic') from ``provider(question, examples, CONTRACT)``; fail-closed.

    Raises SemanticIntentError when the provider fails or its output is not the contract's object.
    """
    try:
        raw = provider(question, list(examples), CONTRACT)
    except Exception as error:
        raise SemanticIntentError(f'provider failed ({type(error).__name__})') from error
    if not isinstance(raw, dict) or 'kind' not in raw or not set(raw) <= _KEYS:
        raise SemanticIntentError('provider output is not the contract object')
    try:
        return _build(question, raw)
    except _Reject:
        return _HOLD


def _examples(question, retrieve):
    if retrieve is None:
        return []
    try:
        found = retrieve(question, limit=5)
        return [{'question': r['question'], 'kind': r['kind'],
                 **({'intent': _EXAMPLE_INTENTS[r['question']]} if r['question'] in _EXAMPLE_INTENTS else {})}
                for r in found or () if isinstance(r, dict) and isinstance(r.get('question'), str)
                and isinstance(r.get('kind'), str)]
    except Exception:
        return []


def graph_intent_handler(question, *, provider, retrieve=None):
    """The extractor's intent when it decides the question, else the verified semantic intent."""
    lexical = extract_graph_intent(question)
    if not isinstance(question, str) or not question.strip() or _lexical_decides(question, lexical):
        return lexical
    proposed = interpret(question, provider, _examples(question, retrieve))
    if execution_gate(question, proposed) == 'not_graph' and lexical.kind is not None:
        return lexical
    return proposed
