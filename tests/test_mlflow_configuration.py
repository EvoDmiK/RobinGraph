"""Tests for optional, fail-open MLflow tracing configuration in RobinGraph."""

from __future__ import annotations

import json
import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from robingraph import tracing
from robingraph.tracing import (
    CHAIN,
    DEFAULT_EXPERIMENT_NAME,
    EMBEDDING,
    ENABLE_ENV,
    LLM,
    NOOP_SPAN,
    RETRIEVER,
    TOOL,
    TracingStatus,
    _SafeSpan,
    configure_tracing,
    is_enabled,
    redact,
    reset_tracing,
    span,
    status,
)


class MLflowConfigurationTest(TestCase):
    def tearDown(self) -> None:
        reset_tracing()
        super().tearDown()

    def test_disabled_by_default(self) -> None:
        reset_tracing()
        result = configure_tracing({})
        self.assertFalse(result.enabled)
        self.assertFalse(is_enabled())
        self.assertIn("not enabled", result.reason)
        self.assertEqual(status(), result)

    def test_disabled_when_flag_is_falsey(self) -> None:
        for val in ("0", "false", "no", "off", "", "something_else"):
            with self.subTest(val=val):
                reset_tracing()
                result = configure_tracing({ENABLE_ENV: val})
                self.assertFalse(result.enabled)
                self.assertFalse(is_enabled())

    def test_disabled_when_uri_scheme_is_invalid(self) -> None:
        for invalid_uri in ("file:///tmp/mlruns", "ftp://example.com", "unknown://foo", ""):
            with self.subTest(uri=invalid_uri):
                reset_tracing()
                result = configure_tracing({
                    ENABLE_ENV: "true",
                    "MLFLOW_TRACKING_URI": invalid_uri,
                })
                self.assertFalse(result.enabled)
                self.assertIn("http(s) or databricks URI", result.reason)

    def test_bounded_http_defaults_applied(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "http://mlflow.example.internal:5000",
        }
        with patch.dict(os.environ, {}, clear=True), patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            configure_tracing(env)
            self.assertEqual(env["MLFLOW_HTTP_REQUEST_MAX_RETRIES"], "2")
            self.assertEqual(env["MLFLOW_HTTP_REQUEST_TIMEOUT"], "10")

    def test_configure_with_default_experiment_name(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "http://mlflow.example.internal:5000",
        }
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            result = configure_tracing(env)
            self.assertTrue(result.enabled)
            self.assertTrue(result.langchain_autolog)
            self.assertTrue(is_enabled())
            mock_mlflow.set_tracking_uri.assert_called_once_with("http://mlflow.example.internal:5000")
            mock_mlflow.set_experiment.assert_called_once_with(DEFAULT_EXPERIMENT_NAME)
            mock_mlflow.langchain.autolog.assert_called_once_with(silent=True)

    def test_configure_with_custom_experiment_name(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "https://tracking.example.com",
            "MLFLOW_EXPERIMENT_NAME": "custom-robingraph-exp",
        }
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            result = configure_tracing(env)
            self.assertTrue(result.enabled)
            mock_mlflow.set_experiment.assert_called_once_with("custom-robingraph-exp")

    def test_configure_with_experiment_id(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "https://tracking.example.com",
            "MLFLOW_EXPERIMENT_ID": "12345",
        }
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            result = configure_tracing(env)
            self.assertTrue(result.enabled)
            mock_mlflow.set_experiment.assert_called_once_with(experiment_id="12345")

    def test_fail_open_on_tracking_server_initialization_error(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        mock_mlflow.set_experiment.side_effect = RuntimeError("Tracking server unreachable")
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "http://down.internal:5000",
        }
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            result = configure_tracing(env)
            self.assertFalse(result.enabled)
            self.assertFalse(is_enabled())
            self.assertIn("initialization failed (RuntimeError)", result.reason)

    def test_gemini_autolog_enabled_when_sdk_available(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "http://mlflow.example.internal:5000",
        }
        with (
            patch.dict("sys.modules", {"mlflow": mock_mlflow}),
            patch("robingraph.tracing._google_genai_sdk_available", return_value=True),
        ):
            result = configure_tracing(env)
            self.assertTrue(result.enabled)
            self.assertTrue(result.gemini_autolog)
            mock_mlflow.gemini.autolog.assert_called_once_with(silent=True)

    def test_reset_tracing_resets_state_and_disables_autolog(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "http://mlflow.example.internal:5000",
        }
        with (
            patch.dict("sys.modules", {"mlflow": mock_mlflow}),
            patch("robingraph.tracing._google_genai_sdk_available", return_value=True),
        ):
            configure_tracing(env)
            self.assertTrue(is_enabled())
            reset_tracing()
            self.assertFalse(is_enabled())
            self.assertEqual(status().reason, "reset")
            mock_mlflow.langchain.autolog.assert_called_with(disable=True, silent=True)
            mock_mlflow.gemini.autolog.assert_called_with(disable=True, silent=True)


class MLflowSpanAndRedactionTest(TestCase):
    def tearDown(self) -> None:
        reset_tracing()
        super().tearDown()

    def test_span_context_manager_when_disabled(self) -> None:
        reset_tracing()
        with span("test.span", CHAIN, {"key": "val"}) as s:
            self.assertIs(s, NOOP_SPAN)
            s.set_inputs({"q": "test"})
            s.set_outputs({"a": "result"})
            s.set_attribute("attr", "val")
            s.set_attributes({"attr2": "val2"})
            s.set_token_usage(10, 20, 30)

    def test_span_context_manager_re_raises_user_exception(self) -> None:
        reset_tracing()
        with self.assertRaises(ValueError):
            with span("test.error", CHAIN):
                raise ValueError("domain error")

    def test_span_when_enabled_invokes_mlflow_start_span(self) -> None:
        mock_mlflow = MagicMock()
        mock_manager = MagicMock()
        mock_live_span = MagicMock()
        mock_manager.__enter__.return_value = mock_live_span
        mock_mlflow.start_span.return_value = mock_manager

        with patch("robingraph.tracing._mlflow", mock_mlflow):
            with span("active.span", LLM, {"key": "safe_val"}) as s:
                self.assertIsInstance(s, _SafeSpan)
                s.set_inputs({"prompt": "hello"})
                s.set_outputs({"reply": "world"})
                s.set_attribute("status", "ok")
                s.set_token_usage(100, 50, 150)

            mock_mlflow.start_span.assert_called_once_with(
                name="active.span",
                span_type=LLM,
                attributes={"key": "safe_val"},
            )
            mock_live_span.set_inputs.assert_called_once_with({"prompt": "hello"})
            mock_live_span.set_outputs.assert_called_once_with({"reply": "world"})
            mock_live_span.set_attributes.assert_called_with({"status": "ok"})
            mock_live_span.set_attribute.assert_called_with(
                "mlflow.chat.tokenUsage",
                {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            )

    def test_safe_span_swallows_mlflow_errors(self) -> None:
        mock_live_span = MagicMock()
        mock_live_span.set_inputs.side_effect = RuntimeError("SDK failure")
        safe = _SafeSpan(mock_live_span)
        # Calling set_inputs must not raise
        safe.set_inputs({"data": "test"})

    def test_token_usage_calculates_total_if_omitted(self) -> None:
        mock_live_span = MagicMock()
        safe = _SafeSpan(mock_live_span)
        safe.set_token_usage(40, 60)
        mock_live_span.set_attribute.assert_called_once_with(
            "mlflow.chat.tokenUsage",
            {"input_tokens": 40, "output_tokens": 60, "total_tokens": 100},
        )

    def test_redact_sensitive_keys(self) -> None:
        payload = {
            "api_key": "secret123",
            "x-goog-api-key": "secret456",
            "password": "pass",
            "neo4j_password": "pass",
            "bearer_token": "token",
            "auth_token": "token",
            "credentials": {"secret": "val"},
            "safe_field": "safe_value",
            "nested": {
                "private_key": "pk",
                "normal": "ok",
            },
        }
        redacted = redact(payload)
        self.assertEqual(redacted["api_key"], "[redacted]")
        self.assertEqual(redacted["x-goog-api-key"], "[redacted]")
        self.assertEqual(redacted["password"], "[redacted]")
        self.assertEqual(redacted["neo4j_password"], "[redacted]")
        self.assertEqual(redacted["bearer_token"], "[redacted]")
        self.assertEqual(redacted["auth_token"], "[redacted]")
        self.assertEqual(redacted["credentials"], "[redacted]")
        self.assertEqual(redacted["safe_field"], "safe_value")
        self.assertEqual(redacted["nested"]["private_key"], "[redacted]")
        self.assertEqual(redacted["nested"]["normal"], "ok")

    def test_redact_truncates_long_strings(self) -> None:
        long_text = "a" * 2500
        redacted = redact(long_text)
        self.assertEqual(len(redacted), 2000 + len("...[truncated]"))
        self.assertTrue(redacted.endswith("...[truncated]"))

    def test_redact_bounds_large_collections(self) -> None:
        large_list = list(range(100))
        redacted_list = redact(large_list)
        self.assertEqual(len(redacted_list), 51)
        self.assertEqual(redacted_list[-1], "[truncated]")

        large_dict = {f"k{i}": i for i in range(100)}
        redacted_dict = redact(large_dict)
        self.assertIn("[truncated]", redacted_dict)
        self.assertTrue(redacted_dict["[truncated]"])

    def test_redact_depth_limit(self) -> None:
        deep = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": "deep"}}}}}}
        redacted = redact(deep)
        l5 = redacted["l1"]["l2"]["l3"]["l4"]["l5"]
        self.assertEqual(l5, "[truncated]")


class MLflowInvariantsTest(TestCase):
    def test_constants_and_span_types(self) -> None:
        self.assertEqual(CHAIN, "CHAIN")
        self.assertEqual(RETRIEVER, "RETRIEVER")
        self.assertEqual(EMBEDDING, "EMBEDDING")
        self.assertEqual(LLM, "LLM")
        self.assertEqual(TOOL, "TOOL")

    def test_supported_https_uri_scheme(self) -> None:
        reset_tracing()
        mock_mlflow = MagicMock()
        env = {
            ENABLE_ENV: "true",
            "MLFLOW_TRACKING_URI": "https://mlflow.dove-nest.com",
            "MLFLOW_EXPERIMENT_NAME": "robingraph",
        }
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            res = configure_tracing(env)
            self.assertTrue(res.enabled)
            mock_mlflow.set_tracking_uri.assert_called_once_with("https://mlflow.dove-nest.com")

    def test_gemini_answerer_tracing_behavior(self) -> None:
        from robingraph.generation import GeminiAnswerer
        from robingraph.retrieval.hybrid import HybridResult
        from robingraph.retrieval.repository import SourceCitation

        # When urlopen is provided, it forces REST fallback
        mock_urlopen = MagicMock()
        answer = {"text": "청둥오리", "evidence_ids": ["c1"]}
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        }).encode("utf-8")
        resp.close.return_value = None
        mock_urlopen.return_value = resp

        answerer = GeminiAnswerer(api_key="secret", urlopen=mock_urlopen)
        evidence = (
            HybridResult("c1", "text", 0.9, ("fulltext",), SourceCitation("s1", "http://x", "p1", "CC0")),
        )
        res = answerer("질문", evidence)
        self.assertEqual(res.text, "청둥오리")
