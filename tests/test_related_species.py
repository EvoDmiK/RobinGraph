import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from robingraph.api.app import create_app
from robingraph.retrieval.related_species import related_species, RELATED_QUERY
from robingraph.retrieval.species_profile import SpeciesNotFoundError
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon

LINEAGE = TaxonomyLineage('Anas platyrhynchos', 'AviList', 'v2025b', 'active', (
    LineageTaxon('family', 'family', 'Anatidae', None),
    LineageTaxon('genus', 'genus', 'Anas', None),
    LineageTaxon('mallard', 'species', 'Anas platyrhynchos', None, '청둥오리')))
SOURCE = {'source_name':'AviList', 'source_url':'https://www.avilist.org/snapshot.xlsx'}


def peer(index):
    return {'taxon':{'taxon_id':f'p{index}', 'rank':'species',
                     'scientific_name':f'Anas species{index}', 'authority':None, 'korean_name':f'한국어새{index}'}, **SOURCE}


class RelatedSpeciesTest(unittest.TestCase):
    def test_scoped_read_returns_bounded_groups_with_snapshot_and_no_evolution_claim(self):
        repo = Mock()
        repo._korean_dataset_id.return_value = 'ko-active'
        repo._run.side_effect = [[SOURCE], [peer(i) for i in range(13)], []]
        result = related_species(repo, lambda _: LINEAGE, '청둥오리')
        self.assertEqual('v2025b', result['taxonomy_release'])
        genus, family = result['groups']
        self.assertEqual(12, len(genus['items']))
        self.assertTrue(genus['has_more'])
        self.assertEqual([], family['items'])
        self.assertEqual(SOURCE['source_url'], family['source_url'])
        self.assertIn('뜻하지 않습니다', result['note'])
        calls = repo._run.call_args_list
        self.assertEqual('genus', calls[1].kwargs['parent_id'])
        self.assertIsNone(calls[1].kwargs['excluded_genus'])
        self.assertEqual('genus', calls[2].kwargs['excluded_genus'])
        for call in calls[1:]:
            self.assertEqual('active', call.kwargs['concept_set_id'])
            self.assertEqual('v2025b', call.kwargs['taxonomy_release'])
            self.assertEqual('ko-active', call.kwargs['korean_dataset_id'])
        self.assertIn('all(link IN relationships(path)', RELATED_QUERY)
        self.assertIn('all(node IN nodes(path)', RELATED_QUERY)
        self.assertIn('node:Taxon AND node:BirdTaxon', RELATED_QUERY)
        self.assertIn('peer.id <> $target_id', RELATED_QUERY)
        self.assertIn("name.name =~ '.*[가-힣].*'", RELATED_QUERY)
        self.assertLess(RELATED_QUERY.index('name.dataset_id=$korean_dataset_id'), RELATED_QUERY.index('LIMIT 13'))
        self.assertNotIn('OPTIONAL MATCH', RELATED_QUERY)
        self.assertEqual('korean_names_only', result['name_filter'])
        self.assertTrue(all(item['korean_name'] for item in genus['items']))

    def test_missing_species_and_revoked_or_invalid_provenance_fail_closed(self):
        repo = Mock()
        with self.assertRaises(SpeciesNotFoundError):
            related_species(repo, lambda _: None, 'unknown')
        repo._run.assert_not_called()
        for sources in ([], [SOURCE, SOURCE], [{'source_name':'AviList'}],
                        [{'source_name':'AviList', 'source_url':'javascript:bad'}]):
            repo._run.return_value = sources
            with self.assertRaises(ValueError):
                related_species(repo, lambda _: LINEAGE, 'mallard')

    def test_endpoint_validation_and_safe_outage(self):
        handler = Mock(return_value={'groups':[]})
        client = TestClient(create_app(related_species_handler=handler))
        self.assertEqual(200, client.get('/v1/taxa/related', params={'name':' 청둥오리 '}).status_code)
        handler.assert_called_once_with('청둥오리')
        self.assertEqual(422, client.get('/v1/taxa/related?name=%20').status_code)
        self.assertEqual(422, client.get('/v1/taxa/related', params={'name':'a'*201}).status_code)
        handler.side_effect = SpeciesNotFoundError()
        self.assertEqual(404, client.get('/v1/taxa/related?name=unknown').status_code)
        handler.side_effect = RuntimeError('secret DB password')
        response = client.get('/v1/taxa/related?name=mallard')
        self.assertEqual(503, response.status_code)
        self.assertNotIn('secret', response.text)
        self.assertEqual(503, TestClient(create_app()).get('/v1/taxa/related?name=mallard').status_code)
