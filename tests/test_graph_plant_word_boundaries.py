"""Existence predicates before fruit are conditions, never inferred plant or species names."""
import unittest
from unittest.mock import Mock

from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.retrieval.semantic_graph_intent import graph_intent_handler


class PlantWordBoundaryTests(unittest.TestCase):
    def test_existence_connectives_do_not_create_fake_plant_or_species(self):
        for scope in ('참새목', '까마귀과', '까마귀속'):
            for predicate in ('기록되어', '기록돼', '표시되어', '분포해'):
                for ending in ('있고', '있으며', '있지만', '있는데', '없고', '없으며', '없지만', '없는데'):
                    q = f'{scope} 안에서 숲이 서식지로 {predicate} {ending} 열매도 먹는 종을 골라 줘.'
                    intent = extract_graph_intent(q)
                    with self.subTest(scope=scope, predicate=predicate, ending=ending):
                        self.assertNotEqual('specific_fruit', intent.kind)
                        self.assertIsNone(intent.specific_plant)
                        self.assertEqual((), intent.species)
                        self.assertEqual('clarify', execution_gate(q, intent))
                        self.assertTrue(intent.residual or intent.negation)
                        start = q.index(ending)
                        covered = {i for span in intent.residual + intent.negation for i in range(span.start, span.end)}
                        self.assertTrue(set(range(start, start + len(ending))) <= covered)

    def test_original_failure_can_reach_semantic_interpreter_with_all_conditions(self):
        q = '까마귀속 안에서 숲이 서식지로 기록되어 있고 열매도 먹는 종을 골라 줘.'
        provider = Mock(return_value={'kind': 'taxon_traits', 'taxon': '까마귀속', 'conditions': [
            {'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'surface': '숲이 서식지로 기록되어 있고'},
            {'trait_name': 'diet_distribution', 'op': 'share_gt', 'value': 'fruit', 'threshold': 0,
             'surface': '열매도 먹는'}], 'unresolved': [], 'unknown_relation': False})
        intent = graph_intent_handler(q, provider=provider)
        provider.assert_called_once()
        self.assertEqual('answer', execution_gate(q, intent))
        self.assertEqual('semantic', intent.source)
        self.assertEqual('까마귀속', intent.rank.text)
        self.assertEqual({'habitat', 'diet_distribution'}, {condition.trait_name for condition, _ in intent.conditions})

    def test_real_and_unknown_plant_nouns_stay_specific_and_insufficient(self):
        for plant in ('마가목', '산수유', '감나무', '은행나무', '도토리', '망고', '황금망고', '새식물'):
            q = f'참새목 중 {plant} 열매를 먹는 새는?'
            intent = extract_graph_intent(q)
            with self.subTest(plant=plant):
                self.assertEqual('specific_fruit', intent.kind)
                self.assertEqual(plant, intent.specific_plant.text)
                self.assertEqual('insufficient_data', execution_gate(q, intent))
        for q in ('직박구리와 같은 열매를 먹는 새는?', '참새목 중 도토리 먹는 새는?'):
            self.assertEqual('insufficient_data', execution_gate(q, extract_graph_intent(q)))
        q = '참새목 중 나무 열매를 먹는 새는?'
        intent = extract_graph_intent(q)
        self.assertEqual('order_fruit', intent.kind)
        self.assertEqual('answer', execution_gate(q, intent))

    def test_other_unresolved_constraints_and_negation_remain_held(self):
        for extra in ('단 밤에만 활동하는 종.', '열매를 먹지 않는 종.', '숲이 아닌 곳에서 사는 종.'):
            q = '까마귀속 안에서 기록되어 있고 열매도 먹는 종을 골라 줘. ' + extra
            intent = extract_graph_intent(q)
            with self.subTest(extra=extra):
                self.assertNotEqual('specific_fruit', intent.kind)
                self.assertEqual('clarify', execution_gate(q, intent))
                self.assertTrue(intent.residual or intent.negation)
