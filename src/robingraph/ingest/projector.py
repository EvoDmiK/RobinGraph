"""Generic leased-outbox delivery loop for future domain events.

Source/control-plane records are intentionally PostgreSQL-only. This module
does not provide a Neo4j projection for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .store import ClaimedOutboxEvent, IngestionStore


class GraphEventProjector(Protocol):
    def apply(self, event: ClaimedOutboxEvent) -> None: ...


@dataclass(frozen=True)
class ProjectionReport:
    claimed: int
    published: int
    failed: int
    dead_lettered: int
    lost_claims: int


class OutboxProjector:
    def __init__(self, store: IngestionStore, graph: GraphEventProjector):
        self._store = store
        self._graph = graph

    def run_once(
        self,
        worker_id: str,
        *,
        limit: int = 100,
        lease_seconds: int = 300,
        max_attempts: int = 10,
        retry_delay_seconds: int = 30,
    ) -> ProjectionReport:
        events = self._store.claim_outbox(worker_id, limit=limit, lease_seconds=lease_seconds)
        published = failed = dead_lettered = lost_claims = 0
        for event in events:
            try:
                self._graph.apply(event)
            except Exception as error:
                updated = self._store.record_projection_failure(
                    event,
                    f"{type(error).__name__}: {error}",
                    max_attempts=max_attempts,
                    retry_delay_seconds=retry_delay_seconds,
                )
                if updated and event.attempts >= max_attempts:
                    dead_lettered += 1
                elif updated:
                    failed += 1
                else:
                    lost_claims += 1
                continue
            if self._store.mark_published(event):
                published += 1
            else:
                # Neo4j may already contain the idempotent projection. A stale
                # lease holder must never acknowledge a newer worker's claim;
                # the event remains eligible for safe replay.
                lost_claims += 1
        return ProjectionReport(len(events), published, failed, dead_lettered, lost_claims)
