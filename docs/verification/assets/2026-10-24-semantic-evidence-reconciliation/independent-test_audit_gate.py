"""Scratch candidate generator with mocked transport: audit never bypassed."""
import copy,importlib.util,json,os,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,'/tmp/rg-evidence-normalization-review')
import test_reconciliation as review
from robingraph.retrieval import semantic_graph_intent as current
from robingraph import tracing
from test_graph_diagnostics import Fake
path=Path(os.environ.get('RG_RECON_GENERATION','/tmp/rg-semantic-evidence-reconciliation/src/robingraph/generation.py'))
spec=importlib.util.spec_from_file_location('robingraph.review_generation',path);g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
def doc(p):return {'candidates':[{'content':{'parts':[{'text':json.dumps(p)}]}}]}
class Tests(unittest.TestCase):
 def test_each_repaired_plan_still_requires_independent_audit(self):
  for key in ('known_false_hold','shared_reference','numeric_restatement'):
   q,raw=review.example(key);candidate,changes=review.s.reconcile_graph_plan(q,raw)
   for verdict in ({'faithful':True,'issues':[]},{'faithful':False,'issues':[]},{'faithful':True,'issues':['missing constraint']}):
    with self.subTest(key=key,verdict=verdict),patch.object(current,'reconcile_graph_plan',review.s.reconcile_graph_plan,create=True):
     a=g.GeminiAnswerer('fake-secret',urlopen=Mock(side_effect=AssertionError('no network')));a._request=Mock(side_effect=[doc(raw),doc(verdict)])
     if verdict=={'faithful':True,'issues':[]}:
      self.assertEqual(candidate,a.propose_structured_graph_intent(q,[],review.s.CONTRACT))
     else:
      with self.assertRaises(g.GeminiAnswerError):a.propose_structured_graph_intent(q,[],review.s.CONTRACT)
     self.assertEqual(2,a._request.call_count)
     audited=json.loads(a._request.call_args_list[1].args[0].split('\n')[-1])
     self.assertEqual(q,audited['question']);self.assertEqual(raw,audited['original_proposal']);self.assertEqual(candidate,audited['proposed_plan']);self.assertEqual(changes,audited['evidence_reconciliations'])
 def test_trace_retains_raw_and_candidate_without_collector_poison(self):
  q,raw=review.example('known_false_hold');candidate,changes=review.s.reconcile_graph_plan(q,raw);fake=Fake()
  with patch.object(tracing,'_mlflow',fake),patch.object(current,'reconcile_graph_plan',review.s.reconcile_graph_plan,create=True):
   token=tracing.begin_outcome()
   try:
    a=g.GeminiAnswerer('fake-secret',urlopen=Mock());a._request=Mock(side_effect=[doc(raw),doc({'faithful':False,'issues':[]})])
    with tracing.span('request'),self.assertRaises(g.GeminiAnswerError):a.propose_structured_graph_intent(q,[],review.s.CONTRACT)
    self.assertEqual({'reason':'semantic_audit_rejected','stage':'semantic_audit'},tracing.collected_outcome())
    plan=next(x for x in fake.spans if x.name=='graph_intent.plan');repair=next(x for x in fake.spans if x.name=='graph_intent.reconciliation');audit=next(x for x in fake.spans if x.name=='graph_intent.audit')
    self.assertEqual(raw,plan.outputs);self.assertEqual(raw,repair.inputs);self.assertEqual(candidate,repair.outputs);self.assertEqual(changes,repair.attrs['evidence_reconciliations']);self.assertIs(plan.root,audit.root)
   finally:tracing.end_outcome(token)
if __name__=='__main__':unittest.main()
