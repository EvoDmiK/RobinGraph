"""Segmentation does not change the proof: every unresolved character needs retained original evidence or framing."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphRecordCoverageTest(TestCase):
    def test_full_partition_overlap_and_boundary_matrix(self):
        rows=[]
        q='Larus argentatus 종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘.'
        whole='종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘';words=whole.split()
        def plan(parts, surface='영양 단계가 Omnivore인',value='Omnivore'):
         return dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name='trophic_level',op='eq',value=value,surface=surface)],unresolved=parts,unknown_relation=False)
        def check(label,question,raw,want):
         before=copy.deepcopy(raw);after,changes=s.reconcile_graph_plan(question,raw);actual=execution_gate(question,s.interpret(question,lambda *_:after));assert raw==before;assert actual==want,(label,actual,raw,after,changes);rows.append(dict(label=label,actual=actual,unresolved=raw['unresolved']))
        for surface in ('영양 단계가 Omnivore인','영양 단계가 Omnivore로'):
         for mask in range(1 << (len(words)-1)):
          parts=[];start=0
          for i in range(len(words)-1):
           if mask & (1<<i):parts.append(' '.join(words[start:i+1]));start=i+1
          parts.append(' '.join(words[start:]));check('all_contiguous_partitions',q,plan(parts,surface),'answer')
         for a in range(len(words)):
          for b in range(a+1,len(words)+1):
           check('all_single_contiguous_fragments',q,plan([' '.join(words[a:b])],surface),'answer')
        check('overlapping_segments',q,plan([' '.join(words[:5]),' '.join(words[2:])]),'answer')
        check('uncovered_one_character',q+' X',plan([whole+'. X']),'clarify')
        check('extra_condition',q+' 겨울에만 사는 종.',plan([whole+'. 겨울에만 사는']),'clarify')
        check('whole_selected_query',q,plan([q.rstrip('.')]),'answer')
        check('outside_scope_boundary','조건X '+q,plan(['조건X '+q.rstrip('.')]),'clarify')
        check('value_mismatch',q,plan([whole],surface='영양 단계가 Omnivore로',value='Carnivore'),'clarify')
        check('source_negative',q.replace('기록되어 있는지','기록되어 있지 않은지'),plan([whole]),'clarify')
        check('duplicate_unresolved_source',q+' '+whole,plan([whole]),'clarify')
        check('symbol_is_not_punctuation',q+' +',plan([whole+'. +']),'clarify')
        for rank_gap in (' ', '\t', '\n', ' , ', ' ; ', ' … '):
         for record_gap in (' ', '\t', '\n'):
          question=q.replace('종의 영양', '종의'+rank_gap+'영양').replace('로 기록', '로'+record_gap+'기록')
          check('whitespace_punctuation_gaps',question,plan([question.rstrip('.')]),'answer')
        check('one_uncovered_middle_character',q.replace('종의 영양','종의 X 영양'),plan([q.replace('종의 영양','종의 X 영양').rstrip('.')]),'clarify')
