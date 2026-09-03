from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.fixture import load_fixture


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(load_fixture()))

    def test_health_discloses_fixture_mode(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("fixture", response.json()["mode"])

    def test_answer_contains_only_allowed_evidence(self) -> None:
        response = self.client.post("/v1/answers", json={"question": "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("answer", payload["disposition"])
        self.assertEqual(["fixture-occ-001"], payload["evidence_ids"])
        self.assertEqual("fixture-occ-001", payload["citations"][0]["evidence_id"])

    def test_sensitive_coordinate_request_abstains_over_http(self) -> None:
        response = self.client.post("/v1/answers", json={"question": "말똥가리의 정확한 관찰 좌표를 알려줘."})
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("abstain", payload["disposition"])
        self.assertNotIn("37.54", payload["answer_text"])

    def test_blank_question_is_rejected(self) -> None:
        response = self.client.post("/v1/answers", json={"question": ""})
        self.assertEqual(422, response.status_code)
