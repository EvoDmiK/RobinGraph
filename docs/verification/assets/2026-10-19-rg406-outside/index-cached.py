import os,json
from types import SimpleNamespace
from neo4j import GraphDatabase,READ_ACCESS
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
s=Neo4jSettings.from_environment();assert s.uri=='bolt://192.168.219.98:7687'
class Cached:
 def embed_documents(self,texts):return tuple(payload['vectors'][text] for text in texts)
client=Cached();client.profile=SimpleNamespace(**payload['profile'])
with GraphDatabase.driver(s.uri,auth=(s.username,s.password)) as driver:
 with driver.session(database=s.database,default_access_mode=READ_ACCESS) as session:
  current=session.run('MATCH(c:TaxonNameVectorCatalog) RETURN c.fingerprint AS fingerprint').single()['fingerprint']
  assert current==expected_fingerprint,'Catalog changed since reviewed backup'
with Neo4jTaxonNameVectorRepository(s) as vectors:
 print(json.dumps(vectors.index_names(payload['inventory'],client,tuple(payload['context']),dry_run=False),indent=2))
