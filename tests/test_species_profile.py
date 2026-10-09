from dataclasses import replace
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon
from robingraph.retrieval.species_profile import (
    CONSERVATION_LABELS, create_species_flow, read_conservation, read_traits,
    species_summary, trait_display, PhotoLookup, _photo, _licensed_images,
)

LINEAGE = TaxonomyLineage('Anas platyrhynchos', 'AviList', 'v2025b', 'concept', (
    LineageTaxon('t', 'species', 'Anas platyrhynchos', None, '청둥오리'),))


class SpeciesProfileTest(unittest.TestCase):
    def test_deferred_card_does_not_call_external_photos_or_notes(self):
        photos, notes = Mock(), Mock()
        flow = create_species_flow(lambda _: LINEAGE,
            lambda _: [{'name':'habitat', 'display':'습지', 'source_name':'AVONET',
                        'source_url':'https://example.com/avonet'}],
            photos=photos, notes=notes, include_enrichment=False)
        profile = flow.invoke('청둥오리')
        photos.assert_not_called()
        notes.assert_not_called()
        self.assertTrue(profile['enrichment_pending'])
        self.assertEqual('pending', profile['photo_availability']['status'])
        self.assertEqual('t', profile['taxon']['taxon_id'])
        self.assertEqual('concept', profile['lineage']['concept_set_id'])
        self.assertIn('습지', profile['summary'])

    def test_deferred_chat_skips_recommendations_and_preserves_legacy_full_response(self):
        basic = create_species_flow(lambda _: LINEAGE, lambda _: [], include_enrichment=False)
        full = Mock(return_value={'taxon':{'rank':'species'}, 'summary':'전체 카드', 'lineage':{}, 'warnings':[]})
        similar = Mock(return_value={})
        client = TestClient(create_app(species_profile_handler=full,
            species_basic_profile_handler=basic.invoke, similar_species_handler=similar))
        early = client.post('/v1/chat', json={'question':'청둥오리', 'intent':'profile', 'defer_enrichment':True})
        self.assertEqual(200, early.status_code)
        self.assertTrue(early.json()['result']['profile']['enrichment_pending'])
        self.assertIsNone(early.json()['result']['similar_species'])
        full.assert_not_called()
        similar.assert_not_called()
        legacy = client.post('/v1/chat', json={'question':'청둥오리', 'intent':'profile'}).json()
        self.assertEqual('전체 카드', legacy['answer_text'])
        full.assert_called_once()
        similar.assert_called_once()

    def test_deferred_subspecies_returns_verified_list_before_full_profile(self):
        basic = create_species_flow(lambda _: LINEAGE, lambda _: [], include_enrichment=False)
        full, similar = Mock(), Mock()
        router = Mock()
        router.classify.return_value = NS(label='subspecies', failure=None)
        data = {'parent_species':{'taxon':{'taxon_id':'t'}}, 'concept_set_id':'concept',
                'taxonomy_release':'v2025b', 'subspecies':[{'taxon_id':'child'}], 'has_more':False}
        client = TestClient(create_app(jev_router=router, species_profile_handler=full,
            species_basic_profile_handler=basic.invoke, similar_species_handler=similar,
            subspecies_handler=lambda _: data))
        result = client.post('/v1/chat', json={'question':'청둥오리 아종 알려줘', 'defer_enrichment':True}).json()
        self.assertEqual('answer', result['disposition'])
        self.assertEqual(data, result['result']['subspecies'])
        full.assert_not_called()
        similar.assert_not_called()
        # An active context mismatch still fails closed on the fast path.
        data['taxonomy_release'] = 'stale'
        changed = client.post('/v1/chat', json={'question':'청둥오리 아종 알려줘', 'defer_enrichment':True}).json()
        self.assertEqual('abstain', changed['disposition'])

    def test_deferred_discovery_returns_full_description_without_optional_relation_queries(self):
        basic, similar, relations, ecological, subspecies = Mock(), Mock(), Mock(), Mock(), Mock()
        notes = Mock(return_value={
            'appearance': [{'text': '부리 끝이 노랗습니다.', 'source_name': 'Wikipedia',
                            'source_url': 'https://en.wikipedia.org/w/index.php?oldid=1'}],
            'fun_facts': [{'text': '무리를 이루어 생활합니다.', 'source_name': 'Wikipedia',
                           'source_url': 'https://en.wikipedia.org/w/index.php?oldid=1'}]})
        measurements = [{'name': name, 'display': value, 'unit': 'mm',
                         'source_name': 'AVONET', 'source_url': 'https://example.com/avonet'}
                        for name, value in [('beak_length_culmen', '59.9'), ('wing_length', '268.2'), ('tail_length', '87.2')]]
        full = create_species_flow(lambda _: LINEAGE, lambda _: measurements, photos=lambda _: [], notes=notes)
        client = TestClient(create_app(species_profile_handler=full.invoke,
            species_basic_profile_handler=basic, similar_species_handler=similar,
            name_relations_handler=relations, ecological_relations_handler=ecological,
            subspecies_handler=subspecies))
        response = client.post('/v1/chat', json={
            'question': 'Anas platyrhynchos', 'intent': 'profile', 'defer_discovery': True})
        self.assertEqual(200, response.status_code)
        result = response.json()['result']
        self.assertFalse(result['profile'].get('enrichment_pending', False))
        text = str(result['profile']['sections'])
        self.assertIn('부리 끝이 노랗습니다.', text)
        self.assertIn('무리를 이루어 생활합니다.', text)
        for value in ('59.9 mm', '268.2 mm', '87.2 mm'):
            self.assertIn(value, text)
        self.assertIsNone(result['similar_species'])
        notes.assert_called_once()
        for handler in (basic, similar, relations, ecological, subspecies):
            handler.assert_not_called()

    def test_deferred_discovery_does_not_defer_explicit_subspecies_question(self):
        full = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=lambda _: [])
        router = Mock()
        router.classify.return_value = NS(label='subspecies', failure=None)
        data = {'parent_species': {'taxon': {'taxon_id': 't'}}, 'concept_set_id': 'concept',
                'taxonomy_release': 'v2025b', 'subspecies': [{'taxon_id': 'child'}], 'has_more': False}
        subspecies, similar = Mock(return_value=data), Mock()
        client = TestClient(create_app(jev_router=router, species_profile_handler=full.invoke,
            subspecies_handler=subspecies, similar_species_handler=similar))
        response = client.post('/v1/chat', json={
            'question': '청둥오리 아종 알려줘', 'defer_discovery': True}).json()
        self.assertEqual('answer', response['disposition'])
        self.assertEqual(data, response['result']['subspecies'])
        subspecies.assert_called_once()
        similar.assert_not_called()

    def test_deferred_appearance_question_still_loads_its_requested_sourced_notes(self):
        basic = Mock()
        notes = Mock(return_value={'appearance':[{'text':'녹색 머리가 있습니다.',
            'source_name':'Wikipedia', 'source_url':'https://en.wikipedia.org/w/index.php?oldid=1'}], 'fun_facts':[]})
        full = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=lambda _: [], notes=notes)
        client = TestClient(create_app(species_profile_handler=full.invoke, species_basic_profile_handler=basic))
        result = client.post('/v1/chat', json={'question':'청둥오리 외관 알려줘', 'defer_enrichment':True}).json()
        self.assertEqual('answer', result['disposition'])
        self.assertIn('녹색 머리', result['answer_text'])
        notes.assert_called_once()
        basic.assert_not_called()

    def test_conservation_normalizes_only_known_codes_with_snapshot_provenance(self):
        repository = Mock()
        source = {'source_name':'AviList global avian checklist',
                  'source_url':'https://www.avilist.org/snapshot-v2025b.xlsx',
                  'source_release':'v2025b', 'source_id':'avilist-v2025b'}
        for raw, expected in [(code, code) for code in CONSERVATION_LABELS] + [
                (' lc ', 'LC'), ('CR (PE)', 'CR'), ('CR (PEW)', 'CR'),
                ('rare', None), ('LC/NT', None), ('CR (maybe)', None),
                ('Least Concern', None), ('', None), (None, None),
                (123, None), (['LC'], None), ({'category':'LC'}, None)]:
            with self.subTest(raw=raw):
                repository._run.return_value = [{'category_raw':raw, **source}]
                result = read_conservation(repository, LINEAGE)
                self.assertEqual(None if expected == 'NE' else expected, result['category'])
                self.assertEqual(raw if isinstance(raw, str) else None, result['category_raw'])
                # Unlinked taxonomy NE is shown as unresolved, never as genuine IUCN 미평가.
                label = '평가 연결 확인 필요' if expected == 'NE' else CONSERVATION_LABELS.get(expected, '확인되지 않음')
                self.assertEqual(label, result['label'])
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

    def test_snapshot_assessment_boundary_and_source_identity(self):
        source = {'source_name':'AviList global avian checklist',
                  'source_url':'https://explore.avilist.org/data/avilist-2025b.json',
                  'source_release':'v2025b', 'source_id':'avilist-v2025b',
                  'snapshot_sha256':'a' * 64,
                  'assessment_reference_url':'https://datazone.birdlife.org/species/factsheet/mallard-anas-platyrhynchos'}
        repository = Mock()
        repository._run.return_value = [{'category_raw':'NE', **source}]
        result = read_conservation(repository, LINEAGE)
        self.assertIsNone(result['category'])
        self.assertEqual('NE', result['category_raw'])
        # Raw NE is preserved, but the label never claims a genuine IUCN "미평가".
        self.assertEqual('평가 연결 확인 필요', result['label'])
        self.assertNotEqual('미평가', result['label'])
        self.assertEqual('taxonomy_snapshot', result['evidence_kind'])
        self.assertEqual('needs_review', result['assessment_status'])
        self.assertFalse(result['independently_verified'])
        self.assertIn('단정할 수 없습니다', result['quality_note'])
        self.assertEqual('a' * 64, result['snapshot_sha256'])
        # A contradictory link must never imply that NE has a matched assessment.
        self.assertNotIn('assessment_reference_url', result)
        for raw in ('DD', 'LC'):
            repository._run.return_value = [{'category_raw':raw, **source}]
            self.assertNotEqual('평가 연결 확인 필요', read_conservation(repository, LINEAGE)['label'])
        for raw in (' ne ', 'Ne'):
            repository._run.return_value = [{'category_raw':raw, **source}]
            ne = read_conservation(repository, LINEAGE)
            self.assertEqual((None, raw, 'needs_review'), (ne['category'], ne['category_raw'], ne['assessment_status']))
            self.assertEqual('평가 연결 확인 필요', ne['label'])
        repository._run.return_value = [{'category_raw':'LC', **source}]
        self.assertEqual('snapshot_only', read_conservation(repository, LINEAGE)['assessment_status'])
        for override in [
            {'source_id':'other-v2025b'}, {'source_id':None},
            {'source_url':'https://avilist.org.evil.test/snapshot'},
            {'source_url':'https://user:pass@www.avilist.org/snapshot'},
            {'source_url':'http://www.avilist.org/snapshot'},
            {'source_url':'https://www.avilist.org:444/snapshot'},
            {'source_url':'https://www.avilist.org:bad/snapshot'},
            {'snapshot_sha256':'not-a-checksum'},
        ]:
            with self.subTest(override=override):
                repository._run.return_value = [{'category_raw':'LC', **source, **override}]
                self.assertIsNone(read_conservation(repository, LINEAGE)['category'])
        repository._run.return_value = [{'category_raw':'LC', **source}]
        self.assertIsNone(read_conservation(repository, replace(LINEAGE, taxonomy_source='Other'))['category'])
        self.assertIn('t.dataset_id=s.dataset_id', repository._run.call_args.args[0])

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
            'source_release':'v2025b', 'source_id':'avilist-v2025b'}]
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

    def test_all_active_ecology_categories_and_distributions_translate_without_changing_values(self):
        categories = {
            'trophic_niche': ['Vertivore', 'Scavenger', 'Omnivore', 'Invertivore', 'Aquatic predator',
                             'Frugivore', 'Herbivore aquatic', 'Herbivore terrestrial', 'Nectarivore', 'Granivore'],
            'trophic_level': ['Carnivore', 'Scavenger', 'Herbivore', 'Omnivore'],
            'habitat_density_category': ['dense', 'semi_open', 'open'],
        }
        for name, values in categories.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    display = trait_display(name, value)
                    self.assertRegex(display, r'[가-힣]')
                    self.assertNotRegex(display, r'[A-Za-z]')
                    self.assertNotEqual('번역 확인 필요', display)
        self.assertEqual('수생동물 포식', trait_display('trophic_niche', 'Aquatic predator'))
        original = {'mid_high': 80, 'unknown_layer': 20, 'aerial': 0, 'ground': None}
        self.assertEqual('중상층 80% · 미분류 항목 20%', trait_display('foraging_strata_distribution', original))
        self.assertEqual(20, original['unknown_layer'])
        self.assertEqual('번역 확인 필요', trait_display('trophic_niche', 'new category'))
        self.assertEqual('자료 없음', trait_display('habitat', 'NA'))
        self.assertEqual('확인된 구성 정보 없음', trait_display('diet_distribution', {'fish':0, 'fruit':None}))
        self.assertEqual('확인된 구성 정보 없음', trait_display('diet_distribution', {'fish':True, 'fruit':float('nan')}))

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
            result = _licensed_images('Ambiguous bird', 1)
            self.assertEqual([], result)
            self.assertEqual('ambiguous_taxon', result.status)

    def test_reviewed_night_heron_classifies_usual_activity_and_preserves_raw_claim(self):
        from robingraph.retrieval.reviewed_activity import reviewed_activity
        lineage = replace(LINEAGE, items=(replace(LINEAGE.items[-1], scientific_name='Nycticorax nycticorax'),))
        raw = {'name':'nocturnal','value':False,'display':'아니요',
               'source_name':'EltonTraits','source_url':'https://ndownloader.figshare.com/files/5631081#SpecID=5182'}
        result = reviewed_activity(lineage,[raw])
        self.assertEqual('activity_pattern',result[0]['name'])
        self.assertEqual('야행성', result[0]['display'])
        self.assertIs(True, result[0]['value'])
        self.assertIn('특별한 시기의 활동은 제외', result[0]['review_note'])
        self.assertEqual([raw],result[0]['source_claims'])
        self.assertFalse(raw['value'])
        self.assertEqual('야행성 아님', trait_display('nocturnal', False))
        self.assertEqual('야행성', trait_display('nocturnal', True))
        self.assertEqual([raw],reviewed_activity(LINEAGE,[raw]))
        self.assertEqual([raw],reviewed_activity(replace(lineage,taxonomy_release='future'),[raw]))
        flow=create_species_flow(lambda _:lineage,lambda _:result,photos=lambda _:[])
        profile=flow.invoke('Nycticorax nycticorax')
        ecology=next(s for s in profile['sections'] if s['key']=='ecology')
        self.assertTrue(any(i['text'] == '활동 시간: 야행성' for i in ecology['items']))
        nankeen = replace(lineage, items=(replace(lineage.items[-1], scientific_name='Nycticorax caledonicus'),))
        self.assertEqual('야행성', reviewed_activity(nankeen, [raw])[0]['display'])
        self.assertIsNone(next((t for t in reviewed_activity(LINEAGE, []) if t['name'] == 'nocturnal'), None))

    def test_photo_absence_reasons_preserve_species_information_and_card_contract(self):
        for status in ('no_licensed_photo', 'unconfirmed_taxon', 'ambiguous_taxon'):
            flow = create_species_flow(lambda _: LINEAGE, lambda _: [],
                                       photos=lambda _: PhotoLookup([], status))
            profile = flow.invoke('청둥오리')
            self.assertEqual(status, profile['photo_availability']['status'])
            self.assertEqual([], profile['images'])
            self.assertEqual('청둥오리', profile['taxon']['korean_name'])
            self.assertTrue(profile['sections'])
        flow = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=Mock(side_effect=TimeoutError))
        self.assertEqual('provider_unavailable', flow.invoke('청둥오리')['photo_availability']['status'])
        _licensed_images.cache_clear()
        with patch('robingraph.retrieval.species_profile._json_get', return_value={'results':{'bindings':[]}}):
            result = _licensed_images('Unconfirmed bird', 1)
            self.assertEqual('unconfirmed_taxon', result.status)
            self.assertEqual([], result)

    def test_profile_outage_does_not_expose_database_details(self):
        client = TestClient(create_app(species_profile_handler=Mock(side_effect=RuntimeError('secret database path'))))
        response = client.get('/v1/taxa/profile?name=청둥오리')
        self.assertEqual(503, response.status_code)
        self.assertNotIn('secret', response.text)


CROW_SNAPSHOT = {
    'source_name': 'AviList global avian checklist', 'source_url': 'https://explore.avilist.org/data/avilist-2025b.json',
    'source_release': 'v2025b', 'source_id': 'avilist-v2025b',
    'snapshot_sha256': '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411',
}
CROW_LINEAGE = TaxonomyLineage('Corvus macrorhynchos', 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b', (
    LineageTaxon('avilist-taxon:v2025b:20236', 'genus', 'Corvus', 'Linnaeus, C, 1758'),
    LineageTaxon('avilist-taxon:v2025b:20296', 'species', 'Corvus macrorhynchos', 'Wagler, JG, 1827')))


class ReferenceAssessmentIntegrationTest(unittest.TestCase):
    def read(self, raw, lineage=CROW_LINEAGE):
        repository = Mock()
        repository._run.return_value = [{'category_raw': raw, **CROW_SNAPSHOT}]
        return read_conservation(repository, lineage)

    def test_actual_crow_helper_and_index_attach_reference_without_changing_the_grade(self):
        result = self.read('NE')
        self.assertEqual((None, 'NE', 'needs_review', '평가 연결 확인 필요'),
                         (result['category'], result['category_raw'], result['assessment_status'], result['label']))
        ref = result['reference_assessment']
        self.assertEqual(('LC', '관심대상', 'reference_only', 'red_list_checklist_reference', 'Corvus macrorhynchos'),
                         (ref['category'], ref['label'], ref['assessment_status'], ref['evidence_kind'], ref['scientific_name']))
        self.assertEqual(('unverified', False, 2024), (ref['taxonomy_alignment'], ref['independently_verified'], ref['assessment_year']))
        self.assertEqual('https://www.iucnredlist.org/species/103727590/264280673', ref['assessment_reference_url'])
        self.assertIn('RLTS.T103727590A264280673', ref['assessment_citation'])
        self.assertIn('확정하지 않습니다', ref['quality_note'])

    def test_non_ne_snapshot_and_other_species_never_get_a_reference(self):
        self.assertNotIn('reference_assessment', self.read('LC'))
        other = replace(CROW_LINEAGE, items=(CROW_LINEAGE.items[0],
                        replace(CROW_LINEAGE.items[1], taxon_id='avilist-taxon:v2025b:0', scientific_name='Corvus corax')))
        self.assertNotIn('reference_assessment', self.read('NE', other))

    def test_helper_contract_is_filtered_and_failures_degrade_to_plain_ne(self):
        good = {'category': 'EN', 'assessment_status': 'reference_only'}
        with patch('robingraph.retrieval.species_profile.reference_checklist', return_value=good) as helper:
            result = self.read('NE')
            self.assertEqual('위기', result['reference_assessment']['label'])
            self.assertIsNone(result['category'])
            self.assertEqual('NE', result['taxonomy_category_raw'])
            self.assertEqual('needs_review', helper.call_args.args[1]['assessment_status'])
        for bad in (None, [], 'LC', {'category': 'NE'}, {'category': 'XX'}, {}):
            with patch('robingraph.retrieval.species_profile.reference_checklist', return_value=bad):
                result = self.read('NE')
                self.assertNotIn('reference_assessment', result, repr(bad))
                self.assertIsNone(result['category'])
                self.assertEqual('NE', result['category_raw'])
        with patch('robingraph.retrieval.species_profile.reference_checklist', side_effect=RuntimeError('boom')):
            self.assertNotIn('reference_assessment', self.read('NE'))

    def test_linked_and_manual_override_take_precedence_and_skip_reference(self):
        with patch('robingraph.retrieval.species_profile.linked_checklist', return_value={'category': 'LC'}), \
             patch('robingraph.retrieval.species_profile.reference_checklist') as helper:
            self.assertEqual({'category': 'LC', 'label': '관심대상'}, self.read('NE'))
            helper.assert_not_called()
        with patch('robingraph.retrieval.species_profile.manual_magpie_override', return_value={'category': 'LC', 'evidence_kind': 'manual_override'}), \
             patch('robingraph.retrieval.species_profile.reference_checklist') as helper:
            self.assertEqual('manual_override', self.read('NE')['evidence_kind'])
            helper.assert_not_called()
