"""Read-only post-deploy verifier for the public RobinGraph API.

`scripts/deploy_nas.sh verify` only asks the API container to call its own
`/health` over loopback. That confirms the process is up, but it does not
confirm that the version actually reachable through Nginx Proxy Manager at
the public domain matches the contract this checkout declares, or that it is
actually resolving real data. Three gaps in particular motivated this
script:

1. **Stale deployment**: a NAS image built before a field was added to the
   API (e.g. `LineageTaxonResponse.korean_name_status`) still serves `200`
   for every request. HTTP status alone cannot tell you the deployed
   contract is behind the current checkout -- only comparing the deployed
   `/openapi.json` (names *and* declared types), and the shape of a real
   response, against what this checkout's FastAPI app declares can.
2. **A `200` with a useless body still needs to fail**: an empty list, a
   bare `null`, or a JSON scalar are all valid JSON and would satisfy a
   naive "is this 200 and parseable" check while telling you nothing about
   the actual contract. Every stage below treats "200 but not the object
   shape we expect" as a hard failure, not something to silently skip.
3. **Two unrelated "release" fields**: `GET /health` reports
   `taxonomy_release` from the in-memory fixture corpus
   (`data/eval/v1/fixture-manifest.json`, e.g. `"fixture-avlist-2025"`) --
   the release backing `/v1/answers` and `/v1/search`. `GET
   /v1/taxa/lineage` reports `taxonomy_release` from the active AviList
   `reference-taxonomy` concept set in Neo4j (e.g. `"v2025b"`) -- a
   completely different data area (see docs/graph-database-schema.md and
   docs/current-implementation.md). These two values are never expected to
   match and must never be diffed against each other; this script reports
   both, labeled, instead of asserting equality.

Beyond the static contract, this script also runs one semantic canary: it
resolves a real, previously-confirmed Korean vernacular name end to end and
checks the *values* in the response, not just which keys are present --
`matched_by`, the resolved scientific name, and `korean_name_status` must
all be the specific values this checkout expects. A deployment that answers
with the right shape but the wrong data (e.g. a stale Neo4j snapshot, or a
name matched to the wrong species) would pass a keys-only check and must not
pass this one.

This script only issues GET requests against public, unauthenticated
endpoints. It reads no `.env*` file and needs no NAS/Neo4j/n8n credential,
so it is safe to run from any machine that can reach the public domain
(operator laptop, CI, or a NAS shell). It never mutates remote state.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://aviary.dove-nest.com"
DEFAULT_LINEAGE_NAME = "청둥오리"
DEFAULT_EXPECTED_SCIENTIFIC_NAME = "Anas platyrhynchos"
DEFAULT_EXPECTED_KOREAN_NAME_STATUS = "community-sourced"
DEFAULT_TIMEOUT = 10.0

LINEAGE_SCHEMA_NAME = "LineageTaxonResponse"

# (url, timeout) -> (http_status, raw_body_bytes). Swappable so tests never
# touch the network; see tests/test_api_deployment.py.
Fetcher = Callable[[str, float], "tuple[int, bytes]"]


def default_fetcher(url: str, timeout: float) -> tuple[int, bytes]:
    # NPM's "Block Common Exploits" preset (or an equivalent WAF rule) 403s
    # the stdlib's default `Python-urllib/x.y` User-Agent on this domain even
    # though the same GET succeeds from curl or a browser -- confirmed live
    # against https://aviary.dove-nest.com on 2026-09-12. Send an
    # identifiable, non-default one so this verifier does not report a false
    # "backend unreachable" against a perfectly healthy deployment.
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "RobinGraph-Deployment-Verifier/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 (public GET only)
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


@dataclass
class EndpointResult:
    path: str
    ok: bool
    status_code: int | None = None
    error: str | None = None
    body: object | None = None


@dataclass
class VerificationReport:
    base_url: str
    lineage_name: str
    expected_scientific_name: str
    expected_korean_name_status: str
    health: EndpointResult
    openapi: EndpointResult
    lineage: EndpointResult
    structural_errors: list[str] = field(default_factory=list)
    schema_drift: list[str] = field(default_factory=list)
    response_drift: list[str] = field(default_factory=list)
    canary_issues: list[str] = field(default_factory=list)
    process_taxonomy_release: str | None = None
    lineage_taxonomy_release: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def backend_reachable(self) -> bool:
        return self.health.ok and self.openapi.ok and self.lineage.ok

    @property
    def contract_parity_ok(self) -> bool:
        return (
            self.backend_reachable
            and not self.structural_errors
            and not self.schema_drift
            and not self.response_drift
            and not self.canary_issues
        )

    @property
    def passed(self) -> bool:
        return self.contract_parity_ok


def _fetch_endpoint(fetcher: Fetcher, base_url: str, path: str, timeout: float) -> EndpointResult:
    url = base_url.rstrip("/") + path
    try:
        status, raw = fetcher(url, timeout)
    except HTTPError as error:
        # HTTPError is also raised by some fakes in tests; default_fetcher
        # already turns it into a status code, so this only triggers for a
        # custom fetcher. Never echo the response body here.
        return EndpointResult(path=path, ok=False, status_code=error.code, error=f"HTTP {error.code}")
    except URLError as error:
        return EndpointResult(path=path, ok=False, error=f"could not reach host ({type(error.reason).__name__})")
    except TimeoutError:
        return EndpointResult(path=path, ok=False, error="request timed out")
    except OSError as error:
        return EndpointResult(path=path, ok=False, error=f"network error ({type(error).__name__})")

    if status != 200:
        return EndpointResult(path=path, ok=False, status_code=status, error=f"unexpected HTTP {status}")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return EndpointResult(path=path, ok=False, status_code=status, error="response was not valid JSON")
    return EndpointResult(path=path, ok=True, status_code=status, body=body)


def local_lineage_schema() -> dict:
    """The `LineageTaxonResponse` JSON schema this checkout's API actually declares."""

    from robingraph.api.app import create_app

    schema = create_app().openapi()
    return schema["components"]["schemas"][LINEAGE_SCHEMA_NAME]


def _property_type_signature(property_schema: object) -> object:
    """A comparable summary of a JSON-schema property's declared type(s).

    Pydantic emits `{"type": "string"}` for a required field and
    `{"anyOf": [{"type": "string"}, {"type": "null"}]}` for an optional one.
    We compare the *set* of `type` values regardless of which shape wrote
    them, so `Optional[str]` written either way still matches, but comparing
    `str` against `int` (or against a field that vanished into `type: null`
    only) is still caught.
    """

    if not isinstance(property_schema, dict):
        return None
    variants = property_schema.get("anyOf")
    if isinstance(variants, list):
        types = {variant.get("type") for variant in variants if isinstance(variant, dict)}
    else:
        types = {property_schema.get("type")}
    return frozenset(t for t in types if t is not None)


def _diff_schema_properties(local_schema: dict, deployed_schema: object) -> list[str]:
    if not isinstance(deployed_schema, dict):
        return [f"deployed OpenAPI document has no usable {LINEAGE_SCHEMA_NAME} schema"]
    local_props = local_schema.get("properties", {})
    deployed_props = deployed_schema.get("properties", {})
    if not isinstance(local_props, dict) or not isinstance(deployed_props, dict):
        return [f"deployed {LINEAGE_SCHEMA_NAME} schema has a malformed 'properties' object"]

    drift: list[str] = []
    missing = sorted(set(local_props) - set(deployed_props))
    drift.extend(f"deployed {LINEAGE_SCHEMA_NAME} schema is missing field {name!r}" for name in missing)

    # `properties` alone is not the full response contract. If a field this
    # checkout requires becomes optional in the deployed schema, callers can
    # receive a valid-looking response that omits it entirely. The live-body
    # check below catches the canary instance; this catches the broader API
    # contract regression even when that one response happens to include it.
    local_required = local_schema.get("required", [])
    deployed_required = deployed_schema.get("required", [])
    if not isinstance(local_required, list) or not isinstance(deployed_required, list):
        drift.append(f"deployed {LINEAGE_SCHEMA_NAME} schema has a malformed 'required' array")
    else:
        missing_required = sorted(set(local_required) - set(deployed_required))
        drift.extend(
            f"deployed {LINEAGE_SCHEMA_NAME} schema no longer requires field {name!r}"
            for name in missing_required
        )

    for name in sorted(set(local_props) & set(deployed_props)):
        local_type = _property_type_signature(local_props[name])
        deployed_type = _property_type_signature(deployed_props[name])
        if local_type is not None and local_type != deployed_type:
            drift.append(
                f"deployed {LINEAGE_SCHEMA_NAME}.{name} has type {set(deployed_type or ())!r}, "
                f"expected {set(local_type)!r}"
            )
    return drift


def _diff_response_properties(local_schema: dict, lineage_items: object) -> list[str]:
    if not isinstance(lineage_items, list) or not lineage_items:
        return ["lineage response has no non-empty 'lineage' array to check"]
    local_props = set(local_schema.get("properties", {}))
    drift: list[str] = []
    for index, item in enumerate(lineage_items):
        if not isinstance(item, dict):
            drift.append(f"lineage[{index}] is not an object")
            continue
        missing = sorted(local_props - set(item))
        if missing:
            label = item.get("scientific_name", f"index {index}")
            drift.append(f"lineage entry {label!r} is missing field(s): {', '.join(missing)}")
    return drift


def _validate_health_canary(health_body: object) -> list[str]:
    if not isinstance(health_body, dict):
        return ["health response is not a JSON object"]
    issues: list[str] = []
    status = health_body.get("status")
    if status != "ok":
        issues.append(f"health.status is {status!r}, expected 'ok'")
    mode = health_body.get("mode")
    if mode != "neo4j":
        issues.append(
            f"health.mode is {mode!r}, expected 'neo4j' -- the public lineage/Korean-name "
            "endpoints require the Neo4j-backed deployment, not serve-fixture"
        )
    return issues


def _validate_lineage_canary(
    lineage_body: object,
    *,
    expected_scientific_name: str,
    expected_korean_name_status: str,
) -> list[str]:
    if not isinstance(lineage_body, dict):
        return ["lineage response is not a JSON object"]

    issues: list[str] = []
    matched_by = lineage_body.get("matched_by")
    if matched_by != "korean_name":
        issues.append(f"matched_by is {matched_by!r}, expected 'korean_name' for a name= query")

    items = lineage_body.get("lineage")
    if not isinstance(items, list) or not items:
        issues.append("lineage array is missing or empty -- no taxon was actually resolved")
        return issues

    target = next((item for item in items if isinstance(item, dict) and item.get("rank") == "species"), None)
    if target is None:
        issues.append("no species-rank entry found in the resolved lineage")
        return issues

    resolved_name = target.get("scientific_name")
    if resolved_name != expected_scientific_name:
        issues.append(
            f"resolved species is {resolved_name!r}, expected {expected_scientific_name!r} -- "
            "the canary name is resolving to the wrong taxon"
        )

    if "korean_name_status" not in target:
        issues.append("resolved species entry has no korean_name_status field at all")
    else:
        status = target.get("korean_name_status")
        if status is None:
            issues.append(
                "korean_name_status is null for a name that should be community-sourced "
                "(a null status is indistinguishable from an official name in the API contract)"
            )
        elif status != expected_korean_name_status:
            issues.append(f"korean_name_status is {status!r}, expected {expected_korean_name_status!r}")

    return issues


def verify_deployment(
    base_url: str = DEFAULT_BASE_URL,
    lineage_name: str = DEFAULT_LINEAGE_NAME,
    expected_scientific_name: str = DEFAULT_EXPECTED_SCIENTIFIC_NAME,
    expected_korean_name_status: str = DEFAULT_EXPECTED_KOREAN_NAME_STATUS,
    timeout: float = DEFAULT_TIMEOUT,
    fetcher: Fetcher = default_fetcher,
    local_schema: dict | None = None,
) -> VerificationReport:
    """Check public contract parity, a live data canary, and report both release identifiers.

    Never raises for a reachable-but-wrong deployment or an unreachable
    backend -- both are reported on `VerificationReport` so a caller (CLI or
    test) decides how to fail. It only raises if `local_schema` cannot be
    computed from this checkout (a real bug in this repo, not the remote
    deployment).
    """

    schema = local_schema if local_schema is not None else local_lineage_schema()

    health = _fetch_endpoint(fetcher, base_url, "/health", timeout)
    openapi = _fetch_endpoint(fetcher, base_url, "/openapi.json", timeout)
    lineage_path = f"/v1/taxa/lineage?name={quote(lineage_name)}"
    lineage = _fetch_endpoint(fetcher, base_url, lineage_path, timeout)

    report = VerificationReport(
        base_url=_safe_display_url(base_url),
        lineage_name=lineage_name,
        expected_scientific_name=expected_scientific_name,
        expected_korean_name_status=expected_korean_name_status,
        health=health,
        openapi=openapi,
        lineage=lineage,
    )

    if health.ok:
        if isinstance(health.body, dict):
            report.process_taxonomy_release = health.body.get("taxonomy_release")
            report.notes.append(
                "health.taxonomy_release is the fixture-corpus process release used by "
                "/v1/answers and /v1/search, not the AviList reference-taxonomy release "
                "served by /v1/taxa/lineage -- the two are unrelated data areas."
            )
        report.canary_issues.extend(_validate_health_canary(health.body))

    if openapi.ok:
        deployed_schema = (
            openapi.body.get("components", {}).get("schemas", {}).get(LINEAGE_SCHEMA_NAME)
            if isinstance(openapi.body, dict)
            else None
        )
        if not isinstance(openapi.body, dict):
            report.structural_errors.append("openapi.json response is not a JSON object")
        else:
            report.schema_drift.extend(_diff_schema_properties(schema, deployed_schema))

    if lineage.ok:
        if isinstance(lineage.body, dict):
            report.lineage_taxonomy_release = lineage.body.get("taxonomy_release")
            report.response_drift.extend(_diff_response_properties(schema, lineage.body.get("lineage")))
        else:
            report.structural_errors.append("lineage response is not a JSON object")
        report.canary_issues.extend(
            _validate_lineage_canary(
                lineage.body,
                expected_scientific_name=expected_scientific_name,
                expected_korean_name_status=expected_korean_name_status,
            )
        )

    if report.process_taxonomy_release is not None and report.lineage_taxonomy_release is not None:
        report.notes.append(
            f"health reports process release {report.process_taxonomy_release!r}; "
            f"lineage reports AviList release {report.lineage_taxonomy_release!r}. "
            "A difference between these two values is expected and is not a defect by itself."
        )

    return report


def _safe_display_url(url: str) -> str:
    """Return a diagnostic-safe public URL, never echoing credentials/query.

    The verifier itself does not load or attach credentials, but an operator
    can accidentally paste a URL containing userinfo or a signed query into
    `--base-url`. Reports are commonly pasted into tickets, so strip those
    portions before retaining the URL in a report or printing it.
    """

    try:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.hostname:
            return "<invalid public API URL>"
        host = parsed.hostname
        # urlsplit.hostname removes IPv6 brackets, which must be restored in
        # a rendered authority component.
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        try:
            port = parsed.port
        except ValueError:
            return "<invalid public API URL>"
        netloc = host if port is None else f"{host}:{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except (TypeError, ValueError):
        return "<invalid public API URL>"


def _endpoint_summary(result: EndpointResult) -> dict:
    return {
        "path": result.path,
        "ok": result.ok,
        "status_code": result.status_code,
        "error": result.error,
    }


def report_to_dict(report: VerificationReport) -> dict:
    return {
        "base_url": report.base_url,
        "lineage_name": report.lineage_name,
        "expected_scientific_name": report.expected_scientific_name,
        "expected_korean_name_status": report.expected_korean_name_status,
        "health": _endpoint_summary(report.health),
        "openapi": _endpoint_summary(report.openapi),
        "lineage": _endpoint_summary(report.lineage),
        "process_taxonomy_release": report.process_taxonomy_release,
        "lineage_taxonomy_release": report.lineage_taxonomy_release,
        "structural_errors": report.structural_errors,
        "schema_drift": report.schema_drift,
        "response_drift": report.response_drift,
        "canary_issues": report.canary_issues,
        "notes": report.notes,
        "backend_reachable": report.backend_reachable,
        "contract_parity_ok": report.contract_parity_ok,
        "passed": report.passed,
    }


def _print_report(report: VerificationReport) -> None:
    print(f"RobinGraph API deployment verification: {report.base_url}")
    for result in (report.health, report.openapi, report.lineage):
        if result.ok:
            print(f"  [OK]   GET {result.path}")
        else:
            detail = f"HTTP {result.status_code}" if result.status_code else result.error
            print(f"  [FAIL] GET {result.path} ({detail})")

    if report.process_taxonomy_release is not None or report.lineage_taxonomy_release is not None:
        print(f"  health.taxonomy_release  = {report.process_taxonomy_release!r}  (fixture/process release)")
        print(f"  lineage.taxonomy_release = {report.lineage_taxonomy_release!r}  (AviList reference-taxonomy release)")

    if report.structural_errors:
        print("  Malformed responses:")
        for line in report.structural_errors:
            print(f"    - {line}")

    if report.schema_drift:
        print("  OpenAPI schema drift (deployed is behind this checkout):")
        for line in report.schema_drift:
            print(f"    - {line}")

    if report.response_drift:
        print("  Live response drift:")
        for line in report.response_drift:
            print(f"    - {line}")

    if report.canary_issues:
        print(f"  Canary check failed for name={report.lineage_name!r}:")
        for line in report.canary_issues:
            print(f"    - {line}")

    for note in report.notes:
        print(f"  note: {note}")

    print(f"  result: {'PASS' if report.passed else 'FAIL'}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ROBINGRAPH_PUBLIC_API_URL", DEFAULT_BASE_URL),
        help="Public API base URL (default: %(default)s, or $ROBINGRAPH_PUBLIC_API_URL)",
    )
    parser.add_argument(
        "--lineage-name",
        default=DEFAULT_LINEAGE_NAME,
        help="Value for the /v1/taxa/lineage?name= canary check (default: %(default)s)",
    )
    parser.add_argument(
        "--expected-scientific-name",
        default=DEFAULT_EXPECTED_SCIENTIFIC_NAME,
        help="Scientific name the canary name must resolve to (default: %(default)s)",
    )
    parser.add_argument(
        "--expected-korean-name-status",
        default=DEFAULT_EXPECTED_KOREAN_NAME_STATUS,
        help="Expected korean_name_status for the resolved species (default: %(default)s)",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = verify_deployment(
            base_url=args.base_url,
            lineage_name=args.lineage_name,
            expected_scientific_name=args.expected_scientific_name,
            expected_korean_name_status=args.expected_korean_name_status,
            timeout=args.timeout,
            fetcher=default_fetcher,
        )
    except Exception as error:  # local schema build failed: a bug in this checkout, not the remote
        print(f"error: could not build the local API contract to compare against: {type(error).__name__}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    if not report.backend_reachable:
        return 2
    if not report.contract_parity_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
