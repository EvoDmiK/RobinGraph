"""The read-only data shapes and interface that `QuestionService` depends on.

`QuestionService` (see `robingraph.slice`) resolves names, places, and
documents and composes answers purely against this `GraphRepository`
protocol. It never branches on a specific taxon, place, or document
identifier, so the same entity-resolution and answer-composition code runs
unchanged against the in-memory fixture corpus (`FixtureRepository`) or a
live Neo4j graph (`robingraph.retrieval.neo4j_repository.Neo4jGraphRepository`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class VernacularName:
    language: str
    name: str


@dataclass(frozen=True)
class TaxonRecord:
    taxon_id: str
    scientific_name: str
    vernacular_names: tuple[VernacularName, ...]

    def names(self) -> tuple[str, ...]:
        """All name strings (scientific + vernacular) usable for text matching."""

        return (self.scientific_name, *(name.name for name in self.vernacular_names))

    def vernacular(self, language: str) -> str | None:
        for name in self.vernacular_names:
            if name.language == language:
                return name.name
        return None


@dataclass(frozen=True)
class PlaceRecord:
    place_id: str
    display_name: str


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    title: str


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class ObservationRecord:
    occurrence_id: str
    taxon_id: str
    place_id: str
    place_name: str
    event_date_raw: str
    sensitivity_class: str


@dataclass(frozen=True)
class SourceCitation:
    source_id: str
    source_url: str
    locator: str
    license_name: str


class GraphRepository(Protocol):
    """Read-only, policy-filtered access to the retrieval corpus."""

    mode: str
    taxonomy_release: str
    data_cutoff: str

    def list_taxonomy(self) -> tuple[TaxonRecord, ...]:
        """All taxa with resolvable names, for entity-resolution indexing."""
        ...

    def list_places(self) -> tuple[PlaceRecord, ...]:
        """All places with a display name observations may be filtered by."""
        ...

    def list_documents(self) -> tuple[DocumentRecord, ...]:
        """All documents whose metadata may be shown (see `policy.py`)."""
        ...

    def list_chunks(self) -> tuple[ChunkRecord, ...]:
        """All chunks eligible for retrieval, across every document."""
        ...

    def chunks_for_document(self, document_id: str) -> tuple[ChunkRecord, ...]:
        """Chunks for one document, ordered by `ordinal`."""
        ...

    def observations_for_taxa(
        self,
        taxon_ids: Sequence[str],
        place_id: str | None,
        month_prefix: str | None,
    ) -> tuple[ObservationRecord, ...]:
        """Observations of any of `taxon_ids`, optionally filtered by place and month.

        `month_prefix` is an ``"YYYY-MM"`` string compared against the first
        seven characters of `event_date_raw`.
        """
        ...

    def citation_for(self, evidence_id: str) -> SourceCitation:
        """Source, license, and locator for a taxon/observation/chunk evidence ID."""
        ...

    def known_evidence_ids(self) -> frozenset[str]:
        """Every evidence ID an answer is allowed to cite."""
        ...

    def known_private_coordinate_values(self) -> frozenset[str]:
        """Sensitive raw coordinate values that must never appear in answer text."""
        ...
