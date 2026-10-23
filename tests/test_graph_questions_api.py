"""Graph question routing contracts; these tests use injected mock retrieval."""
import unittest
from unittest.mock import Mock

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.retrieval.species_profile import SpeciesNotFoundError


class GraphQuestionApiTest(unittest.TestCase):
    def payload(self, status="answer"):
        return {"title": "관계 탐색", "text": "출처에서 확인한 관계입니다.", "status": status,
                "items": [], "paths": [], "sources": [], "limitations": [], "has_more": False}

    def test_graph_question_bypasses_single_species_and_semantic_routing(self):
        graph = Mock(return_value=self.payload())
        profile = Mock(side_effect=AssertionError("single species route"))
        router = Mock()
        router.classify.side_effect = AssertionError("embedding route")
        client = TestClient(create_django_app(graph_question_handler=graph,
                            species_profile_handler=profile, semantic_router=router))
        response = client.post("/v1/chat", json={"question": "참새목 중 열매를 먹고 사는 새는?",
                                               "species_scope": "korea"})
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("graph_query", body["result"]["kind"])
        self.assertEqual("answer", body["disposition"])
        self.assertEqual("deterministic", body["route_method"])
        self.assertEqual("korea", graph.call_args.kwargs["species_scope"])
        profile.assert_not_called()
        router.classify.assert_not_called()

    def test_screenshot_order_bird_phrase_routes_to_general_fruit(self):
        graph = Mock(return_value=self.payload())
        client = TestClient(create_django_app(graph_question_handler=graph))
        body = client.post('/v1/chat', json={'question': '참새목 새중에서 열매를 먹는 새는?'}).json()
        self.assertEqual('answer', body['disposition'])
        parsed = graph.call_args.args[0]
        self.assertEqual(('order_fruit', '참새목', 'fruit_share'),
                         (parsed.kind, parsed.rank_name, parsed.criterion))

    def test_tree_fruit_question_routes_with_explicit_category_boundary(self):
        graph = Mock(return_value=self.payload())
        body = TestClient(create_django_app(graph_question_handler=graph)).post(
            '/v1/chat', json={'question': '참새목 새 중에서 나무열매를 먹는 새는?'}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertEqual('tree_fruit_share', graph.call_args.args[0].criterion)

    def test_natural_question_ending_bypasses_semantic_fallback(self):
        graph = Mock(return_value=self.payload())
        router = Mock()
        router.classify.side_effect = AssertionError('must use the graph route')
        body = TestClient(create_django_app(graph_question_handler=graph, semantic_router=router)).post(
            '/v1/chat', json={'question': '참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?'}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertEqual('tree_fruit_share', graph.call_args.args[0].criterion)
        router.classify.assert_not_called()

    def test_no_handler_and_backend_failure_abstain_without_claiming_absence(self):
        for handler in (None, Mock(side_effect=RuntimeError("private backend detail"))):
            with self.subTest(handler=handler):
                body = TestClient(create_django_app(graph_question_handler=handler)).post(
                    "/v1/chat", json={"question": "참새목 중 열매를 먹고 사는 새는?"}).json()
                self.assertEqual("abstain", body["disposition"])
                self.assertEqual("insufficient_data", body["result"]["payload"]["status"])
                self.assertNotIn("private backend", str(body))

    def test_insufficient_specific_fruit_evidence_is_not_an_answer(self):
        graph = Mock(return_value=self.payload("insufficient_data"))
        body = TestClient(create_django_app(graph_question_handler=graph)).post(
            "/v1/chat", json={"question": "숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?"}).json()
        graph.assert_called_once()
        self.assertEqual("abstain", body["disposition"])

    def test_single_species_filter_is_not_silently_ignored(self):
        graph = Mock(return_value=self.payload())
        body = TestClient(create_django_app(graph_question_handler=graph)).post(
            "/v1/chat", json={"question": "참새목 중 열매를 먹고 사는 새는?",
                              "filters": {"kind": "profile", "name": "청둥오리"}}).json()
        self.assertEqual("clarify", body["disposition"])
        graph.assert_not_called()

    def test_openapi_exposes_additive_graph_result(self):
        body = TestClient(create_django_app()).get("/openapi.json").json()
        result = body["components"]["schemas"]["ChatResponse"]["properties"]["result"]
        self.assertEqual("#/components/schemas/ChatGraphResult", result["discriminator"]["mapping"]["graph_query"])

    def test_explicit_profile_empty_filter_sent_by_ui_is_not_a_conflict(self):
        graph = Mock(return_value=self.payload())
        body = TestClient(create_django_app(graph_question_handler=graph)).post(
            "/v1/chat", json={"question": "참새목 중 열매를 먹고 사는 새는?", "intent": "profile",
                              "filters": {"kind": "profile"}}).json()
        self.assertEqual("graph_query", body["result"]["kind"])
        self.assertEqual("explicit", body["route_method"])
        graph.assert_called_once()

    def test_unknown_species_is_a_name_clarification_not_backend_outage(self):
        graph = Mock(side_effect=SpeciesNotFoundError("unknown"))
        body = TestClient(create_django_app(graph_question_handler=graph)).post(
            "/v1/chat", json={"question": "천둥오리와 같은 속에 속하는 새를 보여줘"}).json()
        self.assertEqual("clarify", body["disposition"])
        self.assertIn("종 이름", body["answer_text"])
        self.assertNotIn("현재 확인할 수 없습니다", body["answer_text"])
