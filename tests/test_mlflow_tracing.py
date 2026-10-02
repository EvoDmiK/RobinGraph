"""MLflow tracing contracts: disabled by default, fail-open, one connected trace per request.

Two layers are exercised.  A tiny in-process fake ``mlflow`` module proves the
startup and span wiring in the default test environment (no tracing extra).
When the optional ``mlflow-tracing`` extra is installed, the same request is
replayed through the real SDK with its exporter captured locally -- no
tracking server or network is used -- to prove LangChain autolog spans and
RobinGraph's manual Jina/Neo4j/Gemini spans share a single parent trace.
"""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import io
import json
import os
import sys
import types
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from robingraph import tracing
from robingraph.api.app import create_app, create_neo4j_search_handler
from robingraph.api.semantic_router import SemanticRouter
from robingraph.embeddings import QUERY_TASK, PASSAGE_TASK, JinaEmbeddingClient, JinaEmbeddingSettings
from robingraph.fixture import load_fixture
from robingraph.generation import GeminiAnswerer
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, HybridResult, HybridSearchOutcome
from robingraph.retrieval.repository import SourceCitation

DIMENSIONS = 512
ENABLED_ENV = {"ROBINGRAPH_MLFLOW_TRACING": "true", "MLFLOW_TRACKING_URI": "http://mlflow.invalid:5000"}
HAS_MLFLOW = importlib.util.find_spec("mlflow") is not None
try:
    HAS_GENAI = importlib.util.find_spec("google.genai") is not None
except ImportError:
    HAS_GENAI = False


class _Response(io.BytesIO):
    pass


def _basis(index: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


class FakeJinaServer:
    """Routes prototype passages to orthogonal axes and every query to 'evidence'."""

    def __init__(self) -> None:
        self.tasks: list[str] = []
        self.headers: list[dict] = []

    def __call__(self, request, timeout):
        payload = json.loads(request.data)
        self.tasks.append(payload["task"])
        self.headers.append(dict(request.header_items()))
        assert payload["dimensions"] == DIMENSIONS
        if payload["task"] == PASSAGE_TASK:
            axes = {"taxonomy": 0, "observations": 1, "evidence": 2}
            vectors = [_basis(next(axis for word, axis in axes.items() if word in text)) for text in payload["input"]]
        else:
            vectors = [_basis(2) for _ in payload["input"]]
        rows = [{"index": index, "embedding": vector} for index, vector in enumerate(vectors)]
        return _Response(json.dumps({"data": rows}).encode())


class FakeGeminiServer:
    def __init__(self, *, status: int | None = None) -> None:
        self.status = status
        self.calls = 0

    def __call__(self, request, timeout):
        self.calls += 1
        if self.status is not None:
            from urllib.error import HTTPError

            raise HTTPError(request.full_url, self.status, "provider body with secret", {}, io.BytesIO(b"secret"))
        answer = {"text": "청둥오리는 물가에 삽니다.", "evidence_ids": ["chunk-1"]}
        return _Response(json.dumps({
            "candidates": [{"content": {"parts": [{"text": json.dumps(answer, ensure_ascii=False)}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30, "totalTokenCount": 150},
            "modelVersion": "gemini-test-001",
        }).encode())


def _result() -> HybridResult:
    return HybridResult(
        "chunk-1", "Mallards live near water.", 0.9, (FULLTEXT_CHANNEL, VECTOR_CHANNEL),
        SourceCitation("source-1", "https://example.org/source", "p1", "CC-BY-4.0"),
    )


def _fake_neo4j_search(settings, request, *, query_embedder=None):
    # Stands in for the parameterized-Cypher search: the real one embeds the
    # query only when the vector channel is requested.
    if query_embedder is not None and VECTOR_CHANNEL in request.channels:
        query_embedder.embed_query(request.query_text)
    return HybridSearchOutcome((_result(),), ())


def _chat_app(gemini: FakeGeminiServer, jina: FakeJinaServer, answerer: GeminiAnswerer | None = None):
    client = JinaEmbeddingClient(JinaEmbeddingSettings(
        endpoint="https://jina.invalid/v1/embeddings", model="jina-embeddings-v3",
        dimensions=DIMENSIONS, api_key="jina-secret-key",
    ), urlopen=jina)
    settings = Neo4jSettings("bolt://neo4j.invalid:7687", "neo4j", "neo4j-password", "neo4j")
    answerer = answerer or GeminiAnswerer("gemini-secret-key", model="gemini-test", urlopen=gemini)
    return create_app(
        FixtureRepository(load_fixture()),
        search_handler=create_neo4j_search_handler(settings, embedding_client=client),
        answer_generator=answerer,
        semantic_router=SemanticRouter(client),
    )


GEMINI_DOCUMENT = {
    "candidates": [{
        "content": {"role": "model", "parts": [{"text": json.dumps(
            {"text": "청둥오리는 물가에 삽니다.", "evidence_ids": ["chunk-1"]}, ensure_ascii=False)}]},
        "finishReason": "STOP",
    }],
    "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30, "totalTokenCount": 150},
    "modelVersion": "gemini-test-001",
}


def _sdk_answerer(handler) -> GeminiAnswerer:
    """A real google-genai Client whose HTTP layer is an in-process httpx transport."""

    import httpx
    from google import genai
    from google.genai import types

    client = genai.Client(api_key="gemini-secret-key", http_options=types.HttpOptions(
        api_version="v1beta", httpx_client=httpx.Client(transport=httpx.MockTransport(handler))))
    return GeminiAnswerer("gemini-secret-key", model="gemini-test", genai_client=client)


def _post_chat(app):
    with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _fake_neo4j_search):
        return TestClient(app).post("/v1/chat", json={"question": "청둥오리 서식지 근거 문헌을 찾아줘"})


class DisabledTracingTest(unittest.TestCase):
    def tearDown(self) -> None:
        tracing.reset_tracing()

    def test_tracing_is_off_without_the_opt_in_flag(self) -> None:
        status = tracing.configure_tracing({"MLFLOW_TRACKING_URI": "http://mlflow.invalid"})
        self.assertFalse(status.enabled)
        self.assertFalse(tracing.is_enabled())
        with tracing.span("anything", tracing.LLM) as span:
            self.assertIs(tracing.NOOP_SPAN, span)
            span.set_token_usage(1, 2)

    def test_invalid_or_missing_tracking_uri_disables_without_echoing_it(self) -> None:
        for uri in ("", "file:///tmp/mlruns", "user:pa55word@mlflow.invalid"):
            status = tracing.configure_tracing({"ROBINGRAPH_MLFLOW_TRACING": "1", "MLFLOW_TRACKING_URI": uri})
            self.assertFalse(status.enabled)
            self.assertNotIn("pa55word", status.reason)

    def test_missing_optional_extra_disables_tracing(self) -> None:
        with mock.patch.dict(sys.modules, {"mlflow": None}):
            status = tracing.configure_tracing(dict(ENABLED_ENV))
        self.assertFalse(status.enabled)
        self.assertIn("tracing", status.reason)

    def test_initialization_failure_is_fail_open(self) -> None:
        fake = FakeMlflow()
        fake.set_experiment = mock.Mock(side_effect=ConnectionError("https://user:pw@host down"))
        with mock.patch.dict(sys.modules, {"mlflow": fake}):
            with self.assertLogs("robingraph.tracing", "WARNING") as logs:
                status = tracing.configure_tracing(dict(ENABLED_ENV))
        self.assertFalse(status.enabled)
        self.assertNotIn("pw@", "\n".join(logs.output))
        self.assertEqual([], fake.langchain.calls)

    def test_disabled_chat_response_and_provider_calls_are_unchanged(self) -> None:
        gemini, jina = FakeGeminiServer(), FakeJinaServer()
        response = _post_chat(_chat_app(gemini, jina))
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(("evidence", "semantic", "answer"), (body["selected_intent"], body["route_method"], body["disposition"]))
        self.assertEqual("청둥오리는 물가에 삽니다. [chunk-1]", body["answer_text"])
        # Query/passage task distinction is preserved: prototypes, routing query, hybrid query.
        self.assertEqual([PASSAGE_TASK, QUERY_TASK, QUERY_TASK], jina.tasks)
        self.assertEqual(1, gemini.calls)

    def test_redaction_drops_credentials_and_bounds_payloads(self) -> None:
        redacted = tracing.redact({
            "api_key": "k", "Authorization": "Bearer x", "access_token": "t", "taxon_key": "2498",
            "input_tokens": 3, "text": "x" * 5000, "items": list(range(80)),
        })
        self.assertEqual("[redacted]", redacted["api_key"])
        self.assertEqual("[redacted]", redacted["Authorization"])
        self.assertEqual("[redacted]", redacted["access_token"])
        self.assertEqual("2498", redacted["taxon_key"])
        self.assertEqual(3, redacted["input_tokens"])
        self.assertLess(len(redacted["text"]), 2100)
        self.assertEqual("[truncated]", redacted["items"][-1])


class FakeSpan:
    def __init__(self, name, span_type, attributes, parent):
        self.name, self.span_type, self.parent = name, span_type, parent
        self.attributes = dict(attributes or {})
        self.inputs = self.outputs = self.error = None

    def set_inputs(self, value):
        self.inputs = value

    def set_outputs(self, value):
        self.outputs = value

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_attributes(self, values):
        self.attributes.update(values)


class FakeMlflow(types.ModuleType):
    """Records configuration calls and span nesting like MLflow's fluent API."""

    def __init__(self) -> None:
        super().__init__("mlflow")
        self.spans: list[FakeSpan] = []
        self._stack: list[FakeSpan] = []
        self.set_tracking_uri = mock.Mock()
        self.set_experiment = mock.Mock()
        self.langchain = types.SimpleNamespace(calls=[], autolog=lambda **kw: self.langchain.calls.append(kw))
        self.gemini = types.SimpleNamespace(calls=[], autolog=lambda **kw: self.gemini.calls.append(kw))

    @contextmanager
    def start_span(self, name, span_type, attributes=None):
        span = FakeSpan(name, span_type, attributes, self._stack[-1] if self._stack else None)
        self.spans.append(span)
        self._stack.append(span)
        try:
            yield span
        except BaseException as error:
            span.error = type(error).__name__
            raise
        finally:
            self._stack.pop()


class FakeTracingWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = FakeMlflow()
        patcher = mock.patch.dict(sys.modules, {"mlflow": self.fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(tracing.reset_tracing)
        env = {**ENABLED_ENV, "MLFLOW_EXPERIMENT_NAME": "robingraph-test"}
        with mock.patch.dict(os.environ, {}, clear=False):
            self.status = tracing.configure_tracing(env)

    def test_startup_configures_server_experiment_and_langchain_autolog(self) -> None:
        self.assertTrue(self.status.enabled)
        self.fake.set_tracking_uri.assert_called_once_with(ENABLED_ENV["MLFLOW_TRACKING_URI"])
        self.fake.set_experiment.assert_called_once_with("robingraph-test")
        self.assertEqual([{"silent": True}], self.fake.langchain.calls)
        # Gemini autolog patches only the Google GenAI SDKs, so it follows SDK presence.
        self.assertEqual(tracing._google_genai_sdk_available(), self.status.gemini_autolog)
        self.assertEqual(len(self.fake.gemini.calls), int(self.status.gemini_autolog))

    def test_chat_request_is_one_parent_with_routing_retrieval_and_model_children(self) -> None:
        response = _post_chat(_chat_app(FakeGeminiServer(), FakeJinaServer()))
        self.assertEqual(200, response.status_code)
        roots = [span for span in self.fake.spans if span.parent is None]
        self.assertEqual(["POST /v1/chat"], [span.name for span in roots])
        root = roots[0]
        self.assertEqual("answer", root.attributes["robingraph.disposition"])

        def ancestors(span):
            while span.parent is not None:
                span = span.parent
                yield span

        by_name = {}
        for span in self.fake.spans:
            by_name.setdefault(span.name, []).append(span)
            self.assertIn(root, [span, *ancestors(span)])
        embeds = by_name["jina.embed"]
        self.assertEqual([PASSAGE_TASK, QUERY_TASK, QUERY_TASK], [span.attributes["embedding.task"] for span in embeds])
        self.assertTrue(all(span.attributes["embedding.dimensions"] == DIMENSIONS for span in embeds))
        self.assertEqual("semantic_router.classify", embeds[0].parent.name)
        retrieval = by_name["neo4j.hybrid_search"][0]
        self.assertEqual(tracing.RETRIEVER, retrieval.span_type)
        self.assertEqual([FULLTEXT_CHANNEL, VECTOR_CHANNEL], retrieval.attributes["retrieval.channels"])
        self.assertIs(retrieval, embeds[2].parent)
        llm = by_name["gemini.generate_content"][0]
        self.assertEqual(tracing.LLM, llm.span_type)
        self.assertEqual({"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}, llm.attributes["mlflow.chat.tokenUsage"])
        self.assertEqual("gemini-test-001", llm.attributes["llm.model_version"])
        self.assertNotIn("secret", json.dumps([span.attributes for span in self.fake.spans], default=str))

    def test_model_error_is_recorded_on_its_span_and_chat_falls_back(self) -> None:
        response = _post_chat(_chat_app(FakeGeminiServer(status=500), FakeJinaServer()))
        self.assertEqual(200, response.status_code)
        self.assertEqual("근거 문서를 확인했습니다.", response.json()["answer_text"])
        llm = next(span for span in self.fake.spans if span.name == "gemini.generate_content")
        self.assertEqual("GeminiAnswerError", llm.error)
        self.assertEqual(500, llm.attributes["http.status_code"])

    def test_span_backend_failures_never_break_the_request(self) -> None:
        def broken_start_span(**_kwargs):
            raise RuntimeError("exporter down")

        self.fake.start_span = broken_start_span
        response = _post_chat(_chat_app(FakeGeminiServer(), FakeJinaServer()))
        self.assertEqual(200, response.status_code)
        self.assertEqual("청둥오리는 물가에 삽니다. [chunk-1]", response.json()["answer_text"])


@unittest.skipUnless(HAS_MLFLOW, "optional 'tracing' extra (mlflow-tracing) is not installed")
class RealMlflowTracingTest(unittest.TestCase):
    """Real SDK spans, captured at the exporter so no tracking server is contacted."""

    def setUp(self) -> None:
        import mlflow
        import mlflow.tracking.fluent as tracking_fluent
        from mlflow.tracing.export.mlflow_v3 import MlflowV3SpanExporter

        self.exported = []
        env_patch = mock.patch.dict(os.environ, {"MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        previous_experiment = tracking_fluent._active_experiment_id

        def set_experiment(*_args, **_kwargs):
            # The lightweight SDK resolves traces against the active experiment.
            tracking_fluent._active_experiment_id = "robingraph-test"

        def restore():
            tracking_fluent._active_experiment_id = previous_experiment
            mlflow.tracing.reset()

        for patcher in (
            mock.patch.object(mlflow, "set_experiment", side_effect=set_experiment),
            mock.patch.object(MlflowV3SpanExporter, "export", lambda _self, spans: self.exported.extend(spans)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(restore)
        self.addCleanup(tracing.reset_tracing)
        mlflow.tracing.reset()
        self.assertTrue(tracing.configure_tracing(dict(ENABLED_ENV)).enabled)

    def test_autolog_and_manual_spans_form_one_connected_trace(self) -> None:
        response = _post_chat(_chat_app(FakeGeminiServer(), FakeJinaServer()))
        self.assertEqual(200, response.status_code)
        spans = list(self.exported)
        self.assertEqual(1, len({span.context.trace_id for span in spans}))
        roots = [span for span in spans if span.parent is None]
        self.assertEqual(["POST /v1/chat"], [span.name for span in roots])
        ids = {span.context.span_id for span in spans}
        self.assertTrue(all(span.parent.span_id in ids for span in spans if span.parent is not None))
        names = {span.name for span in spans}
        # LangChain autolog covers the LCEL evidence flow; manual spans cover the rest.
        self.assertTrue({"RunnableSequence", "retrieve_evidence", "answer_evidence"} <= names, names)
        self.assertTrue({"semantic_router.classify", "jina.embed", "neo4j.hybrid_search", "gemini.generate_content"} <= names)
        llm = next(span for span in spans if span.name == "gemini.generate_content")
        self.assertEqual('"LLM"', llm.attributes["mlflow.spanType"])
        self.assertEqual(150, json.loads(llm.attributes["mlflow.chat.tokenUsage"])["total_tokens"])
        flat = json.dumps([dict(span.attributes) for span in spans], default=str)
        self.assertNotIn("gemini-secret-key", flat)
        self.assertNotIn("jina-secret-key", flat)

    @unittest.skipUnless(HAS_GENAI, "google-genai is not installed")
    def test_native_gemini_autolog_spans_replace_manual_llm_span_under_the_request(self) -> None:
        import httpx

        self.assertTrue(tracing.status().gemini_autolog)
        answerer = _sdk_answerer(lambda _r: httpx.Response(200, json=GEMINI_DOCUMENT))
        response = _post_chat(_chat_app(FakeGeminiServer(), FakeJinaServer(), answerer))
        self.assertEqual("청둥오리는 물가에 삽니다. [chunk-1]", response.json()["answer_text"])
        spans = list(self.exported)
        self.assertEqual(1, len({span.context.trace_id for span in spans}))
        by_id = {span.context.span_id: span for span in spans}
        root = next(span for span in spans if span.parent is None)
        self.assertEqual("POST /v1/chat", root.name)
        llm_spans = [span for span in spans if span.attributes.get("mlflow.spanType") in ('"LLM"', '"CHAT_MODEL"')]
        # Autolog owns every LLM span (it wraps generate_content and its private
        # _generate_content); the REST-only manual span must not appear.
        self.assertEqual({"Models.generate_content", "Models._generate_content"}, {span.name for span in llm_spans})
        self.assertNotIn("gemini.generate_content", {span.name for span in spans})
        ancestor = llm_spans[0]
        while ancestor.parent is not None:
            ancestor = by_id[ancestor.parent.span_id]
        self.assertIs(root, ancestor)
        # MLflow sums usage only from the outermost span carrying it, so the
        # trace total equals the single provider call (no manual duplicate).
        def has_usage(span):
            return "mlflow.chat.tokenUsage" in span.attributes

        def usage_ancestor(span):
            while span.parent is not None:
                span = by_id[span.parent.span_id]
                if has_usage(span):
                    return True
            return False

        outermost = [span for span in spans if has_usage(span) and not usage_ancestor(span)]
        self.assertEqual([150], [json.loads(span.attributes["mlflow.chat.tokenUsage"])["total_tokens"] for span in outermost])
        self.assertNotIn("gemini-secret-key", json.dumps([dict(span.attributes) for span in spans], default=str))

    def test_failed_model_call_marks_only_its_span_as_error(self) -> None:
        response = _post_chat(_chat_app(FakeGeminiServer(status=503), FakeJinaServer()))
        self.assertEqual(200, response.status_code)
        statuses = {span.name: span.status.status_code.name for span in self.exported}
        self.assertEqual("ERROR", statuses["gemini.generate_content"])
        self.assertEqual("OK", statuses["POST /v1/chat"])


@unittest.skipUnless(HAS_GENAI, "optional 'tracing' extra (google-genai) is not installed")
class NativeGeminiSdkTest(unittest.TestCase):
    """The native SDK path feeds the same validators and keeps the REST safety contract."""

    def _answer(self, handler):
        from robingraph.generation import GeminiAnswerError

        answerer = _sdk_answerer(handler)
        try:
            return answerer("청둥오리는 어디에 사나요?", (_result(),)), None
        except GeminiAnswerError as error:
            return None, error

    def test_sdk_is_default_without_injected_transport_and_rest_with_it(self) -> None:
        self.assertTrue(GeminiAnswerer("k")._use_sdk)
        self.assertFalse(GeminiAnswerer("k", urlopen=FakeGeminiServer())._use_sdk)
        with mock.patch("robingraph.generation._google_genai_installed", return_value=False):
            self.assertFalse(GeminiAnswerer("k")._use_sdk)

    def test_structured_request_and_validated_answer(self) -> None:
        import httpx

        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=GEMINI_DOCUMENT)

        answer, error = self._answer(handler)
        self.assertIsNone(error)
        self.assertEqual(("청둥오리는 물가에 삽니다.", ("chunk-1",)), (answer.text, answer.evidence_ids))
        self.assertEqual(1, len(requests))
        self.assertTrue(requests[0].url.path.endswith("/v1beta/models/gemini-test:generateContent"))
        self.assertEqual("gemini-secret-key", requests[0].headers["x-goog-api-key"])
        body = json.loads(requests[0].content)
        self.assertNotIn("gemini-secret-key", requests[0].content.decode())
        self.assertEqual("user", body["contents"][0]["role"])
        self.assertIn("evidence_id: chunk-1", body["contents"][0]["parts"][0]["text"])
        config = body["generationConfig"]
        self.assertEqual("application/json", config["responseMimeType"])
        self.assertEqual(["evidence_ids", "text"], sorted(config["responseSchema"]["properties"]))

    def test_unavailable_retries_once_then_errors_are_redacted(self) -> None:
        import httpx

        statuses = [503, 200]
        answer, error = self._answer(lambda _r: httpx.Response(statuses.pop(0), json=GEMINI_DOCUMENT if not statuses else {"error": {"message": "secret body"}}))
        self.assertIsNone(error)
        self.assertEqual("청둥오리는 물가에 삽니다.", answer.text)
        _, error = self._answer(lambda _r: httpx.Response(400, json={"error": {"code": 400, "message": "secret body"}}))
        self.assertEqual("Gemini HTTP error 400", str(error))
        self.assertIsNone(error.__cause__)

        def broken(_request):
            raise httpx.ConnectError("secret host")

        _, error = self._answer(broken)
        self.assertEqual("Gemini request failed: ConnectError", str(error))

    def test_blocked_and_unsupported_outputs_are_rejected_by_existing_validators(self) -> None:
        import httpx

        blocked = {**GEMINI_DOCUMENT, "candidates": [{**GEMINI_DOCUMENT["candidates"][0], "finishReason": "SAFETY"}]}
        _, error = self._answer(lambda _r: httpx.Response(200, json=blocked))
        self.assertEqual("Gemini blocked the response", str(error))
        unknown = json.loads(json.dumps(GEMINI_DOCUMENT))
        unknown["candidates"][0]["content"]["parts"][0]["text"] = json.dumps({"text": "x", "evidence_ids": ["other"]})
        _, error = self._answer(lambda _r: httpx.Response(200, json=unknown))
        self.assertIn("not supplied", str(error))

    def test_oversized_sdk_response_is_rejected(self) -> None:
        import httpx

        huge = json.loads(json.dumps(GEMINI_DOCUMENT))
        huge["candidates"][0]["content"]["parts"][0]["text"] = "x" * (2 * 1024 * 1024 + 1)
        _, error = self._answer(lambda _r: httpx.Response(200, json=huge))
        self.assertEqual("Gemini response exceeded the maximum allowed size", str(error))


if __name__ == "__main__":
    unittest.main()
