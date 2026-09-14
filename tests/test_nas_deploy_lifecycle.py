from __future__ import annotations

import os
import re
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
# invocation and answers just enough to exercise the full lifecycle --
# preflight/build/deploy/update/rollback/dry-run/stop -- without touching a
# real Docker daemon or network.
log="$DOCKER_CALL_LOG"
printf '%s\\n' "$*" >> "$log"

if [ "$1" = "network" ] && [ "$2" = "inspect" ]; then
    [ "$3" = "$DOCKER_STUB_NETWORK" ] && exit 0
    exit 1
fi

if [ "$1" = "image" ] && [ "$2" = "inspect" ]; then
    [ "$3" = "${DOCKER_STUB_ROLLBACK_IMAGE:-}" ] && exit 0
    exit 1
fi

if [ "$1" = "inspect" ]; then
    echo "${DOCKER_STUB_HEALTH:-healthy}"
    exit 0
fi

if [ "$1" = "compose" ]; then
    shift
    rest="$*"
    case "$rest" in
        *"ps -q api"*)
            echo "${DOCKER_STUB_CONTAINER_ID:-stub-container-id}"
            exit 0
            ;;
        *"version"*)
            exit 0
            ;;
        *"config --quiet"*)
            exit 0
            ;;
        *"config"*)
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


def _non_comment_code(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines)


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
        for action in (
            "preflight)",
            "build)",
            "deploy)",
            "update)",
            "verify)",
            "status)",
            "logs)",
            "stop)",
            "rollback)",
            "dry-run)",
        ):
            self.assertIn(action, script)

        for action in ("build)", "deploy)", "update)", "stop)", "rollback)", "dry-run)"):
            block = script.split(action, 1)[1].split(";;", 1)[0]
            self.assertIn(
                "preflight_api",
                block,
                f"{action} must run preflight_api before mutating anything",
            )

        usage_line = next(line for line in script.splitlines() if line.strip().startswith('die "usage:'))
        for action in (
            "preflight",
            "build",
            "deploy",
            "update",
            "verify",
            "status",
            "logs",
            "stop",
            "rollback",
            "dry-run",
            "package",
        ):
            self.assertIn(action, usage_line)

        # The zero-argument fail-closed path must die with the same kind of
        # usage message before ACTION is ever assigned from $1.
        zero_arg_line = next(
            line for line in script.splitlines() if '[ "$#" -gt 0 ] || die "usage:' in line
        )
        for action in ("preflight", "build", "deploy", "update", "rollback", "dry-run"):
            self.assertIn(action, zero_arg_line)

    def test_zero_arguments_is_not_a_valid_action_and_uses_die(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        # There must be no `${1:-<action>}` default anywhere: a missing
        # action must never silently resolve to a real action name.
        self.assertNotRegex(script, r"\$\{1:-[a-zA-Z-]+\}")
        self.assertIn('[ "$#" -gt 0 ] || die "usage:', script)
        # The zero-argument check must run before ACTION is derived from $1.
        zero_arg_idx = script.index('[ "$#" -gt 0 ] || die "usage:')
        action_assign_idx = script.index("ACTION=$1")
        self.assertLess(zero_arg_idx, action_assign_idx)

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

    def test_rollback_action_never_builds_or_downs_and_requires_an_image_argument(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        rollback_block = script.split("rollback)", 1)[1].split(";;", 1)[0]
        code_lines = [
            line
            for line in rollback_block.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        self.assertIn("docker image inspect", code_only)
        self.assertIn("compose_api up -d --remove-orphans api", code_only)
        self.assertIn("wait_for_api", code_only)
        self.assertNotIn("compose_api build", code_only)
        self.assertNotIn("down", code_only)
        self.assertNotIn("-v", code_only)
        self.assertNotIn("--volumes", code_only)
        # Must require an explicit argument before doing anything else.
        self.assertRegex(code_only, r'\[\s*"\$#"\s*-ge\s*1\s*\]')

    def test_dry_run_action_never_mutates(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        dry_run_block = script.split("dry-run)", 1)[1].split(";;", 1)[0]
        code_lines = [
            line
            for line in dry_run_block.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        self.assertNotIn("compose_api build", code_only)
        self.assertNotIn("compose_api up", code_only)
        self.assertNotIn("down", code_only)

    def test_package_action_delegates_and_never_touches_docker(self) -> None:
        script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
        package_block = script.split("package)", 1)[1].split(";;", 1)[0]
        self.assertIn("package_nas_release.sh", package_block)
        self.assertNotIn("docker", package_block)

        package_script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        code = _non_comment_code(package_script).replace(".dockerignore", "")
        self.assertNotIn("docker", code)
        self.assertNotIn("curl ", code)
        self.assertNotIn("wget ", code)
        self.assertNotIn("git push", package_script)

    def _run_with_stub_docker(
        self,
        action: str,
        env_overrides: dict[str, str],
        network_ok: bool = True,
        extra_args: list[str] | None = None,
        stub_env: dict[str, str] | None = None,
        no_action: bool = False,
    ) -> tuple[subprocess.CompletedProcess, str]:
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
            if stub_env:
                env.update(stub_env)

            argv = ["sh", str(DEPLOY_SCRIPT)]
            if not no_action:
                argv.append(action)
            if extra_args:
                argv.extend(extra_args)

            result = subprocess.run(
                argv,
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

    def test_deploy_and_update_actions_build_deploy_and_health_check(self) -> None:
        for action in ("deploy", "update"):
            with self.subTest(action=action):
                result, calls = self._run_with_stub_docker(action, {}, network_ok=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("build --pull api", calls)
                self.assertIn("up -d --remove-orphans api", calls)
                self.assertIn("healthy", result.stdout)
                self.assertNotIn("down", calls)

    def test_rollback_requires_an_image_argument_before_touching_docker(self) -> None:
        result, calls = self._run_with_stub_docker("rollback", {}, network_ok=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("usage", result.stderr)
        self.assertEqual("", calls.strip(), "rollback with no image argument must issue zero docker calls")

    def test_rollback_never_builds_and_recovers_via_health_check(self) -> None:
        result, calls = self._run_with_stub_docker(
            "rollback",
            {},
            network_ok=True,
            extra_args=["robingraph-api:previous-good"],
            stub_env={"DOCKER_STUB_ROLLBACK_IMAGE": "robingraph-api:previous-good"},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("image inspect robingraph-api:previous-good", calls)
        self.assertIn("up -d --remove-orphans api", calls)
        self.assertNotIn("build --pull api", calls)
        self.assertNotIn("down", calls)
        for line in calls.splitlines():
            self.assertNotIn("-v", line.split())
            self.assertNotIn("--volumes", line)
        self.assertIn("healthy", result.stdout)

    def test_rollback_fails_closed_when_the_image_is_not_present_locally(self) -> None:
        result, calls = self._run_with_stub_docker(
            "rollback",
            {},
            network_ok=True,
            extra_args=["robingraph-api:never-built"],
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("rollback image not found locally", result.stderr)
        self.assertNotIn("up -d --remove-orphans api", calls)
        self.assertNotIn("build --pull api", calls)

    def test_dry_run_action_makes_zero_mutating_docker_calls(self) -> None:
        result, calls = self._run_with_stub_docker("dry-run", {}, network_ok=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("build --pull api", calls)
        self.assertNotIn("up -d --remove-orphans api", calls)
        self.assertNotIn("down", calls)
        self.assertIn("dry-run", result.stdout)

    def test_zero_argument_stub_audit_proves_no_docker_mutations(self) -> None:
        result, calls = self._run_with_stub_docker("", {}, network_ok=True, no_action=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(
            "", calls.strip(), "a zero-argument invocation must never call docker at all"
        )
        self.assertIn("usage", result.stderr)
        self.assertNotIn("build --pull api", calls)
        self.assertNotIn("up -d --remove-orphans api", calls)

    def test_unknown_action_fails_closed_without_calling_docker(self) -> None:
        result, calls = self._run_with_stub_docker("this-is-not-an-action", {}, network_ok=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", calls.strip())


if __name__ == "__main__":
    unittest.main()
