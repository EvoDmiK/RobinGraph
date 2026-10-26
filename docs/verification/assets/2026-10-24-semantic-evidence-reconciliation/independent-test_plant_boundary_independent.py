"""Local deterministic regression; no provider, API, DB or new holdout scoring."""
import unittest
import importlib.util,sys
from pathlib import Path
_original_source=Path("src/robingraph/retrieval/graph_condition_extractor.py").read_text().replace("if not run or re.fullmatch(r'(?:있|없)(?:고|으며|지만|는데)', run.group()):", "if not run:")
_baseline=Path("/tmp/rg-evidence-normalization-review/extractor_before_boundary.py");_baseline.write_text(_original_source)
_spec=importlib.util.spec_from_file_location("robingraph.retrieval._independent_baseline",_baseline);_before=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=_before;_spec.loader.exec_module(_before)
from unittest.mock import Mock
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.retrieval.semantic_graph_intent import graph_intent_handler

class Boundaries(unittest.TestCase):
 def test_whole_token_only(self):
  for token in ('황금있고','황금없고','황금있으며','황금없는데','망고'):
   q=f'참새목에서 {token} 열매를 먹는 새를 알려줘.'
   i=extract_graph_intent(q)
   with self.subTest(token=token):
    self.assertEqual(i.kind,'specific_fruit')
    old=_before.extract_graph_intent(q)
    self.assertEqual(i,old) # preserve all existing behavior for non-exact whole tokens
    self.assertEqual(execution_gate(q,i),execution_gate(q,old))
    self.assertNotEqual(execution_gate(q,i),'answer')
 def test_explicit_negation_remains_guarded(self):
  q='까마귀속에서 숲이 서식지로 기록되어 있지 않고 열매도 먹는 종을 골라 줘.'
  provider=Mock(side_effect=AssertionError('negative original must not be replaced by positive plan'))
  i=graph_intent_handler(q,provider=provider)
  self.assertEqual(execution_gate(q,i),'clarify')
  self.assertTrue(i.negation)
  provider.assert_not_called()
 def test_unclaimed_connective_not_deleted(self):
  for token in ('있고','있으며','없고','없는데'):
   q=f'까마귀속에서 숲이 서식지로 기록되어 {token} 열매도 먹는 종을 골라 줘.'
   i=extract_graph_intent(q)
   with self.subTest(token=token):
    self.assertIsNone(i.specific_plant)
    self.assertEqual(execution_gate(q,i),'clarify')
    span=set(range(q.index(token),q.index(token)+len(token)))
    residual={x for s in i.residual+i.negation for x in range(s.start,s.end)}
    self.assertTrue(span <= residual)
if __name__=='__main__': unittest.main(verbosity=2)
