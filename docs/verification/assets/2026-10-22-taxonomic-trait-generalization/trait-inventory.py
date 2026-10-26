"""Read-only inventory of active trait fields, value shapes, and direct scope."""
import json
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.graph_questions import _CLAIM_GUARD
store=IngestionStore(PostgresSettings.from_environment());rows=[]
with Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment()) as repo:
 for pipeline in ('reference-avonet','reference-taxonomy-traits'):
  context=store.active_release_context(pipeline)
  if not context:continue
  cursor=context.cursor; concept=cursor.get('concept_set_id',cursor.get('taxonomy_concept_set_id')); release=cursor.get('taxonomy_release')
  q="""MATCH (c:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release,policy_status:'allowed'})<-[:IN_CONCEPT_SET]-(t:Taxon:BirdTaxon {source_release:$taxonomy_release,policy_status:'allowed'})<-[:ASSERTS_ABOUT]-(claim:TraitClaim {dataset_id:$dataset_id,source_release:$release,policy_status:'allowed'})-[:SUPPORTED_BY]->(ev:EvidenceUnit {policy_status:'allowed'}) WHERE """+_CLAIM_GUARD.format(alias='claim',ev='ev')+""" RETURN claim.trait_name AS trait_name,t.rank AS rank,count(DISTINCT t) AS taxa,collect(DISTINCT claim.value_text)[..30] AS text_values,head(collect(claim.value_json)) AS example_json,head(collect(claim.value_num)) AS example_number,collect(DISTINCT claim.unit)[..5] AS units ORDER BY trait_name,rank"""
  rs=repo._run(q,concept_set_id=concept,taxonomy_release=release,dataset_id=context.dataset.id,release=cursor.get('trait_release',context.release.release_key))
  rows.append({'pipeline':pipeline,'fields':rs})
print(json.dumps({'read_only':True,'pipelines':rows},ensure_ascii=False))
