"""Independent numeric particle matrix, all synthetic and separate from sealed questions."""
import unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

class NumericParticleMatrix(unittest.TestCase):
 def test_nominal_comparators_with_functional_particles_and_quotes(self):
  for op,word in [('num_gte','이상'),('num_lte','이하'),('num_gt','초과'),('num_lt','미만')]:
   for suffix in ('으로','로','라는','이라고','이라는','인','이고','이며','이다','입니다','의','은','을','에'):
    surface=f'체중 200g {word}'
    q=f'황조롱이의 종 기록에서 {surface}{suffix} 조건을 확인해 줘'
    raw={'kind':'taxon_traits','taxon':'황조롱이','conditions':[{'trait_name':'body_mass','op':op,'threshold':200,'unit':'g','surface':surface}]}
    with self.subTest(op=op,suffix=suffix):self.assertEqual('answer',execution_gate(q,s.interpret(q,lambda *_:raw)))

 def test_quoted_and_nominal_copular_denials_are_not_positive_filters(self):
  raw={'kind':'taxon_traits','taxon':'황조롱이','conditions':[{'trait_name':'body_mass','op':'num_gte','threshold':200,'unit':'g','surface':'체중 200g 이상인'}]}
  for denial in ('아니라는','아니라고','아니라서','아님','아닌'):
   q=f'황조롱이 종 기록에서 체중 200g 이상이 {denial} 조건을 적용해 줘'
   with self.subTest(denial=denial):
    candidate,changes=s.reconcile_graph_plan(q,raw)
    self.assertNotEqual('answer',execution_gate(q,s.interpret(q,lambda *_:candidate)))

 def test_particle_prefix_does_not_eat_content_words_or_denial(self):
  surface='체중 200g 이상'
  raw={'kind':'taxon_traits','taxon':'황조롱이','conditions':[{'trait_name':'body_mass','op':'num_gte','threshold':200,'unit':'g','surface':surface}]}
  for suffix in ('으로마늘','로켓','이라는망고','치','이라는 것은 아니다','이라고는 할 수 없는'):
   q=f'황조롱이의 종 기록에서 {surface}{suffix} 조건을 확인해 줘'
   with self.subTest(suffix=suffix):self.assertNotEqual('answer',execution_gate(q,s.interpret(q,lambda *_:raw)))

if __name__=='__main__':unittest.main(verbosity=2)
