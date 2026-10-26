"""Independent typed record assignment checks, frozen before proposed helper review. No model/API calls."""
import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

def plan(trait='trophic_level',value='Omnivore',surface='영양 단계가 Omnivore인',unresolved=()):
 return {'kind':'taxon_traits','taxon':'Turdus merula','conditions':[{'trait_name':trait,'op':'eq','value':value,'surface':surface}],'unresolved':list(unresolved),'unknown_relation':False}
def run(q,p):
 before=copy.deepcopy(p);c,changes=s.reconcile_graph_plan(q,p);assert p==before
 return execution_gate(q,s.interpret(q,lambda *_:c)),c,changes
Q='Turdus merula 종의 영양 단계 기록값이 Omnivore인지 확인하고 싶어요.'
class RecordAssignmentGuards(unittest.TestCase):
 def test_unique_typed_original_assignment_only_changes_evidence(self):
  cases=[(Q,plan()),('Turdus merula라는 종의 영양 단계가 Omnivore로 기록되어 있는지 조회해 주세요.',plan()),('Turdus merula 종의 서식 환경이 Wetland로 기록되어 있는지 확인해 주세요.',plan('habitat','Wetland','Wetland로'))]
  for q,p in cases:
   gate,c,changes=run(q,p)
   with self.subTest(q=q):
    self.assertEqual('answer',gate);self.assertIn(c['conditions'][0]['surface'],q)
    for key in ('trait_name','op','value'):self.assertEqual(p['conditions'][0][key],c['conditions'][0][key])
 def test_wrong_value_field_or_cross_binding_never_recovers(self):
  q='Turdus merula의 영양 단계 기록값이 Omnivore인지, 먹이 유형 기록값이 Carnivore인지 확인하고 싶어요.'
  for p in [plan(value='Carnivore',surface='영양 단계가 Carnivore인'),plan(trait='diet_category'),plan('diet_category','Omnivore','먹이 유형이 Omnivore인')]:
   with self.subTest(p=p):self.assertNotEqual('answer',run(q,p)[0])
  for p in [plan('trophic_niche'),plan(value='Carnivore'),plan('habitat')]:
   with self.subTest(p=p):self.assertNotEqual('answer',run(Q,p)[0])
 def test_repeated_identical_assignments_are_not_arbitrarily_selected(self):
  for q in [Q+' 영양 단계 기록값이 Omnivore인지 한 번 더 확인해 줘.', 'Turdus merula의 영양 단계 기록값이 Omnivore이고 먹이 유형 기록값도 Omnivore인지 확인하고 싶어요.', 'Turdus merula의 영양 단계와 먹이 유형 기록값이 Omnivore인지 확인하고 싶어요.']:
   with self.subTest(q=q):self.assertNotEqual('answer',run(q,plan())[0])
 def test_original_negative_or_disjunction_retained(self):
  for q in [Q.replace('Omnivore인지','Omnivore가 아닌지'),Q.replace('Omnivore인지','Omnivore인지 Carnivore인지'),Q.replace('Omnivore인지','Omnivore 또는 Carnivore인지'),Q+' Omnivore라는 것은 아닙니다.']:
   with self.subTest(q=q):self.assertNotEqual('answer',run(q,plan())[0])
 def test_additional_conditions_are_not_covered_by_record_frame(self):
  for extra in ['체중 200g 이상인 종만.','부리 길이가 20mm 미만인 종만.','서울에서만 사는 종만.','겨울에 사는 종만.','Carnivore를 먹이 유형으로 가진 종만.']:
   q=Q+' '+extra;p=plan(unresolved=[extra])
   with self.subTest(extra=extra):self.assertNotEqual('answer',run(q,p)[0])
 def test_mutation_request_is_not_record_lookup_evidence(self):
  for q in ['Turdus merula의 영양 단계를 Omnivore로 기록해 줘.','Turdus merula의 영양 단계 기록값을 Omnivore로 바꿔 주세요.']:
   with self.subTest(q=q):self.assertNotEqual('answer',run(q,plan())[0])
 def test_numeric_and_share_contract_cannot_use_categorical_recovery(self):
  q='Turdus merula의 체중 기록값이 200g인지 확인하고 싶어요.'
  p=plan('body_mass',None,'체중이 200g인');p['conditions'][0].update(op='num_gt',threshold=200,unit='g')
  self.assertNotEqual('answer',run(q,p)[0])
  q='Turdus merula의 먹이 구성 기록값이 열매인지 확인하고 싶어요.'
  p=plan('diet_distribution','fruit','열매를 먹는');p['conditions'][0].update(op='share_gt',threshold=0)
  self.assertNotEqual('answer',run(q,p)[0])
