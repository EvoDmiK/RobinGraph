import unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
class RecordAssignmentBoundaries(unittest.TestCase):
 def test_leading_whitespace_keeps_source_offsets(self):
  base='Turdus merula의 영양 단계 기록값이 Omnivore인지 확인하고 싶어요.'
  for prefix in ('',' ','\n  ','\t'):
   q=prefix+base;p={'kind':'taxon_traits','taxon':'Turdus merula','conditions':[{'trait_name':'trophic_level','op':'eq','value':'Omnivore','surface':'영양 단계가 Omnivore인'}],'unresolved':[],'unknown_relation':False}
   c,_=s.reconcile_graph_plan(q,p)
   with self.subTest(prefix=repr(prefix)):self.assertEqual('answer',execution_gate(q,s.interpret(q,lambda *_:c)))
 def test_inside_word_label_is_not_original_assignment(self):
  for label in ('가짜영양 단계','반영양 단계','유사먹이 유형'):
   trait='diet_category'if'먹이'in label else'trophic_level';q=f'Turdus merula의 {label} 기록값이 Omnivore인지 확인하고 싶어요.'
   surface='먹이 유형이 Omnivore인'if trait=='diet_category'else'영양 단계가 Omnivore인'
   p={'kind':'taxon_traits','taxon':'Turdus merula','conditions':[{'trait_name':trait,'op':'eq','value':'Omnivore','surface':surface}],'unresolved':[],'unknown_relation':False}
   c,_=s.reconcile_graph_plan(q,p)
   with self.subTest(label=label):self.assertEqual('clarify',execution_gate(q,s.interpret(q,lambda *_:c)))
