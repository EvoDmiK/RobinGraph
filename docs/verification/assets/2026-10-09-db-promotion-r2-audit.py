import json,hashlib
from neo4j import GraphDatabase,READ_ACCESS
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
import psycopg
from psycopg import sql
p=PostgresSettings.from_environment();n=Neo4jSettings.from_environment()
out={'postgres':{'database':p.database,'schema':p.schema},'neo4j':{'database':n.database}}
with psycopg.connect(**p.connection_kwargs()) as c:
 c.execute('SET TRANSACTION READ ONLY')
 schemas=c.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name <> 'information_schema' ORDER BY 1").fetchall();out['postgres']['schemas']=[x[0] for x in schemas]
 tables=c.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type=%s ORDER BY table_name',(p.schema,'BASE TABLE')).fetchall()
 counts={};hashes={}
 for (t,) in tables:
  rows=c.execute(sql.SQL('SELECT row_to_json(t)::text FROM {}.{} t ORDER BY row_to_json(t)::text').format(sql.Identifier(p.schema),sql.Identifier(t))).fetchall()
  counts[t]=len(rows);hashes[t]=hashlib.sha256('\n'.join(r[0] for r in rows).encode()).hexdigest()
 out['postgres']['tables']=counts;out['postgres']['hashes']=hashes
with GraphDatabase.driver(n.uri,auth=(n.username,n.password)) as d:
 with d.session(database=n.database,default_access_mode=READ_ACCESS) as s:
  out['neo4j']['nodes']=s.run('MATCH (n) RETURN count(n) AS count').single()['count']
  out['neo4j']['relationships']=s.run('MATCH ()-[r]->() RETURN count(r) AS count').single()['count']
  out['neo4j']['labels']=s.run('MATCH (n) UNWIND labels(n) AS label RETURN label,count(*) AS count ORDER BY label').data()
  out['neo4j']['types']=s.run('MATCH ()-[r]->() RETURN type(r) AS type,count(*) AS count ORDER BY type').data()
  out['neo4j']['indexes']=s.run('SHOW INDEXES YIELD name,type,state,labelsOrTypes,properties RETURN name,type,state,labelsOrTypes,properties ORDER BY name').data()
  out['neo4j']['constraints']=s.run('SHOW CONSTRAINTS YIELD name,type,labelsOrTypes,properties RETURN name,type,labelsOrTypes,properties ORDER BY name').data()
print(json.dumps(out,ensure_ascii=False,indent=2))
