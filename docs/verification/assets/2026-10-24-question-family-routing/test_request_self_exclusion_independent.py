"""Feedback-exposed guard regressions. Reads saved evidence; no live calls or root edits."""
import copy,importlib.util,json,os,sys,unittest
from pathlib import Path
from unittest.mock import Mock
from robingraph.retrieval.graph_intent_schema import execution_gate
ROOT=Path.cwd();path=Path(os.environ.get('RG_RECON_MODULE', ROOT/'src/robingraph/retrieval/semantic_graph_intent.py'))
spec=importlib.util.spec_from_file_location('robingraph.retrieval.independent_request_fix',path);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
observed=json.loads((ROOT/'docs/verification/assets/2026-10-24-question-family-routing/holdout-traces.json').read_text())['rows']
sub=next(r for r in observed if r['case']=='H05B')
QUESTION=sub['request']['question'];RAW=next(t['outputs'] for t in sub['diagnostic_spans'] if t['name']=='graph_intent.plan')
RELQUESTION=next(r for r in observed if r['case']=='H06B')['request']['question']
def rel(reference='Ardea cinerea'):
 return {'kind':'shared_diet','species':reference,'relation_text':'먹이 생태 범주가 같은','conditions':[],'unresolved':[],'unknown_relation':False}
class IndependentFollowup(unittest.TestCase):
 def test_terminal_request_recovery_preserves_plan_and_input(self):
  raw=copy.deepcopy(RAW);before=copy.deepcopy(raw);candidate,changes=s.reconcile_graph_plan(QUESTION,raw)
  self.assertEqual(raw,before);self.assertTrue(changes);self.assertEqual(candidate['unresolved'],[])
  self.assertEqual({k:v for k,v in raw.items() if k!='unresolved'},{k:v for k,v in candidate.items() if k!='unresolved'})
  self.assertEqual(execution_gate(QUESTION,s._build(QUESTION,candidate)),'answer')
 def test_embedded_changed_absent_or_duplicated_request_is_not_removed(self):
  for q in (QUESTION.replace('궁금해','궁금해하지만'),QUESTION.replace('궁금해','궁금해도'),QUESTION.replace('궁금해','궁금해하는'),QUESTION.replace('궁금해','알려줘'),QUESTION+' 궁금해'):
   with self.subTest(question=q):self.assertEqual(s.reconcile_graph_plan(q,RAW),(RAW,[]))
 def test_condition_bearing_unresolved_text_never_cleared(self):
  for text in ('밤에만 활동하는 새가 궁금해','가장 무거운 종이 궁금해','숲에 사는 새가 궁금해'):
   q=QUESTION.replace('궁금해',text);raw={**copy.deepcopy(RAW),'unresolved':[text]}
   with self.subTest(text=text):self.assertEqual(s.reconcile_graph_plan(q,raw),(raw,[]))
  raw={**copy.deepcopy(RAW),'unresolved':['궁금해','숲에 사는']};q=QUESTION+' 숲에 사는 종.'
  self.assertEqual(s.reconcile_graph_plan(q,raw),(raw,[]))
 def test_self_exclusion_comma_reaches_checked_plan_only(self):
  provider=Mock(return_value=rel());i=s.graph_intent_handler(RELQUESTION,provider=provider)
  provider.assert_called_once();self.assertEqual(execution_gate(RELQUESTION,i),'answer');self.assertEqual(i.species[0].text,'Ardea cinerea')
 def test_other_species_extra_numeric_or_negative_condition_still_hold(self):
  cases=[('Ardea cinerea 자신은 빼고, Egretta garzetta와 먹이 생태 범주가 같은 종을 알려줘.',rel('Egretta garzetta')),
         (RELQUESTION+' 체중이 100g 미만인 새.',rel()),
         (RELQUESTION+' 숲에 살지 않는 새.',rel())]
  for q,p in cases:
   with self.subTest(question=q):self.assertNotEqual(execution_gate(q,s.graph_intent_handler(q,provider=lambda *_:p)),'answer')
if __name__=='__main__':unittest.main(verbosity=2)
