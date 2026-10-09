"""Conservative reference expansion and whole unresolved-subset evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from robingraph.retrieval import conservation as c
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('unresolved_fixtures', ROOT / 'tests/test_conservation_index.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
spec = importlib.util.spec_from_file_location('unresolved_audit', ROOT / 'scripts/audit_unresolved_conservation.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReferenceNotationTest(unittest.TestCase):
    def test_only_initials_and_author_separators_relaxed_for_references(self):
        for left, right in (
            ('Sclater, PL; Salvin, O, 1868', 'Sclater & Salvin, 1868'),
            ('(Lesson, RP, 1832)', '(Lesson, R, 1832)'),
            ("(Salvadori, AT; d'Albertis, LM, 1875)", "(Salvadori & d'Albertis, 1875)"),
        ):
            with self.subTest(left=left):
                self.assertIsNone(c._authority_match(left, right))
                self.assertEqual('author_initials_normalized', c._reference_authority_match(left, right))
        for right in ('(Lesson, A, 1832)', '(Lesson, R, 1833)', 'Lesson, R, 1832', '(Other, R, 1832)',
                      '(Lesson, RPA, 1832)', '(Lesson & Other, 1832)'):
            self.assertIsNone(c._reference_authority_match('(Lesson, RP, 1832)', right))
        self.assertIsNone(c._reference_authority_match('Sclater, PL; Salvin, O, 1868', 'Salvin & Sclater, 1868'))

    def test_truncated_citation_requires_exact_name_authorship_and_canonical_url(self):
        citation = 'BirdLife International 2022. Lampornis castaneoventris (Gould, 1851). The IUCN Red List of Threatened Species 2022:'
        args = ('Lampornis castaneoventris', '(Gould, 1851)', citation,
                'https://www.iucnredlist.org/species/22725795/167021482', '22725795')
        self.assertEqual(('167021482', 'canonical_source_url_truncated_citation'), c._reference_assessment_identity(*args))
        self.assertIsNone(fixtures.builder._assessment_year(citation))
        for offset, value in ((0, 'Lampornis other'), (1, '(Other, 1851)'),
                              (2, citation.replace('Species 2022:', 'Species 2021:')),
                              (2, citation + ' https://doi.org/wrong'),
                              (3, args[3] + '?x=1'), (3, 'http://www.iucnredlist.org/species/22725795/167021482'),
                              (4, '1'), (3, None)):
            changed = list(args); changed[offset] = value
            self.assertIsNone(c._reference_assessment_identity(*changed))

    def test_builder_accepts_ne_reference_only_and_never_primary(self):
        f = fixtures.ConservationIndexTest(); f.setUp()
        f.avilist[0][15] = 'NE'; f.avilist[0][16] = None
        f.avilist[0][6] = '(Lesson, RP, 1832)'
        f.core[0][9] = '(Lesson, R, 1832)'
        index = f.build()
        self.assertEqual({}, index['taxa'])
        self.assertEqual('author_initials_normalized', index['references']['avilist-taxon:v2025b:1']['authority_match_method'])


class FullUnresolvedSourceTest(unittest.TestCase):
    def test_every_new_reference_passes_runtime_without_upgrading_avilist_ne(self):
        ledger = json.loads((ROOT / 'docs/verification/assets/2026-10-09-unresolved-conservation-review.json').read_text())
        added = [r for r in ledger['species'] if r['reference_added']]
        self.assertEqual(25, len(added))
        for row in added:
            lineage = TaxonomyLineage(row['scientific_name'], 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b',
                (LineageTaxon(row['taxon_id'], 'species', row['scientific_name'], row['authority']),))
            snapshot = dict(category=None, category_raw='NE', evidence_kind='taxonomy_snapshot',
                            assessment_status='needs_review', snapshot_sha256=c.TAXONOMY_SHA256)
            before = deepcopy(snapshot)
            ref = c.reference_checklist(lineage, snapshot)
            self.assertIsNotNone(ref, row['scientific_name'])
            self.assertEqual('reference_only', ref['assessment_status'])
            self.assertFalse(ref['independently_verified'])
            self.assertEqual('unverified', ref['taxonomy_alignment'])
            self.assertIsNone(c.linked_checklist(lineage, snapshot))
            self.assertEqual(before, snapshot)
            if ref['assessment_identity_method'] == 'canonical_source_url_truncated_citation':
                self.assertNotIn('assessment_year', ref)

    def test_complete_original_subset_has_distinct_outcomes_and_no_inherited_grades(self):
        ledger = json.loads((ROOT / 'docs/verification/assets/2026-10-09-unresolved-conservation-review.json').read_text())
        self.assertEqual(447, len(ledger['species']))
        self.assertEqual(447, len({r['taxon_id'] for r in ledger['species']}))
        self.assertEqual(447, sum(ledger['counts']['review_status'].values()))
        self.assertEqual(0, ledger['counts']['primary_grades_assigned'])
        for row in ledger['species']:
            self.assertFalse(row['primary_grade_assigned'])
            self.assertEqual('NE', row['taxonomy_category_raw'])
            for candidate in row['candidates']:
                self.assertFalse(candidate['assign_grade_to_target'])
                self.assertEqual('unverified', candidate['concept_alignment'])
        source_categories = {grade for row in ledger['species'] for candidate in row['candidates']
                             for grade in candidate['global_categories']}
        self.assertIn('EN', source_categories)
        self.assertIn('VU', source_categories)


if __name__ == '__main__':
    unittest.main()
