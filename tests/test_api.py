from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from robingraph.api.app import SearchBackendUnavailableError, create_app, create_neo4j_search_handler
from robingraph.embeddings import EmbeddingConfigurationError, EmbeddingHTTPError
from robingraph.fixture import load_fixture
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.hybrid import HybridResult, HybridSearchOutcome
from robingraph.retrieval.repository import SourceCitation


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(FixtureRepository(load_fixture())))

    def test_health_discloses_fixture_mode(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("fixture", response.json()["mode"])

    def test_answer_contains_only_allowed_evidence(self) -> None:
        response = self.client.post("/v1/answers", json={"question": "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("answer", payload["disposition"])
        self.assertEqual(["fixture-occ-001"], payload["evidence_ids"])
        self.assertEqual("fixture-occ-001", payload["citations"][0]["evidence_id"])

    def test_sensitive_coordinate_request_abstains_over_http(self) -> None:
        response = self.client.post("/v1/answers", json={"question": "말똥가리의 정확한 관찰 좌표를 알려줘."})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("abstain", payload["disposition"])
        self.assertNotIn("37.54", payload["answer_text"])

    def test_blank_question_is_rejected(self) -> None:
        response = self.client.post("/v1/answers", json={"question": ""})
        self.assertEqual(422, response.status_code)

    def test_search_is_declared_but_unavailable_in_fixture_mode(self) -> None:
        operation = self.client.get("/openapi.json").json()["paths"]["/v1/search"]["post"]
        self.assertIn("503", operation["responses"])
        response = self.client.post("/v1/search", json={"question": "물새", "mode": "hybrid", "limit": 5})
        self.assertEqual(503, response.status_code)

    def test_search_returns_rank_channels_and_citation(self) -> None:
        calls: list[tuple[str, int, bool]] = []

        def search_handler(question: str, limit: int, hybrid: bool) -> HybridSearchOutcome:
            calls.append((question, limit, hybrid))
            citation = SourceCitation("source", "https://example.invalid/source", "section 1", "CC BY 4.0")
            result = HybridResult("chunk-1", "호수의 물새 기록", 0.03, ("fulltext", "vector"), citation)
            return HybridSearchOutcome((result,), ())

        client = TestClient(
            create_app(FixtureRepository(load_fixture()), search_handler=search_handler)
        )
        response = client.post(
            "/v1/search",
            json={"question": "호수와 하천에서 관찰된 물새", "mode": "hybrid", "limit": 5},
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual([("호수와 하천에서 관찰된 물새", 5, True)], calls)
        self.assertEqual("hybrid", payload["requested_mode"])
        self.assertEqual("hybrid", payload["mode"])
        self.assertTrue(payload["fixture_only"])
        self.assertEqual(["fulltext", "vector"], payload["results"][0]["channels"])
        self.assertEqual("section 1", payload["results"][0]["citation"]["locator"])

    def test_search_rejects_invalid_mode_and_limit(self) -> None:
        response = self.client.post("/v1/search", json={"question": "물새", "mode": "vector", "limit": 101})
        self.assertEqual(422, response.status_code)

    def test_search_discloses_fulltext_fallback_from_requested_hybrid(self) -> None:
        citation = SourceCitation("source", "https://example.invalid/source", "section 1", "CC BY 4.0")
        outcome = HybridSearchOutcome(
            (HybridResult("chunk-1", "text", 0.01, ("fulltext",), citation),),
            ("Embedding request failed; results are keyword-only fulltext",),
        )
        client = TestClient(
            create_app(FixtureRepository(load_fixture()), search_handler=lambda *_args: outcome)
        )
        response = client.post("/v1/search", json={"question": "물새", "mode": "hybrid"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("hybrid", response.json()["requested_mode"])
        self.assertEqual("fulltext", response.json()["mode"])
        self.assertIn("keyword-only", response.json()["warnings"][0])

    def test_search_backend_failure_is_503(self) -> None:
        def unavailable(_question: str, _limit: int, _hybrid: bool) -> HybridSearchOutcome:
            raise SearchBackendUnavailableError("Neo4j search is unavailable")

        client = TestClient(create_app(FixtureRepository(load_fixture()), search_handler=unavailable))
        response = client.post("/v1/search", json={"question": "물새"})
        self.assertEqual(503, response.status_code)
        self.assertEqual("Neo4j search is unavailable", response.json()["detail"])


class Neo4jApiSearchHandlerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Neo4jSettings("bolt://localhost:7687", "neo4j", "test-only", "neo4j")
        self.citation = SourceCitation("source", "https://example.invalid/source", "section 1", "CC BY 4.0")
        self.outcome = HybridSearchOutcome(
            (HybridResult("chunk-1", "text", 0.01, ("fulltext",), self.citation),),
            (),
        )

    def test_fulltext_mode_does_not_create_embedding_client(self) -> None:
        handler = create_neo4j_search_handler(self.settings)
        with patch("robingraph.embeddings.JinaEmbeddingClient.from_env") as client, patch(
            "robingraph.retrieval.neo4j_hybrid.search", return_value=self.outcome
        ) as search:
            outcome = handler("물새", 5, False)
        self.assertEqual(self.outcome, outcome)
        client.assert_not_called()
        self.assertEqual(("fulltext",), search.call_args.args[1].channels)
        self.assertNotIn("query_embedder", search.call_args.kwargs)

    def test_hybrid_mode_passes_embedding_client(self) -> None:
        handler = create_neo4j_search_handler(self.settings)
        embedder = object()
        with patch("robingraph.embeddings.JinaEmbeddingClient.from_env", return_value=embedder), patch(
            "robingraph.retrieval.neo4j_hybrid.search", return_value=self.outcome
        ) as search:
            handler("물새", 5, True)
        self.assertEqual(("fulltext", "vector"), search.call_args.args[1].channels)
        self.assertIs(embedder, search.call_args.kwargs["query_embedder"])

    def test_embedding_provider_failure_falls_back_to_fulltext(self) -> None:
        handler = create_neo4j_search_handler(self.settings)
        with patch("robingraph.embeddings.JinaEmbeddingClient.from_env", return_value=object()), patch(
            "robingraph.retrieval.neo4j_hybrid.search",
            side_effect=(EmbeddingHTTPError(503), self.outcome),
        ) as search:
            outcome = handler("물새", 5, True)
        self.assertEqual(2, search.call_count)
        self.assertEqual(("fulltext",), search.call_args.args[1].channels)
        self.assertIn("keyword-only", outcome.warnings[-1])

    def test_invalid_embedding_configuration_is_unavailable(self) -> None:
        handler = create_neo4j_search_handler(self.settings)
        with patch(
            "robingraph.embeddings.JinaEmbeddingClient.from_env",
            side_effect=EmbeddingConfigurationError("missing endpoint"),
        ), self.assertRaisesRegex(SearchBackendUnavailableError, "missing endpoint"):
            handler("물새", 5, True)
