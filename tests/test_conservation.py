"""Exercise concept boundaries against the bundled real public source index."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from robingraph.retrieval import conservation as c
from robingraph.retrieval.species_profile import read_conservation
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


class PublicConservationTest(unittest.TestCase):
    def setUp(self):
        self.index = deepcopy(c._index())
        self.taxon_id, self.record = next((key, value) for key, value in self.index['taxa'].items()
                                        if value['scientific_name'] == 'Anas platyrhynchos')
        self.lineage = TaxonomyLineage('청둥오리', 'AviList', 'v2025b',
            'rg:concept-set:avilist-v2025b', (LineageTaxon(self.taxon_id, 'species',
                self.record['scientific_name'], self.record['authority'], '청둥오리'),))
        self.snapshot = dict(category='LC', category_raw=self.record['taxonomy_category_raw'],
            evidence_kind='taxonomy_snapshot', snapshot_sha256=c.TAXONOMY_SHA256,
            assessment_reference_url=self.record['mapping_reference_url'])

    def test_actual_public_record_preserves_assessment_and_source_years(self):
        result = c.linked_checklist(self.lineage, self.snapshot)
        self.assertEqual('LC', result['category'])
        self.assertEqual('linked_checklist', result['assessment_status'])
        self.assertFalse(result['independently_verified'])
        self.assertEqual(2025, result['assessment_year'])
        self.assertEqual('2026-1', result['source_release'])
        self.assertEqual('https://www.iucnredlist.org/species/22680186/281835571', result['assessment_reference_url'])
        self.assertEqual('CC BY 4.0', result['license_name'])
        self.assertNotIn('assessment_date', result)

    def test_changed_active_concept_or_identity_never_inherits_grade(self):
        for lineage in (replace(self.lineage, taxonomy_release='v2026'),
                        replace(self.lineage, concept_set_id='other'),
                        replace(self.lineage, taxonomy_source='other'),
                        replace(self.lineage, items=(replace(self.lineage.items[0], scientific_name='Anas other'),)),
                        replace(self.lineage, items=(replace(self.lineage.items[0], authority='Linnaeus, C, 1800'),)),
                        replace(self.lineage, items=(replace(self.lineage.items[0], rank='subspecies'),))):
            with self.subTest(lineage=lineage):
                self.assertIsNone(c.linked_checklist(lineage, self.snapshot))
        for override in ({'category':'NE'}, {'snapshot_sha256':'a'*64},
                         {'snapshot_sha256':None}, {'category_raw':'CR (PE)'},
                         {'assessment_reference_url':'https://datazone.birdlife.org/species/factsheet/123'}):
            with self.subTest(override=override):
                self.assertIsNone(c.linked_checklist(self.lineage, {**self.snapshot, **override}))

    def test_corrupt_or_untrusted_artifact_fails_closed(self):
        variants = []
        for key, value in [('schema_version', 2), ('mapping_method', 'fuzzy_name'),
                           ('taxonomy_snapshot_sha256', 'a'*64), ('taxa', [])]:
            index = deepcopy(self.index); index[key] = value; variants.append(index)
        for key, value in [('url', 'https://www.gbif.org/dataset/other'),
                           ('license_name', 'CC BY-NC'), ('snapshot_sha256', 'a'*64),
                           ('publisher', 'Other'), ('release', '2025-2')]:
            index = deepcopy(self.index); index['source'][key] = value; variants.append(index)
        for key, value in [('assessment_id', True), ('sis_id', '123'),
                           ('assessment_reference_url', 'https://evil.test/species/1/2'),
                           ('assessment_year', 2026), ('assessment_citation', 'No verified identifier'),
                           ('category', 'NE'), ('authority_match_method', 'fuzzy'),
                           ('assessment_authority', 'Linnaeus, 1800')]:
            index = deepcopy(self.index); index['taxa'][self.taxon_id][key] = value; variants.append(index)
        for index in variants:
            with self.subTest(index=variants.index(index)), patch.object(c, '_index', return_value=index):
                self.assertIsNone(c.linked_checklist(self.lineage, self.snapshot))

    def test_repository_uses_primary_only_after_trusted_snapshot(self):
        repository = Mock()
        row = {'category_raw':self.snapshot['category_raw'],
               'source_name':'AviList global avian checklist',
               'source_url':'https://explore.avilist.org/data/avilist-2025b.json',
               'source_release':'v2025b', 'source_id':'avilist-v2025b',
               'snapshot_sha256':c.TAXONOMY_SHA256,
               'assessment_reference_url':self.snapshot['assessment_reference_url']}
        repository._run.return_value = [row]
        self.assertEqual('red_list_checklist', read_conservation(repository, self.lineage)['evidence_kind'])
        repository._run.return_value = [{**row, 'category_raw':'NE'}]
        self.assertEqual('needs_review', read_conservation(repository, self.lineage)['assessment_status'])
        repository._run.return_value = [{**row, 'source_id':'untrusted'}]
        self.assertIsNone(read_conservation(repository, self.lineage)['category'])
        repository._run.return_value = [row]
        with patch.object(c, '_index', return_value={}):
            self.assertEqual('snapshot_only', read_conservation(repository, self.lineage)['assessment_status'])

    def test_ne_magpie_is_not_mapped_by_name(self):
        self.assertFalse(any(row['scientific_name'] == 'Pica serica' for row in self.index['taxa'].values()))
        taxon = replace(self.lineage.items[0], taxon_id='unknown', scientific_name='Pica serica')
        self.assertIsNone(c.linked_checklist(replace(self.lineage, items=(taxon,)), self.snapshot))

    def test_real_ingest_trim_preserves_original_category_provenance(self):
        taxon_id, record = next((key, value) for key, value in self.index['taxa'].items()
                               if value['scientific_name'] == 'Pericrocotus albifrons')
        self.assertEqual('LC ', record['taxonomy_category_raw'])
        taxon = LineageTaxon(taxon_id, 'species', record['scientific_name'], record['authority'])
        lineage = replace(self.lineage, items=(taxon,))
        snapshot = {**self.snapshot, 'category_raw':'LC',
                    'assessment_reference_url':record['mapping_reference_url']}
        primary = c.linked_checklist(lineage, snapshot)
        self.assertEqual('red_list_checklist', primary['evidence_kind'])
        self.assertEqual('LC ', primary['taxonomy_category_raw'])

    def test_manual_magpie_display_preserves_unverified_original_and_scope(self):
        taxon = LineageTaxon('avilist-taxon:v2025b:20193', 'species', 'Pica serica', 'Gould, J, 1845')
        lineage = replace(self.lineage, items=(taxon,))
        snapshot = {**self.snapshot, 'category':'NE', 'category_raw':'NE',
                    'assessment_status':'needs_review'}
        result = c.manual_magpie_override(lineage, snapshot)
        self.assertEqual('LC', result['category'])
        self.assertEqual('manual_override', result['evidence_kind'])
        self.assertEqual('NE', result['original_snapshot']['category'])
        self.assertFalse(result['independently_verified'])
        self.assertIsNone(result['source_url'])
        self.assertNotIn('assessment_year', result)
        self.assertNotIn('assessment_reference_url', result)
        for changed in (replace(lineage, taxonomy_release='v2026'),
                        replace(lineage, concept_set_id='other'),
                        replace(lineage, items=(replace(taxon, taxon_id='other'),)),
                        replace(lineage, items=(replace(taxon, scientific_name='Pica pica'),)),
                        replace(lineage, items=(replace(taxon, rank='subspecies'),))):
            self.assertIsNone(c.manual_magpie_override(changed, snapshot))
        self.assertIsNone(c.manual_magpie_override(lineage, {**snapshot, 'category':'LC'}))
        self.assertIsNone(c.manual_magpie_override(lineage, {**snapshot, 'snapshot_sha256':'a'*64}))

    def test_repository_applies_only_magpie_manual_display(self):
        taxon = LineageTaxon('avilist-taxon:v2025b:20193', 'species', 'Pica serica', 'Gould, J, 1845')
        lineage = replace(self.lineage, items=(taxon,))
        row = dict(category_raw='NE', source_name='AviList global avian checklist',
                   source_url='https://explore.avilist.org/data/avilist-2025b.json',
                   source_id='avilist-v2025b', source_release='v2025b',
                   snapshot_sha256=c.TAXONOMY_SHA256)
        repository = Mock(); repository._run.return_value = [row]
        result = read_conservation(repository, lineage)
        self.assertEqual('LC', result['category'])
        self.assertEqual(row['source_url'], result['original_snapshot']['source_url'])
        self.assertEqual('needs_review', result['original_snapshot']['assessment_status'])
        other = replace(lineage, items=(replace(taxon, taxon_id='other', scientific_name='Aegithalos concinnus'),))
        self.assertEqual('NE', read_conservation(repository, other)['category'])
