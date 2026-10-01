"""Transactional PostgreSQL system of record for ingestion control data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .postgres import PostgresSettings


@dataclass(frozen=True)
class SourceDatasetInput:
    id: str
    source_id: str
    name: str
    provider: str
    landing_uri: str
    release_strategy: str
    policy_status: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class SourceReleaseInput:
    id: str
    dataset_id: str
    release_key: str
    retrieved_at: datetime
    content_sha256: str | None = None
    raw_object_uri: str | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class IngestionRunInput:
    id: str
    pipeline_id: str
    source_release_id: str
    started_at: datetime
    pipeline_git_sha: str | None = None
    config_sha256: str | None = None
    manifest: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class SourceRecordInput:
    id: str
    source_release_id: str
    external_id: str
    record_type: str
    raw_object_uri: str
    raw_sha256: str
    retrieved_at: datetime
    parser_version: str
    ingestion_run_id: str
    license_policy_status: str
    payload: Mapping[str, Any]
    record_version: str = "1"
    supersedes_record_id: str | None = None
    source_updated_at: datetime | None = None


@dataclass(frozen=True)
class QuarantineItemInput:
    record_key: str
    ingestion_run_id: str
    stage: str
    reason_code: str
    severity: str
    rule_version: str
    field_path: str | None = None
    raw_value_redacted: Any = None


@dataclass(frozen=True)
class OutboxEventInput:
    event_key: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: Mapping[str, Any]
    ingestion_run_id: str


@dataclass(frozen=True)
class ClaimedOutboxEvent:
    id: int
    event_key: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: Mapping[str, Any]
    ingestion_run_id: str
    attempts: int
    claim_token: UUID


@dataclass(frozen=True)
class IngestionRunContext:
    """Canonical dataset/release data associated with one immutable run."""

    dataset: SourceDatasetInput
    release: SourceReleaseInput


@dataclass(frozen=True)
class ActiveReleaseContext:
    """Active allowed release and its optimistic activation version."""

    pipeline_id: str
    dataset: SourceDatasetInput
    release: SourceReleaseInput
    last_successful_run_id: str
    cursor: Mapping[str, Any]
    version: int


class IngestionConflictError(ValueError):
    """An idempotency key was reused with different immutable content."""


class IngestionStateError(ValueError):
    """An invalid ingestion-run or activation transition was requested."""


def _source_release_identity(release: SourceReleaseInput) -> tuple[object, ...]:
    """The immutable identity of a content-addressed source release.

    ``retrieved_at`` is deliberately excluded: it records when this runner
    observed an already-identical immutable snapshot.  The first insert keeps
    that provenance timestamp instead of letting later retries rewrite it.
    """

    return (
        release.dataset_id,
        release.release_key,
        release.content_sha256,
        release.raw_object_uri,
        dict(release.metadata or {}),
    )


def _source_record_identity(record: SourceRecordInput) -> tuple[object, ...]:
    """Immutable source content, excluding first-observed/run provenance."""

    return (
        record.source_release_id,
        record.external_id,
        record.record_type,
        record.record_version,
        record.supersedes_record_id,
        record.raw_object_uri,
        record.raw_sha256,
        record.source_updated_at,
        record.parser_version,
        record.license_policy_status,
        dict(record.payload),
    )


def _outbox_payload_identity(event_type: str, payload_value: Mapping[str, Any]) -> dict[str, Any]:
    """Projection payload identity, excluding source-record observation time."""

    payload = dict(payload_value)
    if event_type == "source_record.upserted" and isinstance(payload.get("record"), Mapping):
        record = dict(payload["record"])
        record.pop("retrieved_at", None)
        payload["record"] = record
    return payload


def _outbox_event_identity(event: OutboxEventInput) -> tuple[object, ...]:
    """Replay-safe event identity, excluding first-enqueue run provenance."""

    return (
        event.aggregate_type,
        event.aggregate_id,
        event.event_type,
        _outbox_payload_identity(event.event_type, event.payload),
    )


def _stored_outbox_event_identity(
    stored: tuple[str, str, str, Mapping[str, Any]],
) -> tuple[object, ...]:
    """Normalize a persisted outbox row with the same replay contract as input."""

    aggregate_type, aggregate_id, event_type, payload = stored
    return (
        aggregate_type,
        aggregate_id,
        event_type,
        _outbox_payload_identity(event_type, payload),
    )


class IngestionStore:
    def __init__(self, settings: PostgresSettings):
        self._settings = settings

    def _connect(self) -> psycopg.Connection[Any]:
        connection = psycopg.connect(**self._settings.connection_kwargs())
        connection.execute(
            sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self._settings.schema))
        )
        return connection

    def begin_run(
        self,
        dataset: SourceDatasetInput,
        release: SourceReleaseInput,
        run: IngestionRunInput,
    ) -> None:
        if release.dataset_id != dataset.id or run.source_release_id != release.id:
            raise ValueError("Dataset, release, and ingestion run identifiers do not form one chain")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_dataset (
                        id, source_id, name, provider, landing_uri, release_strategy,
                        policy_status, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        provider = EXCLUDED.provider,
                        landing_uri = EXCLUDED.landing_uri,
                        release_strategy = EXCLUDED.release_strategy,
                        policy_status = EXCLUDED.policy_status,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    WHERE source_dataset.source_id = EXCLUDED.source_id
                    """,
                    (
                        dataset.id,
                        dataset.source_id,
                        dataset.name,
                        dataset.provider,
                        dataset.landing_uri,
                        dataset.release_strategy,
                        dataset.policy_status,
                        Jsonb(dict(dataset.metadata)),
                    ),
                )
                if cursor.rowcount != 1:
                    raise IngestionConflictError(f"Dataset id {dataset.id!r} belongs to a different source")
                cursor.execute(
                    """
                    INSERT INTO source_release (
                        id, dataset_id, release_key, content_sha256, raw_object_uri,
                        retrieved_at, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        release.id,
                        release.dataset_id,
                        release.release_key,
                        release.content_sha256,
                        release.raw_object_uri,
                        release.retrieved_at,
                        Jsonb(dict(release.metadata or {})),
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        SELECT dataset_id, release_key, content_sha256, raw_object_uri, metadata
                        FROM source_release WHERE id = %s
                        """,
                        (release.id,),
                    )
                    existing = cursor.fetchone()
                    if existing != _source_release_identity(release):
                        raise IngestionConflictError(f"Release id {release.id!r} was reused with different content")
                cursor.execute(
                    """
                    INSERT INTO ingestion_run (
                        id, pipeline_id, source_release_id, status, pipeline_git_sha,
                        config_sha256, started_at, manifest
                    ) VALUES (%s, %s, %s, 'loading', %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        run.id,
                        run.pipeline_id,
                        run.source_release_id,
                        run.pipeline_git_sha,
                        run.config_sha256,
                        run.started_at,
                        Jsonb(dict(run.manifest or {})),
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        "SELECT pipeline_id, source_release_id, status FROM ingestion_run WHERE id = %s",
                        (run.id,),
                    )
                    existing = cursor.fetchone()
                    if existing is None or existing[:2] != (run.pipeline_id, run.source_release_id):
                        raise IngestionConflictError(f"Run id {run.id!r} was reused with different content")
                    if existing[2] not in {"loading", "succeeded"}:
                        raise IngestionStateError(f"Run {run.id!r} is already {existing[2]}")

    def pipeline_state_version(self, pipeline_id: str) -> int:
        """Return the activation version a newly started run must finalize against."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT version FROM ingest_state WHERE pipeline_id = %s",
                (pipeline_id,),
            ).fetchone()
        return 0 if row is None else int(row[0])

    def active_dataset_id(self, pipeline_id: str) -> str | None:
        """Return the active allowed dataset for a pipeline, fail-closed.

        PostgreSQL owns ingest activation and policy state. A missing state,
        dangling release, or dataset whose policy is no longer ``allowed``
        therefore makes the dataset unavailable to graph readers.
        """

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT dataset.id
                FROM ingest_state AS state
                JOIN source_release AS release ON release.id = state.active_release_id
                JOIN source_dataset AS dataset ON dataset.id = release.dataset_id
                WHERE state.pipeline_id = %s
                  AND dataset.policy_status = 'allowed'
                """,
                (pipeline_id,),
            ).fetchone()
        return None if row is None else str(row[0])

    def active_release_context(self, pipeline_id: str) -> ActiveReleaseContext | None:
        """Return the active allowed release with metadata needed by readers."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT dataset.id, dataset.source_id, dataset.name, dataset.provider,
                       dataset.landing_uri, dataset.release_strategy, dataset.policy_status,
                       dataset.metadata, release.id, release.release_key,
                       release.retrieved_at, release.content_sha256,
                       release.raw_object_uri, release.metadata,
                       state.last_successful_run_id, state.cursor, state.version
                FROM ingest_state AS state
                JOIN source_release AS release ON release.id = state.active_release_id
                JOIN source_dataset AS dataset ON dataset.id = release.dataset_id
                WHERE state.pipeline_id = %s
                  AND dataset.policy_status = 'allowed'
                """,
                (pipeline_id,),
            ).fetchone()
        if row is None:
            return None
        dataset = SourceDatasetInput(
            id=row[0], source_id=row[1], name=row[2], provider=row[3],
            landing_uri=row[4], release_strategy=row[5], policy_status=row[6], metadata=row[7],
        )
        release = SourceReleaseInput(
            id=row[8], dataset_id=dataset.id, release_key=row[9], retrieved_at=row[10],
            content_sha256=row[11], raw_object_uri=row[12], metadata=row[13],
        )
        return ActiveReleaseContext(
            pipeline_id=pipeline_id,
            dataset=dataset,
            release=release,
            last_successful_run_id=str(row[14]),
            cursor=row[15],
            version=int(row[16]),
        )

    def run_context(self, run_id: str) -> IngestionRunContext:
        """Return the server-authoritative dataset and release for ``run_id``.

        The internal HTTP boundary uses this rather than accepting source
        metadata from the caller, keeping every record tied to the
        dataset/release it was begun under.
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT dataset.id, dataset.source_id, dataset.name, dataset.provider,
                           dataset.landing_uri, dataset.release_strategy, dataset.policy_status,
                           dataset.metadata, release.id, release.release_key,
                           release.retrieved_at, release.content_sha256,
                           release.raw_object_uri, release.metadata
                    FROM ingestion_run AS run
                    JOIN source_release AS release ON release.id = run.source_release_id
                    JOIN source_dataset AS dataset ON dataset.id = release.dataset_id
                    WHERE run.id = %s
                    """,
                    (run_id,),
                )
                row = cursor.fetchone()
        if row is None:
            raise IngestionStateError(f"Unknown ingestion run {run_id!r}")
        dataset = SourceDatasetInput(
            id=row[0],
            source_id=row[1],
            name=row[2],
            provider=row[3],
            landing_uri=row[4],
            release_strategy=row[5],
            policy_status=row[6],
            metadata=row[7],
        )
        release = SourceReleaseInput(
            id=row[8],
            dataset_id=dataset.id,
            release_key=row[9],
            retrieved_at=row[10],
            content_sha256=row[11],
            raw_object_uri=row[12],
            metadata=row[13],
        )
        return IngestionRunContext(dataset=dataset, release=release)

    def append_batch(
        self,
        run_id: str,
        *,
        records: Sequence[SourceRecordInput] = (),
        quarantine_items: Sequence[QuarantineItemInput] = (),
        events: Sequence[OutboxEventInput] = (),
    ) -> None:
        if any(value.ingestion_run_id != run_id for value in (*records, *quarantine_items, *events)):
            raise ValueError("Every batch item must belong to the requested ingestion run")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, source_release_id FROM ingestion_run WHERE id = %s FOR UPDATE",
                    (run_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise IngestionStateError(f"Unknown ingestion run {run_id!r}")
                if row[0] != "loading":
                    raise IngestionStateError(f"Run {run_id!r} is not loading")
                if any(record.source_release_id != row[1] for record in records):
                    raise ValueError("Every source record must belong to the ingestion run's source release")
                for record in records:
                    self._insert_record(cursor, record)
                for item in quarantine_items:
                    cursor.execute(
                        """
                        INSERT INTO quarantine_item (
                            record_key, ingestion_run_id, stage, reason_code, severity,
                            field_path, raw_value_redacted, rule_version,
                            first_seen_run_id, last_seen_run_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (record_key, stage, reason_code, (COALESCE(field_path, '')))
                        DO UPDATE SET
                            ingestion_run_id = EXCLUDED.ingestion_run_id,
                            last_seen_run_id = EXCLUDED.last_seen_run_id,
                            last_seen_at = now(),
                            severity = EXCLUDED.severity,
                            raw_value_redacted = EXCLUDED.raw_value_redacted,
                            rule_version = EXCLUDED.rule_version
                        """,
                        (
                            item.record_key,
                            item.ingestion_run_id,
                            item.stage,
                            item.reason_code,
                            item.severity,
                            item.field_path,
                            Jsonb(item.raw_value_redacted),
                            item.rule_version,
                            item.ingestion_run_id,
                            item.ingestion_run_id,
                        ),
                    )
                for event in events:
                    self._insert_event(cursor, event)

    @staticmethod
    def _insert_record(cursor: psycopg.Cursor[Any], record: SourceRecordInput) -> None:
        cursor.execute(
            """
            INSERT INTO source_record (
                id, source_release_id, external_id, record_type, record_version,
                supersedes_record_id, raw_object_uri, raw_sha256, retrieved_at,
                source_updated_at, parser_version, ingestion_run_id,
                license_policy_status, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            (
                record.id,
                record.source_release_id,
                record.external_id,
                record.record_type,
                record.record_version,
                record.supersedes_record_id,
                record.raw_object_uri,
                record.raw_sha256,
                record.retrieved_at,
                record.source_updated_at,
                record.parser_version,
                record.ingestion_run_id,
                record.license_policy_status,
                Jsonb(dict(record.payload)),
            ),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            SELECT source_release_id, external_id, record_type, record_version,
                   supersedes_record_id, raw_object_uri, raw_sha256,
                   source_updated_at, parser_version, license_policy_status, payload
            FROM source_record WHERE id = %s
            """,
            (record.id,),
        )
        existing = cursor.fetchone()
        if existing != _source_record_identity(record):
            raise IngestionConflictError(f"Source record id {record.id!r} was reused with different content")

    @staticmethod
    def _insert_event(cursor: psycopg.Cursor[Any], event: OutboxEventInput) -> None:
        cursor.execute(
            """
            INSERT INTO outbox_event (
                event_key, aggregate_type, aggregate_id, event_type, payload, ingestion_run_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key) DO NOTHING
            RETURNING id
            """,
            (
                event.event_key,
                event.aggregate_type,
                event.aggregate_id,
                event.event_type,
                Jsonb(dict(event.payload)),
                event.ingestion_run_id,
            ),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            SELECT aggregate_type, aggregate_id, event_type, payload
            FROM outbox_event WHERE event_key = %s
            """,
            (event.event_key,),
        )
        existing = cursor.fetchone()
        if existing is None or _stored_outbox_event_identity(existing) != _outbox_event_identity(event):
            raise IngestionConflictError(f"Outbox key {event.event_key!r} was reused with different content")

    def activate_release(
        self,
        run_id: str,
        *,
        counts: Mapping[str, Any],
        cursor_value: Mapping[str, Any] | None = None,
        expected_state_version: int = 0,
    ) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pipeline_id, source_release_id, status FROM ingestion_run WHERE id = %s FOR UPDATE",
                    (run_id,),
                )
                run = cursor.fetchone()
                if run is None:
                    raise IngestionStateError(f"Unknown ingestion run {run_id!r}")
                pipeline_id, release_id, status = run
                cursor.execute(
                    """
                    SELECT version, last_successful_run_id, active_release_id
                    FROM ingest_state WHERE pipeline_id = %s FOR UPDATE
                    """,
                    (pipeline_id,),
                )
                state = cursor.fetchone()
                if status == "succeeded" and state is not None and state[1] == run_id:
                    return state[0]
                if status != "loading":
                    raise IngestionStateError(f"Run {run_id!r} is not loading")
                cursor.execute(
                    """
                    SELECT count(*) FROM quarantine_item
                    WHERE ingestion_run_id = %s AND severity = 'blocked' AND resolution_status = 'open'
                    """,
                    (run_id,),
                )
                if cursor.fetchone()[0]:
                    raise IngestionStateError(f"Run {run_id!r} has open blocked quarantine items")
                current_version = 0 if state is None else state[0]
                if current_version != expected_state_version:
                    raise IngestionStateError(
                        f"Pipeline {pipeline_id!r} state changed concurrently: "
                        f"expected {expected_state_version}, found {current_version}"
                    )
                cursor.execute(
                    """
                    UPDATE ingestion_run
                    SET status = 'succeeded', finished_at = now(), counts = %s
                    WHERE id = %s AND status = 'loading'
                    """,
                    (Jsonb(dict(counts)), run_id),
                )
                next_version = current_version + 1
                cursor.execute(
                    """
                    INSERT INTO ingest_state (
                        pipeline_id, active_release_id, last_successful_run_id,
                        cursor, version, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (pipeline_id) DO UPDATE SET
                        active_release_id = EXCLUDED.active_release_id,
                        last_successful_run_id = EXCLUDED.last_successful_run_id,
                        cursor = EXCLUDED.cursor,
                        version = EXCLUDED.version,
                        updated_at = now()
                    WHERE ingest_state.version = %s
                    """,
                    (
                        pipeline_id,
                        release_id,
                        run_id,
                        Jsonb(dict(cursor_value or {})),
                        next_version,
                        expected_state_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise IngestionStateError(
                        f"Pipeline {pipeline_id!r} state changed during activation"
                    )
                previous_release_id = None if state is None else state[2]
                if previous_release_id is not None and previous_release_id != release_id:
                    cursor.execute(
                        "UPDATE source_release SET status = 'superseded' WHERE id = %s",
                        (previous_release_id,),
                    )
                cursor.execute("UPDATE source_release SET status = 'active' WHERE id = %s", (release_id,))
                return next_version

    def fail_run(self, run_id: str, reason: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ingestion_run
                    SET status = 'failed', finished_at = now(), error_reason = %s
                    WHERE id = %s AND status IN ('pending', 'loading')
                    """,
                    (reason, run_id),
                )
                if cursor.rowcount == 0:
                    cursor.execute("SELECT status FROM ingestion_run WHERE id = %s", (run_id,))
                    row = cursor.fetchone()
                    if row is None:
                        raise IngestionStateError(f"Unknown ingestion run {run_id!r}")
                    if row[0] != "failed":
                        raise IngestionStateError(f"Run {run_id!r} cannot transition from {row[0]} to failed")

    def claim_outbox(
        self,
        worker_id: str,
        *,
        limit: int = 100,
        lease_seconds: int = 300,
    ) -> tuple[ClaimedOutboxEvent, ...]:
        if not worker_id or not 1 <= limit <= 1000 or lease_seconds < 1:
            raise ValueError("Invalid outbox claim parameters")
        token = uuid4()
        lease_before = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidates AS (
                        SELECT event.id FROM outbox_event AS event
                        WHERE event.published_at IS NULL
                          AND event.dead_lettered_at IS NULL
                          AND event.available_at <= now()
                          AND (event.claimed_at IS NULL OR event.claimed_at < %s)
                          AND NOT EXISTS (
                              SELECT 1 FROM outbox_event AS prior
                              WHERE prior.aggregate_type = event.aggregate_type
                                AND prior.aggregate_id = event.aggregate_id
                                AND prior.id < event.id
                                AND prior.published_at IS NULL
                          )
                        ORDER BY event.id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE outbox_event AS event
                    SET claimed_at = now(), claimed_by = %s, claim_token = %s,
                        attempts = event.attempts + 1, last_error = NULL
                    FROM candidates
                    WHERE event.id = candidates.id
                    RETURNING event.id, event.event_key, event.aggregate_type,
                              event.aggregate_id, event.event_type, event.payload,
                              event.ingestion_run_id, event.attempts, event.claim_token
                    """,
                    (lease_before, limit, worker_id, token),
                )
                return tuple(ClaimedOutboxEvent(*row) for row in cursor.fetchall())

    def mark_published(self, event: ClaimedOutboxEvent) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE outbox_event
                    SET published_at = now(), claimed_at = NULL, claimed_by = NULL,
                        claim_token = NULL, last_error = NULL
                    WHERE id = %s AND claim_token = %s AND published_at IS NULL
                    """,
                    (event.id, event.claim_token),
                )
                return cursor.rowcount == 1

    def record_projection_failure(
        self,
        event: ClaimedOutboxEvent,
        error: str,
        *,
        max_attempts: int = 10,
        retry_delay_seconds: int = 30,
    ) -> bool:
        if max_attempts < 1 or retry_delay_seconds < 0:
            raise ValueError("Invalid outbox retry parameters")
        dead_lettered_at = datetime.now(timezone.utc) if event.attempts >= max_attempts else None
        available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE outbox_event
                    SET claimed_at = NULL, claimed_by = NULL, claim_token = NULL,
                        last_error = %s, available_at = %s, dead_lettered_at = %s
                    WHERE id = %s AND claim_token = %s AND published_at IS NULL
                    """,
                    (error[:4000], available_at, dead_lettered_at, event.id, event.claim_token),
                )
                updated = cursor.rowcount == 1
                if updated and dead_lettered_at is not None:
                    cursor.execute(
                        """
                        INSERT INTO quarantine_item (
                            record_key, ingestion_run_id, stage, reason_code, severity,
                            raw_value_redacted, rule_version,
                            first_seen_run_id, last_seen_run_id
                        ) VALUES (%s, %s, 'project', 'projection_retry_exhausted', 'blocked',
                                  %s, 'outbox-v1', %s, %s)
                        ON CONFLICT (record_key, stage, reason_code, (COALESCE(field_path, '')))
                        DO UPDATE SET
                            ingestion_run_id = EXCLUDED.ingestion_run_id,
                            last_seen_run_id = EXCLUDED.last_seen_run_id,
                            last_seen_at = now(),
                            raw_value_redacted = EXCLUDED.raw_value_redacted,
                            resolution_status = 'open'
                        """,
                        (
                            f"{event.aggregate_type}:{event.aggregate_id}",
                            event.ingestion_run_id,
                            Jsonb(
                                {
                                    "outbox_event_id": event.id,
                                    "event_type": event.event_type,
                                    "error": error[:1000],
                                }
                            ),
                            event.ingestion_run_id,
                            event.ingestion_run_id,
                        ),
                    )
                return updated
