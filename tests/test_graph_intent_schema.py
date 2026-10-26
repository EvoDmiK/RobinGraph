from contextlib import redirect_stdout
from dataclasses import replace
import importlib.util
import io
import json
from pathlib import Path
from unittest import TestCase

from robingraph.retrieval.graph_intent_schema import (
    EXPECTED_FIELDS, GraphIntent, Span, execution_gate, from_graph_question, intent_from_expected, span_of,
    to_graph_question, validate_intent)
from robingraph.retrieval.graph_questions import GraphQuestion, parse_graph_question

ROOT = Path(__file__).resolve().parents[1]
TUNING = ROOT / 'data/eval/graph_questions/tuning.jsonl'
spec = importlib.util.spec_from_file_location('eval_graph_questions', ROOT / 'scripts/eval_graph_questions.py')
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)

Q = '참새목 중 열매를 먹는 새는?'


def order_fruit(question=Q, **changes):
    intent = GraphIntent('order_fruit', rank=span_of(question, '참새목'), diet='fruit_share',
                         evidence=(('diet', span_of(question, '열매를 먹는')),))
    return replace(intent, **changes)


def record(question, **expected):
    base = {'kind': None, 'disposition': 'not_graph'}
    return {'id': 'X', 'split': 'tuning', 'question': question, 'expected': {**base, **expected},
            'categories': ['c'], 'provenance': {'author': 'test'}}


class SpanValidationTests(TestCase):
    def test_offsets_must_be_real_ints_inside_the_question_and_match_the_slice(self):
        self.assertEqual((), validate_intent(Q, order_fruit()))
        tail = len(Q) - len('새는?')
        bad = (Span('참새목', 0, 4), Span('참새목', True, 3), Span('새는?', -3, len(Q)),
               Span('새는?', tail, len(Q) + 5), Span('', 0, 0), Span('참새목', 3, 0), Span('참새목', 0.0, 3))
        for span in bad:
            with self.subTest(span=span):
                self.assertIn('span_mismatch', validate_intent(Q, order_fruit(rank=span)))
                self.assertEqual('clarify', execution_gate(Q, order_fruit(rank=span)))

    def test_unknown_kind_or_values_fail_closed_without_key_errors(self):
        for intent in (GraphIntent('free_cypher'), GraphIntent(['order_fruit']), order_fruit(diet='insect'),
                       order_fruit(kind='MATCH (n) RETURN n'), 'not an intent'):
            with self.subTest(intent=intent):
                self.assertEqual('clarify', execution_gate(Q, intent))
                self.assertIsNone(to_graph_question(Q, intent))
        self.assertEqual('clarify', execution_gate(None, order_fruit()))

    def test_scalar_slots_need_original_text_evidence_unless_source_is_trusted(self):
        bare = order_fruit(evidence=())
        self.assertIn('scalar_without_evidence', validate_intent(Q, bare))
        self.assertEqual('clarify', execution_gate(Q, bare))
        self.assertEqual('answer', execution_gate(Q, replace(bare, source='regex_fullmatch')))
        wrong = order_fruit(evidence=(('diet', Span('과실식', 0, 3)),))
        self.assertEqual('clarify', execution_gate(Q, wrong))


class GateTests(TestCase):
    def test_answerable_intent_maps_to_the_existing_graph_question(self):
        self.assertEqual('answer', execution_gate(Q, order_fruit()))
        self.assertEqual(GraphQuestion('order_fruit', (), '참새목', None, 'fruit_share', None),
                         to_graph_question(Q, order_fruit()))

    def test_blocking_conditions_are_never_dropped(self):
        q = '참새목 중 열매를 안 먹는 작은 새는?'
        base = order_fruit(q, evidence=(('diet', span_of(q, '열매를')),))
        self.assertEqual('answer', execution_gate(q, base))
        for changes, disposition in (({'negation': (span_of(q, '안 먹는'),)}, 'clarify'),
                                     ({'residual': (span_of(q, '작은'),)}, 'clarify'),
                                     ({'ambiguity': ('other',)}, 'clarify'),
                                     ({'unsupported': ('co_occurrence',)}, 'unsupported'),
                                     ({'scope': 'korea', 'evidence': base.evidence + (('scope', span_of(q, '참새목')),)},
                                      'clarify')):
            with self.subTest(changes=changes):
                self.assertEqual(disposition, execution_gate(q, replace(base, **changes)))
                self.assertIsNone(to_graph_question(q, replace(base, **changes)))

    def test_specific_plant_is_insufficient_without_db_and_never_relaxed(self):
        q = '참새목 중 감나무 열매를 먹지 않는 새'
        plant = GraphIntent('specific_fruit', rank=span_of(q, '참새목'), specific_plant=span_of(q, '감나무'))
        self.assertEqual('insufficient_data', execution_gate(q, plant))
        self.assertEqual('specific_fruit', to_graph_question(q, plant).kind)
        negated = replace(plant, negation=(span_of(q, '먹지 않는'),))
        self.assertEqual('clarify', execution_gate(q, negated))
        self.assertIsNone(to_graph_question(q, negated))
        relaxed = replace(plant, kind='order_fruit', diet='fruit_share', source='regex_fullmatch')
        self.assertEqual('insufficient_data', execution_gate(q, relaxed))
        self.assertIsNone(to_graph_question(q, relaxed))

    def test_slot_rules_reject_templates_that_do_not_exist(self):
        q = '숲에 사는 새 중 직박구리와 먹이 범주가 다른 새는?'
        intent = GraphIntent('habitat_different_diet', species=(span_of(q, '직박구리'),), habitat='Forest',
                             diet='niche', relation='different', source='regex_fullmatch')
        self.assertEqual('clarify', execution_gate(q, intent))
        self.assertEqual('answer', execution_gate(q, replace(intent, habitat='target')))
        self.assertEqual('clarify', execution_gate(q, replace(intent, habitat='target', species=())))

    def test_regex_round_trip_keeps_the_existing_graph_question(self):
        for q in ('청둥오리와 흰뺨검둥오리는 어떤 관계야?', '한국에 기록된 오리 중 청둥오리와 같은 속인 종은?',
                  '참새목 중 열매를 먹고 사는 새는?', '청둥오리와 같은 속에 속하는 새를 보여줘',
                  '숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는?', '청둥오리와 서식지가 겹치면서 먹이가 다른 새는?',
                  '숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?'):
            with self.subTest(q=q):
                parsed = parse_graph_question(q)
                intent = from_graph_question(q, parsed)
                self.assertEqual((), validate_intent(q, intent))
                self.assertEqual(parsed, to_graph_question(q, intent))
        self.assertEqual('not_graph', execution_gate('청둥오리 학명', from_graph_question('청둥오리 학명', None)))


class GoldFormatTests(TestCase):
    def test_scalar_and_pair_forms_and_omitted_optional_fields(self):
        scalar = intent_from_expected(Q, {'kind': 'order_fruit', 'disposition': 'answer', 'rank': '참새목',
                                          'diet': 'fruit_share'})
        pair = intent_from_expected(Q, {'kind': 'order_fruit', 'disposition': 'answer', 'rank': ['order', '참새목'],
                                        'diet': ['fruit_share', '열매를 먹는']})
        self.assertEqual((scalar.rank, scalar.diet), (pair.rank, pair.diet))
        self.assertEqual((('diet', span_of(Q, '열매를 먹는')),), pair.evidence)

    def test_bad_records_are_rejected(self):
        for expected in ({'kind': 'order_fruit'},
                         {'kind': None, 'disposition': 'not_graph', 'cypher': 'MATCH (n)'},
                         {'kind': 'order_fruit', 'disposition': 'answer', 'rank': '비둘기목', 'diet': 'fruit_share'},
                         {'kind': 'order_fruit', 'disposition': 'clarify', 'rank': '참새목', 'diet': 'fruit_share'},
                         {'kind': 'order_fruit', 'disposition': 'answer', 'rank': ['family', '참새목'],
                          'diet': 'fruit_share'},
                         {'kind': None, 'disposition': 'maybe'}):
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError):
                    intent_from_expected(Q, expected)

    def test_tuning_set_is_valid_agent_reviewed_tuning_only(self):
        rows = evaluator.load(TUNING)
        valid, errors = evaluator.check(rows)
        self.assertEqual([], errors)
        self.assertTrue(60 <= len(valid) <= 100)
        for item, _ in valid:
            self.assertEqual('tuning', item['split'])
            self.assertTrue(item['id'].startswith('GGQ-T-'))
            self.assertEqual(('agent:claude-opus-5-5', 'agent_reviewed'),
                             (item['provenance']['author'], item['provenance']['review_status']))
            self.assertEqual(set(EXPECTED_FIELDS), set(item['expected']))
            self.assertNotIn('human', ' '.join(item['provenance']['reviewers']).replace('not human', ''))
        questions = {item['question'] for item, _ in valid}
        for verbatim in ('참새목 새중에서 열매를 먹는 새는?', '참새목 새 중에서 나무열매를 먹는 새는?',
                         '참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?',
                         '참새목에 속한 새 가운데 열매를 먹는 종류 좀 알려줄래?', '열매 먹는 참새목 새를 찾아 줘',
                         '숲에서 살면서 직박구리와 식성이 같은 새가 궁금해', '청둥오리랑 서식지는 같지만 먹이는 다른 종을 찾아줘'):
            self.assertIn(verbatim, questions)


class EvaluatorTests(TestCase):
    def test_raw_and_gated_scores_are_kept_apart(self):
        rows = list(enumerate([
            record(Q, kind='order_fruit', disposition='answer', rank='참새목', diet='fruit_share'),
            record('국내 기록된 참새목 중 열매를 먹는 새', kind='order_fruit', disposition='clarify', rank='참새목',
                   diet='fruit_share', scope='korea'),
            record('청둥오리와 같이 사는 새는?', disposition='unsupported', unsupported=['co_occurrence']),
        ], 1))
        for number, (_, item) in enumerate(rows):
            item['id'] = f'X{number}'
        valid, errors = evaluator.check(rows)
        self.assertEqual([], errors)
        fake = {Q: GraphQuestion('order_fruit', (), '참새목', None, 'fruit_share'),
                '국내 기록된 참새목 중 열매를 먹는 새': GraphQuestion('order_fruit', (), '국내 기록된 참새목', None,
                                                          'fruit_share')}
        items, latencies = evaluator.score(valid, parse=fake.get)
        result = evaluator.metrics(items)
        self.assertEqual((1, 1), (result['raw']['coverage']['hits'], result['gated']['coverage']['hits']))
        self.assertEqual(1, result['raw']['false_execution']['hits'])    # scope dropped, executed
        self.assertEqual(1, result['raw']['condition_loss_executed'])
        self.assertEqual(0, result['gated']['false_execution']['hits'])  # gate rejects the multi-word rank
        self.assertEqual(['scope'], items[1]['lost_conditions'])
        self.assertEqual(3, len(latencies))

    def test_raw_execution_with_a_wrong_slot_is_a_false_execution(self):
        q = '해외에만 있는 청둥오리와 같은 속 새'
        rows = [(1, record(q, kind='same_genus', disposition='clarify', species=['청둥오리'], relation='same',
                           residual=['해외에만 있는']))]
        valid, _ = evaluator.check(rows)
        items, _ = evaluator.score(valid, parse=lambda _: GraphQuestion('same_genus', ('해외에만 있는 청둥오리',)))
        result = evaluator.metrics(items)
        self.assertEqual((1, 1), (result['raw']['false_execution']['hits'], result['gated']['false_execution']['hits']))

    def test_cli_exits_nonzero_on_invalid_gold(self):
        tmp = ROOT / 'tests' / '__invalid_probe__.jsonl'
        try:
            tmp.write_text(json.dumps(record(Q, kind='order_fruit', disposition='answer', rank='비둘기목'),
                                      ensure_ascii=False) + '\n', encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(1, evaluator.main(['--gold', str(tmp)]))
        finally:
            tmp.unlink(missing_ok=True)

    def test_leak_check_uses_normalized_questions(self):
        rows = [(1, record('참새목 중 열매를 먹는 새는?'))]
        tmp = ROOT / 'tests' / '__leak_probe__.jsonl'
        try:
            tmp.write_text(json.dumps(record('참새목중 열매를먹는 새는'), ensure_ascii=False) + '\n', encoding='utf-8')
            self.assertEqual(['X'], evaluator.leaks(rows, [tmp]))
        finally:
            tmp.unlink(missing_ok=True)
