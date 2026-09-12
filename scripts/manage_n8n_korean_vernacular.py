"""Read-only status plus explicit-write activate/deactivate for the Korean
vernacular n8n workflow's schedule.

`scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply`
creates or updates the canonical workflow, always inactive. This script
never deploys a definition; it only inspects the already-deployed canonical
workflow and, on request, flips its Public API `active` flag.

Every subcommand defaults to a dry run: it prints what it found and what it
*would* do, but performs no write. `activate`/`deactivate` only call the n8n
API when invoked with `--apply` -- explicit write intent, mirroring
`deploy_n8n_reference_ingest.py --apply`.

`activate` refuses unless two independent things are true, both checked
against the live n8n API (never taken on trust from a flag or an operator's
say-so):

1. **The canonical remote definition matches the reviewed local artifact.**
   Recomputed with the exact same `build_deployment` this project already
   uses to deploy, then compared against what `GET /workflows/{id}` actually
   returns. A workflow that was hand-edited in the n8n UI after the last
   `--apply`, or that has drifted from an older deploy, refuses activation
   until it is redeployed. Comparison is exact after removing only the
   explicitly allowlisted, observed server defaults. Other added fields,
   including execution-affecting overrides, are rejected.
2. **The specific execution offered as evidence actually ran the definition
   being activated, not an older one that happened to succeed.** The Public
   API has no manual-run endpoint (see docs/n8n/korean-vernacular-ingest.md
   and the 2026-09-12 work log): the only way to smoke-test this pipeline
   through that API is a throwaway webhook-triggered copy, run once, then
   deleted. Activation evidence instead requires a canonical execution,
   which can be started manually in the n8n UI.
   That copy's execution history is `n8n-korean-vernacular-<its own
   execution id>` under a *different*, now-deleted workflow id -- it is
   never visible through `GET /executions?workflowId=<canonical id>` and
   this script never asks an operator to just assert "it worked, trust me".
   An execution only counts as evidence when *all* of the following hold:
   - it belongs to the canonical workflow id (`workflowId`);
   - n8n itself reports `status: "success"` on the execution detail, not
     only the list endpoint's `status=success` filter;
   - the execution's own recorded `workflowData` (the definition snapshot
     n8n stored *at the time that execution ran*) matches `expected` by the
     same narrowly normalized comparison as (1) -- a success from *before* the
     definition was last edited must never count for the definition being
     activated *now*, even though it shares the same workflow id;
   - its 'Verify Korean vernacular release finalized' node output shows
     `finalize_ok: true`, `loaded_vernacular_names`/`loaded_candidates` are
     both actual non-negative integers (never blindly coerced -- a
     malformed or missing value is treated as disqualifying, not as zero)
     summing to more than zero (not merely "the execution's overall status
     is success", which n8n also reports for a run that legitimately found
     nothing to do); and
   - that output's own `run_id` equals `n8n-korean-vernacular-<this
     execution's id>` (see `build_configuration_js`) -- confirming the
     counts actually belong to *this* execution and were not left over from
     unrelated pinned/cached data.

Today, satisfying (2) against the real canonical workflow requires running
it for real at least once (manually, from the n8n UI, per the first-run
checklist) *after* the current definition was deployed -- there is no way
around that with the tools this project has. That is a real, current
limitation, not something this script works around; see the printed
guidance when no qualifying execution is found.

`deactivate` has no such gate: turning the schedule off is always the safe
direction, so it only requires `--apply`.

This script does not compute or print a "next scheduled run" time for the
cron trigger. n8n's `cronExpression` (see `Schedule Trigger` in the
generated workflow) can only be resolved to a precise next-run instant by
n8n's own scheduler; approximating it here risks reporting a wrong time
with false confidence. `status` prints the raw cron expression and
timezone instead.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Mirrors generate_n8n_korean_vernacular_ingest.py's own import fallback:
# `python -m scripts.manage_n8n_korean_vernacular` (as tests import it) has
# `scripts` as a real package on sys.path, so the relative import resolves.
# `python scripts/manage_n8n_korean_vernacular.py` (direct invocation, as
# used from the NAS `nas-tools` image and `deploy_nas.sh`) runs this file as
# `__main__` with no parent package -- the relative import raises
# `ImportError: attempted relative import with no known parent package`,
# caught here, and the absolute fallback resolves because sys.path[0] is
# then this file's own directory (scripts/), which contains
# deploy_n8n_reference_ingest.py directly.
try:
    from .deploy_n8n_reference_ingest import (
        DEFAULT_DISCORD_CHANNEL_ID,
        DEFAULT_DISCORD_GUILD_ID,
        DISCORD_REQUIRED,
        N8nClient,
        WORKFLOWS,
        build_deployment,
        credential_by_name,
        load_env,
    )
except ImportError:  # pragma: no cover - exercised when run as a script
    from deploy_n8n_reference_ingest import (
        DEFAULT_DISCORD_CHANNEL_ID,
        DEFAULT_DISCORD_GUILD_ID,
        DISCORD_REQUIRED,
        N8nClient,
        WORKFLOWS,
        build_deployment,
        credential_by_name,
        load_env,
    )

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_KEY = "korean-vernacular"
FINALIZE_NODE_NAME = "Verify Korean vernacular release finalized"
# How many of the most recent successful executions (by n8n's own summary
# `status`) to fetch full run data for, looking for one that qualifies as
# meaningful evidence. Bounded and small: this is a one-off operator check,
# not a dashboard, and each candidate costs one extra `includeData=true` GET.
MAX_EXECUTIONS_TO_INSPECT = 10


def load_local_artifact() -> dict[str, object]:
    source_path, workflow_id_env = WORKFLOWS[WORKFLOW_KEY]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("active") is not False or not source.get("nodes") or not source.get("connections"):
        raise SystemExit("Korean vernacular workflow artifact is invalid or active")
    return source


def require_client() -> tuple[N8nClient, str]:
    load_env(ROOT / ".env")
    base_url = os.environ.get("ROBINGRAPH_N8N_API_URL", "").strip()
    api_key = os.environ.get("ROBINGRAPH_N8N_API_KEY", "").strip()
    _, workflow_id_env = WORKFLOWS[WORKFLOW_KEY]
    workflow_id = os.environ.get(workflow_id_env, "").strip()
    if not base_url or not api_key:
        raise SystemExit("ROBINGRAPH_N8N_API_URL and ROBINGRAPH_N8N_API_KEY are required")
    if not workflow_id:
        raise SystemExit(
            f"{workflow_id_env} is not set; deploy the canonical workflow first "
            "(scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply)"
        )
    return N8nClient(base_url, api_key), workflow_id


def expected_deployment(client: N8nClient, source: dict[str, object]) -> dict[str, object]:
    credential_rows = client.request("GET", "/credentials?limit=100")["data"]
    neo4j = credential_by_name(
        credential_rows,
        os.environ.get("ROBINGRAPH_N8N_NEO4J_CREDENTIAL", "Neo4j"),
        "neo4jApi",
    )
    discord_required = DISCORD_REQUIRED.get(WORKFLOW_KEY, True)
    discord = None
    if any(item["type"] == "n8n-nodes-base.discord" for item in source["nodes"]):
        try:
            discord = credential_by_name(
                credential_rows,
                os.environ.get("ROBINGRAPH_N8N_DISCORD_CREDENTIAL", "Nesty API 키"),
                "discordBotApi",
            )
        except RuntimeError:
            if discord_required:
                raise
            discord = None
    return build_deployment(
        source,
        neo4j,
        discord,
        os.environ.get("ROBINGRAPH_DISCORD_GUILD_ID", DEFAULT_DISCORD_GUILD_ID),
        os.environ.get("ROBINGRAPH_DISCORD_CHANNEL_ID", DEFAULT_DISCORD_CHANNEL_ID),
        discord_required=discord_required,
    )


# Server-added fields, confirmed by a real read-only GET against the live
# canonical workflow (see the 2026-09-12 work log), that this project's
# generator/deployer never sends and that carry no execution-affecting
# meaning by themselves. Each is dropped from `actual` *only* when it is
# absent from `expected` and holds exactly this observed value -- never
# unconditionally. This is a narrow allowlist, not a general "ignore extra
# fields" rule: an earlier draft of this comparison recursively ignored
# *any* added key, which would have let a node an operator disabled in the
# n8n UI (`disabled: true`), or one with an added `onError`/`executeOnce`
# override silently changing its failure behavior, pass as "matching" --
# exactly the kind of drift this activation guard exists to catch. Every
# other field, in both `nodes` and `settings`, is compared for exact
# equality; anything not on this list is a real, meaningful difference.
_HARMLESS_SETTINGS_DEFAULTS = {"availableInMCP": False, "binaryMode": "separate"}
# `webhookId` is server-owned only for trigger nodes in this workflow. Do not
# drop it from arbitrary nodes: doing so would turn a narrow compatibility
# exception into a general-purpose bypass for future n8n node properties.
_WEBHOOK_ID_SERVER_DEFAULT_NODE_TYPES = {
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.scheduleTrigger",
}


def _normalize_node_for_comparison(
    actual_node: dict[str, object], expected_node: dict[str, object]
) -> dict[str, object]:
    normalized = dict(actual_node)
    # n8n assigns an opaque `webhookId` to trigger-capable nodes regardless
    # of whether this workflow's trigger is actually a webhook; it routes
    # nothing for a manual/schedule trigger and is never something this
    # project's deployer sets, so its value (unlike `disabled`) carries no
    # meaning to check.
    if (
        "webhookId" not in expected_node
        and expected_node.get("type") in _WEBHOOK_ID_SERVER_DEFAULT_NODE_TYPES
    ):
        normalized.pop("webhookId", None)
    # `disabled: false` (the default -- the node still runs) is dropped only
    # at that exact value. `disabled: true` is deliberately never stripped:
    # a node silently turned off in the n8n UI keeps every one of its
    # `parameters` untouched, so this is the only field that would catch it.
    if "disabled" not in expected_node and normalized.get("disabled") is False:
        normalized.pop("disabled")
    return normalized


def _normalize_settings_for_comparison(
    actual_settings: dict[str, object], expected_settings: dict[str, object]
) -> dict[str, object]:
    normalized = dict(actual_settings)
    for key, harmless_value in _HARMLESS_SETTINGS_DEFAULTS.items():
        if key not in expected_settings and normalized.get(key) == harmless_value:
            normalized.pop(key)
    return normalized


def _definition_matches(actual: dict[str, object] | None, expected: dict[str, object]) -> bool:
    """Exact match on everything except a narrow, explicit allowlist of
    observed-harmless server additions (see `_HARMLESS_SETTINGS_DEFAULTS`
    and `_normalize_node_for_comparison`). Nodes are matched by `name`
    (their content-derived `id` should already agree, but name is what a
    human reads and what every generator helper keys connections by), and
    the node *sets* must agree exactly -- not just counts -- so a swapped
    or duplicated name can never mask a genuinely missing node.
    """

    if not isinstance(actual, dict):
        return False

    actual_nodes, expected_nodes = actual.get("nodes"), expected.get("nodes")
    if not isinstance(actual_nodes, list) or not isinstance(expected_nodes, list):
        return False
    if not all(isinstance(node, dict) and isinstance(node.get("name"), str) for node in actual_nodes):
        return False
    if not all(isinstance(node, dict) and isinstance(node.get("name"), str) for node in expected_nodes):
        return False
    actual_names = [node.get("name") for node in actual_nodes]
    expected_names = [node.get("name") for node in expected_nodes]
    if (
        sorted(actual_names) != sorted(expected_names)
        or len(actual_names) != len(set(actual_names))
        or len(expected_names) != len(set(expected_names))
    ):
        return False
    expected_by_name = {node["name"]: node for node in expected_nodes}
    for actual_node in actual_nodes:
        expected_node = expected_by_name[actual_node["name"]]
        if _normalize_node_for_comparison(actual_node, expected_node) != expected_node:
            return False

    if actual.get("connections") != expected.get("connections"):
        return False

    actual_settings, expected_settings = actual.get("settings"), expected.get("settings")
    if not isinstance(actual_settings, dict) or not isinstance(expected_settings, dict):
        return False
    return _normalize_settings_for_comparison(actual_settings, expected_settings) == expected_settings


def canonical_definition_matches_local_artifact(remote: dict[str, object], expected: dict[str, object]) -> bool:
    """Compare only the fields this project's deployer writes.

    `remote` (a live `GET /workflows/{id}`) carries extra server-owned
    top-level fields (`id`, `versionId`, `createdAt`, `updatedAt`, `active`,
    `tags`, `pinData`, `meta`) that `expected` (this checkout's own
    `build_deployment` output, the exact payload the deployer would `PUT`)
    never claims to reproduce -- comparing those would always mismatch and
    tell an operator nothing. Within `nodes`/`connections`/`settings`, see
    `_definition_matches` for the narrow, explicit tolerance applied.
    """

    return _definition_matches(remote, expected)


def execution_definition_matches_expected(detail: dict[str, object], expected: dict[str, object]) -> bool:
    """True if the definition *this specific execution actually ran* is
    still the one under review -- not merely that it shares the canonical
    workflow id, which an older, since-edited success would too. `detail`
    lacking a `workflowData` snapshot at all (an older n8n Public API
    response shape, or a pruned execution) fails closed here rather than
    being treated as an unverifiable-but-acceptable match.
    """

    return _definition_matches(detail.get("workflowData"), expected)


def _as_nonnegative_int(value: object) -> int | None:
    """Strict, non-coercing count validator.

    Deliberately not `int(value or 0)`: that would silently turn a
    malformed value (a string, `None`, a negative number) into `0`, which
    this script's caller would then treat as "a real run that legitimately
    loaded nothing" instead of "the execution data here cannot be trusted".
    `bool` is explicitly excluded even though `isinstance(True, int)` is
    `True` in Python -- a stray boolean here is never a legitimate count.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def list_recent_execution_ids(client: N8nClient, workflow_id: str) -> list[str]:
    response = client.request(
        "GET",
        f"/executions?workflowId={workflow_id}&status=success&limit={MAX_EXECUTIONS_TO_INSPECT}",
    )
    if not isinstance(response, dict) or not isinstance(response.get("data"), list):
        return []
    return [
        item["id"]
        for item in response["data"]
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    ]


def finalize_evidence_from_execution(
    execution: dict[str, object], workflow_id: str, expected: dict[str, object]
) -> dict[str, object] | None:
    """Extract 'Verify Korean vernacular release finalized' output, or None.

    Every one of these must hold for the execution to count as evidence:

    - `workflowId` matches the canonical id (the cheapest, first check;
      belt-and-suspenders alongside the `?workflowId=` filter already used
      to list candidates).
    - `status` is exactly `"success"` on the execution *detail* itself, not
      only trusted from the list endpoint's `status=success` filter used to
      find candidate ids in the first place.
    - `execution_definition_matches_expected`: the definition this
      execution actually ran is still the one under review -- an older
      success from before the last edit must never count for the
      definition being activated now, even under the same workflow id.
    - `finalize_ok: true`, with `loaded_vernacular_names`/`loaded_candidates`
      both genuine non-negative integers (see `_as_nonnegative_int` --
      malformed data disqualifies, it is never coerced to zero) summing to
      more than zero. Matches what the real smoke run actually produced
      (948 Wikidata bindings -> 846 names, 102 candidates), not a trivially
      "successful" execution that found zero candidates to write (which the
      workflow's own ASSEMBLE_KOREAN_VERNACULAR_GATES already refuses with
      `ready_to_load: false` -- see generate_n8n_korean_vernacular_ingest.py
      -- but is worth guarding here too, defensively, since this reads raw
      execution data).
    - the payload's own `run_id` equals `n8n-korean-vernacular-<this
      execution's id>` (see `build_configuration_js`), confirming the
      counts genuinely belong to this execution rather than stale
      pinned/cached data under it.
    """

    execution_id = execution.get("id")
    if str(execution.get("workflowId")) != str(workflow_id):
        return None
    if execution.get("status") != "success":
        return None
    if not execution_definition_matches_expected(execution, expected):
        return None
    run_data = (
        execution.get("data", {})
        .get("resultData", {})
        .get("runData", {})
        .get(FINALIZE_NODE_NAME)
    )
    if not run_data:
        return None
    try:
        payload = run_data[-1]["data"]["main"][0][0]["json"]
    except (KeyError, IndexError, TypeError):
        return None
    if payload.get("finalize_ok") is not True:
        return None
    if payload.get("run_id") != f"n8n-korean-vernacular-{execution_id}":
        return None
    names = _as_nonnegative_int(payload.get("loaded_vernacular_names"))
    candidates = _as_nonnegative_int(payload.get("loaded_candidates"))
    if names is None or candidates is None or names + candidates <= 0:
        return None
    return {
        "execution_id": execution_id,
        "run_id": payload.get("run_id"),
        "wikidata_dataset_id": payload.get("wikidata_dataset_id"),
        "loaded_vernacular_names": names,
        "loaded_candidates": candidates,
        "started_at": execution.get("startedAt"),
    }


def find_meaningful_run_evidence(
    client: N8nClient, workflow_id: str, expected: dict[str, object]
) -> dict[str, object] | None:
    for execution_id in list_recent_execution_ids(client, workflow_id):
        detail = client.request("GET", f"/executions/{execution_id}?includeData=true")
        evidence = finalize_evidence_from_execution(detail, workflow_id, expected)
        if evidence is not None:
            return evidence
    return None


def schedule_summary(source: dict[str, object]) -> str:
    trigger = next(
        (item for item in source["nodes"] if item["type"] == "n8n-nodes-base.scheduleTrigger"),
        None,
    )
    if trigger is None:
        return "no schedule trigger found"
    expression = trigger["parameters"]["rule"]["interval"][0].get("expression", "?")
    timezone = source.get("settings", {}).get("timezone", "?")
    # Deliberately not resolved to a next-run timestamp -- see module docstring.
    return f"cron={expression!r} timezone={timezone!r} (next-run time not computed here)"


def cmd_status(_: argparse.Namespace) -> None:
    source = load_local_artifact()
    print(f"local artifact: nodes={len(source['nodes'])} active={source['active']}")
    print(f"schedule: {schedule_summary(source)}")

    client, workflow_id = require_client()
    remote = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
    if not isinstance(remote, dict) or not isinstance(remote.get("nodes"), list):
        raise SystemExit("n8n returned a malformed workflow response")
    print(f"remote workflow {workflow_id}: active={remote.get('active')} nodes={len(remote['nodes'])}")

    expected = expected_deployment(client, source)
    matches = canonical_definition_matches_local_artifact(remote, expected)
    print(f"remote definition matches reviewed local artifact: {matches}")

    evidence = find_meaningful_run_evidence(client, workflow_id, expected)
    if evidence is None:
        print(
            "no qualifying successful execution found under this canonical workflow id "
            f"(inspected up to {MAX_EXECUTIONS_TO_INSPECT} recent successes)"
        )
    else:
        print(
            "most recent meaningful successful execution: "
            f"execution={evidence['execution_id']} run={evidence['run_id']} "
            f"started_at={evidence['started_at']} "
            f"loaded_vernacular_names={evidence['loaded_vernacular_names']} "
            f"loaded_candidates={evidence['loaded_candidates']}"
        )


def cmd_activate(args: argparse.Namespace) -> None:
    source = load_local_artifact()
    client, workflow_id = require_client()
    remote = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")

    if not isinstance(remote, dict):
        raise SystemExit("n8n returned a malformed workflow response")
    if remote.get("active") is True:
        print(f"workflow {workflow_id} is already active; no-op")
        return

    expected = expected_deployment(client, source)
    if not canonical_definition_matches_local_artifact(remote, expected):
        raise SystemExit(
            "refusing to activate: the canonical remote workflow does not match the "
            "reviewed local artifact. Redeploy first: "
            "scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply"
        )

    evidence = find_meaningful_run_evidence(client, workflow_id, expected)
    if evidence is None:
        raise SystemExit(
            "refusing to activate: no successful execution with meaningful load counts was "
            f"found under canonical workflow {workflow_id}'s own execution history (inspected "
            f"up to {MAX_EXECUTIONS_TO_INSPECT} recent successes). A temporary webhook-triggered "
            "copy's execution (and its data) does not count as evidence here even if one "
            "succeeded and was observed manually -- it ran under a different, since-deleted "
            "workflow id and the Public API cannot see it under this one. An older execution "
            "that ran under a definition this workflow has since moved past also does not "
            "count -- if the definition was redeployed after the last real run, run it again "
            "first. Run the canonical workflow for real at least once, under its current "
            "definition, from the n8n UI (see the first-run checklist in "
            "docs/n8n/korean-vernacular-ingest.md) before activating its schedule."
        )
    print(
        "activation preconditions satisfied: definition matches, and execution "
        f"{evidence['execution_id']} (run {evidence['run_id']}) shows finalize_ok with "
        f"{evidence['loaded_vernacular_names']} names / {evidence['loaded_candidates']} candidates"
    )

    if not args.apply:
        print("dry-run: re-run with --apply to activate the schedule")
        return

    # Re-read immediately before the mutating request. A workflow may be
    # edited in the UI while the execution details above are being fetched;
    # without this final check a previously-valid execution could authorize
    # activation of that changed definition. (The remaining tiny API race is
    # n8n's responsibility; this Public API exposes no version precondition.)
    current = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
    if not isinstance(current, dict):
        raise SystemExit("refusing to activate: n8n returned a malformed workflow response")
    if current.get("active") is True:
        print(f"workflow {workflow_id} became active while checking; no-op")
        return
    if not canonical_definition_matches_local_artifact(current, expected):
        raise SystemExit(
            "refusing to activate: the canonical workflow changed while execution evidence was being checked"
        )

    client.request("POST", f"/workflows/{workflow_id}/activate")
    print(f"activated: workflow={workflow_id}")


def cmd_deactivate(args: argparse.Namespace) -> None:
    client, workflow_id = require_client()
    remote = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")

    if not isinstance(remote, dict):
        raise SystemExit("n8n returned a malformed workflow response")
    if remote.get("active") is False:
        print(f"workflow {workflow_id} is already inactive; no-op")
        return

    if not args.apply:
        print(f"dry-run: workflow {workflow_id} is active; re-run with --apply to deactivate")
        return

    client.request("POST", f"/workflows/{workflow_id}/deactivate")
    print(f"deactivated: workflow={workflow_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Read-only local/remote/execution-evidence report")

    activate_parser = subparsers.add_parser("activate", help="Activate the canonical schedule")
    activate_parser.add_argument(
        "--apply", action="store_true", help="Actually call the n8n API; otherwise dry-run only"
    )

    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate the canonical schedule")
    deactivate_parser.add_argument(
        "--apply", action="store_true", help="Actually call the n8n API; otherwise dry-run only"
    )

    args = parser.parse_args()
    {
        "status": cmd_status,
        "activate": cmd_activate,
        "deactivate": cmd_deactivate,
    }[args.command](args)


if __name__ == "__main__":
    main()
