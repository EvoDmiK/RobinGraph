"""Read-only active numeric claim multiplicity check for interval semantics."""
import json
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.graph_questions import TRAIT_CONDITIONS
s=IngestionStore(PostgresSettings.from_environment());c=s.active_release_context('reference-avonet');assert c
fields=[n for n,v in TRAIT_CONDITIONS.items() if v[1]=='number']
with Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment()) as r:
 rows=r._run("""MATCH (ctx:TaxonConceptSet {id:$concept,version:$taxonomy_release,policy_status:'allowed'})<-[:IN_CONCEPT_SET]-(t:Taxon:BirdTaxon {source_release:$taxonomy_release,policy_status:'allowed'})<-[:ASSERTS_ABOUT]-(c:TraitClaim {dataset_id:$dataset,source_release:$release,policy_status:'allowed',inferred:false}) WHERE c.trait_name IN $fields WITH t.id AS taxon_id,c.trait_name AS trait_name,count(DISTINCT c) AS claims RETURN count(*) AS taxon_trait_pairs,max(claims) AS maximum_claims_per_pair,sum(CASE WHEN claims>1 THEN 1 ELSE 0 END) AS multiple_claim_pairs""",concept=c.cursor.get('concept_set_id',c.cursor.get('taxonomy_concept_set_id')),taxonomy_release=c.cursor['taxonomy_release'],dataset=c.dataset.id,release=c.cursor.get('trait_release',c.release.release_key),fields=fields)
print(json.dumps({'scope':'Actual active TEST numeric claim multiplicity, read only','result':rows}))
