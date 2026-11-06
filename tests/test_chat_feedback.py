"""Offline capability, original-trace association and retry contracts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from asgi_client import TestClient
from robingraph import tracing
from robingraph.api.drf import create_django_app
from robingraph.api.schemas import ChatFeedbackRequest


class FeedbackSdk:
    def __init__(self):
        self.traces = {}
        self.writes = []
        self.get_trace = Mock(side_effect=self.traces.get)
        self.get_trace.side_effect = lambda trace_id, **kwargs: self.traces.get(trace_id)
        self.log_feedback = Mock(side_effect=self.save)
        self.flush_trace_async_logging = Mock()

    @contextmanager
    def start_span(self, *, name, **kwargs):
        trace_id = 'tr-' + uuid.uuid4().hex
        live = SimpleNamespace(trace_id=trace_id, name=name, parent_id=None,
            set_inputs=Mock(), set_outputs=Mock(), set_attributes=Mock())
        self.traces[trace_id] = SimpleNamespace(info=SimpleNamespace(experiment_id='33', assessments=[]),
                                                data=SimpleNamespace(spans=[live]))
        yield live

    def update_current_trace(self, **kwargs):
        pass

    def save(self, **kwargs):
        self.writes.append(kwargs)
        self.traces[kwargs['trace_id']].info.assessments.append(SimpleNamespace(
            name=kwargs['name'], source=kwargs['source'], feedback=SimpleNamespace(value=kwargs['value'])))
        return SimpleNamespace(assessment_id='fixture-assessment')


@unittest.skipUnless(importlib.util.find_spec('mlflow'), 'optional tracing extra required')
class ChatFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.sdk = FeedbackSdk()
        self.addCleanup(patch.stopall)
        patch.object(tracing, '_mlflow', self.sdk).start()
        patch.object(tracing, '_status', tracing.TracingStatus(True, 'enabled', experiment_id='33')).start()
        patch.dict(os.environ, {'ROBINGRAPH_DEPLOY_TARGET': 'test'}).start()
        self.client = TestClient(create_django_app(graph_intent_mode='active'))

    def chat(self):
        return self.client.post('/v1/chat', json={'question': '청둥오리랑 비슷한 식생을 가진 새는?'})

    def vote(self, token, rating='helpful'):
        return self.client.post('/v1/chat/feedback', json={'token': token, 'rating': rating})

    def test_each_rating_attaches_human_assessment_to_original_chat(self):
        for rating in ('helpful', 'misunderstood', 'incorrect'):
            with self.subTest(rating=rating):
                chat = self.chat()
                token = chat.headers['x-robingraph-feedback-token']
                trace_id = chat.headers['x-robingraph-trace-id']
                vote = self.vote(token, rating)
                self.assertEqual(200, vote.status_code)
                self.assertEqual({'status': 'saved'}, vote.json())
                write = self.sdk.writes[-1]
                self.assertEqual((trace_id, 'user_feedback', rating),
                                 (write['trace_id'], write['name'], write['value']))
                self.assertEqual('HUMAN', write['source'].source_type)
                self.assertNotIn(token, str(self.sdk.traces[trace_id].data.spans[0].set_inputs.call_args))
                self.assertNotIn('_trace_id', chat.json())
                self.assertEqual('no-store', chat.headers['cache-control'])

    def test_disabled_failed_or_unsupported_tracing_never_changes_chat_body(self):
        traced = self.chat()
        for disabled in (None, SimpleNamespace(start_span=Mock(side_effect=RuntimeError('private')))):
            with patch.object(tracing, '_mlflow', disabled):
                chat = self.chat()
            self.assertEqual(traced.json(), chat.json())
            self.assertNotIn('x-robingraph-feedback-token', chat.headers)
        with patch.object(tracing, '_mlflow', None):
            self.assertEqual(503, self.vote(traced.headers['x-robingraph-feedback-token']).status_code)

    def test_token_signing_failure_is_fail_open(self):
        before = self.chat().json()
        with patch('robingraph.api.feedback.signing.dumps', side_effect=RuntimeError('private key')):
            chat = self.chat()
        self.assertEqual(before, chat.json())
        self.assertNotIn('x-robingraph-feedback-token', chat.headers)

    def test_bad_tampered_expired_cross_target_and_rotated_key_tokens_do_not_read_or_write(self):
        from django.test import override_settings
        token = self.chat().headers['x-robingraph-feedback-token']
        self.sdk.get_trace.reset_mock()
        for value in ('not-a-token', token[:-1] + ('a' if token[-1] != 'a' else 'b')):
            self.assertEqual(400, self.vote(value).status_code)
        with patch('django.core.signing.time.time', return_value=10**11):
            self.assertEqual(400, self.vote(token).status_code)
        with patch.dict(os.environ, {'ROBINGRAPH_DEPLOY_TARGET': 'prod'}):
            self.assertEqual(400, self.vote(token).status_code)
        with override_settings(SECRET_KEY='a-different-unit-test-signing-key'):
            self.assertEqual(400, self.vote(token).status_code)
        self.sdk.get_trace.assert_not_called()
        self.sdk.log_feedback.assert_not_called()

    def test_invalid_payload_is_422_and_never_reaches_storage(self):
        for data in ({}, {'token':'x', 'rating':'bad'}, {'token':'x'*2049,'rating':'helpful'},
                     {'token':'x','rating':'helpful','trace_id':'a-different-trace'},
                     {'token':[], 'rating':'helpful'}):
            with self.subTest(data=str(data)[:80]):
                self.assertEqual(422, self.client.post('/v1/chat/feedback', json=data).status_code)
        self.sdk.get_trace.assert_not_called()
        self.sdk.log_feedback.assert_not_called()

    def test_other_experiment_or_nonchat_trace_is_rejected(self):
        chat = self.chat(); trace_id = chat.headers['x-robingraph-trace-id']
        token = chat.headers['x-robingraph-feedback-token']; trace = self.sdk.traces[trace_id]
        trace.info.experiment_id = '50'
        self.assertEqual(400, self.vote(token).status_code)
        trace.info.experiment_id = '33'; trace.data.spans[0].name = 'GET /health'
        self.assertEqual(400, self.vote(token).status_code)
        trace.data.spans[0].name = 'POST /v1/chat'; trace.data.spans[0].parent_id = 'other-parent'
        self.assertEqual(503, self.vote(token).status_code)
        self.sdk.log_feedback.assert_not_called()

    def test_pending_trace_and_storage_outage_are_retryable_without_secret_leak(self):
        chat = self.chat(); token = chat.headers['x-robingraph-feedback-token']
        self.sdk.get_trace.side_effect = lambda *a, **k: None
        self.assertEqual(503, self.vote(token).status_code)
        self.sdk.get_trace.side_effect = lambda trace_id, **kw: self.sdk.traces.get(trace_id)
        self.sdk.log_feedback.side_effect = RuntimeError('private credential')
        response = self.vote(token)
        self.assertEqual(503, response.status_code)
        self.assertNotIn('private credential', response.text)
        self.sdk.log_feedback.side_effect = ValueError('private provider validation')
        self.assertEqual(503, self.vote(token).status_code)
        self.sdk.log_feedback.side_effect = self.sdk.save
        self.assertEqual(200, self.vote(token).status_code)

    def test_new_trace_export_is_flushed_before_first_feedback(self):
        token = self.chat().headers['x-robingraph-feedback-token']
        self.sdk.get_trace.side_effect = lambda trace_id, **kw: self.sdk.traces.get(trace_id) if self.sdk.flush_trace_async_logging.called else None
        self.assertEqual(200, self.vote(token).status_code)
        self.assertEqual(1, len(self.sdk.writes))

    def test_partial_trace_remains_retryable_and_never_receives_feedback(self):
        token = self.chat().headers['x-robingraph-feedback-token']
        self.sdk.get_trace.side_effect = lambda *a, **k: SimpleNamespace(
            info=SimpleNamespace(experiment_id='33'), data=SimpleNamespace(spans=[]))
        self.assertEqual(503, self.vote(token).status_code)
        self.sdk.log_feedback.assert_not_called()

    def test_duplicate_same_rating_is_saved_once_and_different_rating_conflicts(self):
        token = self.chat().headers['x-robingraph-feedback-token']
        self.assertEqual(200, self.vote(token).status_code)
        self.assertEqual(200, self.vote(token).status_code)
        self.assertEqual(409, self.vote(token, 'incorrect').status_code)
        self.assertEqual(1, len(self.sdk.writes))

    def test_concurrent_retries_are_saved_once(self):
        token = self.chat().headers['x-robingraph-feedback-token']
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: self.vote(token).status_code, range(8)))
        self.assertEqual([200]*8, statuses)
        self.assertEqual(1, len(self.sdk.writes))

    def test_acknowledgement_lost_then_retry_recognizes_already_saved_rating(self):
        token = self.chat().headers['x-robingraph-feedback-token']
        def lost_ack(**kwargs):
            self.sdk.save(**kwargs)
            raise ConnectionError('private transport')
        self.sdk.log_feedback.side_effect = lost_ack
        self.assertEqual(503, self.vote(token).status_code)
        self.assertEqual(200, self.vote(token).status_code)
        self.assertEqual(1, len(self.sdk.writes))

    def test_openapi_and_method_contract(self):
        schema = self.client.get('/openapi.json').json()
        self.assertIn('/v1/chat/feedback', schema['paths'])
        self.assertEqual(ChatFeedbackRequest.model_json_schema(), schema['components']['schemas']['ChatFeedbackRequest'])
        self.assertEqual(405, self.client.get('/v1/chat/feedback').status_code)
        self.assertEqual(422, self.client.post('/v1/chat/feedback', content='not-json', headers={'Content-Type':'application/json'}).status_code)
