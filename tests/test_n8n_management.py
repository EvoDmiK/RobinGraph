"""Unit tests for scripts/manage_n8n_korean_vernacular.py.

Everything here runs against a fake n8n Public API client: no real HTTP
call, no real credential, no remote mutation. `activate`/`deactivate` are
exercised both without `--apply` (must never call the mutating endpoint)
and with `--apply` (must call it exactly once, only once every precondition
already held). A dedicated subprocess test class covers the real bug that
mocking cannot: importing this module as a plain script rather than through
the `scripts` package.
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from scripts.deploy_n8n_reference_ingest import build_deployment
from scripts.manage_n8n_korean_vernacular import (
    FINALIZE_NODE_NAME,
    _as_nonnegative_int,
    canonical_definition_matches_local_artifact,
    cmd_activate,
    cmd_deactivate,
    cmd_status,
    execution_definition_matches_expected,
    finalize_evidence_from_execution,
    schedule_summary,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "canonical-workflow-id"
ENV = {
    "ROBINGRAPH_N8N_API_URL": "https://n8n.example.invalid/api/v1",
    "ROBINGRAPH_N8N_API_KEY": "test-api-key",
    "ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID": WORKFLOW_ID,
    "ROBINGRAPH_N8N_NEO4J_CREDENTIAL": "Neo4j",
}

FAKE_SOURCE = {
    "id": "local-artifact-id",
    "name": "RobinGraph — Korean vernacular-name ingest from Wikidata (inactive until verified)",
    "active": False,
    "pinData": {},
    "nodes": [
        {
            "id": "n1",
            "name": "Manual Trigger",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "parameters": {},
            "position": [0, 0],
        },
        {
            "id": "n2",
            "name": "Schedule Trigger — 1st of month 04:00 KST",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 4 1 * *"}]}},
            "position": [0, 80],
        },
        {
            "id": "n3",
            "name": "Some Neo4j write",
            "type": "n8n-nodes-neo4j.neo4j",
            "typeVersion": 1,
            "parameters": {"resource": "graphDb", "operation": "executeQuery", "cypherQuery": "={{ 'RETURN 1' }}"},
            "position": [200, 0],
        },
    ],
    "connections": {},
    "settings": {"executionOrder": "v1", "timezone": "Asia/Seoul", "concurrency": 1},
    "versionId": "local-version-id",
    "meta": {"templateCredsSetupCompleted": False},
    "tags": [],
}

CREDENTIALS_RESPONSE = {"data": [{"id": "neo4j-cred-id", "name": "Neo4j", "type": "neo4jApi"}]}


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], object], calls: list[tuple[str, str, object]]) -> None:
        self._responses = responses
        self.calls = calls

    def request(self, method: str, path: str, body: object | None = None) -> object:
        self.calls.append((method, path, body))
        key = (method, path)
        if key not in self._responses:
            raise AssertionError(f"unexpected request in test: {method} {path}")
        value = self._responses[key]
        return value(body) if callable(value) else value


def client_factory(responses: dict[tuple[str, str], object]) -> tuple[object, list[tuple[str, str, object]]]:
    calls: list[tuple[str, str, object]] = []

    def factory(_base_url: str, _api_key: str) -> FakeClient:
        return FakeClient(responses, calls)

    return factory, calls


def expected_payload() -> dict[str, object]:
    return build_deployment(
        copy.deepcopy(FAKE_SOURCE),
        {"id": "neo4j-cred-id", "name": "Neo4j"},
        None,
        "guild-id",
        "channel-id",
        discord_required=False,
    )


def matching_remote_workflow(*, active: bool) -> dict[str, object]:
    expected = expected_payload()
    return {
        "id": WORKFLOW_ID,
        "active": active,
        "nodes": expected["nodes"],
        "connections": expected["connections"],
        "settings": expected["settings"],
        "versionId": "remote-version-id",
        "createdAt": "2026-09-01T00:00:00.000Z",
        "updatedAt": "2026-09-10T00:00:00.000Z",
    }


def executions_path() -> str:
    return f"/executions?workflowId={WORKFLOW_ID}&status=success&limit=10"


def meaningful_finalize_json(execution_id: str, **overrides: object) -> dict[str, object]:
    payload = {
        "run_id": f"n8n-korean-vernacular-{execution_id}",
        "finalize_ok": True,
        "wikidata_dataset_id": "wikidata-dataset:taxon-labels:sha256-abc",
        "loaded_vernacular_names": 846,
        "loaded_candidates": 102,
    }
    payload.update(overrides)
    return payload


def make_execution_detail(
    execution_id: str,
    workflow_id: str,
    finalize_json: dict[str, object],
    *,
    status: str = "success",
    workflow_data: dict[str, object] | None = "__default__",
) -> dict[str, object]:
    if workflow_data == "__default__":
        payload = expected_payload()
        workflow_data = {
            "nodes": payload["nodes"],
            "connections": payload["connections"],
            "settings": payload["settings"],
        }
    detail: dict[str, object] = {
        "id": execution_id,
        "workflowId": workflow_id,
        "status": status,
        "startedAt": "2026-09-11T12:00:00.000Z",
        "data": {"resultData": {"runData": {FINALIZE_NODE_NAME: [{"data": {"main": [[{"json": finalize_json}]]}}]}}},
    }
    if workflow_data is not None:
        detail["workflowData"] = workflow_data
    return detail


class FinalizeEvidenceTest(unittest.TestCase):
    def test_meaningful_success_is_recognized(self) -> None:
        expected = expected_payload()
        execution = make_execution_detail("exec-1", WORKFLOW_ID, meaningful_finalize_json("exec-1"))
        evidence = finalize_evidence_from_execution(execution, WORKFLOW_ID, expected)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["execution_id"], "exec-1")
        self.assertEqual(evidence["loaded_vernacular_names"], 846)
        self.assertEqual(evidence["loaded_candidates"], 102)

    def test_finalize_ok_false_is_not_evidence(self) -> None:
        expected = expected_payload()
        execution = make_execution_detail(
            "exec-2", WORKFLOW_ID, meaningful_finalize_json("exec-2", finalize_ok=False)
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_zero_counts_are_not_meaningful_even_if_finalize_ok(self) -> None:
        """A run that legitimately found nothing to write still reports
        finalize_ok: true (see FINALIZE_STATEMENT) -- that is a real
        success for the pipeline, but it is not the kind of evidence that
        should be enough to justify turning on a schedule for the first
        time; there is nothing here demonstrating the write path works."""

        expected = expected_payload()
        execution = make_execution_detail(
            "exec-3",
            WORKFLOW_ID,
            meaningful_finalize_json("exec-3", loaded_vernacular_names=0, loaded_candidates=0),
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_missing_run_data_is_not_evidence(self) -> None:
        expected = expected_payload()
        execution = make_execution_detail("exec-4", WORKFLOW_ID, {})
        execution["data"]["resultData"]["runData"] = {}
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_status_must_be_success_on_the_detail_itself(self) -> None:
        """Not just trusted from the list endpoint's `status=success`
        filter used to find candidate execution ids in the first place --
        the detail response is checked again directly."""

        expected = expected_payload()
        execution = make_execution_detail(
            "exec-5", WORKFLOW_ID, meaningful_finalize_json("exec-5"), status="error"
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_missing_workflow_data_snapshot_fails_closed(self) -> None:
        expected = expected_payload()
        execution = make_execution_detail(
            "exec-6", WORKFLOW_ID, meaningful_finalize_json("exec-6"), workflow_data=None
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_execution_under_an_older_definition_is_rejected(self) -> None:
        """Regression test for a real gap: a successful execution that ran
        before the workflow was last redeployed must never count as
        evidence for the *current* (edited) definition, even though it
        shares the same canonical workflow id."""

        expected = expected_payload()
        stale_workflow_data = {
            "nodes": copy.deepcopy(expected["nodes"]),
            "connections": expected["connections"],
            "settings": expected["settings"],
        }
        stale_workflow_data["nodes"][-1]["parameters"]["cypherQuery"] = "={{ 'an older Cypher statement' }}"
        execution = make_execution_detail(
            "exec-7", WORKFLOW_ID, meaningful_finalize_json("exec-7"), workflow_data=stale_workflow_data
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_workflow_data_with_the_specific_observed_server_defaults_still_counts(self) -> None:
        """The flip side of the staleness check: the two specific,
        actually-observed harmless server additions (see
        _HARMLESS_SETTINGS_DEFAULTS / _normalize_node_for_comparison) in the
        stored execution snapshot must not refuse an execution that
        genuinely ran the current definition."""

        expected = expected_payload()
        fresh_workflow_data = {
            "nodes": copy.deepcopy(expected["nodes"]),
            "connections": expected["connections"],
            "settings": {**expected["settings"], "availableInMCP": False, "binaryMode": "separate"},
        }
        for node in fresh_workflow_data["nodes"]:
            node["disabled"] = False
        execution = make_execution_detail(
            "exec-8", WORKFLOW_ID, meaningful_finalize_json("exec-8"), workflow_data=fresh_workflow_data
        )
        evidence = finalize_evidence_from_execution(execution, WORKFLOW_ID, expected)
        self.assertIsNotNone(evidence)

    def test_workflow_data_with_a_disabled_finalize_node_is_rejected(self) -> None:
        """Same adversarial case as the definition-match tests, applied to
        the execution's own snapshot: an execution recorded against a
        definition where the Finalize node was disabled must never count as
        evidence that the write path works."""

        expected = expected_payload()
        tampered_workflow_data = {
            "nodes": copy.deepcopy(expected["nodes"]),
            "connections": expected["connections"],
            "settings": expected["settings"],
        }
        tampered_workflow_data["nodes"][-1]["disabled"] = True
        execution = make_execution_detail(
            "exec-11", WORKFLOW_ID, meaningful_finalize_json("exec-11"), workflow_data=tampered_workflow_data
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_run_id_must_belong_to_this_execution(self) -> None:
        """Guards against stale/leftover pinned data under the right
        execution id but from a different run's payload."""

        expected = expected_payload()
        execution = make_execution_detail(
            "exec-9", WORKFLOW_ID, meaningful_finalize_json("some-other-execution-id")
        )
        self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))

    def test_non_integer_and_negative_counts_are_rejected_without_crashing(self) -> None:
        expected = expected_payload()
        for bad_names in ("846", None, -5, 846.5, True):
            with self.subTest(bad_names=bad_names):
                execution = make_execution_detail(
                    "exec-10", WORKFLOW_ID, meaningful_finalize_json("exec-10", loaded_vernacular_names=bad_names)
                )
                self.assertIsNone(finalize_evidence_from_execution(execution, WORKFLOW_ID, expected))


class AsNonnegativeIntTest(unittest.TestCase):
    def test_accepts_only_genuine_non_negative_ints(self) -> None:
        self.assertEqual(0, _as_nonnegative_int(0))
        self.assertEqual(846, _as_nonnegative_int(846))
        self.assertIsNone(_as_nonnegative_int(-1))
        self.assertIsNone(_as_nonnegative_int("846"))
        self.assertIsNone(_as_nonnegative_int(846.0))
        self.assertIsNone(_as_nonnegative_int(None))
        self.assertIsNone(_as_nonnegative_int(True))


class CanonicalDefinitionMatchTest(unittest.TestCase):
    def test_matches_ignores_server_owned_fields(self) -> None:
        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        self.assertTrue(canonical_definition_matches_local_artifact(remote, expected))

    def test_mismatch_on_edited_node(self) -> None:
        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][-1]["parameters"]["cypherQuery"] = "={{ 'DROP EVERYTHING' }}"
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_tolerates_only_the_specific_observed_harmless_server_defaults(self) -> None:
        """Narrow, explicit allowlist only -- these two settings keys and
        two node keys are the ones actually confirmed present (2026-09-12
        work log) on a real read-only GET against the live canonical
        workflow, at exactly these values, never sent by this project's own
        deployer. A strict `==` on the whole structure would otherwise
        permanently refuse a perfectly valid, unedited deployment."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        for index, node in enumerate(remote["nodes"]):
            node["disabled"] = False
            if index == 0:
                node["webhookId"] = "server-assigned-uuid"
        remote["settings"] = {**remote["settings"], "availableInMCP": False, "binaryMode": "separate"}
        self.assertTrue(canonical_definition_matches_local_artifact(remote, expected))

    def test_missing_node_list_entry_is_still_caught(self) -> None:
        """Tolerating specific extra keys must never widen into tolerating
        a missing or extra *node* -- that is a real structural difference."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])[:-1]
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_a_node_silently_disabled_in_the_n8n_ui_is_never_tolerated(self) -> None:
        """The exact hole an earlier, over-broad "ignore any extra key"
        comparison had: `disabled: true` on a critical write node changes
        what actually runs while leaving every one of its `parameters`
        byte-for-byte untouched. Only `disabled: false` (the default) may
        ever be normalized away -- `true` must always cause a mismatch."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][-1]["disabled"] = True
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_an_added_onerror_override_is_never_tolerated(self) -> None:
        """An execution-affecting override added outside this project's
        generator (e.g. `onError: continueRegularOutput` added in the UI to
        silently swallow a failure this project's Cypher relies on
        propagating) must be a real, caught difference -- not dismissed as
        just another extra field."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][0]["onError"] = "continueRegularOutput"
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_an_added_executeonce_override_is_never_tolerated(self) -> None:
        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][-1]["executeOnce"] = True
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_webhook_id_is_only_tolerated_on_known_trigger_nodes(self) -> None:
        """A server-generated webhook id is harmless on this workflow's
        triggers, but accepting it on every node would unnecessarily widen
        the normalization exception."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][-1]["webhookId"] = "unexpected-on-neo4j-node"
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_malformed_node_entries_fail_closed_without_raising(self) -> None:
        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = ["not-a-node"]
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_an_unrecognized_extra_settings_key_is_never_tolerated(self) -> None:
        """Only the two specific, actually-observed settings keys are
        allowlisted -- any other addition (even one that looks equally
        plausible as a future server default) is treated as a real
        difference until it too has been confirmed and explicitly added."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["settings"] = {**remote["settings"], "errorWorkflow": None}
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))

    def test_a_duplicated_node_name_masking_a_missing_node_is_caught(self) -> None:
        """Guards the per-node name lookup itself: swapping in a duplicate
        of an existing name while dropping a different node, keeping the
        total count unchanged, must not slip past as "every name matched"."""

        expected = expected_payload()
        remote = matching_remote_workflow(active=False)
        remote["nodes"] = copy.deepcopy(remote["nodes"])
        remote["nodes"][-1] = copy.deepcopy(remote["nodes"][0])
        self.assertFalse(canonical_definition_matches_local_artifact(remote, expected))


class ExecutionDefinitionMatchTest(unittest.TestCase):
    def test_matching_snapshot_passes(self) -> None:
        expected = expected_payload()
        detail = {
            "workflowData": {
                "nodes": expected["nodes"],
                "connections": expected["connections"],
                "settings": expected["settings"],
            }
        }
        self.assertTrue(execution_definition_matches_expected(detail, expected))

    def test_missing_snapshot_fails_closed(self) -> None:
        expected = expected_payload()
        self.assertFalse(execution_definition_matches_expected({}, expected))

    def test_non_dict_snapshot_fails_closed(self) -> None:
        expected = expected_payload()
        self.assertFalse(execution_definition_matches_expected({"workflowData": "not-a-dict"}, expected))


class ScheduleSummaryTest(unittest.TestCase):
    def test_reports_raw_cron_without_computing_a_next_run(self) -> None:
        summary = schedule_summary(FAKE_SOURCE)
        self.assertIn("0 4 1 * *", summary)
        self.assertIn("Asia/Seoul", summary)
        self.assertIn("not computed", summary)


class StatusCommandTest(unittest.TestCase):
    def test_status_is_read_only_and_reports_evidence(self) -> None:
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
            ("GET", executions_path()): {"data": [{"id": "exec-1"}]},
            ("GET", "/executions/exec-1?includeData=true"): make_execution_detail(
                "exec-1", WORKFLOW_ID, meaningful_finalize_json("exec-1")
            ),
        }
        factory, calls = client_factory(responses)
        with mock.patch("scripts.manage_n8n_korean_vernacular.N8nClient", factory), mock.patch(
            "scripts.manage_n8n_korean_vernacular.load_local_artifact", return_value=copy.deepcopy(FAKE_SOURCE)
        ), mock.patch.dict("os.environ", ENV, clear=False):
            cmd_status(mock.Mock())
        # Read-only: every recorded call must be a GET.
        self.assertTrue(all(method == "GET" for method, _, _ in calls))


class ActivateCommandTest(unittest.TestCase):
    def _run_activate(self, responses: dict, *, apply: bool) -> list[tuple[str, str, object]]:
        factory, calls = client_factory(responses)
        with mock.patch("scripts.manage_n8n_korean_vernacular.N8nClient", factory), mock.patch(
            "scripts.manage_n8n_korean_vernacular.load_local_artifact", return_value=copy.deepcopy(FAKE_SOURCE)
        ), mock.patch.dict("os.environ", ENV, clear=False):
            cmd_activate(mock.Mock(apply=apply))
        return calls

    def _activation_ready_responses(self) -> dict:
        return {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
            ("GET", executions_path()): {"data": [{"id": "exec-1"}]},
            ("GET", "/executions/exec-1?includeData=true"): make_execution_detail(
                "exec-1", WORKFLOW_ID, meaningful_finalize_json("exec-1")
            ),
            ("POST", f"/workflows/{WORKFLOW_ID}/activate"): {"id": WORKFLOW_ID, "active": True},
        }

    def test_already_active_is_a_no_op_and_never_calls_activate(self) -> None:
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=True),
        }
        calls = self._run_activate(responses, apply=True)
        self.assertNotIn(("POST", f"/workflows/{WORKFLOW_ID}/activate", None), calls)

    def test_refuses_when_remote_definition_does_not_match_local_artifact(self) -> None:
        drifted = matching_remote_workflow(active=False)
        drifted["nodes"] = copy.deepcopy(drifted["nodes"])
        drifted["nodes"][-1]["parameters"]["cypherQuery"] = "={{ 'something hand-edited in the n8n UI' }}"
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): drifted,
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
        }
        with self.assertRaisesRegex(SystemExit, "does not match the"):
            self._run_activate(responses, apply=True)

    def test_refuses_when_no_successful_execution_exists(self) -> None:
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
            ("GET", executions_path()): {"data": []},
        }
        with self.assertRaisesRegex(SystemExit, "no successful execution"):
            self._run_activate(responses, apply=True)

    def test_refuses_when_the_only_execution_belongs_to_a_different_workflow_id(self) -> None:
        """The exact confusion this tool exists to prevent: a temporary
        webhook-triggered copy was run and succeeded, but it is a different
        workflow id (and, in the real flow, was deleted right after) -- its
        execution must never be accepted as evidence for the canonical id."""

        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
            ("GET", executions_path()): {"data": [{"id": "exec-from-temp-copy"}]},
            ("GET", "/executions/exec-from-temp-copy?includeData=true"): make_execution_detail(
                "exec-from-temp-copy",
                "temporary-webhook-copy-workflow-id",
                meaningful_finalize_json("exec-from-temp-copy"),
            ),
        }
        with self.assertRaisesRegex(SystemExit, "no successful execution"):
            self._run_activate(responses, apply=True)

    def test_refuses_when_the_only_success_ran_under_an_older_definition(self) -> None:
        stale_workflow_data = copy.deepcopy(matching_remote_workflow(active=False))
        stale_workflow_data["nodes"][-1]["parameters"]["cypherQuery"] = "={{ 'an older Cypher statement' }}"
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
            ("GET", "/credentials?limit=100"): CREDENTIALS_RESPONSE,
            ("GET", executions_path()): {"data": [{"id": "exec-old"}]},
            ("GET", "/executions/exec-old?includeData=true"): make_execution_detail(
                "exec-old",
                WORKFLOW_ID,
                meaningful_finalize_json("exec-old"),
                workflow_data={
                    "nodes": stale_workflow_data["nodes"],
                    "connections": stale_workflow_data["connections"],
                    "settings": stale_workflow_data["settings"],
                },
            ),
        }
        with self.assertRaisesRegex(SystemExit, "no successful execution"):
            self._run_activate(responses, apply=True)

    def test_dry_run_reports_readiness_without_calling_activate(self) -> None:
        calls = self._run_activate(self._activation_ready_responses(), apply=False)
        self.assertNotIn(("POST", f"/workflows/{WORKFLOW_ID}/activate", None), calls)

    def test_apply_calls_activate_exactly_once_when_every_precondition_holds(self) -> None:
        calls = self._run_activate(self._activation_ready_responses(), apply=True)
        activate_calls = [call for call in calls if call[:2] == ("POST", f"/workflows/{WORKFLOW_ID}/activate")]
        self.assertEqual(1, len(activate_calls))

    def test_apply_refuses_if_definition_changes_during_evidence_check(self) -> None:
        first = matching_remote_workflow(active=False)
        changed = matching_remote_workflow(active=False)
        changed["nodes"] = copy.deepcopy(changed["nodes"])
        changed["nodes"][-1]["parameters"]["cypherQuery"] = "={{ 'changed after smoke run' }}"
        remote_versions = iter((first, changed))
        responses = self._activation_ready_responses()
        responses[("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true")] = lambda _body: next(remote_versions)
        factory, calls = client_factory(responses)
        with mock.patch("scripts.manage_n8n_korean_vernacular.N8nClient", factory), mock.patch(
            "scripts.manage_n8n_korean_vernacular.load_local_artifact", return_value=copy.deepcopy(FAKE_SOURCE)
        ), mock.patch.dict("os.environ", ENV, clear=False), self.assertRaisesRegex(
            SystemExit, "changed while execution evidence"
        ):
            cmd_activate(mock.Mock(apply=True))
        self.assertNotIn(("POST", f"/workflows/{WORKFLOW_ID}/activate", None), calls)


class DeactivateCommandTest(unittest.TestCase):
    def _run_deactivate(self, responses: dict, *, apply: bool) -> list[tuple[str, str, object]]:
        factory, calls = client_factory(responses)
        with mock.patch("scripts.manage_n8n_korean_vernacular.N8nClient", factory), mock.patch.dict(
            "os.environ", ENV, clear=False
        ):
            cmd_deactivate(mock.Mock(apply=apply))
        return calls

    def test_already_inactive_is_a_no_op(self) -> None:
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=False),
        }
        calls = self._run_deactivate(responses, apply=True)
        self.assertNotIn(("POST", f"/workflows/{WORKFLOW_ID}/deactivate", None), calls)

    def test_dry_run_never_calls_deactivate(self) -> None:
        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=True),
        }
        calls = self._run_deactivate(responses, apply=False)
        self.assertNotIn(("POST", f"/workflows/{WORKFLOW_ID}/deactivate", None), calls)

    def test_apply_calls_deactivate_when_active_needs_no_run_evidence_or_definition_match(self) -> None:
        """Turning the schedule off is always the safe direction: unlike
        activate, it must not require the definition-match or execution-
        evidence checks (which is why this response set omits both
        `/credentials` and `/executions`, and would fail loudly via
        FakeClient's assertion if deactivate ever tried to call them)."""

        responses = {
            ("GET", f"/workflows/{WORKFLOW_ID}?excludePinnedData=true"): matching_remote_workflow(active=True),
            ("POST", f"/workflows/{WORKFLOW_ID}/deactivate"): {"id": WORKFLOW_ID, "active": False},
        }
        calls = self._run_deactivate(responses, apply=True)
        deactivate_calls = [call for call in calls if call[:2] == ("POST", f"/workflows/{WORKFLOW_ID}/deactivate")]
        self.assertEqual(1, len(deactivate_calls))


class DirectScriptInvocationTest(unittest.TestCase):
    """Regression coverage for a real bug: `from scripts.deploy_n8n_...
    import ...` (an absolute, package-qualified import) crashes with
    `ModuleNotFoundError: No module named 'scripts'` the moment this file is
    run directly as a script (`python scripts/manage_n8n_korean_vernacular.py`)
    rather than imported as part of the `scripts` package -- exactly how
    `deploy_nas.sh` invokes it inside the NAS `nas-tools` container. A
    mocked in-process import can't catch this class of bug at all, because
    the test process itself already has `scripts` importable on `sys.path`;
    only a real subprocess, run the way the NAS container actually runs it,
    can.
    """

    def _minimal_env(self, **overrides: str) -> dict[str, str]:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
        env.update(overrides)
        return env

    def test_help_succeeds_when_invoked_as_a_direct_script_from_repo_root(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/manage_n8n_korean_vernacular.py", "--help"],
            cwd=ROOT,
            env=self._minimal_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertIn("status", result.stdout)
        self.assertIn("activate", result.stdout)
        self.assertIn("deactivate", result.stdout)

    def test_help_succeeds_when_invoked_as_a_module(self) -> None:
        """The other supported shape: `python -m scripts.manage_n8n_korean_vernacular`."""

        result = subprocess.run(
            [sys.executable, "-m", "scripts.manage_n8n_korean_vernacular", "--help"],
            cwd=ROOT,
            env=self._minimal_env(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_status_without_credentials_fails_closed_before_any_network_call(self) -> None:
        """Exercises past the import line into `require_client()`, still as
        a real subprocess, without ever attempting a real HTTP request:
        blank credentials in the subprocess's own environment are present
        (not merely absent), so `load_env`'s `setdefault` cannot repopulate
        them from a real, git-ignored `.env` this checkout might have."""

        result = subprocess.run(
            [sys.executable, "scripts/manage_n8n_korean_vernacular.py", "status"],
            cwd=ROOT,
            env=self._minimal_env(
                ROBINGRAPH_N8N_API_URL="",
                ROBINGRAPH_N8N_API_KEY="",
                ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID="",
            ),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertIn("ROBINGRAPH_N8N_API_URL", result.stderr)


if __name__ == "__main__":
    unittest.main()
