import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('chunk_measurement', Path(__file__).parents[1] / 'scripts/measure_chunk_search.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ChunkMeasurementTests(unittest.TestCase):
    def test_p95_uses_nearest_rank_and_does_not_change_samples(self):
        samples = list(range(100, 0, -1))
        self.assertEqual(probe.summary(samples), {'samples': 100, 'p50_ms': 50.5, 'p95_ms': 95, 'max_ms': 100})
        self.assertEqual(samples[0], 100)

    def test_production_target_cannot_run_probe_against_test_host(self):
        with patch.dict(os.environ, ROBINGRAPH_DEPLOY_TARGET='prod'):
            with self.assertRaises(ValueError):
                probe.require_test(SimpleNamespace(uri='bolt://192.168.219.98:7687'))

    def test_test_target_cannot_run_probe_against_other_host(self):
        with patch.dict(os.environ, ROBINGRAPH_DEPLOY_TARGET='test'):
            with self.assertRaises(ValueError):
                probe.require_test(SimpleNamespace(uri='bolt://192.168.219.99:7687'))
            probe.require_test(SimpleNamespace(uri='bolt://192.168.219.98:7687'))
