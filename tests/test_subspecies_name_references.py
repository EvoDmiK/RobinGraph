"""Generated subspecies English-name artifact: identity, provenance and conflict rejection.

Set ROBINGRAPH_SUBSPECIES_SOURCE_DIR to a directory holding the three pinned
source files (see SOURCES[...]['file'] in the builder) to also verify the
artifact against the real AviList release and to rebuild it byte-for-byte.
"""
import importlib.util
import json
import os
import re
from pathlib import Path
from unittest import TestCase, skipUnless

from robingraph.retrieval.taxonomy_lineage import SUBSPECIES_NAME_REFERENCES

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('subspecies_name_builder', ROOT / 'scripts/build_subspecies_names.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
ARTIFACT = ROOT / 'src/robingraph/retrieval/subspecies_name_references.json'
SOURCE_DIR = os.environ.get('ROBINGRAPH_SUBSPECIES_SOURCE_DIR')
ID_PATTERN = re.compile(r'avilist-taxon:v2025b:[1-9]\d*')
TRINOMIAL = re.compile(r'[A-Z][a-z]+ [a-z]+ [a-z]+')


def avilist_row(seq, rank, name, authority='', english='', order='Testiformes'):
    row = [None] * 26
    row[0], row[1], row[2], row[5], row[6], row[8] = str(seq), rank, order, name, authority, english or None
    return row


FIXTURE_ROWS = [
    avilist_row(1, 'species', 'Ardea cinerea', 'Linnaeus, 1758', 'Grey Heron'),
    avilist_row(2, 'subspecies', 'Ardea cinerea cinerea', 'Linnaeus, 1758'),
    avilist_row(3, 'subspecies', 'Ardea cinerea jouyi', 'Clark, AH, 1907'),
    avilist_row(4, 'subspecies', 'Ardea cinerea monicae', 'Jouanin, C; Roux, F, 1963'),
    avilist_row(5, 'species', 'Anas platyrhynchos', 'Linnaeus, 1758', 'Mallard'),
    avilist_row(6, 'subspecies', 'Anas platyrhynchos conboschas', 'Brehm, CL, 1831'),
    avilist_row(7, 'subspecies', 'Anas platyrhynchos platyrhynchos', 'Linnaeus, 1758'),
]
PRESERVED = {
    'avilist-taxon:v2025b:3': {'scientific_name': 'Ardea cinerea jouyi', 'english_name': 'Oriental Grey Heron'},
}


def cand(source, name, english, authority, page=1, require_year=False):
    value, reject = builder.clean_english(english)
    return {'source_id': source, 'name': name, 'authority': authority, 'english_cell': english,
            'english': value, 'reject': reject, 'require_year': require_year,
            'locator': {'source_id': source, 'page': page}}


def run(candidates, rows=FIXTURE_ROWS, preserved=None, species_names=None):
    subs, _ = builder.parse_avilist(rows)
    return builder.resolve(subs, candidates, species_names or {}, preserved or {})


class GeneratedArtifactTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ARTIFACT.read_text(encoding='utf-8'))

    def test_release_concept_set_and_source_pins_match_the_builder_and_registry(self):
        d = self.data
        self.assertEqual(1, d['schema_version'])
        self.assertEqual('v2025b', d['taxonomy']['release'])
        self.assertEqual('rg:concept-set:avilist-v2025b', d['taxonomy']['concept_set_id'])
        registry = json.loads((ROOT / 'config/collection-points.json').read_text(encoding='utf-8'))
        point = next(p for p in registry['collection_points'] if p['collection_point_id'] == 'taxonomy-avilist-v2025b')
        self.assertEqual(point['expected_sha256'], d['sources']['avilist-v2025b']['sha256'])
        self.assertEqual(point['endpoint_uri'], d['sources']['avilist-v2025b']['url'])
        self.assertEqual(set(builder.SOURCES), set(d['sources']))
        for sid, source in d['sources'].items():
            self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(builder.SOURCES[sid]['sha256'], source['sha256'])
            self.assertTrue(source['url'].startswith('https://'))
            self.assertTrue(source['license'])
        for excluded in d['evaluated_and_excluded_sources']:
            self.assertTrue(excluded['reason'] and excluded['url'].startswith('https://'))

    def test_every_name_is_bound_to_an_avilist_id_exact_scientific_name_and_a_cited_source_row(self):
        names = self.data['names']
        self.assertGreater(len(names), 1000)
        seen_parent_names = set()
        for tid, entry in names.items():
            self.assertRegex(tid, ID_PATTERN)
            self.assertRegex(entry['parent_id'], ID_PATTERN)
            self.assertRegex(entry['scientific_name'], TRINOMIAL)
            value, reject = builder.clean_english(entry['english_name'])
            self.assertEqual((entry['english_name'], None), (value, reject), tid)
            self.assertTrue(entry['evidence'])
            for ev in entry['evidence']:
                self.assertIn(ev['source_id'], builder.CONTRIBUTING_SOURCE_IDS)
                self.assertEqual(ev['source_id'], ev['locator']['source_id'])
                self.assertGreaterEqual(ev['locator']['page'], 1)
                if ev['source_id'] == 'dof-2019':
                    self.assertEqual(entry['english_name'], re.sub(r'\s+', ' ', ev['raw_english']).strip())
                else:
                    self.assertTrue(ev['raw_english'].startswith(entry['english_name']), tid)
                self.assertTrue(builder.authority_check(ev['source_authority'], entry['authority_avilist'],
                                                        ev['source_id'] == 'dof-2019')[0], tid)
            key = (entry['parent_id'], builder.fold(entry['english_name']))
            self.assertNotIn(key, seen_parent_names, f'{tid}: same name for two subspecies of one species')
            seen_parent_names.add(key)

    def test_coverage_numerator_and_denominator_are_consistent_with_the_names(self):
        cov = self.data['coverage']
        self.assertEqual(19879, cov['denominator_avilist_subspecies'])
        self.assertEqual(len(self.data['names']), cov['numerator_generated_names'])
        self.assertEqual(round(100 * cov['numerator_generated_names'] / 19879, 2), cov['percent_generated'])
        self.assertEqual(sum(cov['by_source_accepted'].values()),
                         sum(len(n['evidence']) for n in self.data['names'].values()))
        self.assertEqual(19879, sum(o['subspecies'] for o in cov['by_order'].values()))
        self.assertEqual(len(self.data['names']), sum(o['accepted'] for o in cov['by_order'].values()))
        self.assertEqual(len(self.data['excluded']), cov['excluded_entries'])
        self.assertEqual(len(self.data['conflicts']), cov['conflicts'])
        self.assertEqual(len(self.data['unmapped_candidates']), cov['unmapped_candidates_with_english'])

    def test_manually_verified_references_are_preserved_and_never_contradicted(self):
        preserved = self.data['preserved_manual_references']
        self.assertEqual(set(SUBSPECIES_NAME_REFERENCES), set(preserved))
        for tid, ref in SUBSPECIES_NAME_REFERENCES.items():
            p = preserved[tid]
            for field in ('scientific_name', 'english_name', 'source_title', 'source_url'):
                self.assertEqual(ref[field], p[field])
            self.assertTrue(p['identity_verified_against_avilist'], tid)
            if tid in self.data['names']:
                self.assertEqual(ref['english_name'], self.data['names'][tid]['english_name'])
                self.assertTrue(self.data['names'][tid]['matches_manual_reference'])
            self.assertEqual(tid in self.data['names'], p['generated_agrees'] or p['generated_name'] is not None)
        self.assertEqual(4, len(preserved))
        self.assertEqual('Oriental Grey Heron', self.data['names']['avilist-taxon:v2025b:5421']['english_name'])

    def test_conflicted_taxa_are_not_emitted_and_every_conflict_is_reported_with_both_sides(self):
        names = self.data['names']
        for conflict in self.data['conflicts']:
            if conflict['type'] == 'sources_disagree':
                self.assertNotIn(conflict['taxon_id'], names)
                self.assertGreaterEqual(len({v['english_name'].casefold() for v in conflict['values']}), 2)
            elif conflict['type'] == 'same_name_for_several_subspecies':
                self.assertGreaterEqual(len(conflict['taxa']), 2)
                for t in conflict['taxa']:
                    self.assertNotIn(t['taxon_id'], names)
            else:
                self.assertIn(conflict['type'], {'duplicate_source_rows_disagree'})
                self.assertNotIn(conflict['taxon_id'], names)
        reasons = {e['reason'] for e in self.data['excluded']}
        self.assertTrue({'english_multiple_names', 'malformed_columns', 'sources_disagree'} <= reasons)
        for e in self.data['excluded']:
            if e['reason'] == 'sources_disagree':
                self.assertNotIn(e['taxon_id'], names)

    @skipUnless(SOURCE_DIR and (Path(SOURCE_DIR) / builder.SOURCES['avilist-v2025b']['file']).exists(),
                'pinned AviList file not available')
    def test_artifact_ids_and_names_exist_exactly_in_the_pinned_avilist_release(self):
        raw = (Path(SOURCE_DIR) / builder.SOURCES['avilist-v2025b']['file']).read_bytes()
        self.assertEqual(builder.SOURCES['avilist-v2025b']['sha256'], builder.sha256_hex(raw))
        rows = {r[0]: r for r in json.loads(raw)}
        subs = [r for r in rows.values() if r[1] == 'subspecies']
        self.assertEqual(self.data['coverage']['denominator_avilist_subspecies'], len(subs))
        for tid, entry in self.data['names'].items():
            row = rows[tid.rsplit(':', 1)[1]]
            self.assertEqual('subspecies', row[1])
            self.assertEqual(entry['scientific_name'], row[5])
            self.assertEqual(row[6] or '', entry['authority_avilist'])
        for tid, ref in self.data['preserved_manual_references'].items():
            self.assertEqual(ref['scientific_name'], rows[tid.rsplit(':', 1)[1]][5])

    @skipUnless(SOURCE_DIR and all((Path(SOURCE_DIR) / s['file']).exists() for s in builder.SOURCES.values()),
                'pinned source files not available')
    def test_rebuilding_from_the_pinned_sources_reproduces_the_artifact_byte_for_byte(self):
        self.assertEqual(0, builder.main(['--offline', '--cache-dir', SOURCE_DIR, '--check', '--output', str(ARTIFACT)]))


class IdentityRulesTest(TestCase):
    def test_ids_come_from_the_pinned_release_sequence_and_exact_name_only(self):
        names, excluded, conflicts, unmapped, _ = run([
            cand('dof-2019', 'Ardea cinerea monicae', 'Mauritanian Heron', 'Jouanin og Roux, 1963', require_year=True)])
        self.assertEqual(['avilist-taxon:v2025b:4'], list(names))
        self.assertEqual('Ardea cinerea monicae', names['avilist-taxon:v2025b:4']['scientific_name'])
        self.assertEqual('avilist-taxon:v2025b:1', names['avilist-taxon:v2025b:4']['parent_id'])
        self.assertEqual(([], [], []), (excluded, conflicts, unmapped))

    def test_near_miss_names_are_never_matched_or_fuzzy_corrected(self):
        for wrong in ('Ardea cinerea Monicae', 'Ardea cinerea  monicae', 'Ardea cinerea monica', 'Ardea cinerea',
                      'Ardeola cinerea monicae', 'ardea cinerea monicae'):
            names, _, _, unmapped, _ = run([cand('dof-2019', wrong, 'Mauritanian Heron', 'Jouanin, 1963')])
            self.assertEqual({}, names, wrong)
            self.assertEqual(1, len(unmapped), wrong)

    def test_release_is_pinned_in_every_generated_id(self):
        subs, _ = builder.parse_avilist(FIXTURE_ROWS)
        self.assertTrue(all(v['taxon_id'].startswith('avilist-taxon:v2025b:') for v in subs.values()))
        self.assertEqual('v2025b', builder.TAXONOMY_RELEASE)

    def test_authority_must_agree_with_avilist(self):
        cases = [('Rothschild, 1907', 'authority_surname_mismatch', False),
                 ('Clark, A.H., 1999', 'authority_year_mismatch', False),
                 ('', 'authority_missing_in_source', False),
                 ('Clark', 'authority_year_missing_in_source', True)]
        for authority, reason, need_year in cases:
            names, excluded, _, _, _ = run([cand('s', 'Ardea cinerea jouyi', 'Oriental Grey Heron', authority,
                                                  require_year=need_year)])
            self.assertEqual({}, names, authority)
            self.assertEqual([reason], [e['reason'] for e in excluded], authority)
        ok = run([cand('s', 'Ardea cinerea jouyi', 'Oriental Grey Heron', 'Clark, A.H., 1907', require_year=True)])[0]
        self.assertEqual(['avilist-taxon:v2025b:3'], list(ok))
        self.assertTrue(builder.authority_check('(Statius Müller, P.L., 1776)', '(Müller, PLS, 1776)', True)[0])
        self.assertTrue(builder.authority_check('von Berlepsch og Stolzmann, 1894', 'Berlepsch, HHCL; Sztolcman, JS, 1894', True)[0])

    def test_ambiguous_avilist_scientific_names_are_not_bound(self):
        rows = FIXTURE_ROWS + [avilist_row(8, 'subspecies', 'Ardea cinerea jouyi', 'Clark, AH, 1907')]
        names, excluded, _, _, _ = run([cand('s', 'Ardea cinerea jouyi', 'Oriental Grey Heron', 'Clark, 1907')], rows)
        self.assertEqual({}, names)
        self.assertEqual(['ambiguous_avilist_name'], [e['reason'] for e in excluded])
        subs, dupes = builder.parse_avilist(rows)
        self.assertEqual(['Ardea cinerea jouyi'], dupes)
        with self.assertRaises(ValueError):
            builder.parse_avilist(rows[:3] + [avilist_row(2, 'subspecies', 'Ardea cinerea other', '')])


class ConflictRejectionTest(TestCase):
    def test_sources_that_disagree_emit_nothing_and_report_both_values(self):
        names, excluded, conflicts, _, _ = run([
            cand('dof-2019', 'Anas platyrhynchos conboschas', 'Greenland Mallard', 'Brehm, C.L., 1831', 5, True),
            cand('birds-nz-2022', 'Anas platyrhynchos conboschas', 'Greenland Duck', 'Brehm', 9)])
        self.assertEqual({}, names)
        self.assertEqual('sources_disagree', conflicts[0]['type'])
        self.assertEqual({'Greenland Mallard', 'Greenland Duck'}, {v['english_name'] for v in conflicts[0]['values']})
        self.assertEqual(2, len([e for e in excluded if e['reason'] == 'sources_disagree']))

    def test_agreeing_sources_are_merged_with_both_citations(self):
        names, _, conflicts, _, _ = run([
            cand('dof-2019', 'Anas platyrhynchos conboschas', 'Greenland Mallard', 'Brehm, C.L., 1831', 5, True),
            cand('birds-nz-2022', 'Anas platyrhynchos conboschas', 'Greenland Mallard', 'Brehm', 9)])
        self.assertEqual([], conflicts)
        entry = names['avilist-taxon:v2025b:6']
        self.assertEqual(['dof-2019', 'birds-nz-2022'], sorted([e['source_id'] for e in entry['evidence']], reverse=True))
        self.assertEqual({5, 9}, {e['locator']['page'] for e in entry['evidence']})

    def test_manual_reference_wins_over_a_contradicting_generated_name(self):
        names, _, conflicts, _, _ = run([cand('birds-nz-2022', 'Ardea cinerea jouyi', 'Asiatic Grey Heron', 'Clark', 4)],
                                         preserved=PRESERVED)
        self.assertEqual({}, names)
        self.assertEqual('sources_disagree', conflicts[0]['type'])
        self.assertIn('manual-preserved', {v['source_id'] for v in conflicts[0]['values']})
        names, _, conflicts, _, _ = run([cand('birds-nz-2022', 'Ardea cinerea jouyi', 'Oriental Grey Heron', 'Clark', 4)],
                                         preserved=PRESERVED)
        self.assertTrue(names['avilist-taxon:v2025b:3']['matches_manual_reference'])
        self.assertEqual([], conflicts)

    def test_disagreeing_duplicate_rows_in_one_source_are_rejected(self):
        names, _, conflicts, _, _ = run([
            cand('dof-2019', 'Ardea cinerea jouyi', 'Oriental Grey Heron', 'Clark, 1907', 7, True),
            cand('dof-2019', 'Ardea cinerea jouyi', 'Chinese Grey Heron', 'Clark, 1907', 90, True)])
        self.assertEqual({}, names)
        self.assertEqual('duplicate_source_rows_disagree', conflicts[0]['type'])

    def test_same_name_for_sibling_subspecies_is_rejected_for_all_of_them(self):
        names, excluded, conflicts, _, _ = run([
            cand('dof-2019', 'Ardea cinerea jouyi', 'Asian Heron', 'Clark, 1907', 1, True),
            cand('dof-2019', 'Ardea cinerea monicae', 'Asian Heron', 'Jouanin, 1963', 1, True)])
        self.assertEqual({}, names)
        self.assertEqual('same_name_for_several_subspecies', conflicts[0]['type'])
        self.assertEqual(2, len(excluded))

    def test_species_level_names_are_not_presented_as_subspecies_names(self):
        for english, species_names in (('Grey Heron', {}), ('Heron Grey', {('dof-2019', 'Ardea cinerea'): {'Heron Grey'}})):
            names, excluded, _, _, _ = run([cand('dof-2019', 'Ardea cinerea jouyi', english, 'Clark, 1907', 1, True)],
                                           species_names=species_names)
            self.assertEqual({}, names)
            self.assertEqual(['same_as_parent_species_name'], [e['reason'] for e in excluded])


class EnglishCellTest(TestCase):
    def test_only_one_plain_english_name_is_accepted(self):
        for good in ('Greenland Mallard', "Gould's Bronze Cuckoo", 'Gould’s Bronze Cuckoo', 'Eastern Bar-tailed Godwit',
                     'St. Helena Plover'):
            self.assertEqual((good, None), builder.clean_english(good), good)
        bad = {'': 'empty', 'Grey Teal / Sunda Teal': 'english_multiple_names', 'Great White Heron (Morph)': 'english_unclean',
               'Sunda-, Indonesian Grey Teal': 'english_unclean', 'lower case name': 'english_unclean',
               'Ostrich 2': 'english_unclean', 'Grønlandsk And': 'english_contains_danish_or_german_letters',
               'Grünreiher': 'english_contains_danish_or_german_letters', 'Heron -': 'english_unclean',
               'Rock group': 'english_unclean', 'A B C D E F G': 'english_unclean'}
        for cell, reason in bad.items():
            self.assertEqual((None, reason), builder.clean_english(cell), cell)


def dof_page(*lines):
    return list(lines)


class DofParsingTest(TestCase):
    PAGES = [[]] * 6 + [dof_page(
        '158 Systematiske, danske, engelske & tyske',
        'Ardea cinerea Linnaeus, 1758 • Fiskehejre • Grey Heron • Graureiher ',
        ' Ardea cinerea jouyi Clark, A.H., 1907 •  Kinesisk Fiskehejre •  • Asiatischer Graureiher ',
        ' Ardea cinerea monicae Jouanin og Roux, 1963 • Mauretansk Hejre • Mauritanian Heron • Mauretanien Graureiher ',
        ' Anas fulvigula maculosa Sennett, 1889 • Plettet Floridagåand • Mottled Duck / Florida Duck • Floridaente ',
        ' Anas poecilorhyncha haringtoni (Oates, 1907) • Burmesisk And • Burmese Spot-',
        'billed Duck • Myanmar-',
        'Fleckschnabelente ',
        'Bubulcus Bonaparte, 1855',
        ' Bubulcus ibis seychellarum (Salomonsen, F., 1934) • Seycheller-kohejre • Seychelles Cattle Egret',
        ' Cygnus columbianus bewickii Yarrell, 1830 • Pibesvane • Bewick’s Swan / Zwergschwan',
        'navne på alverdens fugle 231119',
    )]

    def test_wrapped_english_cells_are_joined_and_headings_never_leak_into_rows(self):
        records = builder.dof_records(self.PAGES)
        parsed = {r['name']: r for r in map(builder.dof_parse, records)}
        self.assertEqual(7, len(parsed))
        self.assertEqual('Burmese Spot-billed Duck', parsed['Anas poecilorhyncha haringtoni']['parts'][2])
        self.assertEqual('Jouanin og Roux, 1963', parsed['Ardea cinerea monicae']['authority'])
        self.assertEqual(7, parsed['Ardea cinerea monicae']['page'])
        self.assertNotIn('Bonaparte', parsed['Anas poecilorhyncha haringtoni']['parts'][-1])

    def test_front_matter_pages_are_not_read_as_rows(self):
        pages = [['Ardea cinerea jouyi Clark, 1907 • a • Fake Heron • b']] + self.PAGES[1:]
        self.assertNotIn('Fakus fakus fakus', [builder.dof_parse(r)['name'] for r in builder.dof_records(pages)])

    def test_candidates_reject_multi_name_malformed_and_empty_cells(self):
        cands, species, count = builder.dof_candidates(self.PAGES)
        by = {c['name']: c for c in cands}
        self.assertEqual('Mauritanian Heron', by['Ardea cinerea monicae']['english'])
        self.assertEqual('empty', by['Ardea cinerea jouyi']['reject'])
        self.assertEqual('english_multiple_names', by['Anas fulvigula maculosa']['reject'])
        self.assertEqual('Burmese Spot-billed Duck', by['Anas poecilorhyncha haringtoni']['english'])
        self.assertEqual('malformed_columns', by['Bubulcus ibis seychellarum']['reject'])
        self.assertEqual('malformed_columns', by['Cygnus columbianus bewickii']['reject'])
        self.assertIsNone(by['Cygnus columbianus bewickii']['english'])
        self.assertEqual({'Grey Heron'}, species[('dof-2019', 'Ardea cinerea')])

    def test_english_cell_copied_from_the_danish_or_single_word_cells_is_rejected(self):
        page = [[]] * 6 + [[
            ' Chrysocolaptes strictus kangeanensis Hoogerwerf, 1963 • Kangean-sultanspætte • Kangean-sultanspætte • Kangean-Sultanspecht',
            ' Tangara chilensis caelicolor (Sclater, 1851) • Grandala-tangare • Grandala • Himmelstangare']]
        by = {c['name']: c for c in builder.dof_candidates(page)[0]}
        self.assertEqual('english_contains_danish_or_german_letters', by['Chrysocolaptes strictus kangeanensis']['reject'])
        self.assertEqual('english_single_word_unverified', by['Tangara chilensis caelicolor']['reject'])
        same = [[]] * 6 + [[' Aa bb cc Smith, 1900 • Banks-petrel • Banks-petrel • X']]
        self.assertEqual('english_equals_danish_or_german_column', builder.dof_candidates(same)[0][0]['reject'])


class NzParsingTest(TestCase):
    @staticmethod
    def heading(y, trinomial, authority, names, extra=()):
        return [(y, 56.0, trinomial + ' ', 'ABC+Arial-BoldItalic'), (y, 56.0, authority, 'ABC+ArialNarrow'),
                (y, 56.0, ' ', 'ABC+ArialNarrow'), (y, 96.0, names, 'ABC+ArialNarrow-Bold'), *extra]

    def test_headings_are_read_from_bold_italic_runs_with_authority_split(self):
        runs = [[(700.0, 10.0, 'Ardea cinerea jouyi ', 'ABC+Arial-Italic'), *self.heading(725.0, 'Ardea cinerea jouyi', 'Clark', 'Oriental Grey Heron'),
                 *self.heading(600.0, 'Anthornis melanura melanura', '(Sparrman)', 'Bellbird', [(600.0, 130.0, '*', 'ABC+ArialNarrow')]),
                 (500.0, 56.0, 'Ardea cinerea jouyi ', 'ABC+Arial-BoldItalic')]]
        found = list(builder.nz_headings(runs))
        self.assertEqual([('Ardea cinerea jouyi', 'Clark', 'Oriental Grey Heron', 1),
                          ('Anthornis melanura melanura', '(Sparrman)', 'Bellbird', 1)],
                         [(h['name'], h['authority'], h['names_text'], h['page']) for h in found])

    def test_bar_convention_is_applied_conservatively(self):
        self.assertEqual(('Eastern Bar-tailed Godwit', None), builder.nz_english('Eastern Bar-tailed Godwit | Kuaka*'))
        self.assertEqual(('Oriental Grey Heron', None), builder.nz_english('Oriental Grey Heron'))
        self.assertEqual(('Bellbird', None), builder.nz_english('Bellbird'))
        self.assertEqual((None, 'nz_maori_name_listed_first'), builder.nz_english('Kōtuku Nui | White Heron'))
        self.assertEqual((None, 'nz_english_maori_identical_apart_from_macrons'), builder.nz_english('Tūī | Tui'))
        self.assertEqual((None, 'nz_single_word_left_of_bar_language_unverified'), builder.nz_english('Ruru | Morepork'))
        self.assertEqual((None, 'nz_macron_name_without_english'), builder.nz_english('Pūkeko'))


class DomesticNameTest(TestCase):
    def test_domesticated_form_names_do_not_become_wild_subspecies_names(self):
        for label in ('Bengalese Munia','Society Finch','Domestic Finch'):
            names, excluded, _, _, _ = run([cand('dof-2019', 'Ardea cinerea monicae', label, 'Jouanin, 1963')])
            self.assertEqual({}, names)
            self.assertEqual('domestication_name_ambiguous',excluded[0]['reason'])
        data=json.loads(ARTIFACT.read_text())
        self.assertFalse(any(e['scientific_name']=='Lonchura striata acuticauda' for e in data['names'].values()))
