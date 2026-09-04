"""`GraphRepository` backed by the in-memory, policy-filtered fixture corpus."""

from __future__ import annotations

from ..fixture import FixtureCorpus
from .repository import (
    ChunkRecord,
    DocumentRecord,
    ObservationRecord,
    PlaceRecord,
    SourceCitation,
    TaxonRecord,
    VernacularName,
)


class FixtureRepository:
    """Serves `FixtureCorpus` records through the backend-agnostic repository shape."""

    mode = "fixture"

    def __init__(self, corpus: FixtureCorpus) -> None:
        self._corpus = corpus
        self.taxonomy_release = corpus.manifest["taxonomy_release"]
        self.data_cutoff = corpus.manifest["retrieved_at"]

    def list_taxonomy(self) -> tuple[TaxonRecord, ...]:
        return tuple(
            TaxonRecord(
                taxon_id=record["source_taxon_id"],
                scientific_name=record["scientific_name_raw"],
                vernacular_names=tuple(
                    VernacularName(name["language"], name["name"]) for name in record["vernacular_names"]
                ),
            )
            for record in self._corpus.taxonomy
        )

    def list_places(self) -> tuple[PlaceRecord, ...]:
        seen: dict[str, str] = {}
        for record in self._corpus.observations:
            place_id = record.get("place_external_id")
            locality = record.get("locality_public")
            if place_id and locality:
                seen.setdefault(place_id, locality)
        return tuple(PlaceRecord(place_id, display_name) for place_id, display_name in seen.items())

    def list_documents(self) -> tuple[DocumentRecord, ...]:
        return tuple(DocumentRecord(record["document_id"], record["title"]) for record in self._corpus.documents)

    def list_chunks(self) -> tuple[ChunkRecord, ...]:
        return tuple(
            ChunkRecord(record["chunk_id"], record["document_id"], record["ordinal"], record["text"])
            for record in self._corpus.chunks
        )

    def chunks_for_document(self, document_id: str) -> tuple[ChunkRecord, ...]:
        matching = [record for record in self._corpus.chunks if record["document_id"] == document_id]
        matching.sort(key=lambda record: record["ordinal"])
        return tuple(ChunkRecord(record["chunk_id"], record["document_id"], record["ordinal"], record["text"]) for record in matching)

    def observations_for_taxa(self, taxon_ids, place_id=None, month_prefix=None) -> tuple[ObservationRecord, ...]:
        candidates = set(taxon_ids)
        records = [record for record in self._corpus.observations if record["source_taxon_id"] in candidates]
        if place_id is not None:
            records = [record for record in records if record["place_external_id"] == place_id]
        if month_prefix is not None:
            records = [record for record in records if record["event_date_raw"][:7] == month_prefix]
        return tuple(
            ObservationRecord(
                occurrence_id=record["occurrence_id"],
                taxon_id=record["source_taxon_id"],
                place_id=record["place_external_id"],
                place_name=record["locality_public"],
                event_date_raw=record["event_date_raw"],
                sensitivity_class=record["sensitivity_class"],
            )
            for record in records
        )

    def citation_for(self, evidence_id: str) -> SourceCitation:
        record = self._corpus.evidence_record(evidence_id)
        if record is None:
            raise ValueError(f"Unknown evidence ID: {evidence_id}")
        source = self._corpus.source_registry[record["source_id"]]
        locator = record.get("locator") or record.get("occurrence_id") or record.get("source_taxon_id")
        return SourceCitation(
            source_id=record["source_id"],
            source_url=source["landing_uri"],
            locator=locator,
            license_name=source.get("license_name") or source["license_uri"],
        )

    def known_evidence_ids(self) -> frozenset[str]:
        return self._corpus.evidence_ids

    def known_private_coordinate_values(self) -> frozenset[str]:
        values: set[str] = set()
        for record in self._corpus.observations:
            if record["sensitivity_class"] != "withheld":
                continue
            for value in (record.get("latitude_private"), record.get("longitude_private")):
                if value is not None:
                    values.add(str(value))
        return frozenset(values)
