"""Opt-in real PostgreSQL/Neo4j test, isolated from NAS and its datasets."""
from __future__ import annotations
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from neo4j import GraphDatabase
from robingraph.api.app import create_app
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings, apply_migrations
from robingraph.ingest.store import IngestionStore, SourceDatasetInput, SourceReleaseInput, IngestionRunInput
from robingraph.retrieval.name_relations import NameRelationRepository, PIPELINE, load_manifest
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository


@unittest.skipUnless(os.getenv("ROBINGRAPH_NAME_RELATIONS_INTEGRATION_TESTS") == "1", "Dedicated graph/control-plane databases required")
class NameRelationsIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg = PostgresSettings.from_environment()
        if "test" not in pg.database or "test" not in pg.schema:
            raise RuntimeError("Dedicated test database and schema names are required")
        apply_migrations(pg)
        cls.store = IngestionStore(pg)
        cls.settings = Neo4jSettings.from_environment()
        cls.namespace = "rg004-test-" + uuid4().hex
        cls.concept = cls.namespace + ":concept"
        cls.release = "test-v1"
        cls.manifest = load_manifest()
        names = sorted({r["scientific_name"] for r in cls.manifest["records"]})
        cls.driver = GraphDatabase.driver(cls.settings.uri, auth=(cls.settings.username, cls.settings.password))
        with cls.driver.session(database=cls.settings.database) as s:
            s.run("CREATE (:TaxonConceptSet {id:$id,version:$release,policy_status:'allowed',test_namespace:$ns})",
                  id=cls.concept, release=cls.release, ns=cls.namespace).consume()
            s.run("""UNWIND $names AS name
                MATCH (c:TaxonConceptSet {id:$concept})
                CREATE (t:Taxon:BirdTaxon {id:$ns+':'+name,scientific_name:name,rank:'species',test_namespace:$ns})-[:IN_CONCEPT_SET]->(c)
                """, names=names, concept=cls.concept, ns=cls.namespace).consume()
        now = datetime.now(timezone.utc)
        ds = SourceDatasetInput(cls.namespace, "rg004-test", "Test taxonomy", "test", "https://example.org/test", "versioned", "allowed", {})
        rel = SourceReleaseInput(cls.namespace+":release", ds.id, cls.release, now)
        run = IngestionRunInput(cls.namespace+":run", "reference-taxonomy-traits", rel.id, now)
        cls.store.begin_run(ds, rel, run)
        cls.store.activate_release(run.id, counts={}, cursor_value={"concept_set_id": cls.concept, "taxonomy_release": cls.release},
                                   expected_state_version=cls.store.pipeline_state_version("reference-taxonomy-traits"))
        cls.repo = Neo4jTaxonomyLineageRepository(cls.settings, active_taxonomy_context=lambda: (cls.concept, cls.release))
        cls.reader = NameRelationRepository(cls.repo, lambda: cls.store.active_release_context(PIPELINE))
        cls.loader = [sys.executable, str(Path(__file__).resolve().parents[1]/"scripts/load_name_relations.py")]

    @classmethod
    def tearDownClass(cls):
        context = cls.store.active_release_context(PIPELINE)
        with cls.driver.session(database=cls.settings.database) as s:
            if context:
                s.run("MATCH (n:BirdNameUsage {source_release:$id}) DETACH DELETE n", id=context.release.id).consume()
            s.run("MATCH (n {test_namespace:$ns}) DETACH DELETE n", ns=cls.namespace).consume()
        cls.repo.close()
        cls.driver.close()

    def test_real_loader_dry_run_activation_idempotence_reverse_search_and_chat(self):
        before = self.store.pipeline_state_version(PIPELINE)
        dry = subprocess.run(self.loader, text=True, capture_output=True, check=True)
        self.assertIn('"apply": false', dry.stdout)
        self.assertEqual(before, self.store.pipeline_state_version(PIPELINE))
        applied = subprocess.run(self.loader+["--apply"], text=True, capture_output=True, check=True)
        self.assertIn("activated", applied.stdout)
        version = self.store.pipeline_state_version(PIPELINE)
        repeated = subprocess.run(self.loader+["--apply"], text=True, capture_output=True, check=True)
        self.assertIn("Already active", repeated.stdout)
        self.assertEqual(version, self.store.pipeline_state_version(PIPELINE))
        client = TestClient(create_app(name_relations_handler=self.reader.for_name))
        for term in ("비둘기", "까마귀", "닭", "집오리"):
            result = self.reader.for_name(term)
            self.assertTrue(result["is_search_term"])
            self.assertGreater(len(result["relations"]), 0)
            answer = client.post("/v1/chat", json={"question": term+"에 대해 알려줘"}).json()
            self.assertEqual("name_relations", answer["result"]["kind"])
            self.assertEqual("clarify", answer["disposition"])
        self.assertFalse(self.reader.for_name("Gallus gallus")["is_search_term"])
        self.assertGreater(len(self.reader.for_name("Gallus gallus")["relations"]), 0)
        # Losing one candidate edge must fail the whole ambiguous lookup.
        with self.driver.session(database=self.settings.database) as s:
            s.run("MATCH (:BirdNameUsage)-[r:NAME_RELATION {concept_set_id:$id}]->(:Taxon {scientific_name:'Corvus corone'}) DELETE r", id=self.concept).consume()
        with self.assertRaises(ValueError): self.reader.for_name("까마귀")
        self.assertEqual(503, client.get("/v1/taxa/name-relations", params={"name":"까마귀"}).status_code)
        # The same reviewed manifest must support a later taxonomy release.
        new_version = "test-v2"
        with self.driver.session(database=self.settings.database) as s:
            s.run("MATCH (c:TaxonConceptSet {id:$id}) SET c.version=$version",
                  id=self.concept, version=new_version).consume()
        now = datetime.now(timezone.utc)
        dataset = SourceDatasetInput(self.namespace, "rg004-test", "Test taxonomy", "test", "https://example.org/test", "versioned", "allowed", {})
        release = SourceReleaseInput(self.namespace+":release-v2", dataset.id, new_version, now)
        run = IngestionRunInput(self.namespace+":run-v2", "reference-taxonomy-traits", release.id, now)
        self.store.begin_run(dataset, release, run)
        self.store.activate_release(run.id, counts={}, cursor_value={"concept_set_id":self.concept,"taxonomy_release":new_version},
                                   expected_state_version=self.store.pipeline_state_version("reference-taxonomy-traits"))
        next_release = subprocess.run(self.loader+["--apply"], text=True, capture_output=True, check=True)
        self.assertIn("activated", next_release.stdout)
        self.assertEqual(new_version, self.store.active_release_context(PIPELINE).cursor["taxonomy_release"])


if __name__ == "__main__":
    unittest.main()
