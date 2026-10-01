"""Opt-in integration tests for the dedicated RobinGraph test database."""

from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
import unittest
from uuid import uuid4

import psycopg

from robingraph.ingest.postgres import PostgresSettings, apply_migrations
from robingraph.ingest.store import (
    IngestionConflictError,
    IngestionRunInput,
    IngestionStateError,
    IngestionStore,
    OutboxEventInput,
    QuarantineItemInput,
    SourceDatasetInput,
    SourceRecordInput,
    SourceReleaseInput,
)


def _integration_opt_in() -> bool:
    return os.getenv("ROBINGRAPH_POSTGRES_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(
    _integration_opt_in(),
    "Set ROBINGRAPH_POSTGRES_INTEGRATION_TESTS=1 with the dedicated test DB environment to run.",
)
class PostgresIngestionStoreIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = PostgresSettings.from_environment()
        apply_migrations(cls.settings)

    def setUp(self) -> None:
        self.prefix = f"integration-{uuid4()}"
        self.dataset_id = f"{self.prefix}-dataset"
        self.release_id = f"{self.prefix}-release"
        self.run_id = f"{self.prefix}-run"
        self.record_id = f"{self.prefix}-record"
        self.event_key = f"{self.prefix}-event"
        self.store = IngestionStore(self.settings)
        self.retrieved_at = datetime.now(timezone.utc)
        self.dataset = SourceDatasetInput(
            self.dataset_id,
            self.prefix,
            "Integration dataset",
            "RobinGraph",
            "https://example.invalid/dataset",
            "versioned",
            "allowed",
            {},
        )
        self.release = SourceReleaseInput(self.release_id, self.dataset_id, "v1", self.retrieved_at)
        self.run = IngestionRunInput(self.run_id, self.prefix, self.release_id, self.retrieved_at)
        self.store.begin_run(
            self.dataset,
            self.release,
            self.run,
        )
        self.addCleanup(self._cleanup)

    def _connection(self):
        connection = psycopg.connect(**self.settings.connection_kwargs())
        connection.execute(f'SET search_path TO "{self.settings.schema}", pg_catalog')
        return connection

    def _cleanup(self) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                pattern = f"{self.prefix}%"
                cursor.execute("DELETE FROM outbox_event WHERE ingestion_run_id LIKE %s", (pattern,))
                cursor.execute("DELETE FROM quarantine_item WHERE ingestion_run_id LIKE %s", (pattern,))
                cursor.execute("DELETE FROM ingest_state WHERE pipeline_id = %s", (self.prefix,))
                cursor.execute("DELETE FROM source_record WHERE ingestion_run_id LIKE %s", (pattern,))
                cursor.execute("DELETE FROM ingestion_run WHERE id LIKE %s", (pattern,))
                cursor.execute("DELETE FROM source_release WHERE dataset_id = %s", (self.dataset_id,))
                cursor.execute("DELETE FROM source_dataset WHERE id = %s", (self.dataset_id,))

    def _record(
        self,
        *,
        raw_hash: str = "a" * 64,
        run_id: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> SourceRecordInput:
        return SourceRecordInput(
            self.record_id,
            self.release_id,
            "external-1",
            "observation",
            "https://example.invalid/record/1",
            raw_hash,
            retrieved_at or self.retrieved_at,
            "integration-v1",
            run_id or self.run_id,
            "allowed",
            {"value": 1},
        )

    def _event(self, *, run_id: str | None = None, retrieved_at: datetime | None = None) -> OutboxEventInput:
        return OutboxEventInput(
            self.event_key,
            "source_record",
            self.record_id,
            "source_record.upserted",
            {
                "record": {
                    "id": self.record_id,
                    "raw_hash": "a" * 64,
                    "retrieved_at": (retrieved_at or self.retrieved_at).isoformat(),
                }
            },
            run_id or self.run_id,
        )

    def test_batch_is_idempotent_and_conflicting_replay_rolls_back(self) -> None:
        record = self._record()
        event = self._event()
        self.store.append_batch(self.run_id, records=(record,), events=(event,))
        self.store.append_batch(self.run_id, records=(record,), events=(event,))

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM source_record WHERE id = %s", (self.record_id,))
                self.assertEqual(1, cursor.fetchone()[0])
                cursor.execute("SELECT count(*) FROM outbox_event WHERE event_key = %s", (self.event_key,))
                self.assertEqual(1, cursor.fetchone()[0])

        with self.assertRaises(IngestionConflictError):
            self.store.append_batch(
                self.run_id,
                records=(self._record(raw_hash="b" * 64),),
                events=(
                    OutboxEventInput(
                        f"{self.event_key}-must-rollback",
                        "source_record",
                        self.record_id,
                        "source_record.upserted",
                        {"record": {"id": self.record_id}},
                        self.run_id,
                    ),
                ),
            )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM outbox_event WHERE event_key = %s",
                    (f"{self.event_key}-must-rollback",),
                )
                self.assertEqual(0, cursor.fetchone()[0])

    def test_content_addressed_release_replay_keeps_first_retrieved_at(self) -> None:
        later = self.retrieved_at + timedelta(minutes=5)
        # The source observation may be later while this replay run starts now;
        # keep lifecycle time ordered so finalize's DB constraint is exercised.
        replay_run = replace(self.run, id=f"{self.prefix}-run-replay", started_at=self.retrieved_at)
        self.store.begin_run(self.dataset, replace(self.release, retrieved_at=later), replay_run)

        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT retrieved_at FROM source_release WHERE id = %s", (self.release_id,))
                self.assertEqual(self.retrieved_at, cursor.fetchone()[0])

        conflicting_run = replace(self.run, id=f"{self.prefix}-run-conflict", started_at=later)
        with self.assertRaises(IngestionConflictError):
            self.store.begin_run(
                self.dataset,
                replace(self.release, retrieved_at=later, raw_object_uri="https://example.invalid/other"),
                conflicting_run,
            )

    def test_content_addressed_record_and_outbox_replay_keep_first_provenance(self) -> None:
        first_record = self._record()
        first_event = self._event()
        self.store.append_batch(self.run_id, records=(first_record,), events=(first_event,))

        later = self.retrieved_at + timedelta(minutes=5)
        replay_run = replace(self.run, id=f"{self.prefix}-run-replay")
        self.store.begin_run(self.dataset, replace(self.release, retrieved_at=later), replay_run)
        replay_record = self._record(run_id=replay_run.id, retrieved_at=later)
        replay_event = self._event(run_id=replay_run.id, retrieved_at=later)
        quarantine = QuarantineItemInput(
            "Q1", replay_run.id, "resolve", "no_matching_taxon", "warning", "integration-v1"
        )
        self.store.append_batch(
            replay_run.id,
            records=(replay_record,),
            quarantine_items=(quarantine,),
            events=(replay_event,),
        )

        with self.assertRaises(IngestionConflictError):
            self.store.append_batch(
                replay_run.id,
                records=(replace(replay_record, raw_sha256="b" * 64),),
            )
        with self.assertRaises(IngestionConflictError):
            self.store.append_batch(
                replay_run.id,
                events=(replace(replay_event, payload={"record": {"id": self.record_id, "raw_hash": "b" * 64, "retrieved_at": later.isoformat()}}),),
            )

        self.assertEqual(
            1,
            self.store.activate_release(
                replay_run.id, counts={"source_records": 1}, expected_state_version=0
            ),
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT retrieved_at, ingestion_run_id FROM source_record WHERE id = %s", (self.record_id,)
                )
                self.assertEqual((self.retrieved_at, self.run_id), cursor.fetchone())
                cursor.execute("SELECT ingestion_run_id FROM outbox_event WHERE event_key = %s", (self.event_key,))
                self.assertEqual(self.run_id, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT last_seen_run_id FROM quarantine_item WHERE record_key = 'Q1' AND stage = 'resolve'"
                )
                self.assertEqual(replay_run.id, cursor.fetchone()[0])

    def test_claim_token_prevents_stale_ack_and_success_is_terminal(self) -> None:
        self.store.append_batch(self.run_id, records=(self._record(),), events=(self._event(),))
        claimed = self.store.claim_outbox("worker-1", limit=1, lease_seconds=60)
        self.assertEqual(1, len(claimed))
        self.assertEqual((), self.store.claim_outbox("worker-2", limit=1, lease_seconds=60))

        stale = replace(claimed[0], claim_token=uuid4())
        self.assertFalse(self.store.mark_published(stale))
        self.assertTrue(self.store.mark_published(claimed[0]))
        self.assertEqual((), self.store.claim_outbox("worker-2", limit=1, lease_seconds=60))

    def test_expired_lease_is_reclaimed_with_a_new_fencing_token(self) -> None:
        self.store.append_batch(self.run_id, records=(self._record(),), events=(self._event(),))
        first = self.store.claim_outbox("worker-1", limit=1, lease_seconds=60)[0]
        with self._connection() as connection:
            connection.execute(
                "UPDATE outbox_event SET claimed_at = now() - interval '10 minutes' WHERE id = %s",
                (first.id,),
            )
        second = self.store.claim_outbox("worker-2", limit=1, lease_seconds=60)[0]
        self.assertNotEqual(first.claim_token, second.claim_token)
        self.assertEqual(first.attempts + 1, second.attempts)
        self.assertFalse(self.store.mark_published(first))
        self.assertTrue(self.store.mark_published(second))

    def test_events_for_one_aggregate_are_claimed_in_order(self) -> None:
        first = self._event()
        second = OutboxEventInput(
            f"{self.event_key}-second",
            first.aggregate_type,
            first.aggregate_id,
            "source_record.upserted",
            {"record": {"id": self.record_id, "revision": 2}},
            self.run_id,
        )
        self.store.append_batch(self.run_id, records=(self._record(),), events=(first, second))

        claimed_first = self.store.claim_outbox("worker-1", limit=10, lease_seconds=60)
        self.assertEqual([first.event_key], [value.event_key for value in claimed_first])
        self.assertTrue(self.store.mark_published(claimed_first[0]))
        claimed_second = self.store.claim_outbox("worker-2", limit=10, lease_seconds=60)
        self.assertEqual([second.event_key], [value.event_key for value in claimed_second])

    def test_retry_exhaustion_dead_letters_and_quarantines_the_event(self) -> None:
        first = self._event()
        blocked_later = OutboxEventInput(
            f"{self.event_key}-blocked-later",
            first.aggregate_type,
            first.aggregate_id,
            "source_record.upserted",
            {"record": {"id": self.record_id, "revision": 2}},
            self.run_id,
        )
        self.store.append_batch(
            self.run_id,
            records=(self._record(),),
            events=(first, blocked_later),
        )
        claimed = self.store.claim_outbox("worker-1", limit=1, lease_seconds=60)[0]
        self.assertTrue(
            self.store.record_projection_failure(
                claimed,
                "Neo4j unavailable",
                max_attempts=1,
                retry_delay_seconds=0,
            )
        )
        self.assertEqual((), self.store.claim_outbox("worker-2", limit=1, lease_seconds=60))
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT dead_lettered_at IS NOT NULL FROM outbox_event WHERE event_key = %s",
                    (self.event_key,),
                )
                self.assertTrue(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT severity, resolution_status FROM quarantine_item
                    WHERE record_key = %s AND stage = 'project'
                    """,
                    (f"source_record:{self.record_id}",),
                )
                self.assertEqual(("blocked", "open"), cursor.fetchone())

    def test_activation_is_optimistic_and_idempotent(self) -> None:
        self.assertIsNone(self.store.active_dataset_id(self.prefix))
        version = self.store.activate_release(
            self.run_id,
            counts={"source_records": 0},
            cursor_value={"page": 1},
            expected_state_version=0,
        )
        self.assertEqual(1, version)
        self.assertEqual(self.dataset_id, self.store.active_dataset_id(self.prefix))
        active = self.store.active_release_context(self.prefix)
        self.assertIsNotNone(active)
        self.assertEqual(self.dataset_id, active.dataset.id)
        self.assertEqual(self.release_id, active.release.id)
        self.assertEqual(self.run_id, active.last_successful_run_id)
        self.assertEqual(1, active.version)
        self.assertEqual(
            1,
            self.store.activate_release(
                self.run_id,
                counts={"source_records": 0},
                cursor_value={"page": 1},
                expected_state_version=0,
            ),
        )
        with self._connection() as connection:
            connection.execute(
                "UPDATE source_dataset SET policy_status = 'denied' WHERE id = %s",
                (self.dataset_id,),
            )
        self.assertIsNone(self.store.active_dataset_id(self.prefix))

    def test_two_concurrent_first_activations_cannot_both_win(self) -> None:
        now = datetime.now(timezone.utc)
        second_release = SourceReleaseInput(
            f"{self.prefix}-release-2", self.dataset_id, "v2", now
        )
        second_run = IngestionRunInput(
            f"{self.prefix}-run-2", self.prefix, second_release.id, now
        )
        dataset = SourceDatasetInput(
            self.dataset_id,
            self.prefix,
            "Integration dataset",
            "RobinGraph",
            "https://example.invalid/dataset",
            "versioned",
            "allowed",
            {},
        )
        self.store.begin_run(dataset, second_release, second_run)
        barrier = Barrier(2)

        def activate(run_id: str):
            barrier.wait()
            try:
                return self.store.activate_release(
                    run_id,
                    counts={"source_records": 0},
                    expected_state_version=0,
                )
            except IngestionStateError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(activate, (self.run_id, second_run.id)))

        self.assertEqual(1, sum(result == 1 for result in results))
        self.assertEqual(1, sum(isinstance(result, IngestionStateError) for result in results))
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT version, last_successful_run_id FROM ingest_state WHERE pipeline_id = %s",
                    (self.prefix,),
                )
                version, winning_run = cursor.fetchone()
                self.assertEqual(1, version)
                self.assertIn(winning_run, {self.run_id, second_run.id})


if __name__ == "__main__":
    unittest.main()
