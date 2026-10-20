import os,json
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository
from robingraph.retrieval.species_scope import scope_matches
from robingraph.embeddings import JinaEmbeddingClient
assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')=='test'
s=Neo4jSettings.from_environment();assert s.uri=='bolt://192.168.219.98:7687'
store=IngestionStore(PostgresSettings.from_environment())
def context():
 a=store.active_release_context('reference-taxonomy-traits');return (a.cursor['concept_set_id'],a.cursor['taxonomy_release'])
with Neo4jTaxonomyLineageRepository(s,lambda:store.active_dataset_id('korean-vernacular-names'),context) as taxonomy, Neo4jTaxonNameVectorRepository(s) as vectors:
 inventory=taxonomy.reviewed_name_candidates();client=JinaEmbeddingClient.from_env();report=vectors.index_names(inventory,client,context(),dry_run=True)
 report['outside']=[x for x in inventory if scope_matches(x,'outside',*context())]
 print(json.dumps(report,ensure_ascii=False,indent=2))
