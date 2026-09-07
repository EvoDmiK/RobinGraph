"""Generate the reviewed RobinGraph operational-ingest n8n workflow."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n" / "robingraph-operational-ingest.json"
RUN_ID = '"n8n-{{ $execution.id }}"'


def node_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"robingraph:n8n:operational-ingest:{name}"))


def node(
    name: str,
    node_type: str,
    type_version: float | int,
    parameters: dict[str, object],
    position: tuple[int, int],
    **extra: object,
) -> dict[str, object]:
    return {
        "parameters": parameters,
        "id": node_id(name),
        "name": name,
        "type": node_type,
        "typeVersion": type_version,
        "position": list(position),
        **extra,
    }


def ssh(
    name: str,
    command: str,
    position: tuple[int, int],
    *,
    check_exit: bool = True,
) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.ssh",
        1,
        {
            "authentication": "privateKey",
            "resource": "command",
            "operation": "execute",
            "command": f'=cd "$ROBINGRAPH_APP_DIR" && uv run --locked {command}',
            "cwd": "/",
        },
        position,
        onError="continueRegularOutput",
        notes=(
            "Requires the documented Python CLI contract."
            + (
                " The SSH node returns a result object even when the remote command exits "
                "non-zero; the following IF node therefore checks code explicitly."
                if check_exit
                else " This best-effort summary must not suppress the independent notification path."
            )
        ),
    )


def exit_check(name: str, position: tuple[int, int]) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.if",
        2.2,
        {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": node_id(f"{name}:condition"),
                        "leftValue": "={{ Number($json.code ?? -1) }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        position,
    )


def discord(name: str, message: str, position: tuple[int, int]) -> dict[str, object]:
    return node(
        name,
        "n8n-nodes-base.discord",
        2,
        {
            "authentication": "webhook",
            "operation": "sendLegacy",
            "content": message,
            "options": {"username": "RobinGraph Operations", "wait": True},
        },
        position,
        onError="continueRegularOutput",
        notes="Map a Discord Webhook credential after import. The webhook URL must not be stored in this JSON.",
    )


def edge(target: str, index: int = 0) -> dict[str, object]:
    return {"node": target, "type": "main", "index": index}


def main() -> None:
    stages = [
        (
            "Acquire exclusive ingest lock — CLI required",
            f"robingraph ingest lock acquire --run-id {RUN_ID} "
            '--lock-dir "$ROBINGRAPH_INGEST_LOCK_DIR" '
            '--stale-after-seconds "$ROBINGRAPH_INGEST_LOCK_STALE_SECONDS"',
        ),
        (
            "Preflight taxonomy sources — CLI required",
            f"robingraph ingest preflight --run-id {RUN_ID} --scope taxonomy "
            '--registry "$ROBINGRAPH_SOURCE_REGISTRY" --approval-manifest "$ROBINGRAPH_APPROVAL_MANIFEST" '
            "--require-enabled --require-policy allowed --require-approved-release",
        ),
        (
            "Preflight observation sources — CLI required",
            f"robingraph ingest preflight --run-id {RUN_ID} --scope observations "
            '--registry "$ROBINGRAPH_SOURCE_REGISTRY" --approval-manifest "$ROBINGRAPH_APPROVAL_MANIFEST" '
            "--require-enabled --require-policy allowed --require-approved-release",
        ),
        (
            "Preflight document and media sources — CLI required",
            f"robingraph ingest preflight --run-id {RUN_ID} --scope documents-media "
            '--registry "$ROBINGRAPH_SOURCE_REGISTRY" --approval-manifest "$ROBINGRAPH_APPROVAL_MANIFEST" '
            "--require-enabled --require-policy allowed --require-approved-release",
        ),
        (
            "Fetch immutable approved releases — CLI required",
            f"robingraph ingest fetch --run-id {RUN_ID}",
        ),
        ("Normalize to staging Parquet — CLI required", f"robingraph ingest normalize --run-id {RUN_ID}"),
        ("Validate and quarantine — CLI required", f"robingraph ingest validate --run-id {RUN_ID}"),
        ("Resolve taxonomy — CLI required", f"robingraph ingest resolve --run-id {RUN_ID}"),
        ("Dedupe without deletion — CLI required", f"robingraph ingest dedupe --run-id {RUN_ID}"),
        ("Embed allowed chunks only — CLI required", f"robingraph ingest embed --run-id {RUN_ID}"),
        ("Idempotent candidate graph load — CLI required", f"robingraph ingest load --run-id {RUN_ID}"),
        ("Verify candidate and quality gates — CLI required", f"robingraph ingest verify --run-id {RUN_ID}"),
        ("Activate verified release atomically — CLI required", f"robingraph ingest activate --run-id {RUN_ID}"),
    ]

    nodes: list[dict[str, object]] = [
        node("Manual Trigger", "n8n-nodes-base.manualTrigger", 1, {}, (-900, -120)),
        node(
            "Schedule Trigger — daily 02:00 KST",
            "n8n-nodes-base.scheduleTrigger",
            1.2,
            {"rule": {"interval": [{"field": "cronExpression", "expression": "0 2 * * *"}]}},
            (-900, 120),
        ),
    ]

    connections: dict[str, dict[str, list[list[dict[str, object]]]]] = {
        "Manual Trigger": {"main": [[edge(stages[0][0])]]},
        "Schedule Trigger — daily 02:00 KST": {"main": [[edge(stages[0][0])]]},
    }

    for index, (stage_name, command) in enumerate(stages):
        x = -600 + index * 480
        check_name = f"Exit code 0? — {stage_name.split(' —')[0]}"
        nodes.append(ssh(stage_name, command, (x, 0)))
        nodes.append(exit_check(check_name, (x + 240, 0)))
        connections[stage_name] = {"main": [[edge(check_name)]]}

        success_target = stages[index + 1][0] if index + 1 < len(stages) else "Build success summary — CLI required"
        failure_target = "Notify lock not acquired" if index == 0 else "Build redacted failure summary — CLI required"
        connections[check_name] = {"main": [[edge(success_target)], [edge(failure_target)]]}

    summary_x = -600 + len(stages) * 480
    nodes.extend(
        [
            ssh(
                "Build success summary — CLI required",
                f"robingraph ingest summarize --run-id {RUN_ID} --status succeeded --redacted",
                (summary_x, -180),
                check_exit=False,
            ),
            discord(
                "Notify success",
                "={{ '✅ **RobinGraph ingest succeeded**\\nRun: n8n-' + $execution.id + '\\n' + "
                "String($json.stdout || 'Inspect the redacted run manifest for counts.').slice(0, 1700) }}",
                (summary_x + 240, -180),
            ),
            ssh(
                "Build redacted failure summary — CLI required",
                f"robingraph ingest summarize --run-id {RUN_ID} --status failed --redacted",
                (summary_x, 240),
                check_exit=False,
            ),
            discord(
                "Notify failure or blocked preflight",
                (
                    "={{ '❌ **RobinGraph ingest blocked or failed**\\nRun: n8n-' + $execution.id + '\\n' + "
                    "String($json.stdout || 'Ingest stopped before activation. Inspect the n8n execution and "
                    "redacted run manifest.').slice(0, 1700) }}"
                ),
                (summary_x + 240, 240),
            ),
            discord(
                "Notify lock not acquired",
                "={{ '⚠️ **RobinGraph ingest did not start**\\nRun: n8n-' + $execution.id + "
                "'\\nThe exclusive lock was not acquired. No owned lock will be released by this execution.' }}",
                (summary_x, 480),
            ),
            ssh(
                "Release owned ingest lock — CLI required",
                f"robingraph ingest lock release --run-id {RUN_ID} --lock-dir \"$ROBINGRAPH_INGEST_LOCK_DIR\"",
                (summary_x + 520, 20),
            ),
            exit_check("Exit code 0? — Release owned ingest lock", (summary_x + 760, 20)),
            discord(
                "Notify lock release failure",
                "={{ '🚨 **RobinGraph ingest lock cleanup failed**\\nRun: n8n-' + $execution.id + "
                "'\\nThe run-owned lock could not be released. Inspect the lock audit record before another run.' }}",
                (summary_x + 1000, 220),
            ),
            node("Finished", "n8n-nodes-base.noOp", 1, {}, (summary_x + 1240, 20)),
        ]
    )

    connections.update(
        {
            "Build success summary — CLI required": {"main": [[edge("Notify success")]]},
            "Notify success": {"main": [[edge("Release owned ingest lock — CLI required")]]},
            "Build redacted failure summary — CLI required": {
                "main": [[edge("Notify failure or blocked preflight")]]
            },
            "Notify failure or blocked preflight": {
                "main": [[edge("Release owned ingest lock — CLI required")]]
            },
            "Notify lock not acquired": {"main": [[edge("Finished")]]},
            "Release owned ingest lock — CLI required": {
                "main": [[edge("Exit code 0? — Release owned ingest lock")]]
            },
            "Exit code 0? — Release owned ingest lock": {
                "main": [[edge("Finished")], [edge("Notify lock release failure")]]
            },
            "Notify lock release failure": {"main": [[edge("Finished")]]},
        }
    )

    workflow = {
        "id": node_id("workflow-id"),
        "name": "RobinGraph — reviewed operational ingest (inactive until approvals and CLI exist)",
        "nodes": nodes,
        "pinData": {},
        "connections": connections,
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "timezone": "Asia/Seoul",
            "saveManualExecutions": True,
            "saveExecutionProgress": True,
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "none",
            "callerPolicy": "workflowsFromSameOwner",
            "concurrency": 1,
        },
        "versionId": node_id("workflow-version"),
        "meta": {"templateCredsSetupCompleted": False},
        "tags": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
