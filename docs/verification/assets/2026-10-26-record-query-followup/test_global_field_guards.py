import unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

def gate(q,trait,value,surface):
 p={'kind':'taxon_traits','taxon':'Turdus merula','conditions':[{'trait_name':trait,'op':'eq','value':value,'surface':surface}],'unresolved':[],'unknown_relation':False}
 return execution_gate(q,s.interpret(q,lambda *_:p))
class GlobalFieldGuards(unittest.TestCase):
 def test_explicit_field_never_changes_with_request_verb(self):
  labels={'trophic_level':'영양 단계','trophic_niche':'먹이 생태 범주','diet_category':'먹이 유형'}
  for field,label in labels.items():
   surface=f'{label} 기록값이 Omnivore인지';q=f'Turdus merula의 {surface} 알아보고 싶어.'
   for planned in labels:
    with self.subTest(field=field,planned=planned):self.assertEqual('answer'if field==planned else'clarify',gate(q,planned,'Omnivore',surface))
 def test_bare_shared_code_requires_one_explicit_dimension(self):
  for field in ('trophic_level','trophic_niche','diet_category'):
   self.assertEqual('clarify',gate('Turdus merula 중 Omnivore인 새를 찾아줘.',field,'Omnivore','Omnivore인'))
   q='Turdus merula의 먹이 유형 기록을 볼게요. Omnivore인 종을 찾아줘.'
   self.assertEqual('answer'if field=='diet_category'else'clarify',gate(q,field,'Omnivore','Omnivore인'))
 def test_joined_explicit_fields_cannot_select_only_one_from_full_span(self):
  for join in ('와 ','과 ','랑 ','하고 ','·'):
   surface='영양 단계'+join+'먹이 유형이 Omnivore인';q='Turdus merula의 '+surface+' 종을 찾아줘.'
   for field in ('trophic_level','diet_category'):
    with self.subTest(join=join,field=field):self.assertEqual('clarify',gate(q,field,'Omnivore',surface))
