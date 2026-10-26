import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate

def run(q,p):
 before=copy.deepcopy(p);c,_=s.reconcile_graph_plan(q,p);assert p==before
 return execution_gate(q,s.interpret(q,lambda *_:c)),c
class LocalThreeGuards(unittest.TestCase):
 def test_record_value_noun_retains_one_field_and_one_value(self):
  q='서식 환경 기록값 Wetland 조건으로 Anas platyrhynchos platyrhynchos 아종 하나를 조회해 줘.'
  p={'kind':'taxon_traits','taxon':'Anas platyrhynchos platyrhynchos','conditions':[{'trait_name':'habitat','op':'eq','value':'Wetland','surface':'Wetland'}],'unresolved':[],'unknown_relation':False}
  gate,c=run(q,p);self.assertEqual('answer',gate);self.assertEqual('서식 환경 기록값 Wetland',c['conditions'][0]['surface'])
  for changed in (q.replace('조건으로','조건이 아닌'),q.replace('Wetland','Riverine'),q.replace('서식 환경','생활 방식'),q+' 서식 환경 기록값 Wetland 조건으로.',q+' 부리 길이 20mm 이상인 종만.'):
   with self.subTest(q=changed):self.assertNotEqual('answer',run(changed,p)[0])
 def test_typed_canonical_support_preserves_negative_code_boundary_and_extra_predicates(self):
  base='물총새과에서 diet_category는 Invertebrate로 지정해 줘.'
  def p(surface,trait='diet_category',value='Invertebrate'):
   return {'kind':'taxon_traits','taxon':'물총새과','conditions':[{'trait_name':trait,'op':'eq','value':value,'surface':surface}],'unresolved':[],'unknown_relation':False}
  surface='diet_category는 Invertebrate로 지정해 줘';self.assertEqual('answer',run(base,p(surface))[0])
  for surface in ('diet_category는 Invertebrate아닌 것으로 지정해 줘','diet_category는 Invertebrate 또는 Omnivore로 지정해 줘','diet_category는 InvertebrateExtra로 지정해 줘','diet_category는 NoInvertebrate로 지정해 줘','diet_category는 Invertebrate로 지정하지 마','diet_category는 Invertebrate로 지정하지 말아 주세요'):
   with self.subTest(surface=surface):self.assertNotEqual('answer',run('물총새과에서 '+surface+'.',p(surface))[0])
  q='물총새과에서 diet_category가 Invertebrate인지 말해줘.'
  self.assertEqual('answer',run(q,p('diet_category가 Invertebrate인지 말해줘'))[0])
  for trait in ('trophic_level','trophic_niche'):
   self.assertNotEqual('answer',run(base,p('diet_category는 Invertebrate로 지정해 줘',trait))[0])
 def test_same_fruit_framing_does_not_hide_independent_relation(self):
  q='검은이마직박구리와 공통으로 먹는 열매가 있는 다른 새를 알려 줘. 열매를 맺는 식물의 종이 동일한 경우만 포함해 줘.'
  i=e.extract_graph_intent(q);self.assertEqual('insufficient_data',execution_gate(q,i));self.assertEqual(['검은이마직박구리'],[x.text for x in i.species])
  for changed in (q.replace('동일한','동일하지 않은'),q.replace('공통으로 먹는','함께 사는'),q.replace('공통으로 먹는','공통으로 먹지 않는'),q+' 몸무게 100g 이상인 종만.',q+' 까치와도 같은 서식지인 종만.',q.replace('동일한 경우만','동일한 경우와 다른 경우만')):
   with self.subTest(q=changed):self.assertNotIn(execution_gate(changed,e.extract_graph_intent(changed)),('answer','insufficient_data'))
