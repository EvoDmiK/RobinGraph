import hashlib,json,os
import psycopg
from neo4j import GraphDatabase
from robingraph.ingest.postgres import PostgresSettings
from robingraph.graph.settings import Neo4jSettings
assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')=='test'
p=PostgresSettings.from_environment(); n=Neo4jSettings.from_environment()
assert (p.host,p.port,p.database,p.username)==('192.168.219.99',5433,'robingraph_test','robingraph_test_app')
assert (n.uri,n.database)==('bolt://192.168.219.98:7687','neo4j')
with psycopg.connect(**p.connection_kwargs()) as c:
 assert c.execute('select current_database(),current_user').fetchone()==('robingraph_test','robingraph_test_app')
 old=c.execute("select pipeline_id,active_release_id,last_successful_run_id,cursor,version from ingest.ingest_state where pipeline_id <> 'avilist-distribution-pilot' order by pipeline_id").fetchall()
 pilot=c.execute("select r.status,count(distinct sr.id) from ingest.ingestion_run r left join ingest.source_record sr on sr.source_release_id=r.source_release_id where r.pipeline_id='avilist-distribution-pilot' group by r.id,r.status order by r.id").fetchall()
with GraphDatabase.driver(n.uri,auth=(n.username,n.password)) as driver:
 with driver.session(database=n.database) as s:
  vectors=s.run('match(n:TaxonNameVectorCatalog) return n.fingerprint as fingerprint').data()
  counts=s.run('match(n:TaxonNameVector) return count(n) as vectors').single().data()
print(json.dumps({'other_pipeline_states_sha256':hashlib.sha256(json.dumps(old,sort_keys=True,default=str).encode()).hexdigest(),'pilot_runs':pilot,'name_catalog':vectors,'name_vector_count':counts['vectors']},sort_keys=True))
