import json
import unittest

from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_intent_schema import GraphIntent, execution_gate, to_graph_question
from robingraph.retrieval.graph_questions import GraphQuestion
from robingraph.retrieval.semantic_graph_intent import (CONTRACT, SEMANTIC_PROTOTYPES, SemanticIntentError,
                                                        graph_intent_handler, interpret)


def P(out):
    return lambda q, e, c: {'conditions': [], 'unresolved': [], 'unknown_relation': False, **out}


def SD(species, relation):
    return {'kind': 'shared_diet', 'species': species, 'relation_text': relation}


def TT(taxon, *conditions):
    return {'kind': 'taxon_traits', 'taxon': taxon, 'conditions': list(conditions)}


def C(trait, op, surface, value=None, threshold=None, unit=None):
    return {'trait_name': trait, 'op': op, 'value': value, 'threshold': threshold, 'unit': unit, 'surface': surface}


class UnresolvedPlanTests(unittest.TestCase):
    def test_none_cannot_erase_an_unresolved_condition_or_retained_slots(self):
        q = '참새목에서 친절한 새를 찾아줘'
        for out in ({'kind': 'none', 'unresolved': ['친절한']},
                    {'kind': 'none', 'unknown_relation': True},
                    {'kind': 'none', 'taxon': '참새목'}):
            with self.subTest(out=out):
                self.assertEqual('clarify', execution_gate(q, interpret(q, P(out))))


CASES = [
 ('까치랑 같은 먹이 생태를 가진 새를 알려줘', SD('까치','같은 먹이 생태를 가진'),'answer'),
 ('까치와 같은 먹이 범주를 공유하는 새는?', SD('까치','같은 먹이 범주를 공유하는'),'answer'),
 ('까치하고 식성이 같은 녀석들 좀 보여줄래', SD('까치','식성이 같은'),'answer'),
 ('까치랑 같은 먹이를 먹는 새', SD('까치','같은 먹이를'),'clarify'),
 ('숲에 사는 까치와 같은 먹이 생태를 가진 새', SD('까치','같은 먹이 생태를 가진'),'clarify'),
 ('숲에 사는 새들 가운데 까치랑 먹이 생태가 같은 애들', {**SD('까치','먹이 생태가 같은'),'conditions':[C('habitat','eq','숲에 사는','Forest')]},'answer'),
 ('숲에 사는 새들 가운데 까치랑 먹이 생태가 같은 애들', {**SD('까치','먹이 생태가 같은'),'conditions':[C('habitat','eq','숲에 사는','Wetland')]},'clarify'),
 ('숲에 사는 새들 가운데 까치랑 먹이 생태가 같은 애들', SD('까치','먹이 생태가 같은'),'clarify'),
 ('까치와 서식지가 같고 먹이 생태도 같은 새', SD('까치','먹이 생태도 같은'),'clarify'),
 ('까치와 같은 먹이 생태를 가진 새', {**SD('까치','같은 먹이 생태를 가진'),'conditions':[C('body_mass','num_gt','x',threshold=1,unit='g')]},'clarify'),
 ('까치와 같은 먹이 생태를 가진 겨울 새', SD('까치','같은 먹이 생태를 가진'),'not_graph'),
 ('까치와 같은 먹이 생태를 가진 새', SD('까마귀','같은 먹이 생태를 가진'),'clarify'),
 ('까마귀과에서 덩치가 1kg 넘는 녀석들 보여줄래', TT('까마귀과',C('body_mass','num_gt','덩치가 1kg 넘는',threshold=1000,unit='g')),'answer'),
 ('까마귀과에서 덩치가 1kg 넘는 녀석들 보여줄래', TT('까마귀과',C('body_mass','num_gte','덩치가 1kg 넘는',threshold=1000,unit='g')),'clarify'),
 ('까마귀과에서 덩치가 1kg 넘는 녀석들 보여줄래', TT('까마귀과',C('body_mass','num_gt','덩치가 1kg 넘는',threshold=1,unit='g')),'clarify'),
 ('까마귀과 중 체중 500g 이상이고 잡식인 새', TT('까마귀과',C('body_mass','num_gte','체중 500g 이상이고',threshold=500,unit='g')),'clarify'),
 ('까마귀과 중 체중 500g 이상이고 잡식인 새', TT('까마귀과',C('body_mass','num_gte','체중 500g 이상이고',threshold=500,unit='g'),C('trophic_level','eq','잡식인','Omnivore')),'clarify'),
 ('참새목 중 주로 땅에서 지내는 새', TT('참새목',C('primary_lifestyle','eq','주로 땅에서 지내는','Terrestrial')),'answer'),
 ('참새목 중 날개가 100~200mm인 새', TT('참새목',C('wing_length','num_gte','날개가 100~200mm인',threshold=100,unit='mm'),C('wing_length','num_lte','날개가 100~200mm인',threshold=200,unit='mm')),'answer'),
 ('참새목 중 날개가 큰 새', {'kind':'none','unresolved':['날개가 큰']},'clarify'),
 ('참새목 중 날개가 큰 새', TT('참새목',C('wing_length','num_gt','날개가 큰',threshold=100,unit='mm')),'clarify'),
 ('참새목 중 날개가 큰 새', TT('참새목'),'clarify'),
 ('참새목 중 날개가 큰 새', {**TT('참새목',C('wing_length','num_gt','날개가 큰',threshold=100,unit='mm')),'unresolved':['큰']},'clarify'),
 ('까마귀과 중 곤충을 먹지 않는 새', TT('까마귀과',C('diet_distribution','share_gt','곤충을','invertebrate',0)),'clarify'),
]


class SemanticGraphIntentTest(unittest.TestCase):
    def test_provider_proposals_are_verified_fail_closed(self):
        for question, proposal, want in CASES:
            with self.subTest(question=question, proposal=proposal):
                intent = graph_intent_handler(question, provider=P(proposal))
                self.assertEqual(want, execution_gate(question, intent))

    def test_lexical_decisions_and_vetoes_never_call_the_provider(self):
        def provider(*_):
            raise AssertionError('provider called')
        for question in ('숲에 사는 새 중 직박구리와 같은 먹이 범주를 공유하는 새는?', '까마귀과 중 곤충을 먹지 않는 새',
                         '까치와 같은 먹이 생태를 가진 겨울 새', '까치와 먹이 경쟁하는 새', '청둥오리와 같은 속의 새',
                         '한국에 기록된 새 중 까치와 같은 먹이 생태를 가진 새', '까치와 같은 먹이 생태를 가진 새 중 가장 큰 새'):
            with self.subTest(question=question):
                self.assertEqual('extractor', graph_intent_handler(question, provider=provider).source)

    def test_semantic_intents_run_only_fixed_kinds(self):
        q = '까치랑 같은 먹이 생태를 가진 새를 알려줘'
        intent = graph_intent_handler(q, provider=P(SD('까치', '같은 먹이 생태를 가진')))
        self.assertEqual(('semantic', GraphQuestion('shared_diet', ('까치',))), (intent.source, to_graph_question(q, intent)))
        q = '숲에 사는 새들 가운데 까치랑 먹이 생태가 같은 애들'
        intent = graph_intent_handler(q, provider=P({**SD('까치', '먹이 생태가 같은'),
                                                     'conditions': [C('habitat', 'eq', '숲에 사는', 'Forest')]}))
        self.assertEqual(GraphQuestion('habitat_shared_diet', ('까치',), habitat='Forest'), to_graph_question(q, intent))

    def test_provider_failure_or_malformed_output_raises(self):
        def broken(*_):
            raise TimeoutError
        for provider in (broken, lambda *_: None, lambda *_: [], lambda *_: {'kind': 'taxon_traits', 'cypher': 'MATCH'},
                         lambda *_: {'kind': 'sql'}, lambda *_: {'kind': 'taxon_traits', 'conditions': 'x'}):
            with self.assertRaises(SemanticIntentError):
                interpret('까마귀과 중 덩치 큰 새', provider)

    def test_hallucinated_names_values_and_spans_hold(self):
        q = '까마귀과에서 덩치가 1kg 넘는 녀석들 보여줄래'
        good = C('body_mass', 'num_gt', '덩치가 1kg 넘는', threshold=1000, unit='g')
        for proposal in (TT('까치과', good), TT('까마귀과', {**good, 'trait_name': 'wingspan'}),
                         TT('까마귀과', {**good, 'surface': '덩치가 2kg 넘는'}), TT('까마귀과', {**good, 'unit': 'kg'}),
                         TT('까마귀과', {**good, 'threshold': True})):
            with self.subTest(proposal=proposal):
                self.assertEqual('clarify', execution_gate(q, interpret(q, P(proposal))))

    def test_conditions_need_their_own_support_and_named_taxa_are_kept(self):
        q = '까마귀과로 범위를 잡을게. 곤충을 먹는 쪽을 골라줘.'
        food = C('diet_distribution', 'share_gt', '곤충을 먹는', 'invertebrate', 0)
        self.assertEqual('answer', execution_gate(q, interpret(q, P(TT('까마귀과', food)))))
        for proposal in (TT('까마귀과', food, C('habitat', 'eq', '골라줘', 'Forest')),          # request form, not a condition
                         TT('까마귀과', food, C('habitat', 'eq', '쪽을 골라줘', 'Forest')),
                         TT(None, food),                                                       # explicit taxon erased
                         TT('까마귀과', {**food, 'surface': '까마귀과로 범위를 잡을게. 곤충을 먹는'})):   # overlaps the taxon
            with self.subTest(proposal=proposal):
                self.assertEqual('clarify', execution_gate(q, interpret(q, P(proposal))))
        for q, taxon in (('Corvus에서 곤충을 먹는 새', None), ('참새목이랑 곤충을 먹는 새', None),
                         ('까마귀과 중 곤충을 먹는 직박구리과 새', '까마귀과')):
            with self.subTest(question=q):
                self.assertEqual('clarify', execution_gate(q, interpret(q, P(TT(taxon, C(
                    'diet_distribution', 'share_gt', '곤충을 먹는', 'invertebrate', 0))))))
        q = '까치랑 같은 먹이 생태를 가진 까마귀과 새'
        self.assertEqual('clarify', execution_gate(q, interpret(q, P(SD('까치', '같은 먹이 생태를 가진')))))

    def test_scientific_name_rank_suffix_and_relation_phrase_scope(self):
        q = 'Corvus 속에서 곤충을 먹는 새'
        intent = interpret(q, P(TT('Corvus 속', C('diet_distribution', 'share_gt', '곤충을 먹는', 'invertebrate', 0))))
        self.assertEqual('Corvus', to_graph_question(q, intent).rank_name)
        # The relation phrase may contain the species name.
        q = '까치와 같은 먹이 생태를 가진 새'
        self.assertEqual(GraphQuestion('shared_diet', ('까치',)),
                         to_graph_question(q, interpret(q, P(SD('까치', '까치와 같은 먹이 생태를 가진')))))
        q = '까치와 같은 새'
        self.assertEqual('clarify', execution_gate(q, interpret(q, P(SD('까치', '까치와')))))   # no words of its own
        # An explicit habitat stated as 서식지가 X is that condition, not a habitat relation.
        q = '서식지가 숲인 새 중 까치와 먹이 생태가 같은 새'
        intent = interpret(q, P({**SD('까치', '먹이 생태가 같은'), 'conditions': [C('habitat', 'eq', '서식지가 숲인', 'Forest')]}))
        self.assertEqual(GraphQuestion('habitat_shared_diet', ('까치',), habitat='Forest'), to_graph_question(q, intent))
        q = '까치와 서식지가 같고 먹이 생태도 같은 새'
        self.assertEqual('clarify', execution_gate(q, interpret(q, P(SD('까치', '먹이 생태도 같은')))))

    def test_taxon_traits_scope_is_the_taxon_slot_at_every_rank(self):
        q = 'Anas platyrhynchos 종의 체중이 1kg 이상인지'
        cond = C('body_mass', 'num_gte', '체중이 1kg 이상인지', threshold=1000, unit='g')
        for proposal in (TT('Anas platyrhynchos', cond), {'kind': 'taxon_traits', 'species': 'Anas platyrhynchos',
                                                          'conditions': [cond]}):
            with self.subTest(proposal=proposal):
                self.assertEqual('Anas platyrhynchos', to_graph_question(q, interpret(q, P(proposal))).rank_name)
        self.assertIn('taxon_traits', CONTRACT['schema']['properties']['species']['description'])

    def test_named_supported_source_is_scope_and_restricts_conditions(self):
        q = 'AVONET 기준으로 까마귀과 중 숲에 사는 새'
        habitat = C('habitat', 'eq', '숲에 사는', 'Forest')
        self.assertEqual('answer', execution_gate(q, graph_intent_handler(q, provider=P(TT('까마귀과', habitat)))))
        q = 'AVONET 자료에서 까마귀과 중 곤충을 먹는 새'   # an EltonTraits field under a named AVONET scope
        self.assertEqual('clarify', execution_gate(q, graph_intent_handler(q, provider=P(TT('까마귀과', C(
            'diet_distribution', 'share_gt', '곤충을 먹는', 'invertebrate', 0))))))

        def provider(*_):
            raise AssertionError('provider called')
        self.assertEqual('extractor', graph_intent_handler('논문 기준 까마귀과 중 숲에 사는 새', provider=provider).source)
        self.assertEqual(sorted(CONTRACT['vocabulary']['sources']), ['AVONET', 'EltonTraits'])
        for q in ('EltonTraits 자료로 까치와 먹이 생태가 같은 새', 'AVONET과 EltonTraits로 까치와 먹이 생태가 같은 새'):
            with self.subTest(question=q):
                self.assertEqual('clarify', execution_gate(q, interpret(q, P(SD('까치', '먹이 생태가 같은')))))
        q = 'AVONET 기준 까치와 먹이 생태가 같은 새'
        self.assertEqual('answer', execution_gate(q, interpret(q, P(SD('까치', '먹이 생태가 같은')))))

    def test_share_above_zero_is_checked_apart_from_measurements(self):
        insects = lambda surface: TT('까마귀과', C('diet_distribution', 'share_gt', surface, 'invertebrate', 0))  # noqa: E731
        for q, surface, want in (('까마귀과 중 곤충을 먹는 새', '곤충을 먹는', 'answer'),
                                 ('까마귀과 중 곤충 비율이 0%보다 많은 새', '곤충 비율이 0%보다 많은', 'answer'),
                                 ('까마귀과 중 곤충 비율이 0 초과인 새', '곤충 비율이 0 초과인', 'answer'),
                                 ('까마귀과 중 곤충 비율이 50% 이상인 새', '곤충 비율이 50% 이상인', 'clarify'),
                                 ('까마귀과 중 곤충 비율이 0% 이상인 새', '곤충 비율이 0% 이상인', 'clarify'),
                                 ('까마귀과 중 곤충을 먹는 새 3종', '곤충을 먹는', 'clarify')):
            with self.subTest(question=q):
                self.assertEqual(want, execution_gate(q, interpret(q, P(insects(surface)))))

    def test_veto_look_alikes_are_blanked_but_vetoes_stay(self):
        def provider(*_):
            raise AssertionError('provider called')
        for q in ('백로과 중 물고기를 포식하는 새', '곤충 없이 사는 새', '까마귀과 중 곤충을 먹지 않는 새'):
            with self.subTest(question=q):
                self.assertEqual('extractor', graph_intent_handler(q, provider=provider).source)
        q = '백로과 중 수생동물 포식인 새'   # the canonical trophic_niche value, not a predation relation
        cond = C('trophic_niche', 'eq', '수생동물 포식인', 'Aquatic predator')
        self.assertEqual('answer', execution_gate(q, graph_intent_handler(q, provider=P(TT('백로과', cond)))))
        cond = C('diet_distribution', 'share_gt', '곤충을 먹는', 'invertebrate', 0)
        for q in ('분류 제한 없이 곤충을 먹는 새', '목·과·속 구분 없이 곤충을 먹는 새', '분류군 상관없이 곤충을 먹는 새', '서식지 제한 없이 곤충을 먹는 새'):
            with self.subTest(question=q):
                self.assertEqual('answer', execution_gate(q, graph_intent_handler(q, provider=P(TT(None, cond)))))
        for q in ('먹이 조건 없이 곤충을 먹는 새', '관계없이 곤충을 먹는 새'):
            with self.subTest(question=q):   # Ambiguous or biological negation remains blocked; explicit dimensions are checked above.
                self.assertEqual('extractor', graph_intent_handler(q, provider=provider).source)

    def test_real_difference_and_predation_vetoes_remain(self):
        for q in ('까치와 먹이는 다른 새', '백로과 중 수생동물 포식자를 피하는 새'):
            with self.subTest(question=q):
                provider = lambda *_: (_ for _ in ()).throw(AssertionError('provider must not run'))
                graph_intent_handler(q, provider=provider)

    def test_catalog_names_need_a_particle_boundary(self):
        self.assertEqual(['까마귀과'], [q[a:b] for q in ['까마귀과 중 곤충을 먹는 새 모아줘']
                                    for a, b in sgi._named_taxa(q)])
        self.assertEqual(['참새목', '까마귀과'], [q[a:b] for q in ['참새목에서는 "까마귀과"처럼']
                                                  for a, b in sgi._named_taxa(q)])

    def test_contract_and_examples(self):
        self.assertEqual({'version', 'instructions', 'schema', 'vocabulary'}, set(CONTRACT))
        json.dumps(CONTRACT, ensure_ascii=False)
        self.assertEqual(15, len(CONTRACT['vocabulary']['traits']))
        self.assertEqual({'taxon_traits', 'shared_diet'}, {kind for kind, _ in SEMANTIC_PROTOTYPES})
        seen = []
        retrieved = [{'kind': 'shared_diet', 'question': SEMANTIC_PROTOTYPES[0][1], 'score': 0.9},
                     {'kind': 'same_genus', 'question': '청둥오리와 같은 속의 새', 'score': 0.5}]

        def provider(question, examples, contract):
            seen.append(examples)
            return {'kind': 'none', 'conditions': [], 'unresolved': [], 'unknown_relation': False}
        graph_intent_handler('까치 좋아하는 새', provider=provider, retrieve=lambda q, limit: retrieved)
        self.assertIn('intent', seen[0][0])
        self.assertEqual(1, len(seen[0]))  # unreviewed retrieval rows never reach the provider
        graph_intent_handler('까치 좋아하는 새', provider=provider, retrieve=lambda q, limit: 1 / 0)
        self.assertEqual([], seen[1])
        for question, intent in sgi._EXAMPLE_INTENTS.items():
            with self.subTest(example=question):
                full = {'conditions': [], 'unresolved': [], 'unknown_relation': False, **intent}
                self.assertEqual('answer', execution_gate(question, interpret(question, lambda *_: full)))


if __name__ == '__main__':
    unittest.main()
