from __future__ import annotations

import unittest
from unittest.mock import Mock

from robingraph.retrieval.operational import OperationalObservationQuery
from robingraph.retrieval.operational_neo4j import Neo4jOperationalObservationRepository


def observation_row(*, sensitivity: str = "public") -> dict[str, object]:
    public = sensitivity == "public"
    return {
        "observation_id": "gbif-observation:123",
        "occurrence_id": "123",
        "observed_at": "2026-09-07T10:00:00Z",
        "count": 2,
        "basis": "human_observation",
        "sensitivity": sensitivity,
        "latitude": 37.5 if public else None,
        "longitude": 127.0 if public else None,
        "coordinate_uncertainty_m": 25.0 if public else None,
        "taxon_id": "gbif-taxon:2498349",
        "taxon_external_key": "2498349",
        "scientific_name": "Anas zonorhyncha",
        "canonical_name": "Anas zonorhyncha",
        "vernacular_name_raw": "Eastern Spot-billed Duck",
        "taxon_rank": "species",
        "place_id": "gbif-place:KR:Seoul",
        "place_name": "Seoul",
        "country_code": "KR",
        "evidence_id": "gbif-evidence:123",
        "dataset_id": "gbif-dataset:dataset-1",
        "dataset_name": "GBIF occurrence dataset",
        "source_url": "https://api.gbif.org/v1/occurrence/123",
        "dataset_url": "https://www.gbif.org/dataset/dataset-1",
        "license_uris": ["https://creativecommons.org/licenses/by/4.0/"],
        "retrieved_at": "2026-09-08T00:00:00Z",
        "source_updated_at": "2026-09-07T12:00:00Z",
        "media_items": [
            {
                "media_id": "gbif-media:123",
                "media_type": "stillimage",
                "format": "image/jpeg",
                "landing_uri": "https://example.invalid/media/123",
                "asset_uri": "https://example.invalid/media/123.jpg",
                "creator": "Observer",
                "publisher": "Publisher",
                "attribution": "Observer / CC BY 4.0",
                "license_uri": "https://creativecommons.org/licenses/by/4.0/",
            }
        ],
    }


class OperationalNeo4jRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Neo4jOperationalObservationRepository.__new__(
            Neo4jOperationalObservationRepository
        )
        self.repository._run = Mock(return_value=[observation_row()])

    def test_filters_are_bound_and_result_carries_operational_provenance(self) -> None:
        results = self.repository.search_observations(
            OperationalObservationQuery(
                taxon_key=" 2498349 ",
                scientific_name=" Anas ",
                place=" Seoul ",
                observed_from="2026-09-01",
                observed_to="2026-09-08",
                limit=10,
                offset=5,
            )
        )
        query = self.repository._run.call_args.args[0]
        parameters = self.repository._run.call_args.kwargs
        self.assertIn("$scientific_name", query)
        self.assertIn("dataset.policy_status = 'allowed'", query)
        self.assertIn("license.policy_status = 'allowed'", query)
        self.assertIn("media.license_uri IN $allowed_media_license_uris", query)
        self.assertIn("ORDER BY source.retrieved_at DESC, source.id DESC", query)
        self.assertIn("})[0] AS citation", query)
        self.assertNotIn("2498349", query)
        self.assertEqual("2498349", parameters["taxon_key"])
        self.assertEqual("Anas", parameters["scientific_name"])
        self.assertEqual("Seoul", parameters["place"])
        self.assertIn(
            "https://creativecommons.org/licenses/by/4.0/",
            parameters["allowed_media_license_uris"],
        )
        self.assertEqual(10, parameters["limit"])
        self.assertEqual("gbif-evidence:123", results[0].citation.evidence_id)
        self.assertEqual("public", results[0].coordinate_disclosure)
        self.assertEqual("gbif-media:123", results[0].media[0].media_id)

    def test_generalized_coordinates_are_never_returned_by_the_query_contract(self) -> None:
        self.repository._run.return_value = [observation_row(sensitivity="generalized")]
        result = self.repository.search_observations(OperationalObservationQuery())[0]
        query = self.repository._run.call_args.args[0]
        self.assertIn("CASE WHEN observation.sensitivity = 'public'", query)
        self.assertEqual("withheld", result.coordinate_disclosure)
        self.assertIsNone(result.latitude)
        self.assertIsNone(result.longitude)

    def test_invalid_bounds_fail_before_querying_neo4j(self) -> None:
        for query in (
            OperationalObservationQuery(limit=0),
            OperationalObservationQuery(limit=101),
            OperationalObservationQuery(offset=-1),
            OperationalObservationQuery(scientific_name="  "),
            OperationalObservationQuery(observed_from="2026-09-08", observed_to="2026-09-01"),
        ):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.repository.search_observations(query)
        self.repository._run.assert_not_called()

    def test_missing_allowed_license_fails_closed(self) -> None:
        row = observation_row()
        row["license_uris"] = []
        self.repository._run.return_value = [row]
        with self.assertRaisesRegex(ValueError, "no allowed license"):
            self.repository.search_observations(OperationalObservationQuery())


if __name__ == "__main__":
    unittest.main()
