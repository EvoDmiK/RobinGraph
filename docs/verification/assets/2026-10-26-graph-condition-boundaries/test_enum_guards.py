"""Independent synthetic guard checks, not live API success evidence."""
import copy,json,unittest
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError


def cond(trait,value,surface):
 return {'trait_name':trait,'op':'eq','value':value,'surface':surface}
def plan(taxon,*cs):
 return {'kind':'taxon_traits','taxon':taxon,'conditions':list(cs),'unresolved':[],'unknown_relation':False}
def gate(q,p):return execution_gate(q,s.interpret(q,lambda *_:copy.deepcopy(p)))
def document(payload):return {'candidates':[{'content':{'parts':[{'text':json.dumps(payload)}]}}]}

class IndependentEnumGuards(unittest.TestCase):
 def test_validated_enum_occurrence_with_scientific_scope(self):
  for taxon in ('Corvus','Corvus corax','Hirundo rustica gutturalis'):
   for trait,code,label in [('trophic_niche','Omnivore','먹이 생태 범주'),('primary_lifestyle','Terrestrial','생활 방식'),('trophic_niche','Herbivore terrestrial','먹이 생태 범주')]:
    surface=f'{label}가 {code}인';q=f'{taxon}에서 {surface} 새를 찾아줘'
    with self.subTest(taxon=taxon,code=code):self.assertEqual('answer',gate(q,plan(taxon,cond(trait,code,surface))))

 def test_same_spelling_elsewhere_is_not_consumed(self):
  for q in ('Omnivore 속에서 먹이 생태 범주가 Omnivore인 새', '먹이 생태 범주가 Omnivore인 Omnivore 속 새'):
   with self.subTest(q=q):self.assertNotEqual('answer',gate(q,plan(None,cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인'))))

 def test_extra_taxon_never_disappears_inside_or_outside_evidence(self):
  for extra in ('Corvus corax','Anas platyrhynchos','까마귀과'):
   for surface in ('먹이 생태 범주가 Omnivore인',f'먹이 생태 범주가 Omnivore인 {extra}'):
    q=f'Turdus에서 먹이 생태 범주가 Omnivore인 {extra} 새'
    with self.subTest(extra=extra,surface=surface):self.assertNotEqual('answer',gate(q,plan('Turdus',cond('trophic_niche','Omnivore',surface))))
  q='Corvus corax에서 먹이 생태 범주가 Omnivore인 새'
  self.assertNotEqual('answer',gate(q,plan('Corvus',cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인'))))

 def test_invalid_code_trait_or_absent_original_evidence_still_holds(self):
  q='Turdus에서 먹이 생태 범주가 Omnivore인 새'
  good=cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인')
  for change in ({'trait_name':'primary_lifestyle'},{'value':'Invertivore'},{'value':'Imaginary'},{'surface':'없는 문구 Omnivore'}, {'surface':'새'}):
   with self.subTest(change=change):self.assertNotEqual('answer',gate(q,plan('Turdus',{**good,**change})))

 def test_negative_and_additional_unsupported_conditions_still_hold(self):
  p=plan('Turdus',cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인'))
  for q in ('Turdus에서 먹이 생태 범주가 Omnivore인 새 말고 다른 새', 'Turdus에서 먹이 생태 범주가 Omnivore인 겨울 새', 'Turdus에서 먹이 생태 범주가 Omnivore인 새 중 가장 큰 종'):
   with self.subTest(q=q):self.assertNotEqual('answer',execution_gate(q,s.graph_intent_handler(q,provider=lambda *_:copy.deepcopy(p))))

 def test_enum_does_not_relax_numeric_checks(self):
  q='Turdus에서 먹이 생태 범주가 Omnivore이고 몸무게가 200g 초과인 새'
  base=cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore이고')
  number={'trait_name':'body_mass','op':'num_gt','threshold':200,'unit':'g','surface':'몸무게가 200g 초과인'}
  self.assertEqual('answer',gate(q,plan('Turdus',base,number)))
  for change in ({'threshold':20},{'unit':'mm'},{'op':'num_gte'}):
   with self.subTest(change=change):self.assertNotEqual('answer',gate(q,plan('Turdus',base,{**number,**change})))

 def test_default_name_detection_and_entity_exclusion_not_globally_exempt(self):
  q='Omnivore 말고 Corvus corax에서 먹이 생태 범주가 Omnivore인 새'
  self.assertEqual(['Omnivore','Corvus corax','Omnivore'],[q[a:b]for a,b in s._named_taxa(q)])
  self.assertIn('Omnivore',[subject for span,subject in s._exclusions(q)])
  self.assertNotEqual('answer',gate(q,plan('Corvus corax',cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인'))))

 def test_semantic_audit_false_still_blocks(self):
  q='Turdus에서 먹이 생태 범주가 Omnivore인 새'
  p=plan('Turdus',cond('trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인'))
  answerer=GeminiAnswerer('dummy',urlopen=Mock())
  answerer._request=Mock(side_effect=[document(p),document({'faithful':False,'issues':['independent veto']})])
  with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):
   answerer.propose_structured_graph_intent(q,[],s.CONTRACT)
  self.assertEqual(2,answerer._request.call_count)

if __name__=='__main__':unittest.main(verbosity=2)
