"""Opt-in real Cypher ordering tests, confined to disposable UUID namespaces.

No active taxonomy state, production IDs, indexes, or constraints are changed.
The reference map is synthetic test input; the query and its LIMIT are real.
"""
from __future__ import annotations

import os
import unittest
from uuid import uuid4

from neo4j import GraphDatabase

from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.related_species import RELATED_QUERY


@unittest.skipUnless(
    os.getenv("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1",
    "Set ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 for isolated real Neo4j ordering tests",
)
class RelatedSpeciesIntegrationTest(unittest.TestCase):
    def test_verified_names_sort_before_limit_and_preserve_taxonomy_boundaries(self):
        settings = Neo4jSettings.from_environment()
        namespace = "related-names-test-" + uuid4().hex
        concept, other_concept = namespace + ":concept", namespace + ":other-concept"
        release, dataset = "test-v1", namespace + ":dataset"
        family, genus, other_genus = (namespace + ":" + key for key in ("family", "genus", "other-genus"))
        target = namespace + ":target"
        ordinary = [
            {"id": namespace + f":ordinary-{i:02d}", "scientific": f"Test ordinary{i}",
             "english": f"A candidate {i:02d}", "raw_korean": f"가짜국명{i:02d}"}
            for i in range(14)
        ]
        verified = {"id": namespace + ":verified", "scientific": "Test verified", "english": "Zulu verified"}
        bad_science = {"id": namespace + ":bad-science", "scientific": "Test wrongscience", "english": "Zulu science mismatch"}
        bad_english = {"id": namespace + ":bad-english", "scientific": "Test wrongenglish", "english": "Zulu English mismatch"}
        peers = ordinary + [verified, bad_science, bad_english]
        references = {
            verified["id"]: {"name": "검증국명", "scientific_name": verified["scientific"], "english_name": verified["english"]},
            bad_science["id"]: {"name": "틀린학명국명", "scientific_name": "Test another", "english_name": bad_science["english"]},
            bad_english["id"]: {"name": "틀린영문국명", "scientific_name": bad_english["scientific"], "english_name": "Different English name"},
        }
        driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))
        try:
            with driver.session(database=settings.database) as session:
                session.run("""
                    UNWIND $concepts AS id
                    CREATE (:TaxonConceptSet {id:id, version:$release, policy_status:'allowed',
                        snapshot_uri:'https://example.org/test-taxonomy', title:'Isolated test taxonomy', test_namespace:$ns})
                    """, concepts=[concept, other_concept], release=release, ns=namespace).consume()
                session.run("""
                    MATCH (c:TaxonConceptSet {id:$concept})
                    UNWIND $parents AS p
                    CREATE (:Taxon:BirdTaxon {id:p.id, rank:p.rank, scientific_name:p.name,
                        dataset_id:$dataset, source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(c)
                    """, concept=concept, parents=[
                        {"id": family, "rank": "family", "name": "TestFamily"},
                        {"id": genus, "rank": "genus", "name": "TestGenus"},
                        {"id": other_genus, "rank": "genus", "name": "OtherGenus"},
                    ], dataset=dataset, release=release, ns=namespace).consume()
                session.run("""
                    MATCH (f:Taxon {id:$family}), (g:Taxon {id:$genus}), (other:Taxon {id:$other_genus})
                    CREATE (f)-[:PARENT_OF {concept_set_id:$concept}]->(g)
                    CREATE (f)-[:PARENT_OF {concept_set_id:$concept}]->(other)
                    """, family=family, genus=genus, other_genus=other_genus, concept=concept).consume()
                session.run("""
                    MATCH (c:TaxonConceptSet {id:$concept}), (g:Taxon {id:$genus})
                    UNWIND $peers AS p
                    CREATE (t:Taxon:BirdTaxon {id:p.id, rank:'species', scientific_name:p.scientific,
                        dataset_id:$dataset, source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(c)
                    CREATE (g)-[:PARENT_OF {concept_set_id:$concept}]->(t)
                    CREATE (t)-[:HAS_VERNACULAR_NAME]->(:VernacularName {id:p.id+':en', name:p.english,
                        language:'en', status:'source-preferred', policy_status:'allowed', dataset_id:$dataset,
                        source_release:$release, test_namespace:$ns})
                    FOREACH (ignored IN CASE WHEN p.raw_korean IS NOT NULL THEN [1] ELSE [] END |
                        CREATE (t)-[:HAS_VERNACULAR_NAME]->(:VernacularName {id:p.id+':ko', name:p.raw_korean,
                            language:'ko', status:'machine-translated', policy_status:'allowed', dataset_id:$ko_dataset,
                            source_release:$release, test_namespace:$ns}))
                    """, concept=concept, genus=genus, peers=peers + [
                        {"id": target, "scientific": "Test target", "english": "A target"}],
                    dataset=dataset, ko_dataset=namespace + ":ko", release=release, ns=namespace).consume()
                # Each invalid peer would sort ahead of the valid candidates if
                # concept membership or relationship scoping were accidentally lost.
                session.run("""
                    MATCH (active:TaxonConceptSet {id:$concept}), (foreign:TaxonConceptSet {id:$other_concept}),
                          (g:Taxon {id:$genus}), (other:Taxon {id:$other_genus})
                    CREATE (outside:Taxon:BirdTaxon {id:$ns+':foreign', rank:'species', scientific_name:'AAA foreign',
                        dataset_id:$dataset, source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(foreign)
                    CREATE (g)-[:PARENT_OF {concept_set_id:$concept}]->(outside)
                    CREATE (wrong:Taxon:BirdTaxon {id:$ns+':wrong-edge', rank:'species', scientific_name:'AAA wrongedge',
                        dataset_id:$dataset, source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(active)
                    CREATE (g)-[:PARENT_OF {concept_set_id:$other_concept}]->(wrong)
                    CREATE (cousin:Taxon:BirdTaxon {id:$ns+':cousin', rank:'species', scientific_name:'Other cousin',
                        dataset_id:$dataset, source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(active)
                    CREATE (other)-[:PARENT_OF {concept_set_id:$concept}]->(cousin)
                    """, concept=concept, other_concept=other_concept, genus=genus, other_genus=other_genus,
                    dataset=dataset, release=release, ns=namespace).consume()

                parameters = {"concept_set_id": concept, "taxonomy_release": release,
                              "parent_id": genus, "rank": "genus", "target_id": target,
                              "excluded_genus": None, "korean_dataset_id": namespace + ":ko",
                              "korean_reference_names": references}
                rows = session.run(RELATED_QUERY, **parameters).data()
                self.assertEqual(13, len(rows), "The actual query must keep its bounded 12+1 window")
                self.assertEqual(verified["id"], rows[0]["taxon"]["taxon_id"])
                self.assertEqual("검증국명", rows[0]["taxon"]["korean_name"])
                self.assertEqual([p["id"] for p in ordinary[:12]], [r["taxon"]["taxon_id"] for r in rows[1:]])
                self.assertTrue(all(r["taxon"].get("korean_name") is None for r in rows[1:]))
                self.assertNotIn(target, {r["taxon"]["taxon_id"] for r in rows})

                # A separate parent exposes both mismatches without the
                # ordinary peers consuming the query's bounded result window.
                mismatch_genus = namespace + ":mismatch-genus"
                session.run("""
                    MATCH (c:TaxonConceptSet {id:$concept})
                    CREATE (g:Taxon:BirdTaxon {id:$id, rank:'genus', scientific_name:'MismatchGenus',
                        source_release:$release, policy_status:'allowed', test_namespace:$ns})-[:IN_CONCEPT_SET]->(c)
                    WITH g UNWIND $ids AS id MATCH (p:Taxon {id:id})
                    CREATE (g)-[:PARENT_OF {concept_set_id:$concept}]->(p)
                    """, concept=concept, id=mismatch_genus, release=release, ns=namespace,
                    ids=[bad_science["id"], bad_english["id"]]).consume()
                mismatches = session.run(RELATED_QUERY, **{**parameters, "parent_id": mismatch_genus}).data()
                self.assertEqual(2, len(mismatches))
                self.assertTrue(all(r["taxon"].get("korean_name") is None for r in mismatches))
                self.assertEqual({bad_science["english"], bad_english["english"]},
                                 {r["taxon"]["english_name"] for r in mismatches})

                cousins = session.run(RELATED_QUERY, **{**parameters, "parent_id": family,
                                      "rank": "family", "excluded_genus": genus}).data()
                self.assertEqual([namespace + ":cousin"], [r["taxon"]["taxon_id"] for r in cousins])
        finally:
            try:
                with driver.session(database=settings.database) as session:
                    session.run("MATCH (n {test_namespace:$ns}) DETACH DELETE n", ns=namespace).consume()
            finally:
                driver.close()
