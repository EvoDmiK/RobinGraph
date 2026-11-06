"""Dry-run by default. Explicit TEST-only import of the pinned, bounded Commons audio catalog."""
import argparse
import json
import os

from neo4j import GraphDatabase
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.recordings import SOURCE_ID, SOURCE_RELEASE, UPSERT_RECORDINGS, graph_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-test', action='store_true')
    parser.add_argument('--expect-uri')
    parser.add_argument('--expect-database')
    parser.add_argument('--expect-concept-set')
    parser.add_argument('--expect-taxonomy-release')
    parser.add_argument('--expect-recordings', type=int)
    args = parser.parse_args()
    rows = graph_rows()
    if not args.apply_test:
        print(json.dumps({'action': 'dry-run', 'recordings': len(rows),
                          'scientific_names': [row['scientific_name'] for row in rows], 'writes': 0}))
        return
    expected = (args.expect_uri, args.expect_database, args.expect_concept_set, args.expect_taxonomy_release)
    if os.environ.get('ROBINGRAPH_DEPLOY_TARGET') != 'test' or not all(expected):
        parser.error('TEST target and all four explicit expected context flags are required')
    if args.expect_recordings != len(rows):
        parser.error('Explicit expected recording count differs from the pinned catalog')
    settings = Neo4jSettings.from_environment()
    if (settings.uri, settings.database) != expected[:2]:
        parser.error('Neo4j target differs from the confirmed TEST target')
    context = IngestionStore(PostgresSettings.from_environment()).active_release_context('reference-taxonomy-traits')
    cursor = context.cursor if context is not None else {}
    if (cursor.get('concept_set_id', cursor.get('taxonomy_concept_set_id')), cursor.get('taxonomy_release')) != expected[2:]:
        parser.error('PostgreSQL active taxonomy differs from the confirmed TEST context')
    def apply(tx):
        matches = tx.run("""
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
UNWIND $names AS name
OPTIONAL MATCH (taxon:Taxon:BirdTaxon {rank:'species', scientific_name:name,
  source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
RETURN name, count(taxon) AS matches
""", concept_set_id=args.expect_concept_set, taxonomy_release=args.expect_taxonomy_release,
            names=[row['scientific_name'] for row in rows]).data()
        if len(matches) != len(rows) or any(row['matches'] != 1 for row in matches):
            raise ValueError('Every reviewed exact-species target must be unique and present; no writes applied')
        result = tx.run(UPSERT_RECORDINGS, rows=rows, dataset_id=SOURCE_ID, source_release=SOURCE_RELEASE,
                        concept_set_id=args.expect_concept_set, taxonomy_release=args.expect_taxonomy_release).single()
        if result is None or result['recordings'] != len(rows):
            raise ValueError('Unexpected recording import count; transaction rolled back')
        return result['recordings']
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            count = session.execute_write(apply)
    print(json.dumps({'action': 'test-upsert', 'recordings': count, 'target': 'test',
                      'source_id': SOURCE_ID, 'source_release': SOURCE_RELEASE}))


if __name__ == '__main__':
    main()
