import re
from types import SimpleNamespace
from unittest import TestCase, mock

from robingraph.retrieval import graph_questions as gq
from robingraph.retrieval.graph_questions import GraphQuestion, graph_question_answer, parse_graph_question
from robingraph.retrieval.species_profile import SpeciesNotFoundError
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage

CONCEPT, RELEASE = 'rg:concept-set:avilist-v2025b', 'v2025b'
AVONET = SimpleNamespace(dataset=SimpleNamespace(id='avonet:test', name='AVONET Supplementary dataset 1'),
                         release=SimpleNamespace(release_key='avonet-r1'),
                         cursor={'concept_set_id': CONCEPT, 'taxonomy_release': RELEASE, 'trait_release': 'avonet-r1'})
ELTON = SimpleNamespace(dataset=SimpleNamespace(id='elton:test', name='AviList and EltonTraits approved reference bundle'),
                        release=SimpleNamespace(release_key='elton-r1'),
                        cursor={'concept_set_id': CONCEPT, 'taxonomy_release': RELEASE, 'trait_release': 'elton-r1'})
TAXONOMY_SOURCE = {'source_name': 'AviList v2025b', 'source_url': 'https://www.avilist.org/checklist/v2025b/'}


def tid(number):
    return f'avilist-taxon:{RELEASE}:{number}'


def lineage(species, species_id, genus, genus_ko, family, family_ko, order, order_ko, korean=None):
    items = (LineageTaxon(tid(f'o-{order}'), 'order', order, None, order_ko),
             LineageTaxon(tid(f'f-{family}'), 'family', family, None, family_ko),
             LineageTaxon(tid(f'g-{genus}'), 'genus', genus, None, genus_ko),
             LineageTaxon(tid(species_id), 'species', species, None, korean))
    return TaxonomyLineage(species, 'AviList', RELEASE, CONCEPT, items)


LINEAGES = {
    '청둥오리': lineage('Anas platyrhynchos', 544, 'Anas', '오리속', 'Anatidae', '오리과', 'Anseriformes', '기러기목', '청둥오리'),
    '흰뺨검둥오리': lineage('Anas zonorhyncha', 540, 'Anas', '오리속', 'Anatidae', '오리과', 'Anseriformes', '기러기목', '흰뺨검둥오리'),
    '직박구리': lineage('Hypsipetes amaurotis', 23698, 'Hypsipetes', None, 'Pycnonotidae', '직박구리과', 'Passeriformes', '참새목', '직박구리'),
    '북섬갈색키위': lineage('Apteryx mantelli', 33, 'Apteryx', None, 'Apterygidae', None, 'Apterygiformes', None),
}


ENGLISH = {540: 'Eastern Spot-billed Duck', 18796: 'Black-naped Oriole', 23698: 'Brown-eared Bulbul'}


def peer(number, science, korean=None, support=None, lineage_nodes=None):
    return {'taxon': {'taxon_id': tid(number), 'rank': 'species', 'scientific_name': science,
                      'korean_name': korean, 'english_name': ENGLISH.get(number)},
            'support': support, 'lineage': lineage_nodes}


def trait_support(name, value, url='https://example.org/avonet#row=1'):
    return {'trait_name': name, 'value_text': value, 'value_json': None, 'certainty': None,
            'source_url': url, 'citation': None}


class FakeRepository:
    def __init__(self, rows=None):
        self.rows, self.calls = rows or {}, []

    def _run(self, query, **params):
        self.calls.append((query, params))
        if query is gq.SOURCE_QUERY:
            return [dict(TAXONOMY_SOURCE, source_url=TAXONOMY_SOURCE['source_url'])]
        if query is gq.TAXON_QUERY:
            return [{'taxon_id': tid('o-' + params['scientific_name']), 'scientific_name': params['scientific_name']}]
        return list(self.rows.get(query, []))

    def queries(self):
        return [query for query, _ in self.calls]


class FakeStore:
    def __init__(self, avonet=AVONET, elton=ELTON):
        self.contexts = {'reference-avonet': avonet, 'reference-taxonomy-traits': elton}

    def active_release_context(self, pipeline):
        return self.contexts.get(pipeline)


def resolve(name):
    return LINEAGES.get(name)


class ParserTest(TestCase):
    def test_user_original_questions_parse_to_exact_kind_and_names(self):
        cases = (
            ('청둥오리와 흰뺨검둥오리는 어떤 관계야?', 'common_taxonomy', ('청둥오리', '흰뺨검둥오리'), {}),
            ('한국에 기록된 오리 중 청둥오리와 같은 속인 종은?', 'korea_same_genus', ('청둥오리',), {'group': '오리'}),
            ('참새목 중 열매를 먹고 사는 새는?', 'order_fruit', (), {'rank_name': '참새목', 'criterion': 'fruit_share'}),
            ('청둥오리와 같은 속에 속하는 새를 보여줘', 'same_genus', ('청둥오리',), {}),
            ('숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?', 'specific_fruit', ('직박구리',), {'habitat': 'Forest'}),
            ('숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?', 'habitat_shared_diet', ('직박구리',), {'habitat': 'Forest'}),
            ('청둥오리와 서식지가 겹치면서 먹이가 다른 새는?', 'habitat_different_diet', ('청둥오리',), {'habitat': None}),
        )
        for question, kind, names, fields in cases:
            with self.subTest(question=question):
                parsed = parse_graph_question(question)
                self.assertEqual((kind, names), (parsed.kind, parsed.names))
                for key, value in fields.items():
                    self.assertEqual(value, getattr(parsed, key))

    def test_assistant_suggested_rephrasing_and_other_target_shapes(self):
        # The insufficient-data answer suggests this wording; it must be accepted as a category question.
        self.assertIn('같은 먹이 범주를 공유하는 새', graph_question_answer(
            FakeRepository(), resolve, parse_graph_question('숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?'))['text'])
        for question, kind in (('숲에 사는 새 중 직박구리와 같은 먹이 범주를 공유하는 새', 'habitat_shared_diet'),
                               ('직박구리와 박새의 공통 분류는 뭐야?', 'common_taxonomy'),
                               ('청둥오리와 흰뺨검둥오리의 분류 경로를 비교해줘', 'common_taxonomy'),
                               ('직박구리와 같은 속 중 국내에서 기록된 새는?', 'korea_same_genus'),
                               ('국내에서 기록된 직박구리와 같은 속 새 알려줘', 'korea_same_genus'),
                               ('참새목 중 과실식 종', 'order_fruit'),
                               ('Passeriformes 중 열매 먹는 새', 'order_fruit'),
                               ('참새목 중 감나무 열매를 먹는 새는?', 'specific_fruit')):
            with self.subTest(question=question):
                self.assertEqual(kind, parse_graph_question(question).kind)
        self.assertEqual('frugivore', parse_graph_question('참새목 중 과실식 종').criterion)
        self.assertEqual('fruit_share', parse_graph_question('참새목에서 열매를 먹는 새 알려줘').criterion)

    def test_order_bird_group_words_are_not_mistaken_for_fruit_plants(self):
        for group in ('새중에서', '새 중에서', '종 중에', '새들 중', '에 속하는 새 중에서'):
            with self.subTest(group=group):
                prefix = '참새목' + (' ' if not group.startswith('에') else '') + group
                parsed = parse_graph_question(prefix + ' 열매를 먹는 새는?')
                self.assertEqual(('order_fruit', '참새목', 'fruit_share'),
                                 (parsed.kind, parsed.rank_name, parsed.criterion))
                specific = parse_graph_question(prefix + ' 감나무 열매를 먹는 새는?')
                self.assertEqual('specific_fruit', specific.kind)

    def test_tree_fruit_variants_and_split_josa_preserve_plant_boundary(self):
        for group in ('새 중에서', '새 중 에서', '새중에서', '종 중 에서'):
            for fruit in ('나무열매', '나무 열매'):
                with self.subTest(group=group, fruit=fruit):
                    q = '참새목 ' + group + ' ' + fruit + '를 먹는 새는?'
                    parsed = parse_graph_question(q)
                    self.assertEqual(('order_fruit', '참새목', 'tree_fruit_share'),
                                     (parsed.kind, parsed.rank_name, parsed.criterion))
            specific = parse_graph_question('참새목 ' + group + ' 감나무 열매를 먹는 새는?')
            self.assertEqual('specific_fruit', specific.kind)

    def test_fruit_wording_matrix_and_common_question_endings(self):
        endings = ('?', ' 어떤게 있어?', ' 어떤 게 있어?', ' 어떤 것이 있나요?',
                   ' 어떤 것들이 있어요?', ' 뭐가 있어?', ' 어떤 종이 있을까?',
                   ' 어떤 새들이 있습니까?', ' 알려줘', ' 알려 주세요', ' 보여줘', ' 알고 싶어요')
        count = 0
        for group in ('중', '중에서', '새중에서', '새 중에서', '새 중 에서', '종 중에', '새들 중'):
            for food, criterion in (('열매를 먹는', 'fruit_share'), ('열매 먹는', 'fruit_share'),
                                    ('열매를 먹고 사는', 'fruit_share'), ('나무열매를 먹는', 'tree_fruit_share'),
                                    ('나무 열매를 먹는', 'tree_fruit_share'), ('과실식', 'frugivore')):
                for ending in endings:
                    q = '참새목 ' + group + ' ' + food + ' 새는' + ending
                    with self.subTest(question=q):
                        parsed = parse_graph_question(q)
                        self.assertIsNotNone(parsed)
                        self.assertEqual(('order_fruit', '참새목', criterion),
                                         (parsed.kind, parsed.rank_name, parsed.criterion))
                    count += 1
            for ending in endings:
                q = '참새목 ' + group + ' 감나무 열매를 먹는 새는' + ending
                with self.subTest(specific=q):
                    self.assertEqual('specific_fruit', parse_graph_question(q).kind)
        self.assertEqual(504, count)
        for prefix, kind in (
                ('청둥오리와 흰뺨검둥오리의 공통 분류는', 'common_taxonomy'),
                ('청둥오리와 같은 속인 새는', 'same_genus'),
                ('한국에 기록된 오리 중 청둥오리와 같은 속인 새는', 'korea_same_genus'),
                ('숲에 사는 새 중 직박구리랑 같은 먹이 범주를 공유하는 새는', 'habitat_shared_diet'),
                ('청둥오리와 서식지가 겹치면서 먹이가 다른 새는', 'habitat_different_diet'),
                ('숲에 사는 새 중 직박구리랑 같은 열매를 먹는 새는', 'specific_fruit')):
            for ending in endings:
                with self.subTest(question=prefix + ending):
                    self.assertEqual(kind, parse_graph_question(prefix + ending).kind)
        for q in ('기후변화에는 어떤 게 있어?', '참새목 중 열매를 먹는 새는 어디에서 사냥해?',
                  '참새목 중 열매를 먹는 새는 독이 있어?', '참새목 중 열매를 먹는 새는 얼마나 커?'):
            with self.subTest(unrelated=q):
                self.assertIsNone(parse_graph_question(q))

    def test_phrases_lists_and_unrelated_questions_are_not_graph_questions(self):
        for question in ('직박구리에 대해 알려줘', '기후변화에 대해 알려줘', '청둥오리와 청둥오리의 공통 분류',
                         '어제 본 새와 같은 속 새 알려줘', '그 새와 같은 속 새 알려줘', '', '왜' * 250 + '와 같은 속 새',
                         '청둥오리와 왜가리와 백로의 공통 분류'):
            with self.subTest(question=question):
                self.assertIsNone(parse_graph_question(question))
        self.assertIsNone(parse_graph_question(None))
        parsed = parse_graph_question('한국에 기록된 오리 중 청둥오리와 같은 속인 종은?')
        self.assertNotIn('중', ''.join(parsed.names))

    def test_fruit_filter_pattern_matches_only_positive_fruit_share(self):
        pattern = re.compile(gq.FRUIT_POSITIVE)
        for value, expected in (('{"fruit":20,"seed":0}', True), ('{"seed":30,"fruit":0.5}', True),
                                ('{"fruit":0,"seed":30}', False), ('{"fruit":0.0}', False),
                                ('{"fruit": 10, "seed": 0}', True), ('{"seed":10}', False)):
            with self.subTest(value=value):
                self.assertEqual(expected, bool(pattern.fullmatch(value)))


class AnswerTest(TestCase):
    def test_common_taxonomy_lists_shared_ranks_and_both_paths_without_distance_claim(self):
        repo = FakeRepository()
        result = graph_question_answer(repo, resolve, parse_graph_question('청둥오리와 흰뺨검둥오리는 어떤 관계야?'))
        self.assertEqual(('answer', 'genus'), (result['status'], result['common_rank']))
        self.assertEqual(['같은 목: 기러기목 (Anseriformes)', '같은 과: 오리과 (Anatidae)', '같은 속: 오리속 (Anas)'],
                         [path['text'] for path in result['paths']])
        self.assertEqual('기러기목 (Anseriformes) > 오리과 (Anatidae) > 오리속 (Anas) > 청둥오리',
                         result['items'][0]['paths'][0]['text'])
        self.assertEqual(TAXONOMY_SOURCE, {k: result['sources'][0][k] for k in TAXONOMY_SOURCE})
        self.assertIn(gq.LIMITATIONS['taxonomy_not_distance'], result['limitations'])

    def test_common_taxonomy_respects_scope_and_never_invents_aves(self):
        outside = graph_question_answer(FakeRepository(), resolve,
                                        GraphQuestion('common_taxonomy', ('청둥오리', '흰뺨검둥오리')), 'outside')
        self.assertEqual(('empty', []), (outside['status'], outside['items']))
        different = graph_question_answer(FakeRepository(), resolve, GraphQuestion('common_taxonomy', ('청둥오리', '북섬갈색키위')))
        self.assertEqual('empty', different['status'])
        self.assertNotIn('Aves', different['text'])
        self.assertNotIn('조류', different['text'])
        with self.assertRaises(SpeciesNotFoundError):
            graph_question_answer(FakeRepository(), resolve, GraphQuestion('common_taxonomy', ('청둥오리', '없는새')))

    def test_korea_same_genus_confirms_group_word_and_uses_korea_scope(self):
        repo = FakeRepository({gq.GENUS_PEERS_QUERY: [peer(540, 'Anas zonorhyncha', '흰뺨검둥오리'),
                                                      peer(999999, 'Anas unknownensis')]})
        result = graph_question_answer(repo, resolve, parse_graph_question('한국에 기록된 오리 중 청둥오리와 같은 속인 종은?'))
        params = dict(repo.calls)[gq.GENUS_PEERS_QUERY]
        self.assertEqual('korea', params['species_scope'])
        self.assertIn(tid(540), params['scope_selected'])
        self.assertEqual('answer', result['status'])
        self.assertEqual(['흰뺨검둥오리'], [item['taxon']['display_name'] for item in result['items']])
        paths = [path['text'] for path in result['items'][0]['paths']]
        self.assertEqual(["범위 확인: ‘오리’ = 오리과 (Anatidae)", '같은 속: 오리속 (Anas)', '국내 기록·분포 근거'], paths[:3])
        self.assertEqual('korea', result['items'][0]['taxon']['distribution']['status'])
        self.assertIn(gq.LIMITATIONS['korea_record'], result['limitations'])

    def test_unconfirmed_group_word_or_conflicting_scope_does_not_answer(self):
        repo = FakeRepository({gq.GENUS_PEERS_QUERY: [peer(540, 'Anas zonorhyncha', '흰뺨검둥오리')]})
        result = graph_question_answer(repo, resolve, GraphQuestion('korea_same_genus', ('청둥오리',), group='매'))
        self.assertEqual('insufficient_data', result['status'])
        self.assertNotIn(gq.GENUS_PEERS_QUERY, repo.queries())
        conflict = graph_question_answer(repo, resolve, GraphQuestion('korea_same_genus', ('청둥오리',)), 'unknown')
        self.assertEqual(('empty', [gq.LIMITATIONS['target_out_of_scope']]), (conflict['status'], conflict['limitations']))

    def test_plain_same_genus_keeps_requested_scope_and_limits_twenty_with_has_more(self):
        rows = [peer(100000 + n, f'Anas test{n:02d}') for n in range(21)]
        repo = FakeRepository({gq.GENUS_PEERS_QUERY: rows})
        result = graph_question_answer(repo, resolve, parse_graph_question('청둥오리와 같은 속에 속하는 새를 보여줘'))
        self.assertEqual('all', dict(repo.calls)[gq.GENUS_PEERS_QUERY]['species_scope'])
        self.assertEqual(21, dict(repo.calls)[gq.GENUS_PEERS_QUERY]['limit'])
        self.assertEqual((20, True), (len(result['items']), result['has_more']))
        self.assertEqual([], result['limitations'])

    def test_order_fruit_share_uses_elton_with_lineage_and_certainty_evidence(self):
        nodes = [{'taxon_id': tid('o-Passeriformes'), 'rank': 'order', 'scientific_name': 'Passeriformes'},
                 {'taxon_id': tid('f-Pycnonotidae'), 'rank': 'family', 'scientific_name': 'Pycnonotidae'},
                 {'taxon_id': tid('g-Hypsipetes'), 'rank': 'genus', 'scientific_name': 'Hypsipetes'},
                 {'taxon_id': tid(23698), 'rank': 'species', 'scientific_name': 'Hypsipetes amaurotis'}]
        support = [{'trait_name': 'diet_distribution', 'value_text': None, 'value_json': '{"fruit":70,"seed":0}',
                    'certainty': 'A', 'source_url': 'https://ndownloader.figshare.com/files/5631081#SpecID=1'}]
        repo = FakeRepository({gq.ORDER_DIET_QUERY: [peer(23698, 'Hypsipetes amaurotis', '직박구리', support, nodes)]})
        result = graph_question_answer(repo, resolve, parse_graph_question('참새목 중 열매를 먹고 사는 새는?'), store=FakeStore())
        params = dict(repo.calls)[gq.ORDER_DIET_QUERY]
        self.assertEqual(('elton:test', 'elton-r1', 'diet_distribution', None, gq.FRUIT_POSITIVE),
                         (params['dataset_id'], params['release'], params['trait_name'], params['value_text'],
                          params['value_json_pattern']))
        self.assertEqual(tid('o-Passeriformes'), params['order_id'])
        paths = [path['text'] for path in result['items'][0]['paths']]
        self.assertEqual('분류 경로: 참새목 (Passeriformes) > 직박구리과 (Pycnonotidae) > Hypsipetes > Hypsipetes amaurotis', paths[0])
        self.assertEqual('먹이 구성: 열매 70% (자료의 먹이 구성비) · EltonTraits 확실성 A', paths[1])
        self.assertIn(gq.LIMITATIONS['elton_interpolated'], result['limitations'])
        self.assertIn(gq.LIMITATIONS['graph_claims_only'], result['limitations'])
        tree = graph_question_answer(repo, resolve, parse_graph_question(
            '참새목 새 중에서 나무열매를 먹는 새는?'), store=FakeStore())
        self.assertEqual(result['items'], tree['items'])
        self.assertIn('나무·풀 구분 없음', tree['title'])
        self.assertIn('나무열매만 먹는 종을 구분한 자료는 없습니다', tree['limitations'][0])

    def test_order_fruit_rejects_interpolated_zero_or_bad_lineage_rows(self):
        nodes = [{'taxon_id': tid('o-Passeriformes'), 'rank': 'order', 'scientific_name': 'Passeriformes'},
                 {'taxon_id': tid(1), 'rank': 'species', 'scientific_name': 'Testus one'}]
        for value_json, certainty, lineage_nodes in (('{"fruit":20}', 'D1', nodes), ('{"fruit":0}', 'A', nodes),
                                                     ('{"fruit":20}', 'A', nodes[1:])):
            support = [{'trait_name': 'diet_distribution', 'value_json': value_json, 'certainty': certainty,
                        'source_url': 'https://example.org/elton'}]
            repo = FakeRepository({gq.ORDER_DIET_QUERY: [peer(1, 'Testus one', None, support, lineage_nodes)]})
            with self.subTest(value_json=value_json, certainty=certainty), self.assertRaises(ValueError):
                graph_question_answer(repo, resolve, GraphQuestion('order_fruit', rank_name='참새목', criterion='fruit_share'),
                                      store=FakeStore())

    def test_frugivore_criterion_uses_avonet_category_and_states_its_limit(self):
        repo = FakeRepository()
        result = graph_question_answer(repo, resolve, parse_graph_question('참새목 중 과실식 종'), store=FakeStore())
        params = dict(repo.calls)[gq.ORDER_TRAIT_QUERY]
        self.assertEqual(('avonet:test', 'trophic_niche', 'Frugivore', None),
                         (params['dataset_id'], params['trait_name'], params['value_text'], params['value_json_pattern']))
        self.assertEqual('empty', result['status'])
        self.assertIn(gq.LIMITATIONS['frugivore_only'], result['limitations'])

    def test_missing_trait_context_or_unknown_order_is_insufficient(self):
        parsed = parse_graph_question('참새목 중 열매를 먹고 사는 새는?')
        self.assertEqual('insufficient_data', graph_question_answer(FakeRepository(), resolve, parsed)['status'])
        stale = SimpleNamespace(**{**vars(ELTON), 'cursor': {'concept_set_id': CONCEPT, 'taxonomy_release': 'v2026a'}})
        self.assertEqual('insufficient_data',
                         graph_question_answer(FakeRepository(), resolve, parsed, store=FakeStore(elton=stale))['status'])
        unknown = graph_question_answer(FakeRepository(), resolve, GraphQuestion('order_fruit', rank_name='없는목', criterion='fruit_share'),
                                        store=FakeStore())
        self.assertEqual('insufficient_data', unknown['status'])

    def test_specific_fruit_is_insufficient_and_never_rewritten_into_a_category(self):
        repo = FakeRepository()
        result = graph_question_answer(repo, resolve, parse_graph_question('숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?'),
                                       store=FakeStore())
        self.assertEqual(('insufficient_data', [], []), (result['status'], result['items'], repo.calls))
        self.assertEqual([gq.LIMITATIONS['no_plant_level_diet']], result['limitations'])

    def _traits(self, habitat, niche):
        base = {'dataset_id': 'avonet:test', 'release': 'avonet-r1', 'inferred': False, 'source_name': 'AVONET'}
        return [{**base, 'name': 'habitat', 'value': habitat, 'source_url': 'https://example.org/avonet#h'},
                {**base, 'name': 'trophic_niche', 'value': niche, 'source_url': 'https://example.org/avonet#n'}]

    def test_shared_diet_is_category_level_with_both_trait_evidence(self):
        support = [trait_support('habitat', 'Forest'), trait_support('trophic_niche', 'Frugivore')]
        repo = FakeRepository({gq.HABITAT_DIET_QUERY: [peer(18796, 'Oriolus chinensis', '꾀꼬리', support)]})
        with mock.patch.object(gq, 'read_traits', return_value=self._traits('Forest', 'Frugivore')):
            result = graph_question_answer(repo, resolve,
                                           parse_graph_question('숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?'),
                                           'korea', store=FakeStore())
        params = dict(repo.calls)[gq.HABITAT_DIET_QUERY]
        self.assertEqual(('Forest', 'Frugivore', True, 'korea'),
                         (params['habitat'], params['niche'], params['same_niche'], params['species_scope']))
        self.assertEqual('answer', result['status'])
        self.assertEqual(['서식 환경: 숲 (Forest)', '먹이 생태 범주: 열매 섭식 (Frugivore)'],
                         [path['text'] for path in result['items'][0]['paths']])
        self.assertIn(gq.LIMITATIONS['category_not_food'], result['limitations'])
        self.assertEqual(tid(23698), result['taxon']['taxon_id'])

    def test_shared_diet_without_habitat_matches_the_niche_only(self):
        support = [trait_support('trophic_niche', 'Frugivore')]
        repo = FakeRepository({gq.SHARED_DIET_QUERY: [peer(18796, 'Oriolus chinensis', '꾀꼬리', support)]})
        with mock.patch.object(gq, 'read_traits', return_value=self._traits('Forest', 'Frugivore')):
            result = graph_question_answer(repo, resolve, GraphQuestion('shared_diet', ('직박구리',)), store=FakeStore())
        params = dict(repo.calls)[gq.SHARED_DIET_QUERY]
        self.assertNotIn(gq.HABITAT_DIET_QUERY, dict(repo.calls))
        self.assertEqual('Frugivore', params['niche'])
        self.assertNotIn('habitat', params)   # the target's habitat is never added
        self.assertEqual('answer', result['status'])
        self.assertEqual(['먹이 생태 범주: 열매 섭식 (Frugivore)'], [p['text'] for p in result['paths']])
        self.assertIn('같은 먹이 생태 범주(열매 섭식)로 분류된 종', result['text'])
        self.assertNotIn('같은 먹이를', result['text'])
        self.assertEqual([gq.LIMITATIONS['category_not_food'], gq.LIMITATIONS['graph_claims_only']], result['limitations'])

    def test_shared_diet_without_own_niche_is_insufficient_without_substitution(self):
        repo = FakeRepository()
        base = {'dataset_id': 'avonet:test', 'release': 'avonet-r1', 'source_name': 'AVONET',
                'source_url': 'https://example.org/avonet#n', 'name': 'trophic_niche', 'value': 'Frugivore'}
        for traits in ([], [{**base, 'inferred': True}], [{**base, 'inferred': False, 'source_scope_kind': 'subspecies_group'}],
                       self._traits('Forest', 'Frugivore')[:1]):
            with self.subTest(traits=traits), mock.patch.object(gq, 'read_traits', return_value=traits):
                result = graph_question_answer(repo, resolve, GraphQuestion('shared_diet', ('직박구리',)), store=FakeStore())
                self.assertEqual(('insufficient_data', []), (result['status'], result['items']))
                self.assertEqual([gq.LIMITATIONS['target_trait_missing']], result['limitations'])
                self.assertNotIn('execution_summary', result)
        self.assertNotIn(gq.SHARED_DIET_QUERY, dict(repo.calls))

    def test_relation_execution_summary_matches_actual_query_scope_even_when_empty(self):
        for kind, habitat, match in (('shared_diet', None, 'same'),
                                     ('habitat_shared_diet', 'Forest', 'same'),
                                     ('habitat_different_diet', None, 'different')):
            with self.subTest(kind=kind):
                repo = FakeRepository()
                parsed = GraphQuestion(kind, ('청둥오리',), habitat=habitat)
                with mock.patch.object(gq, 'read_traits', return_value=self._traits('Wetland', 'Herbivore aquatic')):
                    result = graph_question_answer(repo, resolve, parsed, 'korea', store=FakeStore())
                query = gq.SHARED_DIET_QUERY if kind == 'shared_diet' else gq.HABITAT_DIET_QUERY
                params = dict(repo.calls)[query]
                summary = result['execution_summary']
                self.assertEqual('empty', result['status'])
                self.assertEqual((kind, 'Anas platyrhynchos', match, True, 'trophic_niche'),
                                 (summary['kind'], summary['reference_name'], summary['match'],
                                  summary['exclude_reference'], summary['share_basis']))
                self.assertEqual(params.get('habitat'), summary['habitat'])
                self.assertEqual(params['niche'], summary['niche_value'])
                for key in ('target_id', 'species_scope', 'dataset_id', 'release', 'concept_set_id', 'taxonomy_release'):
                    self.assertEqual(params[key], summary[key])

    def test_different_diet_uses_target_habitat_and_states_no_coexistence(self):
        support = [trait_support('habitat', 'Wetland'), trait_support('trophic_niche', 'Invertivore')]
        repo = FakeRepository({gq.HABITAT_DIET_QUERY: [peer(540, 'Anas zonorhyncha', '흰뺨검둥오리', support)]})
        with mock.patch.object(gq, 'read_traits', return_value=self._traits('Wetland', 'Herbivore aquatic')):
            result = graph_question_answer(repo, resolve, parse_graph_question('청둥오리와 서식지가 겹치면서 먹이가 다른 새는?'),
                                           store=FakeStore())
        params = dict(repo.calls)[gq.HABITAT_DIET_QUERY]
        self.assertEqual(('Wetland', 'Herbivore aquatic', False), (params['habitat'], params['niche'], params['same_niche']))
        self.assertIn(gq.LIMITATIONS['different_diet'], result['limitations'])
        self.assertIn('‘수생 초식’ 범주와 다른 종', result['text'])

    def test_missing_target_traits_or_bad_provenance_fail_closed(self):
        parsed = parse_graph_question('청둥오리와 서식지가 겹치면서 먹이가 다른 새는?')
        with mock.patch.object(gq, 'read_traits', return_value=[]):
            self.assertEqual('insufficient_data',
                             graph_question_answer(FakeRepository(), resolve, parsed, store=FakeStore())['status'])
        bad = [trait_support('habitat', 'Wetland', url='ftp://example.org'), trait_support('trophic_niche', 'Invertivore')]
        repo = FakeRepository({gq.HABITAT_DIET_QUERY: [peer(540, 'Anas zonorhyncha', None, bad)]})
        with mock.patch.object(gq, 'read_traits', return_value=self._traits('Wetland', 'Herbivore aquatic')), \
                self.assertRaises(ValueError):
            graph_question_answer(repo, resolve, parsed, store=FakeStore())

    def test_queries_are_fixed_text_with_scope_and_provenance_guards(self):
        for query in (gq.GENUS_PEERS_QUERY, gq.ORDER_TRAIT_QUERY, gq.HABITAT_DIET_QUERY, gq.SHARED_DIET_QUERY):
            with self.subTest(query=query[:40]):
                self.assertIn("$species_scope='all'", query)
                self.assertLess(query.index('$scope_selected'), query.index('LIMIT $limit'))
                self.assertIn("policy_status:'allowed'", query)
                self.assertNotIn('{', query.split('LIMIT')[1])
        for query in (gq.ORDER_TRAIT_QUERY, gq.HABITAT_DIET_QUERY, gq.SHARED_DIET_QUERY):
            self.assertIn("certainty IN ['A','B','C']", query)
            self.assertIn('source_record_id', query)
        repo = FakeRepository()
        graph_question_answer(repo, resolve, parse_graph_question('청둥오리와 같은 속에 속하는 새를 보여줘'))
        self.assertTrue(all('청둥오리' not in query for query, _ in repo.calls))
        with self.assertRaises(ValueError):
            graph_question_answer(repo, resolve, GraphQuestion('arbitrary'))
        with self.assertRaises(ValueError):
            graph_question_answer(repo, resolve, GraphQuestion('same_genus', ('청둥오리',)), 'KR')


class LegacyFruitRankingTest(TestCase):
    def test_high_share_beyond_page_boundary_is_ranked_before_limit(self):
        rows = []
        for index in range(22):
            support = [{'trait_name': 'diet_distribution', 'value_json': '{"fruit":%d}' % (90 if index == 21 else 10),
                        'certainty': 'A', 'source_url': 'https://example.org/elton'}]
            nodes = [{'taxon_id': tid('o-Passeriformes'), 'rank': 'order', 'scientific_name': 'Passeriformes'},
                     {'taxon_id': tid(index), 'rank': 'species', 'scientific_name': 'Testus ' + chr(97 + index)}]
            rows.append(peer(index, 'Testus ' + chr(97 + index), support=support, lineage_nodes=nodes))
        repo = FakeRepository({gq.ORDER_DIET_QUERY: rows})
        result = graph_question_answer(repo, resolve, GraphQuestion('order_fruit', rank_name='참새목',
                                                                  criterion='fruit_share'), store=FakeStore())
        self.assertEqual([tid(21)] + [tid(i) for i in range(19)],
                         [item['taxon']['taxon_id'] for item in result['items']])
        self.assertTrue(result['has_more'])
        self.assertIn('열매 비율이 높은 순', result['text'])
        self.assertNotIn('LIMIT', gq.ORDER_DIET_QUERY)
