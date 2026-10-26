"""Independent synthetic boundary checks; no model, API or database calls."""
import copy,json,unittest
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.generation import GeminiAnswerer,GeminiAnswerError

def plan(surface='영양 단계가 Carnivore인',value='Carnivore',trait='trophic_level',taxon='Larus argentatus',unresolved=()):
 return dict(kind='taxon_traits',taxon=taxon,conditions=[dict(trait_name=trait,op='eq',value=value,surface=surface)],unresolved=list(unresolved),unknown_relation=False)
def resolved(q,p):
 before=copy.deepcopy(p);c,changes=s.reconcile_graph_plan(q,p);assert before==p
 return execution_gate(q,s.interpret(q,lambda *_:c)),c,changes
Q='Larus argentatus 종의 영양 단계가 Carnivore로 기록되어 있는지 확인해 줘.'
F='다른 새 가운데 꼬까울새가 먹는 것과 식물 종까지 동일한 열매를 먹는 종을 알려줘.'

class FourGuardTests(unittest.TestCase):
 def test_record_positive_changes_evidence_not_semantics(self):
  p=plan();gate,c,changes=resolved(Q,p)
  self.assertEqual('answer',gate);self.assertTrue(changes)
  self.assertEqual('영양 단계가 Carnivore로',c['conditions'][0]['surface'])
  for key in ('trait_name','op','value'):self.assertEqual(p['conditions'][0][key],c['conditions'][0][key])
 def test_record_value_trait_scope_and_repeated_original(self):
  for p in (plan(value='Omnivore'),plan(trait='trophic_niche'),plan(taxon='Larus'),plan(taxon='Larus fuscus')):
   with self.subTest(p=p):self.assertNotEqual('answer',resolved(Q,p)[0])
  for q in (Q+Q,Q+' Corvus corax도 포함해.',Q.replace('Carnivore로','Omnivore로'),Q.replace('영양 단계','생활 방식')):
   with self.subTest(q=q):self.assertNotEqual('answer',resolved(q,plan())[0])
 def test_record_negation_additional_constraints_are_not_requests(self):
  for q in (Q.replace('되어 있는지','되어 있지 않은지'),Q.replace('확인해 줘','확인하지 마'),Q+' 겨울에만 사는 종.',Q+' 몸무게가 200g 이상인 종.',Q+' Carnivore라는 것은 아니다.',Q.replace('기록되어','기록되어 있거나 아닌지 확인하고 기록되어')):
   with self.subTest(q=q):self.assertNotEqual('answer',resolved(q,plan())[0])
 def test_record_framing_exact_rank_and_request(self):
  p=plan('영양 단계가 Carnivore로',unresolved=['종의','기록되어 있는지 확인해 줘'])
  self.assertEqual('answer',resolved(Q,p)[0])
  for q in (Q.replace(' 종의',' 아종의'),Q+' 다른 종의 기록.',Q+' 숲에서만.',Q.replace('있는지 확인','있지 않은지 확인')):
   with self.subTest(q=q):self.assertNotEqual('answer',resolved(q,p)[0])
 def test_ratio_meta_never_erases_actual_share_or_constraint(self):
  q='Sturnus 속의 먹이 유형 Invertebrate 기록이 궁금해요. 비율 조건은 적용하지 마세요.'
  p=plan('먹이 유형 Invertebrate','Invertebrate','diet_category','Sturnus',['비율 조건은 적용하지 마세요.'])
  self.assertEqual('answer',resolved(q,p)[0])
  for suffix in (' 대신 겨울에 사는 종만.', ' 몸무게가 200g 이상인 종만.', ' 열매가 20% 이상인 종만.', ' 이 유형이 아닌 종만.'):
   with self.subTest(suffix=suffix):self.assertNotEqual('answer',resolved(q+suffix,p)[0])
  p['conditions'][0].update(trait_name='diet_distribution',op='share_gt',value='invertebrate',threshold=0)
  self.assertNotEqual('answer',resolved(q,p)[0])
 def test_fruit_reference_exact_and_unknown_subject_not_invented(self):
  for bird in ('꼬까울새','청둥오리','직박구리'):
   q=F.replace('꼬까울새',bird);i=e.extract_graph_intent(q)
   self.assertEqual('insufficient_data',execution_gate(q,i));self.assertEqual([bird],[x.text for x in i.species])
  for bird in ('식물','동물','아무이름','꼬까울새비슷한것'):
   q=F.replace('꼬까울새',bird);i=e.extract_graph_intent(q)
   self.assertEqual('clarify',execution_gate(q,i));self.assertNotIn(bird,[x.text for x in i.species])
 def test_fruit_extra_reference_negation_and_trait_remain_held(self):
  for q in (F.replace('꼬까울새가','꼬까울새와 청둥오리가'),F.replace('꼬까울새가','꼬까울새가 청둥오리와'),F+' 직박구리와 비교해.',F+' 체중 100g 이상인 종.',F+' 과실식성인 종.',F+' 밤에만 활동하는 종.',F.replace('먹는 것과','먹지 않는 것과'),F.replace('동일한','동일하지 않은')):
   with self.subTest(q=q):self.assertEqual('clarify',execution_gate(q,e.extract_graph_intent(q)))
 def test_repaired_plan_does_not_bypass_independent_audit(self):
  def doc(p):return {'candidates':[{'content':{'parts':[{'text':json.dumps(p)}]}}]}
  a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(plan()),doc({'faithful':False,'issues':['veto']})])
  with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):a.propose_structured_graph_intent(Q,[],s.CONTRACT)
  self.assertEqual(2,a._request.call_count)
