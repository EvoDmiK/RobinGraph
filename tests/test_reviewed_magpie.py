from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
import json
from pathlib import Path
import subprocess
import sys

from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon
from robingraph.retrieval.reviewed_magpie import reviewed_magpie_traits, reviewed_magpie_notes, MASS_SHA256
from robingraph.retrieval.species_profile import create_species_flow

LINEAGE = TaxonomyLineage('Pica serica', 'AviList', 'v2025b',
    'rg:concept-set:avilist-v2025b', (LineageTaxon('avilist-taxon:v2025b:20193',
        'species', 'Pica serica', 'Gould, J, 1845', '까치', english_name='Oriental magpie'),))


class ReviewedMagpieTest(TestCase):
    def test_pinned_public_supplement_reproduces_displayed_mass(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads(subprocess.check_output([sys.executable,
            str(root/'scripts/verify_reviewed_magpie_mass.py'),
            str(root/'docs/verification/assets/2026-10-09-pica-serica-mass-source.xlsx')]))
        mass = next(t for t in reviewed_magpie_traits(LINEAGE, []) if t['name']=='body_mass')
        self.assertEqual(data['sample_mean'], mass['value'])
        self.assertEqual(data['sample_size'], mass['sample_size'])
        self.assertEqual(data['source_sha256'], mass['source_snapshot_sha256'])

    def test_research_mass_has_sample_scope_and_attribution(self):
        traits = reviewed_magpie_traits(LINEAGE, [])
        mass = next(t for t in traits if t['name'] == 'body_mass')
        self.assertEqual(220.64, mass['value'])
        self.assertEqual('sample_mean', mass['summary_statistic'])
        self.assertEqual(115, mass['sample_size'])
        self.assertIn('2008년 3월', mass['source_scope'])
        self.assertEqual('CC BY 4.0', mass['license_name'])
        self.assertEqual(MASS_SHA256, mass['source_snapshot_sha256'])
        self.assertTrue(all(t['source_url'].startswith('https://') and t['citation'] for t in traits))

    def test_other_species_and_contexts_do_not_inherit_facts(self):
        for changed in (replace(LINEAGE, taxonomy_release='v2026'),
                        replace(LINEAGE, concept_set_id='other'),
                        replace(LINEAGE, taxonomy_source='other'),
                        replace(LINEAGE, items=(replace(LINEAGE.items[0], scientific_name='Pica pica'),)),
                        replace(LINEAGE, items=(replace(LINEAGE.items[0], taxon_id='other'),)),
                        replace(LINEAGE, items=(replace(LINEAGE.items[0], rank='subspecies'),))):
            self.assertEqual([], reviewed_magpie_traits(changed, []))
            self.assertEqual({}, reviewed_magpie_notes(changed))

    def test_existing_active_mass_is_preserved_and_results_are_isolated(self):
        existing = {'name':'body_mass', 'value':250, 'source_url':'https://example.com'}
        result = reviewed_magpie_traits(LINEAGE, [existing])
        self.assertEqual([existing], [t for t in result if t['name']=='body_mass'])
        result[-1]['citation'] = 'changed'
        self.assertNotEqual('changed', reviewed_magpie_traits(LINEAGE, [])[-1]['citation'])

    def test_basic_and_full_profiles_have_facts_without_external_notes(self):
        for enrichment in (False, True):
            notes = Mock(side_effect=TimeoutError('provider unavailable'))
            flow = create_species_flow(lambda _:LINEAGE, lambda _:[], photos=lambda _:[],
                                       notes=notes, include_enrichment=enrichment)
            profile = flow.invoke('까치')
            notes.assert_not_called()
            self.assertEqual(4, len(profile['traits']))
            self.assertIn('연구 표본 평균', profile['summary'])
            self.assertIn('220.64', profile['summary'])
            self.assertEqual([], profile['warnings'])
            self.assertTrue(all(section['items'] for section in profile['sections']))

    def test_trait_provider_failure_still_keeps_reviewed_facts(self):
        flow = create_species_flow(lambda _:LINEAGE, Mock(side_effect=TimeoutError()),
                                   photos=lambda _:[], include_enrichment=False)
        profile = flow.invoke('까치')
        self.assertEqual(4, len(profile['traits']))
        self.assertIn('종 특성 제공처를 현재 조회할 수 없습니다.', profile['warnings'])
