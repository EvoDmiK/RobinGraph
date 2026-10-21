import os,json
from neo4j import GraphDatabase,READ_ACCESS,Query
assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')=='test'
assert os.environ['NEO4J_URI'].startswith('bolt://192.168.219.98:')
out={}
with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD'])) as d:
 with d.session(database=os.getenv('NEO4J_DATABASE','neo4j'),default_access_mode=READ_ACCESS) as s:
  for key,pattern in [('memory','java.lang:type=Memory'),('page_cache','org.neo4j:*')]:
   try:
    rows=s.run(Query('CALL dbms.queryJmx($pattern) YIELD name,attributes RETURN name,attributes',timeout=15),pattern=pattern).data()
    if key=='page_cache':rows=[r for r in rows if any(x in r['name'].lower() for x in ['page cache','pagecache','memory','store file'])]
    out[key]=rows
   except Exception as e:out[key]={'error_type':type(e).__name__,'code':getattr(e,'code',None)}
print(json.dumps(out,indent=2,default=str))
