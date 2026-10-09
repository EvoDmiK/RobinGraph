"""All scoped taxa use the same narrative contract; no live LLM calls."""
import unittest
from robingraph.retrieval.avonet_subgroups import subgroup_index
from robingraph.retrieval.species_profile import species_sections, species_summary, create_species_flow
from tests.test_avonet_ebird import lineage


class NarrativeScopeTests(unittest.TestCase):
    def note(self, text='수컷의 머리는 검은색입니다.'):
        return {'text': text, 'source_name': 'Wikipedia · Bird', 'source_url': 'https://en.wikipedia.org/w/index.php?oldid=123',
                'source_scope_kind': 'encyclopedia_taxon',
                'taxonomy_alignment': {'status': 'article_identity_only'}, 'source_release': '123'}

    def test_all_356_pinned_species_bound_notes_even_without_fallback_traits(self):
        groups = list(subgroup_index().values())
        self.assertEqual(len(groups), 356)
        self.assertEqual(sum(len(group) > 1 for group in groups), 290)
        for group in groups:
            with self.subTest(name=group[0]['target_name']):
                sections = species_sections({'scientific_name': group[0]['target_name']}, [],
                                            {'appearance': [self.note()], 'fun_facts': [self.note('나무 구멍에 둥지를 만듭니다.')]})
                self.assertFalse(any(s['key'] in ('appearance', 'fun_facts') for s in sections))
                scoped = next(s for s in sections if s['key'] == 'source_scope_notes')
                self.assertEqual(len(scoped['items']), 2)
                self.assertTrue(scoped['collapsed'])
                self.assertTrue(all(n['taxonomy_alignment']['status'] == 'unverified' for n in scoped['items']))
                self.assertTrue(all(n['source_release'] == '123' for n in scoped['items']))

    def test_unbounded_control_and_exact_duplicate(self):
        # Deliberately outside the relationship artifact; source is still attributed.
        sections = species_sections({'scientific_name': 'Control species'}, [],
                                    {'appearance': [self.note(), self.note()], 'fun_facts': [self.note()]})
        self.assertEqual([s['key'] for s in sections], ['basic', 'appearance', 'ecology', 'fun_facts'])
        self.assertEqual(len(sections[1]['items']), 1)
        self.assertEqual(sections[3]['items'], [])

    def test_subgroup_reference_never_appears_in_species_sections(self):
        values = [{'name': 'body_mass', 'display': str(value), 'unit': 'g', 'source_scope': scope,
                   'source_scope_kind': 'subspecies_group', 'summary_statistic': 'subgroup_mean',
                   'source_name': 'AVONET', 'source_url': 'https://example.org/source',
                   'mapping_provenance': {'relationship_source_url': 'https://example.org/relation'},
                   'source_note': '원자료 참고', 'inferred': False}
                  for value, scope in ((12, 'Bird alpha'), (19, 'Bird beta'))]
        sections = species_sections({'scientific_name': 'Bird species'}, values, {})
        self.assertNotIn('12', species_summary({}, values))
        self.assertTrue(all(len(s['items']) == (1 if s['key'] == 'basic' else 0) for s in sections[:4]))
        self.assertEqual(len(sections), 4)

    def test_all_356_species_profiles_reject_injected_subgroup_traits(self):
        for entries in subgroup_index().values():
            entry = entries[0]
            with self.subTest(species=entry['target_name']):
                target = lineage(entry)
                primary = {'name': 'habitat', 'display': '숲', 'source_name': 'Species source',
                           'source_url': 'https://example.org/species'}
                scoped = [{'name': 'body_mass', 'display': '9999', 'unit': 'g',
                           'source_name': 'Subgroup source', 'source_url': 'https://example.org/subgroup',
                           'source_scope_kind': 'subspecies_group', 'source_scope': e['subgroup_name']}
                          for e in entries]
                flow = create_species_flow(lambda _: target, lambda _: [primary, *scoped],
                                           photos=lambda _: [], include_enrichment=False)
                profile = flow.invoke('query')
                self.assertEqual(profile['traits'], [primary])
                self.assertNotIn('9999', profile['summary'])
                self.assertFalse(any(s['key'] == 'subspecies_groups' for s in profile['sections']))
                self.assertFalse(any(item.get('source_scope_kind') == 'subspecies_group'
                                     for section in profile['sections'] for item in section['items']))

    def test_species_diet_only_once_and_metadata_kept(self):
        values = [{'name': name, 'display': '잡식', 'source_name': 'Dataset', 'source_url': 'https://example.org',
                   'source_note': '근거', 'inferred': True}
                  for name in ('diet_category', 'trophic_niche')]
        ecology = next(s for s in species_sections({}, values, {}) if s['key'] == 'ecology')['items']
        self.assertEqual(len(ecology), 1)
        self.assertEqual(ecology[0]['source_note'], '근거')
        self.assertIn('추정값', ecology[0]['text'])
