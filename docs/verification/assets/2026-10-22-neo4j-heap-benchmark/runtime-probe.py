import os,json,datetime
from neo4j import GraphDatabase,Query
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test' and os.environ['NEO4J_URI']=='bolt://192.168.219.98:7687'
out={'target':'test','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD'])) as d:
 with d.session(database=os.getenv('NEO4J_DATABASE','neo4j'),default_access_mode='READ') as s:
  for label,pattern in [('memory','java.lang:type=Memory'),('gc','java.lang:type=GarbageCollector,name=*'),('runtime','java.lang:type=Runtime')]:
   try:
    rows=s.run(Query('CALL dbms.queryJmx($pattern) YIELD name,attributes RETURN name,attributes',timeout=10),pattern=pattern).data()
    allowed={'HeapMemoryUsage','NonHeapMemoryUsage','CollectionCount','CollectionTime','Uptime','StartTime'}
    out[label]=[{'name':r['name'],'attributes':{k:v['value'] for k,v in r['attributes'].items() if k in allowed}} for r in rows]
   except Exception as e:out[label]={'unavailable':type(e).__name__}
  out['counts']={}
  for label in ['Taxon','TraitClaim','Chunk','TaxonNameVector']:
   out['counts'][label]=s.run(Query('MATCH(n:'+label+') RETURN count(n) AS n',timeout=10)).single()['n']
  out['settings']=s.run(Query("SHOW SETTINGS YIELD name,value WHERE name IN ['server.memory.heap.initial_size','server.memory.heap.max_size','server.memory.pagecache.size'] RETURN name,value",timeout=10)).data()
print(json.dumps(out,indent=2,default=str))
