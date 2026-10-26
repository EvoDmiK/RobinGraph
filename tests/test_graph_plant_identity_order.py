"""Plant-species identity is a data gap across word order; unrelated comparisons and constraints stay held."""
import unittest

from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate


class PlantIdentityOrderTests(unittest.TestCase):
    def test_explicit_identity_keeps_reference_and_habitat(self):
        rows = (
            ('큰까마귀가 먹는 열매와 식물의 종까지 똑같은 열매를 먹는 다른 종을 찾아줘.', '큰까마귀', None),
            ('먹는 열매의 식물 종이 큰까마귀가 먹는 것과 정확히 같은 다른 새는 무엇이야?', '큰까마귀', None),
            ('Parus major가 먹는 열매와 식물의 종까지 정확히 일치하는 열매를 먹으며 숲에 사는 다른 새를 알려줘.', 'Parus major', 'Forest'),
        )
        for q, reference, habitat in rows:
            intent = extract_graph_intent(q)
            with self.subTest(question=q):
                self.assertEqual('insufficient_data', execution_gate(q, intent))
                self.assertEqual('specific_fruit', intent.kind)
                self.assertEqual([reference], [name.text for name in intent.species])
                self.assertEqual(habitat, intent.habitat)
                self.assertIsNone(intent.diet)

    def test_unrelated_identity_negation_and_other_conditions_remain_held(self):
        stem = '먹는 열매의 식물 종이 큰까마귀가 먹는 것과 정확히 같은 다른 새는 무엇이야?'
        for extra in (' 겨울에만 사는 종.', ' 몸무게 100g 이상인 종.', ' 직박구리는 빼고.', ' 열매를 먹지 않는 종.'):
            q = stem + extra
            with self.subTest(question=q):
                self.assertEqual('clarify', execution_gate(q, extract_graph_intent(q)))
        for q in (
            stem.replace('정확히 같은', '같지 않은'),
            stem.replace('정확히 같은', '비슷한'),
            stem.replace('큰까마귀가', '큰까마귀와 직박구리가'),
            '큰까마귀와 서식지가 같은 새 중 식물 종이 다른 열매를 먹는 새는?',
            '큰까마귀와 먹이 생태 범주가 같은 새 중 식물 종이 다른 열매를 먹는 새는?',
        ):
            with self.subTest(question=q):
                self.assertEqual('clarify', execution_gate(q, extract_graph_intent(q)))

    def test_negative_trait_filter_never_falls_through_without_positive_condition(self):
        for q in (
            '제비과 자료에서 먹이 생태 범주가 Invertivore가 아닌 종을 조회해 줘.',
            '먹이 유형이 PlantSeed가 아닌 종을 알려줘.',
        ):
            intent = extract_graph_intent(q)
            with self.subTest(question=q):
                self.assertEqual('clarify', execution_gate(q, intent))
                self.assertTrue(intent.negation)
        q = '제비과 논문에서 먹이 생태 범주가 Invertivore가 아닌 종을 조회해 줘.'
        self.assertEqual('not_graph', execution_gate(q, extract_graph_intent(q)))
