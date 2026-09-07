"""Deploy the reviewed workflow to the RobinGraph NAS through the n8n Public API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "n8n" / "robingraph-operational-ingest.json"
DEFAULT_NEO4J_URL = "http://neo4j:7474/db/neo4j/query/v2"
DEFAULT_DISCORD_GUILD_ID = "1504129603310981120"
DEFAULT_DISCORD_CHANNEL_ID = "1541317761517756436"


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
            "User-Agent": "RobinGraph n8n API deployer",
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
        raise RuntimeError(f"Expected one {kind} credential named {name!r}; found {len(matches)}")
    return {"id": str(matches[0]["id"]), "name": name}


def build_deployment(
    workflow: dict[str, object],
    neo4j_credential: dict[str, str],
    discord_credential: dict[str, str],
    neo4j_url: str,
    discord_guild_id: str,
    discord_channel_id: str,
) -> dict[str, object]:
    deployed = json.loads(json.dumps(workflow))
    deployed["name"] = "RobinGraph — native GBIF ingest to Neo4j"

    for item in deployed["nodes"]:
        name = item["name"]
        if name == "Build run configuration":
            item["parameters"]["jsCode"] = item["parameters"]["jsCode"].replace(
                "http://REPLACE_WITH_NEO4J_HOST:7474/db/neo4j/query/v2",
                neo4j_url,
            )
        elif name == "Atomic upsert to Neo4j Query API":
            parameters = item["parameters"]
            parameters["authentication"] = "predefinedCredentialType"
            parameters.pop("genericAuthType", None)
            parameters["nodeCredentialType"] = "neo4jApi"
            item["credentials"] = {"neo4jApi": neo4j_credential}
        elif name in {"Notify success", "Notify failure"}:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Update the inactive NAS workflow")
    args = parser.parse_args()
    load_env(ROOT / ".env")

    base_url = os.environ.get("ROBINGRAPH_N8N_API_URL", "").strip()
    api_key = os.environ.get("ROBINGRAPH_N8N_API_KEY", "").strip()
    workflow_id = os.environ.get("ROBINGRAPH_N8N_WORKFLOW_ID", "").strip()
    if not all((base_url, api_key, workflow_id)):
        raise SystemExit(
            "ROBINGRAPH_N8N_API_URL, ROBINGRAPH_N8N_API_KEY and ROBINGRAPH_N8N_WORKFLOW_ID are required"
        )

    client = N8nClient(base_url, api_key)
    current = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
    if current["active"]:
        raise SystemExit("Refusing to update an active workflow; deactivate it first")

    credential_rows = client.request("GET", "/credentials?limit=100")["data"]
    neo4j = credential_by_name(
        credential_rows,
        os.environ.get("ROBINGRAPH_N8N_NEO4J_CREDENTIAL", "Neo4j"),
        "neo4jApi",
    )
    discord = credential_by_name(
        credential_rows,
        os.environ.get("ROBINGRAPH_N8N_DISCORD_CREDENTIAL", "Nesty API 키"),
        "discordBotApi",
    )
    neo4j_url = os.environ.get("ROBINGRAPH_NEO4J_QUERY_URL", "").strip()
    if not neo4j_url or "REPLACE_WITH_NEO4J_HOST" in neo4j_url:
        neo4j_url = DEFAULT_NEO4J_URL
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload = build_deployment(
        source,
        neo4j,
        discord,
        neo4j_url,
        os.environ.get("ROBINGRAPH_DISCORD_GUILD_ID", DEFAULT_DISCORD_GUILD_ID),
        os.environ.get("ROBINGRAPH_DISCORD_CHANNEL_ID", DEFAULT_DISCORD_CHANNEL_ID),
    )

    if not args.apply:
        print(f"ready: workflow={workflow_id}, nodes={len(payload['nodes'])}, active={current['active']}")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path.home() / ".local" / "state" / "robingraph" / "n8n-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{workflow_id}-{stamp}.json"
    backup_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    backup_path.chmod(0o600)

    client.request("PUT", f"/workflows/{workflow_id}", payload)
    updated = client.request("GET", f"/workflows/{workflow_id}?excludePinnedData=true")
    ssh_nodes = sum(item["type"] == "n8n-nodes-base.ssh" for item in updated["nodes"])
    print(
        f"updated: workflow={updated['id']}, nodes={len(updated['nodes'])}, "
        f"ssh={ssh_nodes}, active={updated['active']}"
    )
    print(f"backup: {backup_path}")


if __name__ == "__main__":
    main()
