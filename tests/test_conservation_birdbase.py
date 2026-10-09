"""Publisher nominal crosswalks remain separate from verified species grades."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from robingraph.retrieval import conservation as c
from robingraph.retrieval.reviewed_conservation import reviewed_index
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('birdbase_conservation_builder', ROOT / 'scripts/build_birdbase_conservation_index.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BirdbaseConservationTest(unittest.TestCase):
    def setUp(self):
        self.index = c._birdbase_index()
        self.record = next(r for r in self.index['entries'].values() if r['taxonomy_category_raw'] == 'NE' and r['category'])
        self.lineage = self.lineage_for(self.record)
        self.snapshot = dict(category=None, category_raw='NE', evidence_kind='taxonomy_snapshot',
            assessment_status='needs_review', snapshot_sha256=c.TAXONOMY_SHA256)

    @staticmethod
    def lineage_for(record):
        return TaxonomyLineage(record['scientific_name'], 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b',
            (LineageTaxon(record['taxon_id'], 'species', record['scientific_name'], record['authority']),))

    def test_all_447_original_targets_have_audited_source_row_and_precise_outcome(self):
        ledger = json.loads((ROOT / 'docs/verification/assets/2026-10-09-unresolved-conservation-review.json').read_text())
        self.assertEqual({'birdbase-v2025.1': 117, 'gbif-iucn-2026-1': 25, 'missing': 305}, ledger['counts']['combined_reference_sources'])
        self.assertEqual(11131, len(self.index['entries']))
        approved = reviewed_index()
        expert_ids, missing_ids = set(), set()
        for row in ledger['species']:
            lookup = row['birdbase_lookup']
            lineage = self.lineage_for(lookup)
            ref = c.best_reference_assessment(lineage, self.snapshot)
            if row['selected_reference_source'] is None:
                self.assertIsNone(lookup['category'])
                if row['taxon_id'] in approved:
                    self.assertEqual(approved[row['taxon_id']], ref)
                    self.assertEqual('reference_only', ref['assessment_status'])
                    self.assertFalse(ref['independently_verified'])
                    self.assertIsNone(ref['assessment_year'])
                    expert_ids.add(row['taxon_id'])
                else:
                    self.assertIsNone(ref, row['scientific_name'])
                    missing_ids.add(row['taxon_id'])
            else:
                self.assertEqual(row['selected_reference_source'], ref['source_id'])
                self.assertEqual(row['reference_category'], ref['category'])
                self.assertEqual('reference_only', ref['assessment_status'])
                self.assertEqual('unverified', ref['taxonomy_alignment'])
                self.assertFalse(ref['independently_verified'])
                if ref['source_id'] == 'birdbase-v2025.1':
                    self.assertEqual(2024, ref['data_year'])
                    self.assertNotIn('assessment_year', ref)
                    self.assertNotIn('assessment_id', ref)
                    self.assertEqual(f"Data!row {ref['source_row']}", ref['source_locator'])
            self.assertIsNone(c.linked_checklist(lineage, self.snapshot))
        self.assertEqual(set(approved), expert_ids)
        self.assertEqual(305 - len(expert_ids), len(missing_ids))
        self.assertEqual(4, ledger['counts']['excluded_unreleased_recommendations'])
        for row in ledger['species']:
            if 'unreleased_recommendation' in row:
                self.assertFalse(row['unreleased_recommendation']['assign_grade_to_target'])

    def test_gbif_reference_precedes_dataset_reference(self):
        sentinel = {'source_id': 'gbif-iucn-2026-1'}
        with patch.object(c, 'reference_checklist', return_value=sentinel), patch.object(c, 'birdbase_reference_checklist') as dataset:
            self.assertIs(sentinel, c.best_reference_assessment(self.lineage, self.snapshot))
            dataset.assert_not_called()

    def test_disabled_or_disallowed_source_does_not_return_reference(self):
        with patch('robingraph.retrieval.birdbase.source_allowed', return_value=False):
            self.assertIsNone(c.birdbase_reference_checklist(self.lineage, self.snapshot))

    def test_source_pins_identity_and_row_locator_fail_closed(self):
        mutations = [('source', 'id', 'other'), ('source', 'name', 'other'),
            ('source', 'snapshot_sha256', '0' * 64), ('source', 'url', 'https://example.com'),
            ('source', 'license_name', 'CC BY-NC'), ('source', 'data_year', 2025),
            ('source', 'data_year', True), ('source', 'category_column', 'other'),
            ('record', 'scientific_name', 'Other bird'), ('record', 'authority', 'Other, 2020'),
            ('record', 'source_row', '3'), ('record', 'source_locator', 'Data!row 1'),
            ('record', 'category', 'NE'), ('record', 'category_raw', 'VU')]
        for target, key, value in mutations:
            with self.subTest(target=target, key=key):
                index = deepcopy(self.index)
                selected = index['source'] if target == 'source' else index['entries'][self.record['taxon_id']]
                selected[key] = value
                with patch.object(c, '_birdbase_index', return_value=index):
                    self.assertIsNone(c.birdbase_reference_checklist(self.lineage, self.snapshot))
        for key, value in [('snapshot_sha256', '0' * 64), ('category_raw', 'LC'),
                           ('assessment_status', 'snapshot_only'), ('evidence_kind', 'live_assessment')]:
            with self.subTest(snapshot=key):
                self.assertIsNone(c.birdbase_reference_checklist(self.lineage, dict(self.snapshot, **{key: value})))

    def test_builder_rejects_duplicate_crosswalk_and_invalid_category(self):
        taxonomy = ['1', 'species', 'Order', 'Family', None, 'Example species', 'Author, 2000'] + [None] * 8 + ['NE']
        row = {'AviList v1 2025': 'Example species', 'Family AviList v1 2025': 'Family',
               builder.COLUMN: 'CR (PE)', '_row': 3}
        built = builder.build([taxonomy], [row], require_complete=False)
        self.assertEqual('CR', built['entries']['avilist-taxon:v2025b:1']['category'])
        self.assertEqual('CR (PE)', built['entries']['avilist-taxon:v2025b:1']['category_raw'])
        with self.assertRaises(ValueError):
            builder.build([taxonomy], [row, row], require_complete=False)
        with self.assertRaises(ValueError):
            builder.build([taxonomy], [dict(row, **{builder.COLUMN: 'invented'})], require_complete=False)


if __name__ == '__main__':
    unittest.main()
