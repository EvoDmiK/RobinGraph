"""Read-only contract for the AviList reference-taxonomy lineage lookup.

This is deliberately its own small protocol, separate from `GraphRepository`
and `OperationalObservationRepository`: it reads the AviList reference
taxonomy graph (`Taxon:BirdTaxon`, gated by the `reference-taxonomy`
`IngestState`), which is a different data area from both the fixture
`Taxon` graph and the GBIF `ExternalTaxonConcept` operational graph. The two
taxonomies are never merged (see `docs/graph-database-schema.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LineageTaxon:
    taxon_id: str
    rank: str
    scientific_name: str
    authority: str | None


@dataclass(frozen=True)
class TaxonomyLineage:
    query_scientific_name: str
    taxonomy_source: str
    taxonomy_release: str
    concept_set_id: str
    items: tuple[LineageTaxon, ...]


class TaxonomyLineageRepository(Protocol):
    """Read-only access to the active AviList reference-taxonomy lineage."""

    def lineage_for_scientific_name(self, scientific_name: str) -> TaxonomyLineage | None:
        """Ordered order->family->genus->species lineage for an exact name match.

        `scientific_name` is matched case-insensitively against the exact
        scientific name of a `Taxon:BirdTaxon` in the currently active
        `reference-taxonomy` concept set. Returns `None` when no such taxon
        exists -- callers should treat that as "not found", not as a backend
        failure.
        """
        ...
