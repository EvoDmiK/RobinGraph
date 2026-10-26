"""Recorded provider response replay, no model calls; print before/after F04B disposition."""
import unittest,json,copy
from pathlib import Path
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
class Phase2FinalReplay(unittest.TestCase):
 def test_four_stored_provider_outputs(self):
  for r in json.loads(Path('/tmp/rg-four-qa-20261026/phase2-final-provider-rows.json').read_text()):
   q=r['request']['question'];p=next(x['outputs']for x in r['diagnostic_spans']if x['name']=='graph_intent.plan');audit=next(x['outputs']for x in r['diagnostic_spans']if x['name']=='graph_intent.audit')
   c,changes=s.reconcile_graph_plan(q,copy.deepcopy(p));print(r['case'],'changes',changes)
   with self.subTest(case=r['case']):
    if r['case']in ('V2-07A','V2-11B'):
     def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
     a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(p),doc(audit)])
     with self.assertRaises(GeminiAnswerError):a.propose_structured_graph_intent(q,[],s.CONTRACT)
     print(r['case'],'audit_rejected')
    else:
     gate=execution_gate(q,s.interpret(q,lambda *_:c));print(r['case'],'local_gate',gate)
     if r['case']=='V2-10B':self.assertEqual('clarify',gate)
