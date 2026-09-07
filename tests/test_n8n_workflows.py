"""Static import and safety checks for the reviewed n8n workflow artifacts."""

from __future__ import annotations

import json
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

    def test_final_checks_every_mutating_ssh_exit_code(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        checked_ssh = [
            item
            for item in workflow["nodes"]
            if item["type"] == "n8n-nodes-base.ssh"
            and "following IF node" in item.get("notes", "")
        ]
        self.assertGreaterEqual(len(checked_ssh), 14)

        for item in checked_ssh:
            with self.subTest(node=item["name"]):
                command = item["parameters"]["command"]
                self.assertTrue(command.startswith("="))
                self.assertIn("n8n-{{ $execution.id }}", command)
                outputs = connections[item["name"]]["main"]
                self.assertEqual(1, len(outputs))
                self.assertEqual(1, len(outputs[0]))
                check_name = outputs[0][0]["node"]
                check = by_name[check_name]
                self.assertEqual("n8n-nodes-base.if", check["type"])
                condition = check["parameters"]["conditions"]["conditions"][0]
                self.assertEqual("={{ Number($json.code ?? -1) }}", condition["leftValue"])
                self.assertEqual(0, condition["rightValue"])

    def test_final_fail_closed_activation_and_lock_paths(self) -> None:
        workflow = load(FINAL)
        connections = workflow["connections"]
        activation = "Activate verified release atomically — CLI required"
        verify_check = "Exit code 0? — Verify candidate and quality gates"
        acquire_check = "Exit code 0? — Acquire exclusive ingest lock"
        release_check = "Exit code 0? — Release owned ingest lock"

        inbound = {
            name: []
            for name in (activation, "Release owned ingest lock — CLI required")
        }
        for source, outputs in connections.items():
            for branch in outputs["main"]:
                for target in branch:
                    if target["node"] in inbound:
                        inbound[target["node"]].append(source)

        self.assertEqual([verify_check], inbound[activation])
        self.assertEqual(
            "Notify lock not acquired",
            connections[acquire_check]["main"][1][0]["node"],
        )
        self.assertNotIn(
            "Release owned ingest lock — CLI required",
            [target["node"] for target in connections[acquire_check]["main"][1]],
        )
        self.assertEqual(
            "Notify lock release failure",
            connections[release_check]["main"][1][0]["node"],
        )

    def test_final_keeps_logic_and_secrets_out_of_n8n(self) -> None:
        workflow = load(FINAL)
        self.assertEqual(1, workflow["settings"]["concurrency"])
        self.assertFalse(any(item["type"] == "n8n-nodes-base.code" for item in workflow["nodes"]))
        notifications = [
            item for item in workflow["nodes"] if item["name"].startswith("Notify ")
        ]
        self.assertEqual(4, len(notifications))
        self.assertTrue(
            all(item["type"] == "n8n-nodes-base.discord" for item in notifications)
        )
        self.assertTrue(
            all(item["parameters"]["authentication"] == "webhook" for item in notifications)
        )
        self.assertFalse(any(item["type"] == "n8n-nodes-base.emailSend" for item in workflow["nodes"]))
        self.assertNotIn("credentials", json.dumps(workflow))
        serialized = json.dumps(workflow).lower()
        self.assertNotIn("-----begin private key-----", serialized)
        self.assertNotIn("bearer ", serialized)


if __name__ == "__main__":
    unittest.main()
