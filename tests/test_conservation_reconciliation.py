"""Independent evidence boundaries and real pinned ALL-species reconciliation."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load('audit_reconciliation', ROOT / 'scripts/audit_conservation_reconciliation.py')
fixtures = load('conservation_fixtures', ROOT / 'tests/test_conservation_index.py')


class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ConservationIndexTest()
        self.fixture.setUp()

    def run_audit(self):
        taxonomy = json.dumps(self.fixture.avilist).encode()
        archive = self.fixture.source_bytes()
        a, b = sha256(taxonomy).hexdigest(), sha256(archive).hexdigest()
        with patch.object(audit.builder, 'AVILIST_SHA256', a), patch.object(audit.builder, 'SOURCE_SHA256', b), \
             patch.object(audit.conservation, 'TAXONOMY_SHA256', a), patch.object(audit.conservation, 'SOURCE_SHA256', b):
            return audit.reconcile(taxonomy, archive)

    def test_ne_reference_is_exposed_without_category_inheritance_or_equivalence(self):
        self.fixture.avilist[0][15] = 'NE'
        self.fixture.avilist[0][16] = None
        result = self.run_audit()
        row = result['species'][0]
        self.assertEqual('NE', row['current_status']['category'])
        self.assertEqual('needs_review', row['current_status']['assessment_status'])
        self.assertEqual(['LC'], row['reference_candidates'][0]['global_categories'])
        self.assertTrue(row['reference_candidates'][0]['evidence_integrity_valid'])
        self.assertFalse(row['auto_upgrade_authorized'])
        self.assertFalse(row['safe_independent_same_concept_evidence'])
        self.assertEqual('unverified', row['reference_candidates'][0]['concept_alignment'])
        self.assertEqual(1, result['denominators']['ne_subset'])

    def test_author_mismatch_does_not_count_as_safe_structural_identity(self):
        self.fixture.avilist[0][15] = 'NE'
        self.fixture.avilist[0][6] = 'Other, 1758'
        row = self.run_audit()['species'][0]
        self.assertEqual('same_name_or_sis_reference_with_identity_or_integrity_gap', row['ne_evidence_category'])
        self.assertIsNone(row['reference_candidates'][0]['authorship_match_method'])

    def test_duplicate_name_keeps_both_candidates_and_ambiguity(self):
        self.fixture.avilist[0][15] = 'NE'
        other = deepcopy(self.fixture.core[0])
        other[0] = other[13] = '99'
        self.fixture.core.append(other)
        row = self.run_audit()['species'][0]
        self.assertEqual(2, row['reference_candidate_count'])
        self.assertEqual('ambiguous_reference_candidates', row['ne_evidence_category'])
        self.assertTrue(row['ambiguity']['multiple_reference_rows'])

    def test_duplicate_sis_does_not_silently_overwrite(self):
        self.fixture.avilist[0][15] = 'NE'
        self.fixture.core.append(deepcopy(self.fixture.core[0]))
        row = self.run_audit()['species'][0]
        self.assertEqual(2, row['reference_candidate_count'])
        self.assertTrue(all('duplicate_source_sis_id' in r['evidence_integrity_failures'] for r in row['reference_candidates']))

    def test_citation_mismatch_keeps_raw_grade_but_rejects_integrity(self):
        self.fixture.avilist[0][15] = 'NE'
        self.fixture.distributions[0][3] = 'different'
        row = self.run_audit()['species'][0]
        self.assertEqual('reference_integrity_gap', row['reference_comparison_category'])
        self.assertEqual(['LC'], row['reference_candidates'][0]['global_categories'])
        self.assertFalse(row['reference_candidates'][0]['evidence_integrity_valid'])

    def test_year_parentheses_are_not_discarded(self):
        for author in ('Linnaeus, 1759', '(Linnaeus, 1758)'):
            self.fixture.avilist[0][15] = 'NE'
            self.fixture.avilist[0][6] = author
            self.assertIsNone(self.run_audit()['species'][0]['reference_candidates'][0]['authorship_match_method'])

    def test_pins_checked_before_parsing(self):
        with self.assertRaisesRegex(ValueError, 'AviList snapshot changed'):
            audit.reconcile(b'[]', b'bad zip')

    def test_actual_pinned_all_species(self):
        av = Path('/tmp/robingraph-global-avilist-2025b.json')
        source = Path('/tmp/robingraph-alternative-sources/iucn-2026-1.zip')
        if not av.exists() or not source.exists():
            self.skipTest('Actual pinned input files unavailable; no substitute for integration evidence')
        result = audit.reconcile(av.read_bytes(), source.read_bytes())
        c = result['counts']
        self.assertEqual(11131, c['all_species'])
        self.assertEqual(11131, len({r['taxon_id'] for r in result['species']}))
        self.assertEqual(808, c['taxonomy_ne'])
        self.assertEqual({'mapped_species':7507, 'authority_mismatch':2286, 'scientific_name_mismatch':474,
                          'assessment_identity_or_citation_mismatch':56, 'avilist_ne_requires_concept_review':808}, c['current_mapping_categories'])
        self.assertEqual(360, c['ne_evidence_categories']['unique_integrity_valid_name_authorship_reference_concept_unverified'])
        self.assertEqual(118, c['ne_evidence_categories']['same_name_or_sis_reference_with_identity_or_integrity_gap'])
        self.assertEqual(330, c['ne_evidence_categories']['no_exact_name_or_sis_reference'])
        for key in ('current_mapping_categories', 'reference_comparison_categories'):
            self.assertEqual(11131, sum(c[key].values()))
        self.assertEqual(808, sum(c['ne_evidence_categories'].values()))
        crow = next(r for r in result['species'] if r['scientific_name'] == 'Corvus macrorhynchos')
        self.assertEqual('avilist-taxon:v2025b:20296', crow['taxon_id'])
        self.assertEqual('NE', crow['taxonomy_category_raw'])
        ref = crow['reference_candidates'][0]
        self.assertEqual(('103727590', 264280673, ['LC']), (ref['sis_id'], ref['assessment_id'], ref['global_categories']))
        self.assertEqual('single_author_initials_omitted', ref['authorship_match_method'])
        self.assertFalse(crow['safe_independent_same_concept_evidence'])


if __name__ == '__main__':
    unittest.main()
