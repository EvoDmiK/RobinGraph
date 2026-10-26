"""Feedback regressions from frozen H05B/H06B plus condition-preservation contrasts."""
import copy
import json
import unittest
from unittest.mock import Mock

from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphTerminalRequestsTest(unittest.TestCase):
    def test_terminal_request_only_is_reconciled_across_numeric_habitat_and_relation(self):
        cases = [
            ('Anas platyrhynchos platyrhynchos 아종의 날개 길이가 30cm보다 짧은지',
             {'kind': 'taxon_traits', 'taxon': 'Anas platyrhynchos platyrhynchos', 'conditions': [
                 {'trait_name': 'wing_length', 'op': 'num_lt', 'threshold': 300, 'unit': 'mm',
                  'surface': '날개 길이가 30cm보다 짧은'}]}),
            ('Corvidae 중 숲이 서식지로 기록되어 있는 종을',
             {'kind': 'taxon_traits', 'taxon': 'Corvidae', 'conditions': [
                 {'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'surface': '숲이 서식지로 기록되어 있는'}]}),
            ('Ardea cinerea 자신은 빼고, 먹이 생태 범주가 같은 종을',
             {'kind': 'shared_diet', 'species': 'Ardea cinerea', 'relation_text': '먹이 생태 범주가 같은',
              'conditions': []})]
        for stem, plan in cases:
            for ending in ('궁금해', '궁금해.', '궁금합니다', '궁금합니다!', '알고 싶어', '알려줘?', '보여 줘', '찾아 주세요'):
                q = stem + ' ' + ending + '.'
                raw = {**copy.deepcopy(plan), 'unresolved': [ending]}
                before = copy.deepcopy(raw)
                with self.subTest(q=q):
                    candidate, changes = sgi.reconcile_graph_plan(q, raw)
                    self.assertEqual(before, raw)
                    self.assertEqual([], candidate['unresolved'])
                    self.assertEqual('terminal_request', changes[0]['rule'])
                    self.assertEqual(raw['conditions'], candidate['conditions'])
                    self.assertEqual('answer', execution_gate(q, sgi.interpret(q, lambda *_: candidate)))

    def test_nonterminal_attached_negative_and_actual_conditions_are_never_deleted(self):
        stem = 'Anas platyrhynchos platyrhynchos 아종의 날개 길이가 30cm보다 짧은지 '
        base = {'kind': 'taxon_traits', 'taxon': 'Anas platyrhynchos platyrhynchos', 'conditions': [
            {'trait_name': 'wing_length', 'op': 'num_lt', 'threshold': 300, 'unit': 'mm',
             'surface': '날개 길이가 30cm보다 짧은'}]}
        cases = [('궁금해하지만 다른 조건도 있어', ['궁금해']), ('궁금해도', ['궁금해']),
                 ('궁금해하는', ['궁금해']), ('안궁금해', ['궁금해']),
                 ('궁금해, 궁금해', ['궁금해']), ('궁금해. 몸무게 100g 이상', ['궁금해']),
                 ('밤에만 활동하는 종을 알려줘', ['밤에만 활동하는 종을 알려줘']),
                 ('날개가 20cm인 것은 빼고 궁금해', ['궁금해']),
                 ('새로운 제한도 궁금해', ['새로운 제한도', '궁금해'])]
        for suffix, unresolved in cases:
            q, raw = stem + suffix, {**copy.deepcopy(base), 'unresolved': unresolved}
            with self.subTest(q=q):
                self.assertEqual((raw, []), sgi.reconcile_graph_plan(q, raw))
                self.assertNotEqual('answer', execution_gate(q, sgi.interpret(q, lambda *_: raw)))

    def test_self_exclusion_punctuation_enters_existing_validation(self):
        for name in ('Ardea cinerea', '청둥오리'):
            for punctuation in (',', '.', '!', '?', ' '):
                q = f'{name} 자신은 빼고{punctuation} 먹이 생태 범주가 같은 종을 알려줘.'
                raw = {'kind': 'shared_diet', 'species': name, 'relation_text': '먹이 생태 범주가 같은'}
                provider = Mock(return_value=raw)
                result = sgi.graph_intent_handler(q, provider=provider)
                with self.subTest(q=q):
                    provider.assert_called_once()
                    self.assertEqual('answer', execution_gate(q, result))
                    self.assertEqual(name, result.species[0].text)

    def test_comma_does_not_erase_other_exclusions_or_restrictions(self):
        raw = {'kind': 'shared_diet', 'species': '청둥오리', 'relation_text': '먹이 생태 범주가 같은'}
        for q in ('청둥오리와 먹이 생태 범주가 같은 종 중 까치는 빼고, 알려줘.',
                  '청둥오리 자신은 빼고, 먹이 생태 범주가 같지 않은 종을 알려줘.',
                  '청둥오리 자신은 빼고, 먹이 생태 범주가 같은 종 중 밤에만 활동하는 종을 알려줘.',
                  '청둥오리 자신은 빼고, 먹이 생태 범주가 같은 종 중 몸무게가 100g인 종을 알려줘.'):
            with self.subTest(q=q):
                result = sgi.graph_intent_handler(q, provider=Mock(return_value=raw))
                self.assertNotEqual('answer', execution_gate(q, result))

    def test_reconciled_request_is_still_audited_and_false_never_retries(self):
        q = 'Ardea cinerea 자신은 빼고, 먹이 생태 범주가 같은 종이 궁금해.'
        raw = {'kind': 'shared_diet', 'species': 'Ardea cinerea', 'relation_text': '먹이 생태 범주가 같은',
               'unresolved': ['궁금해']}
        def document(payload):
            return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}
        answerer = GeminiAnswerer('dummy', urlopen=Mock())
        answerer._request = Mock(side_effect=[document(raw), document({'faithful': False, 'issues': ['조건 불일치']})])
        with self.assertRaisesRegex(GeminiAnswerError, 'did not pass semantic audit'):
            answerer.propose_structured_graph_intent(q, [], sgi.CONTRACT)
        self.assertEqual(2, answerer._request.call_count)
        payload = json.loads(answerer._request.call_args_list[1].args[0].split('\n')[-1])
        self.assertEqual(raw, payload['original_proposal'])
        self.assertEqual([], payload['proposed_plan']['unresolved'])

    def test_relation_particle_recovery_requires_exact_adjacent_reference_and_predicate(self):
        for name, actual, proposed in [('쇠백로', '와', '과'), ('까치', '랑', '하고'), ('Ardea cinerea', '와', '랑')]:
            q = f'{name}{actual} 같은 먹이 생태 범주인 다른 새를 찾아줘.'
            raw = {'kind':'shared_diet','species':name,'conditions':[], 'relation_text':proposed+' 같은 먹이 생태 범주인'}
            result, changes = sgi.reconcile_graph_plan(q, raw)
            self.assertEqual('reference_particle',changes[0]['rule'])
            self.assertEqual(name+actual+' 같은 먹이 생태 범주인',result['relation_text'])
            self.assertEqual('answer',execution_gate(q,sgi.interpret(q,lambda *_:result)))
        for q, reference, phrase in [
            ('쇠백로와 다른 먹이 생태 범주인 새', '쇠백로', '과 같은 먹이 생태 범주인'),
            ('쇠백로와 같은 먹이 생태 범주인 새', '까치', '과 같은 먹이 생태 범주인'),
            ('쇠백로와 같은 먹이 생태 범주인 새 중 밤에만 사는 새', '쇠백로', '과 같은 먹이 생태 범주인'),
            ('쇠백로와 같은 먹이를 먹는 새', '쇠백로', '과 같은 먹이를 먹는')]:
            raw={'kind':'shared_diet','species':reference,'conditions':[],'relation_text':phrase}
            self.assertEqual((raw,[]),sgi.reconcile_graph_plan(q,raw))
