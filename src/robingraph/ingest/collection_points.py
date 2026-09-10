"""Validated collection boundaries for approved external data sources."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from .validation import POLICY_STATUSES, validate_source_registry_record


SCOPES = frozenset({"taxonomy", "traits", "habitat", "vegetation", "conservation"})
PAYLOAD_MODES = frozenset({"source_snapshot", "structured_claim", "spatial_inference", "link_only"})
EVIDENCE_KINDS = frozenset({"direct", "literature", "spatial_inference"})


@dataclass(frozen=True)
class CollectionPoint:
    collection_point_id: str
    source_id: str
    source_release: str
    scope: str
    role: str
    endpoint_uri: str
    payload_mode: str
    evidence_kind: str
    score: int
    enabled: bool
    license_policy_status: str
    target_entities: tuple[str, ...]
    expected_sha256: str | None = None
    notes: str | None = None

    @property
    def collectable(self) -> bool:
        """Whether automated collection may cross this boundary now."""

        return self.enabled and self.license_policy_status == "allowed"

    def as_dict(self) -> dict[str, object]:
        return {
            "collection_point_id": self.collection_point_id,
            "source_id": self.source_id,
            "source_release": self.source_release,
            "scope": self.scope,
            "role": self.role,
            "endpoint_uri": self.endpoint_uri,
            "payload_mode": self.payload_mode,
            "evidence_kind": self.evidence_kind,
            "score": self.score,
            "enabled": self.enabled,
            "license_policy_status": self.license_policy_status,
            "collectable": self.collectable,
            "target_entities": list(self.target_entities),
            "expected_sha256": self.expected_sha256,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CollectionPointRegistry:
    registry_version: str
    selected_design: str
    points: tuple[CollectionPoint, ...]

    def select(
        self,
        *,
        scope: str | None = None,
        include_blocked: bool = False,
    ) -> tuple[CollectionPoint, ...]:
        if scope is not None and scope not in SCOPES:
            raise ValueError(f"unknown collection scope: {scope}")
        return tuple(
            point
            for point in self.points
            if (scope is None or point.scope == scope) and (include_blocked or point.collectable)
        )


def default_config_root() -> Path:
    return Path(__file__).resolve().parents[3] / "config"


def _require_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"collection point requires non-empty {field}")
    return value


def _require_http_uri(record: dict[str, Any], field: str) -> str:
    value = _require_text(record, field)
    if urlsplit(value).scheme not in {"http", "https"}:
        raise ValueError(f"collection point {field} must be an HTTP(S) URI")
    return value


def _point_from_dict(record: dict[str, Any]) -> CollectionPoint:
    scope = _require_text(record, "scope")
    payload_mode = _require_text(record, "payload_mode")
    evidence_kind = _require_text(record, "evidence_kind")
    policy_status = _require_text(record, "license_policy_status")
    if scope not in SCOPES:
        raise ValueError(f"invalid collection scope: {scope}")
    if payload_mode not in PAYLOAD_MODES:
        raise ValueError(f"invalid payload mode: {payload_mode}")
    if evidence_kind not in EVIDENCE_KINDS:
        raise ValueError(f"invalid evidence kind: {evidence_kind}")
    if policy_status not in POLICY_STATUSES:
        raise ValueError(f"invalid collection policy status: {policy_status}")
    score = record.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise ValueError("collection point score must be an integer from 0 to 100")
    enabled = record.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("collection point enabled must be a boolean")
    if enabled and policy_status != "allowed":
        raise ValueError("only allowed collection points may be enabled")
    target_entities = record.get("target_entities")
    if not isinstance(target_entities, list) or not target_entities or not all(
        isinstance(value, str) and value.strip() for value in target_entities
    ):
        raise ValueError("collection point target_entities must be a non-empty string list")
    notes = record.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("collection point notes must be a string or null")
    expected_sha256 = record.get("expected_sha256")
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
    ):
        raise ValueError("collection point expected_sha256 must be a lowercase SHA-256 or null")
    return CollectionPoint(
        collection_point_id=_require_text(record, "collection_point_id"),
        source_id=_require_text(record, "source_id"),
        source_release=_require_text(record, "source_release"),
        scope=scope,
        role=_require_text(record, "role"),
        endpoint_uri=_require_http_uri(record, "endpoint_uri"),
        payload_mode=payload_mode,
        evidence_kind=evidence_kind,
        score=score,
        enabled=enabled,
        license_policy_status=policy_status,
        target_entities=tuple(target_entities),
        expected_sha256=expected_sha256,
        notes=notes,
    )


def load_collection_points(config_root: Path | None = None) -> CollectionPointRegistry:
    root = config_root or default_config_root()
    source_records = json.loads((root / "source-registry.json").read_text(encoding="utf-8"))
    if not isinstance(source_records, list):
        raise ValueError("source registry must be a JSON array")
    sources: dict[str, dict[str, Any]] = {}
    for source in source_records:
        if not isinstance(source, dict):
            raise ValueError("source registry entries must be objects")
        issues = validate_source_registry_record(source)
        if issues:
            details = ", ".join(f"{item.field_path}:{item.reason_code}" for item in issues)
            raise ValueError(f"invalid source registry entry: {details}")
        source_id = str(source["source_id"])
        if source_id in sources:
            raise ValueError(f"duplicate source_id: {source_id}")
        sources[source_id] = source

    payload = json.loads((root / "collection-points.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("collection point registry must be a JSON object")
    if payload.get("selected_design") != "terra-claim-first":
        raise ValueError("collection point registry must select terra-claim-first")
    records = payload.get("collection_points")
    if not isinstance(records, list):
        raise ValueError("collection_points must be a JSON array")
    points = tuple(_point_from_dict(record) for record in records if isinstance(record, dict))
    if len(points) != len(records):
        raise ValueError("collection point entries must be objects")
    point_ids: set[str] = set()
    for point in points:
        if point.collection_point_id in point_ids:
            raise ValueError(f"duplicate collection_point_id: {point.collection_point_id}")
        point_ids.add(point.collection_point_id)
        source = sources.get(point.source_id)
        if source is None:
            raise ValueError(f"unknown source_id: {point.source_id}")
        if point.enabled != source["enabled"]:
            raise ValueError(f"enabled mismatch for source: {point.source_id}")
        if point.license_policy_status != source["license_policy_status"]:
            raise ValueError(f"policy mismatch for source: {point.source_id}")
        if point.collectable and source["access_method"] == "download" and point.expected_sha256 is None:
            raise ValueError(f"enabled download requires expected_sha256: {point.collection_point_id}")

    return CollectionPointRegistry(
        registry_version=_require_text(payload, "registry_version"),
        selected_design=str(payload["selected_design"]),
        points=points,
    )


def serialize_points(points: Iterable[CollectionPoint]) -> list[dict[str, object]]:
    return [point.as_dict() for point in points]
