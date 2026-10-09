import json,collections
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository,_parse_lineage_items
from robingraph.retrieval.taxonomy_lineage import sourced_korean_names
r=Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment())
rows=r._run("""MATCH (t:Taxon:BirdTaxon {rank:'species',source_release:'v2025b',policy_status:'allowed'})-[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:'rg:concept-set:avilist-v2025b'})
OPTIONAL MATCH (t)-[:HAS_VERNACULAR_NAME]->(en:VernacularName {language:'en',policy_status:'allowed',status:'source-preferred'}) WHERE en.dataset_id=t.dataset_id AND en.source_release=t.source_release
WITH t,collect(DISTINCT en.name) AS names
OPTIONAL MATCH (t)-[:HAS_VERNACULAR_NAME]->(ko:VernacularName {language:'ko',policy_status:'allowed'})
RETURN t.id AS taxon_id,t.rank AS rank,t.scientific_name AS scientific_name,names AS english_names,collect(DISTINCT ko{.name,.status,.dataset_id,.source_release}) AS graph_korean""")
labels=sourced_korean_names();out=[]
for x in rows:
 x['english_name']=min(x['english_names']) if x['english_names'] else None
 item=_parse_lineage_items([x])[0]
 x['rendered_korean']=item.korean_name;x['expected_korean']=labels.get(x['taxon_id'],{}).get('name')
 x['known_korean_suppressed']=bool(x['expected_korean'] and not item.korean_name)
 out.append(x)
print(json.dumps({'species_count':len(out),'rows':out,'known_korean_suppressed':[x for x in out if x['known_korean_suppressed']],'duplicate_english':{k:v for k,v in collections.Counter(n for x in rows for n in x['english_names']).items() if v>1}},ensure_ascii=False))
r.close()
