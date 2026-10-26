"""Independent exposed-family regression and compositional counterexamples; local only."""
import unittest
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate
class FamilyRoutingGuards(unittest.TestCase):
 def test_explicit_trait_negation_remains_a_graph_constraint(self):
  for q in ('제비과 자료에서 먹이 생태 범주가 Invertivore가 아닌 종을 조회해 줘.', 'Corvus에서 영양 단계가 Omnivore가 아닌 새를 찾아줘.'):
   i=e.extract_graph_intent(q)
   with self.subTest(q=q):self.assertTrue(i.negation);self.assertEqual('clarify',execution_gate(q,i))
 def test_explicit_plant_identity_order_variations_keep_reference(self):
  for q,name in [('큰까마귀가 먹는 열매와 식물의 종까지 똑같은 열매를 먹는 다른 종을 찾아줘.','큰까마귀'),('먹는 열매의 식물 종이 큰까마귀가 먹는 것과 정확히 같은 다른 새는 무엇이야?','큰까마귀'),('Parus major가 먹는 열매와 식물의 종까지 정확히 일치하는 열매를 먹으며 숲에 사는 다른 새를 알려줘.','Parus major')]:
   i=e.extract_graph_intent(q)
   with self.subTest(q=q):self.assertEqual('insufficient_data',execution_gate(q,i));self.assertEqual([name],[x.text for x in i.species])
 def test_unrelated_identity_or_incomplete_or_negative_plants_never_form_relation(self):
  for q in ('큰까마귀와 서식지가 같고 식물 종의 열매를 먹는 새를 알려줘.', '큰까마귀와 먹이 생태 범주가 같고 식물 종의 열매를 먹는 새를 알려줘.', '큰까마귀가 먹는 열매와 식물의 종이 다른 열매를 먹는 새를 알려줘.', '큰까마귀가 먹는 열매와 식물의 종까지 같지 않은 열매를 먹는 새를 알려줘.', '큰까마귀가 먹는 열매와 식물의 종까지 똑같은 열매를 먹는 새 중 몸무게 200g 이상만 알려줘.', '큰까마귀가 먹는 열매와 식물의 종까지 똑같은 열매를 먹는 새 중 겨울에만 사는 종을 알려줘.', '큰까마귀와 청둥오리가 먹는 것과 식물 종까지 똑같은 열매를 먹는 새를 알려줘.'):
   i=e.extract_graph_intent(q)
   with self.subTest(q=q):self.assertNotIn(execution_gate(q,i),('answer','insufficient_data'))
