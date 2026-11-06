"""Mock API checks: original restrictions survive both user confirmation steps."""
from unittest import TestCase
from unittest.mock import Mock
from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.retrieval.species_questions import ecology_meaning_choices, parse_species_question
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent


CANDIDATE = {'mention': '천둥오리', 'status': 'candidates', 'method': 'vector',
             'candidates': [{'taxon_id':'mallard', 'scientific_name':'Anas platyrhynchos',
                             'display_name':'청둥오리', 'score':.91}]}
MATCH = {'mention':'Anas platyrhynchos','status':'matched','method':'graph_exact',
         'canonical_name':'Anas platyrhynchos','taxon_id':'mallard',
         'concept_set_id':'active','taxonomy_release':'v2025b'}


class ChatClarificationTest(TestCase):
    def test_meaning_choices_preserve_every_other_word_without_retrieval(self):
        blocked = Mock(side_effect=AssertionError('no retrieval before meaning confirmation'))
        client = TestClient(create_django_app(graph_intent_mode='active',graph_intent_handler=blocked,
                                               graph_question_handler=blocked,taxon_name_resolution_handler=blocked))
        for q in ('천둥오리랑 비슷한 식생을 가진 새들을 알려줘',
                  '숲에 살지 않는 새 중 청둥오리와 식생이 비슷한 새',
                  '청둥오리와 식생이 비슷하고 몸무게 500g 이상인 새'):
            body = client.post('/v1/chat',json={'question':q,'species_scope':'korea'}).json()
            self.assertEqual('clarify',body['disposition'])
            choices=body['result']['choices']
            self.assertEqual([q.replace('식생',word) for word in ('식성','서식 환경')],
                             [c['question'] for c in choices])
            self.assertIn('식생',body['answer_text'])
        blocked.assert_not_called()

    def test_corrected_ecological_orders_keep_reference_and_relation(self):
        for name in ('청둥오리','천둥오리','Anas platyrhynchos','흰뺨 검둥 오리'):
            for noun,category in (('식성','trophic_niche'),('서식 환경','habitat')):
                q=f'{name}랑 비슷한 {noun}을 가진 새들을 알려줘'
                parsed=parse_species_question(q)
                self.assertEqual((name,'ecological_related',category),(parsed.name,parsed.topic,parsed.category))
        self.assertIsNone(parse_species_question('청둥오리랑 비슷한 식성을 가진 새 중 몸무게 500g 이상인 새'))
        self.assertEqual((),ecology_meaning_choices('숲 식생 분포에 대해 알려줘'))

    def test_inflected_ambiguity_and_ordinary_requests_use_the_same_flow(self):
        question='Anas platyrhynchos랑 비슷한 식생인 조류가 궁금해'
        choices=ecology_meaning_choices(question)
        self.assertEqual(2,len(choices))
        for choice in choices:
            parsed=parse_species_question(choice['question'])
            self.assertIsNotNone(parsed)
            self.assertEqual('Anas platyrhynchos',parsed.name)
        parsed=parse_species_question('청 둥 오리와 먹이 습성이 비슷한 새를 보여 줘')
        self.assertEqual(('청 둥 오리','trophic_niche'),(parsed.name,parsed.category))
        self.assertEqual(2,len(ecology_meaning_choices('청둥오리랑 비슷한 식생인데 곤충은 먹지 않는 새는?')))

    def test_graph_candidate_confirmation_reexecutes_original_relation_with_scope(self):
        question='천둥오리와 서식지가 겹치면서 먹이가 다른 새는?'
        resolver=Mock(side_effect=[CANDIDATE,MATCH])
        graph=Mock(return_value={'status':'answer','title':'검증 fixture','text':'근거 fixture','limitations':[]})
        client=TestClient(create_django_app(graph_intent_mode='active',graph_intent_handler=extract_graph_intent,
                                           taxon_name_resolution_handler=resolver,graph_question_handler=graph))
        first=client.post('/v1/chat',json={'question':question,'species_scope':'korea'}).json()
        self.assertEqual('clarify',first['disposition']);graph.assert_not_called()
        candidate=first['entity_resolution']['candidates'][0]
        self.assertEqual('auto',candidate['route_intent'])
        self.assertEqual(question.replace('천둥오리','Anas platyrhynchos'),candidate['question'])
        second=client.post('/v1/chat',json={'question':candidate['question'],'intent':candidate['route_intent'],
                                          'species_scope':'korea'}).json()
        self.assertEqual('answer',second['disposition'])
        executed=graph.call_args.args[0]
        self.assertEqual(('Anas platyrhynchos',),executed.names)
        self.assertEqual('habitat_different_diet',executed.kind)
        self.assertEqual({'species_scope':'korea'},graph.call_args.kwargs)
        self.assertEqual([('천둥오리',),('Anas platyrhynchos',)], [c.args for c in resolver.call_args_list])

    def test_unavailable_name_search_never_executes_graph(self):
        graph=Mock(side_effect=AssertionError('no graph execution'))
        client=TestClient(create_django_app(graph_intent_mode='active',graph_intent_handler=extract_graph_intent,
                       taxon_name_resolution_handler=Mock(side_effect=RuntimeError('private credential')),
                       graph_question_handler=graph))
        body=client.post('/v1/chat',json={'question':'천둥오리와 서식지가 겹치면서 먹이가 다른 새는?'}).json()
        self.assertEqual('clarify',body['disposition']);self.assertIn('후보 검색',body['answer_text'])
        self.assertNotIn('private credential',str(body));graph.assert_not_called()

    def test_candidate_rewrite_has_name_boundaries_and_keeps_other_entities(self):
        from robingraph.api.question_entities import rewrite_name_candidate
        self.assertEqual('물까치와 Pica serica의 공통 분류는?',
                         rewrite_name_candidate('물까치와 까치의 공통 분류는?','까치','Pica serica'))
        for mention in ('숲에사는청둥오리','청둥오리와직박구리','천둥오리와직박구리',
                        '참새목중청둥오리','대한민국에서관찰된청둥오리'):
            with self.subTest(mention=mention),self.assertRaises(ValueError):
                rewrite_name_candidate(mention+'랑 비슷한 식성을 가진 새',mention,'Anas platyrhynchos')
        with self.assertRaises(ValueError):
            rewrite_name_candidate('Anas platyrhynchos conboschas와 비슷한 종','Anas platyrhynchos','Anas acuta')
