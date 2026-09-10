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
        self.assertIn("min(koreanName.name) AS korean_name", _LINEAGE_QUERY)
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
        self.assertIn("ORDER BY target.id", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("WITH DISTINCT target", _LINEAGE_BY_KOREAN_NAME_QUERY)
        self.assertIn("min(koreanName.name) AS korean_name", _LINEAGE_BY_KOREAN_NAME_QUERY)
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

    def test_korean_name_rejects_blank_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "korean_name must not be blank"):
            self.repository.lineage_for_korean_name("   ")
        self.repository._run.assert_not_called()

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
