"""Bounded source concepts must never masquerade as full-species averages."""
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from robingraph.retrieval import avonet_subgroups as ag
from robingraph.retrieval.species_profile import LABELS, trait_display, species_summary, species_sections
from tests.test_trait_mapping import context, lineage


def target(name):
    return lineage(next(e for entries in ag.subgroup_index().values() for e in entries if e['target_name'] == name))


def traits(name, existing=None):
    return ag.subgroup_traits(target(name), existing or [], context('avonet'), LABELS, trait_display)


class AvonetSubgroupsTests(TestCase):
    def test_pinned_real_relationships(self):
        index = ag.subgroup_index()
        self.assertEqual(len(index), 356)
        self.assertEqual(sum(map(len, index.values())), 708)
        for name in ['Parus cinereus', 'Corypha somalica', 'Dicrurus sharpei', 'Nannopsittacus nigrifrons']:
            for trait in traits(name):
                self.assertEqual(trait['source_scope_kind'], 'subspecies_group')
                self.assertEqual(trait['taxonomy_alignment']['status'], 'reference_subgroup')
                self.assertTrue(trait['summary_statistic'].startswith('subgroup_'))
                self.assertIn('현재 종 전체', trait['source_note'])
                self.assertEqual(trait['mapping_provenance']['relationship_source_sha256'], ag.EBIRD_SHA256)

    def test_parus_uses_cinereus_group_not_major_or_unmatched_minor(self):
        values = traits('Parus cinereus')
        mass = next(t for t in values if t['name'] == 'body_mass')
        self.assertEqual(mass['value'], 14.4)
        self.assertEqual(mass['source_scope'], 'Parus cinereus [cinereus Group]')
        self.assertEqual(mass['summary_statistic'], 'subgroup_mean')
        self.assertNotIn('sample_size', mass)
        self.assertEqual(mass['source_morphology_sample_size'], 8)
        self.assertIn('체중 문헌의 표본수가 아닙니다', mass['source_note'])
        self.assertEqual(mass['mapping_provenance']['source_avibase_id'], 'avibase-99cf4a04')
        self.assertEqual(mass['mapping_provenance']['target_avibase_id'], 'avibase-414dc961')

    def test_distinct_subgroups_not_averaged_or_first_selected(self):
        values = traits('Dicrurus sharpei')
        masses = [t for t in values if t['name'] == 'body_mass']
        self.assertEqual(len(masses), 2)
        self.assertEqual({t['source_scope'] for t in masses}, {'Dicrurus sharpei sharpei', 'Dicrurus sharpei occidentalis'})
        summary = species_summary({'scientific_name': 'Dicrurus sharpei'}, values)
        self.assertNotIn('체중은', summary)
        self.assertNotIn('아종군', summary)
        sections = species_sections({'scientific_name': 'Dicrurus sharpei'}, values, {})
        basic = next(s for s in sections if s['key'] == 'basic')['items']
        self.assertEqual(len(basic), 1)
        reference = next(s for s in sections if s['key'] == 'subspecies_groups')
        self.assertEqual(sum(item['name'] == 'body_mass' for item in reference['items']), 2)
        self.assertTrue(reference['collapsed'])
        self.assertEqual(len(reference['items']), len(values))

    def test_existing_primary_fields_win_for_every_subgroup(self):
        existing = {'name': 'body_mass', 'value': 22.0, 'inferred': False}
        self.assertEqual([t for t in traits('Parus cinereus', [existing]) if t['name'] == 'body_mass'], [existing])

    def test_reject_wrong_context_identity_and_tampered_extract(self):
        lin = target('Parus cinereus')
        self.assertEqual(ag.subgroup_traits(lin, [], None, LABELS, trait_display), [])
        self.assertEqual(ag.subgroup_traits(replace(lin, taxonomy_release='other'), [], context('avonet'), LABELS, trait_display), [])
        ag.subgroup_index.cache_clear()
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            self.assertEqual(ag.subgroup_index(), {})
        ag.subgroup_index.cache_clear()

    def test_generator_rejects_slash_and_conflicting_report_as(self):
        import sys
        sys.path.insert(0, str(Path('scripts').resolve()))
        from build_avonet_subgroup_supplement import build
        a = [{'Taxon_rank': 'species', 'Sequence': '1', 'Scientific_name': 'Target species', 'AvibaseID': 'avibase-12345678'}]
        eb = [{'category': 'species', 'species_code': 'target', 'bio_concept_code': 'avibase-avibase-12345678'},
              {'category': 'issf', 'species_code': 'group', 'bio_concept_code': 'avibase-avibase-abcdef12',
               'report_as': 'target', 'sci_name': 'Target species group', 'primary_com_name': 'Group'}]
        row = {'Avibase.ID2': 'AVIBASE-abcdef12', 'Species2': 'Old species', '_row': 2, 'Inference': 'NO'}
        sheets = {'AVONET1_BirdLife': [], 'AVONET2_eBird': [row]}
        self.assertEqual(len(build(a, eb, sheets)['entries']), 1)
        self.assertEqual(build(a, eb + [eb[0]], sheets)['entries'], [])
        eb[1]['category'] = 'slash'
        self.assertEqual(build(a, eb, sheets)['entries'], [])

    def test_subgroup_categories_never_create_species_ecological_edges(self):
        from unittest.mock import Mock
        from robingraph.retrieval.ecological_relations import ecological_relations
        from tests.test_ecological_relations import LINEAGE, trait
        repo = Mock()
        with patch('robingraph.retrieval.ecological_relations.read_traits', return_value=[trait(source_scope_kind='subspecies_group')]):
            self.assertEqual(ecological_relations(repo, Mock(), lambda _: LINEAGE, 'x')['groups'], [])
        repo._run.assert_not_called()

    def test_subgroup_categories_never_add_species_similarity_bonus(self):
        from unittest.mock import Mock
        from robingraph.retrieval.similar_species import similar_species
        from tests.test_similar_species import FakeRepository, candidate, LINEAGE, HABITAT
        repo = FakeRepository([candidate('good', 'Good bird', True, True)], [])
        with patch('robingraph.retrieval.similar_species.read_traits', return_value=[{**HABITAT, 'source_scope_kind': 'subspecies_group'}]):
            result = similar_species(repo, Mock(), lambda _: LINEAGE, 'x')
        self.assertFalse(any('UNWIND $categories' in query for query, _ in repo.calls))
        self.assertEqual(result['groups'][0]['items'][0]['similarity_score'], 60)
