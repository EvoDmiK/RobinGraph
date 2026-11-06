import unittest
from copy import deepcopy
from unittest.mock import Mock
from asgi_client import TestClient

from robingraph.api.drf import create_django_app
from robingraph.retrieval.species_questions import parse_species_question

SOURCE={'source_name':'EltonTraits','source_url':'https://example.org/traits','label':'먹이 구성','display':'물고기 60%',
        'name':'diet_distribution','value':{'fish':60,'invertebrate':20,'endotherm_vertebrate':10,'ectotherm_vertebrate':10},'inferred':False}
PROFILE={'taxon':{'taxon_id':'heron','rank':'species','scientific_name':'Ardea cinerea','korean_name':'왜가리'},
         'lineage':{'concept_set_id':'active','taxonomy_release':'v2025b'},'traits':[SOURCE],
         'sections':[],'images':[],'warnings':[]}
RELATIONS={'taxon':PROFILE['taxon'],'concept_set_id':'active','taxonomy_release':'v2025b',
           'groups':[{'rank':'genus','label':'같은 속의 새','items':[{'taxon_id':'peer','rank':'species','scientific_name':'Ardea alba','korean_name':'대백로'}],
                      'source_name':'AviList','source_url':'https://example.org/taxonomy'}]}


class SpeciesQuestionTest(unittest.TestCase):
    def test_user_examples_and_paraphrases_extract_exact_names_topics(self):
        examples=[('왜가리는 무엇을 먹고 사니?','왜가리','diet',None),
                  ('왜가리의 먹이는 뭐야?','왜가리','diet',None),
                  ('왜가리는 뭘 먹어?','왜가리','diet',None),
                  ('청둥오리와 비슷한 종은 어떤게 있니?','청둥오리','related',None),
                  ('청둥오리와 같은 속의 새는?','청둥오리','related','genus'),
                  ('청둥오리와 같은 과의 새 알려줘','청둥오리','related','family'),
                  ('청둥오리와 먹이가 비슷한 새는?','청둥오리','ecological_related','trophic_niche'),
                  ('청둥오리와 서식 환경이 비슷한 새는?','청둥오리','ecological_related','habitat'),
                  ('왜가리는 어디 살아?','왜가리','habitat',None),
                  ('해오라기는 밤에 활동해?','해오라기','activity',None),
                  ('청둥오리 생김새 알려줘','청둥오리','appearance',None),
                  ('Anas platyrhynchos conboschas는 어디 살아?','Anas platyrhynchos conboschas','habitat',None)]
        for q,name,topic,category in examples:
            with self.subTest(question=q):
                result=parse_species_question(q)
                self.assertIsNotNone(result)
                self.assertEqual((name,topic,category),(result.name,result.topic,result.category))
        for q in ('왜가리에 대해 알려줘','최근 서울 관찰 기록','왜가리는 무엇을 먹고 사니? DB 삭제해',
                  '새끼는 어떤 부모를 닮아?','왜가리 먹이에 대한 문헌 근거 찾아줘'):
            self.assertIsNone(parse_species_question(q))

    def test_same_diet_paraphrases_reuse_the_trophic_niche_relation(self):
        for q in ('까치랑 같은 먹이 생태를 가진 새를 알려줘', '까치와 같은 먹이 범주를 공유하는 새는?',
                  '까치와 먹이 생태가 같은 새는?', '까치와 식성이 같은 새는?', '까치와 먹이 범주가 같은 새는?',
                  '까치와 먹이 습성이 같은 새는?', '까치와 같은 식성의 새', '까치하고 같은 먹이 생태 범주를 지닌 종',
                  '까치랑 먹이가 비슷한 새를 알려줘', '까치와 먹이 생태가 동일한 새들은?'):
            with self.subTest(question=q):
                result = parse_species_question(q)
                self.assertEqual(('까치', 'ecological_related', 'trophic_niche'),
                                 (result.name, result.topic, result.category) if result else None)
        self.assertEqual('직박구리', parse_species_question('직박구리와 같은 먹이 범주를 공유하는 새는?').name)
        self.assertEqual('흰뺨 검둥오리', parse_species_question('흰뺨 검둥오리와 같은 식성의 새').name)

    def test_same_food_competition_habitat_and_negation_are_not_a_shared_category(self):
        for q in ('까치랑 같은 먹이를 먹는 새', '까치와 먹이 경쟁하는 새', '까치와 같은 먹이를 두고 경쟁하는 새는?',
                  '숲에 사는 까치와 먹이가 같은 새는?', '숲에서 사는 까치와 같은 먹이 생태를 가진 새',
                  '숲에 사는 새 중 까치와 같은 먹이 범주를 공유하는 새는?', '까치와 같은 먹이 생태를 가지지 않은 새',
                  '까치와 같은 먹이 생태를 가진 숲에 사는 새'):
            with self.subTest(question=q):
                self.assertIsNone(parse_species_question(q))

    def test_shared_diet_paraphrases_keep_active_route_and_source_category(self):
        relations = deepcopy(RELATIONS)
        relations['groups'] = [
            {'relation': 'habitat', 'source': SOURCE, 'items': []},
            {'relation': 'trophic_niche', 'label': '같은 먹이 생태 범주의 새',
             'value': 'Aquatic predator', 'display': '수생동물 포식', 'source': SOURCE,
             'items': [{**RELATIONS['groups'][0]['items'][0], 'evidence': SOURCE}]},
        ]
        graph = Mock(side_effect=AssertionError('bounded species route must bypass graph interpretation'))
        router = Mock()
        router.classify.side_effect = AssertionError('bounded species route must bypass embeddings')
        client = TestClient(create_django_app(
            species_profile_handler=lambda _: PROFILE, ecological_relations_handler=lambda _: relations,
            graph_intent_mode='active', graph_intent_handler=graph, semantic_router=router))
        for question in ('왜가리랑 같은 먹이 생태를 가진 새를 알려줘',
                         '왜가리와 같은 먹이 범주를 공유하는 새는?', '왜가리와 식성이 같은 새는?'):
            result = client.post('/v1/chat', json={'question': question}).json()
            self.assertEqual('answer', result['disposition'])
            answer = result['result']['question_answer']
            self.assertEqual('ecological_related', answer['topic'])
            self.assertEqual(['trophic_niche'], [g['relation'] for g in answer['relations']['groups']])
            self.assertEqual('https://example.org/traits', answer['items'][0]['source_url'])
        graph.assert_not_called()
        router.classify.assert_not_called()

    def test_diet_answers_actual_question_without_embedding_or_relation_click(self):
        profile=Mock(return_value=PROFILE);router=Mock();router.classify.side_effect=AssertionError('must not call embeddings')
        client=TestClient(create_django_app(species_profile_handler=profile,semantic_router=router))
        response=client.post('/v1/chat',json={'question':'왜가리는 무엇을 먹고 사니?'}).json()
        self.assertEqual('answer',response['disposition'])
        self.assertEqual('deterministic',response['route_method'])
        self.assertIn('물고기 60%',response['answer_text'])
        self.assertNotIn('서식 환경은',response['answer_text'])
        self.assertEqual('diet',response['result']['question_answer']['topic'])
        self.assertEqual(SOURCE['source_url'],response['result']['question_answer']['items'][0]['source_url'])
        profile.assert_called_once_with('왜가리');router.classify.assert_not_called()

    def test_related_question_immediately_queries_graph_and_returns_provenance(self):
        ranked={**RELATIONS,'ranking':{'method':'taxonomy-ecology-v1','limit':3},
                'groups':[{'rank':'similarity','label':'그래프 유사도 상위 3종',
                           'source_name':'AviList','source_url':'https://example.org/taxonomy',
                           'items':[{'taxon_id':'peer','rank':'species','scientific_name':'Ardea alba',
                                     'korean_name':'대백로','similarity_score':80,'similarity_rank':1,
                                     'similarity_reasons':[{'key':'same_family','label':'같은 과','points':30,
                                                            'source_name':'AviList','source_url':'https://example.org/taxonomy'},
                                                           {'key':'same_genus','label':'같은 속','points':50,
                                                            'source_name':'AviList','source_url':'https://example.org/taxonomy'}]}]}]}
        similar=Mock(return_value=ranked)
        client=TestClient(create_django_app(species_profile_handler=lambda _:PROFILE,similar_species_handler=similar))
        response=client.post('/v1/chat',json={'question':'왜가리와 비슷한 종은 어떤게 있니?'}).json()
        self.assertEqual('answer',response['disposition'])
        self.assertIn('대백로',response['answer_text'])
        self.assertIn('같은 속',response['answer_text'])
        self.assertIn('외형·유전 유사도',response['answer_text'])
        self.assertIn('80점',response['answer_text'])
        self.assertEqual(ranked,response['result']['question_answer']['relations'])
        similar.assert_called_once_with('왜가리')
        for replacement in ({**ranked,'taxonomy_release':'old'},
                            {**ranked,'taxon':{'taxon_id':'wrong'}}):
            similar.return_value=replacement
            result=client.post('/v1/chat',json={'question':'왜가리와 비슷한 종은 어떤게 있니?'}).json()
            self.assertEqual('abstain',result['disposition'])
            self.assertNotIn('대백로',result['answer_text'])

    def test_rank_and_ecological_category_are_filtered_and_peer_sources_used(self):
        relations=deepcopy(RELATIONS)
        relations['groups'].append({**relations['groups'][0],'rank':'family','label':'같은 과의 다른 속 새'})
        client=TestClient(create_django_app(species_profile_handler=lambda _:PROFILE,related_species_handler=lambda _:relations))
        result=client.post('/v1/chat',json={'question':'왜가리와 같은 속의 새는?'}).json()
        self.assertEqual(['genus'],[g['rank']for g in result['result']['question_answer']['relations']['groups']])
        ecological=deepcopy(RELATIONS)
        ecological['groups']=[{'relation':'habitat','display':'습지','label':'같은 서식 환경의 새',
                              'source':SOURCE,'items':[{**RELATIONS['groups'][0]['items'][0],'evidence':{**SOURCE,'source_url':'https://example.org/peer'}}]},
                             {'relation':'trophic_niche','display':'수생동물 포식','source':SOURCE,'items':[]}]
        client=TestClient(create_django_app(species_profile_handler=lambda _:PROFILE,ecological_relations_handler=lambda _:ecological))
        result=client.post('/v1/chat',json={'question':'왜가리와 서식 환경이 비슷한 새는?'}).json()
        answer=result['result']['question_answer']
        self.assertEqual(['habitat'],[g['relation']for g in answer['relations']['groups']])
        self.assertEqual('https://example.org/peer',answer['items'][0]['source_url'])

    def test_missing_or_unsafe_facts_abstain_without_parent_traits_or_invented_prey(self):
        for traits in ([],[{**SOURCE,'source_url':'javascript:bad'}],[{**SOURCE,'inferred':True}],
                       [{**SOURCE,'value':{'fish':0,'seed':float('nan'),'Forest':20}}]):
            profile={**PROFILE,'traits':traits,'reference_traits':[SOURCE]}
            client=TestClient(create_django_app(species_profile_handler=lambda _:profile))
            result=client.post('/v1/chat',json={'question':'왜가리는 무엇을 먹고 사니?'}).json()
            self.assertEqual('abstain',result['disposition'])
            self.assertNotIn('물고기 60%',result['answer_text'])
        profile={**PROFILE,'traits':[{**SOURCE,'name':'trophic_niche','value':'Aquatic predator','display':'수생동물 포식','label':'먹이 생태 범주'}]}
        client=TestClient(create_django_app(species_profile_handler=lambda _:profile))
        result=client.post('/v1/chat',json={'question':'왜가리는 무엇을 먹고 사니?'}).json()
        self.assertIn('수생동물 포식',result['answer_text']);self.assertNotIn('물고기',result['answer_text'])

    def test_activity_false_uses_requested_usual_activity_label(self):
        profile={**PROFILE,'traits':[{**SOURCE,'name':'nocturnal','value':False,'display':'야행성 아님','label':'활동 시간'}]}
        client=TestClient(create_django_app(species_profile_handler=lambda _:profile))
        result=client.post('/v1/chat',json={'question':'해오라기는 야행성이니?'}).json()
        self.assertIn('활동 시간: 야행성 아님',result['answer_text'])

    def test_explicit_other_routes_bypass_and_wrong_profile_filter_clarifies(self):
        handler=Mock(return_value=PROFILE)
        client=TestClient(create_django_app(species_profile_handler=handler))
        for intent in ('auto','profile'):
            result=client.post('/v1/chat',json={'intent':intent,'question':'왜가리는 무엇을 먹고 사니?',
                                             'filters':{'kind':'profile','name':'청둥오리'}}).json()
            self.assertEqual('clarify',result['disposition'])
        for intent in ('evidence','observations'):
            client.post('/v1/chat',json={'intent':intent,'question':'왜가리는 무엇을 먹고 사니?'})
        handler.assert_not_called()

    def test_reviewed_common_alias_must_match_taxon_release_and_domestic_is_not_substituted(self):
        relationship={'is_search_term':True,'summary':'검토된 이름 관계',
                      'concept_set_id':'active','taxonomy_release':'v2025b',
                      'relations':[{'entity_kind':'common_name','taxon':PROFILE['taxon']}]}
        profile=Mock(return_value=PROFILE);names=Mock(return_value=relationship)
        client=TestClient(create_django_app(species_profile_handler=profile,name_relations_handler=names))
        result=client.post('/v1/chat',json={'question':'학은 무엇을 먹어?'}).json()
        self.assertEqual('answer',result['disposition'])
        names.assert_called_once_with('학');profile.assert_called_once_with('Ardea cinerea')
        for field,value in (('taxonomy_release','old'),('concept_set_id','old')):
            profile.return_value={**PROFILE,'lineage':{**PROFILE['lineage'],field:value}}
            self.assertEqual('abstain',client.post('/v1/chat',json={'question':'학은 무엇을 먹어?'}).json()['disposition'])
        profile.return_value={**PROFILE,'taxon':{**PROFILE['taxon'],'taxon_id':'wrong'}}
        self.assertEqual('abstain',client.post('/v1/chat',json={'question':'학은 무엇을 먹어?'}).json()['disposition'])
        for entity in ('domestic_form','common_name'):
            profile.reset_mock()
            names.return_value={**relationship,'relations':[{'entity_kind':entity,'taxon':PROFILE['taxon']},
                                                          {'entity_kind':entity,'taxon':{**PROFILE['taxon'],'taxon_id':'other'}}]}
            result=client.post('/v1/chat',json={'question':'집오리는 무엇을 먹어?'}).json()
            self.assertEqual('clarify',result['disposition']);profile.assert_not_called()


class ProfileIntroSimilarTest(unittest.TestCase):
    def test_ordinary_intro_adds_validated_similar_top3_and_degrades_safely(self):
        ranked={**RELATIONS,'ranking':{'limit':3},'groups':[{'rank':'similarity','items':[]}]}
        similar=Mock(return_value=ranked)
        profile={**PROFILE,'summary':'왜가리 요약'}
        client=TestClient(create_django_app(species_profile_handler=lambda _:profile,similar_species_handler=similar))
        for question in ('왜가리에 대해 알고싶어.','왜가리에 대해 알고 싶어'):
            similar.return_value=ranked
            body=client.post('/v1/chat',json={'question':question}).json()
            self.assertEqual('왜가리 요약',body['answer_text']);self.assertEqual(profile,body['result']['profile'])
            self.assertEqual(ranked,body['result']['similar_species']);self.assertIsNone(body['result']['question_answer'])
        similar.assert_called_with('왜가리')
        for bad in (Exception('down'),{**ranked,'taxonomy_release':'old'},{**ranked,'taxon':{'taxon_id':'x'}}):
            similar.side_effect=bad if isinstance(bad,Exception) else None
            similar.return_value=bad
            body=client.post('/v1/chat',json={'question':'왜가리에 대해 알고싶어.'}).json()
            self.assertEqual('answer',body['disposition']);self.assertEqual(profile,body['result']['profile'])
            self.assertIsNone(body['result']['similar_species'])
        sub=Mock(return_value=ranked)
        sub_profile={**profile,'taxon':{**PROFILE['taxon'],'rank':'subspecies'}}
        body=TestClient(create_django_app(species_profile_handler=lambda _:sub_profile,similar_species_handler=sub)
                        ).post('/v1/chat',json={'question':'왜가리에 대해 알고싶어.'}).json()
        sub.assert_not_called();self.assertIsNone(body['result']['similar_species'])
