"""Loading and policy-filtering for the deterministic evaluation fixture."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .ingest.validation import validate_source_registry_record, validate_staging_record


ALLOWED_POLICY_STATUS = "allowed"


@dataclass(frozen=True)
class FixtureCorpus:
    """Policy-filtered records that are safe for search and answer generation."""

    taxonomy: tuple[dict[str, Any], ...]
    observations: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]
    chunks: tuple[dict[str, Any], ...]
    source_registry: dict[str, dict[str, Any]]
    manifest: dict[str, Any]

    @property
    def evidence_ids(self) -> frozenset[str]:
        return frozenset(
            [record["source_taxon_id"] for record in self.taxonomy]
            + [record["occurrence_id"] for record in self.observations]
            + [record["chunk_id"] for record in self.chunks]
        )

    def evidence_record(self, evidence_id: str) -> dict[str, Any] | None:
        for record in self.taxonomy:
            if record["source_taxon_id"] == evidence_id:
                return record
        for record in self.observations:
            if record["occurrence_id"] == evidence_id:
                return record
        for record in self.chunks:
            if record["chunk_id"] == evidence_id:
                return record
        return None


def default_fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "eval" / "v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read fixture JSONL: {path}") from error


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read fixture JSON: {path}") from error


def _verify_manifest(root: Path, manifest: dict[str, Any]) -> None:
    expected_counts = manifest.get("expected_counts", {})
    if manifest.get("fixture_version") != "v1":
        raise ValueError("Unsupported fixture version")
    for item in manifest.get("files", []):
        relative_path = item.get("path")
        if not isinstance(relative_path, str):
            raise ValueError("Fixture manifest has a file without a path")
        path = root / relative_path
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != item.get("sha256"):
            raise ValueError(f"Fixture checksum mismatch: {relative_path}")
        if path.stat().st_size != item.get("bytes"):
            raise ValueError(f"Fixture byte size mismatch: {relative_path}")
    if expected_counts.get("taxonomy") != 10 or expected_counts.get("gold_questions") != 15:
        raise ValueError("Fixture manifest does not describe the v1 contract")


def _require_valid_records(records: Iterable[dict[str, Any]], record_type: str) -> None:
    issues = [issue for record in records for issue in validate_staging_record(record_type, record)]
    if issues:
        details = ", ".join(f"{issue.record_key}:{issue.reason_code}:{issue.field_path}" for issue in issues)
        raise ValueError(f"Fixture staging validation failed: {details}")


def load_fixture(root: Path | None = None) -> FixtureCorpus:
    """Verify the manifest and produce a corpus excluding non-allowed records."""

    root = root or default_fixture_root()
    manifest = _read_json(root / "fixture-manifest.json")
    _verify_manifest(root, manifest)
    taxonomy = _read_jsonl(root / "input" / "taxonomy.jsonl")
    observations = _read_jsonl(root / "input" / "observations.jsonl")
    documents = _read_jsonl(root / "input" / "documents.jsonl")
    chunks = _read_jsonl(root / "input" / "chunks.jsonl")
    registry_records = _read_json(root / "source-registry.json")
    for records, record_type in [
        (taxonomy, "taxonomy"),
        (observations, "observation"),
        (documents, "document"),
        (chunks, "chunk"),
    ]:
        _require_valid_records(records, record_type)

    if len(taxonomy) != 10 or len(observations) != 101 or len(documents) != 3 or len(chunks) != 5:
        raise ValueError("Fixture input counts do not match v1")
    registry_issues = [issue for record in registry_records for issue in validate_source_registry_record(record)]
    if registry_issues:
        details = ", ".join(
            f"{issue.record_key}:{issue.reason_code}:{issue.field_path}" for issue in registry_issues
        )
        raise ValueError(f"Fixture source registry validation failed: {details}")
    registry = {record["source_id"]: record for record in registry_records}
    for record in [*taxonomy, *observations, *documents, *chunks]:
        source = registry.get(record["source_id"])
        if source is None:
            raise ValueError(f"Unknown fixture source: {record['source_id']}")
        if source["license_policy_status"] != record["license_policy_status"]:
            raise ValueError(f"Policy mismatch for {record['record_key']}")

    corpus = FixtureCorpus(
        taxonomy=tuple(record for record in taxonomy if record["license_policy_status"] == ALLOWED_POLICY_STATUS),
        observations=tuple(record for record in observations if record["license_policy_status"] == ALLOWED_POLICY_STATUS),
        documents=tuple(record for record in documents if record["license_policy_status"] == ALLOWED_POLICY_STATUS),
        chunks=tuple(record for record in chunks if record["license_policy_status"] == ALLOWED_POLICY_STATUS),
        source_registry=registry,
        manifest=manifest,
    )
    counts = manifest["expected_counts"]
    if (
        len(corpus.taxonomy) != counts["taxonomy"]
        or len(corpus.observations) != counts["allowed_observations"]
        or len(corpus.documents) != counts["allowed_documents"]
        or len(corpus.chunks) != counts["allowed_chunks"]
    ):
        raise ValueError("Policy-filtered fixture counts do not match manifest")
    return corpus
