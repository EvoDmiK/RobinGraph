"""Static import and safety checks for the reviewed n8n workflow artifacts."""

from __future__ import annotations

import json
import os
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

    def test_final_uses_parameterized_atomic_neo4j_load_and_fail_closed_paths(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        load_node = by_name["Atomic upsert to Neo4j Query API"]
        self.assertEqual("n8n-nodes-base.httpRequest", load_node["type"])
        self.assertEqual("POST", load_node["parameters"]["method"])
        self.assertEqual("genericCredentialType", load_node["parameters"]["authentication"])
        self.assertEqual("httpBasicAuth", load_node["parameters"]["genericAuthType"])
        body = load_node["parameters"]["jsonBody"]
        self.assertIn("UNWIND $observations AS row", body)
        self.assertIn("parameters: $json", body)
        self.assertIn("MERGE (state:IngestState", body)

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
        self.assertFalse(any("credentials" in item for item in workflow["nodes"]))
        serialized = json.dumps(workflow).lower()
        self.assertNotIn("-----begin private key-----", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("robingraph ingest ", serialized)

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
            "quarantine_count": 0,
            "event_date_end": "2026-09-07",
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
