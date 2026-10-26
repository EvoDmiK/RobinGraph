"""Independent mocked contract review; sealed questions are never loaded here."""
import copy,importlib,importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import Mock
BASE=Path('/tmp/rg-question-contract-backend/src/robingraph')
for suffix in ('retrieval.graph_intent_schema','retrieval.graph_condition_extractor','retrieval.semantic_graph_intent','generation'):
 name='robingraph.'+suffix;parent,child=name.rsplit('.',1);p=importlib.import_module(parent)
 spec=importlib.util.spec_from_file_location(name,BASE/Path(*suffix.split('.')).with_suffix('.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;setattr(p,child,m);spec.loader.exec_module(m)
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import canonical_graph_plan,execution_gate
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.generation import GeminiAnswerer,GeminiAnswerError

def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
class Review(unittest.TestCase):
 def test_nearest_example_is_reviewed_context_never_an_executable_substitute(self):
  approved=s.verified_semantic_examples()[0];faked=copy.deepcopy(approved);faked['intent']={'kind':'none'}
  got=s._examples('new question',lambda *_a,**_kw:[faked,{**approved,'question':'unreviewed query'}])
  self.assertEqual(got,[approved]);got[0]['intent']['kind']='none'
  self.assertNotEqual(s.verified_semantic_examples()[0]['intent']['kind'],'none')
  question='직박구리와 같은 먹이 생태 범주를 가진 새를 알려줘.'
  wrong={'kind':'shared_diet','species':'까치','relation_text':'같은 먹이 생태 범주를 가진','conditions':[]}
  intent=s.graph_intent_handler(question,provider=lambda *_:wrong)
  self.assertNotEqual(execution_gate(question,intent),'answer')
 def test_audit_rejection_still_does_not_return_plan(self):
  question='Corvus 중 몸무게가 1000g 초과인 새를 찾아줘.'
  plan={'kind':'taxon_traits','taxon':'Corvus','conditions':[{'trait_name':'body_mass','op':'num_gt','threshold':1000,'unit':'g','surface':'몸무게가 1000g 초과인'}]}
  answerer=GeminiAnswerer('dummy',urlopen=Mock());answerer._request=Mock(side_effect=[doc(plan),doc({'faithful':False,'issues':['몸무게가 1000g 초과인 범위를 확인하지 못함']})])
  with self.assertRaises(GeminiAnswerError) as caught:answerer.propose_structured_graph_intent(question,[],s.CONTRACT)
  self.assertEqual(caught.exception.reason,'semantic_audit_rejected');self.assertEqual(answerer._request.call_count,2)
  self.assertEqual([x.text for x in caught.exception.original_spans],['몸무게가 1000g 초과인'])
 def test_numeric_comparator_and_extra_constraints_never_collapse(self):
  q='Corvus 중 몸무게가 1000g 초과인 새를 찾아줘.'
  def plan(op,threshold=1000):return {'kind':'taxon_traits','taxon':'Corvus','conditions':[{'trait_name':'body_mass','op':op,'threshold':threshold,'unit':'g','surface':'몸무게가 1000g 초과인'}]}
  good=s.interpret(q,lambda *_:plan('num_gt'));self.assertIsNotNone(canonical_graph_plan(q,good))
  for p in (plan('num_gte'),plan('num_gt',999)):
   actual=s.interpret(q,lambda *_:p);self.assertIsNone(canonical_graph_plan(q,actual))
  for question in ('까치와 같은 먹이 생태 범주를 가진 새 중 밤에만 활동하는 새는?', '까치와 같지 않은 먹이 생태 범주를 가진 새는?', '까치와 같은 먹이 생태 범주를 가진 새 중 가장 무거운 새는?'):
   provider=Mock();intent=s.graph_intent_handler(question,provider=provider);provider.assert_not_called();self.assertIsNone(canonical_graph_plan(question,intent))
 def test_canonical_condition_qualifier_and_source_wording_stay_separate(self):
  ordinary='참새목 중 열매를 먹는 새는?';tree='참새목 중 나무 열매를 먹는 새는?';niche='참새목 중 과실식 새는?'
  plans=[canonical_graph_plan(q,extract_graph_intent(q)) for q in (ordinary,tree,niche)]
  self.assertTrue(all(p is not None for p in plans));self.assertEqual(len({json.dumps(p,sort_keys=True) for p in plans}),3)
  self.assertIsNone(canonical_graph_plan('참새목 중 망고 열매를 먹는 새는?',extract_graph_intent('참새목 중 망고 열매를 먹는 새는?')))
if __name__=='__main__':unittest.main(verbosity=2)
