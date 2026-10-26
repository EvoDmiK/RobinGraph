"""Comparison endings share one bounded grammar, preserving content-word and denial guards (mock plans)."""
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphPredicateTailsTest(TestCase):
    def test_comparison_particle_quotation_matrix(self):
        rows=[]
        def plan(surface,op):return dict(kind='taxon_traits',conditions=[dict(trait_name='body_mass',op=op,threshold=200,unit='g',surface=surface)],unresolved=[],unknown_relation=False)
        for word,op in [('초과','num_gt'),('미만','num_lt'),('이상','num_gte'),('이하','num_lte')]:
         for tail in ('인','이라는','이라고','이고','이며','이다','입니다','이면서','라는','라고','으로','로','의','은','는','이','가','을','를','에서','에','고','지'):
          q='체중 200g '+word+tail+' 새를 찾아줘';p=plan('체중 200g '+word,op);gate=execution_gate(q,s.interpret(q,lambda *_:p));assert gate=='answer',(q,gate);rows.append(dict(question=q,gate=gate))
        for tail in ('라는사과','로빈','으로만드는','의자','는지렁이','지고릴라','이라는내용없는','라는 것은 아니다','라고는 아니야'):
         q='체중 200g 이상'+tail+' 새를 찾아줘';p=plan('체중 200g 이상','num_gte');gate=execution_gate(q,s.interpret(q,lambda *_:p));assert gate=='clarify',(q,gate);rows.append(dict(question=q,gate=gate))
        for word,op in [('초과','num_gt'),('미만','num_lt'),('이상','num_gte'),('이하','num_lte')]:
         q='자료를 펼쳐서 체중200g '+word+'로 새를 찾아줘';p=plan('체중 200g '+word+'이라는',op);candidate,changes=s.reconcile_graph_plan(q,p);gate=execution_gate(q,s.interpret(q,lambda *_:candidate));assert gate=='answer',(q,gate,changes);rows.append(dict(question=q,gate=gate,changes=changes))
