from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch
from robingraph.retrieval import reviewed_conservation as r
from robingraph.retrieval import conservation as c
from robingraph.retrieval.species_profile import read_conservation
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


class ReviewedReferenceTest(unittest.TestCase):
    def setUp(self):
        self.record = deepcopy(next(iter(r.reviewed_index().values())))
        self.lineage = TaxonomyLineage('박새', 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b',
            (LineageTaxon(self.record['taxon_id'], 'species', 'Parus cinereus', 'Vieillot, LJP, 1818', '박새'),))
        self.snapshot = dict(category='NE', category_raw='NE', assessment_status='needs_review',
                             evidence_kind='taxonomy_snapshot', snapshot_sha256=r.TAXONOMY_SHA256)

    def test_pinned_record_is_reference_not_independent_assessment(self):
        value = r.reviewed_reference_assessment(self.lineage, self.snapshot)
        self.assertEqual(value['category'], 'LC')
        self.assertEqual(value['taxonomy_alignment'], 'partial_scope')
        self.assertEqual(value['assessment_status'], 'reference_only')
        self.assertIsNone(value['assessment_year'])
        self.assertFalse(value['independently_verified'])
        self.assertEqual(value['source_scientific_name'], 'Parus minor')
        self.assertEqual(value['assessment_scientific_name'], 'Parus major')
        self.assertIn('독립된 신규 평가', value['source_scope_note'])
        self.assertEqual(self.snapshot['category'], 'NE')

    def test_read_conservation_keeps_original_ne_and_effective_null(self):
        repo = Mock()
        repo._run.return_value = [dict(category_raw='NE', source_name='AviList global avian checklist',
            source_url='https://www.avilist.org/', source_release='v2025b', source_id='avilist-v2025b',
            snapshot_sha256=r.TAXONOMY_SHA256)]
        value = read_conservation(repo, self.lineage)
        self.assertIsNone(value['category'])
        self.assertEqual(value['category_raw'], 'NE')
        self.assertEqual(value['taxonomy_category_raw'], 'NE')
        self.assertEqual(value['reference_assessment']['category'], 'LC')

    def test_no_other_concept_or_source_inherits_reference(self):
        for key, value in [('scientific_name','Parus minor'), ('taxon_id','avilist-taxon:v2025b:1'),
                           ('rank','subspecies'), ('authority','Other')]:
            changed = replace(self.lineage, items=(replace(self.lineage.items[0], **{key:value}),))
            self.assertIsNone(r.reviewed_reference_assessment(changed, self.snapshot))
        for key, value in [('taxonomy_release','v2026'), ('concept_set_id','other'), ('taxonomy_source','Other')]:
            self.assertIsNone(r.reviewed_reference_assessment(replace(self.lineage, **{key:value}), self.snapshot))
        for change in ({'snapshot_sha256':'0'*64}, {'category_raw':'LC'}, {'assessment_status':'linked_checklist'}):
            self.assertIsNone(r.reviewed_reference_assessment(self.lineage, {**self.snapshot, **change}))

    def test_corrupt_artifact_and_record_fail_closed(self):
        r.reviewed_index.cache_clear()
        with patch.object(r.Path, 'read_bytes', return_value=b'{}'):
            self.assertEqual(r.reviewed_index(), {})
        r.reviewed_index.cache_clear()
        for key, value in [('category','EN'), ('assessment_year',2024), ('source_url','https://example.org'),
                           ('source_scientific_name','Other'), ('record_sha256','0'*64)]:
            record = {**self.record, key:value}
            self.assertFalse(r.valid_record(record))

    def test_exact_name_contract_stays_reference_only(self):
        record = {**self.record, 'source_scientific_name':'Parus cinereus',
                  'taxonomy_alignment':'exact_source_name', 'mapping_method':'reviewed_exact_source_name'}
        record['record_sha256'] = r.record_digest(record)
        self.assertTrue(r.valid_record(record))
        record['independently_verified'] = True
        record['record_sha256'] = r.record_digest(record)
        self.assertFalse(r.valid_record(record))

    def test_all_reviewed_records_resolve_without_promoting_primary_grade(self):
        records = r.reviewed_index()
        self.assertGreaterEqual(len(records), 6)
        for record in records.values():
            with self.subTest(name=record['scientific_name']):
                lineage = replace(self.lineage, items=(LineageTaxon(record['taxon_id'], 'species',
                    record['scientific_name'], record['authority'], None),))
                repo = Mock()
                repo._run.return_value = [dict(category_raw='NE', source_name='AviList global avian checklist',
                    source_url='https://www.avilist.org/', source_release='v2025b', source_id='avilist-v2025b',
                    snapshot_sha256=r.TAXONOMY_SHA256)]
                result = read_conservation(repo, lineage)
                self.assertIsNone(result['category'])
                self.assertEqual(result['category_raw'], 'NE')
                self.assertEqual(result['reference_assessment']['category'], 'LC')
                self.assertEqual(result['reference_assessment']['source_url'], record['source_url'])
                self.assertEqual(result['reference_assessment']['record_sha256'], record['record_sha256'])
        pipit = records['avilist-taxon:v2025b:30040']
        self.assertIsNone(pipit['assessment_scientific_name'])
        self.assertEqual(pipit['citation_scientific_name'], 'Anthus rubescens')

    def test_existing_reference_priority_is_unchanged(self):
        for official, dataset, expected in [({'a':1},{'b':2},{'a':1}), (None,{'b':2},{'b':2})]:
            with patch.object(c,'reference_checklist',return_value=official), patch.object(c,'birdbase_reference_checklist',return_value=dataset), patch.object(r,'reviewed_reference_assessment') as expert:
                self.assertEqual(c.best_reference_assessment(self.lineage,self.snapshot),expected)
                expert.assert_not_called()
