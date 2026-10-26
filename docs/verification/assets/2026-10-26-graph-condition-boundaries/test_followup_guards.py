"""Independent negative boundaries for narrow clarification repairs; no live calls."""
import copy,json,unittest
from unittest.mock import Mock
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


def typed(taxon,trait,value,surface,unresolved=()):
 return {'kind':'taxon_traits','taxon':taxon,'conditions':[{'trait_name':trait,'op':'eq','value':value,'surface':surface}],'unresolved':list(unresolved),'unknown_relation':False}
def relation(name,phrase,unresolved=()):
 return {'kind':'shared_diet','species':name,'relation_text':phrase,'conditions':[],'unresolved':list(unresolved),'unknown_relation':False}
def answer(q,p):return execution_gate(q,s.interpret(q,lambda *_:p))=='answer'

a=typed('Turdus','trophic_niche','Omnivore','먹이 생태 범주가 Omnivore인')

class NarrowRepairBoundaries(unittest.TestCase):
 def test_metadiscourse_cannot_consume_biological_negative_or_qualifying_clause(self):
  for clause in ('숲에 살지 않는','날개가 200mm를 넘지 않는','체중 제한을 두지 말고 야행성인','비율은 10% 이상이어야 해','비율 조건을 뜻하는 건 아니고 숲에 사는','자료를 펼쳐서 겨울 새만'):
   q=f'Turdus에서 먹이 생태 범주가 Omnivore인 새. {clause}'
   raw={**a,'unresolved':[clause]};before=copy.deepcopy(raw)
   candidate,changes=s.reconcile_graph_plan(q,raw)
   with self.subTest(clause=clause):
    self.assertFalse(answer(q,candidate));self.assertEqual(before,raw)

 def test_repeated_or_absent_discourse_evidence_does_not_get_erased(self):
  clause='비율 조건은 적용하지 마세요'
  for q in (f'Turdus에서 먹이 생태 범주가 Omnivore인 새. {clause}. {clause}.', 'Turdus에서 먹이 생태 범주가 Omnivore인 새.'):
   raw={**a,'unresolved':[clause]};candidate,changes=s.reconcile_graph_plan(q,raw)
   with self.subTest(q=q):self.assertFalse(answer(q,candidate))

 def test_only_same_reference_exclusion_can_be_reconciled(self):
  for exclusion in ('까치 말고','청둥오리와 까치 말고','청둥오리가 아닌 새만','청둥오리보다 무거운 새는 빼고'):
   q=f'{exclusion}, 청둥오리와 같은 먹이 생태 범주를 가진 새'
   raw=relation('청둥오리','같은 먹이 생태 범주를 가진',[exclusion]);candidate,changes=s.reconcile_graph_plan(q,raw)
   with self.subTest(exclusion=exclusion):self.assertFalse(answer(q,candidate))

 def test_extra_relation_or_condition_cannot_be_removed_with_self_exclusion(self):
  for clause in ('까치와도 같은 먹이 범주','숲에 살지 않는','몸무게가 100g 이하인','겨울에만 사는'):
   q=f'청둥오리는 빼고, 청둥오리와 같은 먹이 생태 범주를 가진 새. {clause}'
   raw=relation('청둥오리','같은 먹이 생태 범주를 가진',['청둥오리는 빼고',clause]);candidate,changes=s.reconcile_graph_plan(q,raw)
   with self.subTest(clause=clause):self.assertFalse(answer(q,candidate))

 def test_unrestricted_dimension_cannot_conflict_with_implicit_relation(self):
  q='먹이 범주는 제한하지 말고 청둥오리와 같은 먹이 생태 범주를 가진 새'
  raw=relation('청둥오리','같은 먹이 생태 범주를 가진',['먹이 범주는 제한하지 말고'])
  candidate,changes=s.reconcile_graph_plan(q,raw)
  self.assertFalse(answer(q,candidate))

 def test_unit_label_repair_preserves_threshold_and_still_requires_audit(self):
  q='Corvus에서 부리 너비 기록이 2cm 미만인 새'
  raw={'kind':'taxon_traits','taxon':'Corvus','conditions':[{'trait_name':'beak_width','op':'num_lt','threshold':20,'unit':'cm','surface':'부리 너비 기록이 2cm 미만인'}],'unresolved':[],'unknown_relation':False}
  before=copy.deepcopy(raw);candidate,changes=s.reconcile_graph_plan(q,raw)
  self.assertEqual(before,raw);self.assertEqual(20,candidate['conditions'][0]['threshold'])
  self.assertEqual('mm',candidate['conditions'][0]['unit']);self.assertTrue(answer(q,candidate))
  document=lambda p:{'candidates':[{'content':{'parts':[{'text':json.dumps(p)}]}}]}
  client=GeminiAnswerer('dummy',urlopen=Mock());client._request=Mock(side_effect=[document(raw),document({'faithful':False,'issues':['reject repaired plan']})])
  with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):
   client.propose_structured_graph_intent(q,[],s.CONTRACT)
  self.assertEqual(2,client._request.call_count)

 def test_unrestricted_dimension_whitespace_and_ratio_proof_stay_strict(self):
  for label in ('날개길이','날개  길이','날개 길이'):
   clause=f'{label} 제한은 두지 않을게'
   q=f'날개 길이가 20mm 이상인 새. {clause}.'
   raw={'kind':'taxon_traits','taxon':None,'conditions':[{'trait_name':'wing_length','op':'num_gte','threshold':20,'unit':'mm','surface':'날개 길이가 20mm 이상인'}],'unresolved':[clause]}
   with self.subTest(label=label):
    candidate,changes=s.reconcile_graph_plan(q,raw);self.assertFalse(answer(q,candidate))
  for raw in (typed('Turdus','habitat','Forest','숲에 사는'), {'kind':'taxon_traits','taxon':'Turdus','conditions':[{'trait_name':'diet_distribution','op':'share_gt','value':'fruit','threshold':0,'surface':'열매를 먹는'}]}):
   surface=raw['conditions'][0]['surface'];q=f'Turdus에서 {surface} 새. 비율 조건을 뜻하는 건 아니야.'
   with self.subTest(raw=raw):self.assertFalse(answer(q,raw))

 def test_number_repair_cannot_change_threshold_unit_trait_or_comparator(self):
  q='까마귀과에서 몸무게가 0.5kg보다 무거운 새'
  number={'trait_name':'body_mass','op':'num_gt','threshold':500,'unit':'g','surface':'몸무게가 0.5kg보다 무거운'}
  for change in ({'threshold':50},{'threshold':5,'unit':'kg'},{'unit':'mm'}, {'trait_name':'wing_length','unit':'mm'},{'op':'num_gte'}, {'op':'num_lt'}):
   raw={'kind':'taxon_traits','taxon':'까마귀과','conditions':[{**number,**change}],'unresolved':[],'unknown_relation':False}
   candidate,changes=s.reconcile_graph_plan(q,raw)
   with self.subTest(change=change):self.assertFalse(answer(q,candidate))

if __name__=='__main__':unittest.main(verbosity=2)
