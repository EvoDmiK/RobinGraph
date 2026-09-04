"""Projection of policy-filtered fixture records into Neo4j-safe parameters.

Policy is re-checked here rather than trusted from the caller: `FixtureCorpus`
is normally built by `fixture.load_fixture`, which already filters by
`license_policy_status` and the document fulltext/chunk/embedding flags, but
a caller may construct or mutate a `FixtureCorpus` directly (for example to
simulate a policy revocation in a test). Reapplying `policy.py` here means a
record that is no longer allowed -- or whose source registry entry cannot be
resolved as `allowed` -- is dropped from the graph payload regardless of how
the corpus was assembled, so a subsequent `neo4j_client.load_fixture` cannot
project stale or unlicensed content even from a stale corpus object.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .. import policy
from ..fixture import FixtureCorpus


def _source_allowed(record: dict[str, Any], corpus: FixtureCorpus) -> bool:
    """Fail-closed: only true when the record's own source resolves to an allowed license."""

    source = corpus.source_registry.get(record.get("source_id"))
    return source is not None and source.get("enabled") is True and source.get("license_policy_status") == policy.ALLOWED


def _source_fields(record: dict[str, Any], corpus: FixtureCorpus) -> dict[str, Any]:
    """Source/license provenance shared by every category (taxa/observations/documents/chunks)."""

    source = corpus.source_registry[record["source_id"]]
    return {
        "source_id": record["source_id"],
        "source_release": record["source_release"],
        "landing_uri": source["landing_uri"],
        "license_uri": source["license_uri"],
        "license_name": source.get("license_name") or source["license_uri"],
        "license_policy_status": record["license_policy_status"],
        "raw_uri": record["raw_object_uri"],
        "raw_hash": record["raw_sha256"],
        "retrieved_at": record["retrieved_at"],
    }


def fixture_graph_payload(corpus: FixtureCorpus) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic graph records without any private coordinate fields."""

    document_by_id = {record["document_id"]: record for record in corpus.documents}

    taxa = []
    names = []
    for taxon in corpus.taxonomy:
        if not (policy.record_allowed(taxon) and _source_allowed(taxon, corpus)):
            continue
        taxon_id = taxon["source_taxon_id"]
        taxa.append(
            {
                "id": taxon_id,
                "rank": taxon["rank"],
                "status": taxon["taxonomic_status"],
                "canonical_label": taxon["canonical_name"],
                "concept_set_id": taxon["concept_set_version"],
                "scientific_name": taxon["scientific_name_raw"],
                "source_record_key": taxon["record_key"],
                **_source_fields(taxon, corpus),
            }
        )
        for name in taxon["vernacular_names"]:
            names.append(
                {
                    "id": f"{taxon_id}:vernacular:{name['language']}:{name['name']}",
                    "taxon_id": taxon_id,
                    "name": name["name"],
                    "normalized_name": name["name"].casefold(),
                    "language": name["language"],
                    "region": name["region_code"],
                    "status": name["name_status"],
                }
            )

    observations = [
        {
            "id": record["record_key"],
            "occurrence_id": record["occurrence_id"],
            "source_record_key": record["record_key"],
            "taxon_id": record["source_taxon_id"],
            "scientific_name_raw": record["scientific_name_raw"],
            "observed_at": record["observed_at"],
            "event_date_raw": record["event_date_raw"],
            "event_date_precision": record["event_date_precision"],
            "count": record["count"],
            "basis": record["basis_of_record"],
            "lat": record["latitude_public"],
            "lon": record["longitude_public"],
            "coordinate_uncertainty_m": record["coordinate_uncertainty_m"],
            "sensitivity": record["sensitivity_class"],
            "place_id": record["place_external_id"],
            "place_name": record["locality_public"],
            **_source_fields(record, corpus),
        }
        for record in corpus.observations
        if policy.record_allowed(record) and _source_allowed(record, corpus)
    ]
    documents = [
        {
            "id": record["document_id"],
            "source_record_key": record["record_key"],
            "title": record["title"],
            "language": record["language"],
            # Projected so retrieval.neo4j_hybrid can independently recheck
            # embedding eligibility from the graph itself (fail-closed),
            # instead of trusting an out-of-band Python recomputation --
            # embedding_allowed is a strictly narrower permission than
            # chunk_storage_allowed (which already gates whether the chunk
            # is projected at all; see policy.document_embedding_allowed),
            # so a chunk can remain validly indexed for fulltext while no
            # longer being embedding-eligible.
            "embedding_allowed": all(record.get(flag) is True for flag in (
                "fulltext_storage_allowed", "chunk_storage_allowed", "embedding_allowed"
            )),
            **_source_fields(record, corpus),
        }
        for record in corpus.documents
        if policy.document_metadata_allowed(record) and _source_allowed(record, corpus)
    ]
    chunks = [
        {
            "id": record["chunk_id"],
            "document_id": record["document_id"],
            "ordinal": record["ordinal"],
            "section": record["section_path"],
            "text": record["text"],
            "locator": record["locator"],
            "content_hash": record["content_hash"],
            "source_record_key": record["record_key"],
            **_source_fields(record, corpus),
        }
        for record in corpus.chunks
        if policy.chunk_allowed(record, document_by_id.get(record["document_id"]))
        and _source_allowed(record, corpus)
        and _source_allowed(document_by_id[record["document_id"]], corpus)
    ]
    for chunk in chunks:
        if hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest() != chunk["content_hash"]:
            raise ValueError(f"Chunk {chunk['id']} content hash mismatch")
    return {"taxa": taxa, "names": names, "observations": observations, "documents": documents, "chunks": chunks}
