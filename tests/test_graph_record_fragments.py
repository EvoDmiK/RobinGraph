"""Only unique original fragments fully inside proved positive record requests are query framing (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphRecordFragmentsTest(TestCase):
    def test_original_containment_and_counterexamples(self):
        rows=[]
        q='Larus argentatus 종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘.'
        def plan(parts):return dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name='trophic_level',op='eq',value='Omnivore',surface='영양 단계가 Omnivore로')],unresolved=parts,unknown_relation=False)
        def check(label,question,parts,want):
         p=plan(parts);original=copy.deepcopy(p);after,changes=s.reconcile_graph_plan(question,p);actual=execution_gate(question,s.interpret(question,lambda *_:after));assert p==original;assert actual==want,(label,actual,after,changes);rows.append(dict(label=label,question=question,unresolved=parts,actual=actual,changes=changes))
        for fragments in (['확인해 줘'],['기록되어'],['있는지'],['확인해'],['줘'],['기록되어','있는지','확인해 줘'],['종의','확인해 줘']):
         check('contained_original_fragment',q,fragments,'answer')
        check('overlap_with_retained_predicate_is_covered',q,['Omnivore로 기록되어'],'answer')
        for fragments in (['확인해 줘. 겨울에 사는'],['확인해 줘. 별도 조건'],['확인해 줘가 아닌']):
         check('not_contained_or_not_original',q,fragments,'clarify')
        check('repeated_fragment_not_removed',q+' 별도로 확인해 줘.', ['확인해 줘'],'clarify')
        check('negative_record_not_framing',q.replace('기록되어 있는지','기록되어 있지 않은지'),['확인해 줘'],'clarify')
        check('additional_condition_preserved',q+' 겨울에만 사는 새.', ['확인해 줘','겨울에만 사는'],'clarify')
        check('overlap_after_frame',q+' 겨울에만 사는 새.', ['확인해 줘. 겨울에만'],'clarify')
