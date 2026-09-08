"""Read-only contracts for observations loaded by the operational GBIF workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OperationalObservationQuery:
    """Bounded filters accepted by the operational observation search."""

    taxon_key: str | None = None
    scientific_name: str | None = None
    place: str | None = None
    observed_from: str | None = None
    observed_to: str | None = None
    limit: int = 25
    offset: int = 0


@dataclass(frozen=True)
class OperationalTaxon:
    taxon_id: str
    external_key: str
    scientific_name: str
    canonical_name: str | None
    vernacular_name_raw: str | None
    rank: str


@dataclass(frozen=True)
class OperationalPlace:
    place_id: str
    name: str
    country_code: str


@dataclass(frozen=True)
class OperationalCitation:
    evidence_id: str
    dataset_id: str
    dataset_name: str
    source_url: str
    dataset_url: str
    license_uris: tuple[str, ...]
    retrieved_at: str
    source_updated_at: str | None


@dataclass(frozen=True)
class OperationalMedia:
    media_id: str
    media_type: str
    format: str | None
    landing_uri: str
    asset_uri: str | None
    creator: str | None
    publisher: str | None
    attribution: str
    license_uri: str


@dataclass(frozen=True)
class OperationalObservation:
    observation_id: str
    occurrence_id: str
    observed_at: str
    count: int | None
    basis: str
    sensitivity: str
    latitude: float | None
    longitude: float | None
    coordinate_uncertainty_m: float | None
    taxon: OperationalTaxon
    place: OperationalPlace
    citation: OperationalCitation
    media: tuple[OperationalMedia, ...]

    @property
    def coordinate_disclosure(self) -> str:
        return "public" if self.latitude is not None and self.longitude is not None else "withheld"


class OperationalObservationRepository(Protocol):
    """Policy-filtered access to the graph populated by the GBIF n8n workflow."""

    def search_observations(
        self, query: OperationalObservationQuery
    ) -> tuple[OperationalObservation, ...]:
        ...
