from __future__ import annotations

from uuid import UUID
import unittest

from robingraph.ingest.projector import OutboxProjector
from robingraph.ingest.store import ClaimedOutboxEvent


def event(number: int = 1) -> ClaimedOutboxEvent:
    return ClaimedOutboxEvent(
        id=number,
        event_key=f"event-{number}",
        aggregate_type="source_record",
        aggregate_id=f"record-{number}",
        event_type="source_record.upserted",
        payload={"record": {"id": f"record-{number}"}},
        ingestion_run_id="run-1",
        attempts=1,
        claim_token=UUID(int=number),
    )


class FakeStore:
    def __init__(self, events=(), *, publish=True, fail=True):
        self.events = tuple(events)
        self.publish_result = publish
        self.failure_result = fail
        self.published = []
        self.failures = []

    def claim_outbox(self, worker_id, *, limit, lease_seconds):
        self.claim = (worker_id, limit, lease_seconds)
        return self.events

    def mark_published(self, value):
        self.published.append(value)
        return self.publish_result

    def record_projection_failure(self, value, error, *, max_attempts, retry_delay_seconds):
        self.failures.append((value, error, max_attempts, retry_delay_seconds))
        return self.failure_result


class FakeGraph:
    def __init__(self, failure=None):
        self.failure = failure
        self.applied = []

    def apply(self, value):
        self.applied.append(value)
        if self.failure:
            raise self.failure


class OutboxProjectorTest(unittest.TestCase):
    def test_successful_projection_is_acknowledged(self) -> None:
        value = event()
        store = FakeStore((value,))
        graph = FakeGraph()
        report = OutboxProjector(store, graph).run_once("worker-1", limit=5, lease_seconds=10)

        self.assertEqual(
            (1, 1, 0, 0, 0),
            (report.claimed, report.published, report.failed, report.dead_lettered, report.lost_claims),
        )
        self.assertEqual([value], graph.applied)
        self.assertEqual([value], store.published)
        self.assertEqual(("worker-1", 5, 10), store.claim)

    def test_projection_failure_is_retried_without_acknowledging(self) -> None:
        value = event()
        store = FakeStore((value,))
        graph = FakeGraph(RuntimeError("neo4j unavailable"))
        report = OutboxProjector(store, graph).run_once(
            "worker-1", max_attempts=3, retry_delay_seconds=7
        )

        self.assertEqual(
            (1, 0, 1, 0, 0),
            (report.claimed, report.published, report.failed, report.dead_lettered, report.lost_claims),
        )
        self.assertEqual([], store.published)
        self.assertIn("RuntimeError: neo4j unavailable", store.failures[0][1])
        self.assertEqual((3, 7), store.failures[0][2:])

    def test_stale_claim_cannot_acknowledge_a_newer_lease(self) -> None:
        store = FakeStore((event(),), publish=False)
        report = OutboxProjector(store, FakeGraph()).run_once("stale-worker")
        self.assertEqual(1, report.lost_claims)
        self.assertEqual(0, report.published)

    def test_retry_exhaustion_is_reported_as_dead_lettered(self) -> None:
        value = ClaimedOutboxEvent(**{**event().__dict__, "attempts": 3})
        store = FakeStore((value,))
        report = OutboxProjector(store, FakeGraph(RuntimeError("still unavailable"))).run_once(
            "worker-1", max_attempts=3
        )
        self.assertEqual(1, report.dead_lettered)
        self.assertEqual(0, report.failed)


if __name__ == "__main__":
    unittest.main()
