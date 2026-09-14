"""Container deployment invariants kept independent of a Docker daemon."""

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
        self.assertIn("build_tools_image", deploy_workflows_block)
        self.assertIn(
            "scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply",
            deploy_workflows_block,
        )

    def test_korean_vernacular_has_dedicated_nas_preflight_deploy_and_verify_actions(self) -> None:
        script = (ROOT / "scripts" / "deploy_nas.sh").read_text(encoding="utf-8")

        preflight = script.split("preflight-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn("preflight_tools", preflight)
        self.assertIn("build_tools_image", preflight)
        self.assertIn("check_korean_vernacular_workflow", preflight)

        deploy = script.split("deploy-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn("check_korean_vernacular_workflow", deploy)
        self.assertIn(
            "scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply",
            deploy,
        )
        self.assertLess(
            deploy.index("check_korean_vernacular_workflow"),
            deploy.index("--workflow korean-vernacular --apply"),
        )

        verify = script.split("verify-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn(
            'require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"',
            verify,
        )
        self.assertIn("check_korean_vernacular_workflow", verify)

    def test_workflow_deployments_rebuild_the_tools_image_from_the_current_checkout(self) -> None:
        script = (ROOT / "scripts" / "deploy_nas.sh").read_text(encoding="utf-8")
        helper = script.split("build_tools_image()", 1)[1].split("}", 1)[0]
        self.assertIn("compose_tools build --pull nas-tools", helper)

    def test_korean_vernacular_has_status_activate_and_deactivate_actions_with_explicit_write_intent(
        self,
    ) -> None:
        script = (ROOT / "scripts" / "deploy_nas.sh").read_text(encoding="utf-8")

        status = script.split("status-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn("preflight_tools", status)
        self.assertIn('require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"', status)
        self.assertIn("scripts/manage_n8n_korean_vernacular.py status", status)
        # Read-only: status must never pass --apply.
        self.assertNotIn("--apply", status)

        activate = script.split("activate-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn('require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"', activate)
        self.assertIn("scripts/manage_n8n_korean_vernacular.py activate --apply", activate)

        deactivate = script.split("deactivate-korean-vernacular)", 1)[1].split(";;", 1)[0]
        self.assertIn('require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"', deactivate)
        self.assertIn("scripts/manage_n8n_korean_vernacular.py deactivate --apply", deactivate)

        usage_line = next(line for line in script.splitlines() if line.strip().startswith('die "usage:'))
        for action in ("status-korean-vernacular", "activate-korean-vernacular", "deactivate-korean-vernacular"):
            self.assertIn(action, usage_line)

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

    def setUp(self) -> None:
        self.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.compose = (ROOT / "compose.nas.yml").read_text(encoding="utf-8")
        self.api = self.compose.split("  nas-tools:", 1)[0]

    def test_runtime_base_is_digest_pinned_and_arm64_capable(self) -> None:
        self.assertIn(
            "FROM ghcr.io/astral-sh/uv:0.11.26-python3.12-trixie-slim@sha256:",
            self.dockerfile,
        )
        self.assertIn("linux/arm64", self.dockerfile)
        self.assertNotIn("--platform=linux/amd64", self.dockerfile)
        self.assertIn("UV_PYTHON_DOWNLOADS=never", self.dockerfile)
        self.assertIn("uv sync --python /usr/local/bin/python --locked --no-dev", self.dockerfile)

    def test_image_has_versioned_oci_metadata_and_required_ui_assets(self) -> None:
        for label in (
            "org.opencontainers.image.title",
            "org.opencontainers.image.version",
            "org.opencontainers.image.revision",
        ):
            self.assertIn(label, self.dockerfile)
        self.assertIn("COPY --chown=robingraph:robingraph src ./src", self.dockerfile)
        for asset in ("index.html", "chat.js", "styles.css"):
            self.assertIn(f"src/robingraph/api/static/{asset}", self.dockerfile)

    def test_image_provenance_labels_explicitly_identify_robingraph(self) -> None:
        repository_url = "https://github.com/EvoDmiK/RobinGraph"
        for label in (
            "org.opencontainers.image.source",
            "org.opencontainers.image.url",
        ):
            self.assertIn(f'{label}="{repository_url}"', self.dockerfile)

    def test_api_is_fixture_first_and_hardened_without_a_host_port(self) -> None:
        self.assertIn("${ROBINGRAPH_API_MODE:-serve-fixture}", self.api)
        self.assertIn("image: ${ROBINGRAPH_IMAGE:-robingraph-api:local}", self.api)
        self.assertIn("VERSION: ${ROBINGRAPH_IMAGE_VERSION:-0.1.0}", self.api)
        self.assertIn("VCS_REF: ${ROBINGRAPH_VCS_REF:-unknown}", self.api)
        self.assertIn("expose:\n      - \"8000\"", self.api)
        self.assertNotIn("ports:", self.api)
        self.assertIn("read_only: true", self.api)
        self.assertIn("/tmp:size=64m,mode=1777", self.api)
        self.assertIn("cap_drop:\n      - ALL", self.api)
        self.assertIn("no-new-privileges:true", self.api)
        self.assertIn("restart: unless-stopped", self.api)
        self.assertIn("stop_grace_period: 20s", self.api)
        self.assertIn("max-size: 10m", self.api)
        self.assertIn("max-file: \"3\"", self.api)

    def test_compose_has_loopback_healthcheck_and_external_edge_network(self) -> None:
        self.assertIn("healthcheck:", self.api)
        self.assertIn("http://127.0.0.1:8000/health", self.api)
        self.assertIn("assert response.status == 200", self.api)
        self.assertIn("start_period: 10s", self.api)
        self.assertIn("external: true", self.compose)
        self.assertIn("name: ${ROBINGRAPH_EDGE_NETWORK:-robingraph-edge}", self.compose)

    def test_non_root_dockerfile_exposes_only_the_api_port(self) -> None:
        self.assertIn("USER 10001:10001", self.dockerfile)
        self.assertEqual(["EXPOSE 8000"], [line for line in self.dockerfile.splitlines() if line.startswith("EXPOSE ")])
        self.assertIn("http://127.0.0.1:8000/health", self.dockerfile)


if __name__ == "__main__":
    unittest.main()
