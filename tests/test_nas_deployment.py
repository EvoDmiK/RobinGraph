from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NasDeploymentTest(unittest.TestCase):
    def test_runtime_image_contains_api_configuration_and_tools(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY --chown=robingraph:robingraph config ./config", dockerfile)
        self.assertIn("COPY --chown=robingraph:robingraph n8n ./n8n", dockerfile)
        self.assertIn("COPY --chown=robingraph:robingraph scripts ./scripts", dockerfile)
        self.assertIn("/app/.cache", dockerfile)
        self.assertIn("USER 10001:10001", dockerfile)

        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("!scripts/**", dockerignore)
        self.assertIn("!config/**", dockerignore)
        self.assertIn("!n8n/**", dockerignore)

    def test_api_and_privileged_one_shot_tools_are_separate(self) -> None:
        compose = (ROOT / "compose.nas.yml").read_text(encoding="utf-8")
        api, tools = compose.split("  nas-tools:", 1)
        self.assertIn("container_name: robingraph-api", api)
        self.assertIn("expose:", api)
        self.assertNotIn("ports:", api)
        self.assertNotIn("ROBINGRAPH_N8N_API_KEY", api)
        self.assertIn("profiles:", tools)
        self.assertIn("ROBINGRAPH_N8N_API_KEY", tools)
        self.assertIn("ingest-cache:/app/.cache", tools)
        self.assertIn("deployment-state:/home/robingraph/.local/state", tools)
        self.assertGreaterEqual(compose.count("read_only: true"), 2)
        self.assertGreaterEqual(compose.count("no-new-privileges:true"), 2)

    def test_ingest_example_contains_names_not_secret_values(self) -> None:
        example = (ROOT / ".env.nas.ingest.example").read_text(encoding="utf-8")
        values = dict(
            line.split("=", 1)
            for line in example.splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        self.assertEqual("", values["ROBINGRAPH_N8N_API_KEY"])
        self.assertEqual("", values["NEO4J_PASSWORD"])
        self.assertEqual("http://neo4j:7474", values["ROBINGRAPH_NEO4J_HTTP_URL"])
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env.nas.ingest", ignored)
        self.assertNotIn(".env.nas.ingest.example", ignored)

    def test_deploy_script_has_preflight_health_and_explicit_mutations(self) -> None:
        script = (ROOT / "scripts" / "deploy_nas.sh").read_text(encoding="utf-8")
        self.assertTrue(script.startswith("#!/bin/sh\nset -eu\n"))
        self.assertIn("docker network inspect", script)
        self.assertIn("config --quiet", script)
        self.assertIn("wait_for_api", script)
        self.assertIn("deploy-workflows)", script)
        self.assertIn("ingest-avonet)", script)
        self.assertNotIn("source \"$", script)
        self.assertNotIn("set -x", script)

    def test_deploy_workflows_action_includes_korean_vernacular(self) -> None:
        script = (ROOT / "scripts" / "deploy_nas.sh").read_text(encoding="utf-8")
        deploy_workflows_block = script.split("deploy-workflows)", 1)[1].split(";;", 1)[0]
        self.assertIn(
            "scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply",
            deploy_workflows_block,
        )

    def test_ingest_example_and_compose_pass_through_korean_vernacular_workflow_id(self) -> None:
        example = (ROOT / ".env.nas.ingest.example").read_text(encoding="utf-8")
        values = dict(
            line.split("=", 1)
            for line in example.splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        self.assertIn("ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID", values)
        self.assertEqual("", values["ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID"])

        compose = (ROOT / "compose.nas.yml").read_text(encoding="utf-8")
        _, tools = compose.split("  nas-tools:", 1)
        self.assertIn(
            "ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID: "
            "${ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID:-}",
            tools,
        )


if __name__ == "__main__":
    unittest.main()
