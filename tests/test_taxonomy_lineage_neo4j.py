"""Offline contract tests for the AviList Neo4j lineage reader."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.taxonomy_lineage_neo4j import (
    _ACTIVE_CONCEPT_SET_QUERY,
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

    def test_rejects_incomplete_lineage_projection_as_a_controlled_error(self) -> None:
        self.repository._run.side_effect = [
            [{"concept_set_id": "avilist-2025b", "taxonomy_release": "2025b"}],
            [{"lineage_items": [{"taxon_id": "species:anas-zonorhyncha", "rank": "species"}]}],
        ]

        with self.assertRaisesRegex(ValueError, "lineage projection"):
            self.repository.lineage_for_scientific_name("Anas zonorhyncha")

    @staticmethod
    def _complete_lineage_items() -> list[dict[str, str | None]]:
        return [
            {"taxon_id": "order:anseriformes", "rank": "order", "scientific_name": "Anseriformes", "authority": None},
            {"taxon_id": "family:anatidae", "rank": "family", "scientific_name": "Anatidae", "authority": "Leach, 1820"},
            {"taxon_id": "genus:anas", "rank": "genus", "scientific_name": "Anas", "authority": "Linnaeus, 1758"},
            {"taxon_id": "species:anas-zonorhyncha", "rank": "species", "scientific_name": "Anas zonorhyncha", "authority": None},
        ]


if __name__ == "__main__":
    unittest.main()
