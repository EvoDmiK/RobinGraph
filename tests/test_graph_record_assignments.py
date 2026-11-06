"""Categorical record assignment evidence is independent of request verbs, without changing predicates (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate

CASES = [('F01B', '영양 단계 기록값이 Omnivore인지 Turdus merula 종에 대해 확인하고 싶어요.', {'kind': 'taxon_traits', 'taxon': 'Turdus merula', 'species': None, 'conditions': [{'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Omnivore', 'surface': '영양 단계가 Omnivore인'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False}), ('F01C', 'Turdus merula라는 종의 영양 단계가 Carnivore로 기록되어 있는지 조회해 주세요.', {'kind': 'taxon_traits', 'taxon': 'Turdus merula', 'species': None, 'conditions': [{'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Carnivore', 'surface': '영양 단계가 Carnivore인'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False}), ('F04A', 'Anas platyrhynchos platyrhynchos 아종의 서식 환경이 Wetland로 기록되어 있는지 확인해 주세요.', {'kind': 'taxon_traits', 'taxon': 'Anas platyrhynchos platyrhynchos', 'species': None, 'conditions': [{'trait_name': 'habitat', 'op': 'eq', 'value': 'Wetland', 'surface': 'Wetland로'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False})]


class GraphRecordAssignmentTest(TestCase):
    def test_original_field_assignment_and_guard_matrix(self):
        rows=[]
        def check(label,q,p,want):
         before=copy.deepcopy(p);after,changes=s.reconcile_graph_plan(q,p);actual=execution_gate(q,s.interpret(q,lambda *_:after));assert p==before;assert actual==want,(label,q,actual,after,changes);assert [{k:v for k,v in c.items()if k!='surface'}for c in p['conditions']]==[{k:v for k,v in c.items()if k!='surface'}for c in after['conditions']];rows.append(dict(label=label,question=q,actual=actual,changes=changes))
        for label, question, raw in CASES:
         check(label,question,raw,"answer")
        def plan(surface,field='trophic_level',value='Omnivore',scope='Turdus merula'):
         return dict(kind='taxon_traits',taxon=scope,conditions=[dict(trait_name=field,op='eq',value=value,surface=surface)],unresolved=[],unknown_relation=False)
        for verb in ('확인해 줘','조회해 주세요','살펴보고 싶어요','알고 싶어','검토 부탁해'):
         q='Turdus merula 종의 영양 단계가 Omnivore로 기록되어 있는지 '+verb
         check('request_verb_independent',q,plan('영양 단계가 Omnivore인'),'answer')
         check('literal_short_expansion',q,plan('Omnivore로'),'answer')
        for prohibition in ('확인하지 마', '조회하지 마세요', '검색하지 말아 줘'):
         q='Turdus merula 종의 영양 단계가 Omnivore로 기록되어 있는지 '+prohibition
         check('prohibited_read_is_not_recovered',q,plan('영양 단계가 Omnivore인'),'clarify')
        q='Turdus merula 종의 영양 단계가 Omnivore로 기록되어 있는지 조회해 주세요'
        for surface in ('Omnivore로','영양 단계가 Omnivore인'):
         for field in ('trophic_niche','diet_category'):
          check('wrong_field_same_enum',q,plan(surface,field),'clarify')
         check('wrong_value',q,plan(surface.replace('Omnivore','Carnivore'),value='Carnivore'),'clarify')
         check('repeated_value',q+' Omnivore',plan(surface),'clarify')
         check('new_uncovered_predicate',q+' 겨울에 사는 새만',plan(surface),'clarify')
         mutated=q.replace('기록되어 있는지','기록해 줘');raw_mutation=plan(surface);assert s.reconcile_graph_plan(mutated,raw_mutation)==(raw_mutation,[]);rows.append(dict(label='mutation_is_not_new_recovery',changes=[]))
        q='Turdus merula 종의 영양 단계가 Omnivore로 기록되어 있지 않은 새는?'
        p=plan('영양 단계가 Omnivore인');called=[]
        def provider(*_):called.append(True);return p
        intent=s.graph_intent_handler(q,provider=provider);assert execution_gate(q,intent)!='answer'and not called;rows.append(dict(label='negative_record_guard',actual='hold_before_provider'))
        for q in ('Omnivore로 기록되어 있는지 조회해 줘','영양 단계가 Omnivore로 기록되어 있는지, 먹이 생태 범주가 Omnivore로 기록되어 있는지 조회해 줘'):
         p=plan('Omnivore로',scope=None);check('missing_or_dual_field',q,p,'clarify')
        for leading in (' ', '\t', '\n'):
         question=leading+'Turdus merula 종의 영양 단계가 Omnivore로 기록되어 있는지 조회해 주세요'
         check('absolute_source_offset',question,plan('영양 단계가 Omnivore인'),'answer')
        for prefix,field,label in (('가짜','trophic_level','영양 단계'),('반','trophic_level','영양 단계'),('유사','diet_category','먹이 유형')):
         question='Turdus merula 종의 '+prefix+label+'가 Omnivore로 기록되어 있는지 조회해 주세요'
         check('field_left_word_boundary',question,plan(label+'가 Omnivore인',field=field),'clarify')
