"""Replay one stored actual proposal/audit, without provider requests."""
import unittest,json,copy
from pathlib import Path
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
class WingReplay(unittest.TestCase):
 def test_stored_bad_unit_and_full_query_reject(self):
  r=json.loads(Path('/tmp/rg-four-qa-20261026/phase2-wing-row.json').read_text());q=r['request']['question'];p=next(x['outputs']for x in r['diagnostic_spans']if x['name']=='graph_intent.plan')
  c,changes=s.reconcile_graph_plan(q,copy.deepcopy(p));self.assertEqual(p,c);self.assertEqual([],changes)
  audit=next(x['outputs']for x in r['diagnostic_spans']if x['name']=='graph_intent.audit')
  def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
  a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(p),doc(audit)])
  with self.assertRaises(GeminiAnswerError):a.propose_structured_graph_intent(q,[],s.CONTRACT)
  # Check why a hypothetical unit-label-only correction cannot commit as a complete valid plan.
  corrected=copy.deepcopy(p);corrected['conditions'][0]['unit']='mm'
  class Trace:
   def set_attributes(self,*args):pass
  try:s._build(q,corrected,Trace())
  except Exception as error:print('corrected-unit complete-plan rejection:',type(error).__name__,str(error))
