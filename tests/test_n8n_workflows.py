"""Static import and safety checks for the reviewed n8n workflow artifacts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "n8n" / "robingraph-operational-ingest.json"
WORKFLOWS = [
    ROOT / "n8n" / "candidates" / "claude-operational-ingest.json",
    ROOT / "n8n" / "candidates" / "terra-operational-ingest.json",
    FINAL,
]


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class N8nWorkflowArtifactTest(unittest.TestCase):
    def test_every_workflow_has_import_shape_and_valid_connections(self) -> None:
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                workflow = load(path)
                self.assertTrue(workflow["id"])
                self.assertIs(workflow["active"], False)
                self.assertEqual("v1", workflow["settings"]["executionOrder"])
                nodes = workflow["nodes"]
                names = [item["name"] for item in nodes]
                ids = [item["id"] for item in nodes]
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(len(ids), len(set(ids)))
                self.assertIn("Manual Trigger", names)
                self.assertTrue(any("Schedule Trigger" in name for name in names))

                known = set(names)
                for source, outputs in workflow["connections"].items():
                    self.assertIn(source, known)
                    for branch in outputs["main"]:
                        for target in branch:
                            self.assertIn(target["node"], known)

    def test_final_collects_gbif_directly_with_bounded_pagination(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        self.assertFalse(any(item["type"] == "n8n-nodes-base.ssh" for item in workflow["nodes"]))

        fetch = by_name["Fetch GBIF Korea Aves pages"]
        self.assertEqual("n8n-nodes-base.httpRequest", fetch["type"])
        self.assertTrue(fetch["parameters"]["url"].startswith("https://api.gbif.org/v1/occurrence/search?"))
        self.assertIn("license=CC0_1_0&license=CC_BY_4_0", fetch["parameters"]["url"])
        query = fetch["parameters"]["queryParameters"]["parameters"]
        query_names = [item["name"] for item in query]
        self.assertIn("country", query_names)
        self.assertIn("taxon_key", query_names)
        self.assertIn("event_date", query_names)
        self.assertIn("has_coordinate", query_names)
        self.assertNotIn("license", query_names)

        pagination = fetch["parameters"]["options"]["pagination"]["pagination"]
        self.assertEqual("updateAParameterInEachRequest", pagination["paginationMode"])
        self.assertTrue(pagination["limitPagesFetched"])
        self.assertGreater(pagination["maxRequests"], 0)
        self.assertGreaterEqual(pagination["requestInterval"], 200)
        self.assertIn("endOfRecords", pagination["completeExpression"])
        self.assertIn("$pageCount", pagination["parameters"]["parameters"][0]["value"])

        raw_hash = by_name["Hash each raw GBIF page"]
        self.assertEqual("n8n-nodes-base.crypto", raw_hash["type"])
        self.assertEqual("SHA256", raw_hash["parameters"]["type"])
        self.assertEqual("raw_sha256", raw_hash["parameters"]["dataPropertyName"])

    def test_final_uses_community_neo4j_load_and_fail_closed_paths(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        load_node = by_name["Atomic upsert to Neo4j"]
        self.assertEqual("n8n-nodes-neo4j.neo4j", load_node["type"])
        self.assertEqual("graphDb", load_node["parameters"]["resource"])
        self.assertEqual("executeQuery", load_node["parameters"]["operation"])
        body = load_node["parameters"]["cypherQuery"]
        self.assertIn("UNWIND $bird_taxa AS row", body)
        self.assertIn("SET taxon:BirdTaxon", body)
        self.assertIn("HAS_ACCEPTED_NAME", body)
        self.assertIn("PARENT_OF", body)
        self.assertIn("UNWIND $observations AS row", body)
        self.assertIn("MERGE (state:IngestState", body)

        verify_node = by_name["Verify Neo4j response counts"]
        self.assertIn("result['state.active_release']", verify_node["parameters"]["jsCode"])

        self.assertEqual(
            "Notify failure",
            connections["Quality gates passed?"]["main"][1][0]["node"],
        )
        self.assertEqual(
            "Advance n8n cursor",
            connections["Atomic load verified?"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Notify failure",
            connections["Atomic load verified?"]["main"][1][0]["node"],
        )
        self.assertEqual("Fail execution", connections["Notify failure"]["main"][0][0]["node"])
        self.assertEqual("n8n-nodes-base.stopAndError", by_name["Fail execution"]["type"])

    def test_final_keeps_secrets_out_and_uses_native_processing_nodes(self) -> None:
        workflow = load(FINAL)
        self.assertEqual(1, workflow["settings"]["concurrency"])
        self.assertTrue(any(item["type"] == "n8n-nodes-base.code" for item in workflow["nodes"]))
        notifications = [
            item for item in workflow["nodes"] if item["name"].startswith("Notify ")
        ]
        self.assertEqual(2, len(notifications))
        self.assertTrue(
            all(item["type"] == "n8n-nodes-base.discord" for item in notifications)
        )
        self.assertTrue(
            all(item["parameters"]["authentication"] == "webhook" for item in notifications)
        )
        self.assertFalse(any(item["type"] == "n8n-nodes-base.emailSend" for item in workflow["nodes"]))
        neo4j_node = next(
            item for item in workflow["nodes"]
            if item["type"] == "n8n-nodes-neo4j.neo4j"
        )
        self.assertEqual(["neo4jApi"], list(neo4j_node["credentials"]))
        serialized = json.dumps(workflow).lower()
        self.assertNotIn("-----begin private key-----", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("robingraph ingest ", serialized)

    def test_community_query_escaping_and_verification(self) -> None:
        from scripts.generate_n8n_operational_ingest import ASSESS_NEO4J, CYPHER_LITERAL_JS

        script = CYPHER_LITERAL_JS + r"""
const assert = require('node:assert/strict');
assert.equal(literal("O'Brien\\$run_id\n"), "'O\\'Brien\\\\$run_id\\u000a'");
assert.equal(literal({rows: [null, true, 12]}), '{rows:[null,true,12]}');
assert.throws(() => literal(Infinity));
assert.throws(() => literal({'bad`key': 1}));
const expected = {taxon_count: 2, taxon_link_count: 1, observation_count: 19,
  media_count: 11, quarantine_count: 0, source_release: 'release'};
const good = {loaded_taxa: 2, loaded_taxon_links: 1, loaded_observations: 19,
  loaded_media: 11, loaded_quarantine: 0, 'state.active_release': 'release'};
""" + "const verify = new Function('$', '$input', " + json.dumps(ASSESS_NEO4J) + ");" + r"""
const check = value => verify(() => ({first: () => ({json: expected})}),
  {first: () => ({json: value})})[0].json.load_ok;
assert.equal(check(good), true);
assert.equal(check({...good, loaded_observations: 18}), false);
assert.equal(check({...good, 'state.active_release': 'old'}), false);
assert.equal(check({error: 'connection failed'}), false);
assert.equal(check({}), false);
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

    def test_nas_api_deployment_maps_existing_credentials(self) -> None:
        from scripts.deploy_n8n_operational_ingest import build_deployment

        payload = build_deployment(
            load(FINAL),
            {"id": "neo4j-id", "name": "Neo4j"},
            {"id": "discord-id", "name": "Nesty API 키"},
            "guild-id",
            "channel-id",
        )
        by_name = {item["name"]: item for item in payload["nodes"]}
        load_node = by_name["Atomic upsert to Neo4j"]
        self.assertEqual("n8n-nodes-neo4j.neo4j", load_node["type"])
        self.assertEqual("neo4j-id", load_node["credentials"]["neo4jApi"]["id"])
        self.assertNotIn("concurrency", payload["settings"])
        for name in ("Notify success", "Notify failure"):
            self.assertEqual("channel-id", by_name[name]["parameters"]["channelId"]["value"])
            self.assertEqual("discord-id", by_name[name]["credentials"]["discordBotApi"]["id"])

    @unittest.skipUnless(
        os.environ.get("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1",
        "Opt in to run the n8n Cypher contract against Neo4j",
    )
    def test_native_neo4j_statement_executes_atomically(self) -> None:
        from neo4j import GraphDatabase
        from scripts.generate_n8n_operational_ingest import NEO4J_STATEMENT

        run_id = "n8n-native-workflow-integration-test"
        observation_id = f"gbif-observation:{run_id}"
        parameters = {
            "run_id": run_id,
            "pipeline_id": f"gbif-occurrence-kr-aves:{run_id}",
            "retrieved_at": "2026-09-07T00:00:00Z",
            "source_release": "gbif-live-integration-test",
            "source_count": 1,
            "taxon_count": 2,
            "taxon_link_count": 1,
            "quarantine_count": 0,
            "event_date_end": "2026-09-07",
            "bird_taxa": [
                {
                    "id": f"gbif-taxon:family-{run_id}",
                    "external_key": f"family-{run_id}",
                    "provider": "GBIF Backbone",
                    "rank": "family",
                    "scientific_name": "Corvidae",
                    "canonical_name": "Corvidae",
                    "authorship": None,
                    "taxonomic_status": "accepted",
                    "vernacular_name_raw": None,
                    "source_uri": f"https://example.invalid/species/family-{run_id}",
                    "retrieved_at": "2026-09-07T00:00:00Z",
                },
                {
                    "id": f"gbif-taxon:{run_id}",
                    "external_key": run_id,
                    "provider": "GBIF Backbone",
                    "rank": "species",
                    "scientific_name": "Pica serica",
                    "canonical_name": "Pica serica",
                    "authorship": "Gould, 1845",
                    "taxonomic_status": "accepted",
                    "vernacular_name_raw": "Oriental Magpie",
                    "source_uri": f"https://example.invalid/species/{run_id}",
                    "retrieved_at": "2026-09-07T00:00:00Z",
                },
            ],
            "taxon_links": [
                {
                    "id": f"family-{run_id}->species-{run_id}",
                    "parent_id": f"gbif-taxon:family-{run_id}",
                    "child_id": f"gbif-taxon:{run_id}",
                }
            ],
            "observations": [
                {
                    "id": observation_id,
                    "external_id": run_id,
                    "occurrence_id": run_id,
                    "event_id": None,
                    "external_taxon_id": f"gbif-taxon:{run_id}",
                    "external_taxon_key": run_id,
                    "scientific_name": "Pica serica",
                    "scientific_name_raw": "Pica serica",
                    "taxon_rank": "species",
                    "observed_at": "2026-09-01T12:00:00Z",
                    "event_date_precision": "instant",
                    "count": 1,
                    "basis": "human_observation",
                    "lat": 37.5,
                    "lon": 127.0,
                    "coordinate_uncertainty_m": 10,
                    "geodetic_datum": "WGS84",
                    "sensitivity": "public",
                    "place_id": f"gbif-place:{run_id}",
                    "place_name": "integration test place",
                    "dataset_id": f"gbif-dataset:{run_id}",
                    "dataset_key": run_id,
                    "publisher_key": None,
                    "license_uri": f"https://example.invalid/license/{run_id}",
                    "source_record_key": f"gbif:integration:{run_id}",
                    "source_release": "gbif-live-integration-test",
                    "raw_uri": f"https://example.invalid/occurrence/{run_id}",
                    "raw_sha256": "0" * 64,
                    "source_updated_at": None,
                    "retrieved_at": "2026-09-07T00:00:00Z",
                    "issues": [],
                }
            ],
            "media": [],
            "quarantine": [],
        }
        driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
        try:
            with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
                result = session.run(NEO4J_STATEMENT, **parameters).single(strict=True)
                self.assertEqual(2, result["loaded_taxa"])
                self.assertEqual(1, result["loaded_taxon_links"])
                self.assertEqual(1, result["loaded_observations"])
                self.assertEqual(0, result["loaded_media"])
                self.assertEqual(0, result["loaded_quarantine"])
                self.assertEqual(parameters["source_release"], result["state.active_release"])
                session.run(
                    "MATCH (node) WHERE node.id CONTAINS $marker DETACH DELETE node",
                    marker=run_id,
                ).consume()
        finally:
            driver.close()


if __name__ == "__main__":
    unittest.main()
