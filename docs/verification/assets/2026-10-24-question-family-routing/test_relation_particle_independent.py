"""Independent bounded surface-repair tests; mocked provider only."""
import copy,json,unittest
from unittest.mock import Mock
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
Q='쇠백로와 같은 먹이 생태 범주인 다른 새를 찾아줘.'
RAW={'kind':'shared_diet','species':'쇠백로','conditions':[],'relation_text':'과 같은 먹이 생태 범주인','unresolved':[],'unknown_relation':False}
def doc(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
class ParticleReview(unittest.TestCase):
 def test_unique_exact_original_only_preserves_semantics(self):
  before=copy.deepcopy(RAW);candidate,proof=s.reconcile_graph_plan(Q,RAW)
  self.assertEqual(RAW,before);self.assertEqual(candidate['relation_text'],'쇠백로와 같은 먹이 생태 범주인')
  self.assertEqual({k:v for k,v in RAW.items() if k!='relation_text'},{k:v for k,v in candidate.items() if k!='relation_text'})
  self.assertEqual(proof[0]['rule'],'reference_particle')
 def test_repeated_surface_other_reference_and_remaining_condition_never_recovered(self):
  for q in (Q+' 쇠백로와 같은 먹이 생태 범주인 새도.',Q.replace('쇠백로','까치'),Q+' 몸무게가 200g 초과인 새만.',Q.replace('같은','다른'),Q.replace('범주인','범주인듯한')):
   with self.subTest(question=q):self.assertEqual(s.reconcile_graph_plan(q,RAW),(RAW,[]))
  raw={**copy.deepcopy(RAW),'unresolved':['숲에 사는']}
  self.assertEqual(s.reconcile_graph_plan(Q+' 숲에 사는 새.',raw),(raw,[]))
 def test_audit_false_still_stops_after_exact_repair(self):
  a=GeminiAnswerer('dummy',urlopen=Mock());a._request=Mock(side_effect=[doc(RAW),doc({'faithful':False,'issues':['원문 관계 재확인 필요']})])
  with self.assertRaises(GeminiAnswerError):a.propose_structured_graph_intent(Q,[],s.CONTRACT)
  self.assertEqual(a._request.call_count,2)
  payload=json.loads(a._request.call_args_list[1].args[0].split('\n')[-1]);self.assertEqual(payload['original_proposal'],RAW)
  self.assertEqual(payload['proposed_plan']['relation_text'],'쇠백로와 같은 먹이 생태 범주인')
if __name__=='__main__':unittest.main(verbosity=2)
