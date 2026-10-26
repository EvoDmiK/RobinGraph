"""Unique source scaffolds do not authorise changed predicates or extra conditions (mock plans)."""
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphSourceScaffoldsTest(TestCase):
    def test_unique_evidence_and_mutations(self):
        rows=[]
        def check(label,q,raw,want):
         candidate,changes=s.reconcile_graph_plan(q,raw);actual=execution_gate(q,s.interpret(q,lambda *_:candidate));rows.append(dict(label=label,expected=want,actual=actual,changes=changes));assert actual==want,(label,actual,candidate)
        raw=dict(kind='taxon_traits',conditions=[dict(trait_name='habitat_density_category',op='eq',value='open',surface='서식지 밀도가 개방형인 open 조건인')],unresolved=[],unknown_relation=False)
        check('condition_scaffold','서식지 밀도가 개방형인 open 조건으로 새를 찾아줘',raw,'answer')
        q='서식지 밀도가 개방형인 open 조건으로, 서식지 밀도가 개방형인 open 조건으로 새를 찾아줘'
        check('repeated_condition_prefix_not_recovered',q,raw,'clarify')
        wrong={**raw,'conditions':[{**raw['conditions'][0],'surface':'서식지 밀도가 빽빽한 closed 조건인'}]}
        check('different_content_not_recovered','서식지 밀도가 개방형인 open 조건으로 새를 찾아줘',wrong,'clarify')
        raw=dict(kind='shared_diet',species='황조롱이',relation_text='먹이 생태 범주가 ... 와 같은',conditions=[],unresolved=['황조롱이는 빼고'],unknown_relation=False)
        q='황조롱이는 빼고 먹이 생태 범주가 황조롱이와 같은 다른 새를 찾아줘'
        check('exact_reference_placeholder',q,raw,'answer')
        check('other_reference_not_substituted',q.replace('황조롱이와','직박구리와'),raw,'clarify')
        check('new_relation_content_not_ignored',q.replace('황조롱이와','겨울에 황조롱이와'),raw,'clarify')
        for extra in ('',' 먹지 않는',' 겨울에 사는'):
         q='해안에 사는 새 중 황조롱이와 정확히 같은 식물 종의 열매를 먹는 다른 새'+extra
         i=e.extract_graph_intent(q);g=execution_gate(q,i);want='clarify'if extra else'insufficient_data';assert g==want,(q,g,i);rows.append(dict(label='specific_food_other_framing'+extra,actual=g,expected=want))
        for reference, expected in (('Falco tinnunculus','insufficient_data'),('Falco tinnunculus interstinctus','insufficient_data'),('Falco','clarify')):
         q=reference+'와 같은 식물 종의 열매를 먹는 다른 새는?'
         intent=e.extract_graph_intent(q);actual=execution_gate(q,intent);assert actual==expected,(q,actual,intent)
         if expected == 'insufficient_data': assert intent.species[0].text == reference
         rows.append(dict(label='scientific_reference_shape',question=q,expected=expected,actual=actual))
        for extra in (' 먹지 않는',' 겨울에 사는'):
         q='Falco tinnunculus와 같은 식물 종의 열매를 먹는 다른 새'+extra
         assert execution_gate(q,e.extract_graph_intent(q))=='clarify'
         rows.append(dict(label='scientific_reference_extra_condition',question=q,expected='clarify',actual='clarify'))
