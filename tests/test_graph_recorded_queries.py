"""Positive source-record evidence and explicit category framing preserve every other constraint (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

CASES = [('E04A', 'Larus argentatus 종의 영양 단계가 Carnivore로 기록되어 있는지 확인해 줘.', {'kind': 'taxon_traits', 'taxon': 'Larus argentatus', 'species': None, 'conditions': [{'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Carnivore', 'surface': '영양 단계가 Carnivore인'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False}), ('E04C', 'Larus argentatus 종의 영양 단계가 Omnivore로 기록되어 있는지 확인해 줘.', {'kind': 'taxon_traits', 'taxon': 'Larus argentatus', 'species': None, 'conditions': [{'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Omnivore', 'surface': '영양 단계가 Omnivore로'}], 'relation_text': None, 'unresolved': ['종의', '기록되어 있는지 확인해 줘'], 'unknown_relation': False}), ('E05B', 'Sturnus 속의 먹이 유형 Invertebrate 기록이 궁금해요. 비율 조건은 적용하지 마세요.', {'kind': 'taxon_traits', 'taxon': 'Sturnus', 'species': None, 'conditions': [{'trait_name': 'diet_category', 'op': 'eq', 'value': 'Invertebrate', 'surface': '먹이 유형 Invertebrate'}], 'relation_text': None, 'unresolved': ['비율 조건은 적용하지 마세요.'], 'unknown_relation': False})]


class GraphRecordedQueryTest(TestCase):
    def test_original_evidence_and_counterexamples(self):
        rows=[]
        def check(label,q,raw,want):
         before=copy.deepcopy(raw);candidate,changes=s.reconcile_graph_plan(q,raw);actual=execution_gate(q,s.interpret(q,lambda *_:candidate));assert raw==before;assert actual==want,(label,actual,candidate,changes);rows.append(dict(label=label,question=q,actual=actual,expected=want,changes=changes))
        for label, question, raw in CASES:
         check(label,question,raw,"answer")
        def tt(surface,value='Carnivore',unresolved=(),taxon='Larus argentatus',field='trophic_level',op='eq'):
         return dict(kind='taxon_traits',taxon=taxon,conditions=[dict(trait_name=field,op=op,value=value,surface=surface)],unresolved=list(unresolved),unknown_relation=False)
        q='Larus argentatus 종의 영양 단계가 Carnivore로 기록되어 있는지 확인해 줘.'
        raw=tt('영양 단계가 Carnivore인')
        for change in ('Omnivore로','Carnivore로 이동하는','Carnivore로 기록되어 있지 않은'):
         check('value_role_negation_not_recovered',q.replace('Carnivore로',change),raw,'clarify')
        check('repeated_evidence_not_recovered',q+' 영양 단계가 Carnivore로 기록되어 있는지 확인해 줘.',raw,'clarify')
        check('rank_word_mismatch',q.replace(' 종의',' 아종의'),tt('영양 단계가 Carnivore로',unresolved=['아종의','기록되어 있는지 확인해 줘']),'clarify')
        check('added_condition_kept',q.replace('확인해 줘.','확인해 줘. 겨울에 사는 종만.'),raw,'clarify')
        q='Larus argentatus 종의 영양 단계가 육식으로 기록되어 있는지 확인해 줘.'
        # Korean adjective uses its original typed value as well, without changing semantic roles.
        # Carnivore label's source vocabulary is 육식.
        raw=tt('영양 단계가 육식인');check('typed_korean_value_record',q,raw,'answer')
        category=tt('먹이 유형 Invertebrate','Invertebrate',['비율 조건은 적용하지 마세요.'],'Sturnus','diet_category')
        q='Sturnus 속의 먹이 유형 Invertebrate 기록이 궁금해요. 비율 조건은 적용하지 마세요.'
        for suffix in ('마세요','말아 주세요','말아 줘'):
         check('explicit_ratio_meta',q.replace('마세요',suffix),{**category,'unresolved':['비율 조건은 적용하지 '+suffix+'.']},'answer')
        share=dict(kind='taxon_traits',conditions=[dict(trait_name='diet_distribution',op='share_gt',value='seed',threshold=0,surface='씨앗을 먹는')],unresolved=['비율 조건은 적용하지 마세요.'],unknown_relation=False)
        check('share_ratio_conflict','씨앗을 먹는 새. 비율 조건은 적용하지 마세요.',share,'clarify')
        check('meta_with_additional_negation',q+' 이 먹이 유형은 아님.',category,'clarify')
        check('unresolved_combined_extra_constraint',q+' 겨울에 사는 종만.',{**category,'unresolved':['비율 조건은 적용하지 마세요. 겨울에 사는 종만.']},'clarify')
