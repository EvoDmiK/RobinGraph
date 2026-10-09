"""Regression tests for scripts/build_trait_crosswalk.py and its committed index.

Three layers, none of which needs network access:

* the committed ``trait_crosswalk.json`` (invariants + representative species);
* small in-memory fixtures that exercise each mapping rule;
* input-validation failures (hash, structure) on throw-away files.

``RobinGraph_TRAIT_RAW_DIR``-style full regeneration needs the three pinned
source files, so it runs only when ``ROBINGRAPH_TRAIT_RAW_DIR`` points at them.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_trait_crosswalk", ROOT / "scripts/build_trait_crosswalk.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

INDEX = ROOT / "src/robingraph/retrieval/trait_crosswalk.json"
DOCUMENT = json.loads(INDEX.read_text(encoding="utf-8"))
COLUMNS = DOCUMENT["schema"]["entry_columns"]
ENTRIES = [dict(zip(COLUMNS, row)) for row in DOCUMENT["entries"]]


def entries_for(name: str, dataset: str | None = None):
    return [e for e in ENTRIES if (e["source_name"] == name or e["target_name"] == name)
            and (dataset is None or e["dataset"] == dataset)]


class CommittedIndexTest(unittest.TestCase):
    def test_file_is_canonical_and_pinned_to_repository_config(self) -> None:
        raw = INDEX.read_bytes()
        self.assertEqual(raw, builder.render(json.loads(raw)), "index must be the generator's canonical bytes")
        pins = builder.load_pins(ROOT)
        for source in DOCUMENT["sources"]:
            pin = pins[source["id"]]
            for key in ("url", "release", "sha256", "license_name", "license_uri"):
                self.assertEqual(pin[key], source[key], (source["id"], key))
            self.assertEqual(64, len(source["sha256"]))
        self.assertEqual(3, len(DOCUMENT["sources"]))

    def test_summary_matches_entries(self) -> None:
        status = {}
        for e in ENTRIES:
            key = f"{e['dataset']}.{e['status']}"
            status[key] = status.get(key, 0) + 1
        self.assertEqual(status, DOCUMENT["summary"]["status"])
        reasons = {}
        for e in ENTRIES:
            if e["reason"]:
                reasons[f"{e['dataset']}.{e['reason']}"] = reasons.get(f"{e['dataset']}.{e['reason']}", 0) + 1
        self.assertEqual(reasons, DOCUMENT["summary"]["reasons"])

    def test_entry_invariants(self) -> None:
        seen_targets = set()
        for e in ENTRIES:
            self.assertIn(e["status"], {"accepted", "needs_review", "unresolved"})
            if e["status"] == "accepted":
                self.assertIsNone(e["reason"])
                self.assertIsNotNone(e["target_name"])
                key = (e["dataset"], e["target_name"])
                self.assertNotIn(key, seen_targets, "a target must have one accepted source row per dataset")
                seen_targets.add(key)
                self.assertIn(e["name_relation"], {"same_name", "name_changed"})
            else:
                self.assertIsNotNone(e["reason"])
            if e["status"] == "unresolved":
                self.assertIsNone(e["target_name"])

    def test_accepted_entries_carry_the_evidence_the_policy_requires(self) -> None:
        for e in ENTRIES:
            if e["status"] != "accepted":
                continue
            if e["dataset"] == "avonet":
                self.assertEqual("avibase_id_unique", e["method"])
                self.assertEqual(e["source_id"].lower(), e["target_avibase_id"].lower())
            else:
                self.assertEqual("birdtree_birdlife_avibase_chain", e["method"])
                self.assertEqual("BL3", e["source_taxonomy"], "only BL3 Elton rows may be accepted")
                self.assertEqual(["1BL to 1BT"], e["evidence"]["match_types"])
                self.assertEqual(e["evidence"]["avibase_id"].lower(), e["target_avibase_id"].lower())

    def test_ioc27_rows_never_accepted(self) -> None:
        ioc = [e for e in ENTRIES if e["dataset"] == "eltontraits" and e["source_taxonomy"] != "BL3"]
        self.assertTrue(ioc)
        self.assertEqual(set(), {e["status"] for e in ioc} & {"accepted"})
        self.assertIn("taxo_not_bl3_crosswalk_basis_unverified", {e["reason"] for e in ioc})

    def test_representative_recoveries(self) -> None:
        # Elton lists these under their BirdTree names; the chain reaches the AviList species.
        for old, new in (("Ixos amaurotis", "Hypsipetes amaurotis"), ("Casmerodius albus", "Ardea alba"),
                         ("Accipiter badius", "Tachyspiza badia")):
            [entry] = [e for e in entries_for(old, "eltontraits") if e["source_name"] == old]
            self.assertEqual(("accepted", new, "name_changed"), (entry["status"], entry["target_name"], entry["name_relation"]), old)
        for name in ("Accipiter nisus", "Hypsipetes amaurotis", "Ardea alba"):
            for dataset in ("avonet", "eltontraits"):
                self.assertTrue([e for e in entries_for(name, dataset) if e["status"] == "accepted"], (name, dataset))

    def test_pica_serica_has_no_source_row_and_stays_unlinked(self) -> None:
        self.assertEqual([], entries_for("Pica serica"), "no Elton/AVONET row exists for Pica serica; nothing may point at it")
        for e in entries_for("Pica pica"):
            self.assertEqual("Pica pica", e["target_name"])
            self.assertEqual("needs_review", e["status"], "broad/other-concept Pica pica row must not be auto-accepted")
            self.assertEqual("exact_name_legacy", e["method"])

    def test_same_name_different_concept_id_is_a_review_record(self) -> None:
        mismatches = [e for e in ENTRIES if e["reason"] == "exact_name_concept_id_mismatch"]
        self.assertEqual(DOCUMENT["summary"]["reasons"]["avonet.exact_name_concept_id_mismatch"], len(mismatches))
        for e in mismatches:
            self.assertEqual("needs_review", e["status"])
            self.assertEqual("same_name", e["name_relation"])
            self.assertNotEqual(e["source_id"].lower(), e["target_avibase_id"].lower())
        self.assertIn("Milvus migrans", {e["source_name"] for e in mismatches})

    def test_conflicting_source_rows_are_not_auto_accepted(self) -> None:
        conflict = entries_for("Colluricincla umbrina", "eltontraits")[0]
        self.assertEqual(("needs_review", "multiple_source_rows_same_target"), (conflict["status"], conflict["reason"]))


# ---------------------------------------------------------------- mapping rules on tiny fixtures

def av(sequence, name, avibase, family="Fam"):
    row = {c: None for c in builder.AVILIST_COLUMNS}
    row.update(Sequence=str(sequence), Taxon_rank="species", Scientific_name=name, AvibaseID=avibase, Family=family)
    return row


def avonet_row(row, name, avibase, inference="NO"):
    return {"_row": row, "Sequence": str(row), "Species1": name, "Avibase.ID1": avibase, "Inference": inference}


def elton_row(line, spec_id, name, taxo="BL3"):
    return {"_line": line, "SpecID": spec_id, "Scientific": name, "Taxo": taxo, "English": "x", "BLFamilyLatin": "Fam"}


PINS = {i: {"name": i, "provider": "p", "url": "https://x", "release": "r", "sha256": "0" * 64,
            "license_name": "l", "license_uri": "u", "landing_uri": "u"}
        for i in (builder.AVILIST_ID, builder.ELTON_ID, builder.AVONET_ID)}
SIZES = {i: 1 for i in PINS}


def run(avilist, elton, avonet1, birdtree_names, crosswalk):
    avonet = {
        "avonet1": avonet1,
        "avonet3": [{"Species3": n} for n in birdtree_names],
        "crosswalk": [{"Species1": a, "Species3": b, "Match.type": t} for a, b, t in crosswalk],
    }
    document = builder.build(avilist, elton, avonet, PINS, SIZES)
    return [dict(zip(COLUMNS, row)) for row in document["entries"]], document


class MappingRuleTest(unittest.TestCase):
    def test_avonet_id_match_is_case_insensitive_and_follows_renames(self) -> None:
        entries, _ = run([av(1, "Genus new", "avibase-AAAA0001")], [],
                         [avonet_row(2, "Genus old", "AVIBASE-AAAA0001")], [], [])
        [entry] = entries
        self.assertEqual(("accepted", "Genus new", "name_changed", "avibase_id_unique"),
                         (entry["status"], entry["target_name"], entry["name_relation"], entry["method"]))

    def test_no_name_similarity_or_epithet_matching(self) -> None:
        avilist = [av(1, "Genus alba", "avibase-AAAA0001"), av(2, "Other albus", "avibase-AAAA0002")]
        avonet1 = [avonet_row(2, "Genus albus", "AVIBASE-ZZZZ9999"), avonet_row(3, "Third alba", "AVIBASE-ZZZZ9998")]
        entries, _ = run(avilist, [], avonet1, [], [])
        self.assertEqual({"unresolved"}, {e["status"] for e in entries})
        self.assertEqual({"no_avibase_match_no_exact_name"}, {e["reason"] for e in entries})

    def test_exact_name_with_other_concept_id_needs_review_not_accepted(self) -> None:
        entries, _ = run([av(1, "Genus one", "avibase-AAAA0001")], [],
                         [avonet_row(2, "Genus one", "AVIBASE-BBBB0002")], [], [])
        [entry] = entries
        self.assertEqual(("needs_review", "exact_name_concept_id_mismatch", "exact_name_legacy"),
                         (entry["status"], entry["reason"], entry["method"]))
        self.assertEqual("avibase-AAAA0001", entry["evidence"]["exact_name_avibase_id"])

    def test_duplicate_source_id_and_ambiguous_avilist_id_are_not_resolved(self) -> None:
        avilist = [av(1, "Genus one", "avibase-AAAA0001"), av(2, "Genus two", "avibase-AAAA0002"),
                   av(3, "Genus three", "avibase-AAAA0002")]
        avonet1 = [avonet_row(2, "Src a", "AVIBASE-AAAA0001"), avonet_row(3, "Src b", "AVIBASE-AAAA0001"),
                   avonet_row(4, "Src c", "AVIBASE-AAAA0002")]
        entries, _ = run(avilist, [], avonet1, [], [])
        self.assertEqual(["multiple_source_rows_same_avibase_id"] * 2 + ["avilist_avibase_id_not_unique"],
                         [e["reason"] for e in entries])
        self.assertNotIn("accepted", {e["status"] for e in entries})

    def test_elton_chain_accepts_only_one_to_one_and_bl3(self) -> None:
        avilist = [av(1, "Genus new", "avibase-AAAA0001")]
        avonet1 = [avonet_row(2, "Genus bl", "AVIBASE-AAAA0001")]
        elton = [elton_row(2, "10", "Genus bt"), elton_row(3, "11", "Genus bt2", taxo="IOC27")]
        crosswalk = [("Genus bl", "Genus bt", "1BL to 1BT")]
        entries, _ = run(avilist, elton, avonet1, ["Genus bt", "Genus bt2"], crosswalk + [("Genus bl", "Genus bt2", "1BL to 1BT")])
        # Genus bl appears in two crosswalk rows -> not unique in both directions -> nothing is accepted.
        elton_entries = [e for e in entries if e["dataset"] == "eltontraits"]
        self.assertEqual({"unresolved"}, {e["status"] for e in elton_entries})
        self.assertEqual({"birdlife_species_in_several_crosswalk_rows"}, {e["reason"] for e in elton_entries})

        entries, _ = run(avilist, [elton_row(2, "10", "Genus bt")], avonet1, ["Genus bt"], crosswalk)
        self.assertEqual("accepted", entries[-1]["status"])
        self.assertEqual("Genus new", entries[-1]["target_name"])

        entries, _ = run(avilist, [elton_row(3, "11", "Genus bt", taxo="IOC27")], avonet1, ["Genus bt"], crosswalk)
        self.assertEqual(("needs_review", "taxo_not_bl3_crosswalk_basis_unverified"), (entries[-1]["status"], entries[-1]["reason"]))
        self.assertEqual("Genus new", entries[-1]["target_name"], "candidate is kept for review, not approved")

    def test_many_to_one_and_split_match_types_are_never_accepted(self) -> None:
        avilist = [av(1, "Genus merged", "avibase-AAAA0001"), av(2, "Genus split", "avibase-AAAA0002")]
        avonet1 = [avonet_row(2, "Genus a", "AVIBASE-AAAA0001"), avonet_row(3, "Genus b", "AVIBASE-AAAA0003"),
                   avonet_row(4, "Genus c", "AVIBASE-AAAA0002")]
        crosswalk = [("Genus a", "Genus merged", "Many BL to 1BT"), ("Genus b", "Genus merged", "Many BL to 1BT"),
                     ("Genus c", "Genus split", "1BL to many BT")]
        elton = [elton_row(2, "10", "Genus merged"), elton_row(3, "11", "Genus split")]
        entries, _ = run(avilist, elton, avonet1, ["Genus merged", "Genus split"], crosswalk)
        elton_entries = [e for e in entries if e["dataset"] == "eltontraits"]
        self.assertEqual(["birdtree_merges_birdlife_species", "birdtree_splits_birdlife_species"],
                         [e["reason"] for e in elton_entries])
        # An exact-name candidate exists, so these are alignment reviews, not silent accepts.
        self.assertEqual({"needs_review"}, {e["status"] for e in elton_entries})

    def test_competing_source_rows_for_one_target_are_not_auto_accepted(self) -> None:
        avilist = [av(1, "Genus kept", "avibase-AAAA0001")]
        avonet1 = [avonet_row(2, "Genus bl", "AVIBASE-AAAA0001")]
        elton = [elton_row(2, "10", "Genus old"), elton_row(3, "11", "Genus kept")]
        crosswalk = [("Genus bl", "Genus old", "1BL to 1BT")]
        entries, _ = run(avilist, elton, avonet1, ["Genus old", "Genus kept"], crosswalk)
        old = [e for e in entries if e["source_name"] == "Genus old"][0]
        self.assertEqual(("needs_review", "multiple_source_rows_same_target"), (old["status"], old["reason"]))

    def test_target_without_any_source_row_gets_no_entry(self) -> None:
        # The Pica serica situation: an AviList species with no Elton/AVONET row stays unlinked.
        avilist = [av(1, "Pica pica", "avibase-AAAA0001"), av(2, "Pica serica", "avibase-AAAA0002")]
        avonet1 = [avonet_row(2, "Pica pica", "AVIBASE-OLD00001")]
        entries, document = run(avilist, [], avonet1, [], [])
        self.assertEqual([], [e for e in entries if e["target_name"] == "Pica serica"])
        self.assertEqual("needs_review", entries[0]["status"])
        self.assertEqual(2, document["summary"]["avilist_species"])
        self.assertEqual(2, document["summary"]["avilist_species_without_accepted_source"]["avonet"])


# ---------------------------------------------------------------- input validation

class InputValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_changed_source_bytes_fail_the_pinned_hash(self) -> None:
        path = self.directory / "source.txt"
        path.write_bytes(b"original")
        digest, _ = builder.sha256_file(path)
        pins = {"p": {"sha256": digest}}
        self.assertEqual({"p": 8}, builder.verify_hashes({"p": path}, pins))
        path.write_bytes(b"original!")
        with self.assertRaisesRegex(builder.CrosswalkError, "does not match the pinned"):
            builder.verify_hashes({"p": path}, pins)

    def test_unpinned_config_is_rejected(self) -> None:
        config = self.directory / "config"
        config.mkdir()
        shutil.copy(ROOT / "config/source-registry.json", config / "source-registry.json")
        points = json.loads((ROOT / "config/collection-points.json").read_text(encoding="utf-8"))

        def blank(node):
            if isinstance(node, dict):
                if node.get("collection_point_id") == builder.ELTON_ID:
                    node["expected_sha256"] = None
                for value in node.values():
                    blank(value)
            elif isinstance(node, list):
                for value in node:
                    blank(value)

        blank(points)
        (config / "collection-points.json").write_text(json.dumps(points), encoding="utf-8")
        with self.assertRaisesRegex(builder.CrosswalkError, "not pinned"):
            builder.load_pins(self.directory)

    def test_avilist_taxonomy_structure_is_checked(self) -> None:
        path = self.directory / "avilist.json"
        path.write_text(json.dumps([[1] * len(builder.AVILIST_COLUMNS)]), encoding="utf-8")
        with self.assertRaisesRegex(builder.CrosswalkError, "row count"):
            builder.read_avilist(path)

    def test_elton_columns_are_checked(self) -> None:
        path = self.directory / "elton.txt"
        path.write_text("SpecID\tScientific\n1\tA b\n", encoding="utf-8")
        with self.assertRaisesRegex(builder.CrosswalkError, "columns missing"):
            builder.read_elton(path)

    def test_avonet_workbook_must_have_the_crosswalk_sheets(self) -> None:
        path = self.directory / "avonet.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                             ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                             '<sheet name="Metadata" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                             '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
            archive.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")
        with self.assertRaisesRegex(builder.CrosswalkError, "sheet missing"):
            builder.read_avonet(path)


@unittest.skipUnless(os.environ.get("ROBINGRAPH_TRAIT_RAW_DIR"), "set ROBINGRAPH_TRAIT_RAW_DIR to the pinned source directory")
class RegenerationTest(unittest.TestCase):
    """Needs the three pinned files (see scripts/build_trait_crosswalk.py --fetch)."""

    def setUp(self) -> None:
        raw = Path(os.environ["ROBINGRAPH_TRAIT_RAW_DIR"])
        self.paths = {i: raw / name for i, name in builder.RAW_NAMES.items()}

    def test_fresh_build_is_byte_identical_to_the_committed_index(self) -> None:
        self.assertEqual(INDEX.read_bytes(), builder.render(builder.generate(self.paths, ROOT)))

    def test_one_changed_byte_in_a_source_stops_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = {}
            for point_id, path in self.paths.items():
                copied[point_id] = Path(directory) / path.name
                shutil.copyfile(path, copied[point_id])
            data = bytearray(copied[builder.ELTON_ID].read_bytes())
            data[-3] ^= 1
            copied[builder.ELTON_ID].write_bytes(bytes(data))
            with self.assertRaisesRegex(builder.CrosswalkError, builder.ELTON_ID):
                builder.generate(copied, ROOT)


if __name__ == "__main__":
    unittest.main()
