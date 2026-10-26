import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
Q='Larus argentatus 종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘.'
def gate(q,parts):
 p=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name='trophic_level',op='eq',value='Omnivore',surface='영양 단계가 Omnivore로')],unresolved=parts,unknown_relation=False)
 before=copy.deepcopy(p);c,_=s.reconcile_graph_plan(q,p);assert p==before
 return execution_gate(q,s.interpret(q,lambda *_:c))
class RecordFragmentGuardTests(unittest.TestCase):
 def test_only_positive_proved_frame_fragments(self):
  for part in ('확인해 줘','기록되어 있는지','있는지 확인해','확인해 줘.'):
   with self.subTest(part=part):self.assertEqual('answer',gate(Q,[part]))
 def test_negative_repeated_or_other_conditions_never_disappear(self):
  for q,parts in [(Q.replace('있는지','있지 않은지'),['확인해 줘']), (Q+' 확인해 줘.', ['확인해 줘']), (Q+' 체중 100g 이상인 종.', ['확인해 줘','체중 100g 이상인']), (Q,['Omnivore로 기록되어']), (Q+' 청둥오리를 제외해.', ['확인해 줘','청둥오리를 제외해']), (Q.replace('기록되어','아니라고 기록되어'),['확인해 줘']), (Q+' 비율 20% 초과인 기록.', ['확인해 줘','비율 20% 초과인']), (Q+' Corvus corax도 포함해.', ['확인해 줘'])]:
   with self.subTest(q=q,parts=parts):self.assertEqual('clarify',gate(q,parts))
