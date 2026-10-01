from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from robingraph.ingest.postgres import PostgresSettings, discover_migrations
from robingraph.ingest.store import (
    OutboxEventInput,
    SourceRecordInput,
    SourceReleaseInput,
    _outbox_event_identity,
    _stored_outbox_event_identity,
    _source_record_identity,
    _source_release_identity,
)


class PostgresSettingsTest(unittest.TestCase):
    def test_reads_isolated_database_and_schema_configuration(self) -> None:
        environment = {
            "ROBINGRAPH_PG_HOST": "postgres.test.internal",
            "ROBINGRAPH_PG_PORT": "5433",
            "ROBINGRAPH_PG_DATABASE": "robingraph_test",
            "ROBINGRAPH_PG_SCHEMA": "ingest",
            "ROBINGRAPH_PG_USERNAME": "robingraph_test_app",
            "ROBINGRAPH_PG_PASSWORD": "test-only",
            "ROBINGRAPH_PG_SSLMODE": "require",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = PostgresSettings.from_environment()

        self.assertEqual("robingraph_test", settings.database)
        self.assertEqual("robingraph_test_app", settings.username)
        self.assertEqual(5433, settings.port)
        self.assertEqual("ingest", settings.schema)
        self.assertNotIn("test-only", repr(settings))

    def test_rejects_missing_credentials_and_unsafe_schema(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "ROBINGRAPH_PG_HOST"):
                PostgresSettings.from_environment()
        with patch.dict(
            os.environ,
            {
                "ROBINGRAPH_PG_HOST": "localhost",
                "ROBINGRAPH_PG_DATABASE": "robingraph_test",
                "ROBINGRAPH_PG_SCHEMA": "ingest;drop schema public",
                "ROBINGRAPH_PG_USERNAME": "app",
                "ROBINGRAPH_PG_PASSWORD": "test-only",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "PostgreSQL identifier"):
                PostgresSettings.from_environment()

    def test_integration_opt_in_rejects_a_production_named_database(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ROBINGRAPH_POSTGRES_INTEGRATION_TESTS": "1",
                "ROBINGRAPH_PG_HOST": "localhost",
                "ROBINGRAPH_PG_DATABASE": "robingraph",
                "ROBINGRAPH_PG_USERNAME": "app",
                "ROBINGRAPH_PG_PASSWORD": "test-only",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "database name containing 'test'"):
                PostgresSettings.from_environment()


class PostgresMigrationTest(unittest.TestCase):
    def test_control_plane_migration_contains_required_tables_and_outbox_index(self) -> None:
        migrations = discover_migrations()
        self.assertEqual(["0001", "0002", "0003", "0004"], [migration.version for migration in migrations])
        sql = migrations[0].sql
        for table in (
            "source_dataset",
            "source_release",
            "ingestion_run",
            "source_record",
            "quarantine_item",
            "ingest_state",
            "outbox_event",
        ):
            self.assertIn(f"CREATE TABLE {table}", sql)
        self.assertIn("WHERE published_at IS NULL", sql)
        self.assertIn("UNIQUE (source_release_id, external_id, record_version)", sql)
        self.assertIn("ingestion_run_id text NOT NULL", migrations[1].sql)
        self.assertIn("claim_token uuid", migrations[2].sql)
        self.assertIn("aggregate_type, aggregate_id, id", migrations[3].sql)

    def test_migration_versions_must_be_unique(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / "0001_second.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "versions must be unique"):
                discover_migrations(root)


class SourceReleaseIdentityTest(unittest.TestCase):
    def test_content_addressed_replay_ignores_later_observation_time_only(self) -> None:
        first = SourceReleaseInput(
            "release-1", "dataset-1", "sha256:abc", datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc),
            content_sha256="a" * 64, raw_object_uri="https://example.invalid/snapshot", metadata={"kind": "sparql"},
        )
        later_observation = SourceReleaseInput(
            "release-1", "dataset-1", "sha256:abc", datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc),
            content_sha256="a" * 64, raw_object_uri="https://example.invalid/snapshot", metadata={"kind": "sparql"},
        )
        altered_snapshot = SourceReleaseInput(
            "release-1", "dataset-1", "sha256:abc", datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc),
            content_sha256="b" * 64, raw_object_uri="https://example.invalid/snapshot", metadata={"kind": "sparql"},
        )

        self.assertEqual(_source_release_identity(first), _source_release_identity(later_observation))
        self.assertNotEqual(_source_release_identity(first), _source_release_identity(altered_snapshot))

    def test_content_addressed_record_and_event_replay_keep_first_observation_provenance(self) -> None:
        first = SourceRecordInput(
            "record-1", "release-1", "Q1", "taxon_label", "https://example.invalid/Q1", "a" * 64,
            datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc), "parser-v1", "run-1", "allowed", {"qid": "Q1"},
        )
        replay = SourceRecordInput(
            "record-1", "release-1", "Q1", "taxon_label", "https://example.invalid/Q1", "a" * 64,
            datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc), "parser-v1", "run-2", "allowed", {"qid": "Q1"},
        )
        changed = SourceRecordInput(
            "record-1", "release-1", "Q1", "taxon_label", "https://example.invalid/Q1", "b" * 64,
            datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc), "parser-v1", "run-2", "allowed", {"qid": "Q1"},
        )
        self.assertEqual(_source_record_identity(first), _source_record_identity(replay))
        self.assertNotEqual(_source_record_identity(first), _source_record_identity(changed))

        event = OutboxEventInput(
            "event-1", "source_record", "record-1", "source_record.upserted",
            {"record": {"id": "record-1", "raw_hash": "a" * 64, "retrieved_at": "2026-09-22T00:00:00+00:00"}}, "run-1",
        )
        replay_event = OutboxEventInput(
            "event-1", "source_record", "record-1", "source_record.upserted",
            {"record": {"id": "record-1", "raw_hash": "a" * 64, "retrieved_at": "2026-09-23T00:00:00+00:00"}}, "run-2",
        )
        changed_event = OutboxEventInput(
            "event-1", "source_record", "record-1", "source_record.upserted",
            {"record": {"id": "record-1", "raw_hash": "b" * 64, "retrieved_at": "2026-09-23T00:00:00+00:00"}}, "run-2",
        )
        self.assertEqual(_outbox_event_identity(event), _outbox_event_identity(replay_event))
        self.assertNotEqual(_outbox_event_identity(event), _outbox_event_identity(changed_event))
        stored = (
            event.aggregate_type,
            event.aggregate_id,
            event.event_type,
            dict(event.payload),
        )
        self.assertEqual(_stored_outbox_event_identity(stored), _outbox_event_identity(replay_event))
        self.assertNotEqual(_stored_outbox_event_identity(stored), _outbox_event_identity(changed_event))


if __name__ == "__main__":
    unittest.main()
