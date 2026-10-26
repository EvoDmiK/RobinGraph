"""User-visible holds identify only source-backed uncertainty; retrieval stays blocked."""
from unittest import TestCase
from unittest.mock import Mock
from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.api.services import _condition_detail, _graph_clarification
from robingraph.retrieval.graph_intent_schema import GraphIntent, Span, span_of
from robingraph import tracing


class ConditionClarificationTests(TestCase):
    def test_source_pieces_join_without_inventing_or_overwriting_words(self):
        question = '까마귀과 중 겨울에만 숲에서 사는 새'
        spans = [span_of(question, '겨울에만'), span_of(question, '숲에서'), Span('secret', 0, 6)]
        self.assertEqual('‘겨울에만 숲에서’', _condition_detail(question, reversed(spans)))

    def test_distinct_unknowns_remain_distinct(self):
        q = '겨울에 살고 가장 작은 새'
        self.assertEqual('‘겨울에’, ‘가장 작은’', _condition_detail(q, [span_of(q, '겨울에'), span_of(q, '가장 작은')]))

    def test_hold_does_not_tell_numeric_query_to_choose_food_or_habitat(self):
        q = '까마귀과 중 몸무게가 가벼운 새'
        intent = GraphIntent('taxon_traits', residual=(span_of(q, '가벼운'),), source='semantic')
        graph = Mock()
        app = create_django_app(graph_intent_handler=Mock(return_value=intent), graph_intent_mode='active', graph_question_handler=graph)
        body = TestClient(app).post('/v1/chat', json={'question': q}).json()
        self.assertEqual('clarify', body['disposition'])
        self.assertIn('‘가벼운’', body['result']['prompt'])
        self.assertNotIn('먹이', body['result']['prompt'])
        self.assertEqual(body['answer_text'], body['result']['prompt'])
        graph.assert_not_called()

    def test_missing_reference_asks_only_for_reference(self):
        prompt = _graph_clarification('같은 먹이를 먹는 새', GraphIntent('shared_diet', source='semantic'))
        self.assertIn('기준 새의 이름', prompt)
        self.assertNotIn('서식 환경', prompt)

    def test_unsupported_and_negated_conditions_explain_different_problems(self):
        q = '까마귀를 제외하고 가장 가까운 새'
        unsupported = _graph_clarification(q, GraphIntent(None, unsupported=('evolutionary_distance',)))
        negative = _graph_clarification(q, GraphIntent(None, negation=(span_of(q, '까마귀를 제외하고'),)))
        self.assertIn('진화적 거리', unsupported)
        self.assertIn('지원하지 않습니다', unsupported)
        self.assertIn('‘까마귀를 제외하고’', negative)
        self.assertNotEqual(unsupported, negative)

    def test_audit_failure_is_not_reported_as_transient_network_error(self):
        q = '까마귀과 중 몸무게가 가벼운 새'
        def reject(question):
            tracing.note_outcome('semantic_audit_rejected', 'plan_validation')
            error = RuntimeError('private audit prose')
            error.reason = 'semantic_audit_rejected'
            error.original_spans = (span_of(q, '가벼운'),)
            raise error
        graph = Mock()
        app = create_django_app(graph_intent_handler=reject, graph_intent_mode='active', graph_question_handler=graph)
        token = tracing.begin_outcome()
        try:
            body = TestClient(app).post('/v1/chat', json={'question': q}).json()
        finally:
            tracing.end_outcome(token)
        self.assertIn('‘가벼운’', body['answer_text'])
        self.assertNotIn('잠시 후', body['answer_text'])
        self.assertNotIn('private', str(body))
        graph.assert_not_called()
