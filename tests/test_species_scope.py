import importlib.util
import json
from pathlib import Path
from unittest import TestCase, mock, skipUnless

from robingraph.retrieval import species_scope
from robingraph.retrieval.species_scope import (
    distribution_for, scope_matches, scope_query_parameters, with_species_scope)

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / 'scripts' / 'build_species_distribution.py'
AVILIST = Path('/tmp/rg406-avilist.json')
CONCEPT, RELEASE = 'rg:concept-set:avilist-v2025b', 'v2025b'
_spec = importlib.util.spec_from_file_location('build_species_distribution', BUILDER_PATH)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


def taxon(taxon_id, scientific_name, **extra):
    return {'taxon_id': f'avilist-taxon:v2025b:{taxon_id}', 'rank': 'species',
            'scientific_name': scientific_name, **extra}


def status(item):
    return distribution_for(item, CONCEPT, RELEASE)


class KoreaRangeTextTest(TestCase):
    def test_plain_korea_peninsula_and_south_mentions_are_accepted(self):
        for text in ('Manchuria, Korea, and China to southern India',
                     'breeds northeastern China, Korea, and Japan',
                     'southern Japan (Honshu, Shikoku, and Kyushu) and Korea (Jeju Islands)',
                     'breeds very locally islets off coastal eastern China and southwestern South Korea',
                     'breeds eastern Siberia to Japan and Korea; winters to southern China and Indochina',
                     'northeastern China (southern Manchuria) to the Korean Peninsula'):
            with self.subTest(text=text):
                self.assertEqual((True, []), builder.korea_text_review(text))

    def test_north_directional_waters_and_uncertain_wording_fail_closed(self):
        for text, reason in (
                ('southern Amurland to northern Korea', 'north_qualified'),
                ('Russian Far East, North Korea, and northeastern China', 'north_qualified'),
                ('breeds northeastern China and far northeastern Korea', 'north_qualified'),
                ('northeastern China and northern Korean Peninsula', 'north_qualified'),
                ('lower Amur River and Sakhalin to N Korea', 'north_qualified'),
                ('Ullung Island (off eastern Korea)', 'non_south_directional_qualifier'),
                ('southern and central Korea and eastern China', 'non_south_directional_qualifier'),
                ('winters to Japanese and Korean waters', 'ambiguous_korean_mention'),
                ('Altai Mountains to northern China, Sea of Okhotsk, Korea, and Japan', 'surrounding_waters_ambiguous'),
                ('formerly Siberia and Korea; probably extinct, last reported 1916',
                 'negation_past_introduced_or_uncertain_wording'),
                ('Korea; introduced Hawaii', 'negation_past_introduced_or_uncertain_wording'),
                ('Mongolia (and possibly Korea)', 'negation_past_introduced_or_uncertain_wording'),
                ('vagrant to Korea', 'negation_past_introduced_or_uncertain_wording'),
                ('Korea?', 'negation_past_introduced_or_uncertain_wording')):
            with self.subTest(text=text):
                accepted, reasons = builder.korea_text_review(text)
                self.assertFalse(accepted)
                self.assertIn(reason, reasons)
        self.assertEqual((False, ['no_korea_text']), builder.korea_text_review('North Island (New Zealand)'))
        self.assertEqual((False, ['no_korea_text']), builder.korea_text_review(None))


class DistributionBundleTest(TestCase):
    def test_counts_are_consistent_and_outside_is_only_the_reviewed_list(self):
        data = species_scope._bundle()
        counts, taxa = data['counts'], data['taxa']
        self.assertEqual(counts['korea'], counts['korea_kos_only'] + counts['korea_avilist_only'] + counts['korea_both'])
        self.assertEqual(counts['active_species'], counts['korea'] + counts['outside'] + counts['unknown'])
        self.assertEqual(len(taxa), counts['korea'] + counts['outside'])
        reviewed = {builder.taxon_id(sequence): science for sequence, science, _ in builder.REVIEWED_OUTSIDE}
        self.assertEqual(reviewed, {k: v['scientific_name'] for k, v in taxa.items() if v['status'] == 'outside'})
        self.assertEqual((CONCEPT, RELEASE, 'KR'),
                         (data['concept_set_id'], data['taxonomy_release'], data['geographic_scope']))
        self.assertEqual(builder.AVILIST_SHA256, data['sources']['avilist-v2025b']['sha256'])
        self.assertIsNone(data['sources']['kos-2025-v2.1']['license_name'])
        self.assertTrue(data['generator']['sha256'] and data['inputs']['species_ko_names']['sha256'])
        for entry in taxa.values():
            for evidence in entry['evidence']:
                self.assertTrue(evidence['source_url'].startswith('https://'))
                self.assertTrue(evidence['source_sha256'] and evidence['geography_basis'])
                if evidence['source_id'] == 'avilist-v2025b':
                    self.assertEqual(builder.sha256(evidence['source_text']), evidence['source_text_sha256'])

    def test_kos_ga1_record_is_korea_any_season_never_residency(self):
        result = status(taxon(26900, 'Turdus hortulorum'))  # AviList text is north-qualified only
        self.assertEqual(('korea', 'source_record_korea', None),
                         (result['status'], result['basis'], result['seasonal_status']))
        self.assertEqual('가-1', result['evidence'][0]['category'])
        self.assertIn('텃새·철새·미조 구분', result['note'])
        self.assertEqual('korea', status(taxon(389, 'Tadorna cristata'))['status'])  # historical KOS record
        self.assertEqual('source_record_and_range_korea', status(taxon(306, 'Branta bernicla'))['basis'])

    def test_direct_subspecies_range_supports_species_without_kos_match(self):
        result = status(taxon(27988, 'Saxicola maurus'))
        self.assertEqual(('korea', 'source_range_korea'), (result['status'], result['basis']))
        self.assertEqual([('subspecies', 'Saxicola maurus stejnegeri', 'avilist-taxon:v2025b:27994')],
                         [(e['source_rank'], e['source_scientific_name'], e['source_taxon_id'])
                          for e in result['evidence']])

    def test_north_korea_only_korean_name_only_and_absent_text_stay_unknown(self):
        data = species_scope._bundle()
        self.assertEqual(['kos_ga2_north_korea_only'],
                         data['unknown_audit']['avilist-taxon:v2025b:30854']['reasons'])
        for item in (taxon(30854, 'Emberiza jankowskii'),   # KOS 가-2
                     taxon(312, 'Branta canadensis', korean_name='캐나다기러기'),  # IOC Korean name only
                     taxon(31, 'Apteryx australis')):        # no Korea text, not reviewed
            with self.subTest(item=item['scientific_name']):
                result = status(item)
                self.assertEqual(('unknown', [], None), (result['status'], result['evidence'], result['seasonal_status']))
                self.assertIn('국외 분포라는 뜻은 아닙니다', result['note'])

    def test_reviewed_outside_is_regular_range_not_absence_of_vagrants(self):
        result = status(taxon(33, 'Apteryx mantelli'))
        self.assertEqual(('outside', 'reviewed_source_range_outside_kr'), (result['status'], result['basis']))
        self.assertEqual('North Island (New Zealand)', result['evidence'][0]['source_text'])
        self.assertIn('not an independent human review', result['evidence'][0]['review'])
        self.assertIn('우연한 도래나 사육 기록이 없다는 뜻은 아닙니다', result['note'])


class ScopeContractTest(TestCase):
    def test_identity_rank_and_context_mismatches_are_unknown(self):
        self.assertEqual('identity_mismatch', status(taxon(26900, 'Turdus obscurus'))['basis'])
        self.assertEqual('species_rank_only',
                         status({**taxon(26900, 'Turdus hortulorum'), 'rank': 'subspecies'})['basis'])
        for concept, release in ((CONCEPT, 'v2026a'), ('rg:concept-set:other', RELEASE)):
            with self.subTest(concept=concept, release=release):
                result = distribution_for(taxon(26900, 'Turdus hortulorum'), concept, release)
                self.assertEqual(('unknown', 'no_current_distribution_context'), (result['status'], result['basis']))
        # A context-free candidate with only rank/id/science still resolves.
        self.assertEqual('korea', status({'taxon_id': 'avilist-taxon:v2025b:20193', 'scientific_name': 'Pica serica'})['status'])

    def test_unreadable_or_invalid_bundle_never_invents_status(self):
        species_scope._bundle.cache_clear()
        try:
            with mock.patch.object(species_scope.Path, 'read_text', return_value=json.dumps({'schema_version': 2})):
                self.assertEqual('no_current_distribution_context', status(taxon(26900, 'Turdus hortulorum'))['basis'])
                self.assertEqual({'species_scope': 'korea', 'scope_known': {}, 'scope_selected': {}},
                                 scope_query_parameters('korea', CONCEPT, RELEASE))
        finally:
            species_scope._bundle.cache_clear()

    def test_with_species_scope_copies_and_picks_display_name_by_scope(self):
        item = taxon(20193, 'Pica serica', korean_name='까치', english_name='Oriental magpie')
        result = with_species_scope(item, 'all', CONCEPT, RELEASE)
        self.assertNotIn('distribution', item)
        self.assertEqual(('까치', 'korea'), (result['display_name'], result['distribution']['status']))
        self.assertEqual('까치', with_species_scope(item, 'korea', CONCEPT, RELEASE)['display_name'])
        self.assertEqual('Oriental magpie', with_species_scope(item, 'outside', CONCEPT, RELEASE)['display_name'])
        kiwi = taxon(33, 'Apteryx mantelli', korean_name=None, english_name=None)
        self.assertEqual('Apteryx mantelli', with_species_scope(kiwi, 'outside', CONCEPT, RELEASE)['display_name'])
        self.assertEqual('까치', with_species_scope({**item, 'english_name': ''}, 'outside', CONCEPT, RELEASE)['display_name'])
        for bad in ('KR', None, ''):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                with_species_scope(item, bad, CONCEPT, RELEASE)

    def test_scope_matches_each_scope(self):
        korea, kiwi, other = taxon(26900, 'Turdus hortulorum'), taxon(33, 'Apteryx mantelli'), taxon(31, 'Apteryx australis')
        expected = {'all': (True, True, True), 'korea': (True, False, False),
                    'outside': (False, True, False), 'unknown': (False, False, True)}
        for scope, values in expected.items():
            with self.subTest(scope=scope):
                self.assertEqual(values, tuple(scope_matches(t, scope, CONCEPT, RELEASE) for t in (korea, kiwi, other)))
        with self.assertRaises(ValueError):
            scope_matches(korea, 'everything', CONCEPT, RELEASE)

    def test_query_parameters_reproduce_the_cypher_predicate(self):
        def cypher(params, peer):
            scope, known, selected = params['species_scope'], params['scope_known'], params['scope_selected']
            return (scope == 'all' or (scope == 'unknown' and known.get(peer['id'], '') != peer['scientific_name'])
                    or selected.get(peer['id']) == peer['scientific_name'])
        peers = [{'id': 'avilist-taxon:v2025b:26900', 'scientific_name': 'Turdus hortulorum'},
                 {'id': 'avilist-taxon:v2025b:26900', 'scientific_name': 'Turdus obscurus'},  # changed identity
                 {'id': 'avilist-taxon:v2025b:33', 'scientific_name': 'Apteryx mantelli'},
                 {'id': 'avilist-taxon:v2025b:31', 'scientific_name': 'Apteryx australis'}]
        for scope in species_scope.SPECIES_SCOPES:
            params = scope_query_parameters(scope, CONCEPT, RELEASE)
            with self.subTest(scope=scope):
                self.assertEqual([scope_matches({**p, 'taxon_id': p['id']}, scope, CONCEPT, RELEASE) for p in peers],
                                 [cypher(params, p) for p in peers])
        counts = species_scope._bundle()['counts']
        self.assertEqual({'species_scope': 'all', 'scope_known': {}, 'scope_selected': {}},
                         scope_query_parameters('all', CONCEPT, RELEASE))
        self.assertEqual(counts['korea'], len(scope_query_parameters('korea', CONCEPT, RELEASE)['scope_selected']))
        unknown = scope_query_parameters('unknown', CONCEPT, RELEASE)
        self.assertEqual(({}, counts['korea'] + counts['outside']), (unknown['scope_selected'], len(unknown['scope_known'])))
        self.assertEqual({'species_scope': 'korea', 'scope_known': {}, 'scope_selected': {}},
                         scope_query_parameters('korea', CONCEPT, 'v2026a'))
        with self.assertRaises(ValueError):
            scope_query_parameters('KR', CONCEPT, RELEASE)


class BuilderReproducibilityTest(TestCase):
    def test_changed_avilist_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            builder.build(b'[]', {})

    @skipUnless(AVILIST.exists(), 'pinned AviList snapshot /tmp/rg406-avilist.json not available')
    def test_bundle_is_reproducible_from_pinned_inputs(self):
        self.assertEqual(0, builder.main(['--avilist', str(AVILIST), '--check']))
