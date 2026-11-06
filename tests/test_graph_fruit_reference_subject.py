"""A plant-species comparison keeps the source-backed bird subject and every restriction."""
import unittest

from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate


class FruitReferenceSubjectTests(unittest.TestCase):
    def test_known_eater_is_reference_across_plant_comparison_wording(self):
        for bird in ('꼬까울새', '청둥오리', '직박구리'):
            for comparison in ('식물 종까지 동일한', '식물 종이 같은', '식물 종도 똑같은', '같은 식물 종의'):
                q = f'다른 새 가운데 {bird}가 먹는 것과 {comparison} 열매를 먹는 종을 알려줘.'
                intent = extract_graph_intent(q)
                with self.subTest(bird=bird, comparison=comparison):
                    self.assertEqual('insufficient_data', execution_gate(q, intent))
                    self.assertEqual([bird], [span.text for span in intent.species])
                    self.assertIn('열매', intent.specific_plant.text)
                    self.assertIsNone(intent.diet)

    def test_other_restrictions_and_unverified_subjects_remain_visible(self):
        stem = '꼬까울새가 먹는 것과 식물 종까지 동일한 열매를 먹는 종을 알려줘.'
        for extra in (' 밤에만 활동하는 종.', ' 열매를 먹지 않는 종.', ' 체중 100g 이상인 종.', ' 직박구리는 제외해.'):
            q = stem + extra
            intent = extract_graph_intent(q)
            with self.subTest(extra=extra):
                self.assertEqual('clarify', execution_gate(q, intent))
                self.assertTrue(intent.residual or intent.negation or intent.ambiguity)
        for noun in ('식물', '동물', '종까지', '아무이름'):
            q = f'{noun}가 먹는 것과 식물 종까지 동일한 열매를 먹는 새는?'
            intent = extract_graph_intent(q)
            with self.subTest(noun=noun):
                self.assertEqual('clarify', execution_gate(q, intent))
                self.assertNotIn(noun, [span.text for span in intent.species])
