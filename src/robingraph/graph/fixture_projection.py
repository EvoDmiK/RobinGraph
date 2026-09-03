"""Projection of policy-filtered fixture records into Neo4j-safe parameters."""

from __future__ import annotations

from typing import Any

from ..fixture import FixtureCorpus


def fixture_graph_payload(corpus: FixtureCorpus) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic graph records without any private coordinate fields."""

    taxa = []
    names = []
    for taxon in corpus.taxonomy:
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
            "source_id": record["source_id"],
            "source_release": record["source_release"],
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
            "raw_uri": record["raw_object_uri"],
            "raw_hash": record["raw_sha256"],
            "retrieved_at": record["retrieved_at"],
        }
        for record in corpus.observations
    ]
    documents = [
        {
            "id": record["document_id"],
            "source_record_key": record["record_key"],
            "source_id": record["source_id"],
            "source_release": record["source_release"],
            "title": record["title"],
            "language": record["language"],
            "raw_uri": record["raw_object_uri"],
            "raw_hash": record["raw_sha256"],
            "retrieved_at": record["retrieved_at"],
        }
        for record in corpus.documents
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
            "source_id": record["source_id"],
            "source_release": record["source_release"],
            "raw_uri": record["raw_object_uri"],
            "raw_hash": record["raw_sha256"],
            "retrieved_at": record["retrieved_at"],
        }
        for record in corpus.chunks
    ]
    return {"taxa": taxa, "names": names, "observations": observations, "documents": documents, "chunks": chunks}
