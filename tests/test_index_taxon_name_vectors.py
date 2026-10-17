"""Explicit TEST-only index command boundary; repository writes tested separately."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('index_names_command', Path(__file__).parents[1] / 'scripts/index_taxon_name_vectors.py')
command = importlib.util.module_from_spec(spec)
spec.loader.exec_module(command)


class NameVectorIndexCommandTests(unittest.TestCase):
    def test_non_test_target_is_rejected_before_database_configuration(self):
        for target in ('', 'prod', 'legacy'):
            with patch.dict(command.os.environ, {'ROBINGRAPH_DEPLOY_TARGET': target}), patch.object(command, 'IngestionStore') as store:
                with self.assertRaises(SystemExit):
                    command.main(['--apply'])
                store.assert_not_called()

    def test_default_is_dry_run_and_apply_is_explicit(self):
        for arguments, dry_run in (([], True), (['--apply'], False)):
            active = SimpleNamespace(cursor={'concept_set_id': 'active', 'taxonomy_release': 'release'})
            store = Mock()
            store.active_release_context.return_value = active
            inventory = [{'taxon_id': 'duck', 'scientific_name': 'Anas example', 'display_name': '검토명', 'text': '검토명'}]
            with patch.dict(command.os.environ, {'ROBINGRAPH_DEPLOY_TARGET': 'test'}), \
                    patch.object(command, 'IngestionStore', return_value=store), \
                    patch.object(command.PostgresSettings, 'from_environment'), \
                    patch.object(command.Neo4jSettings, 'from_environment'), \
                    patch.object(command, 'Neo4jTaxonomyLineageRepository') as taxonomy, \
                    patch.object(command, 'JinaEmbeddingClient') as client, \
                    patch('robingraph.retrieval.taxon_name_vectors_neo4j.Neo4jTaxonNameVectorRepository') as repository:
                taxonomy.return_value.reviewed_name_candidates.return_value = inventory
                repository.return_value.index_names.return_value = {'dry_run': dry_run}
                with patch('builtins.print'):
                    command.main(arguments)
                repository.return_value.index_names.assert_called_once_with(
                    inventory, client.from_env.return_value, ('active', 'release'), dry_run=dry_run)
