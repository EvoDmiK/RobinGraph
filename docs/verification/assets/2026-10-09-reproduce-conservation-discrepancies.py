#!/usr/bin/env python3
"""Reproducibility script for conservation index discrepancy analysis.

Analyzes the 3,624 excluded taxa between AviList v2025b and GBIF IUCN 2026-1.
Outputs detailed breakdown JSON including file checksums, classification rules,
and overlap analysis for the 2,286 authority mismatches.

Note on Surname Verification:
This script does NOT perform author surname equality comparison.
The 933 count merely represents records where year difference and parenthesis
difference flags were false under heuristic pattern checks. Surname agreement
remains unverified.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

# Run from a checkout with PYTHONPATH=src; no credentials or network access.
from robingraph.retrieval.conservation import _authority_match

DEFAULT_AVILIST = Path("/tmp/rg010-avilist.json")
DEFAULT_IUCN = Path("/tmp/gbif-iucn-quality-review-2026-1.zip")
DEFAULT_OUTPUT = Path("/tmp/conservation_discrepancy_breakdown.json")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avilist", type=Path, default=DEFAULT_AVILIST, help="Path to AviList JSON snapshot")
    parser.add_argument("--iucn", type=Path, default=DEFAULT_IUCN, help="Path to GBIF IUCN zip archive")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output breakdown JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    avilist_path = args.avilist.resolve()
    iucn_path = args.iucn.resolve()
    output_path = args.output.resolve()

    avilist_sha = sha256_file(avilist_path)
    iucn_sha = sha256_file(iucn_path)

    with open(avilist_path, "r", encoding="utf-8") as f:
        avilist = json.load(f)

    active_species = [r for r in avilist if r[1] == "species"]

    with zipfile.ZipFile(iucn_path) as z:
        with z.open("taxon.txt") as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            source_rows = [
                r for r in reader
                if len(r) > 12 and r[4] == "AVES" and r[10] == "species" and r[12] == "accepted"
            ]

    by_sis = {r[0]: r for r in source_rows}

    # Baseline exclusion category counts
    top_categories = Counter()
    failed_auth_records = []

    for r in active_species:
        seq, name, auth, grade, ref = r[0], r[5], r[6], r[15], r[16]
        grade_clean = grade.strip().upper() if isinstance(grade, str) else ""
        link = re.fullmatch(r"https://datazone\.birdlife\.org/species/factsheet/([1-9][0-9]*)", ref or "")

        if grade_clean == "NE":
            top_categories["avilist_ne_requires_concept_review"] += 1
            continue
        if not ref or not link:
            top_categories["missing_or_invalid_birdlife_link"] += 1
            continue

        sis_id = link[1]
        s_row = by_sis.get(sis_id)
        if not s_row:
            top_categories["no_accepted_source_bird_species"] += 1
            continue

        s_name = " ".join((s_row[7], s_row[8]))
        if s_name != name:
            top_categories["scientific_name_mismatch"] += 1
            continue

        auth_match = _authority_match(auth, s_row[9])
        if not auth_match:
            top_categories["authority_mismatch"] += 1
            failed_auth_records.append({
                "sequence": seq,
                "scientific_name": name,
                "avilist_authority": auth,
                "iucn_authority": s_row[9],
                "sis_id": sis_id
            })
            continue

        match_url = re.fullmatch(r"https://www\.iucnredlist\.org/species/([1-9][0-9]*)/([1-9][0-9]*)", s_row[15])
        cited = re.findall(r"RLTS\.T([1-9][0-9]*)A([1-9][0-9]*)\.en", s_row[14])
        if not match_url or match_url[1] != sis_id or cited != [(sis_id, match_url[2])]:
            top_categories["assessment_identity_or_citation_mismatch"] += 1
            continue

        top_categories["mapped_species"] += 1

    # Detailed breakdown of the 2,286 authority_mismatch records
    independent_features = Counter()
    combination_breakdown = Counter()
    waterfall_breakdown = Counter()

    for item in failed_auth_records:
        a = item["avilist_authority"]
        b = item["iucn_authority"]

        is_multi = (";" in a) or ("&" in b) or ("et al" in a.lower()) or ("et al" in b.lower())

        ya = re.findall(r"\b(1[789][0-9]{2}|20[0-2][0-9])\b", a)
        yb = re.findall(r"\b(1[789][0-9]{2}|20[0-2][0-9])\b", b)
        is_year = bool(ya and yb and ya[-1] != yb[-1])

        is_paren = (a.strip().startswith("(") != b.strip().startswith("("))
        is_dots = ("." in b)

        if is_multi: independent_features["multi_author"] += 1
        if is_year: independent_features["year_diff"] += 1
        if is_paren: independent_features["parenthesis_diff"] += 1
        if is_dots: independent_features["dots_in_iucn"] += 1

        combo = []
        if is_multi: combo.append("multi_author")
        if is_year: combo.append("year_diff")
        if is_paren: combo.append("paren_diff")
        if is_dots: combo.append("dots_iucn")
        if not combo: combo.append("other_orthography")
        combination_breakdown["+".join(combo)] += 1

        # Hierarchical waterfall assignment
        if is_multi:
            waterfall_breakdown["multi_author"] += 1
        elif is_year:
            waterfall_breakdown["year_diff"] += 1
        elif is_paren:
            waterfall_breakdown["paren_diff"] += 1
        elif is_dots:
            waterfall_breakdown["dots_iucn"] += 1
        else:
            waterfall_breakdown["other_orthography"] += 1

    # Candidate grouping by observed heuristic flags (NOT surname verification)
    no_year_or_paren_flag_count = (
        combination_breakdown["multi_author"]
        + combination_breakdown["dots_iucn"]
        + combination_breakdown["multi_author+dots_iucn"]
    )
    flagged_discrepancy_count = len(failed_auth_records) - no_year_or_paren_flag_count

    result = {
        "analysis_metadata": {
            "created_at": "2026-10-09T17:33:00+09:00",
            "environment": "RobinGraph dev-3 offline reproducibility script",
            "source_files": {
                "avilist_path": str(avilist_path),
                "avilist_sha256": avilist_sha,
                "iucn_archive_path": str(iucn_path),
                "iucn_archive_sha256": iucn_sha,
            }
        },
        "baseline_species_counts": {
            "total_active_species": len(active_species),
            "mapped_species": top_categories["mapped_species"],
            "total_excluded": len(active_species) - top_categories["mapped_species"],
            "exclusion_categories": {
                "authority_mismatch": top_categories["authority_mismatch"],
                "avilist_ne_requires_concept_review": top_categories["avilist_ne_requires_concept_review"],
                "scientific_name_mismatch": top_categories["scientific_name_mismatch"],
                "assessment_identity_or_citation_mismatch": top_categories["assessment_identity_or_citation_mismatch"],
            }
        },
        "authority_mismatch_analysis": {
            "total_count": len(failed_auth_records),
            "explanation": "Scientific name and BirdLife SIS ID match 100%, but author strings differ",
            "surname_comparison_executed": False,
            "surname_verification_disclaimer": "This script did NOT evaluate author surname equality. Flag grouping below is strictly based on punctuation and year heuristics.",
            "independent_feature_occurrences": dict(independent_features),
            "hierarchical_waterfall_decomposition": {
                "description": "Waterfall order: multi_author -> year_diff -> paren_diff -> dots_iucn -> other",
                "counts": dict(waterfall_breakdown),
                "sum": sum(waterfall_breakdown.values())
            },
            "mutually_exclusive_combination_decomposition": {
                "description": "Exact disjoint subsets accounting for all overlaps",
                "counts": dict(sorted(combination_breakdown.items(), key=lambda x: -x[1])),
                "sum": sum(combination_breakdown.values())
            },
            "heuristic_flag_grouping": {
                "no_detected_year_or_parenthesis_flag": {
                    "count": no_year_or_paren_flag_count,
                    "categories_included": ["multi_author (pure: 823)", "dots_iucn (pure: 73)", "multi_author+dots_iucn (37)"],
                    "character": "Observation only: no year or parenthesis differences detected by heuristics. Surname agreement NOT verified."
                },
                "detected_year_parenthesis_or_other_flags": {
                    "count": flagged_discrepancy_count,
                    "character": "Flagged for year difference (693 total), basionym parenthesis (371 total), or other orthography (328)."
                }
            }
        },
        "overall_candidate_landscape": {
            "current_verified_linked": top_categories["mapped_species"],
            "unlinked_groups_observed": {
                "authority_mismatch_unlinked": len(failed_auth_records),
                "scientific_name_mismatch_unlinked": top_categories["scientific_name_mismatch"],
                "assessment_identity_or_citation_mismatch_unlinked": top_categories["assessment_identity_or_citation_mismatch"],
                "avilist_ne_concept_non_match_unlinked": top_categories["avilist_ne_requires_concept_review"],
                "total_unlinked": len(active_species) - top_categories["mapped_species"]
            },
            "cautionary_note": "All unlinked groups require independent syntactic and semantic verification before any mapping activation."
        }
    }

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_path} successfully.")
    print(f"Total active: {result['baseline_species_counts']['total_active_species']}, Mapped: {result['baseline_species_counts']['mapped_species']}")


if __name__ == "__main__":
    main()
