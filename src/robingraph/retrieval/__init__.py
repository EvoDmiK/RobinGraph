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

__all__ = [
    "ChunkRecord",
    "DocumentRecord",
    "FixtureRepository",
    "GraphRepository",
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
    "VernacularName",
]
