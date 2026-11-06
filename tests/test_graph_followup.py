"""Condition-keeping follow-up questions (one added condition); injected mock graph retrieval only."""
from contextlib import contextmanager
import importlib.util
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from asgi_client import TestClient
from robingraph import tracing
from robingraph.api.drf import create_django_app
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_questions import LIMITATIONS, TraitCondition

FOREST = TraitCondition('habitat', 'eq', 'Forest')
WETLAND = TraitCondition('habitat', 'eq', 'Wetland')
FRUIT = TraitCondition('diet_distribution', 'share_gt', 'fruit', 0)


def payload(status='answer'):
    return {'title': '조건 조회', 'text': '조건에 맞는 종입니다.', 'status': status, 'items': [], 'paths': [],
            'sources': [], 'limitations': ['그래프 주장만 검색합니다.'], 'has_more': False}


class GraphFollowupTest(unittest.TestCase):
    def setUp(self):
        self.graph = Mock(return_value=payload())
        self.client = TestClient(create_django_app(graph_intent_mode='active', graph_intent_handler=extract_graph_intent,
                                                   graph_question_handler=self.graph))

    def ask(self, question, context=None, **extra):
        body = {'question': question, **extra}
        if context is not None:
            body['followup_context'] = context
        response = self.client.post('/v1/chat', json=body)
        self.assertEqual(200, response.status_code)
        return response.json()

    def signed(self, **changes):
        """A correctly signed token whose plan content is invalid: the signature alone is not trusted."""
        from django.core import signing
        data = {'v': 1, 'q': '숲에 사는 새', 'rank': None, 's': None, 't': 0, 'ss': 'all',
                'c': [{'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest'}],
                'target': os.environ.get('ROBINGRAPH_DEPLOY_TARGET', 'legacy'), **changes}
        return signing.dumps(data, salt='robingraph.chat.followup', compress=True)

    def executed(self):
        question = self.graph.call_args.args[0]
        return question.kind, question.rank_name, set(question.conditions), self.graph.call_args.kwargs['species_scope']

    def test_korea_scope_added_to_habitat_and_diet_query_keeps_every_condition(self):
        base = self.ask('숲에 사는 열매 먹는 새')
        self.assertEqual('answer', base['disposition'])
        self.assertNotIn('followup', base)
        self.graph.reset_mock()
        body = self.ask('그중 한국에서 볼 수 있는 새는?', base['followup_context'])
        self.assertEqual('answer', body['disposition'])
        self.assertEqual(('taxon_traits', None, {FOREST, FRUIT}, 'korea'), self.executed())
        self.graph.assert_called_once()   # the full plan is re-run, never a filtered previous page
        self.assertIn(LIMITATIONS['korea_record'], body['warnings'])
        self.assertIn(LIMITATIONS['korea_record'], body['result']['payload']['limitations'])
        shown = {'conditions': ['서식 환경 숲(Forest)', '먹이 구성에 열매 포함'], 'taxon': None, 'scope': 'korea'}
        self.assertEqual({'status': 'applied', 'reason': None, 'root_question': '숲에 사는 열매 먹는 새',
                          'added': '국내 기록', 'plan': shown, 'retained': shown}, body['followup'])
        self.assertNotEqual(base['followup_context'], body['followup_context'])

    def test_chain_of_taxon_diet_and_scope_additions(self):
        context = self.ask('참새목 중 숲에 사는 새')['followup_context']
        body = self.ask('그중에서도 열매 먹는 새만 보여줘', context)
        self.assertEqual(('taxon_traits', '참새목', {FOREST, FRUIT}, 'all'), self.executed())
        body = self.ask('이 중 국내에 기록된 새 알려줘', body['followup_context'])
        self.assertEqual(('taxon_traits', '참새목', {FOREST, FRUIT}, 'korea'), self.executed())
        self.assertEqual('참새목 중 숲에 사는 새', body['followup']['root_question'])

    def test_order_fruit_base_continues_as_the_same_conditions(self):
        context = self.ask('참새목 중 열매를 먹고 사는 새는?')['followup_context']
        self.ask('그 중에서 습지에 사는 새는?', context)
        self.assertEqual(('taxon_traits', '참새목', {FRUIT, WETLAND}, 'all'), self.executed())

    def test_taxon_and_measure_additions(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.ask('그럼 그중 까마귀과 새는?', context)
        self.assertEqual(('taxon_traits', '까마귀과', {FOREST, FRUIT}, 'all'), self.executed())
        self.ask('그 새들 중 체중 100g 이상인 새는?', context)
        self.assertEqual({FOREST, FRUIT, TraitCondition('body_mass', 'num_gte', None, 100.0, 'g')}, self.executed()[2])

    def test_followup_without_or_with_untrusted_context_is_never_run(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.graph.reset_mock()
        tampered = context[:-3] + ('AAA' if not context.endswith('AAA') else 'BBB')
        cases = {None: 'context_missing', '': 'context_missing', 'not-a-token': 'context_invalid',
                 tampered: 'context_invalid', self.signed(c=[{'trait_name': 'habitat', 'op': 'eq', 'value': 'Moon'}]):
                 'context_invalid', self.signed(c=[]): 'context_invalid', self.signed(rank='참새목 OR 1=1'):
                 'context_invalid', self.signed(s='outside'): 'context_invalid', self.signed(v=2): 'context_invalid',
                 self.signed(c=[{'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'extra': 1}]):
                 'context_invalid'}
        for token, reason in cases.items():
            with self.subTest(token=token):
                body = self.ask('그중 한국에서 볼 수 있는 새는?', token)
                self.assertEqual(('clarify', 'clarify', 'rejected', reason),
                                 (body['disposition'], body['result']['kind'], body['followup']['status'],
                                  body['followup']['reason']))
                self.assertNotIn('followup_context', body)
        with patch('robingraph.api.followup._MAX_AGE', -1):
            self.assertEqual('context_invalid', self.ask('그중 습지에 사는 새', context)['followup']['reason'])
        with patch.dict(os.environ, {'ROBINGRAPH_DEPLOY_TARGET': 'other-target'}):
            self.assertEqual('context_invalid', self.ask('그중 습지에 사는 새', context)['followup']['reason'])
        self.graph.assert_not_called()
        self.assertEqual(422, self.client.post('/v1/chat', json={'question': '그중 습지 새',
                                                                'followup_context': 'x' * 5000}).status_code)

    def test_context_from_another_scope_tab_is_not_mixed(self):
        context = self.ask('숲에 사는 열매 먹는 새', species_scope='outside')['followup_context']
        self.graph.reset_mock()
        body = self.ask('그중 습지에 사는 새', context, species_scope='all')
        self.assertEqual('context_scope_mismatch', body['followup']['reason'])
        self.graph.assert_not_called()

    def test_failed_or_empty_base_issues_no_context(self):
        for result in (payload('empty'), payload('insufficient_data'), RuntimeError('backend')):
            with self.subTest(result=result):
                self.graph.side_effect = [result]
                self.graph.return_value = None
                body = self.ask('숲에 사는 열매 먹는 새')
                self.assertNotIn('followup_context', body)
                self.graph.side_effect = None
                self.graph.return_value = payload()

    def test_empty_followup_keeps_the_last_successful_plan(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.graph.return_value = payload('empty')
        body = self.ask('그중 한국에서 볼 수 있는 새는?', context)
        self.assertEqual(('abstain', 'applied', context), (body['disposition'], body['followup']['status'],
                                                           body['followup_context']))
        # Shown: the plan that ran (with Korea); carried: the last successful plan (without it).
        self.assertEqual(('korea', 'all'), (body['followup']['plan']['scope'], body['followup']['retained']['scope']))
        self.assertEqual(body['followup']['plan']['conditions'], body['followup']['retained']['conditions'])
        self.graph.return_value = payload()
        self.ask('그중 까마귀과 새는?', body['followup_context'])
        self.assertEqual(('taxon_traits', '까마귀과', {FOREST, FRUIT}, 'all'), self.executed())

    def test_rejected_additions_clarify_and_keep_the_context(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.graph.reset_mock()
        cases = {'그중 열매 안 먹는 새': 'unsupported_addition', '그중 한국에 없는 새는?': 'unsupported_addition',
                 '그중 까치와 같은 속인 새': 'unsupported_addition', '그중 곡식 먹는 새': 'unsupported_addition',
                 '그중 포식자인 새': 'unsupported_addition', '그중 야행성인 새': 'unresolved_addition',
                 '그중 한국에 사는 새': 'unresolved_addition', '그중 겨울에 오는 새': 'unresolved_addition',
                 '그중 한국에서 볼 수 있는 습지에 사는 새': 'multiple_additions',
                 '그중 습지에 사는 새': 'conflicting_condition', '그중 열매 먹는 새': 'duplicate_condition'}
        for question, reason in cases.items():
            with self.subTest(question=question):
                body = self.ask(question, context)
                self.assertEqual(('clarify', reason, context), (body['disposition'], body['followup']['reason'],
                                                                body['followup_context']))
                self.assertIn('유지한 조건', body['answer_text'])
                self.assertEqual(body['followup']['plan'], body['followup']['retained'])
        self.graph.assert_not_called()

    def test_scope_and_taxon_conflicts(self):
        korea = self.ask('숲에 사는 열매 먹는 새', species_scope='korea')['followup_context']
        self.assertEqual('duplicate_condition',
                         self.ask('그중 국내 기록된 새', korea, species_scope='korea')['followup']['reason'])
        outside = self.ask('숲에 사는 열매 먹는 새', species_scope='outside')['followup_context']
        self.assertEqual('conflicting_condition',
                         self.ask('그중 국내 기록된 새', outside, species_scope='outside')['followup']['reason'])
        ranked = self.ask('참새목 중 숲에 사는 새')['followup_context']
        self.assertEqual('conflicting_condition', self.ask('그중 까마귀과 새는?', ranked)['followup']['reason'])
        self.assertEqual('duplicate_condition', self.ask('그중 참새목 새는?', ranked)['followup']['reason'])

    def test_new_standalone_question_ignores_the_context(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        body = self.ask('습지에 사는 새 알려줘', context)
        self.assertEqual(('taxon_traits', None, {WETLAND}, 'all'), self.executed())
        self.assertNotIn('followup', body)
        self.assertNotEqual(context, body['followup_context'])
        other = self.ask('까치와 같은 속인 새', context)   # another graph kind: answered, not continued
        self.assertEqual('same_genus', self.graph.call_args.args[0].kind)
        self.assertNotIn('followup_context', other)
        self.assertNotIn('followup', other)

    def test_feedback_headers_are_kept_on_followups(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        headers = {'X-RobinGraph-Trace-Id': 'trace-1', 'X-RobinGraph-Feedback-Token': 'token',
                   'Cache-Control': 'no-store'}
        with patch('robingraph.api.feedback.feedback_headers', return_value=headers):
            response = self.client.post('/v1/chat', json={'question': '그중 한국에서 볼 수 있는 새는?',
                                                          'followup_context': context})
        self.assertEqual(('trace-1', 'token', 'no-store'), (response.headers['x-robingraph-trace-id'],
                                                            response.headers['x-robingraph-feedback-token'],
                                                            response.headers['cache-control']))

    def test_bare_demonstrative_is_a_followup_not_a_new_question(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.graph.reset_mock()
        for question in ('그중', '그중?', '그 중에서는?', '여기서'):
            with self.subTest(question=question):
                self.assertEqual('context_missing', self.ask(question)['followup']['reason'])
                self.assertEqual('unresolved_addition', self.ask(question, context)['followup']['reason'])
        self.graph.assert_not_called()

    def test_signing_failure_keeps_the_base_answer(self):
        with patch('django.core.signing.dumps', side_effect=RuntimeError('key unavailable')):
            body = self.ask('숲에 사는 열매 먹는 새')
        self.assertEqual(('answer', 'graph_query'), (body['disposition'], body['result']['kind']))
        self.assertNotIn('followup_context', body)

    def test_explicit_route_or_species_filter_is_not_dropped_for_the_context(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        self.graph.reset_mock()
        for extra in ({'filters': {'kind': 'profile', 'name': '직박구리'}},
                      {'intent': 'profile', 'filters': {'kind': 'profile', 'name': '직박구리'}},
                      {'intent': 'taxonomy'}, {'intent': 'evidence'},
                      {'filters': {'kind': 'observations', 'place': '서울'}}):
            with self.subTest(extra=extra):
                body = self.ask('그중 한국에서 볼 수 있는 새는?', context, **extra)
                self.assertEqual(('clarify', 'route_conflict', context),
                                 (body['disposition'], body['followup']['reason'], body['followup_context']))
        self.graph.assert_not_called()
        self.ask('그중 한국에서 볼 수 있는 새는?', context, intent='profile', filters={'kind': 'profile'})
        self.assertEqual(('taxon_traits', None, {FOREST, FRUIT}, 'korea'), self.executed())   # empty filter: no conflict
        lineage = Mock(return_value=None)
        client = TestClient(create_django_app(graph_intent_mode='active', graph_intent_handler=extract_graph_intent,
                                              graph_question_handler=self.graph, lineage_handler=lineage))
        body = client.post('/v1/chat', json={'question': '참새목의 분류는?', 'intent': 'taxonomy',
                                             'followup_context': context}).json()   # standalone: context ignored
        self.assertNotIn('followup', body)

    def test_initial_species_scope_is_shown_in_every_followup_plan(self):
        for scope in ('korea', 'outside', 'unknown'):
            with self.subTest(scope=scope):
                context = self.ask('숲에 사는 열매 먹는 새', species_scope=scope)['followup_context']
                body = self.ask('그중 참새목 새는?', context, species_scope=scope)
                self.assertEqual(('taxon_traits', '참새목', {FOREST, FRUIT}, scope), self.executed())
                self.assertEqual((scope, scope), (body['followup']['plan']['scope'], body['followup']['retained']['scope']))
                rejected = self.ask('그중 야행성인 새', context, species_scope=scope)
                self.assertEqual(scope, rejected['followup']['plan']['scope'])
                self.assertIn({'korea': '국내 기록', 'outside': '국외 분포', 'unknown': '한국 분포 미확인'}[scope],
                              rejected['answer_text'])

    def test_followup_token_responses_are_never_cached_without_feedback(self):
        body_response = self.client.post('/v1/chat', json={'question': '숲에 사는 열매 먹는 새'})
        self.assertEqual('no-store', body_response.headers['cache-control'])
        context = body_response.json()['followup_context']
        followup = self.client.post('/v1/chat', json={'question': '그중 참새목 새는?', 'followup_context': context})
        self.assertEqual('no-store', followup.headers['cache-control'])

    def test_boundary_additions(self):
        context = self.ask('숲에 사는 열매 먹는 새')['followup_context']
        cases = {'그중 Turdus 새는?': ('Turdus', set()), '그중 지빠귀과 새는?': ('지빠귀과', set()),
                 '그중 Passeriformes 새는?': ('Passeriformes', set()), '그중 까마귀속 새는?': ('까마귀속', set()),
                 '그중 Turdus merula 중에서': ('Turdus merula', set()),   # rank is decided by the data at execution
                 '그중 꼬리 길이 100mm 이상인 새': (None, {TraitCondition('tail_length', 'num_gte', None, 100.0, 'mm')}),
                 '그중 먹이 생태 범주가 잡식인 새': (None, {TraitCondition('trophic_niche', 'eq', 'Omnivore')}),
                 '그중 날개 길이 100mm 미만인 새는?': (None, {TraitCondition('wing_length', 'num_lt', None, 100.0, 'mm')}),
                 '그중 체중 50g 초과인 새': (None, {TraitCondition('body_mass', 'num_gt', None, 50.0, 'g')}),
                 '그중 곤충 먹는 새는?': (None, {TraitCondition('diet_distribution', 'share_gt', 'invertebrate', 0)}),
                 '그중 꽃꿀 먹는 새는?': (None, {TraitCondition('diet_distribution', 'share_gt', 'nectar', 0)}),
                 '그중 나무열매 먹는 새는?': (None, {TraitCondition('diet_distribution', 'share_gt', 'fruit', 0,
                                                              qualifier='tree_fruit')})}
        for question, (rank, added) in cases.items():
            with self.subTest(question=question):
                body = self.ask(question, context)
                self.assertEqual('applied', body['followup']['status'], body['answer_text'])
                self.assertEqual(('taxon_traits', rank, {FOREST, FRUIT} | added, 'all'), self.executed())
        rejected = {'그중 체중 100kg 이상 50g 이하인 새': 'unresolved_addition', '그중 체중이 무거운 새': 'unresolved_addition',
                    '그중 해안이나 습지에 사는 새': 'unresolved_addition',
                    '그중 부리 길이 20mm 이하인 새': 'unresolved_addition', '그중 꼬리 길이 100 이상인 새': 'unresolved_addition',
                    '그중 잡식성 새': 'unresolved_addition'}   # the same holds as the standalone extractor
        for question, reason in rejected.items():
            with self.subTest(question=question):
                body = self.ask(question, context)
                self.assertEqual('rejected', body['followup']['status'])


@unittest.skipUnless(importlib.util.find_spec('mlflow'), 'optional tracing extra required')
class FollowupTracingTest(unittest.TestCase):
    def test_trace_keeps_question_and_plan_but_never_the_token(self):
        recorded = []

        class Sdk:
            @contextmanager
            def start_span(self, *, name, **kwargs):
                live = SimpleNamespace(trace_id='tr-1', name=name, parent_id=None,
                                       **{method: (lambda method: lambda *args: recorded.append((name, method, args)))(method)
                                          for method in ('set_inputs', 'set_outputs', 'set_attributes', 'set_attribute')})
                yield live

            def update_current_trace(self, **kwargs):
                pass

        graph = Mock(return_value=payload())
        with patch.object(tracing, '_mlflow', Sdk()):
            client = TestClient(create_django_app(graph_intent_mode='active', graph_intent_handler=extract_graph_intent,
                                                  graph_question_handler=graph))
            context = client.post('/v1/chat', json={'question': '숲에 사는 열매 먹는 새'}).json()['followup_context']
            recorded.clear()
            response = client.post('/v1/chat', json={'question': '그중 참새목 새는?', 'followup_context': context})
        self.assertEqual('applied', response.json()['followup']['status'])
        text = repr(recorded)
        self.assertNotIn(context[:24], text)
        self.assertNotIn(response.json()['followup_context'][:24], text)
        self.assertIn('[redacted]', text)
        self.assertIn('그중 참새목 새는?', text)
        self.assertIn('숲에 사는 열매 먹는 새', text)
        self.assertIn('graph_followup.canonical_plan', text)


if __name__ == '__main__':
    unittest.main()
