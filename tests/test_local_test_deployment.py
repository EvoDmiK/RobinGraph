from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalTestDeploymentTest(unittest.TestCase):
    def run_action(self, action):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            for name in ("deploy_local_test.sh", "deploy_nas.sh"):
                shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
            for name in ("compose.nas.yml", "compose.local-test.yml"):
                shutil.copyfile(ROOT / name, root / name)
            (root / ".env.nas.test").write_text(
                "ROBINGRAPH_API_MODE=serve-fixture\n"
                "ROBINGRAPH_IMAGE=robingraph-api:test-only\n"
                "ROBINGRAPH_EDGE_NETWORK=local-test-network\n"
            )
            (root / ".env.nas.prod").write_text("ROBINGRAPH_IMAGE=robingraph-api:prod-only\n")
            calls = root / "calls.jsonl"
            docker = root / "bin" / "docker"
            docker.write_text(
                f"#!{sys.executable}\n"
                "import os, sys, json\n"
                "keys = ['ROBINGRAPH_DEPLOY_TARGET', 'ROBINGRAPH_COMPOSE_PROJECT', 'ROBINGRAPH_API_CONTAINER', 'ROBINGRAPH_IMAGE']\n"
                "with open(os.environ['DOCKER_CALLS'], 'a') as f:\n"
                " f.write(json.dumps({'args': sys.argv[1:], 'env': {k: os.getenv(k) for k in keys}}) + '\\n')\n"
            )
            docker.chmod(0o755)
            env = {**os.environ, "PATH": f"{root / 'bin'}:{os.environ['PATH']}",
                   "DOCKER_CALLS": str(calls), "ROBINGRAPH_DEPLOY_TARGET": "prod",
                   "ROBINGRAPH_COMPOSE_PROJECT": "production", "ROBINGRAPH_IMAGE": "prod-image"}
            env.pop("ROBINGRAPH_NAS_API_ENV", None)
            result = subprocess.run(
                ["sh", str(root / "scripts" / "deploy_local_test.sh"), action],
                env=env, capture_output=True, text=True,
            )
            records = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            return result, records

    def test_start_uses_local_ports_and_pins_test_despite_inherited_prod(self):
        result, calls = self.run_action("start")
        self.assertEqual(result.returncode, 0, result.stderr)
        start = next(call for call in calls if "up" in call["args"])
        self.assertEqual(start["env"]["ROBINGRAPH_DEPLOY_TARGET"], "test")
        self.assertEqual(start["env"]["ROBINGRAPH_COMPOSE_PROJECT"], "robingraph-test")
        self.assertEqual(start["env"]["ROBINGRAPH_API_CONTAINER"], "robingraph-api-test")
        self.assertEqual(start["env"]["ROBINGRAPH_IMAGE"], "robingraph-api:test-only")
        self.assertTrue(any(arg.endswith("compose.local-test.yml") for arg in start["args"]))
        self.assertTrue(any(arg.endswith(".env.nas.test") for arg in start["args"]))
        self.assertNotIn("build", start["args"])

    def test_deploy_builds_before_starting_only_api(self):
        result, calls = self.run_action("deploy")
        self.assertEqual(result.returncode, 0, result.stderr)
        build = next(i for i, call in enumerate(calls) if "build" in call["args"])
        start = next(i for i, call in enumerate(calls) if "up" in call["args"])
        self.assertLess(build, start)
        self.assertEqual(calls[start]["args"][-4:], ["up", "-d", "--no-build", "api"])

    def test_invalid_action_does_not_touch_docker(self):
        result, calls = self.run_action("prod")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
