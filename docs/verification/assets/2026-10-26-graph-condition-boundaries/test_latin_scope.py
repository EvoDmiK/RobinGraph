"""Local scope preservation; lexical acceptance is not taxonomic existence verification."""
import unittest
from unittest.mock import Mock
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval import semantic_graph_intent as semantic
from robingraph.retrieval.graph_intent_schema import execution_gate,to_graph_question
from robingraph.retrieval.graph_questions import graph_question_answer

class LatinScopeGuards(unittest.TestCase):
 def test_full_binomial_trinomial_and_hyphenated_names_are_preserved(self):
  for name in ('Anas platyrhynchos','Anas platyrhynchos platyrhynchos','Corvus corone','Turdus iliacus coburni','Corvus example-name example-sub'):
   q=f'{name}와 같은 식물 종의 열매를 먹는 다른 새는?'
   intent=e.extract_graph_intent(q)
   with self.subTest(name=name):
    self.assertEqual('insufficient_data',execution_gate(q,intent));self.assertEqual([name],[s.text for s in intent.species]);self.assertTrue(e._valid_name(name))

 def test_actual_graph_plan_retains_subspecies_scope(self):
  name='Anas platyrhynchos platyrhynchos'
  for ending in ('와 같은 속의 새는?','와 같은 먹이 생태 범주를 가진 새는?'):
   q=name+ending;intent=e.extract_graph_intent(q)
   with self.subTest(ending=ending):
    self.assertEqual([name],[x.text for x in intent.species])
    if '먹이' in ending:
     raw={'kind':'shared_diet','species':name,'relation_text':'같은 먹이 생태 범주를 가진','conditions':[],'unresolved':[],'unknown_relation':False}
     intent=semantic.interpret(q,lambda *_:raw)
    self.assertEqual('answer',execution_gate(q,intent));self.assertEqual((name,),to_graph_question(q,intent).names)

 def test_genus_four_words_and_additional_conditions_are_not_silently_dropped(self):
  for q in ('Anas와 같은 식물 종의 열매를 먹는 다른 새는?',
            'Anas platyrhynchos platyrhynchos extra와 같은 식물 종의 열매를 먹는 다른 새는?',
            'Anas platyrhynchos platyrhynchos와 같은 식물 종의 열매를 먹지 않는 다른 새는?',
            'Anas platyrhynchos platyrhynchos와 같은 식물 종의 열매를 먹는 다른 겨울 새는?'):
   with self.subTest(q=q):self.assertEqual('clarify',execution_gate(q,e.extract_graph_intent(q)))

 def test_specific_food_gap_does_not_claim_taxon_identity(self):
  q='Invented example와 같은 식물 종의 열매를 먹는 다른 새는?';intent=e.extract_graph_intent(q)
  self.assertEqual('insufficient_data',execution_gate(q,intent))
  repository=Mock();resolve=Mock();payload=graph_question_answer(repository,resolve,to_graph_question(q,intent))
  self.assertEqual('insufficient_data',payload['status']);self.assertFalse(payload.get('taxon'));self.assertFalse(payload.get('items'));resolve.assert_not_called();repository.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
