from dataclasses import replace
import importlib.util
from pathlib import Path
from unittest import TestCase

from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import GraphIntent, execution_gate, to_graph_question, validate_intent
from robingraph.retrieval.graph_questions import GraphQuestion
from robingraph.retrieval.graph_semantic_router import KindCandidates

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('eval_graph_questions', ROOT / 'scripts/eval_graph_questions.py')
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)

ENDINGS = ('?', ' 어떤게 있어?', ' 어떤 게 있어?', ' 어떤 것이 있나요?', ' 어떤 것들이 있어요?', ' 뭐가 있어?',
           ' 어떤 종이 있을까?', ' 어떤 새들이 있습니까?', ' 알려줘', ' 알려 주세요', ' 보여줘', ' 알고 싶어요')


def gate(question, candidates=()):
    intent = extract_graph_intent(question, candidates)
    return execution_gate(question, intent), intent


class TuningTests(TestCase):
    def test_tuning_dispositions_and_no_false_execution(self):
        valid, errors = evaluator.check(evaluator.load(ROOT / 'data/eval/graph_questions/tuning.jsonl'))
        self.assertEqual([], errors)
        # The immutable 2026-10-22 gold predates the user-approved insect display alias.
        # Its superseded case is checked under the new policy below, not scored as old-policy accuracy.
        obsolete = [item for item, _ in valid if item['id'] == 'GGQ-T-049']
        self.assertEqual(1, len(obsolete))
        self.assertEqual('unsupported', obsolete[0]['expected']['disposition'])
        current = extract_graph_intent(obsolete[0]['question'])
        self.assertEqual('answer', execution_gate(obsolete[0]['question'], current))
        query = to_graph_question(obsolete[0]['question'], current)
        self.assertEqual('taxon_traits', query.kind)
        self.assertEqual(('diet_distribution', 'share_gt', 'invertebrate', 0),
                         (query.conditions[0].trait_name, query.conditions[0].op,
                          query.conditions[0].value, query.conditions[0].threshold))
        valid = [(item, gold) for item, gold in valid if item['id'] != 'GGQ-T-049']
        items, _ = evaluator.score(valid, analyze=evaluator.extractor_analyze)
        result = evaluator.metrics(items)['gated']
        self.assertEqual(0, result['false_execution']['hits'])
        self.assertEqual(0, result['condition_loss_executed'])
        known = {}
        self.assertEqual(result['coverage']['n'] - len(known), result['coverage']['hits'])
        for item, _ in valid:
            intent = extract_graph_intent(item['question'])
            with self.subTest(question=item['question']):
                self.assertEqual('extractor', intent.source)
                self.assertEqual((), validate_intent(item['question'], intent))
                self.assertEqual(known.get(item['id'], item['expected']['disposition']),
                                 execution_gate(item['question'], intent))


class ExistingExpressionTests(TestCase):
    """The regex-era 504/664 forms keep the same fixed query (expected values, not the parser itself)."""

    def test_order_fruit_matrix(self):
        count = 0
        for group in ('중', '중에서', '새중에서', '새 중에서', '새 중 에서', '종 중에', '새들 중'):
            for food, criterion in (('열매를 먹는', 'fruit_share'), ('열매 먹는', 'fruit_share'),
                                    ('열매를 먹고 사는', 'fruit_share'), ('나무열매를 먹는', 'tree_fruit_share'),
                                    ('나무 열매를 먹는', 'tree_fruit_share'), ('과실식', 'frugivore')):
                for ending in ENDINGS:
                    q = '참새목 ' + group + ' ' + food + ' 새는' + ending
                    with self.subTest(q=q):
                        self.assertEqual(GraphQuestion('order_fruit', (), '참새목', None, criterion),
                                         to_graph_question(q, extract_graph_intent(q)))
                    count += 1
            for ending in ENDINGS:
                q = '참새목 ' + group + ' 감나무 열매를 먹는 새는' + ending
                with self.subTest(q=q):
                    self.assertEqual('insufficient_data', gate(q)[0])
                    self.assertEqual('감나무', extract_graph_intent(q).specific_plant.text)
        self.assertEqual(504, count)

    def test_other_kinds_with_common_endings(self):
        cases = (('청둥오리와 흰뺨검둥오리의 공통 분류는', GraphQuestion('common_taxonomy', ('청둥오리', '흰뺨검둥오리'))),
                 ('청둥오리와 같은 속인 새는', GraphQuestion('same_genus', ('청둥오리',))),
                 ('한국에 기록된 오리 중 청둥오리와 같은 속인 새는',
                  GraphQuestion('korea_same_genus', ('청둥오리',), group='오리')),
                 ('숲에 사는 새 중 직박구리랑 같은 먹이 범주를 공유하는 새는',
                  GraphQuestion('habitat_shared_diet', ('직박구리',), habitat='Forest')),
                 ('청둥오리와 서식지가 겹치면서 먹이가 다른 새는', GraphQuestion('habitat_different_diet', ('청둥오리',))),
                 ('숲에 사는 새 중 직박구리랑 같은 열매를 먹는 새는',
                  GraphQuestion('specific_fruit', ('직박구리',), habitat='Forest')))
        for prefix, expected in cases:
            for ending in ENDINGS:
                with self.subTest(q=prefix + ending):
                    self.assertEqual(expected, to_graph_question(prefix + ending, extract_graph_intent(prefix + ending)))

    def test_original_user_questions(self):
        for q, kind in (('청둥오리와 흰뺨검둥오리는 어떤 관계야?', 'common_taxonomy'),
                        ('한국에 기록된 오리 중 청둥오리와 같은 속인 종은?', 'korea_same_genus'),
                        ('참새목 중 열매를 먹고 사는 새는?', 'order_fruit'),
                        ('청둥오리와 같은 속에 속하는 새를 보여줘', 'same_genus'),
                        ('숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?', 'habitat_shared_diet'),
                        ('청둥오리와 서식지가 겹치면서 먹이가 다른 새는?', 'habitat_different_diet'),
                        ('참새목에 속한 새 가운데 열매를 먹는 종류 좀 알려줄래?', 'order_fruit'),
                        ('열매 먹는 참새목 새를 찾아 줘', 'order_fruit'),
                        ('숲에서 살면서 직박구리와 식성이 같은 새가 궁금해', 'habitat_shared_diet'),
                        ('청둥오리랑 서식지는 같지만 먹이는 다른 종을 찾아줘', 'habitat_different_diet')):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual(('answer', kind), (disposition, intent.kind))
        self.assertEqual('insufficient_data', gate('숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?')[0])


class RouteBoundaryTests(TestCase):
    def test_questions_without_a_graph_cue_are_clean_not_graph(self):
        for q in ('청둥오리의 학명은 뭐야?', '직박구리는 무엇을 먹어?', '기후변화가 철새에 미치는 영향은?',
                  '참새목은 어떤 특징이 있어?', '청둥오리 사진 보여줘', '직박구리 서식지는 어디야?',
                  '참새 관찰 기록 보여줘', '참새목 분류 계통 알려줘', '청둥오리 먹이 알려줘',
                  '한국에 기록된 새는?', '오늘 서울에서 본 새 기록 남겨줘', '직박구리와 비슷한 종은?',
                  '청둥오리 아종 알려줘', '까치 보전 등급은?'):
            with self.subTest(q=q):
                self.assertEqual(GraphIntent(None, source='extractor'), extract_graph_intent(q))
                self.assertEqual('not_graph', gate(q)[0])
        # '숲에 사는 새 알려줘' moved: a clear trait condition is now a whole-catalog taxon_traits query (root, taxon traits).

    def test_literature_or_observation_requests_go_to_their_routes(self):
        for q in ('참새목에서 열매를 먹는 새에 대한 논문을 찾아줘', '직박구리를 잡아먹는 새에 대한 문헌을 검색해줘',
                  '청둥오리와 같은 속 새의 관찰 기록 보여줘', '숲에 사는 새 중 직박구리와 먹이 범주가 같은 새 연구 알려줘'):
            with self.subTest(q=q):
                self.assertEqual(GraphIntent(None, source='extractor'), extract_graph_intent(q))
        for q in ('참새목 중 열매를 먹는 새 알려주고 관련 논문도 찾아줘', '청둥오리와 같은 속인 새와 사진도 보여줘'):
            with self.subTest(q=q):
                self.assertEqual('clarify', gate(q)[0])

    def test_unconsumed_or_injected_text_is_never_executed(self):
        base = '참새목 중 열매를 먹는 새는?'
        self.assertEqual('answer', gate(base)[0])
        for q in ('MATCH (n) DETACH DELETE n 참새목 중 열매를 먹는 새는?', '참새목 중 열매를 먹는 새는?; DROP',
                  '참새목 중 열매를 먹는 새는? RETURN n', '참새목 중 열매를 먹는 새는 {kind: x}?'):
            with self.subTest(q=q):
                self.assertNotEqual('answer', gate(q)[0])

    def test_blocking_words_are_never_fillers(self):
        additions = ('겨울에', '여름에만', '세 마리 이상', '많이', '대부분', '주로', '멸종위기인', '천연기념물인',
                     '보호종인', '제주도에서', '서울에 사는', '텃새인', '철새인', '작은', '희귀한', '흔한', '최근', '1종만')
        for addition in additions:
            for q in (f'참새목 중 {addition} 열매를 먹는 새는?', f'{addition} 청둥오리와 같은 속인 새는?',
                      f'숲에 사는 새 중 {addition} 직박구리와 먹이 범주가 같은 새는?'):
                with self.subTest(q=q):
                    disposition, intent = gate(q)
                    self.assertNotEqual('answer', disposition)
                    self.assertTrue(intent.residual or intent.negation or intent.ambiguity)
        for q in ('참새목 중 열매를 안 먹는 새는?', '청둥오리와 같은 속이 아닌 새는?', '직박구리 말고 숲에 사는 과실식 새는?',
                  '참새목 중 감나무 열매는 먹지 않는 새', '청둥오리와 서식지가 겹치지 않는 새는?'):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual('clarify', disposition)
                self.assertTrue(intent.negation)

    def test_specific_plant_or_same_fruit_is_never_relaxed(self):
        for q in ('참새목 중 산수유 열매를 먹는 새는?', '마가목 열매 먹는 새 알려줘', '참새목 중에서 감 먹는 새 있어?',
                  '직박구리와 똑같은 열매를 먹는 새', '감나무 열매를 먹는 참새목 새는?'):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual(('insufficient_data', 'specific_fruit'), (disposition, intent.kind))
                self.assertIsNone(intent.diet)

    def test_unsupported_relations_and_missing_parts(self):
        for q, code in (('직박구리와 같이 사는 새는?', 'co_occurrence'), ('청둥오리와 진화적으로 가장 가까운 새는?',
                                                              'evolutionary_distance'),
                        ('청둥오리를 잡아먹는 새는?', 'predation'), ('직박구리와 먹이 경쟁하는 새', 'other'),
                        ('청둥오리와 같은 과인 새는?', 'other')):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual(('unsupported', (code,)), (disposition, intent.unsupported))
        for q in ('같은 속인 새 알려줘', '서식지가 겹치면서 먹이가 다른 새는?', '오리와 같은 속인 새는?',
                  '청둥오리와 흰뺨검둥오리와 같은 속인 새', '숲이랑 습지에 사는 새 중 직박구리와 먹이가 같은 새',
                  '숲에 사는 새 중 직박구리와 먹이가 비슷한 새'):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual('clarify', disposition)
                self.assertTrue(intent.ambiguity)

    def test_spaced_names_join_only_when_they_match_a_sourced_name(self):
        for q, names in (('청둥 오리와 흰뺨검둥오리 공통분류 알려줘', ('청둥 오리', '흰뺨검둥오리')),
                         ('흰뺨 검둥 오리와 같은 속인 새는?', ('흰뺨 검둥 오리',)),
                         ('청둥오리와 흰뺨 검둥오리는 어떤 관계야?', ('청둥오리', '흰뺨 검둥오리'))):
            with self.subTest(q=q):
                self.assertEqual(names, tuple(s.text for s in extract_graph_intent(q).species))
                self.assertEqual('answer', gate(q)[0])
        for q in ('여름에만 청둥오리와 같은 속인 새는?', '대부분 청둥오리와 같은 속인 새는?', '큰 오리와 같은 속인 새는?'):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertNotEqual('answer', disposition)
                self.assertNotIn(' ', ''.join(s.text for s in intent.species))

    def test_species_are_original_spans_and_scalars_have_evidence(self):
        q = '숲에서 살면서 직박구리와 식성이 같은 새가 궁금해'
        intent = extract_graph_intent(q)
        self.assertEqual(('직박구리',), tuple(s.text for s in intent.species))
        self.assertEqual(q.index('직박구리'), intent.species[0].start)
        self.assertEqual({'diet', 'relation', 'habitat'}, {slot for slot, _ in intent.evidence})
        self.assertEqual((), validate_intent(q, intent))
        stripped = replace(intent, evidence=())
        self.assertEqual('clarify', execution_gate(q, stripped))


class ConflictTests(TestCase):
    def test_differing_values_are_held_never_picked(self):
        for q in ('참새목 중 과실식이면서 나무열매를 먹는 새', '참새목 중 과실식이면서 열매를 먹는 새',
                  '숲에 사는 새 중 직박구리와 식성이 같고 먹이 범주가 다른 새', '참새목 중 감나무 열매와 산수유 열매를 먹는 새',
                  '참새목과 비둘기목 중 열매를 먹는 새', '청둥오리와 흰뺨검둥오리의 공통 분류와 같은 속인 새',
                  '숲에 사는 새 중 습지에 사는 직박구리와 먹이 범주가 같은 새'):
            with self.subTest(q=q):
                disposition, intent = gate(q)
                self.assertEqual('clarify', disposition)
                self.assertTrue(intent.ambiguity)
        self.assertEqual('answer', gate('참새목 중 나무열매를 먹는 새')[0])

    def test_long_graph_questions_clarify_and_long_others_stay_on_their_route(self):
        padding = ' 그리고 이건 아주 길게 늘여 쓴 문장입니다' * 12
        long_graph = '참새목 중 열매를 먹는 새는?' + padding
        self.assertGreater(len(long_graph), 200)
        self.assertEqual('clarify', gate(long_graph)[0])
        long_other = '기후변화가 철새에 미치는 영향은?' + padding
        self.assertEqual(GraphIntent(None, source='extractor'), extract_graph_intent(long_other))


class CandidateTests(TestCase):
    def test_candidates_only_add_kind_tie(self):
        q = '참새목 중 열매를 먹는 새는?'
        plain = extract_graph_intent(q)
        agree = KindCandidates((('order_fruit', 0.9), ('same_genus', 0.5)), 0.4, 'ok')
        disagree = KindCandidates((('same_genus', 0.9), ('order_fruit', 0.5)), 0.4, 'ok')
        weak = KindCandidates((('same_genus', 0.6), ('order_fruit', 0.5)), 0.1, 'below_threshold')
        self.assertEqual(plain, extract_graph_intent(q, agree))
        self.assertEqual(plain, extract_graph_intent(q, weak))
        self.assertEqual(plain, extract_graph_intent(q, KindCandidates()))
        tied = extract_graph_intent(q, disagree)
        self.assertEqual(replace(plain, ambiguity=('kind_tie',)), tied)
        self.assertEqual('clarify', execution_gate(q, tied))
        none_q = '청둥오리의 학명은 뭐야?'
        self.assertEqual(extract_graph_intent(none_q), extract_graph_intent(none_q, disagree))

    def test_broken_candidates_never_raise(self):
        class Broken:
            @property
            def top(self):
                raise RuntimeError('broken')
        q = '참새목 중 열매를 먹는 새는?'
        intent = extract_graph_intent(q, Broken())
        self.assertEqual('clarify', execution_gate(q, intent))

    def test_never_raises(self):
        for q in (None, '', '   ', 3, '?' * 10, '새' * 300, '🐦🐦', '1234', 'Anas', '와', '목', '열매', '같은 속'):
            with self.subTest(q=q):
                intent = extract_graph_intent(q)
                self.assertIsInstance(intent, GraphIntent)
                self.assertEqual('extractor', intent.source)
                self.assertNotEqual('answer', execution_gate(q if isinstance(q, str) else '', intent))
