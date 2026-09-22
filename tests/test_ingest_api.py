from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.fixture import load_fixture
from robingraph.ingest.store import (
    IngestionConflictError,
    IngestionRunContext,
    IngestionStateError,
    SourceDatasetInput,
    SourceReleaseInput,
)
from robingraph.retrieval.fixture_repository import FixtureRepository


TOKEN_ENV = "ROBINGRAPH_INGEST_INTERNAL_TOKEN"


class FakeIngestStore:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.context = IngestionRunContext(
            dataset=SourceDatasetInput(
                "wikidata-dataset", "wikidata", "Wikidata Korean labels", "Wikidata",
                "https://www.wikidata.org/", "dated_snapshot", "allowed", {"license": "CC0"},
            ),
            release=SourceReleaseInput(
                "wikidata-release", "wikidata-dataset", "snapshot-a",
                datetime(2026, 9, 22, tzinfo=timezone.utc), content_sha256="a" * 64,
            ),
        )
        self.error: Exception | None = None
        self.state_version = 2

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    def begin_run(self, dataset, release, run) -> None:
        self._raise()
        self.calls.append(("begin", dataset, release, run))

    def pipeline_state_version(self, pipeline_id: str) -> int:
        self._raise()
        self.calls.append(("state_version", pipeline_id))
        return self.state_version

    def run_context(self, run_id: str) -> IngestionRunContext:
        self._raise()
        self.calls.append(("context", run_id))
        return self.context

    def append_batch(self, run_id, *, records, quarantine_items, events) -> None:
        self._raise()
        self.calls.append(("append", run_id, records, quarantine_items, events))

    def activate_release(self, run_id, *, counts, cursor_value, expected_state_version) -> int:
        self._raise()
        self.calls.append(("finalize", run_id, counts, cursor_value, expected_state_version))
        return 3

    def fail_run(self, run_id, reason: str) -> None:
        self._raise()
        self.calls.append(("fail", run_id, reason))


class IngestApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeIngestStore()
        self.environment = patch.dict(os.environ, {TOKEN_ENV: "test-internal-token"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(create_app(FixtureRepository(load_fixture()), ingest_store=self.store))
        self.headers = {"Authorization": "Bearer test-internal-token"}

    def _begin_body(self) -> dict[str, object]:
        return {
            "dataset": {
                "id": "wikidata-dataset",
                "source_id": "wikidata",
                "name": "Wikidata Korean labels",
                "provider": "Wikidata",
                "landing_uri": "https://www.wikidata.org/",
                "release_strategy": "dated_snapshot",
                "policy_status": "allowed",
                "metadata": {"license": "CC0"},
            },
            "release": {
                "id": "wikidata-release",
                "release_key": "snapshot-a",
                "retrieved_at": "2026-09-22T00:00:00Z",
                "content_sha256": "a" * 64,
            },
            "run": {
                "id": "wikidata-run-a",
                "pipeline_id": "korean-vernacular-shadow",
                "started_at": "2026-09-22T00:00:00Z",
                "manifest": {"workflow": "korean-vernacular"},
            },
        }

    def _record(self) -> dict[str, object]:
        return {
            "id": "wikidata-record-q25348",
            "external_id": "Q25348",
            "record_type": "korean_vernacular_name",
            "raw_object_uri": "https://query.wikidata.org/sparql",
            "raw_sha256": "b" * 64,
            "retrieved_at": "2026-09-22T00:00:00Z",
            "parser_version": "korean-vernacular-v1",
            "license_policy_status": "allowed",
            "payload": {"scientific_name": "Anas platyrhynchos", "korean_name": "청둥오리"},
        }

    def test_begin_requires_the_environment_bearer_token(self) -> None:
        response = self.client.post("/internal/v1/ingest/begin", json=self._begin_body())
        self.assertEqual(401, response.status_code)
        self.assertEqual("Bearer", response.headers["www-authenticate"])
        self.assertEqual([], self.store.calls)

        response = self.client.post(
            "/internal/v1/ingest/begin", json=self._begin_body(), headers=self.headers
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "started", "state_version": 2}, response.json())
        _, dataset, release, run = self.store.calls[0]
        self.assertEqual(dataset.id, release.dataset_id)
        self.assertEqual(release.id, run.source_release_id)
        self.assertEqual(("state_version", "korean-vernacular-shadow"), self.store.calls[1])

    def test_append_keeps_source_records_in_postgres_without_projection_events(self) -> None:
        response = self.client.post(
            "/internal/v1/ingest/wikidata-run-a/append",
            json={
                "records": [self._record()],
                "quarantine_items": [
                    {
                        "record_key": "Q99999",
                        "stage": "resolve",
                        "reason_code": "no_matching_taxon",
                        "severity": "warning",
                        "rule_version": "korean-vernacular-v1",
                    }
                ],
            },
            headers=self.headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("appended", response.json()["status"])
        _, run_id, records, quarantine, events = self.store.calls[-1]
        self.assertEqual("wikidata-run-a", run_id)
        self.assertEqual("wikidata-release", records[0].source_release_id)
        self.assertEqual("wikidata-run-a", records[0].ingestion_run_id)
        self.assertEqual("wikidata-run-a", quarantine[0].ingestion_run_id)
        self.assertEqual((), events)

    def test_domain_graph_fields_and_invalid_payloads_are_rejected_before_store_calls(self) -> None:
        body = self._begin_body()
        body["dataset"]["taxon_id"] = "must-not-enter-rdb"  # type: ignore[index]
        response = self.client.post("/internal/v1/ingest/begin", json=body, headers=self.headers)
        self.assertEqual(422, response.status_code)
        self.assertEqual([], self.store.calls)

        invalid_record = self._record()
        invalid_record["raw_sha256"] = "not-a-hash"
        response = self.client.post(
            "/internal/v1/ingest/wikidata-run-a/append",
            json={"records": [invalid_record]},
            headers=self.headers,
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual([], self.store.calls)

    def test_finalize_and_fail_are_idempotent_repository_actions_and_hide_state_details(self) -> None:
        response = self.client.post(
            "/internal/v1/ingest/wikidata-run-a/finalize",
            json={"counts": {"source_records": 1}, "cursor": {"offset": 1}},
            headers=self.headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "finalized", "state_version": 3}, response.json())

        response = self.client.post(
            "/internal/v1/ingest/wikidata-run-a/fail",
            json={"reason": "upstream response was incomplete"},
            headers=self.headers,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("failed", response.json()["status"])

        self.store.error = IngestionStateError("database detail that must not be returned")
        response = self.client.post(
            "/internal/v1/ingest/wikidata-run-a/finalize", json={}, headers=self.headers
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("Invalid ingestion state", response.json()["detail"])

    def test_router_is_not_enabled_without_explicit_store_or_token(self) -> None:
        public_client = TestClient(create_app(FixtureRepository(load_fixture())))
        self.assertEqual(404, public_client.post("/internal/v1/ingest/begin").status_code)

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, TOKEN_ENV):
                create_app(FixtureRepository(load_fixture()), ingest_store=FakeIngestStore())

    def test_conflicts_are_safe_and_deterministic(self) -> None:
        self.store.error = IngestionConflictError("immutable content mismatch")
        response = self.client.post(
            "/internal/v1/ingest/begin", json=self._begin_body(), headers=self.headers
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("Ingestion conflict", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
