import copy
from dataclasses import replace
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from robingraph.retrieval import recordings as audio
from robingraph.retrieval.species_profile import create_species_flow
from test_species_profile import LINEAGE


class RecordingSourceTests(TestCase):
    def setUp(self):
        self.data = json.loads(Path(audio.__file__).with_name('commons_bird_recordings.json').read_text())
        self.row = copy.deepcopy(self.data['records'][0])

    def test_reviewed_catalog_preserves_original_files_and_their_optional_facts(self):
        records = audio.reviewed_catalog()
        self.assertTrue({'Anas platyrhynchos', 'Passer montanus', 'Hypsipetes amaurotis'} <=
                        {record['scientific_name'] for record in records.values()})
        self.assertTrue(audio.source_allowed())
        self.assertEqual(12, len(audio.graph_rows()))
        mallard = next(r for r in records.values() if r['scientific_name'] == 'Anas platyrhynchos')
        self.assertEqual('Jonathon Jongsma', mallard['creator'])
        self.assertEqual('2010-09-14 13:53', mallard['recorded_at'])
        self.assertEqual('Powderhorn Park, Minneapolis, MN', mallard['location'])
        self.assertIsNone(mallard['recording_type'])
        self.assertNotIn('utm_', mallard['audio_url'])

    def test_catalog_matches_reviewed_domestic_species_manifest_and_original_provenance(self):
        expected = {'Anas platyrhynchos', 'Hypsipetes amaurotis', 'Passer montanus', 'Ardea alba',
                    'Ardea cinerea', 'Dryocopus martius', 'Cuculus canorus', 'Fulica atra', 'Hirundo rustica',
                    'Motacilla alba', 'Nycticorax nycticorax', 'Streptopelia orientalis'}
        catalog = audio.reviewed_catalog()
        self.assertEqual(expected, {record['scientific_name'] for record in catalog.values()})
        self.assertEqual(12, len(catalog))
        original = {'commons-recording:23927872': 'f7a7f6584afe2ccd18758e2e8da4a7653f16886ccd120f7ef6e96943b3ccc9ee',
                    'commons-recording:186512225': '3e4eb39f678379fc13a9a27f28e986f743353e2beccb63dad63a0e26d2622ce1',
                    'commons-recording:16592315': 'c9651be0b378f0a54f70f27939f56ad42398bdca9f359fd7ba33eb6584987a9d'}
        for record_id, digest in original.items():
            self.assertEqual(digest, catalog[record_id]['evidence']['metadata_sha256'])
            self.assertEqual('2026-10-30T06:29:17.911783+00:00', catalog[record_id]['evidence']['retrieved_at'])
        for record in catalog.values():
            self.assertEqual({'id','scientific_name','audio_url','source_url','creator','license_name','license_url',
                              'title','recording_type','recorded_at','location','evidence'}, set(record))
            if record['id'] not in original:
                self.assertTrue(record['evidence']['retrieved_at'].startswith('2026-11-02'))
        formats = {f"commons-recording:{row['page_id']}": row['imageinfo']['mime'] for row in self.data['records']}
        self.assertEqual(formats, {row['id']: row['format'] for row in audio.graph_rows()})
        self.assertIn('audio/mpeg', formats.values())

    def test_empty_duplicate_species_duplicate_ids_and_wrong_manifest_are_rejected(self):
        invalid = []
        empty = copy.deepcopy(self.data); empty['records'] = []; empty['expected_recordings'] = 0; empty['expected_species'] = []
        invalid.append(empty)
        for different_id in (False, True):
            duplicate = copy.deepcopy(self.data); extra = copy.deepcopy(duplicate['records'][0])
            if different_id:
                extra['page_id'] += 1
            duplicate['records'].append(extra); duplicate['expected_recordings'] += 1
            duplicate['expected_species'].append(extra['scientific_name']); invalid.append(duplicate)
        wrong = copy.deepcopy(self.data); wrong['expected_species'][0] = 'Anas crecca'; invalid.append(wrong)
        try:
            for data in invalid:
                audio.reviewed_catalog.cache_clear()
                with self.subTest(count=data['expected_recordings']), patch.object(audio, '_reviewed_data', return_value=data), self.assertRaises(ValueError):
                    audio.reviewed_catalog()
        finally:
            audio.reviewed_catalog.cache_clear()

    def test_only_canonical_official_http_license_links_are_upgraded(self):
        row = copy.deepcopy(self.row)
        row['imageinfo']['extmetadata']['LicenseUrl']['value'] = 'http://creativecommons.org/licenses/by-sa/3.0/'
        record = audio.reviewed_record(row, self.data['retrieved_at'])
        self.assertEqual('https://creativecommons.org/licenses/by-sa/3.0/', record['license_url'])
        for url in ('http://creativecommons.org.evil.invalid/licenses/by-sa/3.0/',
                    'https://user@creativecommons.org/licenses/by-sa/3.0/',
                    'https://creativecommons.org:8443/licenses/by-sa/3.0/',
                    'https://creativecommons.org/licenses/by-nc/3.0/'):
            row['imageinfo']['extmetadata']['LicenseUrl']['value'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                audio.reviewed_record(row, self.data['retrieved_at'])

    def test_importer_rejects_a_count_outside_the_reviewed_manifest_before_connecting(self):
        import os
        import subprocess
        import sys
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'import_reviewed_recordings.py'
        result = subprocess.run([sys.executable, str(script), '--apply-test', '--expect-uri', 'bolt://example.invalid',
                                 '--expect-database', 'neo4j', '--expect-concept-set', 'confirmed-test',
                                 '--expect-taxonomy-release', 'v2025b', '--expect-recordings', '11'],
                                env={**os.environ, 'ROBINGRAPH_DEPLOY_TARGET': 'test'},
                                capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn('expected recording count differs', result.stderr)

    def test_video_dimensions_are_not_accepted_as_an_ogg_recording(self):
        row = copy.deepcopy(self.row); row['imageinfo'].update(width=1280, height=720)
        with self.assertRaises(ValueError):
            audio.reviewed_record(row, self.data['retrieved_at'])

    def test_pinned_snapshot_rejects_unreviewed_bundle_changes(self):
        audio.reviewed_catalog.cache_clear()
        try:
            with patch.object(Path, 'read_bytes', return_value=b'{}'), self.assertRaisesRegex(ValueError, 'pinned hash'):
                audio.reviewed_catalog()
        finally:
            audio.reviewed_catalog.cache_clear()

    def test_license_restriction_author_and_exact_species_mismatches_fail_closed(self):
        for field, value in (('License', 'cc-by-nc-4.0'), ('LicenseUrl', 'https://evil.invalid/license'),
                             ('Restrictions', 'permission required'), ('Artist', '')):
            row = copy.deepcopy(self.row)
            row['imageinfo']['extmetadata'][field]['value'] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audio.reviewed_record(row, self.data['retrieved_at'])
        row = copy.deepcopy(self.row); row['scientific_name'] = 'Anas zonorhyncha'
        with self.assertRaises(ValueError):
            audio.reviewed_record(row, self.data['retrieved_at'])

    def test_audio_and_landing_urls_are_allowlisted_and_match_the_file(self):
        for key, value in (('url', 'http://upload.wikimedia.org/wikipedia/commons/file.ogg'),
                           ('url', 'https://upload.wikimedia.org.evil.invalid/wikipedia/commons/file.ogg'),
                           ('url', 'https://user@upload.wikimedia.org/wikipedia/commons/file.ogg'),
                           ('url', 'https://upload.wikimedia.org/wikipedia/commons/Other.ogg'),
                           ('descriptionurl', 'https://commons.wikimedia.org/wiki/File:Other.ogg')):
            row = copy.deepcopy(self.row); row['imageinfo'][key] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                audio.reviewed_record(row, self.data['retrieved_at'])

    def test_no_date_or_type_is_inferred_from_upload_date_or_filename(self):
        row = copy.deepcopy(self.row)
        row['imageinfo']['extmetadata'].pop('DateTimeOriginal', None)
        record = audio.reviewed_record(row, self.data['retrieved_at'])
        self.assertIsNone(record['recorded_at'])
        self.assertIsNone(record['recording_type'])
        row['location'] = 'Seoul, Korea'
        with self.assertRaises(ValueError):
            audio.reviewed_record(row, self.data['retrieved_at'])


class RecordingGraphAndProfileTests(TestCase):
    def setUp(self):
        self.record = next(r for r in audio.reviewed_catalog().values() if r['scientific_name'] == 'Anas platyrhynchos')
        self.repo = Mock()
        self.repo._run.return_value = [{'id': self.record['id'], 'payload_json': json.dumps(self.record),
                                       'metadata_sha256': self.record['evidence']['metadata_sha256']}]

    def test_exact_graph_record_is_read_with_active_taxonomy_and_source_guards(self):
        self.assertEqual([self.record], audio.read_recordings(self.repo, LINEAGE))
        query = self.repo._run.call_args.args[0]
        params = self.repo._run.call_args.kwargs
        self.assertEqual(('concept', 'v2025b', 't', 'Anas platyrhynchos'),
                         (params['concept_set_id'], params['taxonomy_release'], params['taxon_id'], params['scientific_name']))
        for guard in ('MediaAsset:Recording', 'HAS_RECORDING', 'SUPPORTED_BY', "policy_status:'allowed'",
                      'evidence.source_record_id=media.id', 'evidence.content_hash=media.metadata_sha256'):
            self.assertIn(guard, query)
        self.assertNotIn('MERGE', query)
        bad = dict(self.record, creator='Someone else')
        self.repo._run.return_value = [{'id': self.record['id'], 'payload_json': json.dumps(bad)}]
        with self.assertRaises(ValueError):
            audio.read_recordings(self.repo, LINEAGE)

    def test_no_parent_audio_for_subspecies_and_disabled_source_has_no_query(self):
        subspecies = replace(LINEAGE, items=(replace(LINEAGE.items[-1], rank='subspecies'),))
        self.assertEqual([], audio.read_recordings(self.repo, subspecies))
        with patch.object(audio, 'source_allowed', return_value=False):
            self.assertEqual([], audio.read_recordings(self.repo, LINEAGE))
            with self.assertRaises(ValueError):
                audio.graph_rows()
        self.repo._run.assert_not_called()

    def test_audio_is_available_in_basic_profile_without_waiting_for_photos(self):
        photos = Mock()
        recordings = Mock(return_value=[self.record])
        flow = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=photos,
                                   recordings=recordings, include_enrichment=False)
        result = flow.invoke('청둥오리')
        self.assertEqual([self.record], result['recordings'])
        self.assertEqual('available', result['recording_availability']['status'])
        self.assertEqual('pending', result['photo_availability']['status'])
        photos.assert_not_called()
        recordings.assert_called_once_with(LINEAGE)

    def test_missing_recordings_and_graph_error_are_distinct_without_losing_profile(self):
        for reader, expected in ((Mock(return_value=[]), 'no_licensed_recording'),
                                 (Mock(side_effect=RuntimeError('private credentials')), 'provider_unavailable')):
            result = create_species_flow(lambda _: LINEAGE, lambda _: [], recordings=reader,
                                         include_enrichment=False).invoke('청둥오리')
            self.assertEqual([], result['recordings'])
            self.assertEqual(expected, result['recording_availability']['status'])
            self.assertNotIn('private credentials', json.dumps(result))
            self.assertEqual('t', result['taxon']['taxon_id'])
