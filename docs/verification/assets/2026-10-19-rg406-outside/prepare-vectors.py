import os,json,hashlib
from neo4j import GraphDatabase,READ_ACCESS
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.taxon_name_vectors_neo4j import _text_hash
from robingraph.retrieval.species_scope import scope_matches
from robingraph.embeddings import JinaEmbeddingClient
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
s=Neo4jSettings.from_environment();assert s.uri=='bolt://192.168.219.98:7687'
store=IngestionStore(PostgresSettings.from_environment())
def context():
 a=store.active_release_context('reference-taxonomy-traits');return (a.cursor['concept_set_id'],a.cursor['taxonomy_release'])
with Neo4jTaxonomyLineageRepository(s,lambda:store.active_dataset_id('korean-vernacular-names'),context) as taxonomy:
 inventory=taxonomy.reviewed_name_candidates()
 with GraphDatabase.driver(s.uri,auth=(s.username,s.password)) as driver:
  with driver.session(database=s.database,default_access_mode=READ_ACCESS) as session:
   existing={r['taxon_id']:r['text_hash'] for r in session.run('MATCH(n:TaxonNameVector) RETURN n.taxon_id AS taxon_id,n.text_hash AS text_hash').data()}
 missing=[row for row in inventory if existing.get(row['taxon_id'])!=_text_hash(row['text'])]
 assert len(missing)==6 and len(inventory)==855
 client=JinaEmbeddingClient.from_env();vectors=client.embed_documents([r['text'] for r in missing])
 print(json.dumps({'inventory':inventory,'context':context(),'profile':vars(client.profile),'vectors':dict(zip([r['text'] for r in missing],vectors))},ensure_ascii=False))
