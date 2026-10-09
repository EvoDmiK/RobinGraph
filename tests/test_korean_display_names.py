"""Korean species names require checked sources and exact taxonomy identity."""
import json
from pathlib import Path
from unittest import TestCase
import robingraph.retrieval.taxonomy_lineage as lineage_module
from robingraph.retrieval.taxonomy_lineage import sourced_korean_names, with_korean_display_name
from robingraph.retrieval.taxonomy_lineage_neo4j import _parse_lineage_items


class KoreanDisplayNamesTest(TestCase):
    def test_requested_magpie_names_keep_the_two_species_distinct(self):
        for tid, science, canonical, korean, english in (
                ('20198', 'Pica pica', 'Eurasian Magpie', None, 'Eurasian magpie'),
                ('20193', 'Pica serica', 'Oriental Magpie', '까치', 'Oriental magpie')):
            row = dict(taxon_id='avilist-taxon:v2025b:'+tid, rank='species',
                       scientific_name=science, english_name=canonical)
            result = with_korean_display_name(row)
            self.assertEqual(korean, result['korean_name'])
            self.assertEqual(english, result['english_name'])
            self.assertEqual(science, result['scientific_name'])
            self.assertEqual(result, with_korean_display_name(result))
            self.assertEqual(english, _parse_lineage_items([row])[0].english_name)
            self.assertIsNone(with_korean_display_name({**row, 'taxon_id':'avilist-taxon:v2026:'+tid})['korean_name'])

    def row_for(self, science):
        key, label = next((k, v) for k, v in sourced_korean_names().items() if v['scientific_name'] == science)
        return {'taxon_id': key, 'rank': 'species', 'scientific_name': science,
                'english_name': label['english_name'], 'authority': 'Original authority'}

    def test_guide_overrides_incorrect_graph_name_and_preserves_identity(self):
        row = self.row_for('Aethia cristatella')
        item = _parse_lineage_items([{**row, 'korean_name': '뿔바다새', 'korean_name_status': 'community-sourced'}])[0]
        self.assertEqual('뿔바다오리', item.korean_name)
        self.assertEqual('source-reference', item.korean_name_status)
        self.assertTrue(item.korean_name_source_url.startswith('https://sites.google.com/khu.ac.kr/korornsoc/'))
        self.assertEqual(row['english_name'], item.english_name)
        self.assertEqual(row['scientific_name'], item.scientific_name)
        self.assertEqual(row['authority'], item.authority)

    def test_unknown_names_and_mismatched_release_use_english(self):
        row = self.row_for('Aethia cristatella')
        for change in ({'taxon_id': 'avilist-taxon:new-release:1'}, {'scientific_name': 'Different species'},
                       {'english_name': 'Changed English name'}):
            result = with_korean_display_name({**row, 'korean_name': '기존미검증명', **change})
            self.assertIsNone(result['korean_name'])
            self.assertIsNone(result['korean_name_status'])
            self.assertIsNone(result['korean_name_source_url'])
        foreign = {'taxon_id': 'avilist-taxon:v2025b:999999', 'rank': 'species',
                   'scientific_name': 'Abeillia abeillei', 'english_name': 'Emerald-chinned Hummingbird',
                   'korean_name': '에메랄드턱벌새', 'korean_name_status': 'machine-translated'}
        self.assertIsNone(_parse_lineage_items([foreign])[0].korean_name)
        self.assertEqual('Emerald-chinned Hummingbird', with_korean_display_name(foreign)['english_name'])
        self.assertEqual({**row, 'rank': 'subspecies'}, with_korean_display_name({**row, 'rank': 'subspecies'}))

    def test_snapshot_sources_crosswalks_and_split_species(self):
        labels = sourced_korean_names()
        self.assertEqual(850, len(labels))
        self.assertEqual(850, len({v['scientific_name'] for v in labels.values()}))
        for key, label in labels.items():
            self.assertTrue(key.startswith('avilist-taxon:v2025b:'))
            self.assertEqual('source-reference', label['status'])
            self.assertTrue(label.get('source_row', 0) > 0 or label.get('source_locator') or '/animal/animalView.do?' in label['source_url'])
            self.assertTrue(label['source_url'])
            self.assertEqual(label['name'].strip(), label['name'])
        for science, expected in [('Thinornis dubius', '꼬마물떼새'), ('Thinornis placidus', '흰목물떼새'),
                                  ('Periparus venustulus', '노랑배진박새')]:
            row = self.row_for(science)
            self.assertEqual(expected, with_korean_display_name(row)['korean_name'])
            self.assertTrue(labels[row['taxon_id']]['taxonomy_crosswalk_source_url'])
        snapshot = json.loads(Path(lineage_module.__file__).with_name('species_ko_names.json').read_text(encoding='utf-8'))
        self.assertEqual(598, snapshot['source_species_count'])
        self.assertEqual({'Anas carolinensis', 'Saxicola stejnegeri'},
                         {v['scientific_name'] for v in snapshot['unmatched_source_species']})
        self.assertEqual('쇠오리', with_korean_display_name(self.row_for('Anas crecca'))['korean_name'])

    def test_institutional_supplement_preserves_exact_identity_and_source_evidence(self):
        snapshot = json.loads(Path(lineage_module.__file__).with_name('species_ko_names.json').read_text())
        added = [v for v in snapshot['labels'].values() if v.get('source_sha256') == '2a0538adbdd042b4328cd96f04df57e7c85598c15983986b7a9afe751a22eb12']
        self.assertEqual(19, len(added))
        for label in added:
            with self.subTest(scientific_name=label['scientific_name']):
                row = self.row_for(label['scientific_name'])
                self.assertEqual(label['name'], with_korean_display_name(row)['korean_name'])
                self.assertIn(label['source_page'], (2, 3))
                self.assertEqual(label['scientific_name'], label['source_scientific_name'])
                self.assertTrue(label['source_url'].startswith('https://www.law.go.kr/'))
        self.assertEqual('자바뿔찌르레기', with_korean_display_name(self.row_for('Acridotheres javanicus'))['korean_name'])
        self.assertEqual('이집트기러기', with_korean_display_name(self.row_for('Alopochen aegyptiaca'))['korean_name'])

    def test_foreign_names_require_sources_and_reject_conflicting_names(self):
        for science, name in [('Struthio camelus', '타조'), ('Gracula religiosa', '구관조'),
                              ('Centropus sinensis', '큰쿠칼')]:
            row = self.row_for(science)
            result = with_korean_display_name(row)
            self.assertEqual(name, result['korean_name'])
            self.assertTrue(result['korean_name_source_url'])
        labels = sourced_korean_names()
        self.assertNotIn('Anthus rubescens', {v['scientific_name'] for v in labels.values()})
        self.assertNotIn('Nycticorax caledonicus', {v['scientific_name'] for v in labels.values()})

    def test_408_review_additions_require_exact_identity_and_real_source_locator(self):
        labels = sourced_korean_names()
        additions = {k: v for k, v in labels.items() if v.get('review_batch') == '2026-10-09-ko408'}
        self.assertEqual(185, len(additions))
        previous_names = {v['name'] for v in labels.values() if v.get('review_batch') != '2026-10-09-ko408'}
        for key, label in additions.items():
            with self.subTest(scientific_name=label['scientific_name']):
                self.assertNotIn(label['name'], previous_names)
                self.assertEqual(label['scientific_name'], label['source_scientific_name'])
                self.assertTrue(label['source_locator'])
                self.assertTrue(label['source_title'])
                self.assertNotIn('wikidata.org', label['source_url'])
                row = self.row_for(label['scientific_name'])
                self.assertEqual(label['name'], with_korean_display_name(row)['korean_name'])
                self.assertIsNone(with_korean_display_name({**row, 'scientific_name': 'Different species'})['korean_name'])
        for science, expected in [('Carduelis carduelis', '오색방울새'), ('Sterna paradisaea', '북극제비갈매기'),
                                  ('Phoenicurus schisticeps', '흰목딱새'), ('Melopsittacus undulatus', '사랑앵무'),
                                  ('Pygoscelis antarcticus', '턱끈펭귄'), ('Urocynchramus pylzowi', '프르제발스키되새')]:
            self.assertEqual(expected, with_korean_display_name(self.row_for(science))['korean_name'])
        for science in ('Pica pica', 'Turdus merula', 'Coturnix coturnix', 'Otus scops', 'Aquila rapax'):
            self.assertNotIn(science, {v['scientific_name'] for v in additions.values()})

    def test_all_408_dispositions_are_auditable_without_claiming_all_are_resolved(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads((root / 'docs/verification/assets/2026-10-09-korean-name-408-resolution.json').read_text())
        records = report['records']
        self.assertEqual(408, len(records))
        self.assertEqual(408, len({r['taxon_id'] for r in records}))
        self.assertEqual(185, sum(bool(r['selected']) for r in records))
        labels = sourced_korean_names()
        for record in records:
            with self.subTest(scientific_name=record['scientific_name']):
                self.assertTrue(record['reason'])
                self.assertTrue(record['investigations'][0]['source_url'])
                self.assertTrue(record['investigations'][0]['sha256'])
                if record['selected']:
                    self.assertEqual(record['selected']['name'], labels[record['taxon_id']]['name'])
                else:
                    self.assertNotIn(record['taxon_id'], labels)
