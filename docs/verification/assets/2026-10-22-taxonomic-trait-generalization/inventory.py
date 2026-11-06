"""Actual TEST taxonomy inventory. Read-only Neo4j/Postgres; no credentials emitted."""
import json
from collections import Counter
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from robingraph.retrieval.taxonomy_lineage import reference_korean_names,sourced_korean_names
store=IngestionStore(PostgresSettings.from_environment())
c=store.active_release_context('reference-taxonomy-traits');assert c
concept=c.cursor['concept_set_id'];release=c.cursor['taxonomy_release']
with Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment()) as repo:
 taxa=repo._run("MATCH (c:TaxonConceptSet {id:$concept,version:$release,policy_status:'allowed'})<-[:IN_CONCEPT_SET]-(t:Taxon:BirdTaxon {source_release:$release,policy_status:'allowed'}) RETURN t.id AS id,t.rank AS rank,t.scientific_name AS scientific_name",concept=concept,release=release)
 links=repo._run("MATCH (c:TaxonConceptSet {id:$concept,version:$release,policy_status:'allowed'})<-[:IN_CONCEPT_SET]-(p:Taxon:BirdTaxon {source_release:$release,policy_status:'allowed'})-[r:PARENT_OF {concept_set_id:$concept}]->(t:Taxon:BirdTaxon {source_release:$release,policy_status:'allowed'})-[:IN_CONCEPT_SET]->(c) RETURN p.id AS parent,t.id AS child",concept=concept,release=release)
 refs=reference_korean_names(); names=sourced_korean_names()
 for t in taxa:
  label=refs.get(t['rank']+':'+t['scientific_name'].casefold(),{}).get('name')
  species=names.get(t['id'],{})
  if species.get('scientific_name')==t['scientific_name']:label=species['name']
  t['korean_name']=label
print(json.dumps({'scope':'Actual TEST active taxonomy catalog; no DB writes','concept_set_id':concept,'taxonomy_release':release,'rank_counts':dict(Counter(t['rank'] for t in taxa)),'taxa':taxa,'parent_edges':links},ensure_ascii=False))
