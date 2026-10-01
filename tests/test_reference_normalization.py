"""Behavioral regression tests for n8n reference-ingest Code-node scripts.

The production workflow runs these scripts inside n8n.  This test executes the
same exported JavaScript constants with a minimal n8n-shaped Node harness so a
syntax-only workflow check cannot hide normalization or quality-gate regressions.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "generate_n8n_reference_ingest.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("reference_ingest_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load reference-ingest generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()


def run_code_node(script: str, items: list[dict[str, object]], named: dict[str, object]) -> dict[str, object]:
    """Run one n8n Code-node body with only the APIs it declares it needs."""

    harness = """
const payload = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const named = payload.named;
global.$ = name => ({first: () => ({json: named[name]})});
global.$input = {
  all: () => payload.items.map(json => ({json})),
  first: () => ({json: payload.items[0] || {}}),
};
const output = (() => {
__SCRIPT__
})();
process.stdout.write(JSON.stringify(output));
""".replace("__SCRIPT__", script)
    payload = json.dumps({"items": items, "named": named}, ensure_ascii=False)
    completed = subprocess.run(
        ["node", "-e", harness],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=payload,
    )
    result = json.loads(completed.stdout)
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise AssertionError(f"unexpected n8n output: {result!r}")
    value = result[0].get("json")
    if not isinstance(value, dict):
        raise AssertionError(f"n8n output did not contain json: {result!r}")
    return value


def configuration() -> dict[str, object]:
    return {
        "taxonomy_release": "v-test",
        "taxonomy_url": "https://example.invalid/avilist.xlsx",
        "taxonomy_hash": "tax-hash",
        "taxonomy_expected_rows": 3,
        "trait_url": "https://example.invalid/elton.tsv",
        "trait_hash": "trait-hash",
        "trait_expected_rows": 3,
        "trait_expected_valid_rows": 2,
        "checklistbank_dataset_key": 123,
        "checklistbank_version": "2026-01-01",
        "checklistbank_doi": "doi-test",
        "minimum_exact_match_ratio": 0.70,
    }


class ReferenceNormalizationTest(unittest.TestCase):
    def test_avilist_normalizes_identity_hierarchy_and_external_identifiers(self) -> None:
        result = run_code_node(
            GENERATOR.NORMALIZE_AVILIST,
            [
                {"Taxon_rank": "order", "Sequence": "1", "Scientific_name": "Anseriformes"},
                {"Taxon_rank": "family", "Sequence": "2", "Scientific_name": "Anatidae"},
                {"Taxon_rank": "genus", "Sequence": "2.5", "Scientific_name": "Anas"},
                {
                    "Taxon_rank": "species",
                    "Sequence": "3",
                    "Scientific_name": " Anas zonorhyncha ",
                    "Authority": " Swinhoe, 1871 ",
                    "AvibaseID": " 1234 ",
                    "Species_code_Cornell_Lab": " mallar3 ",
                },
                {"Taxon_rank": "kingdom", "Sequence": "4", "Scientific_name": "Animalia"},
            ],
            {
                "Build reference configuration": configuration(),
                "Hash AviList snapshot": {"raw_sha256": "tax-hash"},
            },
        )

        self.assertEqual(4, result["taxonomy_source_row_count"])
        self.assertEqual(4, result["taxonomy_taxon_count"])
        species = result["taxa"][3]
        self.assertEqual("avilist-taxon:v-test:3", species["id"])
        self.assertEqual("Anas zonorhyncha", species["scientific_name"])
        self.assertEqual("Swinhoe, 1871", species["authority"])
        self.assertEqual(
            [
                {"parent_id": "avilist-taxon:v-test:1", "child_id": "avilist-taxon:v-test:2"},
                {"parent_id": "avilist-taxon:v-test:2", "child_id": "avilist-taxon:v-test:2.5"},
                {"parent_id": "avilist-taxon:v-test:2.5", "child_id": "avilist-taxon:v-test:3"},
            ],
            result["taxon_links"],
        )
        self.assertEqual(
            {"avibase", "cornell-lab-species-code"},
            {item["scheme"] for item in result["taxon_identifiers"]},
        )

    def test_avilist_rejects_rows_without_a_stable_source_identity(self) -> None:
        result = run_code_node(
            GENERATOR.NORMALIZE_AVILIST,
            [
                {"Taxon_rank": "species", "Sequence": None, "Scientific_name": "Anas platyrhynchos"},
                {"Taxon_rank": "species", "Sequence": "", "Scientific_name": "Anas acuta"},
                {"Taxon_rank": "species", "Sequence": "3", "Scientific_name": ""},
            ],
            {
                "Build reference configuration": configuration(),
                "Hash AviList snapshot": {"raw_sha256": "tax-hash"},
            },
        )

        self.assertEqual(0, result["taxonomy_taxon_count"])
        self.assertEqual([], result["taxa"])

    def test_avilist_normalizes_compact_explorer_json_without_expanding_n8n_items(self) -> None:
        row = [None] * 26
        row[0] = "3"
        row[1] = "species"
        row[2] = "Anseriformes"
        row[3] = "Anatidae"
        row[4] = "Ducks, Geese and Swans"
        row[5] = "Anas zonorhyncha"
        row[6] = "Swinhoe, 1871"
        row[8] = "Eastern Spot-billed Duck"
        row[13] = "East Asia"
        row[19] = "AVIBASE-TEST"
        result = run_code_node(
            GENERATOR.NORMALIZE_AVILIST,
            [{"data": json.dumps([row])}],
            {
                "Build reference configuration": configuration(),
                "Hash AviList snapshot": {"raw_sha256": "tax-hash"},
            },
        )

        self.assertEqual(1, result["taxonomy_source_row_count"])
        self.assertEqual("Anas zonorhyncha", result["taxa"][0]["scientific_name"])
        self.assertEqual("East Asia", result["taxa"][0]["range_text"])
        self.assertEqual("AVIBASE-TEST", result["taxon_identifiers"][0]["value"])

    def test_elton_normalizes_finite_measurements_and_quarantines_missing_identity(self) -> None:
        result = run_code_node(
            GENERATOR.NORMALIZE_ELTON,
            [
                {
                    "SpecID": "42",
                    "Scientific": " Anas zonorhyncha ",
                    "Taxo": "Anatidae",
                    "BodyMass-Value": "1100.5",
                    "BodyMass-Source": "handbook",
                    "BodyMass-SpecLevel": "species",
                    "Nocturnal": "0",
                    "PelagicSpecialist": "1",
                    "Diet-5Cat": "omnivore",
                    "Diet-Inv": "100",
                    "Diet-Fish": "not-a-number",
                    "ForStrat-ground": "100",
                },
                {"SpecID": "", "Scientific": "Missing identity"},
                {"SpecID": "ignored", "not_scientific": "not an Elton row"},
            ],
            {"Hash EltonTraits snapshot": {"raw_sha256": "trait-hash"}},
        )

        self.assertEqual("trait-hash", result["trait_sha256"])
        self.assertEqual(2, result["trait_source_row_count"])
        self.assertEqual(1, result["trait_valid_row_count"])
        self.assertEqual(1, result["trait_invalid_row_count"])
        profile = result["trait_profiles"][0]
        self.assertEqual("Anas zonorhyncha", profile["scientific_name"])
        self.assertEqual(1100.5, profile["body_mass_g"])
        self.assertIsNone(profile["diet_distribution"]["fish"])
        self.assertEqual(100, profile["foraging_distribution"]["ground"])

    def test_elton_rejects_invalid_measurements_distributions_and_duplicate_ids(self) -> None:
        valid_distribution = {"Diet-Inv": "100", "ForStrat-ground": "100"}
        result = run_code_node(
            GENERATOR.NORMALIZE_ELTON,
            [
                {"SpecID": "mass", "Scientific": "Mass bird", "BodyMass-Value": "0", **valid_distribution},
                {"SpecID": "flag", "Scientific": "Flag bird", "Nocturnal": "2", **valid_distribution},
                {"SpecID": "range", "Scientific": "Range bird", "Diet-Inv": "101", "ForStrat-ground": "100"},
                {"SpecID": "sum", "Scientific": "Sum bird", "Diet-Inv": "95", "ForStrat-ground": "100"},
                {"SpecID": "rounded", "Scientific": "Rounded bird", "Diet-Inv": "99", "ForStrat-ground": "100"},
                {"SpecID": "duplicate", "Scientific": "First bird", **valid_distribution},
                {"SpecID": "duplicate", "Scientific": "Second bird", **valid_distribution},
            ],
            {"Hash EltonTraits snapshot": {"raw_sha256": "trait-hash"}},
        )

        self.assertEqual(2, result["trait_valid_row_count"])
        self.assertEqual(5, result["trait_invalid_row_count"])
        reasons = {row["source_taxon_id"]: row["reason"] for row in result["trait_invalid_rows"]}
        self.assertIn("invalid_body_mass", reasons["mass"])
        self.assertIn("invalid_nocturnal", reasons["flag"])
        self.assertIn("out_of_range_diet_distribution_invertebrate", reasons["range"])
        self.assertIn("invalid_diet_distribution_sum", reasons["sum"])
        self.assertEqual("duplicate_source_taxon_id", reasons["duplicate"])
        rounded = next(profile for profile in result["trait_profiles"] if profile["source_taxon_id"] == "rounded")
        self.assertEqual(99, rounded["diet_distribution"]["invertebrate"])
        self.assertEqual(["diet_distribution_total:99"], rounded["distribution_warnings"])

    def test_assembly_preserves_units_provenance_and_unmatched_taxa_as_candidates(self) -> None:
        config = configuration()
        config["trait_expected_valid_rows"] = 2
        config["minimum_exact_match_ratio"] = 0.4
        profile = {
            "source_taxon_id": "42",
            "scientific_name": "Anas zonorhyncha",
            "source_taxonomy": "EltonTraits",
            "body_mass_g": 1100.5,
            "body_mass_source": "handbook",
            "body_mass_spec_level": "species",
            "nocturnal": 0,
            "pelagic_specialist": 1,
            "diet_category": "omnivore",
            "diet_source": "handbook",
            "diet_certainty": "high",
            "diet_distribution": {"fish": 100},
            "foraging_distribution": {"ground": 99},
            "distribution_warnings": ["foraging_distribution_total:99"],
            "foraging_source": "handbook",
            "foraging_spec_level": "species",
        }
        input_data = {
            "taxonomy_sha256": "tax-hash",
            "taxonomy_source_row_count": 3,
            "taxonomy_taxon_count": 3,
            "taxonomy_duplicate_species_names": 0,
            "trait_sha256": "trait-hash",
            "trait_source_row_count": 3,
            "trait_valid_row_count": 2,
            "trait_invalid_row_count": 0,
            "checklistbank_release_ok": True,
            "taxa": [
                {"id": "taxon:duck", "rank": "species", "scientific_name": "Anas zonorhyncha"},
                {"id": "taxon:genus", "rank": "genus", "scientific_name": "Anas"},
            ],
            "trait_profiles": [profile, {**profile, "source_taxon_id": "43", "scientific_name": "No match"}],
            "taxon_links": [],
            "taxon_identifiers": [],
        }
        result = run_code_node(
            GENERATOR.ASSEMBLE_REFERENCE,
            [input_data],
            {"Build reference configuration": config},
        )

        self.assertTrue(result["ready_to_load"])
        self.assertEqual(1, result["trait_exact_match_count"])
        self.assertEqual(0.5, result["trait_exact_match_ratio"])
        claims = {claim["trait_name"]: claim for claim in result["trait_claims"]}
        self.assertEqual(6, len(claims))
        self.assertEqual("g", claims["body_mass"]["unit"])
        self.assertEqual(1100.5, claims["body_mass"]["value_num"])
        self.assertEqual("percent", claims["diet_distribution"]["unit"])
        self.assertEqual({"fish": 100}, json.loads(claims["diet_distribution"]["value_json"]))
        self.assertEqual({"ground": 99}, json.loads(claims["foraging_strata_distribution"]["value_json"]))
        self.assertEqual("handbook; foraging_distribution_total:99", claims["foraging_strata_distribution"]["source_note"])
        self.assertEqual("eltontraits-evidence:v1:42", claims["body_mass"]["evidence_id"])
        self.assertIn("#SpecID=42", claims["body_mass"]["source_uri"])
        self.assertEqual(1, result["mapping_candidate_count"])
        self.assertEqual("exact_name_not_found", result["mapping_candidates"][0]["reason_code"])

    def test_assembly_blocks_bad_snapshot_duplicate_names_and_insufficient_exact_mapping(self) -> None:
        config = configuration()
        input_data = {
            "taxonomy_sha256": "unexpected",
            "taxonomy_source_row_count": 2,
            "taxonomy_taxon_count": 2,
            "taxonomy_duplicate_species_names": 1,
            "trait_sha256": "unexpected",
            "trait_source_row_count": 1,
            "trait_valid_row_count": 1,
            "trait_invalid_row_count": 0,
            "checklistbank_release_ok": False,
            "checklistbank_failure_reason": "pinned release mismatch",
            "taxa": [{"id": "taxon:one", "rank": "species", "scientific_name": "One bird"}],
            "trait_profiles": [{"source_taxon_id": "1", "scientific_name": "Other bird"}],
            "taxon_links": [],
            "taxon_identifiers": [],
        }
        result = run_code_node(
            GENERATOR.ASSEMBLE_REFERENCE,
            [input_data],
            {"Build reference configuration": config},
        )

        self.assertFalse(result["ready_to_load"])
        self.assertEqual((), tuple(result["trait_claims"]))
        for reason in (
            "AviList SHA-256 mismatch",
            "AviList species names are not unique",
            "EltonTraits SHA-256 mismatch",
            "pinned release mismatch",
            "Exact trait mapping ratio",
            "No trait claims were produced",
        ):
            self.assertIn(reason, result["failure_reason"])


if __name__ == "__main__":
    unittest.main()
