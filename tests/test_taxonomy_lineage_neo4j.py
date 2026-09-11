"""Offline contract tests for the AviList Neo4j lineage reader."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.taxonomy_lineage_neo4j import (
    _ACTIVE_CONCEPT_SET_QUERY,
    _LINEAGE_BY_KOREAN_NAME_QUERY,
    _LINEAGE_QUERY,
    Neo4jTaxonomyLineageRepository,
)


class Neo4jTaxonomyLineageRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        # Avoid creating a driver: each test exercises the reader's pure
        # response validation and verifies its calls at the Cypher boundary.
        self.repository = object.__new__(Neo4jTaxonomyLineageRepository)
        self.repository._settings = Neo4jSettings("bolt://localhost:7687", "neo4j", "test-only", "neo4j")
        self.repository._run = Mock()

    def test_uses_bound_exact_case_insensitive_name_in_the_active_concept_set(self) -> None:
        supplied_name = "  AnAs zonorhyncha'; MATCH (n) DETACH DELETE n //  "
        cleaned_name = supplied_name.strip()
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": self._complete_lineage_items()}],
        ]

        lineage = self.repository.lineage_for_scientific_name(supplied_name)

        self.assertEqual(cleaned_name, lineage.query_scientific_name)
        active_call, lineage_call = self.repository._run.call_args_list
        self.assertEqual(_ACTIVE_CONCEPT_SET_QUERY, active_call.args[0])
        self.assertEqual({}, active_call.kwargs)
        self.assertEqual(_LINEAGE_QUERY, lineage_call.args[0])
        self.assertEqual(
            {"concept_set_id": "avilist-2025b", "scientific_name": cleaned_name},
            lineage_call.kwargs,
        )
        self.assertIn("toLower(target.scientific_name) = toLower($scientific_name)", _LINEAGE_QUERY)
        self.assertNotIn(cleaned_name, _LINEAGE_QUERY)
        self.assertIn("MATCH (state:IngestState {id: 'reference-taxonomy'})", _ACTIVE_CONCEPT_SET_QUERY)
        self.assertIn("state.active_concept_set_id", _ACTIVE_CONCEPT_SET_QUERY)

    def test_uses_only_the_active_reference_taxonomy_concept_set(self) -> None:
        self.repository._run.return_value = []

        with self.assertRaisesRegex(ValueError, "Active AviList reference-taxonomy concept set"):
            self.repository.lineage_for_scientific_name("Anas zonorhyncha")

        self.repository._run.assert_called_once_with(_ACTIVE_CONCEPT_SET_QUERY)

    def test_missing_active_release_is_a_controlled_error(self) -> None:
        self.repository._run.return_value = [{"concept_set_id": "avilist-2025b", "taxonomy_release": None}]

        with self.assertRaisesRegex(ValueError, "Active AviList reference-taxonomy release"):
            self.repository.lineage_for_scientific_name("Anas zonorhyncha")

    def test_preserves_cypher_root_to_leaf_order_deterministically(self) -> None:
        items = self._complete_lineage_items()
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": items}],
        ]

        lineage = self.repository.lineage_for_scientific_name("Anas zonorhyncha")

        self.assertEqual(["order", "family", "genus", "species"], [item.rank for item in lineage.items])
        self.assertIn("ORDER BY depth DESC", _LINEAGE_QUERY)
        self.assertIn("ORDER BY target.id", _LINEAGE_QUERY)
        self.assertIn("korean_name: chosenKorean.name", _LINEAGE_QUERY)
        self.assertIn("korean_name_status: chosenKorean.status", _LINEAGE_QUERY)
        self.assertIn("ORDER BY depth DESC, ancestor.id", _LINEAGE_QUERY)

    def test_scientific_name_response_populates_new_fields(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": self._complete_lineage_items()}],
        ]

        lineage = self.repository.lineage_for_scientific_name("  Anas zonorhyncha  ")

        self.assertEqual("Anas zonorhyncha", lineage.query_name)
        self.assertEqual("Anas zonorhyncha", lineage.query_scientific_name)
        self.assertEqual("Anas zonorhyncha", lineage.resolved_query_scientific_name)
        self.assertEqual("scientific_name", lineage.matched_by)
        self.assertEqual("흰뺨검둥오리", lineage.items[-1].korean_name)
        self.assertIsNone(lineage.items[0].korean_name)

    def test_scientific_name_returns_none_when_target_is_not_found(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [],
        ]

        self.assertIsNone(self.repository.lineage_for_scientific_name("Nonexistent species"))

    def test_scientific_name_rejects_incomplete_lineage_projection_as_a_controlled_error(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": [{"taxon_id": "species:anas-zonorhyncha", "rank": "species"}]}],
        ]

        with self.assertRaisesRegex(ValueError, "lineage projection"):
            self.repository.lineage_for_scientific_name("Anas zonorhyncha")

    def test_scientific_name_rejects_a_non_list_projection(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": "not-a-list"}],
        ]

        with self.assertRaisesRegex(ValueError, "Invalid AviList lineage projection"):
            self.repository.lineage_for_scientific_name("Anas zonorhyncha")

    def test_scientific_name_rejects_blank_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "scientific_name must not be blank"):
            self.repository.lineage_for_scientific_name("   ")
        self.repository._run.assert_not_called()

    # -- Korean-name lookup path -------------------------------------------------

    def test_korean_name_uses_bound_exact_case_insensitive_name_in_the_active_concept_set(self) -> None:
        supplied_name = "  흰뺨검둥오리'; MATCH (n) DETACH DELETE n //  "
        cleaned_name = supplied_name.strip()
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"targetScientificName": "Anas zonorhyncha", "lineage_items": self._complete_lineage_items()}],
        ]

        lineage = self.repository.lineage_for_korean_name(supplied_name)

        self.assertEqual("Anas zonorhyncha", lineage.query_scientific_name)
        active_call, lineage_call = self.repository._run.call_args_list
        self.assertEqual(_ACTIVE_CONCEPT_SET_QUERY, active_call.args[0])
        self.assertEqual({}, active_call.kwargs)
        self.assertEqual(_LINEAGE_BY_KOREAN_NAME_QUERY, lineage_call.args[0])
        self.assertEqual(
            {"concept_set_id": "avilist-2025b", "korean_name": cleaned_name},
            lineage_call.kwargs,
        )
        self.assertIn("toLower(vernacular.name) = toLower($korean_name)", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertNotIn(cleaned_name, _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("language: 'ko'", _LINEAGE_BY_KOREAN_NAME_QUERY)

    def test_korean_name_uses_only_the_active_reference_taxonomy_concept_set(self) -> None:
        self.repository._run.return_value = []

        with self.assertRaisesRegex(ValueError, "Active AviList reference-taxonomy concept set"):
            self.repository.lineage_for_korean_name("흰뺨검둥오리")

        self.repository._run.assert_called_once_with(_ACTIVE_CONCEPT_SET_QUERY)

    def test_korean_name_preserves_ancestor_order_and_reports_resolved_scientific_name(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"targetScientificName": "Anas zonorhyncha", "lineage_items": self._complete_lineage_items()}],
        ]

        lineage = self.repository.lineage_for_korean_name("흰뺨검둥오리")

        self.assertEqual(["order", "family", "genus", "species"], [item.rank for item in lineage.items])
        self.assertEqual("흰뺨검둥오리", lineage.query_name)
        self.assertEqual("Anas zonorhyncha", lineage.query_scientific_name)
        self.assertEqual("Anas zonorhyncha", lineage.resolved_query_scientific_name)
        self.assertEqual("korean_name", lineage.matched_by)
        self.assertIn("ORDER BY depth DESC", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("collect(DISTINCT target) AS targets", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("WHERE size(targets) = 1", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("korean_name: chosenKorean.name", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("korean_name_status: chosenKorean.status", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("ORDER BY depth DESC, ancestor.id", _LINEAGE_BY_KOREAN_NAME_QUERY)

    def test_korean_name_returns_none_when_no_licensed_vernacular_name_matches(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [],
        ]

        self.assertIsNone(self.repository.lineage_for_korean_name("존재하지않는이름"))

    def test_korean_name_rejects_missing_resolved_scientific_name_as_a_controlled_error(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"targetScientificName": None, "lineage_items": self._complete_lineage_items()}],
        ]

        with self.assertRaisesRegex(ValueError, "Invalid AviList lineage projection"):
            self.repository.lineage_for_korean_name("흰뺨검둥오리")

    def test_korean_name_rejects_incomplete_lineage_projection_as_a_controlled_error(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [
                {
                    "targetScientificName": "Anas zonorhyncha",
                    "lineage_items": [{"taxon_id": "species:anas-zonorhyncha", "rank": "species"}],
                }
            ],
        ]

        with self.assertRaisesRegex(ValueError, "lineage projection"):
            self.repository.lineage_for_korean_name("흰뺨검둥오리")

    def test_korean_name_rejects_a_non_list_projection(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"targetScientificName": "Anas zonorhyncha", "lineage_items": "not-a-list"}],
        ]

        with self.assertRaisesRegex(ValueError, "Invalid AviList lineage projection"):
            self.repository.lineage_for_korean_name("흰뺨검둥오리")

    def test_korean_name_target_and_ancestor_projection_require_an_allowed_license_chain(self) -> None:
        """Not just a display filter: a Korean name that is not traceable to
        an approved dataset must never resolve a target, and must never be
        projected as an ancestor's korean_name -- both matter, since a name
        planted outside the approved ingest path (or belonging to a
        revoked/paused dataset) must be as invisible as one that was never
        ingested at all."""

        for query, dataset_var in (
            (_LINEAGE_QUERY, "koreanDataset"),
            (_LINEAGE_BY_KOREAN_NAME_QUERY, "matchDataset"),
        ):
            self.assertIn(
                f"-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->({dataset_var}:SourceDataset {{policy_status: 'allowed'}})",
                query,
            )
        # Both queries additionally gate on the *currently active* Korean
        # dataset, not merely "any allowed dataset" -- this is what lets a
        # superseded/removed name stop resolving without an explicit delete.
        self.assertIn("koreanState.active_dataset_id AS koreanDatasetId", _LINEAGE_QUERY)
        self.assertIn("WHERE koreanDataset.id = koreanDatasetId", _LINEAGE_QUERY)
        self.assertIn("koreanState.active_dataset_id AS koreanDatasetId", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("ancestorDataset.id = koreanDatasetId", _LINEAGE_BY_KOREAN_NAME_QUERY)
        # The target-resolution MATCH in the Korean-name query specifically
        # (not just the ancestor projection) must carry the chain, so an
        # untrusted name fails to resolve a target at all rather than
        # resolving one with a hidden/blanked-out name.
        target_match = _LINEAGE_BY_KOREAN_NAME_QUERY.split("collect(DISTINCT target)")[0]
        self.assertIn("MATCH (target)-[:HAS_VERNACULAR_NAME]->(vernacular:VernacularName {language: 'ko'})", target_match)
        self.assertIn(
            "-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(matchDataset:SourceDataset {policy_status: 'allowed'})",
            target_match,
        )
        self.assertIn("matchDataset.id = koreanDatasetId", target_match)

    def test_korean_name_refuses_to_arbitrarily_pick_a_target_when_the_label_is_ambiguous(self) -> None:
        """The real bug this fixes: the same Korean label attached to two
        genuinely different species must not resolve to "whichever taxon
        has the lowest id" -- it must resolve to nothing, exactly like a
        name that matches zero taxa. This is exercised at the Cypher-text
        level here (the actual multi-target collapse happens inside Neo4j);
        the opt-in live integration test in test_n8n_workflows.py exercises
        the real query end-to-end against a live database."""

        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            # A real Neo4j session running _LINEAGE_BY_KOREAN_NAME_QUERY
            # against two distinct matching taxa returns zero rows (the
            # `WHERE size(targets) = 1` guard filters the row out entirely)
            # -- so the mock reproduces exactly that observable contract.
            [],
        ]

        self.assertIsNone(self.repository.lineage_for_korean_name("동명이인후보"))
        self.assertIn("collect(DISTINCT target) AS targets", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("WHERE size(targets) = 1", _LINEAGE_BY_KOREAN_NAME_QUERY)

    def test_korean_name_rejects_blank_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "korean_name must not be blank"):
            self.repository.lineage_for_korean_name("   ")
        self.repository._run.assert_not_called()

    # -- Korean vernacular-name ingest contract (offline) ------------------------

    def test_korean_name_resolves_a_freshly_ingested_mallard_from_the_wikidata_pipeline(self) -> None:
        """Offline contract check, not live proof.

        This does not run the real ``robingraph-korean-vernacular-ingest.json``
        n8n workflow against a live Neo4j instance -- it asserts that the
        response shape the *write* path
        (``scripts/generate_n8n_korean_vernacular_ingest.py``'s
        ``BATCH_STATEMENT``) is designed to produce -- a
        ``VernacularName {language: 'ko', status: 'community-sourced'}`` node
        attached to the matched ``Taxon:BirdTaxon`` by ``HAS_VERNACULAR_NAME``
        -- is exactly what this *read* path already returns correctly. Real
        end-to-end proof requires the opt-in
        ``ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1`` Neo4j contract test in
        ``tests/test_n8n_workflows.py``, or an actual verified NAS run.
        """

        mallard_lineage_with_ingested_korean_name = [
            {
                "taxon_id": "order:anseriformes",
                "rank": "order",
                "scientific_name": "Anseriformes",
                "authority": None,
                "korean_name": None,
            },
            {
                "taxon_id": "family:anatidae",
                "rank": "family",
                "scientific_name": "Anatidae",
                "authority": "Leach, 1820",
                "korean_name": None,
            },
            {
                "taxon_id": "genus:anas",
                "rank": "genus",
                "scientific_name": "Anas",
                "authority": "Linnaeus, 1758",
                "korean_name": None,
            },
            {
                "taxon_id": "species:anas-platyrhynchos",
                "rank": "species",
                "scientific_name": "Anas platyrhynchos",
                "authority": "Linnaeus, 1758",
                # This is the value the Wikidata batch write's
                # `vernacular.name` SET clause would populate: exactly the ko
                # label the SPARQL query returned for Q25348. `status`
                # matches what BATCH_STATEMENT actually writes
                # ('community-sourced'), never claiming this is an official
                # Korean standard name.
                "korean_name": "청둥오리",
                "korean_name_status": "community-sourced",
            },
        ]
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [
                {
                    "targetScientificName": "Anas platyrhynchos",
                    "lineage_items": mallard_lineage_with_ingested_korean_name,
                }
            ],
        ]

        lineage = self.repository.lineage_for_korean_name("청둥오리")

        self.assertEqual("Anas platyrhynchos", lineage.resolved_query_scientific_name)
        self.assertEqual("Anas platyrhynchos", lineage.query_scientific_name)
        self.assertEqual("청둥오리", lineage.query_name)
        self.assertEqual("korean_name", lineage.matched_by)
        self.assertEqual(
            ["order", "family", "genus", "species"], [item.rank for item in lineage.items]
        )
        self.assertEqual("청둥오리", lineage.items[-1].korean_name)
        self.assertEqual("community-sourced", lineage.items[-1].korean_name_status)
        self.assertIsNone(lineage.items[0].korean_name)
        self.assertIsNone(lineage.items[0].korean_name_status)

    def test_korean_name_lookup_returns_none_for_a_species_not_yet_ingested(self) -> None:
        """A species that exists in AviList but has no Wikidata match (or was
        routed to ``VernacularNameCandidate`` instead of written) must 404,
        never fabricate a name. This is the same "current AviList load only
        guarantees English names" gap the Korean vernacular pipeline targets,
        exercised here for a name the write path has not (yet) resolved."""

        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [],
        ]

        self.assertIsNone(self.repository.lineage_for_korean_name("아직적재안된이름"))

    @staticmethod
    def _complete_lineage_items() -> list[dict[str, str | None]]:
        return [
            {
                "taxon_id": "order:anseriformes",
                "rank": "order",
                "scientific_name": "Anseriformes",
                "authority": None,
                "korean_name": None,
            },
            {
                "taxon_id": "family:anatidae",
                "rank": "family",
                "scientific_name": "Anatidae",
                "authority": "Leach, 1820",
                "korean_name": None,
            },
            {
                "taxon_id": "genus:anas",
                "rank": "genus",
                "scientific_name": "Anas",
                "authority": "Linnaeus, 1758",
                "korean_name": None,
            },
            {
                "taxon_id": "species:anas-zonorhyncha",
                "rank": "species",
                "scientific_name": "Anas zonorhyncha",
                "authority": None,
                "korean_name": "흰뺨검둥오리",
            },
        ]


if __name__ == "__main__":
    unittest.main()
