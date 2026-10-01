"""Apply explicit source-backed reviews to quarantined names in the active snapshot.

Dry run by default. Does not change taxonomy, ingest activation, or source records.
The original candidate and immutable fetch evidence are retained for audit.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from neo4j import GraphDatabase
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore

RESOLVE = """
MATCH (set:TaxonConceptSet {id:$concept_set_id, policy_status:'allowed'})
MATCH (taxon:Taxon:BirdTaxon {scientific_name:$scientific_name, rank:'species'})-[:IN_CONCEPT_SET]->(set)
MATCH (candidate:VernacularNameCandidate {dataset_id:$dataset_id, taxon_name:$scientific_name, proposed_name:$korean_name})
WHERE $qid IN candidate.qids AND candidate.reason_code='ambiguous_korean_name_across_taxa'
WITH collect(DISTINCT taxon) AS taxa, collect(DISTINCT candidate) AS candidates
WHERE size(taxa)=1 AND size(candidates)>0
WITH taxa[0] AS taxon, candidates[0] AS candidate
OPTIONAL MATCH (other:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept_set_id}),
(other)-[:HAS_VERNACULAR_NAME]->(existing:VernacularName {language:'ko', name:$korean_name, dataset_id:$dataset_id, policy_status:'allowed'})
WITH taxon, candidate, collect(DISTINCT other.id) AS existingTargets
WHERE all(id IN existingTargets WHERE id=taxon.id)
RETURN taxon.id AS taxon_id, candidate.id AS candidate_id, candidate.source_record_ids AS source_record_ids
"""
APPLY = """
MATCH (t:Taxon:BirdTaxon {id:$taxon_id})-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept_set_id})
MATCH (c:VernacularNameCandidate {id:$candidate_id, dataset_id:$dataset_id})
MERGE (n:VernacularName {id:$taxon_id + ':vernacular:ko:reviewed:' + $dataset_id})
ON CREATE SET n.name=$korean_name, n.language='ko', n.status='community-sourced-reviewed',
 n.dataset_id=$dataset_id, n.policy_status='allowed', n.source_release=$source_release,
 n.source_qids=[$qid], n.source_record_ids=$source_record_ids,
 n.source_scientific_name_claim=$scientific_name, n.review_evidence_url=$evidence_url,
 n.reviewed_at=$reviewed_at, n.review_reason=$reason, n.review_candidate_id=$candidate_id
MERGE (t)-[:HAS_VERNACULAR_NAME]->(n)
SET c.resolution_status='accepted-after-review', c.review_evidence_url=$evidence_url,
 c.reviewed_at=$reviewed_at, c.resolved_taxon_id=$taxon_id
RETURN n.id AS name_id
"""

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviews',type=Path,default=Path(__file__).resolve().parents[1]/'config/korean-name-reviews.json')
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    review=json.loads(args.reviews.read_text(encoding='utf-8'))
    store=IngestionStore(PostgresSettings.from_environment())
    korean=store.active_release_context('korean-vernacular-names')
    taxonomy=store.active_release_context('reference-taxonomy-traits')
    if korean is None or taxonomy is None:
        raise RuntimeError('Active allowed taxonomy and Korean snapshot are required')
    s=Neo4jSettings.from_environment()
    with GraphDatabase.driver(s.uri,auth=(s.username,s.password)) as d, d.session(database=s.database) as session:
        for row in review['accepted']:
            params={**row, 'dataset_id':korean.dataset.id,'concept_set_id':taxonomy.cursor['concept_set_id'],
                    'source_release':korean.release.release_key,'evidence_url':review['evidence_url'],
                    'reviewed_at':review['reviewed_at'],'reason':review['reason']}
            matches=session.run(RESOLVE,params).data()
            if len(matches)!=1:
                raise RuntimeError('Review requires one exact quarantined source and an unambiguous active species')
            params.update(matches[0])
            if args.apply:
                if store.active_release_context('korean-vernacular-names') != korean or store.active_release_context('reference-taxonomy-traits') != taxonomy:
                    raise RuntimeError('Active context changed; retry against current snapshot')
                result=session.execute_write(lambda tx: tx.run(APPLY,params).data())
                if len(result)!=1:
                    raise RuntimeError('Review write did not resolve exactly one name')
            print(json.dumps({'apply':args.apply,'scientific_name':row['scientific_name'],'korean_name':row['korean_name'],'taxon_id':params['taxon_id'],'candidate_id':params['candidate_id']},ensure_ascii=False))

if __name__=='__main__':
    main()
