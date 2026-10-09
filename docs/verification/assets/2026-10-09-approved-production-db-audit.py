import json,hashlib,collections,gc,datetime
from neo4j import GraphDatabase,READ_ACCESS
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
import psycopg
from psycopg import sql

def encode(value):
 def default(v):
  if hasattr(v,'iso_format'):return v.iso_format()
  if isinstance(v,(bytes,bytearray)):return v.hex()
  raise TypeError(type(v).__name__)
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=default).encode('utf-8')
def aggregate(groups):
 return {k:{'count':len(v),'sha256':hashlib.sha256(b''.join(sorted(v))).hexdigest()} for k,v in sorted(groups.items())}
p=PostgresSettings.from_environment();n=Neo4jSettings.from_environment()
out={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'postgres':{'database':p.database,'schema':p.schema},'neo4j':{'database':n.database},'method':'canonical properties plus labels and directed endpoint properties; sorted per-row SHA256 digests by node label set / relationship type; PG sorted row_to_json full rows'}
with psycopg.connect(**p.connection_kwargs()) as c:
 c.execute('SET TRANSACTION READ ONLY')
 out['postgres']['schemas']=[x[0] for x in c.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name <> 'information_schema' ORDER BY 1").fetchall()]
 tables=c.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type=%s ORDER BY table_name',(p.schema,'BASE TABLE')).fetchall()
 counts={};hashes={}
 for (t,) in tables:
  rows=c.execute(sql.SQL('SELECT row_to_json(t)::text FROM {}.{} t ORDER BY row_to_json(t)::text').format(sql.Identifier(p.schema),sql.Identifier(t))).fetchall()
  counts[t]=len(rows);hashes[t]=hashlib.sha256('\n'.join(r[0] for r in rows).encode()).hexdigest()
 out['postgres']['tables']=counts;out['postgres']['hashes']=hashes
 out['postgres']['running_ingestions']=c.execute(sql.SQL("SELECT count(*) FROM {}.ingestion_run WHERE status IN ('running','pending')").format(sql.Identifier(p.schema))).fetchone()[0]
 del rows;gc.collect()
with GraphDatabase.driver(n.uri,auth=(n.username,n.password)) as d:
 with d.session(database=n.database,default_access_mode=READ_ACCESS,fetch_size=300) as s:
  out['neo4j']['nodes']=s.run('MATCH (n) RETURN count(n) AS count').single()['count']
  out['neo4j']['relationships']=s.run('MATCH ()-[r]->() RETURN count(r) AS count').single()['count']
  out['neo4j']['labels']=s.run('MATCH (n) UNWIND labels(n) AS label RETURN label,count(*) AS count ORDER BY label').data()
  out['neo4j']['types']=s.run('MATCH ()-[r]->() RETURN type(r) AS type,count(*) AS count ORDER BY type').data()
  out['neo4j']['indexes']=s.run('SHOW INDEXES YIELD name,type,state,labelsOrTypes,properties RETURN name,type,state,labelsOrTypes,properties ORDER BY name').data()
  out['neo4j']['constraints']=s.run('SHOW CONSTRAINTS YIELD name,type,labelsOrTypes,properties RETURN name,type,labelsOrTypes,properties ORDER BY name').data()
  groups=collections.defaultdict(list)
  for r in s.run('MATCH (n) RETURN labels(n) AS labels,properties(n) AS properties'):
   labels=sorted(r['labels']);groups['|'.join(labels)].append(hashlib.sha256(encode([labels,r['properties']])).digest())
  out['neo4j']['node_content']=aggregate(groups);del groups;gc.collect()
  groups=collections.defaultdict(list)
  for r in s.run('MATCH (a)-[r]->(b) RETURN type(r) AS type,properties(r) AS properties,labels(a) AS al,properties(a) AS ap,labels(b) AS bl,properties(b) AS bp'):
   groups[r['type']].append(hashlib.sha256(encode([r['type'],r['properties'],[sorted(r['al']),r['ap']],[sorted(r['bl']),r['bp']]])).digest())
  out['neo4j']['relationship_content']=aggregate(groups)
print(json.dumps(out,ensure_ascii=False,indent=2))
