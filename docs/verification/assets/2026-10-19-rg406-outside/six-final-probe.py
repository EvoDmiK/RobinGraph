import os,json
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository
from robingraph.retrieval.taxon_name_resolution import TaxonNameResolver
from robingraph.retrieval.species_scope import scope_query_parameters
from robingraph.embeddings import JinaEmbeddingClient
assert os.getenv('ROBINGRAPH_DEPLOY_TARGET')=='test'
s=Neo4jSettings.from_environment();assert s.uri=='bolt://192.168.219.98:7687'
store=IngestionStore(PostgresSettings.from_environment())
def context():
 a=store.active_release_context('reference-taxonomy-traits');return (a.cursor['concept_set_id'],a.cursor['taxonomy_release'])
with Neo4jTaxonomyLineageRepository(s,lambda:store.active_dataset_id('korean-vernacular-names'),context) as taxonomy, Neo4jTaxonNameVectorRepository(s) as vectors:
 client=JinaEmbeddingClient.from_env()
 def exact(name):
  return taxonomy.lineage_for_scientific_name(name) or taxonomy.lineage_for_english_name(name) or taxonomy.lineage_for_korean_name(name)
 resolver=TaxonNameResolver(exact,taxonomy.reviewed_name_candidates,client,context,vectors.search)
 output={'inventory':len(taxonomy.reviewed_name_candidates()),'cases':[]}
 for taxon_id,science in scope_query_parameters('outside',*context())['scope_selected'].items():
  english=taxonomy.lineage_for_scientific_name(science).items[-1].english_name
  for scope in ('all','outside'):
   for kind,q in [('scientific_exact',science),('english_exact',english),('scientific_typo',science[:-1]+'x'),('english_typo',english+'a' if english=='Kea' else english[:-1]+'x')]:
    result=resolver.resolve(q,scope);ids=[r['taxon_id'] for r in result['candidates']]
    output['cases'].append({'scope':scope,'kind':kind,'query':q,'expected_id':taxon_id,'expected_english':english,'status':result['status'],'matched_id':result['taxon_id'],'candidate_ids':ids,'candidate_names':[r['display_name'] for r in result['candidates']],'scores':[r['score'] for r in result['candidates']],'target_found':result['taxon_id']==taxon_id or taxon_id in ids})
 print(json.dumps(output,ensure_ascii=False,indent=2))
