"""Focused unittest-discoverable contracts for the integrated chat route."""

from __future__ import annotations

import math
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.api.semantic_router import SemanticRouter, SemanticRouterConfig
from robingraph.cli import serve_neo4j
from robingraph.embeddings import EmbeddingConfigurationError, JinaEmbeddingClient, JinaEmbeddingSettings
from robingraph.fixture import load_fixture
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.hybrid import HybridResult, HybridSearchOutcome
from robingraph.retrieval.operational import OperationalCitation, OperationalObservation, OperationalPlace, OperationalTaxon
from robingraph.retrieval.repository import SourceCitation
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


class FakeEmbeddings:
    def __init__(self, documents, query) -> None:
        self.documents, self.query = documents, query
        self.document_calls = self.query_calls = 0

    def embed_documents(self, _texts):
        self.document_calls += 1
        return self.documents

    def embed_query(self, _text):
        self.query_calls += 1
        return self.query


class FailingEmbeddings(FakeEmbeddings):
    def embed_documents(self, _texts):
        raise RuntimeError("secret-provider-detail")


def sample_lineage() -> TaxonomyLineage:
    return TaxonomyLineage(
        "Anas platyrhynchos", "AviList", "2025b", "avilist:2025b",
        (LineageTaxon("taxon:species", "species", "Anas platyrhynchos", None, "청둥오리"),),
    )


def sample_observation() -> OperationalObservation:
    return OperationalObservation(
        "gbif:1", "1", "2025-01-02", 1, "human_observation", "generalized", None, None, None,
        OperationalTaxon("taxon:1", "1", "Anas platyrhynchos", None, None, "species"),
        OperationalPlace("place:1", "Seoul", "KR"),
        OperationalCitation("evidence:1", "dataset:1", "GBIF", "https://example.invalid/source",
                            "https://example.invalid/dataset", ("https://creativecommons.org/licenses/by/4.0/",),
                            "2025-01-03", "2025-01-04"), (),
    )


def sample_evidence(*, with_fallback_warning: bool = True) -> HybridSearchOutcome:
    return HybridSearchOutcome(
        (HybridResult("chunk:1", "grounded excerpt", 0.2, ("fulltext",),
                      SourceCitation("source:1", "https://example.invalid", "p. 1", "CC-BY")),),
        (("Embedding request failed; results are keyword-only fulltext",) if with_fallback_warning else ()),
    )


def graph_repository_mock() -> Mock:
    repository = Mock()
    repository.list_places.return_value = ()
    repository.list_documents.return_value = ()
    repository.list_taxonomy.return_value = ()
    repository.mode = "neo4j"
    repository.taxonomy_release = "2025b"
    return repository


class SemanticRouterTest(unittest.TestCase):
    def test_cache_thresholds_ties_malformed_and_required_capabilities(self) -> None:
        fake = FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (1.0, 0.0))
        router = SemanticRouter(fake, config=SemanticRouterConfig(0.7, 0.1))
        self.assertEqual("taxonomy", router.classify("taxonomy"))
        self.assertEqual("taxonomy", router.classify("taxonomy again"))
        self.assertEqual(1, fake.document_calls)
        self.assertEqual(2, fake.query_calls)
        vectors = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))
        low_confidence = SemanticRouter(
            FakeEmbeddings(vectors, (0.8, 0.6)),
            config=SemanticRouterConfig(0.9, 0.1),
        )
        narrow_margin = SemanticRouter(
            FakeEmbeddings(vectors, (0.72, 0.69)),
            config=SemanticRouterConfig(0.7, 0.08),
        )
        tied = SemanticRouter(
            FakeEmbeddings(((1.0, 0.0), (1.0, 0.0), (-1.0, 0.0)), (1.0, 0.0))
        )
        self.assertIsNone(low_confidence.classify("x"))
        self.assertIsNone(narrow_margin.classify("x"))
        self.assertIsNone(tied.classify("x"))
        self.assertIsNone(SemanticRouter(FakeEmbeddings(((1.0, 0.0), (0.0, True), (-1.0, 0.0)), (1.0, 0.0))).classify("x"))
        with self.assertRaises(ValueError):
            SemanticRouter(FakeEmbeddings((), ()), prototypes=(("taxonomy", "x"), ("observations", "x")))
        with self.assertRaises(ValueError):
            SemanticRouterConfig(confidence_threshold=-0.1)
        with self.assertRaises(ValueError):
            SemanticRouterConfig(winner_margin_threshold=2.1)

        malformed = (
            (((1.0, 0.0), (0.0, 1.0)), (1.0, 0.0)),
            (((1.0, 0.0), (0.0, 1.0), (-1.0,)), (1.0, 0.0)),
            (((1.0, 0.0), (0.0, "bad"), (-1.0, 0.0)), (1.0, 0.0)),
            (((1.0, 0.0), (0.0, math.inf), (-1.0, 0.0)), (1.0, 0.0)),
            (((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (0.0, 0.0)),
        )
        for documents, query in malformed:
            with self.subTest(documents=documents, query=query):
                self.assertIsNone(SemanticRouter(FakeEmbeddings(documents, query)).classify("x"))

        self.assertIsNone(SemanticRouter(FailingEmbeddings((), ())).classify("x"))

    def test_jina_transport_uses_passage_for_prototypes_and_query_for_question(self) -> None:
        requests = []

        class Response:
            def read(self, _size):
                return b'{"model":"test","data":[{"index":0,"embedding":[1.0,0.0]},{"index":1,"embedding":[0.0,1.0]},{"index":2,"embedding":[-1.0,0.0]}]}'
            def close(self):
                pass

        def transport(request, **_kwargs):
            requests.append(request.data)
            # query request carries one input, so return one compatible row.
            if b'"task":"retrieval.query"' in request.data:
                class QueryResponse(Response):
                    def read(self, _size):
                        return b'{"model":"test","data":[{"index":0,"embedding":[1.0,0.0]}]}'
                return QueryResponse()
            return Response()

        client = JinaEmbeddingClient(JinaEmbeddingSettings("http://example.invalid/embed", "test", 2), urlopen=transport)
        self.assertEqual("taxonomy", SemanticRouter(client).classify("계통"))
        self.assertIn(b'"task":"retrieval.passage"', requests[0])
        self.assertIn(b'"task":"retrieval.query"', requests[1])


class SemanticChatApiTest(unittest.TestCase):
    def make_client(self, **kwargs) -> TestClient:
        return TestClient(create_app(FixtureRepository(load_fixture()), **kwargs))

    def test_auto_route_and_explicit_bypass_preserve_typed_results(self) -> None:
        auto = self.make_client(
            semantic_router=SemanticRouter(FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (1.0, 0.0))),
            lineage_handler=lambda _name: sample_lineage(),
        ).post("/v1/chat", json={"question": "학명 계통", "intent": "auto"})
        payload = auto.json()
        self.assertEqual(200, auto.status_code)
        self.assertEqual("semantic", payload["route_method"])
        self.assertEqual("AviList", payload["result"]["lineage"]["taxonomy_source"])
        self.assertEqual("avilist:2025b", payload["result"]["lineage"]["concept_set_id"])

        broken = Mock()
        broken.classify.side_effect = AssertionError("explicit route used router")
        taxonomy_queries = []
        observation_queries = []
        evidence_calls = []

        def taxonomy_handler(query):
            taxonomy_queries.append(query)
            return sample_lineage()

        def observations(query):
            observation_queries.append(query)
            return (sample_observation(),)

        def evidence(question, limit, hybrid):
            evidence_calls.append((question, limit, hybrid))
            return sample_evidence(with_fallback_warning=False)

        explicit = self.make_client(
            semantic_router=broken,
            lineage_handler=taxonomy_handler,
            observation_handler=observations,
            search_handler=evidence,
        )
        taxonomy = explicit.post(
            "/v1/chat",
            json={"question": "x", "intent": "taxonomy", "filters": {"kind": "taxonomy"}},
        ).json()
        observation_payload = explicit.post(
            "/v1/chat",
            json={
                "question": "x",
                "intent": "observations",
                "filters": {"kind": "observations", "place": "Seoul", "limit": 1},
            },
        ).json()
        evidence_payload = explicit.post(
            "/v1/chat",
            json={"question": "x", "intent": "evidence"},
        ).json()
        self.assertEqual("explicit", taxonomy["route_method"])
        self.assertEqual(["x"], taxonomy_queries)
        self.assertEqual("withheld", observation_payload["result"]["results"][0]["coordinate_disclosure"])
        self.assertIsNone(observation_payload["result"]["results"][0]["latitude"])
        self.assertEqual("2025-01-02", observation_payload["result"]["results"][0]["observed_at"])
        self.assertEqual("2025-01-03", observation_payload["result"]["results"][0]["citation"]["retrieved_at"])
        self.assertNotIn("data_cutoff", observation_payload)
        self.assertEqual(1, observation_queries[0].limit)
        self.assertEqual("Seoul", observation_queries[0].place)
        self.assertEqual("grounded excerpt", evidence_payload["result"]["search"]["results"][0]["text"])
        self.assertEqual(["fulltext"], evidence_payload["result"]["search"]["results"][0]["channels"])
        self.assertEqual([], evidence_payload["warnings"])
        self.assertEqual([("x", 10, False)], evidence_calls)
        broken.classify.assert_not_called()

        auto_evidence_calls = []

        def auto_evidence(question, limit, hybrid):
            auto_evidence_calls.append((question, limit, hybrid))
            return sample_evidence()

        auto_evidence_payload = self.make_client(
            semantic_router=SemanticRouter(
                FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (-1.0, 0.0))
            ),
            search_handler=auto_evidence,
        ).post(
            "/v1/chat",
            json={"question": "인용 근거", "intent": "auto"},
        ).json()
        self.assertEqual("evidence", auto_evidence_payload["selected_intent"])
        self.assertEqual("hybrid", auto_evidence_payload["result"]["search"]["requested_mode"])
        self.assertEqual(
            ["Embedding request failed; results are keyword-only fulltext"],
            auto_evidence_payload["warnings"],
        )
        self.assertEqual([("인용 근거", 10, True)], auto_evidence_calls)

    def test_auto_observations_preserves_typed_bounded_filters_and_complete_provenance(self) -> None:
        observation_queries = []

        def observations(query):
            observation_queries.append(query)
            return (sample_observation(),)

        auto_observations = self.make_client(
            semantic_router=SemanticRouter(
                FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (0.0, 1.0))
            ),
            observation_handler=observations,
        ).post(
            "/v1/chat",
            json={
                "question": "서울 청둥오리 관찰 기록",
                "intent": "auto",
                "filters": {
                    "kind": "observations",
                    "taxon_key": "1",
                    "scientific_name": "Anas platyrhynchos",
                    "place": "Seoul",
                    "observed_from": "2025-01-01",
                    "observed_to": "2025-01-31",
                    "limit": 2,
                },
            },
        )
        payload = auto_observations.json()

        self.assertEqual(200, auto_observations.status_code)
        self.assertEqual("observations", payload["selected_intent"])
        self.assertEqual("semantic", payload["route_method"])
        self.assertEqual("answer", payload["disposition"])
        self.assertEqual(2, payload["result"]["limit"])
        self.assertEqual(1, len(payload["result"]["results"]))
        self.assertEqual(1, len(observation_queries))
        query = observation_queries[0]
        self.assertEqual("1", query.taxon_key)
        self.assertEqual("Anas platyrhynchos", query.scientific_name)
        self.assertEqual("Seoul", query.place)
        self.assertEqual("2025-01-01", query.observed_from)
        self.assertEqual("2025-01-31", query.observed_to)
        self.assertEqual(2, query.limit)
        self.assertEqual(0, query.offset)

        observation = payload["result"]["results"][0]
        self.assertEqual("withheld", observation["coordinate_disclosure"])
        self.assertIsNone(observation["latitude"])
        self.assertIsNone(observation["longitude"])
        self.assertIsNone(observation["coordinate_uncertainty_m"])
        self.assertEqual(
            {
                "observation_id": "gbif:1", "occurrence_id": "1", "observed_at": "2025-01-02",
                "count": 1, "basis": "human_observation", "sensitivity": "generalized",
                "coordinate_disclosure": "withheld", "latitude": None, "longitude": None,
                "coordinate_uncertainty_m": None,
                "taxon": {
                    "taxon_id": "taxon:1", "external_key": "1", "scientific_name": "Anas platyrhynchos",
                    "canonical_name": None, "vernacular_name_raw": None, "rank": "species",
                },
                "place": {"place_id": "place:1", "name": "Seoul", "country_code": "KR"},
                "citation": {
                    "evidence_id": "evidence:1", "dataset_id": "dataset:1", "dataset_name": "GBIF",
                    "source_url": "https://example.invalid/source", "dataset_url": "https://example.invalid/dataset",
                    "license_uris": ["https://creativecommons.org/licenses/by/4.0/"],
                    "retrieved_at": "2025-01-03", "source_updated_at": "2025-01-04",
                },
                "media": [],
            },
            observation,
        )
        self.assertNotIn("data_cutoff", payload)

        evidence_payload = self.make_client(
            search_handler=lambda _question, _limit, _hybrid: sample_evidence(with_fallback_warning=False),
        ).post("/v1/chat", json={"question": "근거", "intent": "evidence", "filters": {"kind": "evidence", "limit": 1}}).json()
        self.assertEqual(
            {
                "chunk_id": "chunk:1", "text": "grounded excerpt", "score": 0.2,
                "channels": ["fulltext"],
                "citation": {
                    "source_id": "source:1", "source_url": "https://example.invalid",
                    "locator": "p. 1", "license_name": "CC-BY",
                },
            },
            evidence_payload["result"]["search"]["results"][0],
        )

    def test_validation_and_router_failure_are_safe(self) -> None:
        client = self.make_client()
        self.assertEqual(422, client.post("/v1/chat", json={"question": "   "}).status_code)
        self.assertEqual(422, client.post("/v1/chat", json={"question": "x", "intent": "observations", "filters": {"kind": "observations", "limit": 11}}).status_code)
        self.assertEqual(422, client.post("/v1/chat", json={"question": "x", "intent": "observations", "filters": {"kind": "observations", "common_name": "x"}}).status_code)
        response = self.make_client(
            semantic_router=SemanticRouter(FailingEmbeddings((), ()))
        ).post(
            "/v1/chat", json={"question": "x", "intent": "auto"}
        ).json()
        self.assertEqual("clarify", response["disposition"])
        self.assertIsNone(response["selected_intent"])
        self.assertNotIn("secret-provider-detail", str(response))

        observation_handler = Mock()
        no_scan = self.make_client(observation_handler=observation_handler).post(
            "/v1/chat",
            json={"question": "모든 관찰", "intent": "observations"},
        ).json()
        self.assertEqual("clarify", no_scan["disposition"])
        observation_handler.assert_not_called()

        mismatched_handler = Mock()
        mismatched = self.make_client(
            semantic_router=SemanticRouter(
                FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (1.0, 0.0))
            ),
            lineage_handler=mismatched_handler,
        ).post(
            "/v1/chat",
            json={
                "question": "분류",
                "intent": "auto",
                "filters": {"kind": "evidence", "limit": 1},
            },
        ).json()
        self.assertEqual("clarify", mismatched["disposition"])
        mismatched_handler.assert_not_called()

    def test_openapi_exposes_discriminated_result_and_preserves_legacy_paths(self) -> None:
        schema = self.make_client().get("/openapi.json").json()
        self.assertTrue(
            {"/health", "/v1/answers", "/v1/search", "/v1/observations", "/v1/taxa/lineage"}
            <= set(schema["paths"])
        )
        response_schema = schema["components"]["schemas"]["ChatResponse"]
        self.assertIn("route_method", response_schema["required"])
        result_schema = response_schema["properties"]["result"]
        self.assertEqual("kind", result_schema["discriminator"]["propertyName"])
        self.assertEqual(4, len(result_schema["oneOf"]))


class ServeNeo4jWiringTest(unittest.TestCase):
    def test_factory_injects_lazy_client_and_router_without_provider_call(self) -> None:
        arguments = Mock(host="127.0.0.1", port=9999)
        embedding_client = FakeEmbeddings(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)), (1.0, 0.0))
        repository = graph_repository_mock()
        operational = Mock()
        lineage = Mock()
        lineage.lineage_for_scientific_name.return_value = sample_lineage()
        served = {}

        def run_app(app, **_kwargs):
            # Construction/configuration alone must not warm the router.
            self.assertEqual(0, embedding_client.document_calls)
            self.assertEqual(0, embedding_client.query_calls)
            response = TestClient(app).post("/v1/chat", json={"question": "학명 계통", "intent": "auto"})
            served["payload"] = response.json()
            self.assertEqual(200, response.status_code)

        with patch("robingraph.cli.Neo4jSettings.from_environment", return_value=Mock()), \
             patch("robingraph.ingest.postgres.PostgresSettings.from_environment", return_value=Mock()), \
             patch("robingraph.embeddings.JinaEmbeddingClient.from_env", return_value=embedding_client), \
             patch("uvicorn.run", side_effect=run_app):
            # Imports inside serve_neo4j bind classes from their source module,
            # so patch them there rather than relying on cli module globals.
            with patch("robingraph.retrieval.neo4j_repository.Neo4jGraphRepository", return_value=repository), \
                 patch("robingraph.retrieval.operational_neo4j.Neo4jOperationalObservationRepository", return_value=operational), \
                 patch("robingraph.retrieval.taxonomy_lineage_neo4j.Neo4jTaxonomyLineageRepository", return_value=lineage):
                serve_neo4j(arguments)
        self.assertEqual(1, embedding_client.document_calls)
        self.assertEqual(1, embedding_client.query_calls)
        self.assertEqual("taxonomy", served["payload"]["selected_intent"])
        self.assertEqual("semantic", served["payload"]["route_method"])
        self.assertEqual("AviList", served["payload"]["result"]["lineage"]["taxonomy_source"])
        lineage.lineage_for_scientific_name.assert_called_once_with("학명 계통")

    def test_invalid_embedding_configuration_injects_no_router_without_stopping_factory(self) -> None:
        arguments = Mock(host="127.0.0.1", port=9999)
        repository = graph_repository_mock()
        operational, lineage = Mock(), Mock()
        operational.search_observations.return_value = (sample_observation(),)
        lineage.lineage_for_scientific_name.return_value = sample_lineage()
        served = {}

        def run_app(app, **_kwargs):
            client = TestClient(app)
            served["taxonomy"] = client.post(
                "/v1/chat",
                json={"question": "Anas platyrhynchos", "intent": "taxonomy"},
            ).json()
            served["observations"] = client.post(
                "/v1/chat",
                json={
                    "question": "Seoul observations",
                    "intent": "observations",
                    "filters": {"kind": "observations", "place": "Seoul", "limit": 1},
                },
            ).json()
            served["evidence"] = client.post(
                "/v1/chat",
                json={"question": "source", "intent": "evidence"},
            ).json()

        configuration = Mock(
            side_effect=EmbeddingConfigurationError("secret endpoint")
        )
        with patch("robingraph.cli.Neo4jSettings.from_environment", return_value=Mock()), \
             patch("robingraph.ingest.postgres.PostgresSettings.from_environment", return_value=Mock()), \
             patch("robingraph.embeddings.JinaEmbeddingClient.from_env", configuration), \
             patch("robingraph.retrieval.neo4j_hybrid.search", return_value=sample_evidence(with_fallback_warning=False)), \
             patch("uvicorn.run", side_effect=run_app), \
             patch("robingraph.retrieval.neo4j_repository.Neo4jGraphRepository", return_value=repository), \
             patch("robingraph.retrieval.operational_neo4j.Neo4jOperationalObservationRepository", return_value=operational), \
             patch("robingraph.retrieval.taxonomy_lineage_neo4j.Neo4jTaxonomyLineageRepository", return_value=lineage):
            serve_neo4j(arguments)
        self.assertEqual("answer", served["taxonomy"]["disposition"])
        self.assertEqual("answer", served["observations"]["disposition"])
        self.assertEqual("answer", served["evidence"]["disposition"])
        self.assertEqual("fulltext", served["evidence"]["result"]["search"]["requested_mode"])
        self.assertEqual(1, configuration.call_count)
        for payload in served.values():
            self.assertNotIn("secret endpoint", str(payload))
