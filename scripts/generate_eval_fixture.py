#!/usr/bin/env python3
"""Create the deterministic, synthetic evaluation fixture described in docs/evaluation.md."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval" / "v1"
FIXTURE_VERSION = "v1"
RETRIEVED_AT = "2026-09-03T00:00:00Z"
RUN_ID = "fixture-run-v1"
PARSER_VERSION = "fixture-generator-v1"

TAXA = [
    ("anas-zonorhyncha", "Anas zonorhyncha", "흰뺨검둥오리", "Eastern Spot-billed Duck"),
    ("ardea-cinerea", "Ardea cinerea", "왜가리", "Grey Heron"),
    ("egretta-garzetta", "Egretta garzetta", "쇠백로", "Little Egret"),
    ("phalacrocorax-carbo", "Phalacrocorax carbo", "민물가마우지", "Great Cormorant"),
    ("alcedo-atthis", "Alcedo atthis", "물총새", "Common Kingfisher"),
    ("hirundo-rustica", "Hirundo rustica", "제비", "Barn Swallow"),
    ("dendrocopos-kizuki", "Dendrocopos kizuki", "쇠딱다구리", "Japanese Pygmy Woodpecker"),
    ("passer-montanus", "Passer montanus", "참새", "Eurasian Tree Sparrow"),
    ("turdus-pallidus", "Turdus pallidus", "흰배지빠귀", "Pale Thrush"),
    ("buteo-japonicus", "Buteo japonicus", "말똥가리", "Japanese Buzzard"),
]

PLACES = [
    ("fixture-place-lake", "fixture 호수", 37.5000, 127.0000),
    ("fixture-place-river", "fixture 하천", 37.5100, 127.0100),
    ("fixture-place-forest", "fixture 숲", 37.5200, 127.0200),
    ("fixture-place-park", "fixture 공원", 37.5300, 127.0300),
    ("fixture-place-coast", "fixture 해안", 37.5400, 127.0400),
]

FIRST_OBSERVATION = {
    "anas-zonorhyncha": ("fixture-place-lake", "2025-01-15"),
    "ardea-cinerea": ("fixture-place-river", "2025-04-12"),
    "hirundo-rustica": ("fixture-place-park", "2025-06-08"),
    "dendrocopos-kizuki": ("fixture-place-forest", "2025-03-21"),
    "turdus-pallidus": ("fixture-place-park", "2025-02-18"),
    "buteo-japonicus": ("fixture-place-coast", "2025-11-09"),
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def common_record(
    *, source_id: str, source_release: str, external_id: str, policy: str
) -> dict[str, Any]:
    raw_object_uri = f"https://example.invalid/robingraph/{source_id}/{external_id}.json"
    return {
        "record_key": f"{source_id}:{source_release}:{external_id}",
        "source_id": source_id,
        "source_release": source_release,
        "external_id": external_id,
        "raw_object_uri": raw_object_uri,
        "raw_sha256": sha256_text(raw_object_uri),
        "retrieved_at": RETRIEVED_AT,
        "parser_version": PARSER_VERSION,
        "ingestion_run_id": RUN_ID,
        "license_policy_status": policy,
    }


def taxonomy_records() -> list[dict[str, Any]]:
    records = []
    for slug, scientific_name, korean_name, english_name in TAXA:
        taxon_id = f"rg:taxon:{slug}"
        record = common_record(
            source_id="fixture-taxonomy",
            source_release="fixture-taxonomy-2026-09-03",
            external_id=taxon_id,
            policy="allowed",
        )
        record.update(
            {
                "source_taxon_id": taxon_id,
                "source_parent_taxon_id": None,
                "rank": "species",
                "taxonomic_status": "accepted",
                "scientific_name_raw": scientific_name,
                "canonical_name": scientific_name,
                "authorship": None,
                "accepted_source_taxon_id": None,
                "name_according_to": "fixture-avlist-2025",
                "concept_set_version": "fixture-avlist-2025",
                "vernacular_names": [
                    {"name": korean_name, "language": "ko", "region_code": "KR", "name_status": "preferred"},
                    {"name": english_name, "language": "en", "region_code": None, "name_status": "preferred"},
                ],
            }
        )
        records.append(record)
    return records


def place_for_observation(slug: str, offset: int) -> tuple[str, str, float, float]:
    # Every taxon has two observations per place; swap the first event as needed for gold cases.
    place_index = offset % len(PLACES)
    expected = FIRST_OBSERVATION.get(slug)
    if expected:
        required_index = next(index for index, place in enumerate(PLACES) if place[0] == expected[0])
        if offset == 0:
            place_index = required_index
        elif offset == required_index:
            place_index = 0
    return PLACES[place_index]


def observation_records() -> list[dict[str, Any]]:
    records = []
    for taxon_index, (slug, scientific_name, _, _) in enumerate(TAXA):
        for offset in range(10):
            record_number = taxon_index * 10 + offset + 1
            occurrence_id = f"fixture-occ-{record_number:03d}"
            place_id, locality, latitude, longitude = place_for_observation(slug, offset)
            date = FIRST_OBSERVATION.get(slug, (None, None))[1] if offset == 0 else None
            if date is None:
                month = ((taxon_index + offset) % 12) + 1
                day = ((record_number * 3) % 27) + 1
                date = f"2025-{month:02d}-{day:02d}"

            record = common_record(
                source_id="fixture-observation",
                source_release="fixture-observation-2026-09-03",
                external_id=occurrence_id,
                policy="allowed",
            )
            withheld = slug == "buteo-japonicus"
            record.update(
                {
                    "occurrence_id": occurrence_id,
                    "event_id": f"fixture-event-{record_number:03d}",
                    "scientific_name_raw": scientific_name,
                    "source_taxon_id": f"rg:taxon:{slug}",
                    "observed_at": f"{date}T10:00:00Z",
                    "event_date_raw": date,
                    "event_date_precision": "day",
                    "count": (offset % 5) + 1,
                    "basis_of_record": "human_observation",
                    "latitude_private": latitude if withheld else None,
                    "longitude_private": longitude if withheld else None,
                    "latitude_public": 37.5000 if withheld else latitude,
                    "longitude_public": 127.0000 if withheld else longitude,
                    "coordinate_uncertainty_m": 20000 if withheld else 10,
                    "geodetic_datum_raw": "WGS84",
                    "place_external_id": place_id,
                    "locality_public": locality,
                    "sensitivity_class": "withheld" if withheld else "public",
                    "observer_external_id": f"fixture-observer-{(record_number % 4) + 1}",
                    "occurrence_status": "present",
                }
            )
            records.append(record)

    restricted = common_record(
        source_id="fixture-restricted-observation",
        source_release="fixture-restricted-2026-09-03",
        external_id="fixture-occ-restricted-001",
        policy="denied",
    )
    restricted.update(
        {
            "occurrence_id": "fixture-occ-restricted-001",
            "event_id": "fixture-event-restricted-001",
            "scientific_name_raw": "Passer montanus",
            "source_taxon_id": "rg:taxon:passer-montanus",
            "observed_at": "2025-07-01T10:00:00Z",
            "event_date_raw": "2025-07-01",
            "event_date_precision": "day",
            "count": 1,
            "basis_of_record": "human_observation",
            "latitude_private": None,
            "longitude_private": None,
            "latitude_public": 37.5300,
            "longitude_public": 127.0300,
            "coordinate_uncertainty_m": 10,
            "geodetic_datum_raw": "WGS84",
            "place_external_id": "fixture-place-park",
            "locality_public": "fixture 공원",
            "sensitivity_class": "public",
            "observer_external_id": "fixture-observer-restricted",
            "occurrence_status": "present",
        }
    )
    records.append(restricted)
    return records


def document_records() -> list[dict[str, Any]]:
    definitions = [
        ("fixture-doc-waterbirds", "Fixture 물가 조류 관찰 기록", "allowed"),
        ("fixture-doc-woodland", "Fixture 도시 숲 조류 관찰 기록", "allowed"),
        ("fixture-review-document", "Fixture 검토 대기 문서", "review_required"),
    ]
    records = []
    for document_id, title, policy in definitions:
        source_id = "fixture-document" if policy == "allowed" else "fixture-review-document"
        record = common_record(
            source_id=source_id,
            source_release="fixture-document-2026-09-03",
            external_id=document_id,
            policy=policy,
        )
        record.update(
            {
                "document_id": document_id,
                "title": title,
                "language": "ko",
                "fulltext_storage_allowed": policy == "allowed",
                "chunk_storage_allowed": policy == "allowed",
                "embedding_allowed": policy == "allowed",
            }
        )
        records.append(record)
    return records


def chunk_records() -> list[dict[str, Any]]:
    definitions = [
        (
            "fixture-chunk-waterbirds-1",
            "fixture-doc-waterbirds",
            1,
            "관찰 결과",
            "fixture 호수에서 흰뺨검둥오리 관찰을, fixture 하천에서 왜가리 관찰을 기록한다.",
            "section 1",
            "allowed",
        ),
        (
            "fixture-chunk-waterbirds-2",
            "fixture-doc-waterbirds",
            2,
            "서식지",
            "이 fixture 문서는 호수와 하천을 물가 서식지로 설명한다.",
            "section 2",
            "allowed",
        ),
        (
            "fixture-chunk-woodland-1",
            "fixture-doc-woodland",
            1,
            "관찰 결과",
            "fixture 공원에서는 제비와 참새를, fixture 숲에서는 쇠딱다구리를 기록한다.",
            "section 1",
            "allowed",
        ),
        (
            "fixture-chunk-woodland-2",
            "fixture-doc-woodland",
            2,
            "서식지",
            "이 fixture 문서는 공원과 숲을 도시 녹지 서식지로 설명한다.",
            "section 2",
            "allowed",
        ),
        (
            "fixture-chunk-review-1",
            "fixture-review-document",
            1,
            "검토 대기",
            "이 텍스트는 review_required 정책 필터를 검증하는 용도다.",
            "section 1",
            "review_required",
        ),
    ]
    records = []
    for chunk_id, document_id, ordinal, section_path, text, locator, policy in definitions:
        source_id = "fixture-document" if policy == "allowed" else "fixture-review-document"
        record = common_record(
            source_id=source_id,
            source_release="fixture-document-2026-09-03",
            external_id=chunk_id,
            policy=policy,
        )
        record.update(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "ordinal": ordinal,
                "section_path": section_path,
                "text": text,
                "locator": locator,
                "char_start": 0,
                "char_end": len(text),
                "token_count": None,
                "content_hash": sha256_text(text),
                "embedding_model": None,
                "embedding_version": None,
            }
        )
        records.append(record)
    return records


def source_registry() -> list[dict[str, Any]]:
    return [
        {
            "source_id": source_id,
            "name": name,
            "provider": "RobinGraph fixture",
            "landing_uri": f"https://example.invalid/robingraph/{source_id}",
            "access_method": "manual",
            "auth_method": "none",
            "release_strategy": "versioned",
            "incremental_cursor": None,
            "rate_limit_note": None,
            "license_uri": "https://example.invalid/robingraph/test-license",
            "terms_uri": None,
            "adapter_owner": "RobinGraph",
            "enabled": enabled,
            "license_policy_status": policy,
        }
        for source_id, name, policy, enabled in [
            ("fixture-taxonomy", "Fixture taxonomy", "allowed", True),
            ("fixture-observation", "Fixture observations", "allowed", True),
            ("fixture-document", "Fixture documents", "allowed", True),
            ("fixture-restricted-observation", "Fixture restricted observation", "denied", False),
            ("fixture-review-document", "Fixture review document", "review_required", False),
        ]
    ]


def gold_questions() -> list[dict[str, Any]]:
    return [
        ("GQ-001", "참새의 학명은 무엇인가?", "entity", ["rg:taxon:passer-montanus"], [], ["rg:taxon:passer-montanus"], "answer", []),
        ("GQ-002", "Eurasian Tree Sparrow는 어떤 종인가?", "entity", ["rg:taxon:passer-montanus"], [], ["rg:taxon:passer-montanus"], "answer", []),
        ("GQ-003", "Alcedo atthis의 한국어 이름은?", "entity", ["rg:taxon:alcedo-atthis"], [], ["rg:taxon:alcedo-atthis"], "answer", []),
        ("GQ-004", "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?", "observation", ["rg:taxon:anas-zonorhyncha"], {"place_external_id": "fixture-place-lake", "event_month": "2025-01"}, ["fixture-occ-001"], "answer", []),
        ("GQ-005", "2025년 4월 fixture 하천에서 왜가리 관찰 근거를 보여줘.", "observation", ["rg:taxon:ardea-cinerea"], {"place_external_id": "fixture-place-river", "event_month": "2025-04"}, ["fixture-occ-011", "fixture-chunk-waterbirds-1"], "answer", []),
        ("GQ-006", "제비는 2025년 6월 fixture 공원에서 언제 관찰됐나?", "observation", ["rg:taxon:hirundo-rustica"], {"place_external_id": "fixture-place-park", "event_month": "2025-06"}, ["fixture-occ-051"], "answer", []),
        ("GQ-007", "쇠딱다구리와 제비 중 2025년 3월 fixture 숲 관찰 근거가 있는 종은?", "comparison", ["rg:taxon:dendrocopos-kizuki"], {"place_external_id": "fixture-place-forest", "event_month": "2025-03"}, ["fixture-occ-061"], "answer", []),
        ("GQ-008", "fixture 물가 조류 관찰 기록이 지지하는 종과 장소를 알려줘.", "document", ["rg:taxon:anas-zonorhyncha", "rg:taxon:ardea-cinerea"], [], ["fixture-chunk-waterbirds-1", "fixture-chunk-waterbirds-2"], "answer", []),
        ("GQ-009", "fixture 도시 숲 조류 관찰 기록에서 숲과 연결된 종은?", "document", ["rg:taxon:dendrocopos-kizuki"], [], ["fixture-chunk-woodland-1", "fixture-chunk-woodland-2"], "answer", []),
        ("GQ-010", "말똥가리의 정확한 관찰 좌표를 알려줘.", "policy", ["rg:taxon:buteo-japonicus"], {"sensitivity_class": "withheld"}, ["fixture-occ-091"], "abstain", ["latitude_private", "longitude_private", "37.5400", "127.0400"]),
        ("GQ-011", "물새는 fixture 호수에서 언제 보였나?", "ambiguous", ["rg:taxon:anas-zonorhyncha", "rg:taxon:phalacrocorax-carbo"], {"place_external_id": "fixture-place-lake"}, [], "clarify", []),
        ("GQ-012", "2025년 2월 fixture 공원에서 흰배지빠귀가 관찰됐나?", "observation", ["rg:taxon:turdus-pallidus"], {"place_external_id": "fixture-place-park", "event_month": "2025-02"}, ["fixture-occ-081"], "answer", []),
        ("GQ-013", "2025년 11월 fixture 해안의 말똥가리 관찰을 설명해줘.", "policy", ["rg:taxon:buteo-japonicus"], {"place_external_id": "fixture-place-coast", "event_month": "2025-11"}, ["fixture-occ-091"], "answer", ["latitude_private", "longitude_private", "37.5400", "127.0400"]),
        ("GQ-014", "fixture 검토 문서가 지지하는 새는 무엇인가?", "unsupported", [], [], [], "abstain", ["fixture-chunk-review-1"]),
        ("GQ-015", "fixture 데이터에 없는 펭귄 관찰 기록을 알려줘.", "unsupported", [], [], [], "abstain", []),
    ]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
        newline="\n",
    )


def search_questions() -> list[dict[str, Any]]:
    return [
        {"question_id": "SQ-001", "question_ko": "fixture 호수의 흰뺨검둥오리 관찰 기록", "relevant_chunk_ids": ["fixture-chunk-waterbirds-1"]},
        {"question_id": "SQ-002", "question_ko": "물가 서식지를 설명한 문서", "relevant_chunk_ids": ["fixture-chunk-waterbirds-2"]},
        {"question_id": "SQ-003", "question_ko": "도시 녹지 서식지를 설명한 문서", "relevant_chunk_ids": ["fixture-chunk-woodland-2"]},
        {"question_id": "SQ-004", "question_ko": "쇠딱다구리와 제비의 관찰 기록", "relevant_chunk_ids": ["fixture-chunk-woodland-1"]},
        {"question_id": "SQ-005", "question_ko": "검토 대기 정책 텍스트", "relevant_chunk_ids": [], "forbidden_chunk_ids": ["fixture-chunk-review-1"]},
    ]


def validate(taxonomy: list[dict[str, Any]], observations: list[dict[str, Any]], documents: list[dict[str, Any]], chunks: list[dict[str, Any]], gold: list[dict[str, Any]], search_gold: list[dict[str, Any]]) -> None:
    allowed_observations = [record for record in observations if record["license_policy_status"] == "allowed"]
    allowed_documents = [record for record in documents if record["license_policy_status"] == "allowed"]
    allowed_chunks = [record for record in chunks if record["license_policy_status"] == "allowed"]
    assert len(taxonomy) == 10
    assert len(allowed_observations) == 100
    assert len(observations) == 101
    assert len(allowed_documents) == 2
    assert len(allowed_chunks) == 4
    assert len(gold) == 15
    assert len(search_gold) == 5
    assert {record["occurrence_id"] for record in allowed_observations} == {
        f"fixture-occ-{index:03d}" for index in range(1, 101)
    }
    assert all(record["source_id"] != "fixture-restricted-observation" for record in allowed_observations)
    assert all(record["latitude_private"] is None for record in allowed_observations if record["sensitivity_class"] == "public")
    assert all(record["latitude_private"] is not None for record in allowed_observations if record["sensitivity_class"] == "withheld")


def generate(output: Path = OUTPUT) -> None:
    """Write byte-identical UTF-8/LF fixture files on every supported platform."""
    input_dir = output / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    taxonomy = taxonomy_records()
    observations = observation_records()
    documents = document_records()
    chunks = chunk_records()
    gold = [
        {
            "question_id": question_id,
            "question_ko": question_ko,
            "query_type": query_type,
            "expected_taxon_ids": expected_taxon_ids,
            "required_filters": required_filters,
            "acceptable_evidence_ids": acceptable_evidence_ids,
            "expected_disposition": disposition,
            "must_not_include": must_not_include,
        }
        for (
            question_id,
            question_ko,
            query_type,
            expected_taxon_ids,
            required_filters,
            acceptable_evidence_ids,
            disposition,
            must_not_include,
        ) in gold_questions()
    ]
    search_gold = search_questions()
    validate(taxonomy, observations, documents, chunks, gold, search_gold)

    write_jsonl(input_dir / "taxonomy.jsonl", taxonomy)
    write_jsonl(input_dir / "observations.jsonl", observations)
    write_jsonl(input_dir / "documents.jsonl", documents)
    write_jsonl(input_dir / "chunks.jsonl", chunks)
    write_jsonl(output / "gold-questions.jsonl", gold)
    write_jsonl(output / "search-questions.jsonl", search_gold)
    write_json(output / "source-registry.json", source_registry())

    tracked_paths = [
        input_dir / "taxonomy.jsonl",
        input_dir / "observations.jsonl",
        input_dir / "documents.jsonl",
        input_dir / "chunks.jsonl",
        output / "gold-questions.jsonl",
        output / "search-questions.jsonl",
        output / "source-registry.json",
    ]
    manifest = {
        "fixture_version": FIXTURE_VERSION,
        "ingestion_run_id": RUN_ID,
        "taxonomy_release": "fixture-avlist-2025",
        "policy_version": "fixture-policy-v1",
        "retrieved_at": RETRIEVED_AT,
        "expected_counts": {
            "taxonomy": 10,
            "allowed_observations": 100,
            "input_observations": 101,
            "allowed_documents": 2,
            "allowed_chunks": 4,
            "gold_questions": 15,
            "search_questions": 5,
            "expected_quarantine": 0,
        },
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in tracked_paths
        ],
    }
    write_json(output / "fixture-manifest.json", manifest)
    print(f"Wrote deterministic fixture to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Destination fixture directory")
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
