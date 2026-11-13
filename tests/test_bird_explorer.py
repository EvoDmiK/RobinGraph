"""Structured bird explorer: GET /v1/taxa/explore reuses the taxon_traits plan without any NL parsing."""
import json
import unittest
from unittest.mock import Mock

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.retrieval import graph_questions as gq
from robingraph.retrieval.graph_questions import GraphQuestion, TraitCondition, graph_question_answer
from test_taxon_traits import TAXA, Repo, Store, empty_row, peer_row, stats

FOREST = TraitCondition('habitat', 'eq', 'Forest')
FRUIT = TraitCondition('diet_distribution', 'share_gt', 'fruit', 0)
SEED = TraitCondition('diet_distribution', 'share_gt', 'seed', 0)
TAXA = {**TAXA, ('family', 'Pycnonotidae'): 'avilist-taxon:v2025b:23600',
        ('species', 'Hypsipetes amaurotis'): 'avilist-taxon:v2025b:23698'}   # 직박구리, sourced species name


def habitat(value='Forest', url='https://example.org/avonet#1'):
    return {'trait_name': 'habitat', 'value_text': value, 'value_json': None, 'value_num': None, 'unit': None,
            'certainty': None, 'source_url': url, 'citation': None}


def diet(fruit, seed, certainty='A'):
    return {'trait_name': 'diet_distribution', 'value_text': None, 'value_num': None, 'unit': 'percent',
            'value_json': json.dumps({'invertebrate': 100 - fruit - seed, 'fruit': fruit, 'seed': seed}),
            'certainty': certainty, 'source_url': 'https://example.org/elton#%d-%d' % (fruit, seed), 'citation': None}


def explore(repo, taxon=None, conditions=(), species_scope='all', page=1):
    def resolve(name):
        raise AssertionError('the explorer never resolves a species name')
    question = GraphQuestion('taxon_traits', rank_name=taxon, criterion='explore', conditions=conditions, page=page)
    return graph_question_answer(repo, resolve, question, species_scope, store=Store())


class ExplorerPlanTest(unittest.TestCase):
    """The fixed taxon_traits query, provenance checks and diet-share ranking, driven by a structured plan."""

    def test_forest_fruit_seed_in_an_order_ranks_by_the_selected_share_sum(self):
        counts = stats(500, 400, 3)
        rows = [peer_row(1, 'Alpha one', [habitat(), diet(10, 10), diet(10, 10)], counts=counts),
                peer_row(2, 'Beta two', [habitat(), diet(30, 20), diet(30, 20)], counts=counts),
                peer_row(3, 'Gamma three', [habitat(), diet(20, 10), diet(20, 10)], counts=counts)]
        repo = Repo(rows, TAXA)
        payload = explore(repo, 'Passeriformes', (FOREST, FRUIT, SEED))
        self.assertEqual('answer', payload['status'])
        self.assertEqual(['Beta two', 'Gamma three', 'Alpha one'],
                         [item['taxon']['scientific_name'] for item in payload['items']])
        (query, params), = repo.trait_calls()
        self.assertIs(gq.TAXON_DIET_QUERY, query)
        self.assertEqual((TAXA[('order', 'Passeriformes')], 'order', 'species'),
                         (params['root_id'], params['root_rank'], params['target_rank']))
        self.assertEqual([('habitat', 'eq', 'Forest'), ('diet_distribution', 'share_gt', 'fruit'),
                          ('diet_distribution', 'share_gt', 'seed')],
                         [(c['trait_name'], c['op'], c['value']) for c in params['conditions']])
        self.assertEqual(counts, payload['coverage'])
        self.assertIn('요청한 먹이 비율의 합이 높은 순', payload['text'])
        self.assertIn(gq.LIMITATIONS['elton_interpolated'], payload['limitations'])
        texts = [path['text'] for path in payload['items'][0]['paths']]
        self.assertIn('서식 환경: 숲 (Forest)', texts)
        self.assertTrue(any('열매 30%' in text and '확실성 A' in text for text in texts), texts)

    def test_interpolated_diet_evidence_is_never_listed(self):
        rows = [peer_row(1, 'Alpha one', [diet(10, 10, certainty='D1')], counts=stats(5, 5, 1))]
        with self.assertRaises(ValueError):
            explore(Repo(rows, TAXA), conditions=(FRUIT,))

    def test_taxon_only_lists_the_species_of_a_reviewed_korean_order(self):
        rows = [peer_row(1, 'Alpha one', [], counts=stats(2, 2, 2)), peer_row(2, 'Beta two', [], counts=stats(2, 2, 2))]
        repo = Repo(rows, TAXA)
        payload = explore(repo, '참새목')
        (query, params), = repo.trait_calls()
        self.assertIs(gq.TAXON_TRAITS_QUERY, query)
        self.assertEqual([], params['conditions'])
        self.assertEqual(('answer', '참새목 (Passeriformes)의 종', [], [], stats(2, 2, 2)),
                         (payload['status'], payload['title'], payload['conditions'], payload['limitations'],
                          payload['coverage']))
        self.assertEqual('참새목 (Passeriformes) 범위의 종 2종입니다.', payload['text'])

    def test_scope_only_reads_the_whole_scoped_catalog_without_conditions(self):
        repo = Repo([empty_row(stats(0, 0, 0))], TAXA)
        payload = explore(repo, species_scope='korea')
        (query, params), = repo.trait_calls()
        self.assertIs(gq.CATALOG_TRAITS_QUERY, query)
        self.assertEqual(('korea', []), (params['species_scope'], params['conditions']))
        self.assertEqual('empty', payload['status'])

    def test_species_and_subspecies_are_not_ranges(self):
        for surface in ('직박구리', 'Corvus corone', 'Corvus corone cornix'):
            with self.subTest(surface=surface):
                repo = Repo([], TAXA)
                payload = explore(repo, surface, (FRUIT,))
                self.assertEqual(('insufficient_data', 'rank_unsupported'),
                                 (payload['status'], payload['taxon_resolution']))
                self.assertEqual([], repo.trait_calls())

    def test_unknown_and_contradicting_names_are_resolution_failures(self):
        for surface, reason in (('없는목', 'not_found'), ('Nonexistus', 'not_found')):
            with self.subTest(surface=surface):
                payload = explore(Repo([], TAXA), surface, (FOREST,))
                self.assertEqual(reason, payload['taxon_resolution'])

    def test_no_data_zero_matches_and_out_of_range_stay_distinct(self):
        cases = ((stats(10, 0, 0), 'insufficient_data'), (stats(10, 6, 0), 'empty'), (stats(0, 0, 0), 'empty'))
        for counts, status in cases:
            with self.subTest(counts=counts):
                payload = explore(Repo([empty_row(counts)], TAXA), 'Passeriformes', (FOREST,))
                self.assertEqual((status, counts), (payload['status'], payload['coverage']))

    def test_has_more_after_twenty_species(self):
        rows = [peer_row(n, f'Species{n:02d} name', [habitat()], counts=stats(30, 30, 25)) for n in range(1, 22)]
        payload = explore(Repo(rows, TAXA), conditions=(FOREST,))
        self.assertEqual((20, True, 25), (len(payload['items']), payload['has_more'], payload['coverage']['matched']))

    def test_pages_cover_all_matches_without_overlap_and_preserve_coverage(self):
        counts = stats(60, 50, 45)
        rows = [peer_row(n, f'Species{n:02d} name', [habitat()], counts=counts) for n in range(1, 46)]
        pages = []
        for page in (1, 2, 3):
            repo = Repo(rows[:page * 20 + 1], TAXA)
            result = explore(repo, conditions=(FOREST,), page=page)
            self.assertEqual(counts, result['coverage'])
            self.assertEqual({'page': page, 'page_size': 20, 'total': 45, 'total_pages': 3}, result['pagination'])
            self.assertEqual(page < 3, result['has_more'])
            self.assertEqual(page * 20 + 1, repo.trait_calls()[0][1]['limit'])
            pages.extend(item['taxon']['scientific_name'] for item in result['items'])
        self.assertEqual([row['taxon']['scientific_name'] for row in rows], pages)
        last = explore(Repo(rows, TAXA), conditions=(FOREST,), page=10000)
        self.assertEqual(3, last['pagination']['page'])
        self.assertEqual(pages[-5:], [item['taxon']['scientific_name'] for item in last['items']])

    def test_diet_is_ranked_globally_before_paging_and_ties_remain_stable(self):
        counts = stats(45, 45, 45)
        for tied in (False, True):
            rows = [peer_row(n, f'Species{n:02d} name', [diet(10 if tied else n, 0)], counts=counts)
                    for n in range(1, 46)]
            names = []
            for page in (1, 2, 3):
                result = explore(Repo(rows, TAXA), conditions=(FRUIT,), page=page)
                names += [item['taxon']['scientific_name'] for item in result['items']]
            expected = rows if tied else list(reversed(rows))
            self.assertEqual([row['taxon']['scientific_name'] for row in expected], names)

    def test_chat_plans_still_need_a_condition(self):
        with self.assertRaises(ValueError):
            graph_question_answer(Repo([], TAXA), None, GraphQuestion('taxon_traits', rank_name='Passeriformes'),
                                  store=Store())


def payload(status='answer', **extra):
    return {'status': status, 'title': 't', 'text': 'x', 'items': [], 'sources': [], 'limitations': ['L'],
            'has_more': False, 'taxon': None, 'conditions': [], 'coverage': stats(1, 1, 1), 'paths': [], **extra}


class ExplorerApiTest(unittest.TestCase):

    def get(self, query, handler=None):
        return TestClient(create_django_app(graph_question_handler=handler)).get('/v1/taxa/explore' + query)

    def test_structured_request_becomes_the_plan_with_every_condition_kept(self):
        handler = Mock(return_value=payload())
        response = self.get('?species_scope=all&taxon=Passeriformes&habitat=Forest&diet=seed,fruit', handler)
        self.assertEqual(200, response.status_code)
        handler.assert_called_once_with(
            GraphQuestion('taxon_traits', rank_name='Passeriformes', criterion='explore',
                          conditions=(FOREST, FRUIT, SEED)), species_scope='all')
        body = response.json()
        self.assertEqual({'species_scope': 'all', 'taxon': 'Passeriformes', 'habitat': 'Forest',
                          'diet': ['fruit', 'seed'], 'page': 1}, body['query'])
        self.assertEqual({**payload(), 'query': body['query']}, body)

    def test_page_is_forwarded_and_clamped_page_is_echoed(self):
        handler = Mock(return_value=payload(pagination={'page': 2, 'page_size': 20, 'total': 25, 'total_pages': 2}))
        body = self.get('?habitat=Forest&page=99', handler).json()
        handler.assert_called_once_with(GraphQuestion('taxon_traits', criterion='explore', conditions=(FOREST,), page=99), species_scope='all')
        self.assertEqual(2, body['query']['page'])

    def test_every_filter_is_optional(self):
        handler = Mock(return_value=payload())
        for query, plan in (('', GraphQuestion('taxon_traits', criterion='explore')),
                            ('?taxon=%20참새목%20', GraphQuestion('taxon_traits', rank_name='참새목', criterion='explore')),
                            ('?habitat=Human%20Modified',
                             GraphQuestion('taxon_traits', criterion='explore',
                                           conditions=(TraitCondition('habitat', 'eq', 'Human Modified'),))),
                            ('?diet=fruit', GraphQuestion('taxon_traits', criterion='explore', conditions=(FRUIT,)))):
            with self.subTest(query=query):
                handler.reset_mock()
                self.assertEqual(200, self.get(query, handler).status_code)
                handler.assert_called_once_with(plan, species_scope='all')

    def test_invalid_unknown_and_repeated_parameters_are_422_before_any_lookup(self):
        handler = Mock(return_value=payload())
        cases = {
            '?page=0': [('greater_than_equal', ['query', 'page'])],
            '?page=-1': [('greater_than_equal', ['query', 'page'])],
            '?page=1.5': [('int_parsing', ['query', 'page'])],
            '?page=10001': [('less_than_equal', ['query', 'page'])],
            '?page=1&page=2': [('duplicate_parameter', ['query', 'page'])],
            '?limit=5': [('extra_forbidden', ['query', 'limit'])],
            '?habitat=Forest&habitat=Wetland': [('duplicate_parameter', ['query', 'habitat'])],
            '?species_scope=asia': [('literal_error', ['query', 'species_scope'])],
            '?habitat=forest': [('literal_error', ['query', 'habitat'])],
            '?diet=fruit,fruit': [('duplicate_value', ['query', 'diet'])],
            '?diet=meat': [('literal_error', ['query', 'diet', 0])],
            '?diet=': [('literal_error', ['query', 'diet', 0])],
            '?diet=fruit,': [('literal_error', ['query', 'diet', 1])],
            '?taxon=': [('string_too_short', ['query', 'taxon'])],
            '?taxon=Turdus%20merula': [('string_pattern_mismatch', ['query', 'taxon'])],
            '?taxon=Corvus%20corone%20cornix': [('string_pattern_mismatch', ['query', 'taxon'])],
            '?taxon=MATCH%20(n)': [('string_pattern_mismatch', ['query', 'taxon'])],
            '?taxon=' + 'A' + 'a' * 100: [('string_too_long', ['query', 'taxon'])],
            '?q=x&diet=seed&diet=fruit': [('extra_forbidden', ['query', 'q']), ('duplicate_parameter', ['query', 'diet'])],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                response = self.get(query, handler)
                self.assertEqual(422, response.status_code)
                self.assertEqual(expected, [(e['type'], e['loc']) for e in response.json()['detail']])
        handler.assert_not_called()

    def test_unresolved_taxon_is_422_not_an_empty_result(self):
        for reason, kind in (('not_found', 'taxon_not_found'), ('ambiguous', 'taxon_ambiguous'),
                             ('label_rank_conflict', 'taxon_rank_conflict'), ('rank_unsupported', 'taxon_rank_unsupported')):
            with self.subTest(reason=reason):
                handler = Mock(return_value=payload('insufficient_data', taxon_resolution=reason))
                response = self.get('?taxon=직박구리', handler)
                self.assertEqual(422, response.status_code)
                (error,) = response.json()['detail']
                self.assertEqual((kind, ['query', 'taxon'], '직박구리'), (error['type'], error['loc'], error['input']))

    def test_unavailable_or_failing_lookups_are_503_never_empty(self):
        for handler in (None, Mock(side_effect=ValueError('bad provenance')), Mock(return_value={'status': 'odd'})):
            with self.subTest(handler=handler):
                response = self.get('?habitat=Forest', handler)
                self.assertEqual(503, response.status_code)
                self.assertIn('Bird explorer', response.json()['detail'])

    def test_empty_and_insufficient_data_pass_through_and_korea_names_its_basis(self):
        for status in ('empty', 'insufficient_data'):
            with self.subTest(status=status):
                body = self.get('?species_scope=korea&diet=fruit', Mock(return_value=payload(status))).json()
                self.assertEqual(status, body['status'])
                self.assertEqual(['L', gq.LIMITATIONS['korea_record']], body['limitations'])

    def test_real_plan_through_the_api_without_nl_routing(self):
        counts = stats(50, 40, 2)
        rows = [peer_row(1, 'Alpha one', [habitat(), diet(10, 0)], counts=counts),
                peer_row(2, 'Beta two', [habitat(), diet(40, 0)], counts=counts)]
        repo = Repo(rows, TAXA)
        handler = Mock(side_effect=lambda parsed, species_scope='all': graph_question_answer(
            repo, None, parsed, species_scope, store=Store()))
        router, intent = Mock(), Mock()
        app = create_django_app(graph_question_handler=handler, semantic_router=router, graph_intent_handler=intent)
        body = TestClient(app).get('/v1/taxa/explore?taxon=Pycnonotidae&habitat=Forest&diet=fruit').json()
        self.assertEqual(['Beta two', 'Alpha one'], [item['taxon']['scientific_name'] for item in body['items']])
        self.assertEqual(['서식 환경 숲(Forest)', '먹이 구성에 열매 포함'], [c['label'] for c in body['conditions']])
        self.assertEqual('Pycnonotidae', body['taxon']['scientific_name'])
        router.assert_not_called()
        intent.assert_not_called()

    def test_openapi_documents_the_route(self):
        operation = TestClient(create_django_app()).get('/openapi.json').json()['paths']['/v1/taxa/explore']['get']
        self.assertEqual(['species_scope', 'taxon', 'habitat', 'diet', 'page'], [p['name'] for p in operation['parameters']])
        self.assertEqual(list(gq.TRAIT_CONDITIONS['habitat'][2]), operation['parameters'][2]['schema']['enum'])


if __name__ == '__main__':
    unittest.main()
