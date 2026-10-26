"""Numeric source evidence keeps operands, field and comparisons unchanged (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphNumericTailTest(TestCase):
    def test_copular_tail_and_boundary_counterexamples(self):
        rows=[]
        def plan(surface,field='body_mass',threshold=200,op='num_gte',unit='g'):
         return dict(kind='taxon_traits',conditions=[dict(trait_name=field,threshold=threshold,op=op,unit=unit,surface=surface)],unresolved=[],unknown_relation=False)
        def check(q,p,want):
         before=copy.deepcopy(p);candidate,changes=s.reconcile_graph_plan(q,p);actual=execution_gate(q,s.interpret(q,lambda *_:candidate));assert actual==want,(q,p,actual,candidate);assert p==before
         rows.append(dict(question=q,expected=want,actual=actual,changes=changes))
        check('0.2kg보다 무겁다는 새를 찾아줘',plan('0.2kg보다 무겁다',op='num_gt'),'answer')
        q='자료를 펼쳐서 체중200g 이상이라는 새를 찾아줘'
        p=plan('체중 200g 이상인');check(q,p,'answer')
        check(q,plan('체중 300g 이상인',threshold=300),'clarify')
        check(q,plan('체중 200g 이하인',op='num_lte'),'clarify')
        check(q,plan('꼬리 길이 200g 이상인',field='tail_length'),'clarify')
        check(q.replace('이상이라는','이상이라는 것은 아니고'),p,'clarify')
        check(q+' 체중200g 이상이라는 새도 찾아줘',p,'clarify')
        check('0.2kg보다 무겁다람쥐를 찾아줘',plan('0.2kg보다 무겁다',op='num_gt'),'clarify')
        wing=plan('날개 길이가 30cm보다 짧은',field='wing_length',threshold=300,op='num_lt',unit='mm')
        check('날개 길이가 30cm보다 짧은지 궁금해',wing,'answer')
        check('날개 길이가 30cm보다 짧은지렁이를 찾아줘',wing,'clarify')
        for denial in ('아니다','아니야','아닙니다','아니에요'):
         q='자료를 펼쳐서 체중200g 이상이라는 것은 '+denial
         check(q,plan('체중 200g 이상인'),'clarify')
         check(q,plan('체중200g 이상'),'clarify')
        category=dict(kind='taxon_traits',conditions=[dict(trait_name='diet_category',op='eq',value='PlantSeed',surface='먹이 유형이 식물·씨앗인')],unresolved=[],unknown_relation=False)
        check('먹이 유형이 식물·씨앗인 새. 비율 조건을 뜻하는 건 아니야.',category,'answer')
        check('먹이 유형이 식물·씨앗인 새. 비율 조건을 뜻하는 건 아니야. 이 먹이 유형은 아니다.',category,'clarify')
        for word,op in [('길다','num_gt'),('짧다','num_lt'),('가볍다','num_lt'),('크다','num_gt'),('작다','num_lt')]:
         assert e._op('보다 '+word)==op
         rows.append(dict(comparator=word,op=op))
