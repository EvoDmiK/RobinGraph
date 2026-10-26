"""Independent bounded repair fixtures after first actual regression; not fresh holdout."""
import copy,unittest
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.retrieval import graph_condition_extractor as e

def gate(q,p):return execution_gate(q,s.interpret(q,lambda *_:p))
def condition(surface='서식지 밀도가 개방형인 open 조건인'):
 return {'kind':'taxon_traits','taxon':'도요목','conditions':[{'trait_name':'habitat_density_category','op':'eq','value':'open','surface':surface}],'unresolved':[],'unknown_relation':False}
def relation(text='먹이 생태 범주가 ... 와 같은'):
 return {'kind':'shared_diet','species':'청둥오리','conditions':[],'relation_text':text,'unresolved':[],'unknown_relation':False}

class FollowupThreeGuards(unittest.TestCase):
 def test_query_noun_ending_changes_only_unique_original_evidence(self):
  raw=condition();q='도요목에서 서식지 밀도가 개방형인 open 조건으로 새를 찾아줘'
  candidate,changes=s.reconcile_graph_plan(q,raw)
  self.assertTrue(changes);self.assertEqual('answer',gate(q,candidate));self.assertEqual('open',candidate['conditions'][0]['value'])
  for q in ('도요목에서 서식지 밀도가 개방형인 open 조건으로 새를 찾아줘. 서식지 밀도가 개방형인 open 조건으로',
            '도요목에서 서식지 밀도가 개방형인 open 조건만 빼고 새를 찾아줘',
            '도요목에서 서식지 밀도가 개방형인 open 조건이 아닌 새를 찾아줘',
            '도요목에서 서식지 밀도가 조밀형인 dense 조건으로 새를 찾아줘'):
   with self.subTest(q=q):
    candidate,changes=s.reconcile_graph_plan(q,raw);self.assertNotEqual('answer',gate(q,candidate))

 def test_single_ellipsis_is_only_exact_reference_gap_not_wildcard(self):
  raw=relation();q='청둥오리와 비교해서 먹이 생태 범주가 청둥오리와 같은 새를 찾아줘'
  candidate,changes=s.reconcile_graph_plan(q,raw)
  self.assertTrue(changes);self.assertEqual('answer',gate(q,candidate))
  variants=[q.replace('범주가 청둥오리','범주가 까치'),q.replace('와 같은 새','와 다른 새'),
            q.replace('와 같은 새','와 같지 않은 새'),q.replace('범주가 청둥오리','범주가 숲에 사는 청둥오리'),
            q+' 먹이 생태 범주가 청둥오리와 같은',q.replace('범주가 청둥오리','범주가 아니고 먹이 생태 범주가 청둥오리')]
  for text in variants:
   with self.subTest(q=text):
    candidate,changes=s.reconcile_graph_plan(text,raw);self.assertNotEqual('answer',gate(text,candidate))
  for phrase in ('먹이 ... 생태 범주가 ... 와 같은','먹이 생태 범주가 * 와 같은','먹이 생태 범주가 .* 와 같은'):
   with self.subTest(phrase=phrase):
    candidate,changes=s.reconcile_graph_plan(q,relation(phrase));self.assertNotEqual('answer',gate(q,candidate))

 def test_other_species_framing_does_not_consume_extra_restrictions(self):
  q='청둥오리와 같은 식물 종의 열매를 먹는 다른 새를 찾아줘'
  self.assertEqual('insufficient_data',execution_gate(q,e.extract_graph_intent(q)))
  for text in (q.replace('다른 새','다른 먹이도 먹는 새'),q.replace('먹는 다른','먹지 않는 다른'),
               q.replace('다른 새','까치와 다른 새'),q.replace('다른 새','다른 서식지에 사는 새'),
               q.replace('다른 새','겨울에만 사는 다른 새')):
   with self.subTest(q=text):self.assertNotEqual('insufficient_data',execution_gate(text,e.extract_graph_intent(text)))

if __name__=='__main__':unittest.main(verbosity=2)
