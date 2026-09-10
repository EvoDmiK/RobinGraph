from copy import deepcopy
import json
import unittest

from scripts.deploy_n8n_reference_ingest import build_deployment, credential_by_name, WORKFLOWS


class ReferenceDeploymentTest(unittest.TestCase):
    def test_mistaken_token_in_credential_name_is_not_echoed_in_errors(self):
        token = "private-token-accidentally-used-as-name"
        with self.assertRaises(RuntimeError) as caught:
            credential_by_name([], token, "discordBotApi")
        self.assertNotIn(token, str(caught.exception))
        self.assertIn("saved credential name", str(caught.exception))

    def test_avonet_maps_neo4j_without_requiring_discord_or_mutating_import(self):
        source_path, id_key = WORKFLOWS["avonet"]
        source = json.loads(source_path.read_text(encoding="utf-8"))
        original = deepcopy(source)
        deployed = build_deployment(source, {"id": "graph", "name": "Test"}, None, "", "")
        self.assertEqual(original, source)
        self.assertNotEqual(WORKFLOWS["reference"][1], id_key)
        self.assertIn("AVONET", deployed["name"])
        self.assertNotIn("active", deployed)
        self.assertNotIn("concurrency", deployed["settings"])
        graph_nodes = [n for n in deployed["nodes"] if n["type"] == "n8n-nodes-neo4j.neo4j"]
        self.assertTrue(graph_nodes)
        self.assertTrue(all(n["credentials"]["neo4jApi"]["id"] == "graph" for n in graph_nodes))

    def test_reference_requires_notification_credentials_before_deployment(self):
        source = json.loads(WORKFLOWS["reference"][0].read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "Discord credential"):
            build_deployment(source, {"id": "graph", "name": "Test"}, None, "", "")


if __name__ == "__main__":
    unittest.main()
