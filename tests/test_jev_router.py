import io
import json
import math
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.api.jev_router import CRITERIA, JevDecision, JevRouter, JevSettings, configured_jev_router
from robingraph.api.question_entities import extract_name


def response(label="subspecies", **changes):
    answer = {"type": "choice", "choice": label, "confidence": 1,
              "probabilities": {k: float(k == label) for k in CRITERIA}}
    answer.update(changes)
    return {"code": 0, "data": {"result": {"answers": {"intent": answer},
            "usage": {"input_tokens": 20, "output_tokens": 8}}, "creditsUsed": 1}}


PROFILE = {"taxon": {"taxon_id": "mallard", "rank": "species", "scientific_name": "Anas platyrhynchos", "korean_name": "청둥오리"},
           "lineage": {"concept_set_id": "active", "taxonomy_release": "2025b"}, "warnings": [], "traits": []}
SUBSPECIES = {"parent_species": {"taxon": PROFILE["taxon"]}, "concept_set_id": "active", "taxonomy_release": "2025b",
              "subspecies": [{"taxon_id": "child", "rank": "subspecies", "scientific_name": "Anas platyrhynchos platyrhynchos"}],
              "source_name": "AviList", "source_url": "https://www.avilist.org/"}


class JevRouterTest(unittest.TestCase):
    def setUp(self):
        self.router = JevRouter(JevSettings("secret-test-key"))

    def test_real_envelope_and_all_probability_guards(self):
        decision, usage, credits, model = self.router._parse(response())
        self.assertEqual("subspecies", decision.label)
        self.assertEqual(20, usage["input_tokens"])
        self.assertEqual(1, credits)
        self.assertIsNone(model)  # Provider does not currently echo a model.
        self.assertEqual("low_confidence", self.router._parse(response(confidence=0.4))[0].failure)
        self.assertEqual("uncertain", self.router._parse(response("uncertain"))[0].failure)
        invalid = [response(choice="invented"), response(type="score"), response(confidence=True),
                   response(confidence=math.nan), response(probabilities={"subspecies": 1}),
                   {"code": 1, "data": {}}, {"code": False, "data": {}}]
        for value in (-1, 2, True, math.inf, math.nan, "1"):
            data = response(); data["data"]["result"]["answers"]["intent"]["probabilities"]["profile"] = value
            invalid.append(data)
        data = response(); data["data"]["result"]["answers"]["intent"]["probabilities"]["profile"] = 1
        invalid.append(data)
        data = response(choice="profile"); invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises((ValueError, KeyError, TypeError)):
                self.router._parse(data)

    def test_margins_probability_and_tied_winners(self):
        probs = {k: 0 for k in CRITERIA}; probs.update(subspecies=0.51, taxonomy=0.49)
        self.assertEqual("low_confidence", self.router._parse(response(probabilities=probs))[0].failure)
        probs.update(subspecies=0.5, taxonomy=0.5)
        self.assertIsNone(self.router._parse(response(probabilities=probs))[0].label)
        probs.update(subspecies=0.4, taxonomy=0.6)
        with self.assertRaises(ValueError): self.router._parse(response(probabilities=probs))

    def test_request_credentials_user_agent_and_safe_tracing(self):
        self.router._opener.open = Mock(return_value=io.BytesIO(json.dumps(response()).encode()))
        with patch("robingraph.api.jev_router.tracing.span") as tracing:
            decision = self.router.classify("청둥오리 아종 알려줘")
        self.assertEqual("subspecies", decision.label)
        request = self.router._opener.open.call_args.args[0]
        self.assertEqual("Bearer secret-test-key", request.get_header("Authorization"))
        self.assertEqual("RobinGraph-Jev/1.0", request.get_header("User-agent"))
        self.assertEqual("typesafe/jev-1.13", json.loads(request.data)["model"])
        self.assertNotIn("secret-test-key", repr(tracing.mock_calls))
        self.assertNotIn("secret-test-key", repr(self.router.settings))

    def test_transport_errors_retry_only_transient_http_and_never_expose_body(self):
        for status, expected, attempts in ((401,"authentication",1),(403,"authentication",1),(429,"rate_limit",2),
                                            (503,"http_error",2),(302,"http_error",1)):
            self.router._opener.open = Mock(side_effect=HTTPError("https://example.com",status,"secret-test-key",{},io.BytesIO(b"secret-test-key")))
            with patch("robingraph.api.jev_router.time.sleep"):
                decision = self.router.classify("test")
            self.assertEqual(expected, decision.failure)
            self.assertEqual(attempts, self.router._opener.open.call_count)
            self.assertNotIn("secret-test-key", repr(decision))
        for error, expected in ((TimeoutError(),"timeout"),(URLError("secret-test-key"),"transport")):
            self.router._opener.open = Mock(side_effect=error)
            self.assertEqual(expected,self.router.classify("test").failure)
            self.router._opener.open.assert_called_once()

    def test_malformed_json_response_never_raises_or_retries(self):
        for body in (b"not json", b"[]", json.dumps(response(choice="bad")).encode(), b"x"*262145):
            self.router._opener.open = Mock(return_value=io.BytesIO(body))
            self.assertEqual("invalid_response", self.router.classify("test").failure)
            self.router._opener.open.assert_called_once()

    def test_configuration_and_explicit_rollback(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(configured_jev_router())
        with patch.dict("os.environ", {"TYPESAFE_API_KEY":"compat-key"}, clear=True):
            self.assertIsInstance(configured_jev_router(), JevRouter)
        with patch.dict("os.environ", {"JEV_API_KEY":"key", "ROBINGRAPH_INTENT_ROUTER":"semantic"}, clear=True):
            self.assertIsNone(configured_jev_router())
        for changes in ({"endpoint":"http://example.com"},{"endpoint":"https://a:b@example.com"},
                        {"timeout_seconds":math.nan},{"max_retries":3},{"confidence_threshold":True}):
            with self.assertRaises(ValueError): JevSettings("key", **changes)


class JevChatTest(unittest.TestCase):
    def make(self, label="subspecies", failure=None, **handlers):
        self.router = Mock(); self.router.classify.return_value = JevDecision(label, failure=failure)
        return TestClient(create_app(jev_router=self.router, **handlers))

    def test_reported_subspecies_questions_use_exact_parent_and_return_list(self):
        for name in ("청둥오리", "흰뺨검둥오리"):
            profile = Mock(return_value=PROFILE); subspecies = Mock(return_value=SUBSPECIES)
            client = self.make(species_profile_handler=profile, subspecies_handler=subspecies)
            result = client.post("/v1/chat", json={"question":name+" 아종 알려줘"}).json()
            self.assertEqual("answer", result["disposition"])
            self.assertEqual("jev", result["route_method"])
            self.assertEqual(SUBSPECIES, result["result"]["subspecies"])
            self.assertEqual("subspecies", result["result"]["question_answer"]["topic"])
            profile.assert_called_once_with(name); subspecies.assert_called_once_with(name)

    def test_empty_subspecies_is_honest_and_changed_context_abstains(self):
        for data, disposition in (({**SUBSPECIES,"subspecies":[]},"answer"),
                                  ({**SUBSPECIES,"concept_set_id":"other"},"abstain")):
            client=self.make(species_profile_handler=lambda n:PROFILE,subspecies_handler=lambda n:data)
            r=client.post("/v1/chat",json={"question":"청둥오리 아종 알려줘"}).json()
            self.assertEqual(disposition,r["disposition"])
            if disposition=="answer": self.assertIn("연결된 아종이 없습니다",r["answer_text"])

    def test_explicit_and_deterministic_never_call_jev(self):
        for payload in ({"question":"청둥오리", "intent":"profile"}, {"question":"청둥오리에 대해 알려줘"},
                        {"question":"청둥오리 먹이 알려줘"}):
            client=self.make(species_profile_handler=lambda n:PROFILE)
            self.assertEqual(200,client.post("/v1/chat",json=payload).status_code)
            self.router.classify.assert_not_called()

    def test_uncertainty_never_falls_back_and_outage_may_use_legacy(self):
        for failure, expected in (("low_confidence","clarify"),("uncertain","clarify"),("authentication","abstain")):
            semantic=Mock(); semantic.classify.return_value="taxonomy"
            client=self.make(None,failure,semantic_router=semantic)
            result=client.post("/v1/chat",json={"question":"청둥오리 아종 알려줘"}).json()
            self.assertEqual(expected,result["disposition"])
            self.assertEqual(1 if failure=="authentication" else 0,semantic.classify.call_count)

    def test_name_missing_or_conflicting_filters_never_run_lookup(self):
        for payload in ({"question":"그 새 아종 알려줘"},
                        {"question":"청둥오리 아종 알려줘","filters":{"kind":"profile","name":"왜가리"}},
                        {"question":"청둥오리 아종 알려줘","filters":{"kind":"evidence"}}):
            profile=Mock(return_value=PROFILE)
            client=self.make(species_profile_handler=profile)
            result=client.post("/v1/chat",json=payload).json()
            self.assertEqual("clarify",result["disposition"])
            profile.assert_not_called()

    def test_jev_observations_require_explicit_bounded_filters(self):
        handler=Mock()
        client=self.make("observations",observation_handler=handler)
        r=client.post("/v1/chat",json={"question":"어제 서울에서 본 새 기록"}).json()
        self.assertEqual("clarify",r["disposition"]); handler.assert_not_called()

    def test_source_spans_never_correct_typos_or_extract_multiple_names(self):
        self.assertEqual("청둥오리",extract_name("청둥오리 아종 알려줘","subspecies"))
        self.assertEqual("흰뺨검둥오리",extract_name("흰뺨검둥오리 아종 알려줘","subspecies"))
        self.assertEqual("Anas platyrhynchos",extract_name("List subspecies of Anas platyrhynchos","subspecies"))
        self.assertIsNone(extract_name("청둥오리 그리고 왜가리 아종 알려줘","subspecies"))
        self.assertIsNone(extract_name("그 새 아종 알려줘","subspecies"))


if __name__ == "__main__": unittest.main()
