"""Prepare the dedicated TEST taxon-name vector index; read-only by default.

Run with the TEST service environment. --apply is the only schema/data write
path; chat requests never build this index or embed the name catalog.
"""
from __future__ import annotations

import argparse
import json
import os

from robingraph.embeddings import JinaEmbeddingClient
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if os.getenv('ROBINGRAPH_DEPLOY_TARGET') != 'test':
        raise SystemExit('Requires ROBINGRAPH_DEPLOY_TARGET=test; no DB connection was opened.')
    from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository

    store = IngestionStore(PostgresSettings.from_environment())

    def context():
        active = store.active_release_context('reference-taxonomy-traits')
        if active is None:
            raise RuntimeError('An active reviewed taxonomy is required')
        values = (active.cursor.get('concept_set_id'), active.cursor.get('taxonomy_release'))
        if not all(isinstance(value, str) and value for value in values):
            raise RuntimeError('The active taxonomy context is incomplete')
        return values

    settings = Neo4jSettings.from_environment()
    taxonomy = Neo4jTaxonomyLineageRepository(
        settings, lambda: store.active_dataset_id('korean-vernacular-names'), context)
    vectors = Neo4jTaxonNameVectorRepository(settings)
    try:
        before = context()
        inventory = taxonomy.reviewed_name_candidates()
        if context() != before or not inventory:
            raise RuntimeError('The reviewed catalog is unavailable or changed')
        client = JinaEmbeddingClient.from_env()
        report = vectors.index_names(inventory, client, before, dry_run=not args.apply)
        if context() != before:
            raise RuntimeError('Taxonomy changed during indexing; re-run for the active context')
    finally:
        vectors.close()
        taxonomy.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
