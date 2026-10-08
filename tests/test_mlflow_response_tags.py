"""RG-016: searchable MLflow trace tags that separate answers from non-answers.

Layers (each test class says which one it is):
* pure unit -- tag allowlist/derivation, no MLflow;
* fake ``mlflow`` module -- wiring, fail-open, isolation, disabled no-op;
* real ``mlflow-tracing`` SDK with the exporter captured locally (no tracking
  server, no network) -- proves the tags land on the real ``TraceInfo`` and the
  trace state stays OK for HTTP 200 non-answers.
Real server ``search_traces(filter_string=...)`` is exercised by
``scripts/verify_mlflow_response_tags.py`` against a reachable server, not here.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from robingraph import tracing
from robingraph.api.app import create_app, create_neo4j_search_handler
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval import neo4j_hybrid
from robingraph.retrieval.hybrid import HybridSearchOutcome
from robingraph.retrieval.species_profile import SpeciesNotFoundError

from tests.test_mlflow_tracing import ENABLED_ENV, FakeMlflow  # noqa: E402

HAS_MLFLOW = importlib.util.find_spec("mlflow") is not None
TAG_KEYS = {"response_disposition", "response_reason", "failure_stage", "selected_intent", "route_method"}

PROFILE = {"taxon": {"taxon_id": "t1", "scientific_name": "Anas platyrhynchos", "rank": "species"},
           "traits": [], "summary": "청둥오리 요약", "warnings": []}


def _profile(name):
    if name == "없는종":
        raise SpeciesNotFoundError(name)
    if name == "장애종":
        raise RuntimeError("neo4j://user:pw@host down")
    return PROFILE


def _search(settings, request, *, query_embedder=None):
    if "장애" in request.query_text:
        raise RuntimeError("search backend down https://u:pw@h")
    return HybridSearchOutcome((), ())


def _name_relations(name):
    if name != "모호통칭":
        return None
    return {"is_search_term": True, "summary": "여러 종에 해당하는 이름입니다.", "relations": [
        {"entity_kind": "common_name", "taxon": {"taxon_id": "t1", "scientific_name": "Anas platyrhynchos"}},
        {"entity_kind": "common_name", "taxon": {"taxon_id": "t2", "scientific_name": "Anas acuta"}},
    ]}


def _app():
    settings = Neo4jSettings("bolt://neo4j.invalid:7687", "neo4j", "neo4j-password", "neo4j")
    return create_app(
        species_profile_handler=_profile,
        observation_handler=lambda query: [],
        name_relations_handler=_name_relations,
        search_handler=create_neo4j_search_handler(settings),
    )


# name -> (request body, expected tags without selected_intent/route_method checks)
CASES = {
    "answer": ({"question": "청둥오리", "intent": "profile"}, ("answer", "none", "none", "profile", "explicit")),
    "not_found": ({"question": "없는종", "intent": "profile"}, ("abstain", "taxon_not_found", "name_resolution", "profile", "explicit")),
    "upstream": ({"question": "장애종", "intent": "profile"}, ("error", "upstream_error", "retrieval", "profile", "explicit")),
    "handler_unavailable": ({"question": "참새", "intent": "taxonomy"}, ("error", "handler_unavailable", "retrieval", "taxonomy", "explicit")),
    "filter_missing": ({"question": "관찰", "intent": "observations"}, ("clarify", "filter_mismatch", "validation", "observations", "explicit")),
    "observations_empty": ({"question": "관찰", "intent": "observations", "filters": {"kind": "observations", "place": "서울"}},
                           ("abstain", "observations_empty", "retrieval", "observations", "explicit")),
    "evidence_empty": ({"question": "서식지 근거", "intent": "evidence"}, ("abstain", "evidence_not_found", "retrieval", "evidence", "explicit")),
    "evidence_error": ({"question": "장애 근거", "intent": "evidence"}, ("error", "upstream_error", "retrieval", "evidence", "explicit")),
    "ambiguous_name": ({"question": "모호통칭", "intent": "profile"}, ("clarify", "ambiguous_name", "name_resolution", "profile", "explicit")),
    "unsupported": ({"question": "청둥오리 먹이 알려줘", "intent": "profile"}, ("abstain", "unsupported_question", "generation", "profile", "explicit")),
    "intent_uncertain": ({"question": "음...", "intent": "auto"}, ("clarify", "intent_uncertain", "routing", "none", "semantic")),
}


def _tuple(tags):
    return (tags["response_disposition"], tags["response_reason"], tags["failure_stage"],
            tags["selected_intent"], tags["route_method"])


class TagDerivationTest(unittest.TestCase):
    """Pure unit: no MLflow involved."""

    def test_allowlist_rejects_unlisted_values(self) -> None:
        tags = tracing.resolve_response_tags(
            "abstain", reason="sk-secret-value", stage="https://u:p@h", selected_intent="홍길동", route_method="x y")
        self.assertEqual(("abstain", "unknown", "unknown", "none", "none"), _tuple(tags))
        self.assertEqual(TAG_KEYS, set(tags))

    def test_technical_reason_is_error_even_for_http_200_abstain(self) -> None:
        self.assertEqual("error", tracing.resolve_response_tags("abstain", reason="upstream_error", stage="retrieval")["response_disposition"])
        self.assertEqual("abstain", tracing.resolve_response_tags("abstain", reason="taxon_not_found", stage="name_resolution")["response_disposition"])

    def test_plain_answer_and_unexplained_non_answer(self) -> None:
        self.assertEqual(("answer", "none", "none"), _tuple(tracing.resolve_response_tags("answer"))[:3])
        self.assertEqual(("abstain", "unknown", "unknown"), _tuple(tracing.resolve_response_tags("abstain"))[:3])

    def test_note_outcome_is_noop_without_a_collector(self) -> None:
        tracing.note_outcome("upstream_error", "retrieval")
        self.assertEqual({}, tracing.collected_outcome())


class FakeTagMlflow(FakeMlflow):
    def __init__(self) -> None:
        super().__init__()
        self.tag_calls: list[dict] = []
        self.update_current_trace = mock.Mock(side_effect=lambda tags=None, **kw: self.tag_calls.append(dict(tags)))


class FakeSdkTagTest(unittest.TestCase):
    """Fake ``mlflow`` module: wiring, fail-open, concurrency isolation."""

    def setUp(self) -> None:
        self.fake = FakeTagMlflow()
        patcher = mock.patch.dict(sys.modules, {"mlflow": self.fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(tracing.reset_tracing)
        self.assertTrue(tracing.configure_tracing(dict(ENABLED_ENV)).enabled)
        self.client = TestClient(_app())

    def _post(self, name):
        with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _search):
            return self.client.post("/v1/chat", json=CASES[name][0])

    def test_every_response_case_writes_one_allowlisted_tag_set(self) -> None:
        for name, (_body, expected) in CASES.items():
            with self.subTest(name):
                self.fake.tag_calls.clear()
                response = self._post(name)
                self.assertEqual(200, response.status_code)
                self.assertEqual(1, len(self.fake.tag_calls))
                tags = self.fake.tag_calls[0]
                self.assertEqual(expected, _tuple(tags))
                self.assertEqual(response.json()["disposition"], tags["response_api_disposition"])
                self.assertNotIn("pw", json.dumps(tags))

    def test_tag_write_failure_does_not_change_the_response(self) -> None:
        baseline = self._post("not_found").json()
        self.fake.update_current_trace.side_effect = RuntimeError("tracking server down")
        self.assertEqual(baseline, self._post("not_found").json())

    def test_span_start_failure_does_not_change_the_response(self) -> None:
        baseline = self._post("not_found").json()

        def broken(**_kw):
            raise RuntimeError("down")

        self.fake.start_span = broken
        self.fake.tag_calls.clear()
        self.assertEqual(baseline, self._post("not_found").json())

    def test_concurrent_requests_keep_their_own_tags(self) -> None:
        names = list(CASES) * 4
        lock_calls = self.fake.tag_calls
        original = neo4j_hybrid.search

        def run(index_name):
            index, name = index_name
            return index, name, TestClient(_app()).post("/v1/chat", json=CASES[name][0]).json()

        # Patch once outside the pool: per-thread patch/unpatch overlap would
        # restore another thread's mock and leave _search installed globally.
        with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _search):
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(run, enumerate(names)))
        self.assertIs(original, neo4j_hybrid.search)
        # Every response matches its case, and the multiset of written tag sets equals the expected multiset.
        expected = sorted(CASES[name][1] for name in names)
        self.assertEqual(expected, sorted(_tuple(tags) for tags in lock_calls))
        for _index, name, body in outcomes:
            self.assertEqual(CASES[name][1][3] if CASES[name][1][3] != "none" else None, body["selected_intent"])

    def test_non_chat_route_http_errors_are_tagged_by_status(self) -> None:
        self.fake.tag_calls.clear()
        response = self.client.get("/v1/taxa/profile", params={"name": "없는종"})
        self.assertEqual(404, response.status_code)
        self.assertEqual(("abstain", "taxon_not_found", "name_resolution"), _tuple(self.fake.tag_calls[0])[:3])


class DisabledTagTest(unittest.TestCase):
    def test_disabled_tracing_makes_no_mlflow_calls_and_keeps_the_response(self) -> None:
        tracing.reset_tracing()
        fake = FakeTagMlflow()
        with mock.patch.dict(sys.modules, {"mlflow": fake}):
            with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _search):
                body = TestClient(_app()).post("/v1/chat", json=CASES["not_found"][0]).json()
        self.assertEqual("abstain", body["disposition"])
        fake.update_current_trace.assert_not_called()
        self.assertEqual([], fake.spans)
        self.assertEqual({}, tracing.collected_outcome())


@unittest.skipUnless(HAS_MLFLOW, "optional 'tracing' extra (mlflow-tracing) is not installed")
class RealSdkTagTest(unittest.TestCase):
    """Real SDK, exporter captured locally: tags are on the real TraceInfo."""

    def setUp(self) -> None:
        import mlflow
        import mlflow.tracking.fluent as tracking_fluent
        from mlflow.tracing.export.mlflow_v3 import MlflowV3SpanExporter

        self.logged = []
        env_patch = mock.patch.dict(os.environ, {"MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        previous = tracking_fluent._active_experiment_id

        def set_experiment(*_a, **_k):
            tracking_fluent._active_experiment_id = "robingraph-test"

        def restore():
            tracking_fluent._active_experiment_id = previous
            mlflow.tracing.reset()

        for patcher in (
            mock.patch.object(mlflow, "set_experiment", side_effect=set_experiment),
            mock.patch.object(MlflowV3SpanExporter, "_log_trace", lambda _self, trace, prompts: self.logged.append(trace)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(restore)
        self.addCleanup(tracing.reset_tracing)
        mlflow.tracing.reset()
        self.assertTrue(tracing.configure_tracing(dict(ENABLED_ENV)).enabled)
        self.client = TestClient(_app())

    def test_tags_and_trace_state_for_each_case(self) -> None:
        for name, (body, expected) in CASES.items():
            with self.subTest(name):
                self.logged.clear()
                with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _search):
                    self.assertEqual(200, self.client.post("/v1/chat", json=body).status_code)
                self.assertEqual(1, len(self.logged))
                info = self.logged[0].info
                self.assertEqual(expected, _tuple(info.tags))
                # HTTP 200 non-answers (including dependency failures handled
                # by the route) are not technical trace errors.
                self.assertEqual("OK", getattr(info.state, "value", str(info.state)))

    def test_http_exception_is_a_technical_error_trace_with_tags(self) -> None:
        self.logged.clear()
        self.assertEqual(404, self.client.get("/v1/taxa/profile", params={"name": "없는종"}).status_code)
        info = self.logged[0].info
        self.assertEqual(("abstain", "taxon_not_found", "name_resolution"), _tuple(info.tags)[:3])
        self.assertEqual("ERROR", getattr(info.state, "value", str(info.state)))

    def test_concurrent_requests_keep_their_own_tags_on_real_traces(self) -> None:
        names = list(CASES) * 3
        original = neo4j_hybrid.search

        def run(name):
            return TestClient(_app()).post("/v1/chat", json=CASES[name][0]).status_code

        with mock.patch("robingraph.retrieval.neo4j_hybrid.search", _search):
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(run, names))
        self.assertIs(original, neo4j_hybrid.search)
        self.assertEqual({200}, set(statuses))
        self.assertEqual(sorted(CASES[n][1] for n in names), sorted(_tuple(t.info.tags) for t in self.logged))


if __name__ == "__main__":
    unittest.main()
