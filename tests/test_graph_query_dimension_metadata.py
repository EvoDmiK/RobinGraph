"""Unused query dimensions differ from biological NOT; raw source evidence and audit still govern execution."""
import json
import unittest
from unittest.mock import Mock

from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


def category_plan(surface, unresolved=()):
    return {'kind': 'taxon_traits', 'conditions': [
        {'trait_name': 'diet_category', 'op': 'eq', 'value': 'Omnivore', 'surface': surface}],
        'unresolved': list(unresolved), 'unknown_relation': False}


class QueryDimensionMetadataTests(unittest.TestCase):
    def test_explicit_query_setting_grammar_reaches_interpreter(self):
        settings = ('비율 조건을 뜻하는 건 아니야', '비율 조건은 적용하지 마세요',
                    '먹이 구성 비율은 검색 조건에 넣지 마', '비율 수치로 걸러 달라는 뜻은 아닙니다',
                    '비율 제한은 적용하지 말아 줘', '구성비에 관한 조건은 사용하지 않아',
                    '먹이 비중은 조회 제한에 사용하지 마세요')
        for setting in settings:
            q = '먹이 유형이 잡식인 새를 찾아줘. ' + setting + '.'
            raw = category_plan('먹이 유형이 잡식인', [setting])
            candidate, _ = s.reconcile_graph_plan(q, raw)
            provider = Mock(return_value=candidate)
            with self.subTest(setting=setting):
                self.assertEqual('answer', execution_gate(q, s.graph_intent_handler(q, provider=provider)))
                provider.assert_called_once()

    def test_biological_conditions_and_incompatible_ratio_remain_held(self):
        for actual in ('먹이 유형은 잡식이 아닙니다', '곤충을 먹지 않는 새만', '겨울에만 사는 새만',
                       '서울에서 관찰된 종만', '먹이 구성 비율 30% 이상인 새만'):
            q = '먹이 유형이 잡식인 새. 비율 조건은 적용하지 마세요. ' + actual
            raw = category_plan('먹이 유형이 잡식인', ['비율 조건은 적용하지 마세요', actual])
            candidate, _ = s.reconcile_graph_plan(q, raw)
            with self.subTest(actual=actual):
                self.assertEqual('clarify', execution_gate(q, s.interpret(q, lambda *_: candidate)))
        q = '씨앗을 먹는 새. 비율 수치로 걸러 달라는 뜻은 아닙니다.'
        raw = {'kind': 'taxon_traits', 'conditions': [{'trait_name': 'diet_distribution', 'op': 'share_gt',
               'value': 'seed', 'threshold': 0, 'surface': '씨앗을 먹는'}], 'unresolved': [], 'unknown_relation': False}
        self.assertEqual('clarify', execution_gate(q, s.interpret(q, lambda *_: raw)))

    def test_literal_surfaces_and_independent_audit_are_mandatory(self):
        q = '영양 단계 기록값이 Omnivore인지 Turdus merula 종에 대해 확인하고 싶어요.'
        raw = {'kind': 'taxon_traits', 'taxon': 'Turdus merula', 'conditions': [
            {'trait_name': 'trophic_level', 'op': 'eq', 'value': 'Omnivore',
             'surface': '영양 단계 기록값이 Omnivore인지'}], 'unresolved': [], 'unknown_relation': False}
        self.assertEqual('answer', execution_gate(q, s.interpret(q, lambda *_: raw)))
        wrong = {**raw, 'conditions': [{**raw['conditions'][0], 'surface': '영양 단계가 Omnivore인지'}]}
        self.assertEqual('clarify', execution_gate(q, s.interpret(q, lambda *_: wrong)))

        def document(payload):
            return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}

        q = '먹이 유형이 잡식인 새. 비율 수치로 걸러 달라는 뜻은 아닙니다.'
        model = GeminiAnswerer('test-key')
        model._request = Mock(side_effect=[document(category_plan('먹이 유형이 잡식인')),
                                           document({'faithful': False, 'issues': ['unsupported predicate']})])
        with self.assertRaises(GeminiAnswerError):
            model.propose_structured_graph_intent(q, [], s.CONTRACT)
