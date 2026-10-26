"""First actual final provider responses replayed without live calls."""
import unittest,json,copy
from pathlib import Path
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
class FinalReplay(unittest.TestCase):
 def test_remaining_proposals_fail_closed(self):
  for r in json.loads(Path('/tmp/rg-four-qa-20261026/v6-final-provider-rows.json').read_text()):
   p=next(x['outputs']for x in r['diagnostic_spans']if x['name']=='graph_intent.plan');q=r['request']['question'];c,changes=s.reconcile_graph_plan(q,copy.deepcopy(p))
   with self.subTest(case=r['case']):
    self.assertEqual(p,c);self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:c)))
