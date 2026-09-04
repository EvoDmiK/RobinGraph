"""Mocked contract tests for the stdlib Jina-compatible embedding adapter."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
import unittest
from urllib.error import HTTPError, URLError

from robingraph.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingHTTPError,
    EmbeddingIntegrityError,
    EmbeddingResponseError,
    EmbeddingTransportError,
    EmbeddingProfile,
    JinaEmbeddingClient,
    JinaEmbeddingSettings,
    embed_fixture_chunks,
)
from robingraph.fixture import load_fixture


class _Response:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self, limit: int = -1) -> bytes:
        return self.body

    def close(self) -> None:
        self.closed = True


def _rows(vectors: list[list[float]], indexes: list[int] | None = None) -> dict[str, object]:
    indexes = indexes or list(range(len(vectors)))
    return {"data": [{"index": i, "embedding": vector} for i, vector in zip(indexes, vectors)]}


def _settings(**kwargs: object) -> JinaEmbeddingSettings:
    values: dict[str, object] = {
        "endpoint": "http://127.0.0.1:19191/embeddings",
        "model": "fixture-model",
        "dimensions": 3,
        "api_key": "secret",
        "normalized": False,
        "batch_size": 2,
        "timeout_seconds": 0.25,
    }
    values.update(kwargs)
    return JinaEmbeddingSettings(**values)  # type: ignore[arg-type]


class JinaHTTPContractTest(unittest.TestCase):
    def test_documents_are_bounded_and_request_uses_passage_task(self) -> None:
        requests: list[object] = []

        def fake_urlopen(request: object, timeout: float) -> _Response:
            requests.append((request, timeout))
            body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
            self.assertEqual("retrieval.passage", body["task"])
            self.assertLessEqual(len(body["input"]), 2)
            return _Response(_rows([[1, 2, 3]] * len(body["input"])))

        client = JinaEmbeddingClient(_settings(), urlopen=fake_urlopen)
        vectors = client.embed_documents(("one", "two", "three"))
        self.assertEqual(3, len(vectors))
        self.assertEqual(2, len(requests))
        request, timeout = requests[0]
        self.assertEqual(0.25, timeout)
        self.assertEqual("Bearer secret", request.get_header("Authorization"))  # type: ignore[attr-defined]

    def test_query_uses_query_task(self) -> None:
        def fake_urlopen(request: object, timeout: float) -> _Response:
            body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
            self.assertEqual("retrieval.query", body["task"])
            self.assertEqual(["what"], body["input"])
            return _Response(_rows([[0.1, 0.2, 0.3]]))

        self.assertEqual(
            (0.1, 0.2, 0.3),
            JinaEmbeddingClient(_settings(), urlopen=fake_urlopen).embed_query("what"),
        )

    def test_empty_documents_do_not_make_http_call(self) -> None:
        calls = 0

        def fake_urlopen(request: object, timeout: float) -> _Response:
            nonlocal calls
            calls += 1
            return _Response(_rows([]))

        self.assertEqual((), JinaEmbeddingClient(_settings(), urlopen=fake_urlopen).embed_documents(()))
        self.assertEqual(0, calls)

    def test_malformed_response_and_index_dimension_finite_fail(self) -> None:
        payloads = [
            {"not_data": []},
            _rows([[1, 2, 3]], [1]),
            _rows([[1, 2, 3], [4, 5, 6]], [0, 0]),
            _rows([[1, 2]], [0]),
            _rows([[1, math.inf, 3]], [0]),
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                client = JinaEmbeddingClient(_settings(), urlopen=lambda request, timeout: _Response(payload))
                with self.assertRaises(EmbeddingResponseError):
                    client.embed_documents(("text",))

    def test_http_and_transport_errors_are_safe(self) -> None:
        def http_failure(request: object, timeout: float) -> None:
            raise HTTPError("http://127.0.0.1", 503, "service unavailable", {}, None)

        with self.assertRaises(EmbeddingHTTPError) as http_context:
            JinaEmbeddingClient(_settings(), urlopen=http_failure).embed_query("x")
        self.assertEqual(503, http_context.exception.status)
        self.assertNotIn("secret", str(http_context.exception))

        def transport_failure(request: object, timeout: float) -> None:
            raise URLError("timed out")

        with self.assertRaises(EmbeddingTransportError):
            JinaEmbeddingClient(_settings(), urlopen=transport_failure).embed_query("x")


class SettingsAndFixturePolicyTest(unittest.TestCase):
    def test_endpoint_is_required_and_env_names_are_explicit(self) -> None:
        with self.assertRaises(EmbeddingConfigurationError):
            JinaEmbeddingSettings.from_env({"ROBINGRAPH_JINA_MODEL": "m", "ROBINGRAPH_JINA_DIMENSIONS": "3"})
        settings = JinaEmbeddingSettings.from_env(
            {
                "ROBINGRAPH_JINA_ENDPOINT": "http://localhost:9000/v1/embeddings",
                "ROBINGRAPH_JINA_MODEL": "m",
                "ROBINGRAPH_JINA_DIMENSIONS": "3",
                "ROBINGRAPH_JINA_NORMALIZED": "false",
                "ROBINGRAPH_JINA_BATCH_SIZE": "4",
                "ROBINGRAPH_JINA_TIMEOUT_SECONDS": "1.5",
            }
        )
        self.assertEqual("http://localhost:9000/v1/embeddings", settings.endpoint)
        self.assertFalse(settings.normalized)
        self.assertEqual(4, settings.batch_size)

    def test_fixture_embedding_rechecks_chunk_document_and_both_sources_before_http(self) -> None:
        corpus = load_fixture()
        calls: list[tuple[str, ...]] = []

        class FakeClient:
            profile = EmbeddingProfile("fixture-model", 3, False)

            def embed_documents(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
                calls.append(texts)
                return tuple((1.0, 2.0, 3.0) for _ in texts)

            def embed_query(self, text: str) -> tuple[float, ...]:
                return (1.0, 2.0, 3.0)

        embedded = embed_fixture_chunks(corpus, FakeClient())
        self.assertEqual(4, len(embedded))
        self.assertEqual(1, len(calls))  # fake itself is not bounded; adapter owns batching

        cases = []
        denied_chunk = deepcopy(corpus.chunks[0])
        denied_chunk["license_policy_status"] = "denied"
        cases.append(replace(corpus, chunks=(denied_chunk,)))
        review_document = deepcopy(corpus.documents[0])
        review_document["license_policy_status"] = "review_required"
        cases.append(replace(corpus, documents=(review_document,)))
        embedding_denied_document = deepcopy(corpus.documents[0])
        embedding_denied_document["embedding_allowed"] = False
        cases.append(replace(corpus, documents=(embedding_denied_document,)))
        chunk_storage_denied_document = deepcopy(corpus.documents[0])
        chunk_storage_denied_document["chunk_storage_allowed"] = False
        cases.append(replace(corpus, documents=(chunk_storage_denied_document,)))
        missing_document = deepcopy(corpus.chunks[0])
        missing_document["document_id"] = "missing"
        cases.append(replace(corpus, chunks=(missing_document,)))
        missing_chunk_source = deepcopy(corpus.chunks[0])
        missing_chunk_source["source_id"] = "missing-source"
        cases.append(replace(corpus, chunks=(missing_chunk_source,)))
        missing_document_source = deepcopy(corpus.documents[0])
        missing_document_source["source_id"] = "missing-source"
        cases.append(replace(corpus, documents=(missing_document_source,)))
        denied_registry = dict(corpus.source_registry)
        denied_registry["fixture-document"] = {**denied_registry["fixture-document"], "license_policy_status": "denied"}
        cases.append(replace(corpus, source_registry=denied_registry))
        for case in cases:
            with self.subTest(case=case):
                calls.clear()
                self.assertEqual((), embed_fixture_chunks(case, FakeClient()))
                self.assertEqual([], calls)

    def test_hash_mismatch_fails_before_http(self) -> None:
        corpus = load_fixture()
        changed = deepcopy(corpus.chunks[0])
        changed["text"] = "tampered"
        case = replace(corpus, chunks=(changed,))
        calls = 0

        class FakeClient:
            profile = EmbeddingProfile("fixture-model", 3, False)

            def embed_documents(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
                nonlocal calls
                calls += 1
                return ((1.0, 2.0, 3.0),)

            def embed_query(self, text: str) -> tuple[float, ...]:
                return (1.0, 2.0, 3.0)

        with self.assertRaises(EmbeddingIntegrityError):
            embed_fixture_chunks(case, FakeClient())
        self.assertEqual(0, calls)

    def test_fake_client_result_dimension_and_finite_values_are_checked(self) -> None:
        corpus = load_fixture()
        for vector in (((1.0, 2.0),) * 4, ((1.0, math.inf, 3.0),) * 4):
            class FakeClient:
                profile = EmbeddingProfile("fixture-model", 3, False)

                def embed_documents(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
                    return vector

                def embed_query(self, text: str) -> tuple[float, ...]:
                    return vector[0]

            with self.subTest(vector=vector), self.assertRaises(EmbeddingResponseError):
                embed_fixture_chunks(corpus, FakeClient())


if __name__ == "__main__":
    unittest.main()
