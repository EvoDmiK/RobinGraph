"""Validate or deploy the RobinGraph reference-ingest workflow through the n8n API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "n8n" / "robingraph-reference-ingest.json"
WORKFLOWS = {
    "reference": (SOURCE, "ROBINGRAPH_N8N_REFERENCE_WORKFLOW_ID"),
    "avonet": (ROOT / "n8n" / "robingraph-avonet-ingest.json", "ROBINGRAPH_N8N_AVONET_WORKFLOW_ID"),
    "korean-vernacular": (
        ROOT / "n8n" / "robingraph-korean-vernacular-ingest.json",
        "ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID",
    ),
}
DEFAULT_DISCORD_GUILD_ID = "1504129603310981120"
DEFAULT_DISCORD_CHANNEL_ID = "1541317761517756436"
# Whether a workflow's Discord notification nodes must have a resolvable
# credential before this script will treat it as ready to deploy. Missing
# from this dict means "required" (the pre-existing, still-in-force
# contract for "reference"; see test_reference_deployment.py). The Korean
# vernacular pipeline's notifications are explicitly optional (see
# docs/n8n/korean-vernacular-ingest.md) -- a missing Discord credential must
# never block generation, the read-only `--remote` precheck, or `--apply`;
# the Discord node itself is `onError: continueRegularOutput`, so an
# unconfigured notification only fails that one node at run time.
DISCORD_REQUIRED = {"korean-vernacular": False}


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


class N8nClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-N8N-API-KEY": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RobinGraph n8n reference workflow deployer",
        }

    def request(self, method: str, path: str, body: object | None = None) -> object:
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=encoded,
            headers=self.headers,
            method=method,
        )
        with urlopen(request, timeout=60) as response:
            raw = response.read()
        return json.loads(raw) if raw else None


def credential_by_name(credentials: list[dict[str, object]], name: str, kind: str) -> dict[str, str]:
    matches = [item for item in credentials if item.get("name") == name and item.get("type") == kind]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {kind} credential matching the configured name; found {len(matches)}. Configure a saved credential name, not a token.")
    return {"id": str(matches[0]["id"]), "name": name}


def build_deployment(
    workflow: dict[str, object],
    neo4j_credential: dict[str, str],
    discord_credential: dict[str, str] | None,
    discord_guild_id: str,
    discord_channel_id: str,
    *,
    discord_required: bool = True,
) -> dict[str, object]:
    deployed = json.loads(json.dumps(workflow))
    deployed["name"] = str(deployed["name"]).removesuffix(" (inactive until verified)")
    for item in deployed["nodes"]:
        if item["type"] == "n8n-nodes-neo4j.neo4j":
            item["credentials"] = {"neo4jApi": neo4j_credential}
        elif item["type"] == "n8n-nodes-base.discord":
            if discord_credential is None:
                if not discord_required:
                    # Leave the node in its pre-deploy template shape (webhook
                    # auth, no credential): it imports fine and simply needs
                    # someone to finish wiring the credential in the n8n UI
                    # before it can actually send -- exactly the
                    # `meta.templateCredsSetupCompleted: False` contract the
                    # rest of this workflow's nodes already rely on.
                    continue
                raise ValueError("Discord credential is required for a workflow with notification nodes")
            content = item["parameters"]["content"]
            item["parameters"] = {
                "resource": "message",
                "guildId": {"__rl": True, "value": discord_guild_id, "mode": "list"},
                "channelId": {"__rl": True, "value": discord_channel_id, "mode": "list"},
                "content": content,
                "options": {},
            }
            item["credentials"] = {"discordBotApi": discord_credential}

    settings = dict(deployed["settings"])
    settings.pop("concurrency", None)
    return {
        "name": deployed["name"],
        "nodes": deployed["nodes"],
        "connections": deployed["connections"],
        "settings": settings,
    }


def write_backup(workflow_id: str, current: object) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path.home() / ".local" / "state" / "robingraph" / "n8n-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"reference-{workflow_id}-{stamp}.json"
    backup_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    backup_path.chmod(0o600)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", choices=WORKFLOWS, default="reference")
    parser.add_argument("--remote", action="store_true", help="Check NAS credentials and inactive workflow state")
    parser.add_argument("--apply", action="store_true", help="Create or update the inactive NAS workflow")
    args = parser.parse_args()
    load_env(ROOT / ".env")

    source_path, workflow_id_env = WORKFLOWS[args.workflow]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("active") is not False or not source.get("nodes") or not source.get("connections"):
        raise SystemExit("Reference workflow artifact is invalid or active")
    if not args.remote and not args.apply:
        print(
            f"ready-local: nodes={len(source['nodes'])}, active={source['active']}; "
            "use --remote to check NAS or --apply to deploy"
        )
        return

    base_url = os.environ.get("ROBINGRAPH_N8N_API_URL", "").strip()
    api_key = os.environ.get("ROBINGRAPH_N8N_API_KEY", "").strip()
    workflow_id = os.environ.get(workflow_id_env, "").strip()
    if not base_url or not api_key:
        raise SystemExit("ROBINGRAPH_N8N_API_URL and ROBINGRAPH_N8N_API_KEY are required")

    client = N8nClient(base_url, api_key)
    current = None
    if workflow_id:
        current = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
        if current["active"]:
            raise SystemExit("Refusing to update an active workflow; deactivate it first")

    credential_rows = client.request("GET", "/credentials?limit=100")["data"]
    neo4j = credential_by_name(
        credential_rows,
        os.environ.get("ROBINGRAPH_N8N_NEO4J_CREDENTIAL", "Neo4j"),
        "neo4jApi",
    )
    discord_required = DISCORD_REQUIRED.get(args.workflow, True)
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
            # Optional for this workflow: proceed without a Discord
            # credential rather than failing the whole read-only precheck
            # or deploy over an unconfigured notification channel.
            discord = None
    payload = build_deployment(
        source,
        neo4j,
        discord,
        os.environ.get("ROBINGRAPH_DISCORD_GUILD_ID", DEFAULT_DISCORD_GUILD_ID),
        os.environ.get("ROBINGRAPH_DISCORD_CHANNEL_ID", DEFAULT_DISCORD_CHANNEL_ID),
        discord_required=discord_required,
    )

    if not args.apply:
        target = workflow_id or "new workflow"
        state = current["active"] if current else False
        print(f"ready-remote: workflow={target}, nodes={len(payload['nodes'])}, active={state}")
        return

    if current is None:
        updated = client.request("POST", "/workflows", payload)
        print(f"created: workflow={updated['id']}, nodes={len(updated['nodes'])}, active={updated['active']}")
        print(f"set {workflow_id_env}={updated['id']} in the Git-ignored .env")
        return

    backup_path = write_backup(workflow_id, current)
    client.request("PUT", f"/workflows/{workflow_id}", payload)
    updated = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
    print(
        f"updated: workflow={updated['id']}, nodes={len(updated['nodes'])}, "
        f"active={updated['active']}"
    )
    print(f"backup: {backup_path}")


if __name__ == "__main__":
    main()
