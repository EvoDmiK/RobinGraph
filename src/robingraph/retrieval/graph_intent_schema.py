"""Structured intent contract for the fixed graph question kinds (RG-205; taxon_traits added later).

A GraphIntent records what a question asks, with entity-like slots kept as
spans of the original text. Anything the fixed templates cannot express is
kept, never dropped: negations, leftover conditions (``residual``), asks the
data cannot support (``unsupported``) and ambiguities all block execution.
Execution only ever goes through ``to_graph_question`` into the existing
fixed-Cypher handlers; no Cypher is built here.

``unsupported`` and ``not_graph`` are evaluation labels. The API keeps its
existing clarify/abstain contract.
"""
from dataclasses import dataclass
import re

from .graph_questions import FOOD_GAPS, GRAPH_QUESTION_KINDS, HABITATS, GraphQuestion, TraitCondition, checked_conditions

SCHEMA_VERSION = 'rg205-v1'
KINDS = GRAPH_QUESTION_KINDS
DISPOSITIONS = ('answer', 'insufficient_data', 'clarify', 'unsupported', 'not_graph')
DIETS = ('fruit_share', 'tree_fruit_share', 'frugivore', 'niche')
FRUIT_DIETS = ('fruit_share', 'tree_fruit_share', 'frugivore')
HABITAT_CODES = tuple(sorted(set(HABITATS.values()))) + ('target',)
RELATIONS = ('same', 'different')
SCOPES = ('korea',)
UNSUPPORTED = ('co_occurrence', 'evolutionary_distance', 'predation', 'ranking', 'other')
AMBIGUITIES = ('kind_tie', 'name_ambiguous', 'relation_unclear', 'group_unresolved', 'other')
# Gold "expected" format (contract draft, fixed for the root-written holdout):
#   kind, disposition: required. Lists default to [], other fields to null when omitted.
#   species/negation/residual: [surface, ...]; group/specific_plant: surface;
#   rank: surface (or ["order", surface]); diet/habitat/relation/scope: code (or [code, surface]);
#   unsupported/ambiguity: [code, ...]. Every surface must occur in the question.
EXPECTED_FIELDS = ('kind', 'disposition', 'species', 'rank', 'group', 'diet', 'habitat', 'relation', 'scope',
                   'specific_plant', 'negation', 'residual', 'unsupported', 'ambiguity')
# Optional, so the fixed RG-205 gold files stay valid unchanged:
#   conditions (taxon_traits): [{trait_name, op, value?, threshold?, unit?, qualifier?, surface}, ...].
OPTIONAL_FIELDS = ('conditions',)
_LIST_FIELDS = ('species', 'negation', 'residual', 'unsupported', 'ambiguity', 'conditions')

# kind -> (required slot values, slots that may also be set). Anything else set blocks execution.
_RULES = {
    'common_taxonomy': ({'species': 2}, set()),
    'same_genus': ({'species': 1, 'relation': 'same'}, set()),
    'korea_same_genus': ({'species': 1, 'relation': 'same', 'scope': 'korea'}, {'group'}),
    'order_fruit': ({'rank': True, 'diet': FRUIT_DIETS}, set()),
    'habitat_shared_diet': ({'species': 1, 'habitat': 'code', 'diet': ('niche',), 'relation': 'same'}, set()),
    'habitat_different_diet': ({'species': 1, 'habitat': 'target', 'diet': ('niche',), 'relation': 'different'},
                               set()),
    # Same AVONET trophic_niche as one species, no habitat (any habitat slot blocks execution).
    'shared_diet': ({'species': 1, 'diet': ('niche',), 'relation': 'same'}, set()),
    # A taxon at any rank (verified against the active data at execution), or none for the whole catalog.
    'taxon_traits': ({'conditions': True}, {'rank'}),
}  # specific_fruit never reaches these rules: it is always insufficient_data.
_SLOTS = ('species', 'rank', 'group', 'diet', 'habitat', 'relation', 'scope', 'specific_plant', 'conditions')
# Kinds that are one family of meaning; a router candidate in the same family is not a kind conflict.
KIND_FAMILIES = (frozenset(('order_fruit', 'taxon_traits')),)
SCALAR_SLOTS = ('diet', 'habitat', 'relation', 'scope')
TRUSTED_SOURCES = ('regex_fullmatch', 'gold')


@dataclass(frozen=True)
class Span:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class GraphIntent:
    kind: str | None
    species: tuple[Span, ...] = ()
    rank: Span | None = None             # taxon surface: an order for order_fruit, any rank for taxon_traits
    group: Span | None = None            # e.g. 오리 in "한국에 기록된 오리 중"
    diet: str | None = None
    habitat: str | None = None           # AVONET code, or 'target' (= the target's habitat)
    relation: str | None = None
    scope: str | None = None             # question-level scope only; the request scope is kept otherwise
    specific_plant: Span | None = None   # e.g. 감나무, 같은 열매
    negation: tuple[Span, ...] = ()
    residual: tuple[Span, ...] = ()
    unsupported: tuple[str, ...] = ()
    ambiguity: tuple[str, ...] = ()
    # (slot, span) original text behind diet/habitat/relation/scope. Required for every scalar slot
    # unless ``source`` is trusted: the regex parser fullmatched the whole question, or a gold record.
    evidence: tuple[tuple[str, Span], ...] = ()
    source: str | None = None
    # taxon_traits: (TraitCondition, original-text Span) pairs, all AND-combined.
    conditions: tuple[tuple[TraitCondition, Span], ...] = ()
    # Food words with no data key (FOOD_GAPS), each also counted in ``unsupported`` as 'other'.
    unsupported_food: tuple[Span, ...] = ()


def span_of(question, text, start=0):
    """First span of ``text`` in ``question`` at or after ``start``, else None."""
    if not isinstance(text, str) or not text.strip():
        return None
    index = question.find(text, start)
    return None if index < 0 else Span(text, index, index + len(text))


def validate_intent(question, intent):
    """Return error codes; an empty tuple means the intent is well formed for ``question``."""
    errors = []
    if intent.kind is not None and intent.kind not in KINDS:
        errors.append('unknown_kind')
    if not isinstance(question, str):
        return ('question_missing',)
    spans = list(intent.species) + list(intent.negation) + list(intent.residual)
    spans += [s for s in (intent.rank, intent.group, intent.specific_plant) if s is not None]
    if not isinstance(intent.unsupported_food, tuple) or (intent.unsupported_food and 'other' not in intent.unsupported):
        errors.append('bad_unsupported_food')
    else:
        spans += list(intent.unsupported_food)
        if any(isinstance(s, Span) and s.text not in FOOD_GAPS for s in intent.unsupported_food):
            errors.append('bad_unsupported_food')
    if not isinstance(intent.conditions, tuple) or any(
            not (isinstance(c, tuple) and len(c) == 2 and isinstance(c[0], TraitCondition)) for c in intent.conditions):
        errors.append('bad_condition')
    else:
        spans += [span for _, span in intent.conditions]
        try:
            if intent.conditions:
                checked_conditions(tuple(c for c, _ in intent.conditions))
        except ValueError:
            errors.append('bad_condition')
    if any(not (isinstance(e, tuple) and len(e) == 2 and e[0] in SCALAR_SLOTS) for e in intent.evidence):
        errors.append('bad_evidence')
    else:
        spans += [span for _, span in intent.evidence]
    if not all(_span_ok(question, s) for s in spans):
        errors.append('span_mismatch')
    if intent.source not in TRUSTED_SOURCES and any(
            getattr(intent, slot) is not None and slot not in {name for name, _ in intent.evidence}
            for slot in SCALAR_SLOTS):
        errors.append('scalar_without_evidence')
    if intent.rank is not None and not re.fullmatch(r'[가-힣]+|[A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){0,2}', intent.rank.text.strip()):
        errors.append('bad_taxon')   # the rank itself is only decided by the active taxonomy data
    for value, allowed, code in ((intent.diet, DIETS, 'unknown_diet'), (intent.habitat, HABITAT_CODES, 'unknown_habitat'),
                                 (intent.relation, RELATIONS, 'unknown_relation'), (intent.scope, SCOPES, 'unknown_scope')):
        if value is not None and value not in allowed:
            errors.append(code)
    if not set(intent.unsupported) <= set(UNSUPPORTED):
        errors.append('unknown_unsupported')
    if not set(intent.ambiguity) <= set(AMBIGUITIES):
        errors.append('unknown_ambiguity')
    return tuple(errors)


def _span_ok(question, span):
    if not isinstance(span, Span) or not isinstance(span.text, str) or not span.text.strip():
        return False
    offsets = (span.start, span.end)
    if any(type(value) is not int for value in offsets):  # bool is not an offset
        return False
    return 0 <= span.start < span.end <= len(question) and question[span.start:span.end] == span.text


def _slot_set(intent, slot):
    value = getattr(intent, slot)
    return bool(value) if slot in ('species', 'conditions') else value is not None


def _required_ok(intent, slot, need):
    value = getattr(intent, slot)
    if slot == 'species':
        return len(value) == need
    if slot == 'conditions':
        return len(value) >= 1
    if need is True:
        return value is not None
    if need == 'code':
        return value is not None and value != 'target'
    return value in need if isinstance(need, tuple) else value == need


def execution_gate(question, intent):
    """Fail-closed disposition for an intent of ``question``; only 'answer' may run a fixed template."""
    if not isinstance(intent, GraphIntent) or validate_intent(question, intent):
        return 'clarify'
    if intent.unsupported:
        return 'unsupported'
    # A negation or leftover condition is never dropped, even on a specific-plant question.
    if intent.negation or intent.residual or intent.ambiguity:
        return 'clarify'
    if intent.specific_plant is not None or intent.kind == 'specific_fruit':
        return 'insufficient_data'
    if intent.kind is None:
        return 'not_graph'
    required, optional = _RULES[intent.kind]
    if not all(_required_ok(intent, slot, need) for slot, need in required.items()):
        return 'clarify'
    if any(_slot_set(intent, slot) for slot in _SLOTS if slot not in required and slot not in optional):
        return 'clarify'
    return 'answer'


def unsupported_food(question, intent):
    """Food spans when a food with no data key is the only thing blocking ``question``, else ().

    Any negation, residual, ambiguity, specific plant or another unsupported relation keeps the clarify."""
    if (not isinstance(intent, GraphIntent) or validate_intent(question, intent) or intent.unsupported != ('other',)
            or not intent.unsupported_food or intent.negation or intent.residual or intent.ambiguity
            or intent.specific_plant is not None):
        return ()
    return intent.unsupported_food


def to_graph_question(question, intent):
    """GraphQuestion for the existing handlers, only when the gate allows it, else None.

    specific_fruit is returned only for insufficient_data: its handler answers without a DB call.
    """
    disposition = execution_gate(question, intent)
    if not (disposition == 'answer' or (disposition == 'insufficient_data' and intent.kind == 'specific_fruit')):
        return None
    return GraphQuestion(
        intent.kind, tuple(s.text.strip() for s in intent.species),
        intent.rank.text.strip() if intent.rank else None,
        intent.habitat if intent.habitat not in (None, 'target') else None,
        intent.diet if intent.kind == 'order_fruit' else None,
        intent.group.text.strip() if intent.group else None,
        tuple(c for c, _ in intent.conditions))


def from_graph_question(question, parsed):
    """Baseline adapter: the intent the current regex parser implies (it has no negation/residual)."""
    if parsed is None:
        return GraphIntent(None)
    species, start = [], 0
    for name in parsed.names:
        span = span_of(question, name, start) or span_of(question, name)
        species.append(span or Span(name, -1, -1))
        start = span.end if span else start
    kind = parsed.kind
    habitat = parsed.habitat
    diet = parsed.criterion
    relation = None
    if kind in ('same_genus', 'korea_same_genus', 'habitat_shared_diet'):
        relation = 'same'
    if kind in ('habitat_shared_diet', 'habitat_different_diet'):
        diet = 'niche'
    if kind == 'habitat_different_diet':
        habitat, relation = 'target', 'different'
    plant = None
    if kind == 'specific_fruit':
        plant = (_plant_span(question) or span_of(question, '같은 열매'))
    return GraphIntent(
        kind, tuple(species),
        span_of(question, parsed.rank_name) if parsed.rank_name else None,
        span_of(question, parsed.group) if parsed.group else None,
        diet, habitat, relation, 'korea' if kind == 'korea_same_genus' else None, plant, source='regex_fullmatch')


def _plant_span(question):
    match = re.search(r'([가-힣]+)\s*열매', question)
    if match and match.group(1) not in ('나무', '같은', '중에서', '중', '에서'):
        return Span(match.group(1), match.start(1), match.end(1))
    return None


def intent_from_expected(question, expected):
    """Build the gold GraphIntent from a JSONL ``expected`` object; raises ValueError on a bad record."""
    if not isinstance(expected, dict) or not {'kind', 'disposition'} <= set(expected) \
            or not set(expected) <= set(EXPECTED_FIELDS + OPTIONAL_FIELDS):
        raise ValueError('expected needs kind and disposition and only the fields ' + ', '.join(EXPECTED_FIELDS))
    if expected['disposition'] not in DISPOSITIONS:
        raise ValueError('unknown disposition')
    get = lambda key: expected.get(key, [] if key in _LIST_FIELDS else None)  # noqa: E731

    def one(text):
        if text is None:
            return None
        span = span_of(question, text)
        if span is None:
            raise ValueError(f'span not in question: {text!r}')
        return span

    def many(key):
        if not isinstance(get(key), list):
            raise ValueError(f'{key} must be a list')
        return tuple(one(text) for text in get(key))

    def code(key):
        """A scalar code, or [code, surface] with the surface kept as evidence."""
        value = get(key)
        if isinstance(value, list):
            if len(value) != 2:
                raise ValueError(f'{key} must be a code or [code, surface]')
            return value[0], ((key, one(value[1])),)
        return value, ()

    rank = get('rank')
    if isinstance(rank, list):
        if len(rank) != 2 or rank[0] != 'order':
            raise ValueError('rank must be a surface or ["order", surface]')
        rank = rank[1]
    (diet, e1), (habitat, e2), (relation, e3), (scope, e4) = (code(k) for k in SCALAR_SLOTS)
    conditions = []
    for item in get('conditions'):
        if not isinstance(item, dict) or not {'trait_name', 'op', 'surface'} <= set(item) or not set(item) <= {
                'trait_name', 'op', 'value', 'threshold', 'unit', 'qualifier', 'surface'}:
            raise ValueError('a condition needs trait_name, op and surface')
        fields = {k: v for k, v in item.items() if k != 'surface'}
        conditions.append((TraitCondition(**fields), one(item['surface'])))
    intent = GraphIntent(
        expected['kind'], many('species'), one(rank), one(get('group')), diet, habitat, relation, scope,
        one(get('specific_plant')), many('negation'), many('residual'), tuple(get('unsupported')),
        tuple(get('ambiguity')), e1 + e2 + e3 + e4, source='gold', conditions=tuple(conditions))
    errors = validate_intent(question, intent)
    if errors:
        raise ValueError(', '.join(errors))
    gate = execution_gate(question, intent)
    if gate != expected['disposition']:
        raise ValueError(f"disposition {expected['disposition']!r} disagrees with gate {gate!r}")
    return intent


def _norm(span):
    return None if span is None else re.sub(r'\s+', '', span.text)


def slot_values(intent):
    """Comparable slot values: spans by whitespace-free text, conditions by presence."""
    species = tuple(_norm(s) for s in intent.species)
    if intent.kind == 'common_taxonomy':
        species = tuple(sorted(species))
    return {'kind': intent.kind, 'species': species, 'rank': _norm(intent.rank), 'group': _norm(intent.group),
            'diet': intent.diet, 'habitat': intent.habitat, 'relation': intent.relation, 'scope': intent.scope,
            'specific_plant': _norm(intent.specific_plant), 'negation': bool(intent.negation),
            'residual': bool(intent.residual), 'unsupported': tuple(sorted(intent.unsupported)),
            'ambiguity': bool(intent.ambiguity),
            'conditions': tuple(sorted((c.trait_name, c.op, c.value or '', c.threshold or 0, c.unit or '', c.qualifier or '')
                                       for c, _ in intent.conditions))}
