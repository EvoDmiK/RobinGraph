"""Backend-agnostic retrieval: entity resolution, repositories, and citations."""

from .repository import (
    ChunkRecord,
    DocumentRecord,
    GraphRepository,
    ObservationRecord,
    PlaceRecord,
    SourceCitation,
    TaxonRecord,
    VernacularName,
)
from .fixture_repository import FixtureRepository
from .operational import (
    OperationalCitation,
    OperationalMedia,
    OperationalObservation,
    OperationalObservationQuery,
    OperationalObservationRepository,
    OperationalPlace,
    OperationalTaxon,
)
from .taxonomy_lineage import LineageTaxon, TaxonomyLineage, TaxonomyLineageRepository

__all__ = [
    "ChunkRecord",
    "DocumentRecord",
    "FixtureRepository",
    "GraphRepository",
    "LineageTaxon",
    "ObservationRecord",
    "OperationalCitation",
    "OperationalMedia",
    "OperationalObservation",
    "OperationalObservationQuery",
    "OperationalObservationRepository",
    "OperationalPlace",
    "OperationalTaxon",
    "PlaceRecord",
    "SourceCitation",
    "TaxonRecord",
    "TaxonomyLineage",
    "TaxonomyLineageRepository",
    "VernacularName",
]
