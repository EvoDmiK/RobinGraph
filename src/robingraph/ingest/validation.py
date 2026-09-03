"""Validation rules shared by staging adapters.

Policy status is not a format error: allowed rows continue to retrieval while
restricted, denied, and review-required rows remain auditable but are filtered
before indexing and answer generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable


POLICY_STATUSES = frozenset({"allowed", "restricted", "review_required", "denied"})
SENSITIVITY_CLASSES = frozenset({"public", "generalized", "withheld", "unknown"})
OCCURRENCE_STATUSES = frozenset({"present", "absent", "unknown"})
DATE_PRECISIONS = frozenset({"instant", "day", "month", "year", "range", "unknown"})
ACCESS_METHODS = frozenset({"api", "download", "manual"})
AUTH_METHODS = frozenset({"none", "api_key", "oauth", "manual"})
RELEASE_STRATEGIES = frozenset({"versioned", "dated_snapshot", "mutable"})


@dataclass(frozen=True)
class ValidationIssue:
    record_key: str
    stage: str
    reason_code: str
    severity: str
    field_path: str


def _issue(record: dict[str, Any], reason_code: str, field_path: str) -> ValidationIssue:
    return ValidationIssue(
        record_key=str(record.get("record_key", "<missing-record-key>")),
        stage="validate",
        reason_code=reason_code,
        severity="error",
        field_path=field_path,
    )


def _missing_fields(record: dict[str, Any], fields: Iterable[str]) -> list[ValidationIssue]:
    return [_issue(record, "missing_required_field", field) for field in fields if record.get(field) in (None, "")]


def _common_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    issues = _missing_fields(
        record,
        (
            "record_key",
            "source_id",
            "source_release",
            "external_id",
            "raw_object_uri",
            "raw_sha256",
            "retrieved_at",
            "parser_version",
            "ingestion_run_id",
            "license_policy_status",
        ),
    )
    if record.get("license_policy_status") not in POLICY_STATUSES:
        issues.append(_issue(record, "invalid_policy_status", "license_policy_status"))
    return issues


def _validate_date(value: Any, precision: Any, record: dict[str, Any]) -> list[ValidationIssue]:
    if not isinstance(value, str):
        return [_issue(record, "invalid_date", "event_date_raw")]
    if precision not in DATE_PRECISIONS:
        return [_issue(record, "invalid_date_precision", "event_date_precision")]
    if precision in {"day", "instant"}:
        try:
            date.fromisoformat(value[:10])
        except ValueError:
            return [_issue(record, "invalid_date", "event_date_raw")]
    elif precision == "month" and len(value) == 7:
        try:
            date.fromisoformat(f"{value}-01")
        except ValueError:
            return [_issue(record, "invalid_date", "event_date_raw")]
    elif precision == "year" and len(value) == 4 and value.isdigit():
        return []
    elif precision not in {"range", "unknown", "month", "year"}:
        return [_issue(record, "invalid_date", "event_date_raw")]
    return []


def _validate_coordinate(record: dict[str, Any], latitude_field: str, longitude_field: str) -> list[ValidationIssue]:
    latitude = record.get(latitude_field)
    longitude = record.get(longitude_field)
    if latitude is None and longitude is None:
        return []
    if latitude is None or longitude is None:
        return [_issue(record, "incomplete_coordinate", latitude_field if latitude is None else longitude_field)]
    if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
        return [_issue(record, "invalid_latitude", latitude_field)]
    if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
        return [_issue(record, "invalid_longitude", longitude_field)]
    return []


def _observation_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    issues = _missing_fields(
        record,
        (
            "occurrence_id",
            "scientific_name_raw",
            "event_date_raw",
            "event_date_precision",
            "basis_of_record",
            "sensitivity_class",
            "occurrence_status",
        ),
    )
    issues.extend(_validate_date(record.get("event_date_raw"), record.get("event_date_precision"), record))
    issues.extend(_validate_coordinate(record, "latitude_private", "longitude_private"))
    issues.extend(_validate_coordinate(record, "latitude_public", "longitude_public"))
    count = record.get("count")
    if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 0):
        issues.append(_issue(record, "invalid_count", "count"))
    if record.get("sensitivity_class") not in SENSITIVITY_CLASSES:
        issues.append(_issue(record, "invalid_sensitivity_class", "sensitivity_class"))
    if record.get("occurrence_status") not in OCCURRENCE_STATUSES:
        issues.append(_issue(record, "invalid_occurrence_status", "occurrence_status"))
    if record.get("sensitivity_class") == "unknown" and any(
        record.get(field) is not None for field in ("latitude_public", "longitude_public")
    ):
        issues.append(_issue(record, "unknown_sensitivity_has_public_coordinate", "latitude_public"))
    return issues


def _taxonomy_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    return _missing_fields(
        record,
        ("source_taxon_id", "rank", "taxonomic_status", "scientific_name_raw", "concept_set_version"),
    )


def _document_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    issues = _missing_fields(record, ("document_id", "title", "language"))
    for field in ("fulltext_storage_allowed", "chunk_storage_allowed", "embedding_allowed"):
        if not isinstance(record.get(field), bool):
            issues.append(_issue(record, "invalid_document_policy_flag", field))
    return issues


def _chunk_issues(record: dict[str, Any]) -> list[ValidationIssue]:
    issues = _missing_fields(record, ("chunk_id", "document_id", "section_path", "text", "locator", "content_hash"))
    if not isinstance(record.get("ordinal"), int) or record.get("ordinal", 0) < 1:
        issues.append(_issue(record, "invalid_chunk_ordinal", "ordinal"))
    return issues


def validate_source_registry_record(record: dict[str, Any]) -> tuple[ValidationIssue, ...]:
    """Validate one source registry entry without reading secrets or endpoints."""

    issues = _missing_fields(
        record,
        (
            "source_id",
            "name",
            "provider",
            "landing_uri",
            "access_method",
            "auth_method",
            "release_strategy",
            "license_uri",
            "adapter_owner",
            "enabled",
            "license_policy_status",
        ),
    )
    for field in ("landing_uri", "license_uri"):
        value = record.get(field)
        if isinstance(value, str) and not value.startswith(("https://", "http://")):
            issues.append(_issue(record, "invalid_uri", field))
    if record.get("access_method") not in ACCESS_METHODS:
        issues.append(_issue(record, "invalid_access_method", "access_method"))
    if record.get("auth_method") not in AUTH_METHODS:
        issues.append(_issue(record, "invalid_auth_method", "auth_method"))
    if record.get("release_strategy") not in RELEASE_STRATEGIES:
        issues.append(_issue(record, "invalid_release_strategy", "release_strategy"))
    if not isinstance(record.get("enabled"), bool):
        issues.append(_issue(record, "invalid_enabled_flag", "enabled"))
    if record.get("license_policy_status") not in POLICY_STATUSES:
        issues.append(_issue(record, "invalid_policy_status", "license_policy_status"))
    return tuple(issues)


def validate_staging_record(record_type: str, record: dict[str, Any]) -> tuple[ValidationIssue, ...]:
    """Return all deterministic validation issues for a canonical staging row."""

    issues = _common_issues(record)
    if record_type == "taxonomy":
        issues.extend(_taxonomy_issues(record))
    elif record_type == "observation":
        issues.extend(_observation_issues(record))
    elif record_type == "document":
        issues.extend(_document_issues(record))
    elif record_type == "chunk":
        issues.extend(_chunk_issues(record))
    else:
        issues.append(_issue(record, "unknown_record_type", "record_type"))
    return tuple(issues)
