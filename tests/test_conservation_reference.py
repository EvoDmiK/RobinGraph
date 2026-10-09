"""Published reference integrity and concept boundaries, separate from grades."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from robingraph.retrieval import conservation as c
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reference_fixtures', ROOT / 'tests/test_conservation_index.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class ReferenceBuilderTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ConservationIndexTest()
        self.f.setUp()
        self.f.avilist[0][15] = 'NE'
        self.f.avilist[0][16] = None

    def test_ne_without_link_exposes_reference_and_never_maps_taxon(self):
        index = self.f.build()
        self.assertEqual({}, index['taxa'])
        ref = index['references']['avilist-taxon:v2025b:1']
        self.assertEqual(('LC', 'NE', 'unverified'), (ref['category'], ref['taxonomy_category_raw'], ref['taxonomy_alignment']))
        self.assertEqual({'unlinked_species':1, 'reference_species':1, 'excluded_reasons':{}}, index['reference_coverage'])

    def test_reference_rejects_duplicates_non_global_and_inconsistent_citations(self):
        for mutation in ('same_name', 'same_id', 'global', 'citation'):
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation == 'same_name':
                    row = deepcopy(self.f.core[0]); row[0] = row[13] = '99'; self.f.core.append(row)
                elif mutation == 'same_id':
                    row = deepcopy(self.f.core[0]); row[7] = 'Other'; self.f.core.append(row)
                elif mutation == 'global':
                    self.f.distributions.append(deepcopy(self.f.distributions[0]))
                else:
                    self.f.distributions[0][3] = 'different'
                index = self.f.build()
                self.assertEqual({}, index['references'])
                self.assertEqual(1, sum(index['reference_coverage']['excluded_reasons'].values()))

    def test_name_author_year_and_parentheses_never_relaxed(self):
        for field, value in ((5, 'Anas changed'), (6, 'Other, 1758'), (6, 'Linnaeus, 1759'), (6, '(Linnaeus, 1758)')):
            with self.subTest(value=value):
                self.setUp(); self.f.avilist[0][field] = value
                self.assertEqual({}, self.f.build()['references'])


class ReferenceRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.index = deepcopy(c._index())
        self.key = 'avilist-taxon:v2025b:20296'
        self.record = self.index['references'][self.key]
        self.lineage = TaxonomyLineage('큰부리까마귀', 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b',
            (LineageTaxon(self.key, 'species', 'Corvus macrorhynchos', 'Wagler, JG, 1827', '큰부리까마귀'),))
        self.snapshot = dict(category='NE', category_raw='NE', evidence_kind='taxonomy_snapshot', assessment_status='needs_review', snapshot_sha256=c.TAXONOMY_SHA256)

    def test_real_reference_never_modifies_snapshot_or_inherits_grade(self):
        before = deepcopy(self.snapshot)
        result = c.reference_checklist(self.lineage, self.snapshot)
        self.assertEqual(before, self.snapshot)
        self.assertIsNone(c.linked_checklist(self.lineage, self.snapshot))
        self.assertEqual('LC', result['category'])
        self.assertEqual('reference_only', result['assessment_status'])
        self.assertEqual('red_list_checklist_reference', result['evidence_kind'])
        self.assertEqual('unverified', result['taxonomy_alignment'])
        self.assertFalse(result['independently_verified'])
        self.assertEqual('103727590', result['sis_id'])
        self.assertEqual('264280673', result['assessment_id'])
        self.assertEqual(2024, result['assessment_year'])
        self.assertEqual('Wagler, 1827', result['assessment_authority'])
        neutral = c.reference_checklist(self.lineage, {**self.snapshot, 'category':None})
        self.assertEqual('LC', neutral['category'])
        self.assertEqual('NE', neutral['taxonomy_category_raw'])

    def test_changed_concept_and_snapshot_fail_closed(self):
        for lineage in (replace(self.lineage, taxonomy_source='other'),
                        replace(self.lineage, taxonomy_release='v2026'),
                        replace(self.lineage, concept_set_id='other'),
                        replace(self.lineage, items=(replace(self.lineage.items[0], rank='subspecies'),)),
                        replace(self.lineage, items=(replace(self.lineage.items[0], scientific_name='Corvus other'),)),
                        replace(self.lineage, items=(replace(self.lineage.items[0], authority='Wagler, JG, 1828'),))):
            with self.subTest(lineage=lineage):
                self.assertIsNone(c.reference_checklist(lineage, self.snapshot))
        for override in ({'snapshot_sha256':None}, {'category_raw':'LC'}, {'evidence_kind':'manual_override'},
                         {'assessment_status':None}, {'assessment_status':'unconfirmed'},
                         {'assessment_status':'linked_checklist'}, {'assessment_status':'manual_override'}):
            self.assertIsNone(c.reference_checklist(self.lineage, {**self.snapshot, **override}))

    def test_corrupted_source_and_reference_record_fail_closed(self):
        cases = [('source', 'snapshot_sha256', 'a'*64), ('source', 'license_name', 'CC BY-NC'),
                 ('source', 'url', 'https://evil.test'), ('source', 'release', '2027-1'),
                 ('record', 'assessment_id', True), ('record', 'assessment_year', 2026),
                 ('record', 'assessment_citation', 'No verified ID'), ('record', 'category', 'NE'),
                 ('record', 'assessment_reference_url', 'https://evil.test'),
                 ('record', 'taxonomy_alignment', 'exact'), ('record', 'authority_match_method', 'fuzzy'),
                 ('record', 'assessment_authority', 'Other, 1827')]
        for scope, key, value in cases:
            with self.subTest(scope=scope, key=key):
                index = deepcopy(self.index)
                target = index['source'] if scope == 'source' else index['references'][self.key]
                target[key] = value
                with patch.object(c, '_index', return_value=index):
                    self.assertIsNone(c.reference_checklist(self.lineage, self.snapshot))

    def test_real_full_index_denominators_and_linked_coverage_unchanged(self):
        coverage = self.index['reference_coverage']
        self.assertEqual(3624, coverage['unlinked_species'])
        self.assertEqual(360, coverage['reference_species'])
        self.assertEqual(3624, len(self.index['references']) + sum(coverage['excluded_reasons'].values()))
        self.assertEqual(7507, len(self.index['taxa']))
        self.assertTrue(all(r['taxonomy_category_raw'] == 'NE' for r in self.index['references'].values()))
        self.assertFalse(set(self.index['taxa']) & set(self.index['references']))
        for key, record in self.index['references'].items():
            taxon = LineageTaxon(key, 'species', record['scientific_name'], record['authority'])
            lineage = replace(self.lineage, items=(taxon,))
            result = c.reference_checklist(lineage, {**self.snapshot, 'category_raw':record['taxonomy_category_raw']})
            self.assertIsNotNone(result, key)
            self.assertFalse(result['independently_verified'])


if __name__ == '__main__':
    unittest.main()
