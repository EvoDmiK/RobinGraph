from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import load_n8n_avonet as loader


class AvonetLoaderTest(unittest.TestCase):
    def test_normalize_row_preserves_interpretation_and_locator(self) -> None:
        config = {
            "release": "test-release",
            "url": "https://example.invalid/avonet.xlsx",
            "sheet": "AVONET1_BirdLife",
            "fields": [
                ["Wing.Length", "wing_length", "mm", "Wing Length"],
                ["Habitat.Density", "habitat_density_category", None, None],
            ],
        }
        profile = loader.normalize_row({
            "Species1": " Example bird ", "Sequence": "NA", "Inference": "YES",
            "Traits.inferred": "Wing Length", "Reference.species": "Reference bird",
            "Avibase.ID1": "id", "Total.individuals": "2", "Mass.Source": "source",
            "Mass.Refs.Other": "refs", "Wing.Length": "12.5", "Habitat.Density": "2",
        }, 7, config)
        self.assertEqual("Example bird", profile["scientific_name"])
        self.assertIsNone(profile["sequence"])
        self.assertEqual(7, profile["row_number"])
        claims = {claim["trait_name"]: claim for claim in profile["claims"]}
        self.assertEqual(12.5, claims["wing_length"]["value_num"])
        self.assertTrue(claims["wing_length"]["inferred"])
        self.assertEqual("semi_open", claims["habitat_density_category"]["value_text"])

    def test_selected_worksheet_reader_handles_shared_strings_and_sparse_cells(self) -> None:
        workbook = """<?xml version='1.0' encoding='UTF-8'?>
<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
 xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>
 <sheets><sheet name='Other' sheetId='1' r:id='rId1'/><sheet name='Wanted' sheetId='2' r:id='rId2'/></sheets>
</workbook>"""
        relationships = """<?xml version='1.0' encoding='UTF-8'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
 <Relationship Id='rId1' Target='worksheets/sheet1.xml'/>
 <Relationship Id='rId2' Target='worksheets/sheet2.xml'/>
</Relationships>"""
        shared = """<sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
<si><t>Name</t></si><si><t>Count</t></si><si><t>Alpha</t></si><si><t>Beta</t></si></sst>"""
        wanted = """<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>
<row r='1'><c r='A1' t='s'><v>0</v></c><c r='B1' t='s'><v>1</v></c></row>
<row r='2'><c r='A2' t='s'><v>2</v></c><c r='B2'><v>3</v></c></row>
<row r='4'><c r='A4' t='s'><v>3</v></c></row>
</sheetData></worksheet>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/workbook.xml", workbook)
                archive.writestr("xl/_rels/workbook.xml.rels", relationships)
                archive.writestr("xl/sharedStrings.xml", shared)
                archive.writestr("xl/worksheets/sheet1.xml", "<unused/>")
                archive.writestr("xl/worksheets/sheet2.xml", wanted)
            rows = list(loader.iter_worksheet_rows(path, "Wanted"))
        self.assertEqual([(2, {"Name": "Alpha", "Count": "3"}),
                          (4, {"Name": "Beta", "Count": None})], rows)

    def test_file_hash_streams_known_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value"
            path.write_bytes(b"RobinGraph")
            self.assertEqual(
                "48b149984fb370fbc46b4efa645b433d605209e34754d6af88e9cfab977d88a5",
                loader.file_sha256(path),
            )

    def test_temporary_workflow_never_embeds_database_password(self) -> None:
        source = Path(loader.__file__).read_text(encoding="utf-8")
        self.assertNotIn("NEO4J_PASSWORD=", source)
        self.assertIn("httpHeaderAuth", source)
        self.assertIn("finally:", source)


if __name__ == "__main__":
    unittest.main()
