"""Feedback-exposed candidate guard review; no live calls or root source writes."""
import copy,importlib.util,sys,unittest
from unittest.mock import Mock
from pathlib import Path
from robingraph.retrieval.graph_intent_schema import execution_gate
path=Path('/tmp/rg-rank-and-order-followup/src/robingraph/retrieval/semantic_graph_intent.py')
spec=importlib.util.spec_from_file_location('robingraph.retrieval.independent_rank',path);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
def raw(taxon):
 return {'kind':'taxon_traits','taxon':taxon,'species':None,'conditions':[{'trait_name':'habitat','op':'eq','value':'Forest','surface':'숲이 서식지로 기록되어 있고'},{'trait_name':'diet_distribution','op':'share_gt','value':'fruit','threshold':0,'surface':'열매도 먹는'}],'unresolved':[],'unknown_relation':False}
def q(name):return f'{name} 안에서 숲이 서식지로 기록되어 있고 열매도 먹는 종을 골라 줘.'
class Review(unittest.TestCase):
 def test_unique_scope_restore_and_immutability(self):
  for full in ('까마귀속','까마귀과','참새목'):
   p=raw(full[:-1]);before=copy.deepcopy(p);candidate,proof=s.reconcile_graph_plan(q(full),p)
   with self.subTest(full=full):
    self.assertEqual(before,p);self.assertEqual(candidate['taxon'],full);self.assertEqual(proof,[{'field':'taxon','rule':'rank_suffix','before':full[:-1],'after':full}])
    self.assertEqual({k:v for k,v in p.items() if k!='taxon'},{k:v for k,v in candidate.items() if k!='taxon'})
 def test_never_choose_rank_or_discard_another_original_name(self):
  base=q('까마귀속')
  variants=[(base,raw('까마귀과')),(base,raw('까마귀목')),(base,raw('까')),(base,raw('Corvus')),(base+' 까마귀는?',raw('까마귀')),(base+' 까마귀속도.',raw('까마귀')),(base+' 까치속도 포함해.',raw('까마귀')),(q('가짜까마귀속'),raw('가짜까마귀')),(q('까마귀'),raw('까마귀'))]
  for question,plan in variants:
   with self.subTest(question=question,taxon=plan['taxon']): self.assertEqual(s.reconcile_graph_plan(question,plan),(plan,[]))
 def test_new_semantic_route_cannot_drop_habitat_or_food(self):
  question='참새목에서 숲이 서식지로 기록돼 있으며 열매도 먹는 새를 찾아줘.'
  p=raw('참새목');p['conditions'][0]['surface']='숲이 서식지로 기록돼 있으며'
  for conditions in ([p['conditions'][0]],[p['conditions'][1]],[]):
   proposal={**p,'conditions':conditions};provider=Mock(return_value=proposal)
   i=s.graph_intent_handler(question,provider=provider)
   provider.assert_called_once();self.assertNotEqual(execution_gate(question,i),'answer')
  changed=copy.deepcopy(p);changed['conditions'][0]['value']='Wetland'
  self.assertNotEqual(execution_gate(question,s.graph_intent_handler(question,provider=lambda *_:changed)),'answer')
 def test_explicit_veto_or_complete_legacy_never_calls_model(self):
  for question in ('참새목 중 열매를 먹는 새는?','참새목 중 망고 열매를 먹는 새는?','참새목에서 숲이 서식지로 기록돼 있으며 열매를 먹지 않는 새는?','참새목에서 숲이 서식지로 기록돼 있으며 열매도 먹고 밤에만 활동하는 새는?'):
   provider=Mock(side_effect=AssertionError('unexpected provider'))
   i=s.graph_intent_handler(question,provider=provider)
   self.assertEqual(i,s.extract_graph_intent(question));provider.assert_not_called()
if __name__=='__main__':unittest.main(verbosity=2)
