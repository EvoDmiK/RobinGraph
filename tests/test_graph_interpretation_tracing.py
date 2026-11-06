"""Offline span/outcome contracts; the interpreter and fail-closed audit stay unchanged."""
from contextlib import ExitStack, contextmanager
import json
import unittest
from unittest.mock import Mock, patch

from robingraph import tracing
from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_intent_schema import execution_gate
from test_mlflow_tracing import FakeMlflow, FakeSpan


QUESTION = '까치랑 같은 먹이 생태를 가진 새를 알려줘'
PLAN = {'kind': 'shared_diet', 'species': '까치', 'relation_text': '같은 먹이 생태를 가진'}
AUDIT = {'faithful': True, 'issues': []}


def document(payload):
    return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}


class GraphInterpretationTracingTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeMlflow()
        self.addCleanup(patch.stopall)
        patch.object(tracing, '_mlflow', self.fake).start()
        token = tracing.begin_outcome()
        self.addCleanup(tracing.end_outcome, token)

    def span(self, name):
        return next(span for span in self.fake.spans if span.name == name)

    def provider(self, plan=PLAN, audit=AUDIT):
        answerer = GeminiAnswerer('dummy', urlopen=Mock())
        answerer._request = Mock(side_effect=[document(plan), document(audit)])
        return answerer.propose_structured_graph_intent

    def outcome(self, reason, stage):
        self.assertEqual({'reason': reason, 'stage': stage}, tracing.collected_outcome())

    def test_plan_audit_validation_are_children_of_one_request_and_do_not_change_answer(self):
        with tracing.span('request') as _:
            actual = sgi.interpret(QUESTION, self.provider())
        expected = sgi.interpret(QUESTION, lambda *_: PLAN)
        self.assertEqual(expected, actual)
        self.assertEqual('answer', execution_gate(QUESTION, actual))
        self.assertEqual({}, tracing.collected_outcome())
        request = self.span('request')
        for name, stage in [('graph_intent.plan', 'interpretation'),
                            ('graph_intent.audit', 'semantic_audit'),
                            ('graph_intent.validation', 'plan_validation')]:
            span = self.span(name)
            self.assertIs(request, span.parent)
            self.assertEqual(stage, span.attributes['stage'])
        self.assertEqual(PLAN, self.span('graph_intent.plan').outputs)
        self.assertEqual(AUDIT, self.span('graph_intent.audit').outputs)
        self.assertEqual('model', self.span('graph_intent.audit').attributes['judgment_source'])

    def test_model_rejection_is_preserved_through_provider_catch_without_retry(self):
        for audit in [{'faithful': False, 'issues': ['model suspects missing scope']},
                      {'faithful': True, 'issues': ['model suspects added habitat']}]:
            with self.subTest(audit=audit):
                with self.assertRaisesRegex(sgi.SemanticIntentError, r'provider failed \(GeminiAnswerError\)'):
                    sgi.interpret(QUESTION, self.provider(audit=audit))
                self.outcome('semantic_audit_rejected', 'semantic_audit')
        self.assertFalse(any(s.name == 'graph_intent.validation' for s in self.fake.spans))
        self.assertEqual(2, sum(s.name == 'graph_intent.audit' for s in self.fake.spans))

    def test_plan_and_audit_payload_format_failures_are_distinct_stages(self):
        for payloads, stage in [([document([])], 'interpretation'),
                                ([document(PLAN), document([])], 'semantic_audit'),
                                ([document(PLAN), document({})], 'semantic_audit')]:
            answerer = GeminiAnswerer('dummy', urlopen=Mock())
            answerer._request = Mock(side_effect=payloads)
            with self.subTest(stage=stage), self.assertRaises(sgi.SemanticIntentError):
                sgi.interpret(QUESTION, answerer.propose_structured_graph_intent)
            self.outcome('invalid_plan', stage)
            self.assertEqual(len(payloads), answerer._request.call_count)

    def test_contract_format_failure_preserves_existing_errors(self):
        for raw, message in [(None, 'provider output is not the contract object'),
                             ({'kind': 'unknown'}, 'unknown kind'),
                             ({'kind': 'none', 'conditions': {}}, 'conditions must be a list')]:
            with self.subTest(raw=raw), self.assertRaisesRegex(sgi.SemanticIntentError, message):
                sgi.interpret(QUESTION, lambda *_: raw)
            self.outcome('invalid_plan', 'plan_validation')

    def test_source_span_failure_preserves_fixed_detail_and_hold(self):
        raw = {**PLAN, 'species': '까마귀'}
        actual = sgi.interpret(QUESTION, lambda *_: raw)
        self.assertEqual(sgi._HOLD, actual)
        self.outcome('plan_validation_rejected', 'plan_validation')
        self.assertEqual('surface not in question',
                         self.span('graph_intent.validation').attributes['rejection_detail'])

    def test_numeric_mismatch_is_recorded_without_weakening_guard(self):
        q = '까마귀과에서 덩치가 1kg 넘는 녀석들 보여줄래'
        raw = {'kind': 'taxon_traits', 'taxon': '까마귀과', 'conditions': [{
            'trait_name': 'body_mass', 'op': 'num_gt', 'surface': '덩치가 1kg 넘는',
            'threshold': 1, 'unit': 'g'}]}
        intent = sgi.interpret(q, lambda *_: raw)
        self.assertEqual('clarify', execution_gate(q, intent))
        self.assertEqual(['1kg'], [span.text for span in intent.residual])
        self.outcome('plan_validation_rejected', 'plan_validation')
        self.assertTrue(self.span('graph_intent.validation').attributes['rejection_detail'])

    def test_normal_hold_branches_record_reason_without_changing_intent(self):
        for extra, reason in [({'unresolved': ['친절한']}, 'unresolved_conditions'),
                              ({'unknown_relation': True}, 'unsupported_relation'),
                              ({'taxon': '참새목'}, 'plan_validation_rejected'),
                              ({'unresolved': ['친절한'], 'unknown_relation': True}, 'unsupported_relation')]:
            with self.subTest(extra=extra):
                raw = {'kind': 'none', **extra}
                intent = sgi.interpret('참새목에서 친절한 새를 찾아줘', lambda *_: raw)
                self.assertEqual('clarify', execution_gate('참새목에서 친절한 새를 찾아줘', intent))
                self.outcome(reason, 'plan_validation')

    def test_provider_failures_preserve_stage_and_sanitized_exception(self):
        for documents, stage in [([], 'interpretation'), ([document(PLAN)], 'semantic_audit')]:
            answerer = GeminiAnswerer('dummy', urlopen=Mock())
            answerer._request = Mock(side_effect=documents + [GeminiAnswerError('provider unavailable')])
            with self.subTest(stage=stage), self.assertRaisesRegex(sgi.SemanticIntentError, r'provider failed \(GeminiAnswerError\)'):
                sgi.interpret(QUESTION, answerer.propose_structured_graph_intent)
            self.outcome('interpretation_error', stage)
        with self.assertRaisesRegex(sgi.SemanticIntentError, r'provider failed \(TimeoutError\)'):
            sgi.interpret(QUESTION, Mock(side_effect=TimeoutError('private transport details')))
        self.outcome('interpretation_error', 'interpretation')

    def test_selection_only_is_an_attribute_not_a_failure(self):
        with patch.object(sgi, '_lexical_decides', return_value=True):
            provider = Mock()
            result = sgi.graph_intent_handler(QUESTION, provider=provider)
        self.assertEqual(sgi.extract_graph_intent(QUESTION), result)
        provider.assert_not_called()
        self.assertEqual('lexical', self.span('graph_intent.selection').attributes['selected_interpreter'])
        self.assertEqual({}, tracing.collected_outcome())

    def test_semantic_selection_and_lexical_fallback_are_attributes_only(self):
        for raw, selected in [(PLAN, 'semantic'), ({'kind': 'none'}, 'lexical')]:
            with self.subTest(selected=selected), patch.object(sgi, '_lexical_decides', return_value=False):
                self.fake.spans.clear()
                question = QUESTION if selected == 'semantic' else '참새목 중 열매를 먹는 새는?'
                actual = sgi.graph_intent_handler(question, provider=lambda *_: raw)
                expected = (sgi.interpret(QUESTION, lambda *_: PLAN) if selected == 'semantic'
                            else sgi.extract_graph_intent(question))
                self.assertEqual(expected, actual)
                self.assertEqual(selected, self.span('graph_intent.selection').attributes['selected_interpreter'])
                self.assertEqual({}, tracing.collected_outcome())

    def test_recorded_payloads_use_existing_bounds_and_credential_key_redaction(self):
        plan = {**PLAN, 'api_key': 'dummy-secret', 'extra': 'x' * 3000}
        answerer = self.provider(plan=plan)
        self.assertEqual(plan, answerer(QUESTION, [], sgi.CONTRACT))
        recorded = self.span('graph_intent.plan').outputs
        self.assertEqual('[redacted]', recorded['api_key'])
        self.assertTrue(recorded['extra'].endswith('[truncated]'))
        self.assertLess(len(recorded['extra']), 2100)

    def test_disabled_and_broken_exporters_preserve_success_and_failure(self):
        expected = sgi.interpret(QUESTION, lambda *_: PLAN)
        for mode in ('disabled', 'start', 'write', 'end'):
            with self.subTest(mode=mode), ExitStack() as stack:
                stack.enter_context(patch.object(tracing, '_mlflow', None if mode == 'disabled' else self.fake))
                if mode == 'start':
                    stack.enter_context(patch.object(self.fake, 'start_span', side_effect=RuntimeError('offline')))
                elif mode == 'write':
                    for method in ('set_outputs', 'set_inputs', 'set_attributes', 'set_attribute'):
                        stack.enter_context(patch.object(FakeSpan, method, side_effect=RuntimeError('offline')))
                elif mode == 'end':
                    @contextmanager
                    def broken_end(**kwargs):
                        try:
                            yield FakeSpan(kwargs['name'], kwargs['span_type'], kwargs.get('attributes'), None)
                        finally:
                            raise RuntimeError('offline')
                    stack.enter_context(patch.object(self.fake, 'start_span', broken_end))
                self.assertEqual(expected, sgi.interpret(QUESTION, self.provider()))
                with self.assertRaisesRegex(sgi.SemanticIntentError, r'provider failed \(GeminiAnswerError\)'):
                    sgi.interpret(QUESTION, self.provider(audit={'faithful': False, 'issues': []}))
