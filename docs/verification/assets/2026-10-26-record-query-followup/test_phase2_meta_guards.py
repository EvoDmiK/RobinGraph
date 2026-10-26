import copy,json,unittest
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
class Phase2MetaGuards(unittest.TestCase):
 def test_unused_query_dimension_is_not_biological_negation(self):
  for meta in ('비율 수치로 걸러 달라는 뜻은 아닙니다','먹이 구성 비율은 검색 조건에 넣지 마','구성비에 관한 조건은 사용하지 않아','이번 검색 설정에서는 먹이 비율을 조건으로 사용하지 않겠어','먹이별 비율 차원은 검색 조건에 적용하지 말아 줘'):
   q='먹이 유형이 잡식인 새를 찾아줘. '+meta+'.'
   p={'kind':'taxon_traits','conditions':[{'trait_name':'diet_category','op':'eq','value':'Omnivore','surface':'먹이 유형이 잡식인'}],'unresolved':[meta],'unknown_relation':False}
   c,_=s.reconcile_graph_plan(q,copy.deepcopy(p));provider=Mock(return_value=c)
   with self.subTest(meta=meta):self.assertEqual('answer',execution_gate(q,s.graph_intent_handler(q,provider=provider)));provider.assert_called_once()
   for extra in (' 곤충을 먹지 않는 새만.', ' 비율은 20% 이상인 새.', ' 잡식이 아닌 새만.', ' 체중이 200g 이상인 새만.'):
    with self.subTest(meta=meta,extra=extra):self.assertNotEqual('answer',execution_gate(q+extra,s.interpret(q+extra,lambda *_:c)))
  q='먹이 유형이 잡식인 새. 비율 조건은 적용하지 마세요. 서울에서만 사는 새.'
  p={'kind':'taxon_traits','conditions':[{'trait_name':'diet_category','op':'eq','value':'Omnivore','surface':'먹이 유형이 잡식인'}],'unresolved':['비율 조건은 적용하지 마세요','서울에서만 사는'],'unknown_relation':False}
  c,_=s.reconcile_graph_plan(q,p);self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:c)))
 def test_no_typed_category_proof_or_wrong_source_or_audit_cannot_pass(self):
  meta='비율 수치로 걸러 달라는 뜻은 아닙니다'
  q='씨앗을 먹는 새. '+meta+'.'
  p={'kind':'taxon_traits','conditions':[{'trait_name':'diet_distribution','op':'share_gt','value':'seed','threshold':0,'surface':'씨앗을 먹는'}],'unresolved':[],'unknown_relation':False}
  self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:p)))
  q='먹이 유형이 잡식인 새. '+meta+'.';p['conditions']=[{'trait_name':'diet_category','op':'eq','value':'Omnivore','surface':'먹이 유형이 잡식인'}]
  bad={**p,'conditions':[{**p['conditions'][0],'surface':'먹이 유형은 잡식인'}]}
  self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:bad)))
  def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
  a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(p),doc({'faithful':False,'issues':['veto']})])
  with self.assertRaises(GeminiAnswerError):a.propose_structured_graph_intent(q,[],s.CONTRACT)
