"""Translations must not replace graph names or leak across taxonomy releases."""
import json
from pathlib import Path
import re
from unittest import TestCase
import robingraph.retrieval.taxonomy_lineage as lineage_module

from robingraph.retrieval.taxonomy_lineage import translated_korean_names, with_korean_display_name
from robingraph.retrieval.taxonomy_lineage_neo4j import _parse_lineage_items


class KoreanDisplayNamesTest(TestCase):
    def test_sourced_supplement_wins_over_machine_translation_and_keeps_provenance(self):
        labels = translated_korean_names()
        references = [(key, value) for key, value in labels.items() if value.get("status") == "source-reference"]
        self.assertEqual(170, len(references))
        taxon_id, label = next((key, value) for key, value in references if value["scientific_name"] == "Sibirionetta formosa")
        item = _parse_lineage_items([{"taxon_id": taxon_id, "rank": "species", **label}])[0]
        self.assertEqual("가창오리", item.korean_name)
        self.assertEqual("source-reference", item.korean_name_status)
        self.assertEqual(label["source_url"], item.korean_name_source_url)

    def test_lineage_translation_preserves_identity_and_verified_names(self):
        taxon_id, label = next(iter(translated_korean_names().items()))
        row = {"taxon_id": taxon_id, "rank": "species", "scientific_name": label["scientific_name"],
               "english_name": label["english_name"], "authority": "Original authority"}
        item = _parse_lineage_items([row])[0]
        self.assertEqual(label["name"], item.korean_name)
        self.assertEqual("machine-translated", item.korean_name_status)
        self.assertEqual(row["english_name"], item.english_name)
        self.assertEqual(row["scientific_name"], item.scientific_name)
        self.assertEqual("Original authority", item.authority)
        verified = _parse_lineage_items([{**row, "korean_name": "검증된 이름", "korean_name_status": "source-preferred"}])[0]
        self.assertEqual("검증된 이름", verified.korean_name)
        self.assertEqual("source-preferred", verified.korean_name_status)
        mislabeled = _parse_lineage_items([{**row, "korean_name": "Foreign language label"}])[0]
        self.assertEqual(label["name"], mislabeled.korean_name)
        self.assertEqual(row["scientific_name"], mislabeled.scientific_name)
        for change in ({"taxon_id": "new-release:1"}, {"scientific_name": "Different species"},
                       {"english_name": "Changed English name"}, {"rank": "subspecies"}):
            self.assertIsNone(with_korean_display_name({**row, **change}).get("korean_name"))

    def test_snapshot_has_complete_validated_translation_coverage(self):
        labels = translated_korean_names()
        self.assertEqual(10291, len(labels))
        self.assertEqual(10291, len({entry["scientific_name"] for entry in labels.values()}))
        for taxon_id, entry in labels.items():
            self.assertTrue(taxon_id.startswith("avilist-taxon:v2025b:"))
            self.assertTrue(re.fullmatch(r"[가-힣ㆍ· \-]+", entry["name"]), entry)
            self.assertTrue(entry["english_name"])
        snapshot = json.loads(Path(lineage_module.__file__).with_name("species_ko_translations.json").read_text())
        self.assertEqual("machine-translated", snapshot["status"])
        self.assertIn("gemini-3.5-flash-lite", snapshot["models"])
