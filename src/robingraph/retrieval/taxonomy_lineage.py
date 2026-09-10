"""Read-only contract for the AviList reference-taxonomy lineage lookup.

This is deliberately its own small protocol, separate from `GraphRepository`
and `OperationalObservationRepository`: it reads the AviList reference
taxonomy graph (`Taxon:BirdTaxon`, gated by the `reference-taxonomy`
`IngestState`), which is a different data area from both the fixture
`Taxon` graph and the GBIF `ExternalTaxonConcept` operational graph. The two
taxonomies are never merged (see `docs/graph-database-schema.md`).

A lineage can be resolved two ways: by the exact (case-insensitive)
`Taxon.scientific_name`, or by an exact (case-insensitive) Korean
`VernacularName` (`language='ko'`) directly attached to the target `Taxon`
within the active concept set. The AviList ingest currently only loads
English vernacular names (`language='en'`) -- see
`docs/graph-database-schema.md` -- so the Korean path is a real, licensed
lookup key with no guaranteed data yet; it must fail closed (404) rather
than fabricate a translation when no Korean `VernacularName` exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

MatchedBy = Literal["scientific_name", "korean_name"]


@dataclass(frozen=True)
class LineageTaxon:
    taxon_id: str
    rank: str
    scientific_name: str
    authority: str | None
    korean_name: str | None = None


@dataclass(frozen=True)
class TaxonomyLineage:
    query_scientific_name: str
    taxonomy_source: str
    taxonomy_release: str
    concept_set_id: str
    items: tuple[LineageTaxon, ...]
    # New, additive fields (defaulted so existing positional/keyword
    # construction of this dataclass keeps working unchanged):
    query_name: str | None = None
    resolved_query_scientific_name: str | None = None
    matched_by: MatchedBy = "scientific_name"


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

    def lineage_for_korean_name(self, korean_name: str) -> TaxonomyLineage | None:
        """Ordered order->family->genus->species lineage for an exact Korean-name match.

        `korean_name` is matched case-insensitively against a
        `VernacularName {language: 'ko'}` directly attached
        (`HAS_VERNACULAR_NAME`) to a `Taxon:BirdTaxon` in the currently
        active `reference-taxonomy` concept set. Returns `None` when no such
        licensed Korean vernacular name exists -- callers should treat that
        as "not found", not as a backend failure.
        """
        ...
