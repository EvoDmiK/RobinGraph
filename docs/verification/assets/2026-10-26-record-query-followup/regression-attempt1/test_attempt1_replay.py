"""Stored proposal replay only; not new model/API measurements."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
class Replay(unittest.TestCase):
 def test_stored_relation_bad_shape_holds(self):
  row=json.loads(Path('/tmp/rg-four-qa-20261026/V2-12B.json').read_text());q=row['request']['question']
  p=next(x['outputs']for x in row['diagnostic_spans']if x['name']=='graph_intent.plan')
  c,changes=s.reconcile_graph_plan(q,copy.deepcopy(p));self.assertEqual(p,c);self.assertFalse(changes)
  self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:c)))
 def test_stored_audit_issue_nonempty_holds(self):
  row=json.loads(Path('/tmp/rg-four-qa-20261026/V2-07B.json').read_text());q=row['request']['question']
  def doc(p):return {'candidates':[{'content':{'parts':[{'text':json.dumps(p)}]}}]}
  plan=next(x['outputs']for x in row['diagnostic_spans']if x['name']=='graph_intent.plan');audit=next(x['outputs']for x in row['diagnostic_spans']if x['name']=='graph_intent.audit')
  a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(plan),doc(audit)])
  with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):a.propose_structured_graph_intent(q,[],s.CONTRACT)
