"""Reviewed name usages are separate from accepted taxa and their traits.

PostgreSQL owns the reviewed manifest, license policy and active release.
Neo4j owns the name-usage -> active AviList taxon edges. Neither path changes
canonical VernacularName nodes or treats a domestic form as its wild relative.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import cache
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

PIPELINE = "reviewed-name-relations"
KINDS = {"common_name", "domestic_form"}
TYPES = {
    "common_usage": "통칭이 가리킬 수 있는 종",
    "domesticated_from": "가축화와 관련된 야생종",
}

RELATIONS_QUERY = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MATCH (usage:BirdNameUsage {dataset_id:$dataset_id, source_release:$source_release, policy_status:'allowed'})
      -[claim:NAME_RELATION {dataset_id:$dataset_id, source_release:$source_release, concept_set_id:$concept_set_id}]->
      (target:Taxon:BirdTaxon {rank:'species'})-[:IN_CONCEPT_SET]->(concept)
WHERE toLower($name) IN usage.search_terms OR toLower(target.scientific_name)=toLower($name)
RETURN usage.id AS usage_id, claim.source_record_id AS source_record_id,
       claim.relation_type AS relation_type, target.id AS taxon_id,
       target.scientific_name AS scientific_name
ORDER BY usage.id, target.scientific_name, target.id
LIMIT 25
"""


def manifest_digest(manifest):
    return sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def load_manifest(path=None):
    path = path or Path(__file__).with_name("name_relations.json")
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


@cache
def reviewed_search_terms():
    return frozenset(t.lower() for r in load_manifest()["records"] for t in r["search_terms"])


def validate_manifest(manifest):
    if manifest.get("policy_status") != "allowed" or not manifest.get("reviewed_at"):
        raise ValueError("A reviewed allowed manifest is required")
    records = manifest.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= 24:
        raise ValueError("One to 24 reviewed relations are required")
    ids = set()
    entities = {}
    for record in records:
        if record.get("id") in ids or not record.get("id"):
            raise ValueError("Relation identifiers must be unique")
        ids.add(record["id"])
        if record.get("entity_kind") not in KINDS or record.get("relation_type") not in TYPES:
            raise ValueError("Unknown reviewed relation type")
        expected_type = "domesticated_from" if record["entity_kind"] == "domestic_form" else "common_usage"
        if record["relation_type"] != expected_type:
            raise ValueError("Name usage kind and relation type disagree")
        if not all(isinstance(record.get(k), str) and record[k].strip()
                   for k in ("entity_id", "name", "scientific_name", "note")):
            raise ValueError("Missing relation fields")
        terms = record.get("search_terms")
        if not isinstance(terms, list) or not terms or len(terms) > 12 or any(
            not isinstance(t, str) or not t.strip() or t != t.strip() or len(t) > 200 for t in terms
        ):
            raise ValueError("Invalid search terms")
        entity = (record["name"], record["entity_kind"], sorted(t.lower() for t in terms))
        if record["entity_id"] in entities and entities[record["entity_id"]] != entity:
            raise ValueError("One name usage cannot have conflicting definitions")
        entities[record["entity_id"]] = entity
        sources = record.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("A relation needs source citations")
        for source in sources:
            url = urlsplit(source.get("url", ""))
            if url.scheme != "https" or not url.hostname or url.username or not source.get("title"):
                raise ValueError("Invalid citation")


class NameRelationRepository:
    def __init__(self, lineage_repository, active_context):
        self.repository = lineage_repository
        self.active_context = active_context

    def for_name(self, name):
        name = name.strip()
        if not name or len(name) > 200:
            raise ValueError("A bounded name is required")
        context = self.active_context()
        if context is None:
            return None
        manifest = (context.release.metadata or {}).get("manifest", {})
        validate_manifest(manifest)
        if context.release.content_sha256 != manifest_digest(manifest):
            raise ValueError("Reviewed relation snapshot does not match its hash")
        concept_id, taxonomy_release = self.repository._active_concept_set()
        if (context.cursor.get("concept_set_id"), context.cursor.get("taxonomy_release")) != (concept_id, taxonomy_release):
            return None
        rows = self.repository._run(
            RELATIONS_QUERY, name=name, concept_set_id=concept_id,
            taxonomy_release=taxonomy_release, dataset_id=context.dataset.id,
            source_release=context.release.id,
        )
        records = {f"{context.release.id}:{r['id']}": r for r in manifest["records"]}
        relations = []
        seen = set()
        for row in rows:
            record = records.get(row.get("source_record_id"))
            if record is None or row.get("scientific_name") != record["scientific_name"] or row.get("relation_type") != record["relation_type"]:
                raise ValueError("Graph relation does not match reviewed evidence")
            if record["id"] in seen:
                raise ValueError("A reviewed relation maps to multiple active targets")
            seen.add(record["id"])
            lineage = self.repository.lineage_for_scientific_name(record["scientific_name"])
            if not lineage or lineage.concept_set_id != concept_id or lineage.taxonomy_release != taxonomy_release or lineage.items[-1].taxon_id != row["taxon_id"]:
                raise ValueError("Active taxonomy changed during relation lookup")
            relations.append({
                "name": record["name"], "entity_kind": record["entity_kind"],
                "relation_type": record["relation_type"],
                "relation_label": TYPES[record["relation_type"]],
                "note": record["note"], "taxon": asdict(lineage.items[-1]),
                "sources": record["sources"],
            })
        expected = {r["id"] for r in manifest["records"] if name.lower() in
                    [t.lower() for t in r["search_terms"]] or name.lower() == r["scientific_name"].lower()}
        # Never silently narrow a common name because an edge is missing.
        if expected != seen:
            raise ValueError("Incomplete reviewed graph relationships")
        is_search_term = any(name.lower() in [t.lower() for t in r["search_terms"]]
                             for r in manifest["records"])
        if not relations:
            summary = "이 종에 대해 검토·등록된 통칭 또는 가축형 관계가 없습니다."
        elif any(r["entity_kind"] == "domestic_form" for r in relations):
            summary = "가축형과 관련 야생종을 구분해 확인해 주세요. 선택 후 표시되는 야생종 자료는 가축형의 사진·체중·생태를 뜻하지 않습니다."
        else:
            summary = "이 이름은 사용 맥락에 따라 여러 대상을 가리킬 수 있습니다. 조회할 종을 선택해 주세요."
        return {"query_name": name, "summary": summary, "is_search_term": is_search_term,
                "taxonomy_source": "AviList", "taxonomy_release": taxonomy_release,
                "concept_set_id": concept_id, "relations": relations}
