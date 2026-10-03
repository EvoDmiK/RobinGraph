"""Load reviewed name usages without merging wild and domestic taxa.

Dry-run by default; --apply journals immutable records in PostgreSQL, creates
one versioned Neo4j projection, then activates it with optimistic concurrency.
Failed or partially written projections stay invisible. Safe to rerun.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from neo4j import GraphDatabase
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import (
    IngestionStore, IngestionRunInput, SourceDatasetInput, SourceReleaseInput, SourceRecordInput,
)
from robingraph.retrieval.name_relations import PIPELINE, load_manifest, manifest_digest

RESOLVE_QUERY = """
UNWIND $names AS name
MATCH (taxon:Taxon:BirdTaxon {scientific_name:name, rank:'species'})
      -[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
RETURN name, collect(DISTINCT taxon.id) AS ids
"""

PROJECT_QUERY = """
UNWIND $rows AS row
MATCH (target:Taxon:BirdTaxon {id:row.taxon_id, scientific_name:row.scientific_name, rank:'species'})
      -[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MERGE (usage:BirdNameUsage {id:row.usage_id})
ON CREATE SET usage.name=row.name, usage.entity_kind=row.entity_kind,
              usage.search_terms=row.search_terms, usage.dataset_id=$dataset_id,
              usage.source_release=$source_release, usage.policy_status='allowed'
MERGE (usage)-[claim:NAME_RELATION {source_record_id:row.source_record_id}]->(target)
ON CREATE SET claim.relation_type=row.relation_type, claim.dataset_id=$dataset_id,
              claim.source_release=$source_release, claim.concept_set_id=$concept_set_id
RETURN count(claim) AS projected
"""


def prepare_projection(manifest, resolved, release_id, concept_id):
    rows = []
    for record in manifest["records"]:
        ids = resolved.get(record["scientific_name"], [])
        if len(ids) != 1:
            raise ValueError(f"Requires one active taxon for {record['scientific_name']}")
        rows.append({**record, "taxon_id": ids[0],
                     "source_record_id": f"{release_id}:{record['id']}",
                     "usage_id": f"{release_id}:{concept_id}:{record['entity_id']}",
                     "search_terms": [t.lower() for t in record["search_terms"]]})
    return rows


def project(tx, rows, **parameters):
    result = tx.run(PROJECT_QUERY, rows=rows, **parameters).single()
    if result is None or result["projected"] != len(rows):
        raise ValueError("Taxonomy changed; projection transaction rolled back")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    digest = manifest_digest(manifest)
    store = IngestionStore(PostgresSettings.from_environment())
    taxonomy = store.active_release_context("reference-taxonomy-traits")
    if taxonomy is None:
        raise RuntimeError("An allowed active AviList snapshot is required")
    concept_id = taxonomy.cursor["concept_set_id"]
    taxonomy_release = taxonomy.cursor["taxonomy_release"]
    dataset_id = f"rg:name-relations:{digest}"
    release_id = f"{dataset_id}:{concept_id}:{taxonomy_release}"
    active = store.active_release_context(PIPELINE)
    expected_version = store.pipeline_state_version(PIPELINE)
    settings = Neo4jSettings.from_environment()
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            names = sorted({record["scientific_name"] for record in manifest["records"]})
            resolved = {r["name"]: r["ids"] for r in session.run(
                RESOLVE_QUERY, names=names, concept_set_id=concept_id, taxonomy_release=taxonomy_release
            ).data()}
            rows = prepare_projection(manifest, resolved, release_id, concept_id)
            print(json.dumps({"apply": args.apply, "relations": len(rows), "taxa": len(names),
                              "concept_set_id": concept_id, "manifest_sha256": digest}))
            if not args.apply:
                return
            if active and active.release.id == release_id and active.release.content_sha256 == digest:
                print("Already active; no writes")
                return
            now = datetime.now(timezone.utc)
            run_id = f"rg:name-relations-run:{uuid4()}"
            source_uri = f"urn:sha256:{digest}"
            dataset = SourceDatasetInput(dataset_id, "robingraph-reviewed-name-relations", "Reviewed bird name relationships",
                                         "RobinGraph", "https://github.com/EvoDmiK/RobinGraph", "versioned", "allowed",
                                         {"content_type": "reviewed factual relationships", "policy": "Original summaries; source citations retained"})
            release = SourceReleaseInput(release_id, dataset_id, release_id, now, digest, source_uri,
                                         {"manifest": manifest, "concept_set_id": concept_id})
            run = IngestionRunInput(run_id, PIPELINE, release_id, now, config_sha256=digest)
            store.begin_run(dataset, release, run)
            try:
                records = [SourceRecordInput(
                    row["source_record_id"], release_id, record["id"], "reviewed-name-relation", f"urn:sha256:{manifest_digest(record)}",
                    manifest_digest(record), now, "name-relations-v1", run_id, "allowed", record,
                ) for row, record in zip(rows, manifest["records"])]
                store.append_batch(run_id, records=records)
                if store.active_release_context("reference-taxonomy-traits") != taxonomy:
                    raise RuntimeError("Active taxonomy changed before projection")
                session.execute_write(project, rows, concept_set_id=concept_id, taxonomy_release=taxonomy_release,
                                      dataset_id=dataset_id, source_release=release_id)
                if store.active_release_context("reference-taxonomy-traits") != taxonomy:
                    raise RuntimeError("Active taxonomy changed before activation")
                store.activate_release(run_id, counts={"records": len(records), "relationships": len(rows)},
                                       cursor_value={"concept_set_id": concept_id, "taxonomy_release": taxonomy_release},
                                       expected_state_version=expected_version)
            except Exception:
                store.fail_run(run_id, "Reviewed relation projection or activation failed")
                raise
            print("Reviewed name relationships activated")


if __name__ == "__main__":
    main()
