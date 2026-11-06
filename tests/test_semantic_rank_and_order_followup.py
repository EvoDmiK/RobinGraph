"""Feedback-exposed rank-suffix and incomplete-order regressions; guards remain fail-closed."""
import copy
import json
import unittest
from unittest.mock import Mock

from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_intent_schema import execution_gate


def plan(taxon):
    return {'kind': 'taxon_traits', 'taxon': taxon, 'conditions': [
        {'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'surface': '숲이 서식지로 기록되어'},
        {'trait_name': 'diet_distribution', 'op': 'share_gt', 'value': 'fruit', 'threshold': 0,
         'surface': '열매도 먹는'}], 'unresolved': [], 'unknown_relation': False}


def question(taxon):
    return f'{taxon} 안에서 숲이 서식지로 기록되어 있고 열매도 먹는 종을 골라 줘.'


def document(payload):
    return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}


class SemanticRankAndOrderFollowupTests(unittest.TestCase):
    def test_exact_catalog_scope_recovers_one_dropped_rank_suffix_only(self):
        for full in ('까마귀속', '까치속', '오리과', '참새목'):
            raw = plan(full[:-1]);before = copy.deepcopy(raw)
            candidate, changes = sgi.reconcile_graph_plan(question(full), raw)
            with self.subTest(full=full):
                self.assertEqual(before, raw)
                self.assertEqual(full, candidate['taxon'])
                self.assertEqual([{'field':'taxon','rule':'rank_suffix','before':full[:-1],'after':full}],changes)
                self.assertEqual(raw['conditions'],candidate['conditions'])
                self.assertEqual('answer',execution_gate(question(full),sgi.interpret(question(full),lambda *_:candidate)))

    def test_different_unknown_multiple_or_repeated_scopes_are_not_repaired(self):
        cases = [(question('까마귀속'), plan('까마귀과')),
                 (question('까마귀속'), plan('까')),
                 (question('까마귀속'), plan('Corvus')),
                 (question('가상새속'), plan('가상새')),
                 (question('까마귀속')+' 까마귀속 자료만.',plan('까마귀')),
                 (question('까마귀속')+' 까마귀도 알려줘.',plan('까마귀')),
                 (question('까마귀속')+' 오리과도 포함해.',plan('까마귀')),
                 (question('까마귀'),plan('까마귀'))]
        for q,raw in cases:
            with self.subTest(q=q,raw=raw):
                self.assertEqual((raw,[]),sgi.reconcile_graph_plan(q,raw))
        raw={'kind':'shared_diet','species':'까마귀','relation_text':'먹이 생태가 같은','conditions':[]}
        q='까마귀속과 먹이 생태가 같은 새를 찾아줘'
        self.assertEqual((raw,[]),sgi.reconcile_graph_plan(q,raw))

    def test_rank_recovery_still_requires_full_validation_and_independent_audit(self):
        raw=plan('까마귀');raw['conditions'][0]['value']='Wetland'
        self.assertEqual((raw,[]),sgi.reconcile_graph_plan(question('까마귀속'),raw))
        answerer=GeminiAnswerer('dummy',urlopen=Mock())
        answerer._request=Mock(side_effect=[document(plan('까마귀')),document({'faithful':False,'issues':['scope disputed']})])
        with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):
            answerer.propose_structured_graph_intent(question('까마귀속'),[],sgi.CONTRACT)
        self.assertEqual(2,answerer._request.call_count)
        audit=json.loads(answerer._request.call_args_list[1].args[0].split('\n')[-1])
        self.assertEqual('까마귀',audit['original_proposal']['taxon'])
        self.assertEqual('까마귀속',audit['proposed_plan']['taxon'])

    def test_order_fruit_with_residual_conditions_reaches_semantic_without_losing_them(self):
        for order in ('참새목','기러기목'):
            q=f'{order}에서 숲이 서식지로 기록돼 있으며 열매도 먹는 새를 찾아줘.'
            lexical=sgi.extract_graph_intent(q)
            self.assertEqual('order_fruit',lexical.kind)
            self.assertTrue(lexical.residual)
            raw=plan(order);raw['conditions'][0]['surface']='숲이 서식지로 기록돼 있으며'
            provider=Mock(return_value=raw)
            intent=sgi.graph_intent_handler(q,provider=provider)
            provider.assert_called_once()
            self.assertEqual('taxon_traits',intent.kind)
            self.assertEqual('answer',execution_gate(q,intent))
            self.assertEqual({'habitat','diet_distribution'},{c.trait_name for c,_ in intent.conditions})

    def test_complete_legacy_vetoes_and_specific_fruit_still_skip_provider(self):
        cases = ['참새목 중 열매를 먹는 새는?',
                 '참새목에서 숲이 서식지로 기록돼 있으며 열매를 먹지 않는 새는?',
                 '참새목에서 숲이 서식지로 기록돼 있으며 열매도 먹는 겨울 새는?',
                 '참새목에서 숲이 서식지로 기록돼 있으며 열매도 먹고 밤에만 활동하는 새는?',
                 '참새목에서 숲이 서식지로 기록돼 있으며 산수유 열매를 먹는 새는?',
                 '참새목 중 직박구리와 같은 열매를 먹는 새는?',
                 '참새목 중 열매를 먹고 같이 사는 새는?']
        for q in cases:
            with self.subTest(q=q):
                provider=Mock()
                actual=sgi.graph_intent_handler(q,provider=provider)
                provider.assert_not_called()
                self.assertEqual(sgi.extract_graph_intent(q),actual)
        q='참새목에서 숲이 서식지로 기록돼 있으며 열매도 먹는 새를 찾아줘.'
        raw={'kind':'none','conditions':[],'unresolved':[],'unknown_relation':False}
        self.assertEqual(sgi.extract_graph_intent(q),sgi.graph_intent_handler(q,provider=lambda *_:raw))
