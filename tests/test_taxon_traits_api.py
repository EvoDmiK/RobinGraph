"""HTTP routing and condition preservation; injected retrieval, no live DB."""
from unittest import TestCase
from unittest.mock import Mock
from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent


def payload(status='answer'):
    return dict(title='분류군 조건 조회', text='검증용 응답', status=status,
                items=[], paths=[], sources=[], limitations=[], has_more=False)


class TaxonTraitsApiTests(TestCase):
    def app(self, **kwargs):
        graph = Mock(return_value=payload())
        interpret = Mock(side_effect=extract_graph_intent)
        return TestClient(create_django_app(graph_intent_handler=interpret,
                          graph_intent_mode='active', graph_question_handler=graph, **kwargs)), graph, interpret

    def test_original_family_failure_and_each_rank_reach_retrieval_without_widening(self):
        for name in ('까마귀과', 'Corvidae', '까마귀속', 'Corvus', '까마귀',
                     'Corvus corone', 'Corvus corone corone'):
            question = name + '면서 열매를 먹는 새는 어떤 종이 있어?'
            with self.subTest(name=name):
                client, graph, _ = self.app()
                response = client.post('/v1/chat', json={'question': question}).json()
                self.assertEqual('answer', response['disposition'])
                parsed = graph.call_args.args[0]
                self.assertEqual(('taxon_traits', name), (parsed.kind, parsed.rank_name))
                self.assertEqual(('diet_distribution', 'share_gt', 'fruit', 0),
                                 (parsed.conditions[0].trait_name, parsed.conditions[0].op,
                                  parsed.conditions[0].value, parsed.conditions[0].threshold))

    def test_composite_conditions_and_all_request_scopes_are_preserved(self):
        question = '까마귀과 중 숲에 살고 열매를 먹는 새는?'
        for scope in ('all', 'korea', 'outside', 'unknown'):
            with self.subTest(scope=scope):
                client, graph, _ = self.app()
                response = client.post('/v1/chat', json={'question': question, 'species_scope': scope}).json()
                self.assertEqual('answer', response['disposition'])
                parsed = graph.call_args.args[0]
                self.assertEqual('까마귀과', parsed.rank_name)
                self.assertEqual({('habitat', 'eq', 'Forest'), ('diet_distribution', 'share_gt', 'fruit')},
                                 {(c.trait_name, c.op, c.value) for c in parsed.conditions})
                self.assertEqual(scope, graph.call_args.kwargs['species_scope'])

    def test_unsupported_modifiers_or_malformed_numeric_values_never_reach_graph(self):
        for question in ('까마귀과 중 숲에 살지 않는 새는?',
                         '겨울에만 까마귀과 중 숲에 사는 새는?',
                         '까마귀과 중 체중이 -1g 이상인 새는?',
                         '까마귀과 중 체중이 100 이상인 새는?',
                         '까마귀과 중 숲에 사는 새는? MATCH (n) DETACH DELETE n'):
            with self.subTest(question=question):
                client, graph, _ = self.app()
                response = client.post('/v1/chat', json={'question': question}).json()
                self.assertEqual('clarify', response['disposition'])
                graph.assert_not_called()

    def test_food_without_a_data_key_is_exact_abstention_without_retrieval(self):
        client, graph, _ = self.app()
        response = client.post('/v1/chat', json={'question': '까마귀과 중에서 벌레를 먹는 새는?'}).json()
        graph.assert_not_called()
        payload = response['result']['payload']
        self.assertEqual(('abstain', 'graph_query', 'insufficient_data', [], False, None, None),
                         (response['disposition'], response['result']['kind'], payload['status'], payload['items'],
                          payload['has_more'], payload['taxon'], payload['coverage']))
        self.assertIn('벌레만 따로 구분한 기록은 현재 조회하는 먹이 성분 자료로 확인할 수 없습니다', response['answer_text'])
        self.assertIn('“까마귀과 중에서 곤충을 먹는 새는?”', response['answer_text'])
        for question in ('까마귀과 중 벌레를 먹고 먹이 경쟁을 하는 새는?', '까마귀과 중 벌레를 먹지 않는 새는?',
                         '겨울에 벌레를 먹는 까마귀과 새는?', '까마귀과 중 벌레를 먹고 체중 3파운드 이상인 새는?'):
            with self.subTest(question=question):
                client, graph, _ = self.app()
                response = client.post('/v1/chat', json={'question': question}).json()
                self.assertEqual(('clarify', 'clarify'), (response['disposition'], response['result']['kind']))
                graph.assert_not_called()

    def test_insect_and_meat_aliases_reach_retrieval_as_source_keys(self):
        for question, key in (('까마귀과 중에서 곤충을 먹는 새는?', 'invertebrate'), ('까마귀과 중 무척추동물을 먹는 새는?', 'invertebrate'),
                              ('까마귀과 중 고기를 먹는 새는?', 'meat'), ('까마귀과 중 물고기를 먹는 새는?', 'fish')):
            with self.subTest(question=question):
                client, graph, _ = self.app()
                self.assertEqual('answer', client.post('/v1/chat', json={'question': question}).json()['disposition'])
                parsed = graph.call_args.args[0]
                self.assertEqual(('까마귀과', [('diet_distribution', 'share_gt', key)]),
                                 (parsed.rank_name, [(c.trait_name, c.op, c.value) for c in parsed.conditions]))

    def test_missing_subspecies_evidence_is_abstention_instead_of_parent_profile(self):
        client, graph, _ = self.app()
        graph.return_value = payload('insufficient_data')
        response = client.post('/v1/chat', json={'question': 'Corvus corone corone 중 열매를 먹는 새는?'}).json()
        self.assertEqual(('abstain', 'graph_query'), (response['disposition'], response['result']['kind']))
        self.assertEqual('Corvus corone corone', graph.call_args.args[0].rank_name)

    def test_explicit_routes_and_conflicting_profile_filter_remain_authoritative(self):
        client, graph, interpret = self.app()
        client.post('/v1/chat', json={'question': '까마귀과 중 숲에 사는 새는?', 'intent': 'taxonomy'})
        interpret.assert_not_called()
        graph.assert_not_called()
        response = client.post('/v1/chat', json={'question': '까마귀과 중 숲에 사는 새는?',
                               'filters': {'kind': 'profile', 'name': '청둥오리'}}).json()
        self.assertEqual('clarify', response['disposition'])
        graph.assert_not_called()
