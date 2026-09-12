from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts.verify_api_deployment import (
    default_fetcher,
    local_lineage_schema,
    main,
    parse_args,
    report_to_dict,
    verify_deployment,
)

LOCAL_SCHEMA = local_lineage_schema()

HEALTH_BODY = json.dumps({"status": "ok", "mode": "neo4j", "taxonomy_release": "fixture-avlist-2025"}).encode()

CURRENT_LINEAGE_ITEM = {
    "taxon_id": "avilist-taxon:v2025b:544",
    "rank": "species",
    "scientific_name": "Anas platyrhynchos",
    "authority": "Linnaeus, C, 1758",
    "korean_name": "청둥오리",
    "korean_name_status": "community-sourced",
}

STALE_LINEAGE_ITEM = {
    key: value for key, value in CURRENT_LINEAGE_ITEM.items() if key != "korean_name_status"
}


def _lineage_body_bytes(items: list) -> bytes:
    return json.dumps(
        {
            "query_name": "청둥오리",
            "query_scientific_name": "Anas platyrhynchos",
            "resolved_query_scientific_name": "Anas platyrhynchos",
            "matched_by": "korean_name",
            "taxonomy_source": "AviList",
            "taxonomy_release": "v2025b",
            "concept_set_id": "rg:concept-set:avilist-v2025b",
            "lineage": items,
        }
    ).encode()


def _lineage_body(item: dict, **overrides) -> bytes:
    payload = json.loads(_lineage_body_bytes([item]))
    payload.update(overrides)
    return json.dumps(payload).encode()


def _openapi_body(*, include_status_field: bool, status_type: str | None = None) -> bytes:
    properties = dict(LOCAL_SCHEMA["properties"])
    if not include_status_field:
        properties.pop("korean_name_status", None)
    elif status_type is not None:
        properties["korean_name_status"] = {"type": status_type, "title": "Korean Name Status"}
    schema = dict(LOCAL_SCHEMA)
    schema["properties"] = properties
    return json.dumps({"components": {"schemas": {"LineageTaxonResponse": schema}}}).encode()


def _fetcher_from_map(responses: dict[str, tuple[int, bytes]]):
    def fetcher(url: str, timeout: float) -> tuple[int, bytes]:
        for suffix, response in responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"unexpected URL requested: {url}")

    return fetcher


def _passing_responses() -> dict[str, tuple[int, bytes]]:
    return {
        "/health": (200, HEALTH_BODY),
        "/openapi.json": (200, _openapi_body(include_status_field=True)),
        "name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC": (200, _lineage_body(CURRENT_LINEAGE_ITEM)),
    }


class VerifyDeploymentContractParityTest(unittest.TestCase):
    def test_matching_deployment_passes_with_no_drift(self) -> None:
        report = verify_deployment(fetcher=_fetcher_from_map(_passing_responses()), local_schema=LOCAL_SCHEMA)
        self.assertTrue(report.backend_reachable)
        self.assertTrue(report.contract_parity_ok)
        self.assertTrue(report.passed)
        self.assertEqual(report.schema_drift, [])
        self.assertEqual(report.response_drift, [])
        self.assertEqual(report.canary_issues, [])

    def test_stale_deployment_missing_korean_name_status_fails_with_named_drift(self) -> None:
        responses = _passing_responses()
        responses["/openapi.json"] = (200, _openapi_body(include_status_field=False))
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body(STALE_LINEAGE_ITEM))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertTrue(report.backend_reachable)
        self.assertFalse(report.contract_parity_ok)
        self.assertFalse(report.passed)
        self.assertTrue(any("korean_name_status" in line for line in report.schema_drift))
        self.assertTrue(any("korean_name_status" in line for line in report.response_drift))
        # A field that vanished from the schema also vanished from the live
        # object -- the canary check must independently notice the missing key too.
        self.assertTrue(any("korean_name_status" in line for line in report.canary_issues))

    def test_wrong_declared_type_is_reported_even_though_the_field_name_matches(self) -> None:
        # A field can be present under the same name but declared with the
        # wrong type -- a names-only diff would wrongly call this a match.
        responses = _passing_responses()
        responses["/openapi.json"] = (200, _openapi_body(include_status_field=True, status_type="integer"))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(
            any("korean_name_status" in line and "type" in line for line in report.schema_drift),
            report.schema_drift,
        )

    def test_deployed_required_field_made_optional_is_reported_as_contract_drift(self) -> None:
        responses = _passing_responses()
        deployed = json.loads(_openapi_body(include_status_field=True))
        schema = deployed["components"]["schemas"]["LineageTaxonResponse"]
        schema["required"] = [name for name in schema["required"] if name != "scientific_name"]
        responses["/openapi.json"] = (200, json.dumps(deployed).encode())

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("no longer requires" in line and "scientific_name" in line for line in report.schema_drift))

    def test_process_and_lineage_release_are_reported_but_never_compared(self) -> None:
        report = verify_deployment(fetcher=_fetcher_from_map(_passing_responses()), local_schema=LOCAL_SCHEMA)
        self.assertEqual(report.process_taxonomy_release, "fixture-avlist-2025")
        self.assertEqual(report.lineage_taxonomy_release, "v2025b")
        # A mismatched pair of release identifiers must not, by itself, fail parity.
        self.assertTrue(report.contract_parity_ok)
        self.assertTrue(any("v2025b" in note and "fixture-avlist-2025" in note for note in report.notes))

    def test_missing_lineage_schema_entirely_is_reported_as_drift(self) -> None:
        responses = _passing_responses()
        responses["/openapi.json"] = (200, json.dumps({"components": {"schemas": {}}}).encode())

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertIn("deployed OpenAPI document has no usable LineageTaxonResponse schema", report.schema_drift)


class VerifyDeploymentMalformedBodyTest(unittest.TestCase):
    """A 200 with a syntactically-valid-but-useless JSON body must fail, not pass silently."""

    def test_openapi_200_with_a_json_array_instead_of_an_object_fails(self) -> None:
        responses = _passing_responses()
        responses["/openapi.json"] = (200, b"[]")

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertTrue(report.backend_reachable)  # 200 + valid JSON, just the wrong shape
        self.assertFalse(report.contract_parity_ok)
        self.assertIn("openapi.json response is not a JSON object", report.structural_errors)

    def test_lineage_200_with_null_body_fails(self) -> None:
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, b"null")

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertTrue(report.backend_reachable)
        self.assertFalse(report.contract_parity_ok)
        self.assertIn("lineage response is not a JSON object", report.structural_errors)
        self.assertIn("lineage response is not a JSON object", report.canary_issues)

    def test_health_200_with_a_json_string_instead_of_an_object_fails(self) -> None:
        responses = _passing_responses()
        responses["/health"] = (200, b'"ok"')

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertIn("health response is not a JSON object", report.canary_issues)

    def test_empty_lineage_array_fails_even_though_the_envelope_is_well_formed(self) -> None:
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body_bytes([]))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("empty" in line for line in report.response_drift))
        self.assertTrue(any("no taxon was actually resolved" in line for line in report.canary_issues))


class VerifyDeploymentCanaryTest(unittest.TestCase):
    """Value-level checks: the right keys with the wrong data must still fail."""

    def test_wrong_resolved_species_fails_even_with_all_fields_present(self) -> None:
        wrong_species = dict(CURRENT_LINEAGE_ITEM, scientific_name="Anas crecca")
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body(wrong_species))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("Anas crecca" in line and "Anas platyrhynchos" in line for line in report.canary_issues))

    def test_null_korean_name_status_fails(self) -> None:
        item = dict(CURRENT_LINEAGE_ITEM, korean_name_status=None)
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body(item))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("null" in line for line in report.canary_issues))

    def test_wrong_korean_name_status_value_fails(self) -> None:
        item = dict(CURRENT_LINEAGE_ITEM, korean_name_status="official")
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body(item))

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("'official'" in line for line in report.canary_issues))

    def test_wrong_matched_by_fails(self) -> None:
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (
            200,
            _lineage_body(CURRENT_LINEAGE_ITEM, matched_by="scientific_name"),
        )

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("matched_by" in line for line in report.canary_issues))

    def test_wrong_health_mode_fails_even_though_status_is_ok(self) -> None:
        responses = _passing_responses()
        responses["/health"] = (
            200,
            json.dumps({"status": "ok", "mode": "fixture", "taxonomy_release": "fixture-avlist-2025"}).encode(),
        )

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("health.mode" in line for line in report.canary_issues))

    def test_wrong_health_status_fails(self) -> None:
        responses = _passing_responses()
        responses["/health"] = (
            200,
            json.dumps({"status": "degraded", "mode": "neo4j", "taxonomy_release": "fixture-avlist-2025"}).encode(),
        )

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.contract_parity_ok)
        self.assertTrue(any("health.status" in line for line in report.canary_issues))

    def test_custom_expected_species_and_status_are_honored(self) -> None:
        item = {
            "taxon_id": "avilist-taxon:v2025b:1",
            "rank": "species",
            "scientific_name": "Struthio camelus",
            "authority": None,
            "korean_name": "타조",
            "korean_name_status": "community-sourced",
        }
        responses = _passing_responses()
        responses["name=%ED%83%80%EC%A1%B0"] = (200, _lineage_body(item))
        del responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"]

        report = verify_deployment(
            fetcher=_fetcher_from_map(responses),
            local_schema=LOCAL_SCHEMA,
            lineage_name="타조",
            expected_scientific_name="Struthio camelus",
        )
        self.assertTrue(report.contract_parity_ok, report.canary_issues)


class VerifyDeploymentBackendFailureTest(unittest.TestCase):
    def test_unreachable_host_is_reported_without_leaking_exception_internals(self) -> None:
        def fetcher(url: str, timeout: float) -> tuple[int, bytes]:
            raise URLError(OSError("a fake low-level socket error with sensitive path /Users/ops/.env"))

        report = verify_deployment(fetcher=fetcher, local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.backend_reachable)
        self.assertFalse(report.passed)
        rendered = json.dumps(report_to_dict(report))
        self.assertNotIn(".env", rendered)
        self.assertNotIn("/Users/ops", rendered)
        self.assertIn("could not reach host", report.health.error)

    def test_non_200_status_is_reported_without_echoing_response_body(self) -> None:
        secret_looking_body = b'{"detail":"upstream token=abc123-should-not-be-echoed"}'
        responses = _passing_responses()
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (503, secret_looking_body)

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.backend_reachable)
        self.assertFalse(report.passed)
        self.assertEqual(report.lineage.status_code, 503)
        rendered = json.dumps(report_to_dict(report))
        self.assertNotIn("abc123", rendered)

    def test_report_redacts_credentials_and_signed_query_in_operator_supplied_url(self) -> None:
        report = verify_deployment(
            base_url="https://operator:super-secret@example.invalid/api?signature=also-secret",
            fetcher=_fetcher_from_map(_passing_responses()),
            local_schema=LOCAL_SCHEMA,
        )
        rendered = json.dumps(report_to_dict(report))
        self.assertNotIn("super-secret", rendered)
        self.assertNotIn("also-secret", rendered)
        self.assertEqual(report.base_url, "https://example.invalid/api")

    def test_invalid_json_body_is_reported_cleanly(self) -> None:
        responses = _passing_responses()
        responses["/health"] = (200, b"<html>not json</html>")

        report = verify_deployment(fetcher=_fetcher_from_map(responses), local_schema=LOCAL_SCHEMA)
        self.assertFalse(report.health.ok)
        self.assertEqual(report.health.error, "response was not valid JSON")
        self.assertFalse(report.backend_reachable)


class VerifyDeploymentCliTest(unittest.TestCase):
    def test_parse_args_defaults_to_the_public_domain(self) -> None:
        args = parse_args([])
        self.assertEqual(args.base_url, "https://aviary.dove-nest.com")
        self.assertEqual(args.lineage_name, "청둥오리")
        self.assertEqual(args.expected_scientific_name, "Anas platyrhynchos")
        self.assertEqual(args.expected_korean_name_status, "community-sourced")

    def test_parse_args_reads_env_override(self) -> None:
        with patch.dict("os.environ", {"ROBINGRAPH_PUBLIC_API_URL": "https://staging.example.com"}):
            args = parse_args([])
        self.assertEqual(args.base_url, "https://staging.example.com")

    def test_main_exits_zero_on_full_parity(self) -> None:
        with patch("scripts.verify_api_deployment.default_fetcher", _fetcher_from_map(_passing_responses())):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["--json"])
        self.assertEqual(exit_code, 0)

    def test_main_exits_one_on_contract_drift(self) -> None:
        responses = _passing_responses()
        responses["/openapi.json"] = (200, _openapi_body(include_status_field=False))
        responses["name=%EC%B2%AD%EB%91%A5%EC%98%A4%EB%A6%AC"] = (200, _lineage_body(STALE_LINEAGE_ITEM))

        with patch("scripts.verify_api_deployment.default_fetcher", _fetcher_from_map(responses)):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main([])
        self.assertEqual(exit_code, 1)

    def test_main_exits_two_when_backend_unreachable(self) -> None:
        def fetcher(url: str, timeout: float) -> tuple[int, bytes]:
            raise URLError(OSError("connection refused"))

        with patch("scripts.verify_api_deployment.default_fetcher", fetcher):
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main([])
        self.assertEqual(exit_code, 2)

    def test_default_fetcher_is_a_plain_get_with_no_credentials_attached(self) -> None:
        # Guards against someone later wiring in an Authorization header or
        # reading .env.nas.ingest into this read-only verifier.
        import inspect

        source = inspect.getsource(default_fetcher)
        self.assertNotIn("Authorization", source)
        self.assertNotIn(".env", source)


if __name__ == "__main__":
    unittest.main()
