"""Frozen provider outputs and source-form safety checks; no real API/DB calls."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate

CASES = [('F04B', '서식 환경 기록값 Wetland 조건으로 Anas platyrhynchos platyrhynchos 아종 하나를 조회해 줘.', {'kind': 'taxon_traits', 'taxon': 'Anas platyrhynchos platyrhynchos', 'species': None, 'conditions': [{'trait_name': 'habitat', 'op': 'eq', 'value': 'Wetland', 'threshold': None, 'unit': None, 'surface': 'Wetland'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False}), ('contract-category-ratio-unapplied-02', '물총새과 종을 조회하되 diet_category는 Invertebrate로 지정해 줘. 먹이별 비율 차원은 검색 조건에 적용하지 말아 줘.', {'kind': 'taxon_traits', 'taxon': '물총새과', 'species': None, 'conditions': [{'trait_name': 'diet_category', 'op': 'eq', 'value': 'Invertebrate', 'surface': 'diet_category는 Invertebrate로 지정해 줘'}], 'relation_text': None, 'unresolved': [], 'unknown_relation': False})]

class GraphSourceContractFollowupTest(TestCase):
    def test_plant_identity_restatements_and_canonical_negation_dimensions(self):
        for bird in ('황여새', '직박구리', '검은이마직박구리'):
            for relation in ('같은', '동일한'):
                questions=(f'{bird}와 {relation} 식물 종의 열매를 먹는 다른 새를 알려 줘. 열매의 식물 종이 일치해야 해.',
                           f'{bird}가 먹는 열매를 맺는 식물과 {relation} 종의 식물에서 열매를 먹는 다른 새를 찾아 줘.')
                for question in questions:
                    self.assertEqual(execution_gate(question,extract_graph_intent(question)),'insufficient_data')
                    for extra in (' 겨울에 사는 새만.', ' 체중이 300g 이상인 새만.', ' 서울에 사는 새만.'):
                        q=question+extra
                        self.assertEqual(execution_gate(q,extract_graph_intent(q)),'clarify')
        for field in ('habitat', 'trophic_level', 'trophic_niche', 'diet_category'):
            question=f'Alcedo 속의 종을 찾되, {field}가 Marine인 종은 제외해 줘.'
            intent=extract_graph_intent(question)
            self.assertTrue(intent.negation)
            self.assertEqual(intent.kind,'taxon_traits')
            self.assertEqual(execution_gate(question,intent),'clarify')

    def test_ratio_configuration_components_keep_actual_numeric_constraints(self):
        for setting in ('이번 검색 설정에서는 먹이 비율을 조건으로 사용하지 않겠어',
                        '먹이별 비율 차원은 검색 조건에 적용하지 말아 줘'):
            question='물총새과에서 diet_category가 Invertebrate인 종을 찾아 줘. '+setting+'.'
            raw=dict(kind='taxon_traits',taxon='물총새과',conditions=[dict(trait_name='diet_category',op='eq',
                     value='Invertebrate',surface='diet_category가 Invertebrate인')],unresolved=[setting])
            candidate,_=s.reconcile_graph_plan(question,raw)
            self.assertEqual(execution_gate(question,s.interpret(question,lambda *_:candidate)),'answer')
            q=question+' 실제 먹이 비율은 50% 이상이어야 해.'
            self.assertNotEqual(execution_gate(q,s.interpret(q,lambda *_:candidate)),'answer')

    def test_original_typed_assignments_and_canonical_evidence(self):
        for label, question, raw in CASES:
            with self.subTest(label=label):
                before=copy.deepcopy(raw)
                candidate,changes=s.reconcile_graph_plan(question,raw)
                self.assertEqual(execution_gate(question,s.interpret(question,lambda *_:candidate)), 'answer')
                self.assertEqual(before,raw)
                self.assertEqual([{k:v for k,v in c.items() if k!='surface'} for c in raw['conditions']],
                                 [{k:v for k,v in c.items() if k!='surface'} for c in candidate['conditions']])

    def test_separated_exact_plant_relation_retains_additional_predicates(self):
        question='검은이마직박구리와 공통으로 먹는 열매가 있는 다른 새를 알려 줘. 열매를 맺는 식물의 종이 동일한 경우만 포함해 줘.'
        intent=extract_graph_intent(question)
        self.assertEqual(intent.kind,'specific_fruit')
        self.assertEqual([span.text for span in intent.species],['검은이마직박구리'])
        self.assertEqual(execution_gate(question,intent),'insufficient_data')
        for extra in (' 겨울에 사는 새만.', ' 열매를 먹지 않는 새만.', ' 체중이 300g 이상인 새만.', ' 서울에 사는 새만.'):
            with self.subTest(extra=extra):
                q=question+extra
                self.assertEqual(execution_gate(q,extract_graph_intent(q)),'clarify')

    def test_typed_canonical_support_cannot_switch_fields(self):
        _,question,raw=CASES[1]
        positive='물총새과에서 diet_category가 Invertebrate인지 말해줘.'
        candidate=copy.deepcopy(raw)
        candidate['conditions'][0]['surface']='diet_category가 Invertebrate인지 말해줘'
        self.assertEqual(execution_gate(positive,s.interpret(positive,lambda *_:candidate)),'answer')
        for trait in ('trophic_niche','trophic_level'):
            candidate=copy.deepcopy(raw)
            candidate['conditions'][0]['trait_name']=trait
            self.assertNotEqual(execution_gate(question,s.interpret(question,lambda *_:candidate)),'answer')
        for ending in ('지정하지 말아 주세요', '지정하지 마'):
            question='물총새과에서 diet_category는 Invertebrate로 '+ending
            candidate=copy.deepcopy(raw)
            candidate['conditions'][0]['surface']='diet_category는 Invertebrate로 '+ending
            self.assertNotEqual(execution_gate(question,s.interpret(question,lambda *_:candidate)),'answer')
