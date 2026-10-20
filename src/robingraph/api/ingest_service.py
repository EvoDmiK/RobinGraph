"""Framework-independent, fail-closed control-plane ingest service.

This boundary deliberately accepts only source/control-plane facts. It never
accepts Taxon, VernacularName, or any other Neo4j domain-graph mutation, and
source records remain PostgreSQL-only rather than being projected to Neo4j.

The Pydantic request/response DTOs and every operation back the internal
native DRF views (`robingraph.api.drf`).
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import re
import secrets
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, field_validator, model_validator

from ..ingest.store import (
    ActiveReleaseContext,
    IngestionConflictError,
    IngestionRunContext,
    IngestionRunInput,
    IngestionStateError,
    QuarantineItemInput,
    SourceDatasetInput,
    SourceRecordInput,
    SourceReleaseInput,
)
from .services import ApiError


_TOKEN_ENV = "ROBINGRAPH_INGEST_INTERNAL_TOKEN"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_MAX_LENGTH = 200
_JSON_MAX_BYTES = 1_000_000


class IngestStore(Protocol):
    """Small repository seam used by the HTTP boundary and its unit tests."""

    def begin_run(
        self, dataset: SourceDatasetInput, release: SourceReleaseInput, run: IngestionRunInput
    ) -> None: ...

    def pipeline_state_version(self, pipeline_id: str) -> int: ...

    def active_release_context(self, pipeline_id: str) -> ActiveReleaseContext | None: ...

    def run_context(self, run_id: str) -> IngestionRunContext: ...

    def append_batch(
        self,
        run_id: str,
        *,
        records: tuple[SourceRecordInput, ...],
        quarantine_items: tuple[QuarantineItemInput, ...],
        events: tuple[Any, ...],
    ) -> None: ...

    def activate_release(
        self,
        run_id: str,
        *,
        counts: dict[str, int],
        cursor_value: dict[str, JsonValue],
        expected_state_version: int,
    ) -> int: ...

    def fail_run(self, run_id: str, reason: str) -> None: ...


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _identifier(value: str) -> str:
    if not value or len(value) > _IDENTIFIER_MAX_LENGTH or any(character.isspace() for character in value):
        raise ValueError("must be a non-blank identifier without whitespace")
    return value


def _optional_identifier(value: str | None) -> str | None:
    return _identifier(value) if value is not None else None


def _json_object(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError("must be a JSON object") from error
    if len(serialized.encode("utf-8")) > _JSON_MAX_BYTES:
        raise ValueError(f"must not exceed {_JSON_MAX_BYTES} bytes")
    return value


def _http_uri(value: str) -> str:
    if not value.startswith(("https://", "http://")):
        raise ValueError("must be an http(s) URI")
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("must include a timezone")
    return value


def _optional_aware(value: datetime | None) -> datetime | None:
    return _aware(value) if value is not None else None


class DatasetRequest(_Request):
    id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    source_id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=500)
    provider: str = Field(min_length=1, max_length=500)
    landing_uri: str = Field(min_length=1, max_length=2_000)
    release_strategy: Literal["versioned", "dated_snapshot", "mutable"]
    policy_status: Literal["allowed", "restricted", "review_required", "denied"]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _ids = field_validator("id", "source_id")(_identifier)
    _landing_uri = field_validator("landing_uri")(_http_uri)
    _metadata = field_validator("metadata")(_json_object)


class ReleaseRequest(_Request):
    id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    release_key: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    retrieved_at: datetime
    content_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    raw_object_uri: str | None = Field(default=None, max_length=2_000)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _ids = field_validator("id", "release_key")(_identifier)
    _retrieved_at = field_validator("retrieved_at")(_aware)
    _metadata = field_validator("metadata")(_json_object)

    @field_validator("content_sha256")
    @classmethod
    def sha256_or_none(cls, value: str | None) -> str | None:
        if value is not None and _SHA256.fullmatch(value) is None:
            raise ValueError("must be a lowercase SHA-256 hex digest")
        return value

    @field_validator("raw_object_uri")
    @classmethod
    def raw_uri_or_none(cls, value: str | None) -> str | None:
        return _http_uri(value) if value is not None else None


class RunRequest(_Request):
    id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    pipeline_id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    started_at: datetime
    pipeline_git_sha: str | None = Field(default=None, max_length=128)
    config_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    manifest: dict[str, JsonValue] = Field(default_factory=dict)

    _ids = field_validator("id", "pipeline_id")(_identifier)
    _started_at = field_validator("started_at")(_aware)
    _manifest = field_validator("manifest")(_json_object)

    @field_validator("config_sha256")
    @classmethod
    def config_sha256_or_none(cls, value: str | None) -> str | None:
        if value is not None and _SHA256.fullmatch(value) is None:
            raise ValueError("must be a lowercase SHA-256 hex digest")
        return value


class BeginRequest(_Request):
    dataset: DatasetRequest
    release: ReleaseRequest
    run: RunRequest


class SourceRecordRequest(_Request):
    id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    external_id: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    record_type: str = Field(min_length=1, max_length=100)
    raw_object_uri: str = Field(min_length=1, max_length=2_000)
    raw_sha256: str = Field(min_length=64, max_length=64)
    retrieved_at: datetime
    parser_version: str = Field(min_length=1, max_length=200)
    license_policy_status: Literal["allowed", "restricted", "review_required", "denied"]
    payload: dict[str, JsonValue]
    record_version: str = Field(default="1", min_length=1, max_length=100)
    supersedes_record_id: str | None = Field(default=None, max_length=_IDENTIFIER_MAX_LENGTH)
    source_updated_at: datetime | None = None

    _ids = field_validator("id", "external_id", "record_version")(_identifier)
    _supersedes_record_id = field_validator("supersedes_record_id")(_optional_identifier)
    _raw_uri = field_validator("raw_object_uri")(_http_uri)
    _payload = field_validator("payload")(_json_object)
    _retrieved_at = field_validator("retrieved_at")(_aware)
    _source_updated_at = field_validator("source_updated_at")(_optional_aware)

    @field_validator("raw_sha256")
    @classmethod
    def raw_sha256_is_valid(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("must be a lowercase SHA-256 hex digest")
        return value


class QuarantineRequest(_Request):
    record_key: str = Field(min_length=1, max_length=_IDENTIFIER_MAX_LENGTH)
    stage: Literal["fetch", "parse", "validate", "resolve", "dedupe", "load", "embed", "project"]
    reason_code: str = Field(min_length=1, max_length=200)
    severity: Literal["warning", "error", "blocked"]
    rule_version: str = Field(min_length=1, max_length=100)
    field_path: str | None = Field(default=None, max_length=500)
    raw_value_redacted: JsonValue | None = None

    _record_key = field_validator("record_key")(_identifier)


class AppendRequest(_Request):
    records: list[SourceRecordRequest] = Field(default_factory=list, max_length=500)
    quarantine_items: list[QuarantineRequest] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def contains_work(self) -> "AppendRequest":
        if not self.records and not self.quarantine_items:
            raise ValueError("must include at least one record or quarantine item")
        return self


class FinalizeRequest(_Request):
    counts: dict[str, StrictInt] = Field(default_factory=dict)
    cursor: dict[str, JsonValue] = Field(default_factory=dict)
    expected_state_version: int = Field(default=0, ge=0)

    _cursor = field_validator("cursor")(_json_object)

    @field_validator("counts")
    @classmethod
    def counts_are_bounded_non_negative_integers(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 100:
            raise ValueError("must have at most 100 values")
        for key, count in value.items():
            _identifier(key)
            if isinstance(count, bool) or count < 0:
                raise ValueError("values must be non-negative integers")
        return value


class FailRequest(_Request):
    reason: str = Field(min_length=1, max_length=4_000)


class OperationResponse(_Request):
    status: Literal["started", "appended", "finalized", "failed"]
    state_version: int | None = None


class ActiveReleaseResponse(_Request):
    pipeline_id: str
    dataset_id: str
    release_id: str
    release_key: str
    content_sha256: str | None
    metadata: dict[str, JsonValue]
    cursor: dict[str, JsonValue]
    last_successful_run_id: str
    state_version: int


def _run_id(value: str) -> str:
    try:
        return _identifier(value)
    except ValueError as error:
        raise ApiError(422, "Invalid run id") from error


def _operation_error(error: Exception) -> ApiError:
    if isinstance(error, IngestionConflictError):
        return ApiError(409, "Ingestion conflict")
    if isinstance(error, IngestionStateError):
        return ApiError(409, "Invalid ingestion state")
    return ApiError(422, "Invalid ingestion request")


class IngestService:
    """Private ingest operations bound to an explicitly injected store.

    The caller must explicitly supply a repository; this module never creates
    a PostgreSQL connection from ambient environment configuration. The
    internal bearer token is mandatory and read once at construction.
    """

    def __init__(self, store: IngestStore) -> None:
        token = os.getenv(_TOKEN_ENV, "")
        if not token:
            raise ValueError(f"{_TOKEN_ENV} must be configured before enabling the ingest API")
        self.store = store
        self._token = token

    def require_internal_bearer(self, authorization: str | None) -> None:
        supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        if not supplied or not secrets.compare_digest(supplied, self._token):
            raise ApiError(401, "Unauthorized", {"WWW-Authenticate": "Bearer"})

    def active_release(self, pipeline_id: str) -> ActiveReleaseResponse:
        pipeline_id = _run_id(pipeline_id)
        try:
            active = self.store.active_release_context(pipeline_id)
        except ValueError as error:
            raise _operation_error(error) from error
        if active is None:
            raise ApiError(404, "Active release not found")
        return ActiveReleaseResponse(
            pipeline_id=active.pipeline_id,
            dataset_id=active.dataset.id,
            release_id=active.release.id,
            release_key=active.release.release_key,
            content_sha256=active.release.content_sha256,
            metadata=dict(active.release.metadata or {}),
            cursor=dict(active.cursor),
            last_successful_run_id=active.last_successful_run_id,
            state_version=active.version,
        )

    def begin(self, request: BeginRequest) -> OperationResponse:
        dataset = SourceDatasetInput(**request.dataset.model_dump())
        release = SourceReleaseInput(
            **request.release.model_dump(), dataset_id=dataset.id
        )
        run = IngestionRunInput(**request.run.model_dump(), source_release_id=release.id)
        try:
            self.store.begin_run(dataset, release, run)
            state_version = self.store.pipeline_state_version(run.pipeline_id)
        except (IngestionConflictError, IngestionStateError, ValueError) as error:
            raise _operation_error(error) from error
        return OperationResponse(status="started", state_version=state_version)

    def append(self, run_id: str, request: AppendRequest) -> OperationResponse:
        run_id = _run_id(run_id)
        try:
            context = self.store.run_context(run_id)
            records = tuple(
                SourceRecordInput(
                    **record.model_dump(),
                    source_release_id=context.release.id,
                    ingestion_run_id=run_id,
                )
                for record in request.records
            )
            quarantine_items = tuple(
                QuarantineItemInput(**item.model_dump(), ingestion_run_id=run_id)
                for item in request.quarantine_items
            )
            self.store.append_batch(
                run_id,
                records=records,
                quarantine_items=quarantine_items,
                events=(),
            )
        except (IngestionConflictError, IngestionStateError, ValueError) as error:
            raise _operation_error(error) from error
        return OperationResponse(status="appended")

    def finalize(self, run_id: str, request: FinalizeRequest) -> OperationResponse:
        run_id = _run_id(run_id)
        try:
            version = self.store.activate_release(
                run_id,
                counts=request.counts,
                cursor_value=request.cursor,
                expected_state_version=request.expected_state_version,
            )
        except (IngestionConflictError, IngestionStateError, ValueError) as error:
            raise _operation_error(error) from error
        return OperationResponse(status="finalized", state_version=version)

    def fail(self, run_id: str, request: FailRequest) -> OperationResponse:
        run_id = _run_id(run_id)
        try:
            self.store.fail_run(run_id, request.reason)
        except (IngestionConflictError, IngestionStateError, ValueError) as error:
            raise _operation_error(error) from error
        return OperationResponse(status="failed")
