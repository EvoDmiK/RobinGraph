"""Korean species names require checked sources and exact taxonomy identity."""
import json
from pathlib import Path
from unittest import TestCase
import robingraph.retrieval.taxonomy_lineage as lineage_module
from robingraph.retrieval.taxonomy_lineage import sourced_korean_names, with_korean_display_name
from robingraph.retrieval.taxonomy_lineage_neo4j import _parse_lineage_items


class KoreanDisplayNamesTest(TestCase):
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
        self.assertEqual(596, len(labels))
        self.assertEqual(596, len({v['scientific_name'] for v in labels.values()}))
        for key, label in labels.items():
            self.assertTrue(key.startswith('avilist-taxon:v2025b:'))
            self.assertEqual('source-reference', label['status'])
            self.assertTrue(label['source_row'] > 0)
            self.assertTrue(label['source_url'])
            self.assertEqual(label['name'].strip(), label['name'])
        for science, expected in [('Thinornis dubius', '꼬마물떼새'), ('Thinornis placidus', '흰목물떼새'),
                                  ('Periparus venustulus', '노랑배진박새')]:
            row = self.row_for(science)
            self.assertEqual(expected, with_korean_display_name(row)['korean_name'])
            self.assertTrue(labels[row['taxon_id']]['taxonomy_crosswalk_source_url'])
        snapshot = json.loads(Path(lineage_module.__file__).with_name('species_ko_names.json').read_text())
        self.assertEqual(598, snapshot['source_species_count'])
        self.assertEqual({'Anas carolinensis', 'Saxicola stejnegeri'},
                         {v['scientific_name'] for v in snapshot['unmatched_source_species']})
        self.assertEqual('쇠오리', with_korean_display_name(self.row_for('Anas crecca'))['korean_name'])
