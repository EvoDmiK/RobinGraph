"""Active graph boundaries of the reviewed Korean vector name inventory."""
import unittest
from unittest.mock import Mock, patch

from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository


class TaxonNameCatalogTests(unittest.TestCase):
    def test_new_taxonomy_release_does_not_reuse_old_korean_inventory(self):
        repo = object.__new__(Neo4jTaxonomyLineageRepository)
        repo._active_concept_set = lambda: ('changed', 'v9999')
        repo._run = Mock()
        self.assertEqual([], repo.reviewed_name_candidates())
        repo._run.assert_not_called()

    def test_inventory_is_bound_to_reviewed_identity_and_active_graph(self):
        repo = object.__new__(Neo4jTaxonomyLineageRepository)
        repo._active_concept_set = lambda: ('rg:concept-set:avilist-v2025b', 'v2025b')
        repo._run = Mock(return_value=[])
        names = {'a': {'status': 'source-reference', 'name': '확인명',
                       'scientific_name': 'Anas example', 'english_name': 'Example duck'},
                 'b': {'status': 'unreviewed', 'name': '추정명'}}
        with patch('robingraph.retrieval.taxonomy_lineage_neo4j.sourced_korean_names', return_value=names):
            repo.reviewed_name_candidates()
        query = repo._run.call_args_list[0].args[0]
        params = repo._run.call_args_list[0].kwargs
        self.assertEqual(['a'], [item['taxon_id'] for item in params['names']])
        self.assertEqual('v2025b', params['release'])
        self.assertIn("policy_status:'allowed'", query)
        self.assertIn('en.dataset_id=t.dataset_id', query)
        self.assertIn('reviewed.scientific_name', query)
