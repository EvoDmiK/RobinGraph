from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from robingraph.api.app import (
    OperationalBackendUnavailableError,
    SearchBackendUnavailableError,
    TaxonomyLineageBackendUnavailableError,
    create_app,
    create_neo4j_lineage_handler,
    create_neo4j_observation_handler,
    create_neo4j_search_handler,
)
from robingraph.embeddings import EmbeddingConfigurationError, EmbeddingHTTPError
from robingraph.fixture import load_fixture
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.hybrid import HybridResult, HybridSearchOutcome
from robingraph.retrieval.operational import (
    OperationalCitation,
    OperationalMedia,
    OperationalObservation,
    OperationalObservationQuery,
    OperationalPlace,
    OperationalTaxon,
)
from robingraph.retrieval.repository import SourceCitation
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


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

    def test_operational_observations_are_declared_but_unavailable_in_fixture_mode(self) -> None:
        operation = self.client.get("/openapi.json").json()["paths"]["/v1/observations"]["get"]
        self.assertIn("503", operation["responses"])
        response = self.client.get("/v1/observations")
        self.assertEqual(503, response.status_code)

    def test_operational_observations_pass_filters_and_disclose_provenance(self) -> None:
        calls: list[OperationalObservationQuery] = []
        observation = OperationalObservation(
            observation_id="gbif-observation:123",
            occurrence_id="123",
            observed_at="2026-09-07T10:00:00Z",
            count=2,
            basis="human_observation",
            sensitivity="public",
            latitude=37.5,
            longitude=127.0,
            coordinate_uncertainty_m=25.0,
            taxon=OperationalTaxon(
                taxon_id="gbif-taxon:2498349",
                external_key="2498349",
                scientific_name="Anas zonorhyncha",
                canonical_name="Anas zonorhyncha",
                vernacular_name_raw="Eastern Spot-billed Duck",
                rank="species",
            ),
            place=OperationalPlace("gbif-place:KR:Seoul", "Seoul", "KR"),
            citation=OperationalCitation(
                evidence_id="gbif-evidence:123",
                dataset_id="gbif-dataset:dataset-1",
                dataset_name="GBIF occurrence dataset",
                source_url="https://api.gbif.org/v1/occurrence/123",
                dataset_url="https://www.gbif.org/dataset/dataset-1",
                license_uris=("https://creativecommons.org/licenses/by/4.0/",),
                retrieved_at="2026-09-08T00:00:00Z",
                source_updated_at="2026-09-07T12:00:00Z",
            ),
            media=(
                OperationalMedia(
                    media_id="gbif-media:123",
                    media_type="stillimage",
                    format="image/jpeg",
                    landing_uri="https://example.invalid/media/123",
                    asset_uri="https://example.invalid/media/123.jpg",
                    creator="Observer",
                    publisher="Publisher",
                    attribution="Observer / CC BY 4.0",
                    license_uri="https://creativecommons.org/licenses/by/4.0/",
                ),
            ),
        )

        def handler(query: OperationalObservationQuery) -> tuple[OperationalObservation, ...]:
            calls.append(query)
            return (observation,)

        client = TestClient(
            create_app(FixtureRepository(load_fixture()), observation_handler=handler)
        )
        response = client.get(
            "/v1/observations",
            params={
                "taxon_key": "2498349",
                "scientific_name": "Anas",
                "place": "Seoul",
                "observed_from": "2026-09-01",
                "observed_to": "2026-09-08",
                "limit": 10,
                "offset": 5,
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            OperationalObservationQuery(
                taxon_key="2498349",
                scientific_name="Anas",
                place="Seoul",
                observed_from="2026-09-01",
                observed_to="2026-09-08",
                limit=10,
                offset=5,
            ),
            calls[0],
        )
        payload = response.json()
        self.assertEqual("operational", payload["mode"])
        self.assertEqual("gbif", payload["data_source"])
        self.assertFalse(payload["fixture_only"])
        self.assertEqual("public", payload["results"][0]["coordinate_disclosure"])
        self.assertEqual(37.5, payload["results"][0]["latitude"])
        self.assertEqual("gbif-evidence:123", payload["results"][0]["citation"]["evidence_id"])
        self.assertEqual(
            ["https://creativecommons.org/licenses/by/4.0/"],
            payload["results"][0]["citation"]["license_uris"],
        )
        self.assertEqual("gbif-media:123", payload["results"][0]["media"][0]["media_id"])

    def test_generalized_observation_coordinates_are_withheld(self) -> None:
        observation = OperationalObservation(
            observation_id="gbif-observation:generalized",
            occurrence_id="generalized",
            observed_at="2026-09-07",
            count=None,
            basis="human_observation",
            sensitivity="generalized",
            latitude=None,
            longitude=None,
            coordinate_uncertainty_m=None,
            taxon=OperationalTaxon("gbif-taxon:1", "1", "Bird one", None, None, "species"),
            place=OperationalPlace("gbif-place:KR:x", "Somewhere", "KR"),
            citation=OperationalCitation(
                "gbif-evidence:generalized",
                "gbif-dataset:x",
                "GBIF occurrence dataset",
                "https://api.gbif.org/v1/occurrence/generalized",
                "https://www.gbif.org/dataset/x",
                ("https://creativecommons.org/publicdomain/zero/1.0/",),
                "2026-09-08T00:00:00Z",
                None,
            ),
            media=(),
        )
        client = TestClient(
            create_app(
                FixtureRepository(load_fixture()),
                observation_handler=lambda _query: (observation,),
            )
        )
        payload = client.get("/v1/observations").json()
        self.assertEqual("withheld", payload["results"][0]["coordinate_disclosure"])
        self.assertIsNone(payload["results"][0]["latitude"])
        self.assertIn("generalized", payload["warnings"][0])

    def test_operational_observation_filters_are_validated(self) -> None:
        client = TestClient(
            create_app(FixtureRepository(load_fixture()), observation_handler=lambda _query: ())
        )
        self.assertEqual(422, client.get("/v1/observations?limit=101").status_code)
        self.assertEqual(422, client.get("/v1/observations?offset=-1").status_code)
        self.assertEqual(422, client.get("/v1/observations?place=%20%20").status_code)
        self.assertEqual(
            422,
            client.get(
                "/v1/observations?observed_from=2026-09-08&observed_to=2026-09-01"
            ).status_code,
        )

    def test_taxonomy_lineage_trims_the_query_and_returns_avilist_lineage(self) -> None:
        calls: list[str] = []
        lineage = TaxonomyLineage(
            query_scientific_name="Anas zonorhyncha",
            taxonomy_source="AviList",
            taxonomy_release="2025b",
            concept_set_id="avilist-2025b",
            items=(
                LineageTaxon("order:anseriformes", "order", "Anseriformes", None),
                LineageTaxon("family:anatidae", "family", "Anatidae", "Leach, 1820"),
                LineageTaxon("genus:anas", "genus", "Anas", "Linnaeus, 1758"),
                LineageTaxon("species:anas-zonorhyncha", "species", "Anas zonorhyncha", None),
            ),
        )

        def handler(scientific_name: str) -> TaxonomyLineage:
            calls.append(scientific_name)
            return lineage

        client = TestClient(create_app(FixtureRepository(load_fixture()), lineage_handler=handler))
        response = client.get("/v1/taxa/lineage", params={"scientific_name": "  Anas zonorhyncha  "})

        self.assertEqual(200, response.status_code)
        self.assertEqual(["Anas zonorhyncha"], calls)
        self.assertEqual(
            {
                "query_scientific_name": "Anas zonorhyncha",
                "taxonomy_source": "AviList",
                "taxonomy_release": "2025b",
                "concept_set_id": "avilist-2025b",
                "lineage": [
                    {
                        "taxon_id": "order:anseriformes",
                        "rank": "order",
                        "scientific_name": "Anseriformes",
                        "authority": None,
                    },
                    {
                        "taxon_id": "family:anatidae",
                        "rank": "family",
                        "scientific_name": "Anatidae",
                        "authority": "Leach, 1820",
                    },
                    {
                        "taxon_id": "genus:anas",
                        "rank": "genus",
                        "scientific_name": "Anas",
                        "authority": "Linnaeus, 1758",
                    },
                    {
                        "taxon_id": "species:anas-zonorhyncha",
                        "rank": "species",
                        "scientific_name": "Anas zonorhyncha",
                        "authority": None,
                    },
                ],
            },
            response.json(),
        )

    def test_taxonomy_lineage_rejects_blank_and_overlong_queries(self) -> None:
        client = TestClient(create_app(FixtureRepository(load_fixture()), lineage_handler=lambda _name: None))
        self.assertEqual(422, client.get("/v1/taxa/lineage?scientific_name=%20").status_code)
        self.assertEqual(422, client.get("/v1/taxa/lineage", params={"scientific_name": "x" * 201}).status_code)

    def test_taxonomy_lineage_not_found_and_unavailable_are_distinguished(self) -> None:
        missing_client = TestClient(
            create_app(FixtureRepository(load_fixture()), lineage_handler=lambda _name: None)
        )
        self.assertEqual(404, missing_client.get("/v1/taxa/lineage?scientific_name=Anas%20zonorhyncha").status_code)

        unavailable_client = TestClient(
            create_app(
                FixtureRepository(load_fixture()),
                lineage_handler=lambda _name: (_ for _ in ()).throw(
                    TaxonomyLineageBackendUnavailableError("AviList reference taxonomy is unavailable")
                ),
            )
        )
        response = unavailable_client.get("/v1/taxa/lineage?scientific_name=Anas%20zonorhyncha")
        self.assertEqual(503, response.status_code)
        self.assertEqual("AviList reference taxonomy is unavailable", response.json()["detail"])

    def test_taxonomy_lineage_is_declared_but_unavailable_without_a_neo4j_handler(self) -> None:
        operation = self.client.get("/openapi.json").json()["paths"]["/v1/taxa/lineage"]["get"]
        parameter = next(value for value in operation["parameters"] if value["name"] == "scientific_name")
        self.assertEqual("query", parameter["in"])
        self.assertEqual(1, parameter["schema"]["minLength"])
        self.assertEqual(200, parameter["schema"]["maxLength"])
        self.assertIn("404", operation["responses"])
        self.assertIn("503", operation["responses"])
        self.assertEqual(
            503,
            self.client.get("/v1/taxa/lineage?scientific_name=Anas%20zonorhyncha").status_code,
        )


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


class Neo4jOperationalHandlerTest(unittest.TestCase):
    def test_repository_failure_is_hidden_behind_safe_error(self) -> None:
        class BrokenRepository:
            def search_observations(self, _query: OperationalObservationQuery):
                raise ValueError("raw graph details")

        handler = create_neo4j_observation_handler(BrokenRepository())
        with self.assertRaisesRegex(
            OperationalBackendUnavailableError, "Operational GBIF observation search is unavailable"
        ) as caught:
            handler(OperationalObservationQuery())
        self.assertNotIn("raw graph details", str(caught.exception))


class Neo4jLineageHandlerTest(unittest.TestCase):
    def test_repository_failure_is_hidden_behind_safe_error(self) -> None:
        class BrokenRepository:
            def lineage_for_scientific_name(self, _scientific_name: str):
                raise ValueError("raw graph details")

        handler = create_neo4j_lineage_handler(BrokenRepository())
        with self.assertRaisesRegex(
            TaxonomyLineageBackendUnavailableError, "AviList reference-taxonomy lineage is unavailable"
        ) as caught:
            handler("Anas zonorhyncha")
        self.assertNotIn("raw graph details", str(caught.exception))
