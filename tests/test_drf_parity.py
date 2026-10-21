"""HTTP contract of the native Django/DRF app against the frozen FastAPI baseline.

The legacy FastAPI adapter was removed after RG-701.  Before removal, every
request below was answered by it and recorded in
`fixtures/drf_parity_golden.json` (status, contract headers and body:
JSON-equal for JSON, byte-identical otherwise).  The Django app must still
answer each request exactly as recorded.  Apps are built from injected fakes
(fixture repository and in-memory handlers/store; no Neo4j, PostgreSQL or
provider calls).  `OpenApiContractTest` keeps the frozen OpenAPI documents
in step with the Pydantic DTOs they were generated from.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
from datetime import date, datetime
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
from typing import get_args
import unittest
from unittest.mock import patch

from pydantic.json_schema import models_json_schema

from asgi_client import TestClient
from robingraph.api import ingest_service, schemas
from robingraph.api.drf import create_django_app
from robingraph.api.schemas import (
    OperationalBackendUnavailableError,
    SearchBackendUnavailableError,
    TaxonomyLineageBackendUnavailableError,
)
from robingraph.fixture import load_fixture
from robingraph.ingest.store import IngestionConflictError, IngestionStateError
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, HybridResult, HybridSearchOutcome
from robingraph.retrieval.operational import (
    OperationalCitation,
    OperationalObservation,
    OperationalPlace,
    OperationalTaxon,
)
from robingraph.retrieval.repository import SourceCitation
from robingraph.retrieval.species_profile import SpeciesNotFoundError
from robingraph.retrieval.species_scope import SpeciesScope
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage
from test_ingest_api import TOKEN_ENV, FakeIngestStore

def frozen_openapi(*, ingest: bool) -> dict:
    """The packaged OpenAPI document the app serves (recorded from the FastAPI adapter)."""

    name = "openapi_ingest.json" if ingest else "openapi.json"
    return json.loads(resources.files("robingraph.api.drf").joinpath(name).read_text(encoding="utf-8"))


GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "drf_parity_golden.json").read_text(encoding="utf-8"))
CONTRACT_HEADERS = ("content-type", "cache-control", "location", "allow", "www-authenticate")
CONTEXT = {"concept_set_id": "avilist-2025", "taxonomy_release": "AviList 2025"}


def _lineage(name: str) -> TaxonomyLineage | None:
    if name == "down":
        raise TaxonomyLineageBackendUnavailableError("AviList reference-taxonomy lineage is unavailable")
    if name not in ("Anas zonorhyncha", "흰뺨검둥오리"):
        return None
    return TaxonomyLineage(
        query_scientific_name="Anas zonorhyncha", taxonomy_source="AviList", taxonomy_release="AviList 2025",
        concept_set_id="avilist-2025", query_name=name,
        matched_by="korean_name" if name == "흰뺨검둥오리" else "scientific_name",
        items=(
            LineageTaxon("order:anseriformes", "order", "Anseriformes", None, None),
            LineageTaxon("family:anatidae", "family", "Anatidae", "Leach, 1820", "오리과"),
            LineageTaxon("species:anas-zonorhyncha", "species", "Anas zonorhyncha", None, "흰뺨검둥오리",
                         korean_name_status="source-preferred"),
        ),
    )


def _taxon(name: str) -> dict:
    return {"taxon_id": "species:anas-zonorhyncha", "scientific_name": "Anas zonorhyncha",
            "korean_name": "흰뺨검둥오리", "rank": "species", "query": name}


def _profile(name: str) -> dict:
    if name == "boom":
        raise RuntimeError("provider detail must not leak")
    if name not in ("Anas zonorhyncha", "흰뺨검둥오리"):
        raise SpeciesNotFoundError(name)
    # Undeclared handler payloads keep the legacy encoder rules (tuples, dates).
    return {"taxon": _taxon(name), "lineage": CONTEXT, "traits": ({"name": "mass", "value": 1.5},),
            "summary": "흰뺨검둥오리 요약", "observed_on": date(2026, 1, 2), "warnings": []}


def _relations(name: str, species_scope: str = "all") -> dict:
    if name == "boom":
        raise RuntimeError("provider detail must not leak")
    if name == "unknown":
        raise SpeciesNotFoundError(name)
    return {"taxon": _taxon(name), **CONTEXT, "groups": [{"rank": "genus", "relation": "habitat", "items": []}]}


def _name_relations(name: str) -> dict | None:
    if name == "boom":
        raise RuntimeError("db detail")
    if name == "snapshot":
        return None
    return {"query": name, "is_search_term": False, "relations": [], "summary": ""}


def _observations(query) -> tuple[OperationalObservation, ...]:
    if query.taxon_key == "down":
        raise OperationalBackendUnavailableError("Operational GBIF observation search is unavailable")
    observation = OperationalObservation(
        observation_id="obs-1", occurrence_id="occ-1", observed_at="2025-01-02", count=None,
        basis="HUMAN_OBSERVATION", sensitivity="generalized", latitude=None, longitude=None,
        coordinate_uncertainty_m=None,
        taxon=OperationalTaxon("gbif:1", "1", "Anas zonorhyncha", "Anas zonorhyncha", "흰뺨검둥오리", "SPECIES"),
        place=OperationalPlace("place:kr", "서울", "KR"),
        citation=OperationalCitation("gbif-occ-1", "ds-1", "Dataset", "https://gbif.org/occurrence/1",
                                     "https://gbif.org/dataset/1", ("https://creativecommons.org/licenses/by/4.0/",),
                                     "2026-01-01T00:00:00Z", None),
        media=(),
    )
    return (observation,) if query.taxon_key != "empty" else ()


def _search(question: str, limit: int, hybrid: bool) -> HybridSearchOutcome:
    if question == "down":
        raise SearchBackendUnavailableError("internal provider detail")
    citation = SourceCitation("src-1", "https://example.org/paper", "p. 3", "CC-BY-4.0")
    channels = (FULLTEXT_CHANNEL, VECTOR_CHANNEL) if hybrid else (FULLTEXT_CHANNEL,)
    return HybridSearchOutcome(results=(HybridResult("chunk-1", "흰뺨검둥오리 서식지", 0.5, channels, citation),),
                               warnings=("fixture search",))


def _resolution(name: str, species_scope: str = "all") -> dict:
    if name == "흰뺨검둥오리":
        return {"mention": name, "status": "matched", "method": "graph_exact", "canonical_name": "Anas zonorhyncha",
                "taxon_id": "species:anas-zonorhyncha", **CONTEXT}
    return {"mention": name, "status": "not_found", "method": "none"}


HANDLERS = dict(
    search_handler=_search, observation_handler=_observations, lineage_handler=_lineage,
    korean_lineage_handler=_lineage, species_profile_handler=_profile, species_basic_profile_handler=_profile,
    related_species_handler=_relations, similar_species_handler=_relations,
    ecological_relations_handler=_relations, subspecies_handler=_relations, name_relations_handler=_name_relations,
    taxon_name_resolution_handler=_resolution,
)


def _sha256_json(body) -> str:
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _plain(value):
    """Store call arguments as JSON-comparable data (the golden encoding)."""

    if dataclasses.is_dataclass(value):
        return {"type": type(value).__name__,
                **{field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)}}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


class ParityCase(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.expected = iter(GOLDEN.get(f"{type(self).__name__}.{self._testMethodName}", ()))

    def build(self, **kwargs) -> TestClient:
        return TestClient(create_django_app(FixtureRepository(load_fixture()), **kwargs), raise_server_exceptions=False)

    def assert_same(self, client: TestClient, method: str, path: str, **kwargs):
        """Answer the next recorded request exactly as the legacy app did."""

        label = f"{method} {path} {kwargs!r}"
        golden = next(self.expected, None)
        self.assertIsNotNone(golden, f"no recorded legacy response for {label}")
        self.assertEqual(golden["request"], label, "request order diverged from the recorded baseline")
        actual = client.request(method, path, follow_redirects=False, **kwargs)
        self.assertEqual(golden["status"], actual.status_code, label)
        for header in CONTRACT_HEADERS:
            left, right = golden["headers"].get(header), actual.headers.get(header)
            if header == "allow" and left and right:
                # Starlette joined a set for its plain documentation routes, so the recorded order is arbitrary.
                left, right = set(left.split(", ")), set(right.split(", "))
            self.assertEqual(left, right, f"{label} [{header}]")
        if "json" in golden:
            self.assertEqual(golden["json"], actual.json(), label)
        elif "json_sha256" in golden:
            self.assertEqual(golden["json_sha256"], _sha256_json(actual.json()), label)
        elif "text" in golden:
            self.assertEqual(golden["text"].encode(), actual.content, label)
        elif "base64" in golden:
            self.assertEqual(base64.b64decode(golden["base64"]), actual.content, label)
        else:
            self.assertEqual((golden["body_length"], golden["body_sha256"]),
                             (len(actual.content), hashlib.sha256(actual.content).hexdigest()), label)
        return actual

    def assert_replayed(self) -> None:
        self.assertIsNone(next(self.expected, None), "recorded legacy responses were not all replayed")


class PublicApiParityTest(ParityCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = self.build(**HANDLERS)

    def test_query_routes_success_errors_and_validation(self) -> None:
        for route in ("profile", "related", "similar", "ecological-related", "subspecies", "name-relations"):
            for query in ("", "?name=", "?name=%20", "?name=" + "x" * 201, "?name=Anas%20zonorhyncha",
                          "?name=%ED%9D%B0%EB%BA%A8%EA%B2%80%EB%91%A5%EC%98%A4%EB%A6%AC", "?name=unknown",
                          "?name=boom", "?name=snapshot", "?name=Anas%20zonorhyncha&species_scope=korea",
                          "?name=Anas%20zonorhyncha&species_scope=invalid", "?name=a&name=Anas%20zonorhyncha"):
                with self.subTest(route=route, query=query):
                    self.assert_same(self.client, "GET", f"/v1/taxa/{route}{query}")
        self.assert_replayed()

    def test_lineage_and_observation_queries(self) -> None:
        for query in ("", "?scientific_name=Anas%20zonorhyncha", "?name=%ED%9D%B0%EB%BA%A8%EA%B2%80%EB%91%A5%EC%98%A4%EB%A6%AC",
                      "?scientific_name=a&name=b", "?scientific_name=%20", "?scientific_name=", "?name=down",
                      "?scientific_name=Missing%20bird", "?scientific_name=Anas%20zonorhyncha&species_scope=outside",
                      "?scientific_name=Anas%20zonorhyncha&species_scope=bad"):
            with self.subTest(query=query):
                self.assert_same(self.client, "GET", "/v1/taxa/lineage" + query)
        for query in ("", "?taxon_key=1", "?taxon_key=empty", "?taxon_key=down", "?taxon_key=%20", "?limit=0",
                      "?limit=101&offset=-1", "?limit=abc", "?observed_from=2026-02-01&observed_to=2026-01-01",
                      "?observed_from=not-a-date", "?observed_from=2026-01-01&limit=5&offset=2",
                      "?taxon_key=" + "1" * 51):
            with self.subTest(query=query):
                self.assert_same(self.client, "GET", "/v1/observations" + query)
        self.assert_replayed()

    def test_json_bodies_follow_the_legacy_validation_contract(self) -> None:
        bodies = [
            {"json": {}}, {"json": None}, {"json": []}, {"json": {"question": ""}}, {"json": {"question": "  "}},
            {"json": {"question": "x" * 2001}}, {"json": {"question": "bird", "species_scope": "invalid"}},
            {"json": {"question": "bird", "unexpected": 1}},
            {"json": {"question": "bird", "intent": "profile", "filters": {"kind": "evidence"}}},
            {"json": {"question": "bird", "filters": {"kind": "nope"}}},
            {"json": {"question": "bird", "intent": "taxonomy", "filters": {"kind": "taxonomy", "name": "a",
                                                                               "scientific_name": "b"}}},
            {"json": {"question": "bird", "intent": "observations",
                      "filters": {"kind": "observations", "observed_from": "2026-02-01", "observed_to": "2026-01-01"}}},
            {"content": b"{bad", "headers": {"content-type": "application/json"}},
            {"content": b'{"question": "bird"}'},
            {"content": b'{"question": "bird"}', "headers": {"content-type": "text/plain"}},
            {"content": b'{"question": "bird"}', "headers": {"content-type": "application/vnd.api+json"}},
            {"content": b"\xff\xfe\xfa", "headers": {"content-type": "application/json"}},
        ]
        for path in ("/v1/chat", "/v1/answers", "/v1/search"):
            for body in bodies:
                with self.subTest(path=path, body=body):
                    self.assert_same(self.client, "POST", path, **body)
        self.assert_replayed()

    def test_chat_routes_and_fail_closed_answers(self) -> None:
        questions = [
            {"question": "흰뺨검둥오리에 대해 알려줘"},
            {"question": "흰뺨검둥오리에 대해 알려줘", "species_scope": "korea"},
            {"question": "흰뺨검둥오리에 대해 알려줘", "defer_enrichment": True, "defer_discovery": True},
            {"question": "흰뺨검둥오리의 분류 알려줘"},
            {"question": "흰뺨검둥오리는 무슨 과야?"},
            {"question": "없는새에 대해 알려줘"},
            {"question": "아무 질문"},
            {"question": "흰뺨검둥오리", "intent": "profile"},
            {"question": "x", "intent": "profile", "filters": {"kind": "profile", "name": "boom"}},
            {"question": "x", "intent": "taxonomy", "filters": {"kind": "taxonomy", "scientific_name": "Anas zonorhyncha"}},
            {"question": "x", "intent": "taxonomy", "filters": {"kind": "taxonomy", "name": "down"}},
            {"question": "x", "intent": "observations"},
            {"question": "x", "intent": "observations", "filters": {"kind": "observations", "taxon_key": "1"}},
            {"question": "x", "intent": "observations", "filters": {"kind": "observations", "taxon_key": "down"}},
            {"question": "서식지 근거", "intent": "evidence"},
            {"question": "down", "intent": "evidence", "filters": {"kind": "evidence", "limit": 3}},
        ]
        for payload in questions:
            with self.subTest(payload=payload):
                self.assert_same(self.client, "POST", "/v1/chat", json=payload)
        for payload in ({"question": "fixture 호수에 물새가 있나?"}, {"question": "말똥가리의 정확한 관찰 좌표를 알려줘."}):
            self.assert_same(self.client, "POST", "/v1/answers", json=payload)
        for payload in ({"question": "서식지"}, {"question": "서식지", "mode": "hybrid", "limit": 3},
                        {"question": "down"}, {"question": "q", "mode": "vector"}, {"question": "q", "limit": 0}):
            self.assert_same(self.client, "POST", "/v1/search", json=payload)
        self.assert_replayed()

    def test_unconfigured_handlers_answer_503_or_abstain(self) -> None:
        client = self.build()
        for path in ("/v1/taxa/profile?name=a", "/v1/taxa/related?name=a", "/v1/taxa/lineage?name=a",
                     "/v1/taxa/lineage?scientific_name=a", "/v1/observations?taxon_key=1",
                     "/v1/taxa/name-relations?name=a", "/v1/taxa/subspecies?name=a"):
            self.assert_same(client, "GET", path)
        self.assert_same(client, "POST", "/v1/search", json={"question": "q"})
        for intent in ("auto", "profile", "taxonomy", "observations", "evidence"):
            self.assert_same(client, "POST", "/v1/chat", json={"question": "흰뺨검둥오리에 대해 알려줘", "intent": intent})
        self.assert_replayed()

    def test_method_routing_redirects_negotiation_and_unknown_paths(self) -> None:
        for method, path in (("HEAD", "/health"), ("OPTIONS", "/v1/chat"), ("PUT", "/v1/taxa/profile"),
                             ("POST", "/health"), ("GET", "/v1/chat"), ("DELETE", "/static/chat.js"),
                             ("GET", "/health/"), ("GET", "/health/?x=1"), ("POST", "/v1/chat/"),
                             ("GET", "/static"), ("GET", "/nope"), ("GET", "/v1/taxa"), ("GET", "/internal/v1/ingest/begin"),
                             ("HEAD", "/openapi.json"), ("POST", "/openapi.json"), ("GET", "/docs/")):
            with self.subTest(method=method, path=path):
                self.assert_same(self.client, method, path)
        # The client's Accept header never changes the JSON contract.
        self.assert_same(self.client, "GET", "/health", headers={"accept": "text/html"})
        self.assert_same(self.client, "GET", "/v1/taxa/profile", headers={"accept": "application/xml"})
        self.assert_replayed()

    def test_documentation_routes_serve_the_frozen_baseline(self) -> None:
        for path in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
            self.assert_same(self.client, "GET", path)
        self.assertEqual(frozen_openapi(ingest=False), self.client.app.openapi())
        self.assert_replayed()


class StaticAssetParityTest(ParityCase):
    def setUp(self) -> None:
        super().setUp()
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name, content in (("index.html", '<link href="/static/styles.css"><script src="/static/chat.js">'),
                              ("chat.js", "console.log('chat');"), ("styles.css", "body{}"),
                              ("birds.html", '<script src="/static/birds.js">'), ("birds.js", "1;"),
                              ("favicon.ico", "ico"), ("favicon-32-test.png", "test-png")):
            (self.root / name).write_text(content, encoding="utf-8")

    def _paths(self):
        return ("/", "/chat", "/birds", "/favicon.ico", "/static/chat.js", "/static/styles.css", "/static/index.html",
                "/static/birds.js", "/static/birds.html", "/static/favicon-32.png", "/static/favicon-192.png",
                "/static/missing.js", "/static/", "/static/%2e%2e/app.py", "/static/..%2fapp.py",
                "/static/%2fetc%2fpasswd")

    def test_complete_partial_and_test_variant_bundles(self) -> None:
        client = self.build(static_dir=self.root)
        for path in self._paths():
            self.assert_same(client, "GET", path)
        with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": "test"}):
            for path in ("/static/favicon-32.png", "/favicon.ico", "/health"):
                self.assert_same(client, "GET", path)
        (self.root / "styles.css").write_text("", encoding="utf-8")
        for path in self._paths():
            self.assert_same(client, "GET", path)
        self.assert_replayed()


class IngestParityTest(ParityCase):
    def setUp(self) -> None:
        super().setUp()
        environment = patch.dict(os.environ, {TOKEN_ENV: "test-internal-token"})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = FakeIngestStore()
        self.client = TestClient(create_django_app(ingest_store=self.store), raise_server_exceptions=False)
        self.auth = {"authorization": "Bearer test-internal-token"}

    def begin_body(self) -> dict:
        return {
            "dataset": {"id": "ds", "source_id": "src", "name": "n", "provider": "p",
                        "landing_uri": "https://example.org/", "release_strategy": "dated_snapshot",
                        "policy_status": "allowed"},
            "release": {"id": "rel", "release_key": "k", "retrieved_at": "2026-09-22T00:00:00Z"},
            "run": {"id": "run", "pipeline_id": "pipe", "started_at": "2026-09-22T00:00:00Z"},
        }

    def test_bearer_routing_validation_and_store_errors(self) -> None:
        record = {"id": "r1", "external_id": "Q1", "record_type": "t", "raw_object_uri": "https://example.org/r",
                  "raw_sha256": "b" * 64, "retrieved_at": "2026-09-22T00:00:00Z", "parser_version": "v1",
                  "license_policy_status": "allowed", "payload": {"a": 1}}
        cases = [
            ("POST", "/internal/v1/ingest/begin", {"json": self.begin_body()}),
            ("POST", "/internal/v1/ingest/begin", {"json": self.begin_body(), "headers": {"authorization": "Bearer wrong"}}),
            ("POST", "/internal/v1/ingest/begin", {"json": self.begin_body(), "headers": {"authorization": "test-internal-token"}}),
            ("POST", "/internal/v1/ingest/begin", {"content": b"{bad", "headers": {"content-type": "application/json"}}),
            ("GET", "/internal/v1/ingest/begin", {}),
            ("GET", "/internal/v1/ingest/run/append", {}),
            ("POST", "/internal/v1/ingest/active/pipe", {}),
            ("GET", "/internal/v1/ingest/run/unknown", {}),
            ("GET", "/internal/v1/ingest/active", {}),
            ("POST", "/internal/v1/ingest/begin", {"json": self.begin_body(), "headers": self.auth}),
            ("POST", "/internal/v1/ingest/begin", {"json": {**self.begin_body(), "extra": 1}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/begin", {"headers": self.auth}),
            ("GET", "/internal/v1/ingest/active/pipe", {"headers": self.auth}),
            ("GET", "/internal/v1/ingest/active/append", {"headers": self.auth}),
            ("GET", "/internal/v1/ingest/active/" + "p" * 201, {"headers": self.auth}),
            ("GET", "/internal/v1/ingest/active/a%20b", {"headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/append", {"json": {"records": [record]}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/active/append", {"json": {"records": [record]}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/append", {"json": {}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/" + "r" * 201 + "/append", {"json": {"records": [{}]}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/finalize", {"json": {"counts": {"a": 1}, "expected_state_version": 2}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/finalize", {"json": {"counts": {"a": -1, "b": True}}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/fail", {"json": {"reason": "network"}, "headers": self.auth}),
            ("POST", "/internal/v1/ingest/run/fail", {"json": {"reason": ""}, "headers": self.auth}),
        ]
        for method, path, kwargs in cases:
            with self.subTest(method=method, path=path, kwargs=kwargs):
                self.assert_same(self.client, method, path, **kwargs)
        self.assertEqual(GOLDEN["IngestParityTest.store_calls"], _plain(self.store.calls))
        for error in (IngestionConflictError("x"), IngestionStateError("y"), ValueError("z")):
            self.store.error = error
            for method, path, kwargs in (("POST", "/internal/v1/ingest/begin", {"json": self.begin_body()}),
                                         ("GET", "/internal/v1/ingest/active/pipe", {}),
                                         ("POST", "/internal/v1/ingest/run/fail", {"json": {"reason": "r"}})):
                with self.subTest(error=error, path=path):
                    self.assert_same(self.client, method, path, headers=self.auth, **kwargs)
        self.assert_replayed()

    def test_large_valid_append_batch_is_accepted(self) -> None:
        # ~3 MB: above Django's default 2.5 MiB body cap, within the DTO bounds
        # (500 records, 1 MB per payload) the legacy API accepted.
        records = [{"id": f"r{index}", "external_id": f"Q{index}", "record_type": "t",
                    "raw_object_uri": "https://example.org/r", "raw_sha256": "b" * 64,
                    "retrieved_at": "2026-09-22T00:00:00Z", "parser_version": "v1",
                    "license_policy_status": "allowed", "payload": {"text": "x" * 60_000}}
                   for index in range(50)]
        body = json.dumps({"records": records}).encode()
        self.assertGreater(len(body), 3_000_000)
        response = self.client.post("/internal/v1/ingest/run/append", content=body,
                                     headers={**self.auth, "content-type": "application/json"})
        self.assertEqual(200, response.status_code, response.text[:200])
        self.assertEqual({"status": "appended", "state_version": None}, response.json())
        self.assertEqual([("context", "run"), "append"], [self.store.calls[0], self.store.calls[1][0]])
        _, run_id, stored, quarantine, events = self.store.calls[1]
        self.assertEqual(("run", 50, (), ()), (run_id, len(stored), quarantine, events))
        self.assertEqual("x" * 60_000, stored[-1].payload["text"])

    def test_openapi_and_missing_token(self) -> None:
        self.assertEqual(frozen_openapi(ingest=True), self.client.app.openapi())
        self.assert_same(self.client, "GET", "/openapi.json")
        with patch.dict(os.environ, {TOKEN_ENV: ""}):
            with self.assertRaisesRegex(ValueError, TOKEN_ENV):
                create_django_app(ingest_store=FakeIngestStore())
        self.assert_same(self.build(), "POST", "/internal/v1/ingest/begin", json=self.begin_body(), headers=self.auth)
        self.assert_replayed()


class NativeRuntimeTest(unittest.TestCase):
    def test_apps_with_different_dependencies_are_isolated(self) -> None:
        first = TestClient(create_django_app(species_profile_handler=lambda name: {"taxon": {"n": 1}}))
        second = TestClient(create_django_app())
        self.assertEqual(200, first.get("/v1/taxa/profile?name=a").status_code)
        self.assertEqual(503, second.get("/v1/taxa/profile?name=a").status_code)
        self.assertEqual(200, first.get("/v1/taxa/profile?name=a").status_code)

    def test_host_header_is_validated_before_routing(self) -> None:
        client = TestClient(create_django_app(), raise_server_exceptions=False)
        allowed = {"/health": 200, "/missing": 404, "/health/": 307}
        for path, status in allowed.items():
            self.assertEqual(status, client.get(path, follow_redirects=False).status_code, path)
        for host in ("evil.example", "evil.example:8000", "bad host!"):
            for path in (*allowed, "/v1/chat", "/static/chat.js", "/internal/v1/ingest/begin"):
                with self.subTest(host=host, path=path):
                    response = client.get(path, headers={"host": host}, follow_redirects=False)
                    self.assertEqual(400, response.status_code)
                    self.assertEqual({"detail": "Bad Request"}, response.json())
                    self.assertEqual("application/json", response.headers["content-type"])
                    self.assertNotIn("evil", response.text)
                    self.assertNotIn("location", response.headers)
            self.assertEqual(400, client.post("/v1/chat", json={"question": "q"}, headers={"host": host}).status_code)

    def test_sync_service_calls_run_concurrently(self) -> None:
        barrier = threading.Barrier(2, timeout=5)

        def profile(name: str) -> dict:
            barrier.wait()  # deadlocks (BrokenBarrierError -> 503) if requests are serialized
            return {"taxon": {"name": name}}

        app = create_django_app(species_profile_handler=profile)

        async def call(name: str) -> int:
            scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                     "scheme": "http", "path": "/v1/taxa/profile", "raw_path": b"/v1/taxa/profile",
                     "query_string": f"name={name}".encode(), "root_path": "", "headers": [(b"host", b"testserver")],
                     "server": ("testserver", 80), "client": ("127.0.0.1", 1)}
            messages = iter([{"type": "http.request", "body": b"", "more_body": False}])
            sent: list[dict] = []

            async def receive():
                try:
                    return next(messages)
                except StopIteration:
                    await asyncio.sleep(3600)

            async def send(message):
                sent.append(message)

            await app(scope, receive, send)
            return sent[0]["status"]

        async def both():
            return await asyncio.gather(call("a"), call("b"))

        self.assertEqual([200, 200], asyncio.run(both()))

    def test_lifespan_is_acknowledged(self) -> None:
        with TestClient(create_django_app()) as client:
            self.assertEqual(200, client.get("/health").status_code)

    def test_native_runtime_does_not_import_fastapi_or_starlette(self) -> None:
        code = ("import sys; from robingraph.api.drf import create_django_app; "
                "from asgi_client import TestClient; "
                "assert TestClient(create_django_app()).get('/health').status_code == 200; "
                "leaked = sorted(m for m in sys.modules if m.split('.')[0] in ('fastapi', 'starlette')); "
                "assert not leaked, leaked")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        self.assertEqual(0, result.returncode, result.stderr)

    def test_frozen_openapi_documents_every_public_route(self) -> None:
        schema = create_django_app().openapi()
        self.assertEqual({"/v1/taxa/name-relations", "/v1/taxa/related", "/v1/taxa/similar",
                          "/v1/taxa/ecological-related", "/v1/taxa/subspecies", "/v1/taxa/profile", "/health",
                          "/v1/answers", "/v1/chat", "/v1/search", "/v1/observations", "/v1/taxa/lineage"},
                         set(schema["paths"]))
        self.assertIn("LineageTaxonResponse", schema["components"]["schemas"])
        self.assertEqual(json.loads(json.dumps(schema)), schema)


def _without_null_defaults(value):
    # The frozen documents were generated before Pydantic began emitting `"default": null`.
    if isinstance(value, dict):
        return {key: _without_null_defaults(item) for key, item in value.items()
                if not (key == "default" and item is None)}
    if isinstance(value, list):
        return [_without_null_defaults(item) for item in value]
    return value


PUBLIC_MODELS = (
    (schemas.ChatRequest, "validation"), (schemas.QuestionRequest, "validation"),
    (schemas.DocumentSearchRequest, "validation"), (schemas.AnswerResponse, "serialization"),
    (schemas.ChatResponse, "serialization"), (schemas.DocumentSearchResponse, "serialization"),
    (schemas.OperationalObservationSearchResponse, "serialization"),
    (schemas.TaxonomyLineageResponse, "serialization"),
)
INGEST_MODELS = (
    (ingest_service.BeginRequest, "validation"), (ingest_service.AppendRequest, "validation"),
    (ingest_service.FinalizeRequest, "validation"), (ingest_service.FailRequest, "validation"),
    (ingest_service.OperationResponse, "serialization"), (ingest_service.ActiveReleaseResponse, "serialization"),
)
# Added by the frozen generator for 422 responses; not backed by a project DTO.
FRAMEWORK_SCHEMAS = {"HTTPValidationError", "ValidationError"}


class OpenApiContractTest(unittest.TestCase):
    """The frozen OpenAPI documents must keep describing the live DTOs."""

    maxDiff = None

    def test_component_schemas_match_the_pydantic_dtos(self) -> None:
        for ingest, models in ((False, PUBLIC_MODELS), (True, PUBLIC_MODELS + INGEST_MODELS)):
            components = frozen_openapi(ingest=ingest)["components"]["schemas"]
            _, generated = models_json_schema(models, ref_template="#/components/schemas/{model}")
            definitions = generated["$defs"]
            with self.subTest(ingest=ingest):
                self.assertEqual(set(components) - FRAMEWORK_SCHEMAS, set(definitions))
                for name, schema in definitions.items():
                    self.assertEqual(_without_null_defaults(components[name]), _without_null_defaults(schema), name)

    def test_species_scope_parameters_match_the_scope_type(self) -> None:
        paths = frozen_openapi(ingest=False)["paths"]
        documented = {route for route, item in paths.items()
                      for parameter in item.get("get", {}).get("parameters", ())
                      if parameter["name"] == "species_scope"}
        self.assertEqual({"/v1/taxa/related", "/v1/taxa/similar", "/v1/taxa/ecological-related",
                          "/v1/taxa/profile", "/v1/taxa/lineage"}, documented)
        for route in documented:
            parameter = next(p for p in paths[route]["get"]["parameters"] if p["name"] == "species_scope")
            self.assertEqual(list(get_args(SpeciesScope)), parameter["schema"]["enum"], route)
            self.assertEqual("all", parameter["schema"]["default"], route)


if __name__ == "__main__":
    unittest.main()
