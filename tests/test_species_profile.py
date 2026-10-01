import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon
from robingraph.retrieval.species_profile import create_species_flow, read_traits, _photo, _licensed_images

LINEAGE = TaxonomyLineage('Anas platyrhynchos', 'AviList', 'v2025b', 'concept', (
    LineageTaxon('t', 'species', 'Anas platyrhynchos', None, '청둥오리'),))


class SpeciesProfileTest(unittest.TestCase):
    def test_langchain_profile_and_partial_photo_outage_through_api(self):
        photos = Mock(side_effect=TimeoutError)
        flow = create_species_flow(lambda name: LINEAGE if name == '청둥오리' else None,
                                   lambda lineage: [{'label':'체중', 'display':'843.42'}], photos)
        client = TestClient(create_app(species_profile_handler=flow.invoke))
        data = client.get('/v1/taxa/profile', params={'name':'청둥오리'}).json()
        self.assertEqual('청둥오리', data['taxon']['korean_name'])
        self.assertEqual('843.42', data['traits'][0]['display'])
        self.assertEqual([], data['images'])
        self.assertTrue(data['warnings'])
        self.assertEqual(404, client.get('/v1/taxa/profile?name=없는새').status_code)
        self.assertEqual(422, client.get('/v1/taxa/profile?name=%20').status_code)
        self.assertEqual(200, client.get('/birds').status_code)
        self.assertEqual(200, client.get('/static/birds.js').status_code)

    def test_trait_reader_pins_allowed_release_and_evidence_identity(self):
        context = NS(cursor={'taxonomy_concept_set_id':'concept', 'taxonomy_release':'v2025b'},
                     dataset=NS(id='d',name='AVONET'), release=NS(release_key='v7'))
        store = Mock()
        store.active_release_context.side_effect = [None, context]
        repository = Mock()
        repository._run.return_value = [
            {'claim':{'trait_name':'body_mass','value_num':843.42, 'unit':'g',
                      'dataset_id':'d', 'source_release':'v7'}, 'source_url':'https://example.com', 'citation':'AVONET'},
            {'claim':{'trait_name':'body_mass','value_num':999, 'dataset_id':'d', 'source_release':'old'},
             'source_url':'https://example.com', 'citation':'stale'},
        ]
        data = read_traits(repository, store, LINEAGE)
        self.assertEqual(1, len(data))
        self.assertEqual('체중', data[0]['label'])
        query = repository._run.call_args.args[0]
        self.assertIn('e.source_record_id=c.source_record_id', query)
        self.assertIn("policy_status:'allowed'", query)
        self.assertEqual('t', repository._run.call_args.kwargs['taxon_id'])
        context.cursor['taxonomy_release'] = 'old'
        repository.reset_mock()
        store.active_release_context.side_effect = [None, context]
        self.assertEqual([], read_traits(repository, store, LINEAGE))
        repository._run.assert_not_called()

    def test_photos_require_per_file_license_creator_and_safe_image_host(self):
        def metadata(**values):
            return {k:{'value':v} for k,v in values.items()}
        info = {'mime':'image/jpeg','thumburl':'https://thumb.wikimedia.org/bird.jpg',
                'descriptionurl':'https://commons.wikimedia.org/wiki/File:Bird.jpg',
                'extmetadata':metadata(License='cc-by-2.0', LicenseShortName='CC BY 2.0',
                                       LicenseUrl='https://creativecommons.org/licenses/by/2.0',
                                       Artist='<a href="x">Photographer</a>')}
        photo = _photo(info)
        self.assertEqual('Photographer', photo['creator'])
        self.assertEqual('CC BY 2.0', photo['license_name'])
        info['extmetadata']['License']['value'] = 'cc-by-nc-4.0'
        self.assertIsNone(_photo(info))
        info['extmetadata']['License']['value'] = 'cc-by-2.0'
        info['thumburl'] = 'https://evil.example/bird.jpg'
        self.assertIsNone(_photo(info))
        info['thumburl'] = 'https://thumb.wikimedia.org/bird.jpg'
        info['extmetadata']['Artist']['value'] = ''
        self.assertIsNone(_photo(info))

    def test_ambiguous_species_does_not_pick_a_photo(self):
        _licensed_images.cache_clear()
        bindings = [{'item':{'value':'Q1'},'image':{'value':'x'}}, {'item':{'value':'Q2'},'image':{'value':'y'}}]
        with patch('robingraph.retrieval.species_profile._json_get', return_value={'results':{'bindings':bindings}}):
            self.assertEqual([], _licensed_images('Ambiguous bird', 1))

    def test_profile_outage_does_not_expose_database_details(self):
        client = TestClient(create_app(species_profile_handler=Mock(side_effect=RuntimeError('secret database path'))))
        response = client.get('/v1/taxa/profile?name=청둥오리')
        self.assertEqual(503, response.status_code)
        self.assertNotIn('secret', response.text)
