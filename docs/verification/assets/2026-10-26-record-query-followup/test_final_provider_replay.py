"""Same stored provider output replay on before/after code. No actual provider calls."""
import unittest,json,copy
from pathlib import Path
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
class FinalProviderReplay(unittest.TestCase):
 def test_three_stored_failures_hold_under_same_contract(self):
  for row in json.loads(Path('/tmp/rg-four-qa-20261026/final-three-provider-rows.json').read_text()):
   q=row['request']['question'];p=next(x['outputs']for x in row['diagnostic_spans']if x['name']=='graph_intent.plan')
   with self.subTest(case=row['case']):
    c,changes=s.reconcile_graph_plan(q,copy.deepcopy(p));self.assertEqual(p,c);self.assertFalse(changes)
    if row['case']=='V2-11C':self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:c)))
    else:
     audit=next(x['outputs']for x in row['diagnostic_spans']if x['name']=='graph_intent.audit')
     def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
     a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(p),doc(audit)])
     with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):a.propose_structured_graph_intent(q,[],s.CONTRACT)
