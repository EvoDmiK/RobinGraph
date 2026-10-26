"""Independent union-coverage repair boundaries; injected plans only."""
import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
Q='Larus argentatus 종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘.'
def gate(q,fragment,value='Omnivore',trait='trophic_level',taxon='Larus argentatus'):
 p=dict(kind='taxon_traits',taxon=taxon,conditions=[dict(trait_name=trait,op='eq',value=value,surface='영양 단계가 Omnivore인')],unresolved=[fragment],unknown_relation=False)
 before=copy.deepcopy(p);c,changes=s.reconcile_graph_plan(q,p);assert p==before
 return execution_gate(q,s.interpret(q,lambda *_:c)),c,changes
F='종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘'
class RecordUnionGuardTests(unittest.TestCase):
 def test_proved_scope_evidence_request_union(self):
  for part in (F,'영양 단계가 Omnivore로 기록되어 있는지 확인해 줘','종의 영양 단계가 Omnivore로','Omnivore로 기록되어 있는지'):
   with self.subTest(part=part):self.assertEqual('answer',gate(Q,part)[0])
 def test_gaps_extra_taxon_and_unknown_condition_cannot_be_consumed(self):
  for q,f in [(Q.replace('종의 영양','종의 겨울에 사는 영양'),F.replace('종의 영양','종의 겨울에 사는 영양')),(Q.replace('종의 영양','종의 Corvus corax 영양'),F.replace('종의 영양','종의 Corvus corax 영양')),(Q.replace('종의 영양','종의 체중 200g 이상인 영양'),F.replace('종의 영양','종의 체중 200g 이상인 영양')),(Q+' 부리 길이가 30mm 이상인 종.',F),(Q.replace('기록되어','아니라고 기록되어'),F.replace('기록되어','아니라고 기록되어')),(Q+Q,F),(Q.replace('종의','아종의'),F.replace('종의','아종의'))]:
   with self.subTest(q=q):self.assertEqual('clarify',gate(q,f)[0])
 def test_changed_typed_value_field_reference_cannot_be_repaired(self):
  for kw in ({'value':'Carnivore'},{'trait':'trophic_niche'},{'taxon':'Larus'},{'taxon':'Larus fuscus'}):
   with self.subTest(kw=kw):self.assertEqual('clarify',gate(Q,F,**kw)[0])
 def test_original_negative_or_absent_fragment_is_not_covered(self):
  for q,f in [(Q.replace('있는지','있지 않은지'),F.replace('있는지','있지 않은지')),(Q.replace('확인해 줘','확인하지 마'),F.replace('확인해 줘','확인하지 마')),(Q,F+' 겨울에만'),(Q,F+' Corvus corax')]:
   with self.subTest(q=q,f=f):self.assertEqual('clarify',gate(q,f)[0])
