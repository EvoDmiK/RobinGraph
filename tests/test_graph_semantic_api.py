"""Mode and execution boundaries using injected interpretation/retrieval (no live API)."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.retrieval.graph_intent_schema import GraphIntent, from_graph_question, span_of
from robingraph.retrieval.graph_questions import parse_graph_question

OLD = '참새목 중 열매를 먹고 사는 새는?'
NEW = '열매 먹는 참새목 새를 찾아 줘'


def new_intent(question=NEW):
    return GraphIntent('order_fruit', rank=span_of(question, '참새목'), diet='fruit_share',
                       evidence=(('diet', span_of(question, '열매 먹는')),), source='extractor')


def payload(status='answer'):
    return dict(title='관계 탐색', text='출처가 확인된 자료', status=status,
                items=[], paths=[], sources=[], limitations=[], has_more=False)


class GraphSemanticApiTests(TestCase):
    def test_structured_handler_can_rescue_not_graph_only_in_active_auto(self):
        plan = Mock(return_value=replace(new_intent(), source='semantic'))
        lexical = Mock(return_value=GraphIntent(None, source='extractor'))
        client, graph = self.app(lexical, graph_plan_handler=plan)
        result = client.post('/v1/chat', json={'question': NEW}).json()
        self.assertEqual('answer', result['disposition'])
        plan.assert_called_once_with(NEW)
        lexical.assert_not_called()
        graph.assert_called_once()
        for mode, intent in (('off', 'auto'), ('shadow', 'auto'), ('active', 'profile')):
            plan.reset_mock()
            client, _ = self.app(Mock(return_value=new_intent()), mode=mode, graph_plan_handler=plan)
            client.post('/v1/chat', json={'question': NEW, 'intent': intent})
            plan.assert_not_called()

    def app(self, handler, mode='active', **kwargs):
        graph = Mock(return_value=payload())
        app = create_django_app(graph_intent_handler=handler, graph_intent_mode=mode,
                                graph_question_handler=graph, **kwargs)
        return TestClient(app), graph

    def test_default_off_keeps_legacy_path_and_makes_no_interpretation_call(self):
        interpret = Mock(side_effect=AssertionError('off mode'))
        client, graph = self.app(interpret, mode='off')
        body = client.post('/v1/chat', json={'question': OLD}).json()
        self.assertEqual(('answer', 'deterministic'), (body['disposition'], body['route_method']))
        interpret.assert_not_called()
        graph.assert_called_once()

    def test_shadow_observes_without_new_retrieval_or_changing_response(self):
        interpret = Mock(return_value=GraphIntent(None, unsupported=('other',)))
        client, graph = self.app(interpret, mode='shadow')
        body = client.post('/v1/chat', json={'question': OLD}).json()
        self.assertEqual(('answer', 'deterministic'), (body['disposition'], body['route_method']))
        self.assertEqual(parse_graph_question(OLD), graph.call_args.args[0])
        graph.assert_called_once()
        interpret.assert_called_once_with(OLD)

    def test_shadow_failure_preserves_legacy_answer(self):
        client, graph = self.app(Mock(side_effect=RuntimeError('private')), mode='shadow')
        body = client.post('/v1/chat', json={'question': OLD}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertNotIn('private', str(body))
        graph.assert_called_once()

    def test_active_uses_validated_original_conditions_and_preserves_all_scopes(self):
        for scope in ('all', 'korea', 'outside', 'unknown'):
            with self.subTest(scope=scope):
                client, graph = self.app(Mock(return_value=new_intent()))
                body = client.post('/v1/chat', json={'question': NEW, 'species_scope': scope}).json()
                self.assertEqual(('answer', 'semantic'), (body['disposition'], body['route_method']))
                parsed = graph.call_args.args[0]
                self.assertEqual(('order_fruit', '참새목', 'fruit_share'),
                                 (parsed.kind, parsed.rank_name, parsed.criterion))
                self.assertEqual(scope, graph.call_args.kwargs['species_scope'])

    def test_unsafe_or_malformed_interpretations_never_reach_retrieval(self):
        q = '열매 먹는 참새목 새를 찾아 줘, 겨울에'
        cases = (replace(new_intent(q), residual=(span_of(q, '겨울에'),)),
                 replace(new_intent(q), unsupported=('ranking',)), GraphIntent('free_cypher'), None)
        for interpretation in cases:
            with self.subTest(interpretation=interpretation):
                client, graph = self.app(Mock(return_value=interpretation))
                body = client.post('/v1/chat', json={'question': q}).json()
                self.assertEqual('clarify', body['disposition'])
                graph.assert_not_called()

    def test_active_provider_failure_clarifies_without_silently_relaxing_conditions(self):
        client, graph = self.app(Mock(side_effect=TimeoutError('secret endpoint')))
        body = client.post('/v1/chat', json={'question': NEW}).json()
        self.assertEqual('clarify', body['disposition'])
        self.assertNotIn('secret endpoint', str(body))
        graph.assert_not_called()

    def test_explicit_non_profile_routes_and_single_species_do_not_invoke_new_router(self):
        for intent, question in (('taxonomy', OLD), ('observations', OLD), ('evidence', OLD),
                                  ('auto', '직박구리는 무엇을 먹어?')):
            with self.subTest(intent=intent):
                interpret = Mock(side_effect=AssertionError('established route'))
                client, graph = self.app(interpret)
                self.assertEqual(200, client.post('/v1/chat', json={'question': question, 'intent': intent}).status_code)
                interpret.assert_not_called()
                graph.assert_not_called()

    def test_explicit_profile_keeps_explicit_method_and_empty_ui_filter(self):
        client, graph = self.app(Mock(return_value=new_intent()))
        body = client.post('/v1/chat', json={'question': NEW, 'intent': 'profile',
                                           'filters': {'kind': 'profile'}}).json()
        self.assertEqual(('answer', 'explicit'), (body['disposition'], body['route_method']))
        graph.assert_called_once()

    def test_species_filter_conflict_is_not_dropped_by_semantic_route(self):
        client, graph = self.app(Mock(return_value=new_intent()))
        body = client.post('/v1/chat', json={'question': NEW,
                                           'filters': {'kind': 'profile', 'name': '청둥오리'}}).json()
        self.assertEqual('clarify', body['disposition'])
        graph.assert_not_called()

    def test_specific_fruit_retains_insufficient_data_contract(self):
        q = '참새목 중 감나무 열매를 먹는 새는?'
        interpret = Mock(return_value=replace(from_graph_question(q, parse_graph_question(q)), source='extractor'))
        client, graph = self.app(interpret)
        graph.return_value = payload('insufficient_data')
        body = client.post('/v1/chat', json={'question': q}).json()
        self.assertEqual('abstain', body['disposition'])
        self.assertEqual('specific_fruit', graph.call_args.args[0].kind)

    def test_invalid_mode_fails_at_construction(self):
        with self.assertRaises(ValueError):
            create_django_app(graph_intent_mode='unsafe')

    def test_active_rejects_trusted_baseline_or_gold_source_without_extractor_evidence(self):
        for source in ('gold', 'regex_fullmatch'):
            with self.subTest(source=source):
                client, graph = self.app(Mock(return_value=replace(new_intent(), source=source)))
                body = client.post('/v1/chat', json={'question': NEW}).json()
                self.assertEqual('clarify', body['disposition'])
                graph.assert_not_called()

    def test_not_graph_without_graph_cues_continues_to_existing_auto_router(self):
        # Existing deterministic single-species recognizers do not match this.
        old_router = Mock()
        old_router.classify.return_value = 'evidence'
        client, graph = self.app(Mock(return_value=GraphIntent(None, source='extractor')),
                                  semantic_router=old_router)
        body = client.post('/v1/chat', json={'question': '기후변화 관련 조류 문헌을 찾아줘'}).json()
        old_router.classify.assert_called_once()
        graph.assert_not_called()
        self.assertEqual('evidence', body['selected_intent'])

    def test_legacy_match_lost_by_extractor_does_not_fall_through_to_a_different_query(self):
        old_router = Mock(side_effect=AssertionError('lost graph conditions'))
        client, graph = self.app(Mock(return_value=GraphIntent(None, source='extractor')),
                                  semantic_router=old_router)
        body = client.post('/v1/chat', json={'question': OLD}).json()
        self.assertEqual('clarify', body['disposition'])
        graph.assert_not_called()
        old_router.classify.assert_not_called()
