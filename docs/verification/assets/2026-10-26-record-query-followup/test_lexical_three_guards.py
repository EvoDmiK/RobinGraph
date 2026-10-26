import unittest
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate

Q='황여새와 동일한 식물 종의 열매를 먹는 다른 조류 종을 알려 줘. 열매의 식물 종이 일치해야 해.'
R='황여새가 먹는 열매를 맺는 식물과 같은 종의 식물에서 열매를 먹는 다른 새를 찾아 줘.'
class LexicalThreeGuards(unittest.TestCase):
 def test_canonical_trait_negative_keeps_precise_hold(self):
  for trait,value in [('habitat','Marine'),('trophic_level','Omnivore'),('diet_category','Invertebrate')]:
   q=f'Alcedo 속의 종을 찾되, {trait}가 {value}인 종은 제외해 줘.';i=e.extract_graph_intent(q)
   with self.subTest(trait=trait):self.assertEqual('clarify',execution_gate(q,i));self.assertTrue(i.negation)
 def test_equivalent_plant_identity_restatement_keeps_one_reference(self):
  for q in [Q,R,Q.replace('일치해야','동일해야'),Q.replace('일치해야','같아야')]:
   i=e.extract_graph_intent(q)
   with self.subTest(q=q):self.assertEqual('insufficient_data',execution_gate(q,i));self.assertEqual(['황여새'],[s.text for s in i.species])
 def test_known_plants_and_extra_constraints_do_not_merge_into_same_identity(self):
  for q in [Q+' 사과와 포도도 먹는 종.',Q+' 망고 열매를 먹는 종.',Q+' 황여새는 제외하지 마.',Q+' 몸무게가 200g 이상인 종만.',Q+' 서울에서만 사는 종만.',Q.replace('황여새와','황여새와 직박구리와'),Q.replace('일치해야','달라야'),Q.replace('일치해야','같지 않아야'),R.replace('같은 종','다른 종'),R+' 직박구리와도 먹이가 같은 새.',R.replace('먹는 열매를','먹지 않는 열매를')]:
   with self.subTest(q=q):self.assertNotIn(execution_gate(q,e.extract_graph_intent(q)),('answer','insufficient_data'))
 def test_identity_of_other_predicate_does_not_complete_plant_subject(self):
  for q in ['황여새가 먹는 열매의 식물 종을 알려줘. 서식지가 일치해야 해.', '황여새가 먹는 열매를 맺는 식물과 같은 서식지의 식물에서 열매를 먹는 새.', '황여새의 먹이 생태 범주와 같은 종의 식물에서 열매를 먹는 새.']:
   with self.subTest(q=q):self.assertNotIn(execution_gate(q,e.extract_graph_intent(q)),('answer','insufficient_data'))
