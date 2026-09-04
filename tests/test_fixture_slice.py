from __future__ import annotations

import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from robingraph.fixture import default_fixture_root, load_fixture
from robingraph.graph.settings import Neo4jSettings
from robingraph.graph.fixture_projection import fixture_graph_payload
from robingraph.ingest.validation import validate_source_registry_record, validate_staging_record
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.slice import QuestionService, validate_answer


class FixtureSliceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = default_fixture_root()
        cls.corpus = load_fixture(cls.root)
        cls.repository = FixtureRepository(cls.corpus)
        cls.service = QuestionService(cls.repository)

    def test_policy_filter_keeps_only_allowed_records(self) -> None:
        self.assertEqual(10, len(self.corpus.taxonomy))
        self.assertEqual(100, len(self.corpus.observations))
        self.assertEqual(2, len(self.corpus.documents))
        self.assertEqual(4, len(self.corpus.chunks))
        self.assertNotIn("fixture-occ-restricted-001", self.corpus.evidence_ids)
        self.assertNotIn("fixture-chunk-review-1", self.corpus.evidence_ids)

    def test_fixture_is_reproducible_by_manifest(self) -> None:
        manifest = json.loads((self.root / "fixture-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("v1", manifest["fixture_version"])
        self.assertEqual(15, manifest["expected_counts"]["gold_questions"])
        self.assertEqual(6, len(manifest["files"]))

    def test_all_gold_questions_obey_evidence_and_policy_contracts(self) -> None:
        gold_rows = [
            json.loads(line)
            for line in (self.root / "gold-questions.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        self.assertEqual(15, len(gold_rows))
        for gold in gold_rows:
            with self.subTest(question_id=gold["question_id"]):
                answer = self.service.answer(gold["question_ko"])
                validate_answer(answer, self.repository)
                self.assertEqual(gold["expected_disposition"], answer.disposition)
                self.assertTrue(set(gold["expected_taxon_ids"]).issubset(answer.taxon_ids))
                expected_evidence = set(gold["acceptable_evidence_ids"])
                if expected_evidence:
                    self.assertTrue(answer.evidence_ids)
                    self.assertTrue(set(answer.evidence_ids).issubset(expected_evidence))
                for forbidden in gold["must_not_include"]:
                    self.assertNotIn(str(forbidden), answer.answer_text)
                    self.assertNotIn(str(forbidden), answer.evidence_ids)

    def test_sensitive_coordinate_request_abstains(self) -> None:
        answer = self.service.answer("말똥가리의 정확한 관찰 좌표를 알려줘.")
        self.assertEqual("abstain", answer.disposition)
        self.assertIn("sensitive_coordinates_withheld", answer.warnings)
        self.assertNotIn("37.54", answer.answer_text)

    def test_staging_validation_distinguishes_format_errors_from_policy_filtering(self) -> None:
        valid_denied = next(
            row
            for row in (
                json.loads(line)
                for line in (self.root / "input" / "observations.jsonl").read_text(encoding="utf-8").splitlines()
            )
            if row["license_policy_status"] == "denied"
        )
        self.assertEqual((), validate_staging_record("observation", valid_denied))

        invalid = deepcopy(valid_denied)
        invalid["count"] = -1
        invalid["latitude_public"] = 91
        issue_codes = {issue.reason_code for issue in validate_staging_record("observation", invalid)}
        self.assertEqual({"invalid_count", "invalid_latitude"}, issue_codes)

    def test_source_registry_contract_rejects_invalid_configuration(self) -> None:
        source = deepcopy(self.corpus.source_registry["fixture-observation"])
        self.assertEqual((), validate_source_registry_record(source))

        source["access_method"] = "scrape"
        source["enabled"] = "yes"
        issue_codes = {issue.reason_code for issue in validate_source_registry_record(source)}
        self.assertEqual({"invalid_access_method", "invalid_enabled_flag"}, issue_codes)

    def test_source_registry_schema_matches_the_python_validator_contract(self) -> None:
        schema_path = self.root.parents[2] / "config" / "schemas" / "source-registry.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        # Every source registry entry is checked by both the JSON Schema (for
        # external tooling) and validate_source_registry_record (at runtime).
        # They must agree on which fields are required and what "enabled" and
        # "license_policy_status" mean, or one side could accept a record the
        # other would reject.
        required_fields = (
            "source_id", "name", "provider", "landing_uri", "access_method", "auth_method",
            "release_strategy", "license_uri", "adapter_owner", "enabled", "license_policy_status",
        )
        self.assertEqual(set(required_fields), set(schema["required"]))
        self.assertEqual(set(required_fields), set(schema["properties"]) - {"license_name", "incremental_cursor", "rate_limit_note", "terms_uri"})

        self.assertEqual({"api", "download", "manual"}, set(schema["properties"]["access_method"]["enum"]))
        self.assertEqual(
            {"allowed", "restricted", "review_required", "denied"},
            set(schema["properties"]["license_policy_status"]["enum"]),
        )

        for source in self.corpus.source_registry.values():
            with self.subTest(source_id=source["source_id"]):
                self.assertEqual((), validate_source_registry_record(source))
                for field in required_fields:
                    self.assertIn(field, source)

    def test_neo4j_settings_require_credentials_and_a_bolt_scheme(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "NEO4J_URI"):
                Neo4jSettings.from_environment()
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "https://not-a-bolt-endpoint",
                "NEO4J_USERNAME": "fixture-user",
                "NEO4J_PASSWORD": "fixture-password",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "Bolt URI"):
                Neo4jSettings.from_environment()
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://fixture-host:7687",
                "NEO4J_USERNAME": "fixture-user",
                "NEO4J_PASSWORD": "fixture-password",
                "NEO4J_DATABASE": "fixture",
            },
            clear=True,
        ):
            settings = Neo4jSettings.from_environment()
        self.assertEqual("fixture", settings.database)

    def test_graph_projection_never_contains_private_coordinates(self) -> None:
        payload = fixture_graph_payload(self.corpus)
        self.assertEqual(10, len(payload["taxa"]))
        self.assertEqual(100, len(payload["observations"]))
        self.assertEqual(2, len(payload["documents"]))
        self.assertEqual(4, len(payload["chunks"]))
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("latitude_private", serialized)
        self.assertNotIn("longitude_private", serialized)


if __name__ == "__main__":
    unittest.main()
