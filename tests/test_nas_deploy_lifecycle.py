from __future__ import annotations

import os
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_nas.sh"
PACKAGE_SCRIPT = ROOT / "scripts" / "package_nas_release.sh"

FAKE_DOCKER = """#!/bin/sh
# Stub docker(1) for offline testing of scripts/deploy_nas.sh. Records every
# invocation and answers just enough to exercise preflight/build/stop
# without touching a real Docker daemon or network.
log="$DOCKER_CALL_LOG"
printf '%s\\n' "$*" >> "$log"

if [ "$1" = "network" ] && [ "$2" = "inspect" ]; then
    [ "$3" = "$DOCKER_STUB_NETWORK" ] && exit 0
    exit 1
fi

if [ "$1" = "compose" ]; then
    shift
    rest="$*"
    case "$rest" in
        *"version"*)
            exit 0
            ;;
        *"config --quiet"*)
            exit 0
            ;;
        *"build --pull api"*)
            exit 0
            ;;
        *"stop api"*)
            exit 0
            ;;
    esac
    exit 0
fi

exit 0
"""


class NasDeployLifecycleTest(unittest.TestCase):
    def test_scripts_are_valid_posix_sh(self) -> None:
        for script in (DEPLOY_SCRIPT, PACKAGE_SCRIPT):
            result = subprocess.run(
                ["sh", "-n", str(script)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                0, result.returncode, f"{script}: {result.stderr}"
            )

    def test_scripts_are_executable_and_shebanged(self) -> None:
        for script in (DEPLOY_SCRIPT, PACKAGE_SCRIPT):
            text = script.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/sh\nset -eu\n"), script)
            mode = script.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f"{script} is not executable")

    def test_lifecycle_actions_are_explicit_and_fail_closed(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        for action in ("preflight)", "build)", "deploy)", "verify)", "status)", "logs)", "stop)"):
            self.assertIn(action, script)

        for action in ("build)", "stop)"):
            block = script.split(action, 1)[1].split(";;", 1)[0]
            self.assertIn(
                "preflight_api",
                block,
                f"{action} must run preflight_api before mutating anything",
            )

        usage_line = next(line for line in script.splitlines() if line.strip().startswith('die "usage:'))
        for action in ("preflight", "build", "deploy", "verify", "status", "logs", "stop", "package"):
            self.assertIn(action, usage_line)

    def test_stop_action_is_rollback_safe(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        stop_block = script.split("stop)", 1)[1].split(";;", 1)[0]
        code_lines = [
            line for line in stop_block.splitlines() if line.strip() and not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        self.assertIn("compose_api stop api", code_only)
        self.assertNotIn("down", code_only)
        self.assertNotIn("-v", code_only)
        self.assertNotIn("--volumes", code_only)
        self.assertNotIn("rm ", code_only)

    def test_package_action_delegates_and_never_touches_docker(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        package_block = script.split("package)", 1)[1].split(";;", 1)[0]
        self.assertIn("package_nas_release.sh", package_block)
        self.assertNotIn("docker", package_block)

        package_script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("docker", package_script)
        self.assertNotIn("git push", package_script)
        self.assertNotIn("git -C \"$ROOT_DIR\" push", package_script)

    def _run_with_stub_docker(
        self, action: str, env_overrides: dict[str, str], network_ok: bool = True
    ) -> tuple[subprocess.CompletedProcess, Path]:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            fake_docker_path = bin_dir / "docker"
            fake_docker_path.write_text(FAKE_DOCKER, encoding="utf-8")
            fake_docker_path.chmod(0o755)

            call_log = tmp_path / "docker-calls.log"
            call_log.write_text("", encoding="utf-8")

            api_env = tmp_path / ".env.nas"
            base_env = {
                "ROBINGRAPH_EDGE_NETWORK": "robingraph-edge",
                "ROBINGRAPH_API_MODE": "serve-fixture",
            }
            base_env.update(env_overrides)
            api_env.write_text(
                "\n".join(f"{k}={v}" for k, v in base_env.items()) + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["DOCKER_CALL_LOG"] = str(call_log)
            env["DOCKER_STUB_NETWORK"] = "robingraph-edge" if network_ok else "unreachable-network"
            env["ROBINGRAPH_NAS_API_ENV"] = str(api_env)
            env["ROBINGRAPH_NAS_TOOLS_ENV"] = str(tmp_path / ".env.nas.ingest")

            result = subprocess.run(
                ["sh", str(DEPLOY_SCRIPT), action],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(ROOT),
            )
            calls = call_log.read_text(encoding="utf-8")
            return result, calls

    def test_preflight_fails_closed_when_edge_network_is_missing(self) -> None:
        result, _ = self._run_with_stub_docker("preflight", {}, network_ok=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("external Docker network does not exist", result.stderr)

    def test_preflight_fails_closed_when_neo4j_mode_missing_credentials(self) -> None:
        result, _ = self._run_with_stub_docker(
            "preflight", {"ROBINGRAPH_API_MODE": "serve-neo4j"}, network_ok=True
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("must be set", result.stderr)

    def test_preflight_succeeds_with_valid_fixture_configuration(self) -> None:
        result, _ = self._run_with_stub_docker("preflight", {}, network_ok=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_stop_action_only_issues_a_non_destructive_compose_stop(self) -> None:
        result, calls = self._run_with_stub_docker("stop", {}, network_ok=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("stop api", calls)
        self.assertNotIn("down", calls)
        for line in calls.splitlines():
            self.assertNotIn("-v", line.split())
            self.assertNotIn("--volumes", line)

    def test_build_action_runs_preflight_before_building(self) -> None:
        result, calls = self._run_with_stub_docker("build", {}, network_ok=True)
        self.assertEqual(0, result.returncode, result.stderr)
        lines = [line for line in calls.splitlines() if line]
        network_calls = [i for i, line in enumerate(lines) if line.startswith("network inspect")]
        build_calls = [i for i, line in enumerate(lines) if "build --pull api" in line]
        self.assertTrue(network_calls, "preflight did not check the network")
        self.assertTrue(build_calls, "build action did not build the api image")
        self.assertLess(
            min(network_calls),
            min(build_calls),
            "preflight (network check) must run before the build mutates anything",
        )

    def test_unknown_action_fails_closed_without_calling_docker(self) -> None:
        result, calls = self._run_with_stub_docker("this-is-not-an-action", {}, network_ok=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", calls.strip())


if __name__ == "__main__":
    unittest.main()
