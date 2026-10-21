import os,json,math
from neo4j import GraphDatabase,READ_ACCESS
from robingraph.embeddings import JinaEmbeddingClient
from robingraph.retrieval.species_scope import scope_matches
import robingraph.retrieval.taxon_name_vectors_neo4j as module
Neo4jTaxonNameVectorRepository=module.Neo4jTaxonNameVectorRepository
from robingraph.graph.settings import Neo4jSettings
assert os.environ.get('ROBINGRAPH_DEPLOY_TARGET')=='test'
s=Neo4jSettings.from_environment();assert s.uri=='bolt://192.168.219.98:7687'
with GraphDatabase.driver(s.uri,auth=(s.username,s.password)) as d:
 with d.session(database=s.database,default_access_mode=READ_ACCESS) as session:
  catalog=session.run('MATCH(c:TaxonNameVectorCatalog) RETURN c.concept_set_id AS concept_set_id,c.taxonomy_release AS release').single()
  nodes=session.run('MATCH(n:TaxonNameVector) RETURN n.taxon_id AS taxon_id,n.scientific_name AS scientific_name,n.display_name AS display_name,n.text AS text,n.name_vector AS vector').data()
context=(catalog['concept_set_id'],catalog['release']);inventory=[{k:n[k] for k in ['taxon_id','scientific_name','display_name','text']} for n in nodes]
embedder=JinaEmbeddingClient.from_env();report={'inventory':len(nodes),'cases':[],'scope_counts':{scope:sum(scope_matches(n,scope,*context) for n in nodes) for scope in ['korea','outside','unknown']}}
with Neo4jTaxonNameVectorRepository(s) as repo:
 for q in ['케아','높은산앵무아','키위아','타조아','천둥오리','청둥오리아','갈매기아','검둥오리아']:
  v=embedder.embed_query(q);hits=repo.search(v,embedder.profile,context,inventory,limit=10)
  ranked=sorted([(sum(a*b for a,b in zip(v,n['vector']))/(math.hypot(*v)*math.hypot(*n['vector'])),n) for n in nodes],key=lambda p:-p[0])
  for scope in ['korea','outside','unknown']:
   eligible=[(i+1,score,n) for i,(score,n) in enumerate(ranked) if scope_matches(n,scope,*context) and score>=.25]
   in_top=[n for n in hits if scope_matches(n,scope,*context) and n['score']>=.25]
   ids=[n['taxon_id'] for n in nodes if scope_matches(n,scope,*context)]
   import time
   started=time.perf_counter()
   scoped=repo.search(v,embedder.profile,context,inventory,limit=10,eligible_taxon_ids=ids)
   elapsed=(time.perf_counter()-started)*1000
   expected=[n['taxon_id'] for _,score,n in eligible[:10]]
   actual=[n['taxon_id'] for n in scoped if n['score']>=.25]
   assert expected==actual, (q,scope,expected,actual)
   report['cases'].append({'query':q,'scope':scope,'scoped_search_ms':round(elapsed,3),'exact_oracle_matches':True,'scoped_count':len(scoped),'global_top10_eligible_count':len(in_top),'exact_scoped_eligible_count':len(eligible),'best_scoped_global_rank':eligible[0][0] if eligible else None,'best_scoped_name':eligible[0][2]['display_name'] if eligible else None,'best_scoped_cosine':round(eligible[0][1],6) if eligible else None})
with Neo4jTaxonNameVectorRepository(s) as repo:
 qv=embedder.embed_query('높은산앵무아')
 top=repo.search(qv,embedder.profile,context,inventory,limit=2)
 assert len(top)==2
 selected=top[1]['taxon_id']
 old=repo.search(qv,embedder.profile,context,inventory,limit=1)
 new=repo.search(qv,embedder.profile,context,inventory,limit=1,eligible_taxon_ids=[selected])
 assert selected not in [r['taxon_id'] for r in old] and [r['taxon_id'] for r in new]==[selected]
 report['live_cutoff_reproduction']={'limit':1,'global_rank':2,'before_found':False,'after_found':True,'scope':'controlled allowed-ID subset over real stored vectors; not geographic source evidence'}
print(json.dumps(report,ensure_ascii=False,indent=2))
