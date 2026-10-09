#!/usr/bin/env python3
"""Build the AviList trait-source crosswalk index (EltonTraits / AVONET).

The output, ``src/robingraph/retrieval/trait_crosswalk.json``, is a *mapping
index only*: it never copies or changes a source trait value. A later ingest
step may use the ``accepted`` entries to attach existing source rows to an
AviList species; every other entry is deliberately left unattached.

Policy (see ``policy`` in the output for the same text):

* AVONET row -> AviList species: the row's ``Avibase.ID1`` must equal the
  ``AvibaseID`` of exactly one AviList species (case-insensitive; AVONET writes
  ``AVIBASE-...``, AviList ``avibase-...``).
* EltonTraits row -> AviList species: only through the published AVONET
  ``BirdLife-BirdTree crosswalk`` sheet, and only for ``1BL to 1BT`` rows whose
  BirdLife species then has a unique Avibase ID matching exactly one AviList
  species. Elton rows whose ``Taxo`` is not ``BL3`` are ``needs_review``.
* Never used: name similarity, edit distance, epithet-only matches, one-to-many
  matches, or any rule that picks one of several candidates.
* A target claimed by several source rows (including a row whose own name
  equals the target) is not auto-accepted; the reason is recorded.
* An existing exact-name match whose concept ID differs (or cannot be shown to
  agree) is ``needs_review`` (``alignment``); the generator does not claim the
  source row predates a split.

Standard library only. Source files are untrusted input: they are read, never
executed, and every one is checked against the SHA-256 pinned in
``config/collection-points.json`` before parsing.

Usage::

    python scripts/build_trait_crosswalk.py --fetch RAW_DIR   # download pinned files
    python scripts/build_trait_crosswalk.py --raw-dir RAW_DIR # (re)write the index
    python scripts/build_trait_crosswalk.py --raw-dir RAW_DIR --check
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/robingraph/retrieval/trait_crosswalk.json"
SCHEMA_VERSION = 1
GENERATOR = "scripts/build_trait_crosswalk.py"

AVILIST_ID = "taxonomy-avilist-v2025b"
ELTON_ID = "traits-eltontraits-v1"
AVONET_ID = "traits-avonet"
RAW_NAMES = {AVILIST_ID: "avilist-2025b.json", ELTON_ID: "BirdFuncDat.txt", AVONET_ID: "AVONET_Supplementary_dataset_1.xlsx"}

# Structure the pinned files are known to have. A mismatch means the file is not
# the audited snapshot even if somebody also changed the pinned hash.
EXPECTED = {
    "avilist_rows": 33684,
    "avilist_species": 11131,
    "elton_rows": 9995,
    "elton_named_rows": 9993,
    "avonet1_rows": 11009,
    "avonet3_rows": 9993,
    "crosswalk_rows": 11289,
}
AVILIST_COLUMNS = [
    "Sequence", "Taxon_rank", "Order", "Family", "Family_English_name", "Scientific_name", "Authority",
    "Bibliographic_details", "English_name_AviList", "English_name_Clements_v2025", "English_name_BirdLife_v10",
    "Proposal_number", "Decision_summary", "Range", "Extinct_or_possibly_extinct", "IUCN_Red_List_Category",
    "BirdLife_DataZone_URL", "Species_code_Cornell_Lab", "Birds_of_the_World_URL", "AvibaseID",
    "Gender_of_genus", "Type_species_of_genus", "Type_locality", "Title_of_original_description",
    "Original_description_URL", "Protonym",
]
ELTON_REQUIRED = ["SpecID", "Taxo", "Scientific", "English", "BLFamilyLatin"]
AVONET_SHEETS = {
    "avonet1": "AVONET1_BirdLife",
    "avonet3": "AVONET3_BirdTree",
    "crosswalk": "BirdLife–BirdTree crosswalk",  # en dash, as in the workbook
}
AVONET_REQUIRED = {
    "avonet1": ["Sequence", "Species1", "Avibase.ID1", "Inference"],
    "avonet3": ["Species3"],
    "crosswalk": ["Species1", "Species3", "Match.type"],
}
ONE_TO_ONE = "1BL to 1BT"
TRUSTED_ELTON_TAXO = "BL3"
MAX_ZIP_BYTES = 600 * 1024 * 1024

POLICY = {
    "avonet": "accepted only when AVONET Avibase.ID1 equals the AvibaseID of exactly one AviList species and no other AVONET row shares that ID or the target name",
    "eltontraits": "accepted only through the AVONET BirdLife-BirdTree crosswalk row with Match.type '1BL to 1BT' (both directions unique) -> that BirdLife species' unique Avibase.ID1 -> exactly one AviList species, Taxo BL3, no competing source row",
    "not_used": ["name similarity", "edit distance", "epithet-only match", "one-to-many or many-to-one match", "choosing among candidates"],
    "needs_review": "candidate exists but is not proven (Taxo other than BL3, exact-name target with a different or unverifiable concept ID, competing source rows); alignment is not asserted to be a pre-split record",
    "unresolved": "no candidate that satisfies the rules; trait rows stay unattached",
    "avibase_id_semantics": (
        "An Avibase ID identifies one taxonomic concept (a circumscription cluster), not a name: a genus change or spelling "
        "change keeps the ID, a split or lump that changes the circumscription gets a new ID, and congruent concepts "
        "from different authorities share it (Lepage et al. 2014, ZooKeys 420:117-135, doi:10.3897/zookeys.420.7089; "
        "the Cornell Clements 'Taxon Concept Id' notes say the same). Equality of IDs is therefore treated as evidence of "
        "the same concept, but it is the curators' mapping, not an independent verification; partly overlapping concepts "
        "are the documented limit."
    ),
}

SCHEMA_DOC = {
    "entry_columns": [
        "dataset", "source_row", "source_id", "source_name", "source_taxonomy",
        "target_sequence", "target_name", "target_avibase_id",
        "status", "method", "name_relation", "reason", "evidence",
    ],
    "dataset": "'avonet' or 'eltontraits'",
    "source_row": "AVONET: row number in sheet AVONET1_BirdLife (header = row 1). Elton: line number in BirdFuncDat.txt (header = line 1)",
    "source_id": "AVONET: Avibase.ID1 as written in the source. Elton: SpecID",
    "source_taxonomy": "AVONET: 'HBW-BirdLife v5.0'. Elton: the Taxo column value (BL3 or IOC27)",
    "target_sequence": "AviList Sequence of the AviList species (null when no candidate)",
    "target_name": "AviList Scientific_name of that species; for needs_review a candidate, not an approval",
    "target_avibase_id": "AviList AvibaseID of that species",
    "status": "'accepted' | 'needs_review' | 'unresolved'. Only 'accepted' may be used to attach source rows",
    "method": "'avibase_id_unique' | 'birdtree_birdlife_avibase_chain' | 'exact_name_legacy' (needs_review candidate taken from the old exact-name rule) | null",
    "name_relation": "accepted/needs_review with a target: 'same_name' | 'name_changed'; else null",
    "reason": "null for accepted; otherwise a code from summary.reasons",
    "evidence": "small object: ids/names/match types the decision used; null when nothing was matched",
    "use": "attach source rows only where status == 'accepted'; source values and percentages are never modified by this index",
}


class CrosswalkError(RuntimeError):
    """A source file is not the pinned, structurally valid snapshot."""


def norm_id(value) -> str:
    return (value or "").strip().lower()


def clean(value) -> str:
    return (value or "").strip()


# ---------------------------------------------------------------- inputs

def load_pins(root: Path = ROOT) -> dict:
    """Pinned URLs/hashes/licenses come from the repository config only."""
    points = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("collection_point_id") in (AVILIST_ID, ELTON_ID, AVONET_ID):
                points[node["collection_point_id"]] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads((root / "config/collection-points.json").read_text(encoding="utf-8")))
    registry = {s["source_id"]: s for s in json.loads((root / "config/source-registry.json").read_text(encoding="utf-8"))}
    pins = {}
    for point_id in (AVILIST_ID, ELTON_ID, AVONET_ID):
        point = points.get(point_id)
        if point is None:
            raise CrosswalkError(f"collection point {point_id} missing from config")
        source = registry.get(point["source_id"])
        if source is None:
            raise CrosswalkError(f"source {point['source_id']} missing from registry")
        sha = point.get("expected_sha256") or ""
        if not re.fullmatch(r"[0-9a-f]{64}", sha) or not point["endpoint_uri"].startswith("https://"):
            raise CrosswalkError(f"{point_id} is not pinned by an https URL and a full SHA-256")
        pins[point_id] = {
            "source_id": point["source_id"], "name": source["name"], "provider": source.get("provider"),
            "url": point["endpoint_uri"], "release": point["source_release"], "sha256": sha,
            "license_name": source["license_name"], "license_uri": source["license_uri"],
            "landing_uri": source["landing_uri"],
        }
    return pins


def sha256_file(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def fetch_all(directory: Path, pins: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for point_id, pin in pins.items():
        target = directory / RAW_NAMES[point_id]
        request = Request(pin["url"], headers={"User-Agent": "RobinGraph trait crosswalk builder"})
        with urlopen(request, timeout=300) as response, open(target, "wb") as out:  # noqa: S310 (pinned https URL)
            for block in iter(lambda: response.read(1 << 20), b""):
                out.write(block)
        digest, _ = sha256_file(target)
        if digest != pin["sha256"]:
            target.unlink()
            raise CrosswalkError(f"{point_id}: downloaded file hash {digest} differs from the pin")


def verify_hashes(paths: dict, pins: dict) -> dict:
    sizes = {}
    for point_id, pin in pins.items():
        digest, size = sha256_file(paths[point_id])
        if digest != pin["sha256"]:
            raise CrosswalkError(f"{point_id}: SHA-256 {digest} does not match the pinned {pin['sha256']}")
        sizes[point_id] = size
    return sizes


def read_avilist(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) != EXPECTED["avilist_rows"]:
        raise CrosswalkError(f"AviList row count {len(raw) if isinstance(raw, list) else 'n/a'} != {EXPECTED['avilist_rows']}")
    rows = []
    for position, item in enumerate(raw):
        if not isinstance(item, list) or len(item) != len(AVILIST_COLUMNS):
            raise CrosswalkError(f"AviList row {position} does not have {len(AVILIST_COLUMNS)} columns")
        rows.append(dict(zip(AVILIST_COLUMNS, item)))
    species = [r for r in rows if r["Taxon_rank"] == "species"]
    if len(species) != EXPECTED["avilist_species"]:
        raise CrosswalkError(f"AviList species count {len(species)} != {EXPECTED['avilist_species']}")
    return rows


def read_elton(path: Path) -> list[dict]:
    # The file mixes Windows-1252 bytes into free-text columns. latin-1 maps every byte
    # one-to-one; the columns used here must still be pure ASCII (checked below).
    with open(path, newline="", encoding="latin-1") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = [c for c in ELTON_REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise CrosswalkError(f"EltonTraits columns missing: {missing}")
        rows = []
        for number, record in enumerate(reader, start=2):
            record["_line"] = number
            rows.append(record)
    if any(not clean(r[c]).isascii() for r in rows for c in ("SpecID", "Taxo", "Scientific")):
        raise CrosswalkError("EltonTraits identity columns contain non-ASCII text")
    if len(rows) != EXPECTED["elton_rows"]:
        raise CrosswalkError(f"EltonTraits row count {len(rows)} != {EXPECTED['elton_rows']}")
    if sum(1 for r in rows if clean(r["Scientific"])) != EXPECTED["elton_named_rows"]:
        raise CrosswalkError("EltonTraits named-row count differs from the audited snapshot")
    return rows


_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def read_avonet(path: Path) -> dict[str, list[dict]]:
    """Read the three needed sheets with the standard library only."""
    with zipfile.ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_ZIP_BYTES:
            raise CrosswalkError("AVONET workbook expands beyond the allowed size")
        ns = {"m": _MAIN}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{_MAIN}}}t"))
            for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        targets = {}
        for sheet in workbook.find("m:sheets", ns):
            target = relations[sheet.get(f"{{{_REL}}}id")].lstrip("/")
            targets[sheet.get("name")] = target if target.startswith("xl/") else f"xl/{target}"
        result = {}
        for key, sheet_name in AVONET_SHEETS.items():
            if sheet_name not in targets:
                raise CrosswalkError(f"AVONET sheet missing: {sheet_name}")
            rows = []
            for _, element in ET.iterparse(archive.open(targets[sheet_name])):
                if not element.tag.endswith("}row"):
                    continue
                cells = {}
                for cell in element:
                    value = cell.find("m:v", ns)
                    if value is None:
                        continue
                    column = 0
                    for char in re.match(r"[A-Z]+", cell.get("r")).group():
                        column = column * 26 + ord(char) - 64
                    cells[column - 1] = shared[int(value.text)] if cell.get("t") == "s" else value.text
                rows.append((int(element.get("r")), cells))
                element.clear()
            header_cells = rows[0][1]
            header = [header_cells.get(i) for i in range(max(header_cells) + 1)]
            missing = [c for c in AVONET_REQUIRED[key] if c not in header]
            if missing:
                raise CrosswalkError(f"AVONET sheet {sheet_name} columns missing: {missing}")
            result[key] = [
                {**{header[i]: cells.get(i) for i in range(len(header))}, "_row": number}
                for number, cells in rows[1:] if cells
            ]
    expected = {"avonet1": EXPECTED["avonet1_rows"], "avonet3": EXPECTED["avonet3_rows"], "crosswalk": EXPECTED["crosswalk_rows"]}
    for key, count in expected.items():
        if len(result[key]) != count:
            raise CrosswalkError(f"AVONET sheet {AVONET_SHEETS[key]} has {len(result[key])} rows, expected {count}")
    return result


# ---------------------------------------------------------------- mapping

class _Targets:
    """AviList species lookups; ambiguity is kept visible, never resolved."""

    def __init__(self, avilist: list[dict]):
        species = [r for r in avilist if r["Taxon_rank"] == "species"]
        self.by_name: dict[str, dict] = {}
        self.by_id: dict[str, list[dict]] = defaultdict(list)
        for record in species:
            self.by_name[record["Scientific_name"]] = record
            if clean(record["AvibaseID"]):
                self.by_id[norm_id(record["AvibaseID"])].append(record)
        self.species_count = len(species)
        self.duplicate_id_count = sum(1 for v in self.by_id.values() if len(v) > 1)


def _entry(dataset, source_row, source_id, source_name, taxonomy, target, status, method, reason, evidence):
    relation = None
    if target is not None:
        relation = "same_name" if target["Scientific_name"] == source_name else "name_changed"
    return {
        "dataset": dataset, "source_row": source_row, "source_id": source_id, "source_name": source_name,
        "source_taxonomy": taxonomy,
        "target_sequence": target["Sequence"] if target else None,
        "target_name": target["Scientific_name"] if target else None,
        "target_avibase_id": target["AvibaseID"] if target else None,
        "status": status, "method": method, "name_relation": relation, "reason": reason,
        "evidence": evidence or None,
    }


def _map_avonet(rows, targets: _Targets) -> list[dict]:
    id_counts = Counter(norm_id(r["Avibase.ID1"]) for r in rows if clean(r["Avibase.ID1"]))
    name_counts = Counter(clean(r["Species1"]) for r in rows)
    entries = []
    for row in rows:
        name, raw_id = clean(row["Species1"]), clean(row["Avibase.ID1"])
        exact = targets.by_name.get(name)
        taxonomy = "HBW-BirdLife v5.0"
        evidence = {"inference": row.get("Inference")}
        make = lambda target, status, method, reason, extra=None: _entry(  # noqa: E731
            "avonet", row["_row"], raw_id or None, name, taxonomy, target, status, method, reason, {**evidence, **(extra or {})})
        if not name:
            entries.append(make(None, "unresolved", None, "missing_source_name"))
            continue
        if not raw_id:
            entries.append(make(exact, "needs_review", "exact_name_legacy", "missing_avibase_id_exact_name_only") if exact
                           else make(None, "unresolved", None, "missing_avibase_id"))
            continue
        candidates = targets.by_id.get(norm_id(raw_id), [])
        if len(candidates) > 1:
            entries.append(make(None, "unresolved", None, "avilist_avibase_id_not_unique", {"candidates": len(candidates)}))
        elif len(candidates) == 1:
            target = candidates[0]
            if id_counts[norm_id(raw_id)] > 1:
                entries.append(make(target, "needs_review", "avibase_id_unique", "multiple_source_rows_same_avibase_id"))
            elif exact is not None and exact is not target:
                entries.append(make(target, "needs_review", "avibase_id_unique", "exact_name_points_to_different_taxon",
                                    {"exact_name_target": exact["Scientific_name"], "exact_name_avibase_id": exact["AvibaseID"]}))
            elif target["Scientific_name"] != name and name_counts[target["Scientific_name"]] > 0:
                entries.append(make(target, "needs_review", "avibase_id_unique", "target_name_used_by_other_source_row"))
            else:
                entries.append(make(target, "accepted", "avibase_id_unique", None))
        elif exact is not None:
            entries.append(make(exact, "needs_review", "exact_name_legacy", "exact_name_concept_id_mismatch",
                                {"exact_name_avibase_id": exact["AvibaseID"]}))
        else:
            entries.append(make(None, "unresolved", None, "no_avibase_match_no_exact_name"))
    return entries


_CHAIN_REASON = {
    "1BL to many BT": "birdtree_splits_birdlife_species",
    "Many BL to 1BT": "birdtree_merges_birdlife_species",
    "Extinct": "crosswalk_extinct",
    "Newly described species": "crosswalk_newly_described",
    "Invalid taxon": "crosswalk_invalid_taxon",
}


def _map_elton(rows, avonet, targets: _Targets) -> list[dict]:
    birdtree_names = {clean(r["Species3"]) for r in avonet["avonet3"]}
    by_birdtree: dict[str, list[dict]] = defaultdict(list)
    by_birdlife: dict[str, list[dict]] = defaultdict(list)
    for item in avonet["crosswalk"]:
        if clean(item["Species3"]):
            by_birdtree[clean(item["Species3"])].append(item)
        if clean(item["Species1"]):
            by_birdlife[clean(item["Species1"])].append(item)
    avonet1: dict[str, list[dict]] = defaultdict(list)
    for item in avonet["avonet1"]:
        avonet1[clean(item["Species1"])].append(item)

    entries = []
    for row in rows:
        name = clean(row["Scientific"])
        if not name:
            continue  # no identity: nothing to index (counted in summary.source_rows_without_name)
        spec_id, taxo = clean(row["SpecID"]), clean(row["Taxo"])
        exact = targets.by_name.get(name)
        make = lambda target, status, method, reason, extra=None: _entry(  # noqa: E731
            "eltontraits", row["_line"], spec_id, name, taxo, target, status, method, reason, extra)

        def fallback(reason, extra=None):
            if exact is not None:
                return make(exact, "needs_review", "exact_name_legacy", reason, extra)
            return make(None, "unresolved", None, reason, extra)

        if name not in birdtree_names:
            entries.append(fallback("name_not_in_birdtree_list"))
            continue
        links = by_birdtree.get(name, [])
        if not links:
            entries.append(fallback("birdtree_name_not_in_crosswalk"))
            continue
        types = sorted({clean(link["Match.type"]) for link in links})
        chain = {"birdtree_name": name, "match_types": types, "birdlife_names": sorted({clean(l["Species1"]) for l in links})}
        if len(links) > 1:
            entries.append(fallback("birdtree_merges_birdlife_species", chain))
            continue
        link = links[0]
        if clean(link["Match.type"]) != ONE_TO_ONE:
            entries.append(fallback(_CHAIN_REASON.get(clean(link["Match.type"]), "crosswalk_match_type_not_one_to_one"), chain))
            continue
        birdlife = clean(link["Species1"])
        if len(by_birdlife[birdlife]) != 1:
            entries.append(fallback("birdlife_species_in_several_crosswalk_rows", chain))
            continue
        profiles = avonet1.get(birdlife, [])
        if len(profiles) != 1 or not clean(profiles[0]["Avibase.ID1"]):
            entries.append(fallback("birdlife_species_without_unique_avonet_avibase_id", chain))
            continue
        avibase = clean(profiles[0]["Avibase.ID1"])
        chain["avibase_id"] = avibase
        candidates = targets.by_id.get(norm_id(avibase), [])
        if len(candidates) != 1:
            entries.append(fallback("avibase_id_not_unique_in_avilist" if candidates else "avibase_id_not_in_avilist", chain))
            continue
        target = candidates[0]
        if taxo != TRUSTED_ELTON_TAXO:
            entries.append(make(target, "needs_review", "birdtree_birdlife_avibase_chain", "taxo_not_bl3_crosswalk_basis_unverified", chain))
        elif exact is not None and exact is not target:
            entries.append(make(target, "needs_review", "birdtree_birdlife_avibase_chain", "exact_name_chain_target_mismatch",
                                {**chain, "exact_name_target": exact["Scientific_name"], "exact_name_avibase_id": exact["AvibaseID"]}))
        else:
            entries.append(make(target, "accepted", "birdtree_birdlife_avibase_chain", None, chain))
    return entries


def _demote_conflicts(entries: list[dict], source_rows: dict[str, list[str]]) -> int:
    """Downgrade accepted entries whose target is claimed by another source row."""
    claims: dict[tuple, list[dict]] = defaultdict(list)
    for entry in entries:
        if entry["status"] == "accepted":
            claims[(entry["dataset"], entry["target_name"])].append(entry)
    demoted = 0
    for (dataset, target_name), group in claims.items():
        own_names = {e["source_name"] for e in group}
        rival_names = [n for n in source_rows[dataset] if n == target_name and n not in own_names]
        if len(group) > 1 or rival_names:
            for entry in group:
                entry["status"] = "needs_review"
                entry["reason"] = "multiple_source_rows_same_target"
                entry["evidence"] = {**(entry["evidence"] or {}),
                                     "competing_accepted_rows": len(group) - 1,
                                     "other_row_with_target_name": bool(rival_names)}
                demoted += 1
    return demoted


def build(avilist, elton_rows, avonet, pins, sizes) -> dict:
    targets = _Targets(avilist)
    avonet_entries = _map_avonet(avonet["avonet1"], targets)
    elton_entries = _map_elton(elton_rows, avonet, targets)
    names = {
        "avonet": [clean(r["Species1"]) for r in avonet["avonet1"]],
        "eltontraits": [clean(r["Scientific"]) for r in elton_rows if clean(r["Scientific"])],
    }
    entries = avonet_entries + elton_entries
    demoted = _demote_conflicts(entries, names)

    status_by_dataset, reasons, methods, relations = Counter(), Counter(), Counter(), Counter()
    for entry in entries:
        status_by_dataset[f"{entry['dataset']}.{entry['status']}"] += 1
        if entry["reason"]:
            reasons[f"{entry['dataset']}.{entry['reason']}"] += 1
        if entry["status"] == "accepted":
            methods[f"{entry['dataset']}.{entry['method']}"] += 1
            relations[f"{entry['dataset']}.{entry['name_relation']}"] += 1
    accepted_targets = {d: {e["target_name"] for e in entries if e["dataset"] == d and e["status"] == "accepted"}
                        for d in ("avonet", "eltontraits")}

    columns = SCHEMA_DOC["entry_columns"]
    summary = {
        "avilist_species": targets.species_count,
        "avilist_duplicate_avibase_ids": targets.duplicate_id_count,
        "source_rows_without_name": {"eltontraits": sum(1 for r in elton_rows if not clean(r["Scientific"]))},
        "status": dict(sorted(status_by_dataset.items())),
        "accepted_by_name_relation": dict(sorted(relations.items())),
        "accepted_by_method": dict(sorted(methods.items())),
        "reasons": dict(sorted(reasons.items())),
        "conflict_demoted": demoted,
        "accepted_targets": {d: len(v) for d, v in sorted(accepted_targets.items())},
        "avilist_species_without_accepted_source": {d: targets.species_count - len(v) for d, v in sorted(accepted_targets.items())},
        "note": (
            "Accepted counts move with the rules: Taxo other than BL3 and competing source rows are excluded from "
            "'accepted' and appear under needs_review; 'name_changed' accepted entries are the additional recoveries over "
            "the old exact-name rule."
        ),
    }
    sources = []
    for point_id, role in ((AVILIST_ID, "taxonomy"), (ELTON_ID, "traits"), (AVONET_ID, "traits and crosswalk")):
        pin = pins[point_id]
        sources.append({
            "id": point_id, "role": role, "name": pin["name"], "provider": pin["provider"], "url": pin["url"],
            "release": pin["release"], "sha256": pin["sha256"], "bytes": sizes[point_id],
            "license_name": pin["license_name"], "license_uri": pin["license_uri"], "landing_uri": pin["landing_uri"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "description": "Mapping index from EltonTraits/AVONET rows to AviList v2025b species. Contains no trait values.",
        "taxonomy_release": "v2025b",
        "sources": sources,
        "structure": {
            "avilist_rows": EXPECTED["avilist_rows"], "avilist_species": EXPECTED["avilist_species"],
            "elton_rows": EXPECTED["elton_rows"], "elton_named_rows": EXPECTED["elton_named_rows"],
            "avonet_sheets": {"AVONET1_BirdLife": EXPECTED["avonet1_rows"], "AVONET3_BirdTree": EXPECTED["avonet3_rows"],
                              "BirdLife–BirdTree crosswalk": EXPECTED["crosswalk_rows"]},
            "avonet_birdlife_taxonomy": "HBW-BirdLife v5.0 (Dec 2020), per AVONET Metadata sheet",
            "avonet_birdtree_taxonomy": "Jetz et al. 2012 (BirdTree), per AVONET Metadata sheet",
        },
        "policy": POLICY,
        "schema": SCHEMA_DOC,
        "summary": summary,
        "entries": [[e[c] for c in columns] for e in entries],
    }


def render(document: dict) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def generate(paths: dict, root: Path = ROOT) -> dict:
    pins = load_pins(root)
    sizes = verify_hashes(paths, pins)
    return build(read_avilist(paths[AVILIST_ID]), read_elton(paths[ELTON_ID]), read_avonet(paths[AVONET_ID]), pins, sizes)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, help="directory holding the three pinned source files")
    parser.add_argument("--fetch", type=Path, metavar="DIR", help="download the pinned files into DIR (hash-checked), then use it")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="regenerate and fail if --output differs byte for byte")
    parser.add_argument("--verification-json", type=Path, help="also write a small verification summary (no source rows)")
    args = parser.parse_args(argv)
    raw_dir = args.fetch or args.raw_dir
    if raw_dir is None:
        parser.error("--raw-dir or --fetch is required")
    if args.fetch:
        fetch_all(args.fetch, load_pins())
    paths = {point_id: raw_dir / name for point_id, name in RAW_NAMES.items()}
    try:
        document = generate(paths)
    except (CrosswalkError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"trait crosswalk: {error}", file=sys.stderr)
        return 2
    payload = render(document)
    if args.verification_json:
        verification = {k: document[k] for k in ("schema_version", "taxonomy_release", "sources", "structure", "summary")}
        verification["output_sha256"] = hashlib.sha256(payload).hexdigest()
        verification["output_bytes"] = len(payload)
        args.verification_json.write_bytes(render(verification))
    if args.check:
        if not args.output.exists() or args.output.read_bytes() != payload:
            print(f"trait crosswalk: {args.output} is not byte-identical to a fresh build", file=sys.stderr)
            return 1
        print(f"OK {args.output} identical ({len(payload)} bytes, sha256 {hashlib.sha256(payload).hexdigest()})")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {args.output} ({len(payload)} bytes, sha256 {hashlib.sha256(payload).hexdigest()})")
    print(json.dumps(document["summary"], ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
