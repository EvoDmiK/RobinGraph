"""Feedback-exposed punctuation guard test; deterministic mocked plan only."""
import copy,unittest
from test_request_self_exclusion_independent import s, QUESTION, RAW
from robingraph.retrieval.graph_intent_schema import execution_gate
class PunctuationReview(unittest.TestCase):
 def test_terminal_punctuation_is_only_a_suffix(self):
  for ending in ('궁금해.','궁금해!','궁금해?','궁금해?!','궁금해...'):
   q=QUESTION.rstrip('.!?').removesuffix('궁금해')+ending;p={**copy.deepcopy(RAW),'unresolved':[ending]}
   candidate,proof=s.reconcile_graph_plan(q,p)
   with self.subTest(ending=ending):
    self.assertTrue(proof);self.assertEqual(candidate['unresolved'],[])
    self.assertEqual(execution_gate(q,s._build(q,candidate)),'answer')
 def test_extra_condition_internal_punctuation_or_mismatched_original_never_removed(self):
  base=QUESTION.rstrip('.!?').removesuffix('궁금해')
  for original,unresolved in [('궁금해. 몸무게가 100g 초과인 새.','궁금해.'),('궁금해. 밤에만 사는 새.','궁금해. 밤에만 사는 새.'),('궁금해하지만.','궁금해.'),('안궁금해.','궁금해.'),('궁금해?','궁금해.'),('궁금해. 궁금해.','궁금해.'),('숲에 사는 새가 궁금해.','숲에 사는 새가 궁금해.')]:
   q=base+original;p={**copy.deepcopy(RAW),'unresolved':[unresolved]}
   with self.subTest(original=original):self.assertEqual(s.reconcile_graph_plan(q,p),(p,[]))
if __name__=='__main__':unittest.main(verbosity=2)
