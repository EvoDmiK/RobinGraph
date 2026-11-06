"""Regression fixtures from traced failures plus independent predicate/negation counterexamples."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from robingraph import tracing
from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_intent_schema import execution_gate


HABITAT_Q = '참새목 안에서 골라 줘. 숲이 서식지로 기록돼 있고 과일도 먹는 새를 찾고 있어.'
HABITAT = {'kind': 'taxon_traits', 'taxon': '참새목', 'species': None, 'conditions': [
    {'trait_name': 'habitat', 'op': 'eq', 'value': 'Forest', 'surface': '숲이 서식지로 기록돼 있어'},
    {'trait_name': 'diet_distribution', 'op': 'share_gt', 'value': 'fruit', 'threshold': 0, 'surface': '과일도 먹는'}],
    'relation_text': None, 'unresolved': [], 'unknown_relation': False}
RELATION_Q = '직박구리 말고 먹이 생태 범주가 직박구리와 같은 다른 종을 알려줘.'
RELATION = {'kind': 'shared_diet', 'species': '직박구리', 'relation_text': '먹이 생태 범주가',
            'conditions': [], 'unresolved': [], 'unknown_relation': False}
NUMBER_Q = '까치속에서 몸무게가 180g을 넘는 새를 찾아줘. 180g인 기록은 제외해.'
NUMBER = {'kind': 'taxon_traits', 'taxon': '까치속', 'conditions': [
    {'trait_name': 'body_mass', 'op': 'num_gt', 'threshold': 180, 'unit': 'g', 'surface': '몸무게가 180g을 넘는'}],
    'unresolved': ['180g인 기록은 제외해'], 'unknown_relation': False}


def document(payload):
    return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}


class GraphEvidenceReconciliationTest(unittest.TestCase):
    def test_three_traced_failures_reconcile_without_mutating_predicates_or_original_plan(self):
        for question, raw, field in [(HABITAT_Q, HABITAT, 'conditions[0].surface'),
                                     (RELATION_Q, RELATION, 'relation_text'),
                                     (NUMBER_Q, NUMBER, 'unresolved')]:
            before = copy.deepcopy(raw)
            candidate, changes = sgi.reconcile_graph_plan(question, raw)
            with self.subTest(field=field):
                self.assertEqual(before, raw)
                self.assertEqual([field], [change['field'] for change in changes])
                self.assertEqual('answer', execution_gate(question, sgi.interpret(question, lambda *_: candidate)))
                for old, new in zip(raw['conditions'], candidate['conditions']):
                    self.assertEqual({k:v for k,v in old.items() if k != 'surface'},
                                     {k:v for k,v in new.items() if k != 'surface'})
                self.assertEqual(raw.get('species'), candidate.get('species'))
                self.assertEqual(raw.get('taxon'), candidate.get('taxon'))

    def test_same_predicate_ending_recovery_is_not_tied_to_forest_or_order(self):
        for word, habitat in [('습지', 'Wetland'), ('숲', 'Forest')]:
            for ending in ('있고', '있으며', '있는'):
                q = f'Corvus 속에서 {word}이 서식지로 기록되어 {ending} 종을 찾아줘'
                raw = {'kind': 'taxon_traits', 'taxon': 'Corvus', 'conditions': [
                    {'trait_name': 'habitat', 'op': 'eq', 'value': habitat,
                     'surface': f'{word}이 서식지로 기록되어 있어'}]}
                with self.subTest(word=word, ending=ending):
                    candidate, changes = sgi.reconcile_graph_plan(q, raw)
                    self.assertTrue(changes)
                    self.assertIn(candidate['conditions'][0]['surface'], q)

    def test_paraphrase_does_not_fix_negative_qualified_or_ambiguous_evidence(self):
        for q in [HABITAT_Q.replace('있고', '없고'), HABITAT_Q.replace('있고', '있고만'),
                  HABITAT_Q.replace('있고', '있지만'), HABITAT_Q.replace('숲이', '습지가'), HABITAT_Q.replace('숲이', '열대숲이'),
                  HABITAT_Q + ' 숲이 서식지로 기록돼 있고',
                  HABITAT_Q.replace('숲이 서식지로 기록돼 있고', '숲이 아닌 서식지로 기록돼 있고')]:
            with self.subTest(q=q):
                self.assertEqual((HABITAT, []), sgi.reconcile_graph_plan(q, HABITAT))

    def test_relation_requires_unique_immediate_exact_reference_and_positive_sameness(self):
        for name in ('까치', '청둥오리'):
            for relation in ('같은', '동일한', '일치하는', '비슷한', '유사한'):
                q = f'{name} 말고 먹이 생태 범주가 {name}와 {relation} 다른 종을 알려줘'
                raw = {**RELATION, 'species': name}
                with self.subTest(name=name, relation=relation):
                    candidate, changes = sgi.reconcile_graph_plan(q, raw)
                    self.assertTrue(changes)
                    self.assertEqual(f'먹이 생태 범주가 {name}와 {relation}', candidate['relation_text'])
        for q in [RELATION_Q.replace('와 같은', '와 다른'), RELATION_Q.replace('와 같은', '와 같지 않은'),
                  RELATION_Q.replace('와 같은', '와 같은지만'), RELATION_Q.replace('가 직박구리와', '가 까치와'),
                  RELATION_Q.replace('가 직박구리와', '가 서식지는 직박구리와'),
                  RELATION_Q + ' 먹이 생태 범주가 직박구리와 같은',
                  RELATION_Q.replace('먹이 생태 범주가', '가짜먹이 생태 범주가'),
                  RELATION_Q.replace('먹이 생태 범주가', '먹이 생태 범주가 아니라 먹이 생태 범주가')]:
            with self.subTest(q=q):
                self.assertEqual((RELATION, []), sgi.reconcile_graph_plan(q, RELATION))

    def test_restatement_supports_unit_conversion_and_strict_lower_or_upper_bounds(self):
        for bound, op in [('넘는', 'num_gt'), ('미만인', 'num_lt')]:
            q = f'까치속에서 몸무게가 0.18kg {bound} 새를 찾아줘. 180g인 기록은 제외해.'
            raw = copy.deepcopy(NUMBER)
            raw['conditions'][0].update(op=op, surface=f'몸무게가 0.18kg {bound}')
            candidate, changes = sgi.reconcile_graph_plan(q, raw)
            with self.subTest(op=op):
                self.assertTrue(changes)
                self.assertEqual([], candidate['unresolved'])
                self.assertEqual(raw['conditions'], candidate['conditions'])

    def test_inclusive_other_value_unit_trait_or_unsupported_constraint_stays_unresolved(self):
        cases = []
        for q, updates in [(NUMBER_Q.replace('넘는', '이상인'), {'op':'num_gte', 'surface':'몸무게가 180g을 이상인'}),
                           (NUMBER_Q, {'threshold': 181}), (NUMBER_Q, {'unit': 'mm'}),
                           (NUMBER_Q, {'trait_name': 'wing_length', 'unit':'mm'})]:
            raw = copy.deepcopy(NUMBER);raw['conditions'][0].update(updates);cases.append((q,raw))
        for exclusion in ['181g인 기록은 제외해', '180mm인 기록은 제외해', '180g 이상인 기록은 제외해',
                          '180g인 기록은 제외해 그리고 겨울 새만', '까치는 제외해']:
            raw = copy.deepcopy(NUMBER);raw['unresolved']=[exclusion]
            cases.append((NUMBER_Q.replace('180g인 기록은 제외해',exclusion),raw))
        raw = copy.deepcopy(NUMBER);raw['unresolved'].append('밤에만 활동하는')
        cases.append((NUMBER_Q+' 밤에만 활동하는 종.',raw))
        raw = copy.deepcopy(NUMBER);raw['unknown_relation']=True;cases.append((NUMBER_Q,raw))
        raw = copy.deepcopy(NUMBER);raw['conditions'].append({
            'trait_name':'wing_length','op':'num_gt','threshold':180,'unit':'mm','surface':'날개가 180mm 넘는'})
        cases.append((NUMBER_Q+' 날개가 180mm 넘는 종.',raw))
        for q,raw in cases:
            with self.subTest(q=q, raw=raw):
                self.assertEqual((raw,[]),sgi.reconcile_graph_plan(q,raw))

    def test_local_candidate_check_cannot_overwrite_parent_outcome(self):
        with patch.object(tracing, '_mlflow', Mock()):
            token=tracing.begin_outcome()
            try:
                tracing.note_outcome('ambiguous_name','name_resolution')
                before=tracing.collected_outcome()
                invalid={**HABITAT,'unresolved':['미확인 조건']}
                self.assertEqual((invalid,[]),sgi.reconcile_graph_plan(HABITAT_Q,invalid))
                self.assertEqual(before,tracing.collected_outcome())
            finally:
                tracing.end_outcome(token)

    def test_audit_receives_original_and_reconciled_plan_and_false_still_blocks_without_retry(self):
        for faithful in (True,False):
            answerer=GeminiAnswerer('dummy',urlopen=Mock())
            answerer._request=Mock(side_effect=[document(NUMBER),document({'faithful':faithful,'issues':[]})])
            if faithful:
                result=answerer.propose_structured_graph_intent(NUMBER_Q,[],sgi.CONTRACT)
                self.assertEqual([],result['unresolved'])
            else:
                with self.assertRaisesRegex(GeminiAnswerError,'did not pass semantic audit'):
                    answerer.propose_structured_graph_intent(NUMBER_Q,[],sgi.CONTRACT)
            self.assertEqual(2,answerer._request.call_count)
            payload=json.loads(answerer._request.call_args_list[1].args[0].split('\n')[-1])
            self.assertEqual(NUMBER,payload['original_proposal'])
            self.assertEqual([],payload['proposed_plan']['unresolved'])
            self.assertEqual('strict_bound_restatement',payload['evidence_reconciliations'][0]['rule'])
