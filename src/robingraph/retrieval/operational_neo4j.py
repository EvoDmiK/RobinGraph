"""Neo4j reader for observations loaded by the operational GBIF workflow."""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from ..graph.settings import Neo4jSettings
from .operational import (
    OperationalCitation,
    OperationalMedia,
    OperationalObservation,
    OperationalObservationQuery,
    OperationalPlace,
    OperationalTaxon,
)


_ALLOWED_MEDIA_LICENSE_URIS = tuple(
    f"{scheme}://{path}{suffix}"
    for scheme in ("http", "https")
    for path in (
        "creativecommons.org/publicdomain/zero/1.0/",
        "creativecommons.org/licenses/by/3.0/",
        "creativecommons.org/licenses/by/4.0/",
    )
    for suffix in ("", "legalcode", "legalcode/")
)


# This query deliberately requires the complete provenance and allowed-license
# chain. Records written manually or left in a partially loaded state stay
# invisible. Query input is bound as parameters; user text never becomes Cypher.
_OBSERVATION_SEARCH_QUERY = """
MATCH (observation:Observation)-[:IDENTIFIED_AS]->(taxon:ExternalTaxonConcept:BirdTaxon)
MATCH (observation)-[:WITHIN]->(place:Place)
MATCH (observation)-[:FROM_RECORD]->(source:SourceRecord)-[:IN_DATASET]->(dataset:SourceDataset)
MATCH (dataset)-[:LICENSED_UNDER]->(license:License)
MATCH (evidence:EvidenceUnit)-[:FROM_RECORD]->(source)
WHERE source.record_type = 'observation'
  AND dataset.provider = 'GBIF'
  AND taxon.provider = 'GBIF Backbone'
  AND evidence.evidence_type = 'observation'
  AND dataset.policy_status = 'allowed'
  AND license.policy_status = 'allowed'
  AND observation.sensitivity IN ['public', 'generalized']
  AND ($taxon_key IS NULL OR taxon.external_key = $taxon_key)
  AND (
    $scientific_name IS NULL
    OR toLower(taxon.scientific_name) CONTAINS toLower($scientific_name)
    OR toLower(coalesce(taxon.canonical_name, '')) CONTAINS toLower($scientific_name)
    OR toLower(coalesce(properties(taxon)['vernacular_name_raw'], '')) CONTAINS toLower($scientific_name)
  )
  AND ($place IS NULL OR toLower(place.name) CONTAINS toLower($place))
  AND ($observed_from IS NULL OR substring(observation.observed_at, 0, 10) >= $observed_from)
  AND ($observed_to IS NULL OR substring(observation.observed_at, 0, 10) <= $observed_to)
WITH observation, taxon, place, source, dataset, evidence, license
ORDER BY source.retrieved_at DESC, source.id DESC
WITH observation, taxon, place,
     collect({
       evidence_id: evidence.id,
       dataset_id: dataset.id,
       dataset_name: dataset.name,
       source_url: source.raw_uri,
       dataset_url: dataset.landing_uri,
       retrieved_at: source.retrieved_at,
       source_updated_at: source.source_updated_at
     })[0] AS citation,
     collect(DISTINCT coalesce(license.license_uri, license.id)) AS license_uris
OPTIONAL MATCH (observation)-[:HAS_MEDIA]->(media:MediaAsset)
WHERE media.redistribution_allowed = true AND media.license_uri IN $allowed_media_license_uris
WITH observation, taxon, place, citation, license_uris,
     collect(DISTINCT CASE WHEN media IS NULL THEN null ELSE {
       media_id: media.id,
       media_type: media.media_type,
       format: media.format,
       landing_uri: media.landing_uri,
       asset_uri: media.asset_uri,
       creator: media.creator,
       publisher: media.publisher,
       attribution: media.attribution,
       license_uri: media.license_uri
     } END) AS media_items
RETURN observation.id AS observation_id,
       observation.occurrence_id AS occurrence_id,
       observation.observed_at AS observed_at,
       observation.count AS count,
       observation.basis AS basis,
       observation.sensitivity AS sensitivity,
       CASE WHEN observation.sensitivity = 'public' THEN observation.lat ELSE null END AS latitude,
       CASE WHEN observation.sensitivity = 'public' THEN observation.lon ELSE null END AS longitude,
       CASE WHEN observation.sensitivity = 'public' THEN observation.coordinate_uncertainty_m ELSE null END
         AS coordinate_uncertainty_m,
       taxon.id AS taxon_id,
       taxon.external_key AS taxon_external_key,
       taxon.scientific_name AS scientific_name,
       taxon.canonical_name AS canonical_name,
       properties(taxon)['vernacular_name_raw'] AS vernacular_name_raw,
       taxon.rank AS taxon_rank,
       place.id AS place_id,
       place.name AS place_name,
       place.country_code AS country_code,
       citation.evidence_id AS evidence_id,
       citation.dataset_id AS dataset_id,
       citation.dataset_name AS dataset_name,
       citation.source_url AS source_url,
       citation.dataset_url AS dataset_url,
       license_uris,
       citation.retrieved_at AS retrieved_at,
       citation.source_updated_at AS source_updated_at,
       media_items
ORDER BY observation.observed_at DESC, observation.occurrence_id
SKIP $offset
LIMIT $limit
"""


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class Neo4jOperationalObservationRepository:
    """Read the non-fixture observation graph produced by n8n."""

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jOperationalObservationRepository":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _run(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._settings.database) as session:
            return session.run(query, **parameters).data()

    def search_observations(
        self, query: OperationalObservationQuery
    ) -> tuple[OperationalObservation, ...]:
        if not 1 <= query.limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if query.offset < 0:
            raise ValueError("offset must not be negative")
        if query.observed_from and query.observed_to and query.observed_from > query.observed_to:
            raise ValueError("observed_from must not be later than observed_to")

        taxon_key = _clean_optional(query.taxon_key)
        scientific_name = _clean_optional(query.scientific_name)
        place = _clean_optional(query.place)
        if query.taxon_key is not None and taxon_key is None:
            raise ValueError("taxon_key must not be blank")
        if query.scientific_name is not None and scientific_name is None:
            raise ValueError("scientific_name must not be blank")
        if query.place is not None and place is None:
            raise ValueError("place must not be blank")

        rows = self._run(
            _OBSERVATION_SEARCH_QUERY,
            taxon_key=taxon_key,
            scientific_name=scientific_name,
            place=place,
            observed_from=query.observed_from,
            observed_to=query.observed_to,
            allowed_media_license_uris=list(_ALLOWED_MEDIA_LICENSE_URIS),
            limit=query.limit,
            offset=query.offset,
        )
        return tuple(self._observation(row) for row in rows)

    @staticmethod
    def _observation(row: dict[str, Any]) -> OperationalObservation:
        license_uris = tuple(sorted(str(value) for value in (row["license_uris"] or []) if value))
        if not license_uris:
            # The Cypher requires an allowed License; this also guards against a
            # malformed projection or future query drift.
            raise ValueError("Operational observation has no allowed license")
        return OperationalObservation(
            observation_id=str(row["observation_id"]),
            occurrence_id=str(row["occurrence_id"]),
            observed_at=str(row["observed_at"]),
            count=None if row["count"] is None else int(row["count"]),
            basis=str(row["basis"]),
            sensitivity=str(row["sensitivity"]),
            latitude=None if row["latitude"] is None else float(row["latitude"]),
            longitude=None if row["longitude"] is None else float(row["longitude"]),
            coordinate_uncertainty_m=(
                None
                if row["coordinate_uncertainty_m"] is None
                else float(row["coordinate_uncertainty_m"])
            ),
            taxon=OperationalTaxon(
                taxon_id=str(row["taxon_id"]),
                external_key=str(row["taxon_external_key"]),
                scientific_name=str(row["scientific_name"]),
                canonical_name=None if row["canonical_name"] is None else str(row["canonical_name"]),
                vernacular_name_raw=(
                    None if row["vernacular_name_raw"] is None else str(row["vernacular_name_raw"])
                ),
                rank=str(row["taxon_rank"]),
            ),
            place=OperationalPlace(
                place_id=str(row["place_id"]),
                name=str(row["place_name"]),
                country_code=str(row["country_code"]),
            ),
            citation=OperationalCitation(
                evidence_id=str(row["evidence_id"]),
                dataset_id=str(row["dataset_id"]),
                dataset_name=str(row["dataset_name"]),
                source_url=str(row["source_url"]),
                dataset_url=str(row["dataset_url"]),
                license_uris=license_uris,
                retrieved_at=str(row["retrieved_at"]),
                source_updated_at=(
                    None if row["source_updated_at"] is None else str(row["source_updated_at"])
                ),
            ),
            media=tuple(
                OperationalMedia(
                    media_id=str(item["media_id"]),
                    media_type=str(item["media_type"]),
                    format=None if item["format"] is None else str(item["format"]),
                    landing_uri=str(item["landing_uri"]),
                    asset_uri=None if item["asset_uri"] is None else str(item["asset_uri"]),
                    creator=None if item["creator"] is None else str(item["creator"]),
                    publisher=None if item["publisher"] is None else str(item["publisher"]),
                    attribution=str(item["attribution"]),
                    license_uri=str(item["license_uri"]),
                )
                for item in (row["media_items"] or [])
                if item is not None
            ),
        )
