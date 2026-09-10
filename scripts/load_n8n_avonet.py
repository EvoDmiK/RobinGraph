"""Validate AVONET and load it through a temporary authenticated n8n gateway.

The XLSX reader opens only the selected species-mean worksheet. This avoids the
workbook-wide expansion that exhausted the NAS n8n worker while retaining the
pinned source hash and the import artifact's normalization contract. Remote
writes require ``--apply``. Temporary n8n resources are removed afterward.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import secrets
import tempfile
from typing import Iterator
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

try:
    from .deploy_n8n_reference_ingest import N8nClient, load_env
    from .generate_n8n_avonet_ingest import BATCH_CYPHER, FINALIZE_CYPHER, configuration
    from .generate_n8n_reference_ingest import code, edge, node
except ImportError:
    from deploy_n8n_reference_ingest import N8nClient, load_env
    from generate_n8n_avonet_ingest import BATCH_CYPHER, FINALIZE_CYPHER, configuration
    from generate_n8n_reference_ingest import code, edge, node


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / ".cache" / "avonet-34480856.xlsx"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
FAIL_CYPHER = (
    "MATCH (run:IngestionRun {id:$run_id}) WHERE run.status='loading' "
    "SET run.status='failed', run.failed_at=datetime(), "
    "run.failure_reason='verified_avonet_batch_loader_failed' "
    "RETURN run.id AS failed_run_id, run.status AS status"
)


def _tag(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_source(path: Path, url: str) -> Path:
    """Download the pinned source only when the cache path is absent."""

    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "RobinGraph verified AVONET loader"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with urlopen(request, timeout=180) as response:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def _worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    with archive.open("xl/workbook.xml") as stream:
        workbook = ET.parse(stream).getroot()
    relationship_id = None
    for sheet in workbook.iter(_tag(SHEET_NS, "sheet")):
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib.get(_tag(REL_NS, "id"))
            break
    if relationship_id is None:
        raise ValueError(f"Worksheet not found: {sheet_name}")

    with archive.open("xl/_rels/workbook.xml.rels") as stream:
        relationships = ET.parse(stream).getroot()
    for relationship in relationships.iter(_tag(PACKAGE_REL_NS, "Relationship")):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib["Target"].lstrip("/")
            if target.startswith("xl/"):
                return posixpath.normpath(target)
            return posixpath.normpath(posixpath.join("xl", target))
    raise ValueError(f"Worksheet relationship not found: {relationship_id}")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        stream = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    values: list[str] = []
    with stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == _tag(SHEET_NS, "si"):
                values.append("".join(part.text or "" for part in element.iter(_tag(SHEET_NS, "t"))))
                element.clear()
    return values


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    if not letters:
        raise ValueError(f"Invalid cell reference: {reference}")
    value = 0
    for character in letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _cell_value(cell: ET.Element, shared: list[str]) -> str | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(part.text or "" for part in cell.iter(_tag(SHEET_NS, "t")))
    value = cell.find(_tag(SHEET_NS, "v"))
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        index = int(value.text)
        if index < 0 or index >= len(shared):
            raise ValueError(f"Shared string index out of range: {index}")
        return shared[index]
    if cell_type == "b":
        return "TRUE" if value.text == "1" else "FALSE"
    return value.text


def iter_worksheet_rows(path: Path, sheet_name: str) -> Iterator[tuple[int, dict[str, str | None]]]:
    """Yield header-keyed rows without expanding unrelated XLSX worksheets."""

    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        worksheet_path = _worksheet_path(archive, sheet_name)
        headers: list[str | None] | None = None
        with archive.open(worksheet_path) as stream:
            for _, row in ET.iterparse(stream, events=("end",)):
                if row.tag != _tag(SHEET_NS, "row"):
                    continue
                row_number = int(row.attrib.get("r", "0"))
                cells = {
                    _column_index(cell.attrib.get("r", "")): _cell_value(cell, shared)
                    for cell in row.findall(_tag(SHEET_NS, "c"))
                }
                if headers is None:
                    last = max(cells, default=-1)
                    headers = [cells.get(index) for index in range(last + 1)]
                    if not headers or any(header is None for header in headers):
                        raise ValueError("AVONET header row is empty or sparse")
                elif cells:
                    yield row_number, {
                        str(header): cells.get(index)
                        for index, header in enumerate(headers)
                        if header is not None
                    }
                row.clear()


def _text(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return None if not rendered or rendered == "NA" else rendered


def _positive_number(value: str, field: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid measurement: {field}") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"Invalid measurement: {field}")
    return number


def normalize_row(
    raw: dict[str, object], row_number: int, config: dict[str, object]
) -> dict[str, object]:
    scientific_name = _text(raw.get("Species1"))
    if scientific_name is None:
        raise ValueError(f"Missing species identity at row {row_number}")
    if raw.get("Inference") not in ("YES", "NO"):
        raise ValueError(f"Invalid inference flag at row {row_number}")
    try:
        sample_number = float(str(raw.get("Total.individuals")))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid sample size at row {row_number}") from error
    if not math.isfinite(sample_number) or sample_number < 0 or not sample_number.is_integer():
        raise ValueError(f"Invalid sample size at row {row_number}")

    inferred_raw = _text(raw.get("Traits.inferred"))
    inferred = {part.strip().lower() for part in (inferred_raw or "").split(";")}
    profile_id = "avonet:" + str(config["release"]) + ":" + quote(
        scientific_name, safe="-_.!~*'()"
    )
    profile: dict[str, object] = {
        "id": profile_id,
        "scientific_name": scientific_name,
        "sequence": _text(raw.get("Sequence")),
        "row_number": row_number,
        "source_uri": f"{config['url']}#sheet={config['sheet']}&row={row_number}",
        "inference_raw": raw["Inference"],
        "inferred_fields_raw": inferred_raw,
        "reference_species": _text(raw.get("Reference.species")),
        "avibase_id": _text(raw.get("Avibase.ID1")),
        "sample_size": int(sample_number),
        "mass_source": _text(raw.get("Mass.Source")),
        "mass_references": _text(raw.get("Mass.Refs.Other")),
        "claims": [],
    }
    claims: list[dict[str, object]] = profile["claims"]  # type: ignore[assignment]
    for field, trait, unit, inferred_name in config["fields"]:  # type: ignore[assignment]
        if field not in raw:
            raise ValueError(f"Missing required column: {field}")
        value = _text(raw[field])
        if value is None:
            continue
        value_num = None
        value_text = None
        if unit:
            value_num = _positive_number(value, field)
        elif field == "Habitat.Density":
            value_text = {"1": "dense", "2": "semi_open", "3": "open"}.get(value)
            if value_text is None:
                raise ValueError(f"Invalid habitat density code at row {row_number}")
        else:
            value_text = value
        claims.append(
            {
                "id": profile_id + ":" + trait,
                "trait_name": trait,
                "source_field": field,
                "value_num": value_num,
                "value_text": value_text,
                "unit": unit,
                "raw_value": value,
                "inferred": bool(inferred_name) and str(inferred_name).lower() in inferred,
                "evidence_kind": "literature_dataset",
                "summary_statistic": "species_mean" if unit else "species_category",
            }
        )
    if not claims:
        raise ValueError(f"Empty trait profile at row {row_number}")
    return profile


def iter_profiles(path: Path, config: dict[str, object]) -> Iterator[dict[str, object]]:
    for row_number, row in iter_worksheet_rows(path, str(config["sheet"])):
        yield normalize_row(row, row_number, config)


def validate_source(path: Path, config: dict[str, object]) -> dict[str, int | str]:
    actual_hash = file_sha256(path)
    if actual_hash != config["sha256"]:
        raise ValueError("AVONET snapshot SHA-256 mismatch")
    seen: set[str] = set()
    rows = 0
    claims = 0
    for profile in iter_profiles(path, config):
        name = str(profile["scientific_name"])
        if name in seen:
            raise ValueError(f"Duplicate species identity: {name}")
        seen.add(name)
        rows += 1
        claims += len(profile["claims"])  # type: ignore[arg-type]
    if rows != config["expected_rows"]:
        raise ValueError(f"AVONET row count mismatch: {rows}")
    if claims != config["expected_source_claims"]:
        raise ValueError(f"AVONET source claim count mismatch: {claims}")
    return {"sha256": actual_hash, "source_rows": rows, "source_claims": claims}


class TemporaryGateway:
    def __init__(self, client: N8nClient, secret: str, paths: dict[str, str], workflow_id: str,
                 credential_ids: list[str]) -> None:
        self.client = client
        self.secret = secret
        self.paths = paths
        self.workflow_id = workflow_id
        self.credential_ids = credential_ids
        self.active = False

    def activate(self) -> None:
        self.client.request("POST", f"/workflows/{self.workflow_id}/activate", {})
        self.active = True

    def post(self, operation: str, payload: dict[str, object]) -> dict[str, object]:
        public_base = self.client.base_url.rsplit("/api/v1", 1)[0]
        request = Request(
            f"{public_base}/webhook/{self.paths[operation]}",
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "RobinGraph verified AVONET loader",
                "X-RobinGraph-Batch-Key": self.secret,
            },
            method="POST",
        )
        with urlopen(request, timeout=300) as response:
            body = json.loads(response.read())
        if isinstance(body, list):
            if len(body) != 1:
                raise RuntimeError(f"{operation} returned an invalid item count")
            body = body[0]
        status_code = int(body.get("statusCode", 0))
        response_body = body.get("body", body)
        errors = response_body.get("errors", []) if isinstance(response_body, dict) else []
        if status_code != 202 or errors:
            message = errors[0].get("message") if errors else "unexpected Neo4j Query API response"
            raise RuntimeError(f"{operation} failed (HTTP {status_code}): {message}")
        data = response_body.get("data", {})
        values = (data.get("values") or [[]])[0]
        return dict(zip(data.get("fields", []), values))

    def close(self) -> list[str]:
        errors: list[str] = []
        if self.active:
            try:
                self.client.request("POST", f"/workflows/{self.workflow_id}/deactivate", {})
            except Exception as error:  # cleanup must continue
                errors.append(f"deactivate workflow: {error}")
        try:
            self.client.request("DELETE", f"/workflows/{self.workflow_id}")
        except Exception as error:
            errors.append(f"delete workflow: {error}")
        for credential_id in self.credential_ids:
            try:
                self.client.request("DELETE", f"/credentials/{credential_id}")
            except Exception as error:
                errors.append(f"delete credential: {error}")
        return errors


def create_gateway(
    client: N8nClient,
    database: str,
    username: str,
    password: str,
    neo4j_http_url: str = "http://neo4j:7474",
) -> TemporaryGateway:
    suffix = secrets.token_hex(12)
    secret = secrets.token_urlsafe(32)
    credential_ids: list[str] = []
    workflow_id = ""
    try:
        header = client.request(
            "POST", "/credentials",
            {"name": f"RobinGraph temporary AVONET loader {suffix}", "type": "httpHeaderAuth",
             "data": {"name": "X-RobinGraph-Batch-Key", "value": secret}},
        )
        credential_ids.append(str(header["id"]))
        basic = client.request(
            "POST", "/credentials",
            {"name": f"RobinGraph temporary AVONET Neo4j API {suffix}", "type": "httpBasicAuth",
             "data": {"user": username, "password": password}},
        )
        credential_ids.append(str(basic["id"]))
        operations = {"batch": BATCH_CYPHER, "finalize": FINALIZE_CYPHER, "fail": FAIL_CYPHER}
        nodes: list[dict[str, object]] = []
        connections: dict[str, object] = {}
        paths: dict[str, str] = {}
        for index, (operation, statement) in enumerate(operations.items()):
            path = f"robingraph-avonet-{operation}-{suffix}"
            paths[operation] = path
            trigger = f"{operation} webhook"
            unwrap = f"{operation} payload"
            query = f"{operation} query"
            nodes.append(node(trigger, "n8n-nodes-base.webhook", 2, {
                "httpMethod": "POST", "path": path, "authentication": "headerAuth",
                "responseMode": "lastNode", "options": {},
            }, (-600, index * 220), webhookId=path,
                credentials={"httpHeaderAuth": {"id": header["id"], "name": header["name"]}}))
            nodes.append(code(unwrap, "const body=$input.first().json.body;if(!body||typeof body!=='object')throw new Error('JSON object body required');return [{json:body}];", (-350, index * 220)))
            nodes.append(node(query, "n8n-nodes-base.httpRequest", 4.4, {
                "method": "POST",
                "url": f"{neo4j_http_url.rstrip('/')}/db/{quote(database, safe='')}/query/v2",
                "authentication": "genericCredentialType", "genericAuthType": "httpBasicAuth",
                "sendHeaders": True,
                "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
                "sendBody": True, "contentType": "json", "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ statement: " + json.dumps(statement) + ", parameters: $json, txMetadata: { app: 'RobinGraph verified AVONET loader', run_id: $json.run_id }, maxExecutionTime: 240 }) }}",
                "options": {"response": {"response": {"fullResponse": True, "neverError": True,
                                                         "responseFormat": "json"}}, "timeout": 270000},
            }, (-100, index * 220),
                credentials={"httpBasicAuth": {"id": basic["id"], "name": basic["name"]}},
                onError="continueRegularOutput"))
            connections[trigger] = {"main": [[edge(unwrap)]]}
            connections[unwrap] = {"main": [[edge(query)]]}
        workflow = client.request("POST", "/workflows", {
            "name": f"RobinGraph temporary verified AVONET load {suffix}",
            "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1", "timezone": "Asia/Seoul",
                         "saveDataSuccessExecution": "none", "saveDataErrorExecution": "all"},
        })
        workflow_id = str(workflow["id"])
        return TemporaryGateway(client, secret, paths, workflow_id, credential_ids)
    except Exception:
        if workflow_id:
            try:
                client.request("DELETE", f"/workflows/{workflow_id}")
            except Exception:
                pass
        for credential_id in credential_ids:
            try:
                client.request("DELETE", f"/credentials/{credential_id}")
            except Exception:
                pass
        raise


def _load_batch(gateway: TemporaryGateway, config: dict[str, object], run_id: str,
                retrieved_at: str, profiles: list[dict[str, object]], totals: dict[str, int],
                batch_index: int, batch_count: int) -> None:
    result = gateway.post("batch", {
        **config, "run_id": run_id, "retrieved_at": retrieved_at,
        "batch_index": batch_index, "batch_count": batch_count, "profiles": profiles,
    })
    loaded_profiles = int(result.get("loaded_profiles", -1))
    loaded_claims = int(result.get("loaded_claims", -1))
    loaded_candidates = int(result.get("loaded_candidates", -1))
    matched_profiles = int(result.get("matched_profiles", -1))
    expected_claims = int(result.get("expected_claims", -1))
    if (result.get("batch_index") != batch_index or result.get("batch_count") != batch_count or
            loaded_profiles != len(profiles) or loaded_claims != expected_claims or
            matched_profiles + loaded_candidates != len(profiles)):
        raise RuntimeError(f"Invalid AVONET batch acknowledgement: {batch_index}")
    totals["loaded_profiles"] += loaded_profiles
    totals["loaded_claims"] += loaded_claims
    totals["loaded_candidates"] += loaded_candidates
    totals["matched_profiles"] += matched_profiles
    print(f"avonet_batch={batch_index + 1}/{batch_count}", flush=True)


def load_remote(path: Path, config: dict[str, object]) -> dict[str, object]:
    required = ["ROBINGRAPH_N8N_API_URL", "ROBINGRAPH_N8N_API_KEY", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Missing required environment settings: " + ", ".join(missing))
    client = N8nClient(os.environ["ROBINGRAPH_N8N_API_URL"], os.environ["ROBINGRAPH_N8N_API_KEY"])
    gateway = create_gateway(
        client,
        os.environ.get("NEO4J_DATABASE", "neo4j"),
        os.environ["NEO4J_USERNAME"],
        os.environ["NEO4J_PASSWORD"],
        os.environ.get("ROBINGRAPH_NEO4J_HTTP_URL", "http://neo4j:7474"),
    )
    run_id = "avonet:verified-batch:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ":" + secrets.token_hex(4)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    batch_size = int(config["batch_size"])
    batch_count = math.ceil(int(config["expected_rows"]) / batch_size)
    totals = {"loaded_profiles": 0, "loaded_claims": 0, "loaded_candidates": 0,
              "matched_profiles": 0}
    current: list[dict[str, object]] = []
    primary_error: Exception | None = None
    try:
        gateway.activate()
        for profile in iter_profiles(path, config):
            profile["profile_json"] = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
            current.append(profile)
            if len(current) < batch_size:
                continue
            _load_batch(gateway, config, run_id, retrieved_at, current, totals,
                        totals["loaded_profiles"] // batch_size, batch_count)
            current = []
        if current:
            _load_batch(gateway, config, run_id, retrieved_at, current, totals,
                        totals["loaded_profiles"] // batch_size, batch_count)
        expected = {
            "loaded_profiles": int(config["expected_rows"]),
            "loaded_claims": int(config["expected_loaded_claims"]),
            "loaded_candidates": int(config["expected_mapping_candidates"]),
            "matched_profiles": int(config["expected_matched_profiles"]),
        }
        if totals != expected:
            raise RuntimeError(f"AVONET remote quality gate mismatch: {totals}")
        finalized = gateway.post("finalize", {
            **config, **totals, "run_id": run_id, "retrieved_at": retrieved_at,
        })
        if (finalized.get("finalized_run_id") != run_id or
                finalized.get("active_release") != config["release"] or
                finalized.get("status") != "succeeded"):
            raise RuntimeError("AVONET finalization did not acknowledge the verified run")
        return {"run_id": run_id, **totals, "active_release": finalized["active_release"]}
    except Exception as error:
        primary_error = error
        if gateway.active:
            try:
                gateway.post("fail", {"run_id": run_id})
            except Exception:
                pass
        raise
    finally:
        cleanup_errors = gateway.close()
        if cleanup_errors and primary_error is None:
            raise RuntimeError("Temporary n8n resource cleanup failed: " + "; ".join(cleanup_errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="Pinned AVONET XLSX cache path; downloaded when absent")
    parser.add_argument("--apply", action="store_true",
                        help="Load verified batches through a temporary authenticated n8n workflow")
    arguments = parser.parse_args()
    config = configuration()
    source = ensure_source(arguments.source.resolve(), str(config["url"]))
    summary = validate_source(source, config)
    print(json.dumps({"status": "validated", **summary}, ensure_ascii=False), flush=True)
    if not arguments.apply:
        print("ready-local: use --apply for remote n8n/Neo4j writes")
        return
    load_env(ROOT / ".env")
    result = load_remote(source, config)
    print(json.dumps({"status": "success", **result}, ensure_ascii=False), flush=True)
    print("temporary_n8n_gateway_removed", flush=True)


if __name__ == "__main__":
    main()
