"""Numeric evidence morphology regression guards; all provider data is synthetic."""
import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

def raw(surface='체중 200g 이상인',threshold=200,op='num_gte',unit='g',trait='body_mass'):
 return {'kind':'taxon_traits','taxon':'황조롱이','conditions':[{'trait_name':trait,'op':op,'threshold':threshold,'unit':unit,'surface':surface}],'unresolved':[],'unknown_relation':False}
def gate(q,p):return execution_gate(q,s.interpret(q,lambda *_:p))

class NumericTailGuards(unittest.TestCase):
 def test_copular_recovery_preserves_numeric_fields(self):
  q='황조롱이 종 기록에 체중 200g 이상이라는 조건을 적용해 주세요.'
  p=raw();before=copy.deepcopy(p);candidate,changes=s.reconcile_graph_plan(q,p)
  self.assertEqual('answer',gate(q,candidate));self.assertEqual(before,p);self.assertTrue(changes)
  self.assertEqual({k:v for k,v in p['conditions'][0].items()if k!='surface'}, {k:v for k,v in candidate['conditions'][0].items()if k!='surface'})

 def test_changed_quantity_comparator_field_or_ambiguous_prefix_does_not_recover(self):
  p=raw()
  for q in ('황조롱이 종 기록에 체중 201g 이상이라는 조건을 적용해 줘',
            '황조롱이 종 기록에 체중 200g 초과라는 조건을 적용해 줘',
            '황조롱이 종 기록에 날개 길이 200mm 이상이라는 조건을 적용해 줘',
            '황조롱이 종 기록에 체중 200g 이상이라는 조건을 적용해 줘. 체중 200g 이상이라고 적었어',
            '황조롱이 종 기록에 체중 200g 이상이 아니라는 조건을 적용해 줘',
            '황조롱이 종 기록에 체중 200g 이상이라는망고를 먹는 새를 찾아줘'):
   with self.subTest(q=q):
    candidate,changes=s.reconcile_graph_plan(q,p);self.assertNotEqual('answer',gate(q,candidate))

 def test_original_copular_denial_survives_numeric_prefix_recovery(self):
  p=raw()
  for denial in ('아니다','아니야','아니에요','아닙니다'):
   q=f'황조롱이 체중 200g 이상이라는 것은 {denial}'
   with self.subTest(denial=denial):
    candidate,changes=s.reconcile_graph_plan(q,p)
    self.assertNotEqual('answer',gate(q,candidate))

 def test_category_ratio_explanation_is_not_biological_negation(self):
  q='되새과에서 먹이 유형이 PlantSeed인 종. 비율 조건을 뜻하는 건 아니야.'
  p={'kind':'taxon_traits','taxon':'되새과','conditions':[{'trait_name':'diet_category','op':'eq','value':'PlantSeed','surface':'먹이 유형이 PlantSeed인'}],'unresolved':['비율 조건을 뜻하는 건 아니야.'],'unknown_relation':False}
  candidate,changes=s.reconcile_graph_plan(q,p)
  self.assertEqual('answer',gate(q,candidate))

 def test_indirect_question_ending_is_functional_but_not_a_noun_prefix(self):
  p=raw('날개 길이가 30cm보다 짧은',threshold=300,op='num_lt',unit='mm',trait='wing_length')
  q='황조롱이 날개 길이가 30cm보다 짧은지 알려줘'
  self.assertEqual('answer',gate(q,p))
  for word in ('지빠귀','지렁이','지않는'):
   with self.subTest(word=word):self.assertNotEqual('answer',gate(q.replace('짧은지','짧은'+word),p))

 def test_bare_comparison_keeps_operator_and_has_functional_original_ending(self):
  q='황조롱이의 종 기록을 대상으로 0.2kg보다 무겁다는 조건을 적용해 줘.'
  p=raw('0.2kg보다 무겁다',op='num_gt')
  self.assertEqual('answer',gate(q,p))
  for change in ({'op':'num_gte'},{'op':'num_lt'},{'threshold':20},{'unit':'mm'}):
   changed=copy.deepcopy(p);changed['conditions'][0].update(change)
   with self.subTest(change=change):self.assertNotEqual('answer',gate(q,changed))
  for ending in ('무겁다람쥐','무겁다곤충','무겁다아닌','무겁지 않다는'):
   text=q.replace('무겁다는',ending)
   with self.subTest(ending=ending):self.assertNotEqual('answer',gate(text,p))

if __name__=='__main__':unittest.main(verbosity=2)
