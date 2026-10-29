"""taxon_traits: one taxon at any active rank (or the whole catalog) x AND-combined direct trait conditions."""
import re
from types import SimpleNamespace
from unittest import TestCase

from robingraph.retrieval import graph_questions as gq
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import (GraphIntent, Span, execution_gate, to_graph_question,
                                                      unsupported_food, validate_intent)
from robingraph.retrieval.graph_questions import GraphQuestion, TraitCondition, graph_question_answer
from robingraph.retrieval.species_profile import SpeciesNotFoundError
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage

CONCEPT, RELEASE = 'rg:concept-set:avilist-v2025b', 'v2025b'
AVONET = SimpleNamespace(dataset=SimpleNamespace(id='avonet:test', name='AVONET'),
                         release=SimpleNamespace(release_key='avonet-r1'),
                         cursor={'concept_set_id': CONCEPT, 'taxonomy_release': RELEASE, 'trait_release': 'avonet-r1'})
ELTON = SimpleNamespace(dataset=SimpleNamespace(id='elton:test', name='EltonTraits bundle'),
                        release=SimpleNamespace(release_key='elton-r1'),
                        cursor={'concept_set_id': CONCEPT, 'taxonomy_release': RELEASE, 'trait_release': 'elton-r1'})
FRUIT = TraitCondition('diet_distribution', 'share_gt', 'fruit', 0)
FRUGIVORE = TraitCondition('trophic_niche', 'eq', 'Frugivore')
EXACT = '까마귀과면서 열매를 먹는 새는 어떤 종이 있어?'
# Real AviList v2025b ids for the Corvus examples (read-only TEST probe).
TAXA = {('family', 'Corvidae'): 'avilist-taxon:v2025b:19917', ('genus', 'Corvus'): 'avilist-taxon:v2025b:20236',
        ('order', 'Passeriformes'): 'avilist-taxon:v2025b:12324',
        ('species', 'Corvus corone'): 'avilist-taxon:v2025b:20280',
        ('subspecies', 'Corvus corone cornix'): 'avilist-taxon:v2025b:20282'}


def tid(number):
    return f'avilist-taxon:{RELEASE}:{number}'


def stats(scoped, evaluable, matched):
    return {'scoped': scoped, 'evaluable': evaluable, 'matched': matched}


def peer_row(number, science, support, rank='species', lineage=None, counts=None):
    return {'taxon': {'taxon_id': tid(number), 'rank': rank, 'scientific_name': science, 'korean_name': None,
                      'english_name': None}, 'support': support, 'lineage': lineage, 'stats': counts}


def empty_row(counts):
    return {'taxon': {'taxon_id': None, 'rank': None, 'scientific_name': None, 'korean_name': None,
                      'english_name': None}, 'support': None, 'lineage': None, 'stats': counts}


def fruit_support(amount=30, certainty='A', url='https://example.org/elton#1'):
    return {'trait_name': 'diet_distribution', 'value_text': None,
            'value_json': '{"invertebrate":70,"fruit":%d}' % amount, 'value_num': None, 'unit': 'percent',
            'certainty': certainty, 'source_url': url, 'citation': None}


class Repo:
    def __init__(self, traits=None, taxa=TAXA):
        self.traits, self.taxa, self.calls = traits or [], taxa, []

    def _run(self, query, **params):
        self.calls.append((query, params))
        if query is gq.SOURCE_QUERY:
            return [{'source_name': 'AviList v2025b', 'source_url': 'https://www.avilist.org/checklist/v2025b/'}]
        if query is gq.TAXON_QUERY:
            key = (params['rank'], params['scientific_name'])
            return [{'taxon_id': self.taxa[key], 'scientific_name': key[1]}] if key in self.taxa else []
        if query is gq.TAXON_BY_NAME_QUERY:
            return [{'taxon_id': taxon_id, 'rank': rank, 'scientific_name': name}
                    for (rank, name), taxon_id in self.taxa.items() if name == params['scientific_name']]
        if query in (gq.TAXON_TRAITS_QUERY, gq.CATALOG_TRAITS_QUERY, gq.TAXON_DIET_QUERY, gq.CATALOG_DIET_QUERY):
            return list(self.traits)
        raise AssertionError('unexpected query')

    def trait_calls(self):
        return [(q, p) for q, p in self.calls if q in (gq.TAXON_TRAITS_QUERY, gq.CATALOG_TRAITS_QUERY, gq.TAXON_DIET_QUERY, gq.CATALOG_DIET_QUERY)]


class Store:
    def active_release_context(self, pipeline):
        return {'reference-avonet': AVONET, 'reference-taxonomy-traits': ELTON}.get(pipeline)


def no_resolve(name):
    raise SpeciesNotFoundError(name)


def answer(rank_name, conditions=(FRUIT,), repo=None, resolve=no_resolve, scope='all'):
    repo = repo or Repo()
    return graph_question_answer(repo, resolve, GraphQuestion('taxon_traits', rank_name=rank_name,
                                                              conditions=conditions), scope, store=Store()), repo


class ExactUserQuestion(TestCase):
    """Stage 1: the TEST question that clarified before; any rank, verified against data."""

    def test_exact_question_executes_as_family_fruit_query(self):
        intent = extract_graph_intent(EXACT)
        self.assertEqual(execution_gate(EXACT, intent), 'answer')
        self.assertEqual(intent.kind, 'taxon_traits')
        self.assertEqual(intent.rank, Span('까마귀과', 0, 4))
        self.assertEqual([(c, s.text) for c, s in intent.conditions], [(FRUIT, '열매를')])
        self.assertEqual((intent.residual, intent.negation, intent.ambiguity), ((), (), ()))
        parsed = to_graph_question(EXACT, intent)
        self.assertEqual(parsed, GraphQuestion('taxon_traits', rank_name='까마귀과', conditions=(FRUIT,)))

    def test_exact_question_answer_is_scoped_to_corvidae_species(self):
        lineage = [{'taxon_id': TAXA[('family', 'Corvidae')], 'rank': 'family', 'scientific_name': 'Corvidae'},
                   {'taxon_id': TAXA[('genus', 'Corvus')], 'rank': 'genus', 'scientific_name': 'Corvus'},
                   {'taxon_id': tid(20280), 'rank': 'species', 'scientific_name': 'Corvus corone'}]
        repo = Repo([peer_row(20280, 'Corvus corone', [fruit_support()], lineage=lineage, counts=stats(130, 120, 1))])
        payload, repo = answer('까마귀과', repo=repo)
        self.assertEqual(payload['status'], 'answer')
        (query, params), = repo.trait_calls()
        self.assertIs(query, gq.TAXON_DIET_QUERY)
        self.assertEqual((params['root_id'], params['root_rank'], params['target_rank']),
                         (TAXA[('family', 'Corvidae')], 'family', 'species'))
        self.assertEqual(params['conditions'][0]['trait_name'], 'diet_distribution')
        self.assertEqual(payload['taxon']['rank'], 'family')
        self.assertEqual(payload['coverage'], stats(130, 120, 1))
        self.assertIn('까마귀과 (Corvidae) · 과 (하위 종 전체)', payload['paths'][0]['text'])
        paths = [p['text'] for p in payload['items'][0]['paths']]
        self.assertTrue(paths[0].startswith('분류 경로: 까마귀과 (Corvidae) > 까마귀속 (Corvus) > Corvus corone'))
        self.assertIn('열매 30%', paths[1])

    def test_rank_variants_resolve_from_data_not_suffix(self):
        for text, rank in (('까마귀과', 'family'), ('Corvidae', 'family'), ('까마귀속', 'genus'), ('Corvus', 'genus'),
                           ('Passeriformes', 'order'), ('까마귀', 'species'), ('Corvus corone', 'species'),
                           ('Corvus corone cornix', 'subspecies')):
            with self.subTest(text=text):
                repo = Repo([empty_row(stats(5, 5, 0))])
                payload, repo = answer(text, repo=repo)
                (_, params), = repo.trait_calls()
                self.assertEqual(params['root_rank'], rank)
                self.assertEqual(params['target_rank'], 'subspecies' if rank == 'subspecies' else 'species')
                self.assertEqual(payload['taxon']['rank'], rank)

    def test_extractor_variants(self):
        cases = {
            'Corvidae면서 열매를 먹는 새는 어떤 종이 있어?': 'Corvidae',
            '까마귀속이면서 열매를 먹는 새는?': '까마귀속',
            'Corvus 중에서 열매를 먹는 새 알려줘': 'Corvus',
            '까마귀면서 열매를 먹는 새는 어떤 종이 있어?': '까마귀',
            'Corvus corone 중에서 열매를 먹는 새': 'Corvus corone',
            'Corvus corone cornix면서 열매를 먹는 새는?': 'Corvus corone cornix',
            '앵무새면서 열매를 먹는 새': '앵무새',   # an order label without 목: the data decides the rank
            '까마귀과에 속하는 새 중 열매를 먹는 새': '까마귀과',
        }
        for question, taxon in cases.items():
            with self.subTest(question=question):
                intent = extract_graph_intent(question)
                self.assertEqual(execution_gate(question, intent), 'answer')
                self.assertEqual((intent.kind, intent.rank.text), ('taxon_traits', taxon))

    def test_established_order_shape_keeps_order_fruit(self):
        for question in ('참새목 중에서 열매를 먹는 새는?', '참새목에 속하는 새 중 열매를 먹는 새',
                         'Passeriformes 중 열매 섭식 새'):
            with self.subTest(question=question):
                intent = extract_graph_intent(question)
                self.assertEqual((execution_gate(question, intent), intent.kind), ('answer', 'order_fruit'))
                self.assertEqual(intent.conditions, ())

    def test_whole_catalog_without_taxon(self):
        question = '열매를 먹는 새는 어떤 종이 있어?'
        intent = extract_graph_intent(question)
        self.assertEqual((execution_gate(question, intent), intent.kind, intent.rank), ('answer', 'taxon_traits', None))
        payload, repo = answer(None, repo=Repo([empty_row(stats(11131, 7067, 0))]))
        (query, params), = repo.trait_calls()
        self.assertIs(query, gq.CATALOG_DIET_QUERY)
        self.assertNotIn('root_id', params)
        self.assertIsNone(payload['taxon'])
        self.assertEqual(payload['status'], 'empty')


class RankBoundaries(TestCase):
    def test_modifier_before_taxon_is_never_absorbed(self):
        for question, leftover in (('겨울에만 까마귀과면서 열매를 먹는 새는?', '겨울에만'),
                                   ('흰까마귀과면서 열매를 먹는 새는?', '흰까마귀과면서'),
                                   ('한국 까마귀과면서 열매를 먹는 새는?', '한국')):
            with self.subTest(question=question):
                intent = extract_graph_intent(question)
                self.assertEqual(execution_gate(question, intent), 'clarify')
                self.assertIn(leftover, [r.text for r in intent.residual])
                self.assertNotEqual(intent.rank and intent.rank.text, leftover)

    def test_two_taxa_negation_plant_and_unbuilt_conditions_never_answer(self):
        for question, gate in (('까마귀과와 참새목 중 열매 먹는 새', 'clarify'),
                               ('까마귀과면서 열매를 먹지 않는 새', 'clarify'),
                               ('까마귀과면서 감나무 열매를 먹는 새', 'insufficient_data'),
                               ('까마귀과면서 열매를 먹는 철새는?', 'clarify'),
                               ('까마귀과 중 열매 섭식이면서 열매를 먹는 새', 'clarify')):
            with self.subTest(question=question):
                self.assertEqual(execution_gate(question, extract_graph_intent(question)), gate)

    def test_species_topic_question_is_not_a_taxon_scope(self):
        intent = extract_graph_intent('까마귀는 열매를 먹어?')
        self.assertIsNone(intent.rank)

    def test_subspecies_never_uses_parent_species_traits(self):
        payload, repo = answer('Corvus corone cornix', repo=Repo([empty_row(stats(1, 0, 0))]))
        (_, params), = repo.trait_calls()
        self.assertEqual((params['root_id'], params['target_rank']), (TAXA[('subspecies', 'Corvus corone cornix')],
                                                                      'subspecies'))
        self.assertEqual(payload['status'], 'insufficient_data')
        self.assertIn('아종 단위로 직접 연결된', payload['text'])
        self.assertIn('부모 종의 자료로 대체하지 않았습니다', payload['text'])
        self.assertIn('아종 질문은 부모 종의 형질 자료로 대체하지 않습니다.', payload['limitations'])

    def test_species_without_claim_is_no_data_and_with_claim_not_matching_is_empty(self):
        payload, _ = answer('까마귀', repo=Repo([empty_row(stats(1, 0, 0))]))
        self.assertEqual(payload['status'], 'insufficient_data')
        payload, _ = answer('까마귀', repo=Repo([empty_row(stats(1, 1, 0))]))
        self.assertEqual(payload['status'], 'empty')
        self.assertIn('맞지 않습니다', payload['text'])

    def test_zero_results_and_no_data_differ_for_higher_ranks(self):
        payload, _ = answer('까마귀속', repo=Repo([empty_row(stats(40, 35, 0))]))
        self.assertEqual(payload['status'], 'empty')
        self.assertIn('35종 중', payload['text'])
        payload, _ = answer('까마귀속', repo=Repo([empty_row(stats(40, 0, 0))]))
        self.assertEqual(payload['status'], 'insufficient_data')

    def test_out_of_scope_taxon(self):
        payload, _ = answer('까마귀속', repo=Repo([empty_row(stats(0, 0, 0))]), scope='korea')
        self.assertEqual(payload['status'], 'empty')

    def test_homonym_and_unknown_names_fail_closed_without_trait_query(self):
        # 초승달가슴새류: a family and a genus label; 화식조: a species and a higher label.
        for name, reason in (('초승달가슴새류', 'ambiguous'), ('화식조', 'ambiguous'), ('용용과', 'not_found'),
                             ('까마귀목', 'not_found'), ('Corvoidea', 'not_found')):
            with self.subTest(name=name):
                payload, repo = answer(name)
                self.assertEqual((payload['status'], payload['taxon_resolution']), ('insufficient_data', reason))
                self.assertEqual(repo.trait_calls(), [])

    def test_label_whose_rank_ending_contradicts_its_rank_is_held(self):
        # Pinned label for genus Cinclus is 물까마귀과 (family ending); family Cinclidae has no label.
        taxa = {**TAXA, ('genus', 'Cinclus'): tid(1), ('genus', 'Fregata'): tid(2), ('family', 'Podicipedidae'): tid(3),
                ('order', 'Psittaciformes'): tid(4)}
        for name in ('물까마귀과', '군함조과', '논병아리목', '팔색조속'):
            with self.subTest(name=name):
                payload, repo = answer(name, repo=Repo(taxa=taxa))
                self.assertEqual((payload['status'], payload['taxon_resolution']), ('insufficient_data', 'label_rank_conflict'))
                self.assertIn('학명으로 다시 질문해 주세요', payload['text'])
                self.assertEqual(repo.trait_calls(), [])
        # A label without a rank ending is legitimate: the rank comes from the data.
        payload, repo = answer('앵무새', repo=Repo([empty_row(stats(3, 3, 0))], taxa=taxa))
        self.assertEqual(payload['taxon']['rank'], 'order')
        # The scientific name of the same taxon resolves.
        payload, repo = answer('Cinclus', repo=Repo([empty_row(stats(5, 5, 0))], taxa=taxa))
        self.assertEqual(payload['taxon']['rank'], 'genus')
        intent = extract_graph_intent('물까마귀과면서 열매를 먹는 새는?')
        self.assertEqual(intent.rank.text, '물까마귀과')   # kept as written; the handler holds it

    def test_label_missing_from_active_release_is_not_found(self):
        payload, repo = answer('까마귀과', repo=Repo(taxa={}))
        self.assertEqual(payload['taxon_resolution'], 'not_found')
        self.assertEqual(repo.trait_calls(), [])

    def test_scientific_shape_and_graph_rank_must_agree(self):
        payload, _ = answer('Corvus', repo=Repo(taxa={('species', 'Corvus'): tid(1)}))
        self.assertEqual(payload['taxon_resolution'], 'not_found')

    def test_resolver_species_only_in_same_context(self):
        other = TaxonomyLineage('Corvus corone', 'AviList', 'v2025a', CONCEPT,
                                (LineageTaxon(tid(20280), 'species', 'Corvus corone', None, '송장까마귀'),))
        payload, repo = answer('송장까마귀', resolve=lambda name: other)
        self.assertEqual(payload['taxon_resolution'], 'not_found')
        same = TaxonomyLineage('Corvus corone', 'AviList', RELEASE, CONCEPT,
                               (LineageTaxon(TAXA[('species', 'Corvus corone')], 'species', 'Corvus corone', None,
                                             '송장까마귀'),))
        payload, repo = answer('송장까마귀', resolve=lambda name: same, repo=Repo([empty_row(stats(1, 1, 0))]))
        self.assertEqual(repo.trait_calls()[0][1]['root_rank'], 'species')


class ExecutionGuards(TestCase):
    def test_returned_support_is_rechecked(self):
        for support in (fruit_support(0), fruit_support(certainty='D1'), dict(fruit_support(), source_url='ftp://x'),
                        dict(fruit_support(), trait_name='habitat')):
            with self.subTest(support=support):
                repo = Repo([peer_row(1, 'Corvus a', [support], counts=stats(2, 2, 1))])
                with self.assertRaises(ValueError):
                    answer('까마귀과', repo=repo)

    def test_rows_must_agree_with_statistics(self):
        repo = Repo([peer_row(1, 'Corvus a', [fruit_support()], counts=stats(2, 2, 2))])
        with self.assertRaises(ValueError):
            answer('까마귀과', repo=repo)

    def test_conditions_are_allowlisted(self):
        bad = (TraitCondition('migration', 'eq', 'Migratory'), TraitCondition('habitat', 'eq', 'Mars'),
               TraitCondition('body_mass', 'num_gte', None, 100, 'kg'), TraitCondition('diet_distribution', 'eq', 'fruit'),
               TraitCondition('nocturnal', 'eq', 'true'))
        for condition in bad:
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                answer('까마귀과', (condition,))
        with self.assertRaises(ValueError):
            answer('까마귀과', (TraitCondition('habitat', 'eq', 'Forest'), TraitCondition('habitat', 'eq', 'Wetland')))
        with self.assertRaises(ValueError):
            answer('까마귀과', ())

    def test_query_text_is_fixed(self):
        _, repo = answer('까마귀과', repo=Repo([empty_row(stats(1, 1, 0))]))
        self.assertNotIn('까마귀', gq.TAXON_TRAITS_QUERY + gq.CATALOG_TRAITS_QUERY)
        self.assertEqual(repo.trait_calls()[0][1]['conditions'][0]['pattern'],
                         gq.FRUIT_POSITIVE)

    def test_router_sibling_kind_is_not_a_conflict(self):
        sibling = SimpleNamespace(top='order_fruit')
        intent = extract_graph_intent(EXACT, sibling)
        self.assertEqual((intent.ambiguity, execution_gate(EXACT, intent)), ((), 'answer'))
        # taxon_traits has no router prototypes, so a confident other kind is not evidence against it.
        for top in ('same_genus', 'specific_fruit', 'habitat_shared_diet'):
            self.assertEqual(extract_graph_intent(EXACT, SimpleNamespace(top=top)).ambiguity, ())
        question = '직박구리과면서 열매를 먹는 새는?'   # TEST Jina top: specific_fruit 0.945
        intent = extract_graph_intent(question, SimpleNamespace(top='specific_fruit'))
        self.assertEqual(execution_gate(question, intent), 'answer')
        # Modelled kinds keep the RG-206 kind_tie rule.
        genus = '청둥오리와 같은 속인 새는?'
        self.assertEqual(extract_graph_intent(genus, SimpleNamespace(top='order_fruit')).ambiguity, ('kind_tie',))
        order = '참새목 중에서 열매를 먹는 새는?'
        self.assertEqual(extract_graph_intent(order, SimpleNamespace(top='taxon_traits')).ambiguity, ())

    def test_schema_rejects_bad_conditions(self):
        question = EXACT
        good = extract_graph_intent(question)
        broken = GraphIntent(**{**good.__dict__, 'conditions': ((TraitCondition('migration', 'eq', 'x'),
                                                                 Span('열매를', 6, 9)),)})
        self.assertIn('bad_condition', validate_intent(question, broken))
        moved = GraphIntent(**{**good.__dict__, 'conditions': ((FRUIT, Span('열매를', 0, 3)),)})
        self.assertIn('span_mismatch', validate_intent(question, moved))
        self.assertEqual(execution_gate(question, broken), 'clarify')


class WholeLexiconNames(TestCase):
    """Stage 2 (in-repo part): every pinned label and sourced species name, Korean and scientific, as a taxon span.

    The full 33,684-taxon run against root's TEST inventory is recorded in /tmp/taxonomic-trait-stage2-names.json.
    """

    def test_every_lexicon_name_is_one_exact_taxon_span(self):
        from robingraph.retrieval.taxonomy_lineage import reference_korean_names, sourced_korean_names
        names = {label['name'] for label in reference_korean_names().values()} | {
            item['name'] for item in sourced_korean_names().values()}
        names |= {key.split(':', 1)[1].capitalize() for key in reference_korean_names()}
        names |= {item['scientific_name'] for item in sourced_korean_names().values()}
        names = {name for name in names if re.fullmatch(r'[가-힣]+|[A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){0,2}', name)}
        self.assertGreater(len(names), 2000)
        for name in sorted(names):
            for template in ('{}면서 열매를 먹는 새는?', '{} 중에서 열매를 먹는 새는?'):
                question = template.format(name)
                intent = extract_graph_intent(question)
                with self.subTest(question=question):
                    self.assertEqual((intent.rank and intent.rank.text, intent.residual), (name, ()))
                    self.assertEqual(execution_gate(question, intent), 'answer')


def conditions_of(question):
    intent = extract_graph_intent(question)
    return execution_gate(question, intent), intent, [c for c, _ in intent.conditions]


class FieldLexicon(TestCase):
    """Stage 3: each of the 15 verified fields from the existing display vocabulary, AND-combined."""

    def test_each_field_has_a_reading(self):
        cases = {
            '까마귀과 중 숲에 사는 새': TraitCondition('habitat', 'eq', 'Forest'),
            '까마귀과 중 서식 환경이 습지인 새': TraitCondition('habitat', 'eq', 'Wetland'),
            '까마귀과 중 개방형 서식지에 사는 새': TraitCondition('habitat_density_category', 'eq', 'open'),
            '까마귀과 중 서식지 밀도가 밀집형인 새': TraitCondition('habitat_density_category', 'eq', 'dense'),
            '까마귀과 중 나무 위 생활을 하는 새': TraitCondition('primary_lifestyle', 'eq', 'Insessorial'),
            '까마귀과 중 주 생활 방식이 지상 생활인 새': TraitCondition('primary_lifestyle', 'eq', 'Terrestrial'),
            '참새목 중 육식 새': TraitCondition('trophic_level', 'eq', 'Carnivore'),
            '까마귀과 중 영양 단계가 잡식인 새': TraitCondition('trophic_level', 'eq', 'Omnivore'),
            '까마귀과 중 먹이 생태 범주가 잡식인 새': TraitCondition('trophic_niche', 'eq', 'Omnivore'),
            '까마귀과 중 씨앗 섭식 새': TraitCondition('trophic_niche', 'eq', 'Granivore'),
            '수생 초식 새는?': TraitCondition('trophic_niche', 'eq', 'Herbivore aquatic'),
            '까마귀과 중 먹이 유형이 열매·꽃꿀인 새': TraitCondition('diet_category', 'eq', 'FruiNect'),
            '까마귀과면서 물고기를 먹는 새': TraitCondition('diet_distribution', 'share_gt', 'fish', 0),
            '까마귀과 중 꽃꿀을 먹는 새': TraitCondition('diet_distribution', 'share_gt', 'nectar', 0),
            '까마귀과면서 체중 500g 이상인 새': TraitCondition('body_mass', 'num_gte', None, 500.0, 'g'),
            '까마귀과 중 부리 너비가 10mm 이하인 새': TraitCondition('beak_width', 'num_lte', None, 10.0, 'mm'),
            '까마귀과 중 부리 높이 2cm 미만인 새': TraitCondition('beak_depth', 'num_lt', None, 20.0, 'mm'),
            '까마귀과 중 부리 길이 (전체) 50mm 초과인 새': TraitCondition('beak_length_culmen', 'num_gt', None, 50.0, 'mm'),
            '까마귀과 중 부리 길이 (콧구멍 기준) 30mm 이상인 새': TraitCondition('beak_length_nares', 'num_gte', None, 30.0, 'mm'),
            '까마귀과 중 다리 길이 50mm 이상인 새': TraitCondition('tarsus_length', 'num_gte', None, 50.0, 'mm'),
            '날개 길이 30cm 이상인 까마귀과 새': TraitCondition('wing_length', 'num_gte', None, 300.0, 'mm'),
            '까마귀과 중 꼬리 길이가 20cm보다 긴 새': TraitCondition('tail_length', 'num_gt', None, 200.0, 'mm'),
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                gate, intent, found = conditions_of(question)
                self.assertEqual((gate, intent.kind, found), ('answer', 'taxon_traits', [expected]))
        self.assertEqual({c.trait_name for c in cases.values()} | {'diet_distribution'}, set(gq.TRAIT_CONDITIONS))

    def test_and_combinations_keep_every_condition(self):
        gate, intent, found = conditions_of('까마귀과 중 숲에 살고 체중 300g 이상이며 열매를 먹는 새')
        self.assertEqual(gate, 'answer')
        self.assertEqual(found, [TraitCondition('habitat', 'eq', 'Forest'),
                                 TraitCondition('body_mass', 'num_gte', None, 300.0, 'g'), FRUIT])
        gate, intent, found = conditions_of('숲에 살고 열매를 먹는 새는?')
        self.assertEqual((gate, intent.rank, found), ('answer', None, [TraitCondition('habitat', 'eq', 'Forest'), FRUIT]))
        gate, intent, found = conditions_of('까마귀과 중 열매 섭식이면서 숲에 사는 새')
        self.assertEqual((gate, found), ('answer', [FRUGIVORE, TraitCondition('habitat', 'eq', 'Forest')]))

    def test_ranges_and_explicit_unit_conversion(self):
        for question, expected in (
                ('체중 100~200g인 새', [(100.0, 'num_gte'), (200.0, 'num_lte')]),
                ('까마귀과면서 체중 100g 이상 200g 이하인 새', [(100.0, 'num_gte'), (200.0, 'num_lte')]),
                ('체중 1.5kg 이상인 새', [(1500.0, 'num_gte')]),
                ('체중 0.5 kg 미만인 새', [(500.0, 'num_lt')]),
                ('까마귀과 중 체중 500g보다 무거운 새', [(500.0, 'num_gt')]),
                ('까마귀과 중 체중 500g보다 가벼운 새', [(500.0, 'num_lt')])):
            with self.subTest(question=question):
                gate, _, found = conditions_of(question)
                self.assertEqual((gate, [(c.threshold, c.op) for c in found]), ('answer', expected))

    def test_numbers_never_lose_a_character(self):
        """Signs, separators, exponents, missing units: held with the original text kept, never re-read."""
        for written in ('-1g', '−1g', '+1g', '.5g', '1,000g', '1e3g', '100', 'NaN g', 'Infinity g', '1.5.3g', '100g인'):
            question = f'까마귀과면서 체중 {written} 이상인 새'.replace('g인 이상인', 'g인')
            with self.subTest(question=question):
                gate, intent, found = conditions_of(question)
                self.assertEqual(gate, 'clarify')
                self.assertEqual(found, [])
                self.assertTrue(intent.residual or intent.ambiguity)
        for question in ('까마귀과면서 체중 30cm 이상인 새', '까마귀과면서 날개 길이 3kg 이상인 새',
                         '까마귀과면서 체중 100g 이상 50g 이하인 새', '까마귀과면서 체중 200~100g인 새',
                         '까마귀과면서 부리 길이 50mm 이상인 새', '체중 100 이상인 새'):
            with self.subTest(question=question):
                self.assertEqual(conditions_of(question)[0], 'clarify')

    def test_ambiguous_unsupported_and_contradictory_words_hold(self):
        for question, gate in (('까마귀과면서 잡식인 새', 'clarify'), ('까마귀과 중 사체 섭식 새', 'clarify'),
                               ('까마귀과 중 숲에 살고 습지에 사는 새', 'clarify'), ('까마귀과 중 숲이랑 습지에 사는 새', 'clarify'),
                               ('숲이랑 습지에 사는 새는?', 'clarify'), ('까마귀과면서 야행성인 새', 'clarify'),
                               ('까마귀과 중 큰 새', 'clarify'), ('까마귀과 중 철새', 'clarify'),
                               ('까마귀과 중 국내에 사는 새', 'clarify'), ('까마귀과 중 멸종위기인 숲에 사는 새', 'clarify'),
                               ('까마귀과 중 숲에 살지 않는 새', 'clarify'), ('참새목 중 벌레를 먹는 새는?', 'unsupported'),
                               ('까마귀과 중 숲에 사는 감나무 열매를 먹는 새', 'insufficient_data'),
                               ('겨울에만 숲에 사는 까마귀과 새', 'clarify')):
            with self.subTest(question=question):
                self.assertEqual(conditions_of(question)[0], gate)

    def test_route_boundaries_are_kept(self):
        for question in ('까마귀과 새는 몇 종이야?', '까마귀과의 특징 알려줘', '참새목 중에서 어떤 새가 있어?',
                         '야행성인 새는?', '체중 100g 이상인 새 논문 알려줘', '숲에 사는 새 관찰 기록 보여줘',
                         '직박구리 서식지는 어디야?', '까치 보전 등급은?'):
            with self.subTest(question=question):
                self.assertEqual(conditions_of(question)[0], 'not_graph')
        self.assertEqual(conditions_of('숲에 사는 새 알려줘')[2], [TraitCondition('habitat', 'eq', 'Forest')])
        # The established habitat relation kind is unaffected.
        question = '숲에 사는 새 중 직박구리와 먹이 범주가 같은 새는?'
        self.assertEqual(extract_graph_intent(question).kind, 'habitat_shared_diet')


def measure_support(name, amount, unit, url='https://example.org/avonet#1'):
    return {'trait_name': name, 'value_text': None, 'value_json': None, 'value_num': amount, 'unit': unit,
            'certainty': None, 'source_url': url, 'citation': None}


def text_support(name, value, url='https://example.org/avonet#2'):
    return {'trait_name': name, 'value_text': value, 'value_json': None, 'value_num': None, 'unit': None,
            'certainty': None, 'source_url': url, 'citation': None}


class MultiConditionExecution(TestCase):
    CONDITIONS = (TraitCondition('habitat', 'eq', 'Forest'), TraitCondition('body_mass', 'num_gte', None, 300.0, 'g'),
                  FRUIT)

    def test_parameters_and_paths_for_three_sources(self):
        row = peer_row(20280, 'Corvus corone', [text_support('habitat', 'Forest'), measure_support('body_mass', 512.0, 'g'),
                                                fruit_support()], counts=stats(130, 90, 1))
        payload, repo = answer('까마귀과', self.CONDITIONS, Repo([row]))
        params = repo.trait_calls()[0][1]['conditions']
        self.assertEqual([(p['trait_name'], p['dataset_id'], p['op']) for p in params],
                         [('habitat', 'avonet:test', 'eq'), ('body_mass', 'avonet:test', 'num_gte'),
                          ('diet_distribution', 'elton:test', 'share_gt')])
        self.assertEqual((params[1]['threshold'], params[1]['unit'], params[1]['pattern']), (300.0, 'g', None))
        texts = [p['text'] for p in payload['items'][0]['paths']]
        self.assertEqual(texts, ['서식 환경: 숲 (Forest)', '체중: 512 g', texts[2]])
        self.assertEqual([p['source_name'] for p in payload['items'][0]['paths']], ['AVONET', 'AVONET', 'EltonTraits bundle'])
        self.assertEqual([c['label'] for c in payload['conditions']],
                         ['서식 환경 숲(Forest)', '체중 300g 이상', '먹이 구성에 열매 포함'])

    def test_returned_measurement_is_rechecked(self):
        for support in (measure_support('body_mass', 299.9, 'g'), measure_support('body_mass', 512.0, 'kg'),
                        measure_support('body_mass', float('nan'), 'g'), measure_support('body_mass', True, 'g'),
                        text_support('habitat', 'Wetland')):
            with self.subTest(support=support):
                good = [text_support('habitat', 'Forest'), measure_support('body_mass', 512.0, 'g'), fruit_support()]
                index = 0 if support['trait_name'] == 'habitat' else 1
                good[index] = support
                with self.assertRaises(ValueError):
                    answer('까마귀과', self.CONDITIONS, Repo([peer_row(1, 'Corvus a', good, counts=stats(2, 2, 1))]))

    def test_range_shows_one_measurement_once(self):
        conditions = (TraitCondition('body_mass', 'num_gte', None, 100.0, 'g'), TraitCondition('body_mass', 'num_lte', None, 200.0, 'g'))
        row = peer_row(1, 'Pluvialis fulva', [measure_support('body_mass', 134.9, 'g')] * 2, counts=stats(5, 5, 1))
        payload, _ = answer(None, conditions, Repo([row]))
        self.assertEqual([p['text'] for p in payload['items'][0]['paths']], ['체중: 134.9 g'])


class MeasureLabelForms(TestCase):
    """Display labels "X (Y)" written as "X Y" or "X(Y)" (root's blind run: 2 safe holds, now readable)."""

    def test_parenthetical_label_written_in_words(self):
        for question, expected in (
                ('까마귀과 중 부리 길이 콧구멍 기준이 5mm 이상인 새는?', ('beak_length_nares', 'num_gte', 5.0)),
                ('까마귀과 중 다리 길이 부척이 10mm 이상인 새는?', ('tarsus_length', 'num_gte', 10.0)),
                ('까마귀과 중 부리 길이(전체)가 50mm 초과인 새', ('beak_length_culmen', 'num_gt', 50.0)),
                ('까마귀과 중 부리 길이 전체가 50mm 초과인 새', ('beak_length_culmen', 'num_gt', 50.0)),
                ('까마귀과 중 다리 길이가 50mm 이상인 새', ('tarsus_length', 'num_gte', 50.0)),
                ('까마귀과 중 접은 날개 길이가 30cm 이상인 새', ('wing_length', 'num_gte', 300.0))):
            with self.subTest(question=question):
                gate, _, found = conditions_of(question)
                self.assertEqual((gate, [(c.trait_name, c.op, c.threshold) for c in found]), ('answer', [expected]))

    def test_shared_or_partial_label_still_holds(self):
        for question in ('까마귀과 중 부리 길이 50mm 이상인 새', '까마귀과 중 부리 길이 콧구멍이 5mm 이상인 새',
                         '까마귀과 중 부리 콧구멍 기준이 5mm 이상인 새'):
            with self.subTest(question=question):
                self.assertEqual(conditions_of(question)[0], 'clarify')

    def test_every_measured_field_label_reads(self):
        for name, spec in gq.TRAIT_CONDITIONS.items():
            if spec[1] != 'number':
                continue
            question = f"까마귀과 중 {gq.LABELS[name]}가 10{spec[2]} 이상인 새"
            with self.subTest(question=question):
                gate, _, found = conditions_of(question)
                self.assertEqual((gate, [c.trait_name for c in found]), ('answer', [name]))


class LifestylePhrasing(TestCase):
    """CT-013 (root TEST API: clarify): display values "X 생활" also said "X에서 생활하는"; nothing invented."""

    def test_x_eseo_saenghwal_for_every_lifestyle_value(self):
        for question, value in (('동박새과 중 나무 위에서 생활하는 새는?', 'Insessorial'),
                                ('칼새목 중 공중에서 생활하는 새는?', 'Aerial'),
                                ('꿩과 중 지상에서 생활하는 새', 'Terrestrial'),
                                ('Picidae 중 나무 위에서 생활하는 새', 'Insessorial'),
                                ('까마귀과 중 다양한 생활 방식을 하는 새', 'Generalist'),
                                ('까마귀과 중 나무 위 생활을 하는 새', 'Insessorial'),
                                ('까마귀과 중 주 생활 방식이 지상 생활인 새', 'Terrestrial')):
            with self.subTest(question=question):
                gate, _, found = conditions_of(question)
                self.assertEqual((gate, found), ('answer', [TraitCondition('primary_lifestyle', 'eq', value)]))

    def test_lifestyle_in_and_combinations(self):
        gate, intent, found = conditions_of('Picidae 중 나무 위에서 생활하며 무척추동물을 먹는 새')
        self.assertEqual((gate, found), ('answer', [TraitCondition('primary_lifestyle', 'eq', 'Insessorial'),
                                                    TraitCondition('diet_distribution', 'share_gt', 'invertebrate', 0)]))
        gate, intent, found = conditions_of('나무 위에서 생활하고 열매를 먹는 새는?')
        self.assertEqual((gate, intent.rank, found), ('answer', None, [TraitCondition('primary_lifestyle', 'eq', 'Insessorial'), FRUIT]))

    def test_other_wordings_negation_and_extra_words_still_hold(self):
        for question in ('오리과 중 물에서 생활하는 새는?', '까마귀과 중 땅에서 생활하는 새', '까마귀과 중 나무에서 생활하는 새',
                         '까마귀과 중 나무 위에서 생활하지 않는 새', '까마귀과 중 겨울에 나무 위에서 생활하는 새',
                         '까마귀과 중 나무 위에서 생활하는 큰 새'):
            with self.subTest(question=question):
                self.assertEqual(conditions_of(question)[0], 'clarify')


class UnsupportedFood(TestCase):
    """A food with no diet_distribution key (벌레, 곡식, ...): exact no-DB guidance, never a substitute query."""

    def test_only_a_food_gap_gets_the_guidance(self):
        for question, food in (('까마귀과 중에서 벌레를 먹는 새는?', '벌레'), ('벌레를 먹는 새는?', '벌레'),
                               ('까마귀과 중 벌레를 먹고 숲에 사는 새는?', '벌레'), ('까마귀과 중 곡식을 먹는 새', '곡식'),
                               ('한국에 기록된 벌레를 먹는 새', '벌레'), ('까마귀과 중 육류를 먹는 새', '육류')):
            with self.subTest(question=question):
                gate, intent, _ = conditions_of(question)
                self.assertEqual(('unsupported', ('other',)), (gate, intent.unsupported))   # gold labels unchanged
                self.assertEqual([food], [s.text for s in unsupported_food(question, intent)])
                self.assertIsNone(to_graph_question(question, intent))
        for question in ('까마귀과 중 벌레를 먹고 먹이 경쟁을 하는 새', '같은 과인 벌레 먹는 새', '겨울에 벌레를 먹는 까마귀과 새',
                         '까마귀과 중 벌레를 먹지 않는 새', '까마귀과 중 벌레를 안 먹는 새는?',
                         '까마귀과 중 벌레를 먹고 체중 3파운드 이상인 새', '까마귀과 중 벌레를 먹고 부리 길이 30mm 이상인 새',
                         '까마귀과 중 벌레를 먹고 체중 100g 이상 50g 이하인 새', '까마귀과 중 벌레를 먹고 숲과 습지에 사는 새',
                         '까마귀과 참새목 중 벌레를 먹는 새', '벌레를 잡아먹는 새', '까마귀과 중 어류를 먹는 새'):
            with self.subTest(question=question):
                gate, intent, _ = conditions_of(question)
                self.assertIn(gate, ('unsupported', 'clarify'))
                self.assertEqual((), unsupported_food(question, intent))
        for question in ('까마귀과 중 무척추동물을 먹는 새는?', '까마귀과 중 물고기를 먹는 새', '까마귀과 중 곤충을 먹는 새는?',
                         '까마귀과 중 고기를 먹는 새'):
            self.assertEqual('answer', conditions_of(question)[0])

    def test_guidance_is_exact_and_queries_nothing(self):
        question = '까마귀과 중 벌레를 먹고 체중 100g 이상인 새'
        result = gq.unsupported_food_answer(question, unsupported_food(question, extract_graph_intent(question)))
        self.assertEqual(('insufficient_data', [], False, None, None, []),
                         (result['status'], result['items'], result['has_more'], result['taxon'], result['coverage'],
                          result['conditions']))
        self.assertIn('벌레만 따로 구분한 기록은 현재 조회하는 먹이 성분 자료로 확인할 수 없습니다', result['text'])
        self.assertIn('‘곤충’', result['text'])
        self.assertIn('“까마귀과 중 곤충을 먹고 체중 100g 이상인 새”', result['text'])   # only the food word changes
        self.assertIn('범주를 바꿔 조회하지 않았습니다.', result['text'])
        self.assertEqual([gq.LIMITATIONS['no_food_key']], result['limitations'])
        joined = '벌레와 곡식을 먹는 새'
        self.assertEqual((), unsupported_food(joined, extract_graph_intent(joined)))   # 벌레와: unread, held

    def test_food_spans_are_checked_against_the_question(self):
        question = '까마귀과 중 벌레를 먹는 새는?'
        food = Span('벌레', 7, 9)
        self.assertEqual((food,), unsupported_food(question, GraphIntent(None, unsupported=('other',),
                                                                         unsupported_food=(food,))))
        for intent in (GraphIntent(None, unsupported_food=(food,)),
                       GraphIntent(None, unsupported=('other',), unsupported_food=(Span('벌레', 0, 2),)),
                       GraphIntent(None, unsupported=('other',), unsupported_food=(Span('까마귀과', 0, 4),)),
                       GraphIntent(None, unsupported=('other', 'predation'), unsupported_food=(food,))):
            self.assertEqual((), unsupported_food(question, intent))


class InsectAndMeatAliases(TestCase):
    """곤충 searches the invertebrate share (shown as such), 고기 the three vertebrate shares; sources are unchanged."""

    def test_aliases_read_as_source_keys_and_former_names_still_work(self):
        share = lambda key: [TraitCondition('diet_distribution', 'share_gt', key, 0)]
        for question, conditions in (('까마귀과 중에서 곤충을 먹는 새는?', share('invertebrate')),
                                     ('까마귀과 중 무척추동물을 먹는 새는?', share('invertebrate')),
                                     ('곤충을 먹는 새', share('invertebrate')),
                                     ('까마귀과 중 고기를 먹는 새', share('meat')),
                                     ('까마귀과 중 척추동물을 먹는 새', share('meat')),
                                     ('까마귀과 중 물고기를 먹는 새', share('fish')),
                                     ('까마귀과 중 사체를 먹는 새', share('carrion')),
                                     ('까마귀과 중 온혈 척추동물을 먹는 새', share('endotherm_vertebrate')),
                                     ('까마귀과 중 먹이 유형이 곤충인 새', [TraitCondition('diet_category', 'eq', 'Invertebrate')]),
                                     ('까마귀과 중 먹이 유형이 무척추동물인 새', [TraitCondition('diet_category', 'eq', 'Invertebrate')]),
                                     ('까마귀과 중 먹이 유형이 척추동물·물고기·사체인 새',
                                      [TraitCondition('diet_category', 'eq', 'VertFishScav')]),
                                     ('까마귀과 중 먹이 유형이 고기·물고기·사체인 새',
                                      [TraitCondition('diet_category', 'eq', 'VertFishScav')]),
                                     ('까마귀과 중 고기 (온혈 척추동물)를 먹는 새', share('endotherm_vertebrate')),
                                     ('까마귀과 중 곤충 섭식 새', [TraitCondition('trophic_niche', 'eq', 'Invertivore')]),
                                     ('까마귀과 중 무척추동물 섭식 새', [TraitCondition('trophic_niche', 'eq', 'Invertivore')]),
                                     ('까마귀과 중 고기 섭식 새', [TraitCondition('trophic_niche', 'eq', 'Vertivore')]),
                                     ('까마귀과 중 척추동물 섭식 새', [TraitCondition('trophic_niche', 'eq', 'Vertivore')])):
            with self.subTest(question=question):
                self.assertEqual(('answer', conditions), (conditions_of(question)[0], conditions_of(question)[2]))
        for question in ('까마귀과 중 곤충을 안 먹는 새는?', '겨울에 곤충을 먹는 까마귀과 새',
                         '까마귀과 중 곤충을 먹고 먹이 경쟁을 하는 새', '까마귀과 중 고기를 먹지 않는 새'):
            with self.subTest(question=question):
                self.assertIn(conditions_of(question)[0], ('clarify', 'unsupported'))

    def test_meat_is_any_vertebrate_share_never_fish_or_carrion(self):
        meat = TraitCondition('diet_distribution', 'share_gt', 'meat', 0)
        pattern = gq._condition_parameter(meat, {'dataset_id': 'd', 'release': 'r'})['pattern']
        support = lambda value: {'trait_name': 'diet_distribution', 'source_url': 'https://example.org/e',
                                 'value_json': value, 'certainty': 'A'}
        fish_only = ('{"invertebrate":10,"endotherm_vertebrate":0,"ectotherm_vertebrate":0,"fish":60,'
                     '"unknown_vertebrate":0,"carrion":30}')
        self.assertIsNone(re.fullmatch(pattern, fish_only))
        with self.assertRaises(ValueError):
            gq._support_text(meat, support(fish_only))
        mixed = '{"endotherm_vertebrate":0,"ectotherm_vertebrate":10,"fish":40,"unknown_vertebrate":20,"carrion":0}'
        self.assertIsNotNone(re.fullmatch(pattern, mixed))
        self.assertIn('고기 (온혈 척추동물·변온 척추동물·기타 척추동물) 30% (변온 척추동물 10% · 기타 척추동물 20%)',
                      gq._support_text(meat, support(mixed)))

    def test_answers_state_what_the_source_category_covers(self):
        insect = TraitCondition('diet_distribution', 'share_gt', 'invertebrate', 0)
        self.assertEqual('먹이 구성에 곤충 포함', gq.condition_label(insect))
        self.assertIn('곤충이 아닌 무척추동물', gq.SHARE_SCOPE['invertebrate'])
        self.assertIn('물고기·사체 성분은 포함하지 않습니다', gq.SHARE_SCOPE['meat'])
        self.assertEqual('고기·물고기·사체', gq.VALUES['VertFishScav'])   # never 고기 alone
        for key, source in (('invertebrate', '무척추동물'), ('endotherm_vertebrate', '온혈 척추동물'),
                            ('ectotherm_vertebrate', '변온 척추동물'), ('unknown_vertebrate', '기타 척추동물'),
                            ('Invertebrate', '무척추동물'), ('Invertivore', '무척추동물 섭식'), ('Vertivore', '척추동물 섭식')):
            self.assertEqual(source, gq.SOURCE_CATEGORY[key])   # original source scope is preserved


class DietRanking(TestCase):
    def rows(self, compositions, conditions=(FRUIT,)):
        import json
        result = []
        for index, composition in enumerate(compositions):
            claim = dict(fruit_support(), value_json=json.dumps(composition))
            support = [claim if c.op == 'share_gt' else
                       {'trait_name': c.trait_name, 'value_text': c.value, 'source_url': 'https://example.org/avonet'}
                       for c in conditions]
            result.append(peer_row(index + 1, 'Testus ' + chr(97 + index), support,
                                   counts=stats(len(compositions), len(compositions), len(compositions))))
        return result

    def test_later_high_share_precedes_first_page_and_ties_keep_existing_order(self):
        rows = self.rows([{'fruit': 10}] * 20 + [{'fruit': 90}, {'fruit': 10}])
        result, repo = answer(None, repo=Repo(rows))
        self.assertEqual([tid(21)] + [tid(i) for i in range(1, 20)],
                         [item['taxon']['taxon_id'] for item in result['items']])
        self.assertTrue(result['has_more'])
        self.assertEqual(22, result['coverage']['matched'])
        query, _ = repo.trait_calls()[0]
        self.assertNotIn('LIMIT', query)
        self.assertIn('먹이 비율이 높은 순', result['text'])

    def test_every_food_component_ranks_its_own_share(self):
        for key in gq.DIET_SHARE_KEYS:
            with self.subTest(key=key):
                condition = TraitCondition('diet_distribution', 'share_gt', key, 0)
                rows = self.rows([{key: 10}, {key: 90}], (condition,))
                result, _ = answer(None, (condition,), Repo(rows))
                self.assertEqual([tid(2), tid(1)], [item['taxon']['taxon_id'] for item in result['items']])

    def test_multiple_foods_sum_shares_independent_of_condition_order(self):
        fish = TraitCondition('diet_distribution', 'share_gt', 'fish', 0)
        for conditions in ((FRUIT, fish), (fish, FRUIT)):
            rows = self.rows([{'fruit': 60, 'fish': 10}, {'fruit': 40, 'fish': 50}], conditions)
            result, _ = answer(None, conditions, Repo(rows))
            self.assertEqual([tid(2), tid(1)], [item['taxon']['taxon_id'] for item in result['items']])

    def test_overlapping_meat_group_does_not_double_count_or_include_fish_carrion(self):
        meat = TraitCondition('diet_distribution', 'share_gt', 'meat', 0)
        warm = TraitCondition('diet_distribution', 'share_gt', 'endotherm_vertebrate', 0)
        conditions = (meat, warm)
        rows = self.rows([{'endotherm_vertebrate': 40, 'ectotherm_vertebrate': 0, 'fish': 30, 'carrion': 30},
                          {'endotherm_vertebrate': 10, 'ectotherm_vertebrate': 20, 'unknown_vertebrate': 20}], conditions)
        result, _ = answer(None, conditions, Repo(rows))
        self.assertEqual([tid(2), tid(1)], [item['taxon']['taxon_id'] for item in result['items']])

    def test_additional_category_filters_do_not_become_ranking_scores(self):
        conditions = (FRUGIVORE, FRUIT)
        rows = self.rows([{'fruit': 10}, {'fruit': 90}], conditions)
        result, _ = answer(None, conditions, Repo(rows))
        self.assertEqual([tid(2), tid(1)], [item['taxon']['taxon_id'] for item in result['items']])
        result, repo = answer(None, (FRUGIVORE,), Repo(self.rows([{}, {}], (FRUGIVORE,))))
        self.assertEqual([tid(1), tid(2)], [item['taxon']['taxon_id'] for item in result['items']])
        self.assertIs(repo.trait_calls()[0][0], gq.CATALOG_TRAITS_QUERY)
        self.assertNotIn('비율이 높은 순', result['text'])

    def test_invalid_or_conflicting_support_never_becomes_a_rank_score(self):
        for value in ('not-json', '{"fruit":true}', '{"fruit":NaN}', '{"fruit":101}'):
            rows = self.rows([{'fruit': 10}])
            rows[0]['support'][0]['value_json'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                answer(None, repo=Repo(rows))
        fish = TraitCondition('diet_distribution', 'share_gt', 'fish', 0)
        rows = self.rows([{'fruit': 30, 'fish': 10}], (FRUIT, fish))
        rows[0]['support'][1] = dict(rows[0]['support'][1], value_json='{"fruit":30,"fish":60}')
        with self.assertRaisesRegex(ValueError, 'Conflicting diet composition'):
            answer(None, (FRUIT, fish), Repo(rows))
