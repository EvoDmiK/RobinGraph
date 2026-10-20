import os,json
from neo4j import GraphDatabase,READ_ACCESS,Query
assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')=='test'
assert os.environ['NEO4J_URI'].startswith('bolt://192.168.219.98:')
d=GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD']))
queries={
 'counts':'MATCH (n) UNWIND labels(n) AS label WITH label,count(*) AS count WHERE label IN ["Chunk","Document","HybridSearchChunk","HybridVectorChunk","SpeciesNameEmbedding","Taxon","SourceDataset"] RETURN label,count',
 'chunks':'MATCH (c:Chunk) RETURN count(c) AS count,sum(size(coalesce(c.text,""))) AS text_characters,sum(CASE WHEN c.hybrid_vector IS NOT NULL THEN size(c.hybrid_vector) ELSE 0 END) AS vector_components,collect(DISTINCT c.hybrid_dimensions) AS dimensions',
 'documents':'MATCH (d:Document) RETURN labels(d) AS labels,count(*) AS count',
 'indices':'SHOW INDEXES YIELD name,type,state,populationPercent,labelsOrTypes,properties,options WHERE type IN ["FULLTEXT","VECTOR"] RETURN name,type,state,populationPercent,labelsOrTypes,properties,options',
 'metrics_available':"SHOW PROCEDURES YIELD name WHERE name CONTAINS 'dbms.queryJmx' OR name CONTAINS 'db.stats' RETURN name",
}
out={'target':'test','neo4j_host':'192.168.219.98','read_only':True,'queries':{}}
with d.session(database=os.getenv('NEO4J_DATABASE','neo4j'),default_access_mode=READ_ACCESS) as s:
 for k,q in queries.items():
  try:out['queries'][k]=s.run(Query(q,timeout=20)).data()
  except Exception as e:out['queries'][k]={'error_type':type(e).__name__,'code':getattr(e,'code',None)}
d.close();print(json.dumps(out,indent=2))
