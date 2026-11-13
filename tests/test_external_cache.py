import json
import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import Mock, patch

from robingraph.retrieval.external_cache import read_cached, remember
from robingraph.retrieval.species_notes import create_species_notes
from robingraph.retrieval.species_profile import create_species_flow, _licensed_images
from tests.test_species_profile import LINEAGE


class ExternalCacheTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        env = patch.dict(os.environ, {'ROBINGRAPH_SPECIES_CACHE_ROOT': self.directory.name})
        env.start()
        self.addCleanup(env.stop)
        _licensed_images.cache_clear()
        self.addCleanup(_licensed_images.cache_clear)

    def test_persists_across_new_handlers_and_is_versioned_and_expires(self):
        load = Mock(return_value={'source_url': 'https://example.org/revision/123'})
        with patch('robingraph.retrieval.external_cache.time.time', return_value=1000):
            expected = remember('v1:species', load)
        with patch('robingraph.retrieval.external_cache.time.time', return_value=2000):
            self.assertEqual(expected, remember('v1:species', Mock(side_effect=AssertionError())))
            self.assertIsNone(read_cached('v2:species'))
        with patch('robingraph.retrieval.external_cache.time.time', return_value=87400):
            self.assertIsNone(read_cached('v1:species'))
        self.assertEqual(1, load.call_count)

    def test_parallel_misses_load_once_and_failure_does_not_poison_cache(self):
        barrier = Barrier(2)
        load = Mock(return_value={'images': []})
        def read():
            barrier.wait()
            return remember('photos', load)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual([{'images': []}] * 2, list(pool.map(lambda _: read(), range(2))))
        self.assertEqual(1, load.call_count)
        with self.assertRaises(TimeoutError):
            remember('notes', Mock(side_effect=TimeoutError()))
        self.assertIsNone(read_cached('notes'))
        self.assertEqual({'notes': []}, remember('notes', lambda: {'notes': []}))

    def test_corrupt_cache_and_unwritable_cache_do_not_hide_valid_data(self):
        remember('record', lambda: {'valid': True})
        next(Path(self.directory.name).glob('*.json')).write_text('{broken')
        self.assertIsNone(read_cached('record'))
        with patch('robingraph.retrieval.external_cache.os.replace', side_effect=OSError()):
            self.assertEqual({'valid': True}, remember('record', lambda: {'valid': True}))

    def test_basic_profile_reuses_persisted_notes_and_photos_without_provider_calls(self):
        source = {'text': 'A supported excerpt.', 'source_name': 'Wikipedia', 'source_url': 'https://en.wikipedia.org/w/index.php?oldid=123',
                  'license_name': 'CC BY-SA 4.0', 'source_scientific_name': 'Anas platyrhynchos'}
        summarize = Mock(return_value={'appearance': [{'text': '출처에 근거한 설명입니다.'}], 'fun_facts': []})
        with patch('robingraph.retrieval.species_notes.encyclopedia_excerpt', return_value=source):
            create_species_notes(summarize, model='model-a')(LINEAGE)
        fresh = create_species_notes(Mock(side_effect=AssertionError()), model='model-a')
        self.assertEqual(source['source_url'], fresh.cached(LINEAGE)['appearance'][0]['source_url'])
        self.assertIsNone(create_species_notes(summarize, model='model-b').cached(LINEAGE))
        remember('photos-v1:species:Anas platyrhynchos', lambda: {'images': [{'image_url': 'https://upload.wikimedia.org/bird.jpg', 'license_name': 'CC BY 4.0'}], 'status': 'available'})
        flow = create_species_flow(lambda _: LINEAGE, lambda _: [], include_enrichment=False, cached_notes=fresh.cached)
        with patch('robingraph.retrieval.species_profile._json_get', side_effect=AssertionError()):
            result = flow.invoke('Anas platyrhynchos')
        self.assertFalse(result.get('enrichment_pending', False))
        self.assertEqual('CC BY 4.0', result['images'][0]['license_name'])
        self.assertIn('출처에 근거한', str(result['sections']))
        self.assertEqual(1, summarize.call_count)

    def test_media_profile_never_waits_for_note_generation(self):
        notes = Mock(side_effect=AssertionError())
        profile = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=lambda _: [], notes=notes,
                                      include_notes=False, cached_notes=lambda _: None).invoke('Anas platyrhynchos')
        self.assertEqual([], profile['images'])
        self.assertTrue(profile['enrichment_pending'])
        notes.assert_not_called()
