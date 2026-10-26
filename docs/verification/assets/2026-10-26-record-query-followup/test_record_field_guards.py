"""Independent source field proof matrix, including shared enum codes."""
import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

def run(q,label,trait,tail,parts):
 p=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name=trait,op='eq',value='Omnivore',surface=label+'가 Omnivore'+tail)],unresolved=parts,unknown_relation=False)
 original=copy.deepcopy(p);c,changes=s.reconcile_graph_plan(q,p);assert original==p
 return execution_gate(q,s.interpret(q,lambda *_:c)),c,changes
class RecordFieldGuardTests(unittest.TestCase):
 def test_shared_enum_source_field_preserved_for_every_segmentation(self):
  for label,correct,wrong in [('영양 단계','trophic_level','trophic_niche'),('먹이 생태 범주','trophic_niche','trophic_level')]:
   q=f'Larus argentatus 종의 {label}가 Omnivore로 기록되어 있는지 확인해 줘.'
   for tail in ('인','로'):
    for parts in ([],['종의'],['확인해 줘'],[f'종의 {label}가 Omnivore로 기록되어 있는지 확인해 줘']):
     with self.subTest(label=label,tail=tail,parts=parts):
      self.assertEqual('answer',run(q,label,correct,tail,parts)[0])
      self.assertEqual('clarify',run(q,label,wrong,tail,parts)[0])
 def test_label_overlap_and_nonlabel_word_boundary(self):
  for label,trait,value in [('서식지 밀도','habitat_density_category','dense'),('서식지','habitat','Forest')]:
   q=f'Larus argentatus 종의 {label}가 {value}로 기록되어 있는지 확인해 줘.'
   p=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name=trait,op='eq',value=value,surface=f'{label}가 {value}인')],unresolved=[q[16:].rstrip('.')],unknown_relation=False)
   # Select the exact full frame, independent of label length.
   p['unresolved']=[q.split(' ',2)[2].rstrip('.')]
   c,_=s.reconcile_graph_plan(q,p);self.assertEqual('answer',execution_gate(q,s.interpret(q,lambda *_:c)))
  for label in ('영양 단계변형','먹이 생태 범주추가'):
   q=f'Larus argentatus 종의 {label}가 Omnivore로 기록되어 있는지 확인해 줘.'
   self.assertEqual('clarify',run(q,label,'trophic_level','인',[q.split(' ',2)[2].rstrip('.')])[0])
