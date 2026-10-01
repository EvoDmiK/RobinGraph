import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon
from robingraph.retrieval.species_profile import (
    CONSERVATION_LABELS, create_species_flow, read_conservation, read_traits,
    species_summary, _photo, _licensed_images,
)

LINEAGE = TaxonomyLineage('Anas platyrhynchos', 'AviList', 'v2025b', 'concept', (
    LineageTaxon('t', 'species', 'Anas platyrhynchos', None, '청둥오리'),))


class SpeciesProfileTest(unittest.TestCase):
    def test_conservation_normalizes_only_known_codes_with_snapshot_provenance(self):
        repository = Mock()
        source = {'source_name':'AviList global avian checklist',
                  'source_url':'https://www.avilist.org/snapshot-v2025b.xlsx',
                  'source_release':'v2025b'}
        for raw, expected in [(code, code) for code in CONSERVATION_LABELS] + [
                (' lc ', 'LC'), ('CR (PE)', 'CR'), ('CR (PEW)', 'CR'),
                ('rare', None), ('LC/NT', None), ('CR (maybe)', None),
                ('Least Concern', None), ('', None), (None, None),
                (123, None), (['LC'], None), ({'category':'LC'}, None)]:
            with self.subTest(raw=raw):
                repository._run.return_value = [{'category_raw':raw, **source}]
                result = read_conservation(repository, LINEAGE)
                self.assertEqual(expected, result['category'])
                self.assertEqual(raw if isinstance(raw, str) else None, result['category_raw'])
                self.assertEqual(CONSERVATION_LABELS.get(expected, '확인되지 않음'), result['label'])
                for key, value in source.items():
                    self.assertEqual(value, result[key])
                self.assertNotIn('assessment_date', result)
        query = repository._run.call_args.args[0]
        self.assertIn('t.source_release=$taxonomy_release', query)
        self.assertIn('s.version=$taxonomy_release', query)
        self.assertIn("policy_status:'allowed'", query)
        self.assertIn('s.snapshot_uri AS source_url', query)
        self.assertEqual({'taxon_id':'t', 'concept_set_id':'concept', 'taxonomy_release':'v2025b'},
                         repository._run.call_args.kwargs)
        for rows in ([], [{**source, 'category_raw':'LC', 'source_release':'old'}],
                     [{**source, 'category_raw':'LC', 'source_url':None}],
                     [{**source, 'category_raw':'LC', 'source_url':'javascript:bad'}],
                     [{'category_raw':'LC'}], [{**source}, {**source}]):
            repository._run.return_value = rows
            self.assertIsNone(read_conservation(repository, LINEAGE)['category'])

    def test_summary_is_brief_and_uses_only_attributed_ecology_fields(self):
        def trait(name, display, **extra):
            return {'name':name, 'display':display, 'source_name':'AVONET',
                    'source_url':'https://example.com/avonet', **extra}
        summary = species_summary({'korean_name':'청둥오리'}, [
            trait('habitat', '습지'), trait('primary_lifestyle', '수생'),
            trait('diet_category', '잡식'), trait('body_mass', '843.42', unit='g'),
            trait('nocturnal', '예'), {'name':'habitat', 'display':'사막'},
        ])
        self.assertIn('청둥오리', summary)
        self.assertIn('습지', summary)
        self.assertIn('수생', summary)
        self.assertIn('잡식', summary)
        self.assertIn('843.42 g', summary)
        self.assertNotIn('평균', summary)
        self.assertNotIn('야행', summary)
        self.assertNotIn('사막', summary)
        self.assertEqual(3, len(summary.split('. ')))
        self.assertIn('아직 확인하지 못했습니다', species_summary({}, []))

    def test_independent_source_failures_and_legacy_positional_photos(self):
        conservation = Mock(side_effect=RuntimeError('secret database'))
        flow = create_species_flow(lambda _: LINEAGE,
                                   lambda _: [{'name':'habitat', 'display':'습지',
                                               'source_name':'AVONET', 'source_url':'https://example.com'}],
                                   lambda _: [], conservation)
        profile = flow.invoke('청둥오리')
        self.assertIsNone(profile['conservation']['category'])
        self.assertIn('습지', profile['summary'])
        self.assertNotIn('secret', str(profile))
        self.assertTrue(profile['warnings'])
        legacy = create_species_flow(lambda _: LINEAGE, Mock(side_effect=TimeoutError), lambda _: [])
        profile = legacy.invoke('청둥오리')
        self.assertEqual([], profile['traits'])
        self.assertIsNone(profile['conservation']['category'])
        self.assertIn('아직 확인하지 못했습니다', profile['summary'])

    def test_profile_endpoint_exposes_snapshot_conservation_and_sourced_summary(self):
        repository = Mock()
        repository._run.return_value = [{'category_raw':'CR (PE)',
            'source_name':'AviList global avian checklist',
            'source_url':'https://www.avilist.org/snapshot-v2025b.xlsx',
            'source_release':'v2025b'}]
        flow = create_species_flow(lambda _: LINEAGE,
            lambda _: [{'name':'habitat', 'display':'습지', 'source_name':'AVONET',
                        'source_url':'https://example.com/avonet'}],
            photos=lambda _: [], conservation=lambda lineage: read_conservation(repository, lineage))
        client = TestClient(create_app(species_profile_handler=flow.invoke))
        profile = client.get('/v1/taxa/profile?name=청둥오리').json()
        self.assertEqual('CR', profile['conservation']['category'])
        self.assertEqual('CR (PE)', profile['conservation']['category_raw'])
        self.assertEqual('v2025b', profile['conservation']['source_release'])
        self.assertEqual('청둥오리의 서식 환경은 습지입니다.', profile['summary'])
        chat = client.post('/v1/chat', json={'question':'청둥오리에 대해 알려줘.'}).json()
        self.assertEqual(profile['summary'], chat['answer_text'])

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

    def test_category_values_are_korean_without_changing_source_values(self):
        context = NS(cursor={'taxonomy_concept_set_id':'concept', 'taxonomy_release':'v2025b'},
                     dataset=NS(id='d', name='AVONET'), release=NS(release_key='v7'))
        store = Mock()
        store.active_release_context.side_effect = [None, context]
        categories = {
            'diet_category': ['PlantSeed', 'Omnivore', 'FruiNect', 'Invertebrate', 'VertFishScav'],
            'habitat': ['Forest', 'Shrubland', 'Woodland', 'Grassland', 'Rock', 'Wetland',
                        'Human Modified', 'Coastal', 'Marine', 'Riverine', 'Desert'],
            'primary_lifestyle': ['Insessorial', 'Aerial', 'Terrestrial', 'Generalist', 'Aquatic'],
        }
        repository = Mock()
        repository._run.return_value = [
            {'claim': {'trait_name': name, 'value_text': value, 'dataset_id':'d', 'source_release':'v7'},
             'source_url':'https://example.com', 'citation':'AVONET'}
            for name, values in categories.items() for value in values
        ]
        traits = read_traits(repository, store, LINEAGE)
        self.assertEqual(21, len(traits))
        for trait in traits:
            self.assertIn(trait['value'], categories[trait['name']])
            self.assertRegex(trait['display'], r'[가-힣]')
            self.assertNotRegex(trait['display'], r'[A-Za-z]')
        self.assertEqual('무척추동물', next(t['display'] for t in traits if t['value'] == 'Invertebrate'))
        self.assertEqual('척추동물·물고기·사체', next(t['display'] for t in traits if t['value'] == 'VertFishScav'))

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
