"""Offline regression of frozen provider plans; no live model, API or database calls."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.retrieval.graph_questions import TRAIT_CONDITIONS


FROZEN_PLANS = [{'case': 'V2-03A',
  'question': 'AVONET 먹이 생태 범주가 Omnivore인 새가 궁금해. 개똥지빠귀속에서만 볼래.',
  'plan': {'kind': 'taxon_traits',
           'taxon': '개똥지빠귀속',
           'species': None,
           'conditions': [{'trait_name': 'trophic_niche',
                           'op': 'eq',
                           'value': 'Omnivore',
                           'surface': '먹이 생태 범주가 Omnivore인'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}},
 {'case': 'V2-03B',
  'question': '개똥지빠귀속을 대상으로 대표 먹이 생태 범주 Omnivore 조건을 적용해 주세요.',
  'plan': {'kind': 'taxon_traits',
           'taxon': '개똥지빠귀속',
           'species': None,
           'conditions': [{'trait_name': 'trophic_niche',
                           'op': 'eq',
                           'value': 'Omnivore',
                           'surface': '대표 먹이 생태 범주 Omnivore'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}},
 {'case': 'V2-03C',
  'question': '개똥지빠귀속에서 대표 먹이 생태 범주가 Invertivore인 새를 보여 주세요.',
  'plan': {'kind': 'taxon_traits',
           'taxon': '개똥지빠귀속',
           'species': None,
           'conditions': [{'trait_name': 'trophic_niche',
                           'op': 'eq',
                           'value': 'Invertivore',
                           'surface': '대표 먹이 생태 범주가 Invertivore인'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}},
 {'case': 'V2-05A',
  'question': '분류 범위는 전체 조류로 둘게. 생활 방식이 Terrestrial로 기록된 종을 모아줘.',
  'plan': {'kind': 'taxon_traits',
           'taxon': None,
           'species': None,
           'conditions': [{'trait_name': 'primary_lifestyle',
                           'op': 'eq',
                           'value': 'Terrestrial',
                           'surface': '생활 방식이 Terrestrial로'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}},
 {'case': 'V2-05B',
  'question': '생활 방식 범주 Terrestrial인 새를 보고 싶어요. 특정 목이나 과로 제한하지 마세요.',
  'plan': {'kind': 'taxon_traits',
           'taxon': None,
           'species': None,
           'conditions': [{'trait_name': 'primary_lifestyle',
                           'op': 'eq',
                           'value': 'Terrestrial',
                           'surface': '생활 방식 범주 Terrestrial인'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}},
 {'case': 'V2-05C',
  'question': '전체 조류에서 생활 방식 범주가 Generalist로 기록된 종을 모아줘.',
  'plan': {'kind': 'taxon_traits',
           'taxon': None,
           'species': None,
           'conditions': [{'trait_name': 'primary_lifestyle',
                           'op': 'eq',
                           'value': 'Generalist',
                           'surface': '생활 방식 범주가 Generalist로'}],
           'relation_text': None,
           'unresolved': [],
           'unknown_relation': False}}]

def plan(value='Omnivore', trait='trophic_niche', surface=None, taxon='Turdus'):
    return {'kind': 'taxon_traits', 'taxon': taxon, 'conditions': [
        {'trait_name': trait, 'op': 'eq', 'value': value, 'surface': surface or f'{value}인'}]}


class TypedEnumNamesTest(unittest.TestCase):
    def test_six_frozen_provider_plans_pass_local_contract_without_modification(self):
        self.assertEqual(6, len(FROZEN_PLANS))
        for row in FROZEN_PLANS:
            raw = row['plan']
            before, question = copy.deepcopy(raw), row['question']
            with self.subTest(case=row['case']):
                result = s.interpret(question, lambda *_: raw)
                self.assertEqual('answer', execution_gate(question, result))
                self.assertEqual(before, raw)
                self.assertEqual([(c['trait_name'], c['value']) for c in raw['conditions']],
                                 [(c.trait_name, c.value) for c, _ in result.conditions])

    def test_every_text_enum_uses_metadata_in_its_own_exact_evidence(self):
        for trait, (_, kind, values) in TRAIT_CONDITIONS.items():
            if kind != 'text':
                continue
            for value in values:
                raw = plan(value, trait)
                question = f'Turdus에서 {trait} 값이 {value}인 종을 알려줘.'
                with self.subTest(trait=trait, value=value):
                    result = s.interpret(question, lambda *_: raw)
                    self.assertEqual('answer', execution_gate(question, result))
                    self.assertEqual(value, result.conditions[0][0].value)

    def test_shared_bare_enum_cannot_select_its_own_field(self):
        for value in ('Omnivore', 'Scavenger'):
            for trait, (_, kind, values) in TRAIT_CONDITIONS.items():
                if kind == 'text' and value in values:
                    question = f'Turdus에서 {value}인 종을 알려줘.'
                    with self.subTest(trait=trait, value=value):
                        self.assertEqual('clarify', execution_gate(question, s.interpret(question, lambda *_: plan(value, trait))))

    def test_scientific_names_and_other_occurrences_are_still_required(self):
        for extra in ('Omnivore', 'Pica pica', 'Anas platyrhynchos platyrhynchos', '까마귀과', 'Corvus',
                      'Omnivore example', 'Omnivore_example', 'Omnivore2'):
            question = f'Turdus에서 Omnivore인 종과 {extra}도 알려줘.'
            with self.subTest(extra=extra):
                result = s.interpret(question, lambda *_: plan())
                self.assertNotEqual('answer', execution_gate(question, result))
        question = 'Omnivore에서 Forest인 종을 알려줘.'
        raw = plan('Forest', 'habitat', taxon='Omnivore')
        result = s.interpret(question, lambda *_: raw)
        self.assertEqual('answer', execution_gate(question, result))
        self.assertEqual('Omnivore', result.rank.text)
        # Even a matching enum inside the surface cannot consume an actual catalog name.
        higher, species = s._taxon_names()
        with patch.object(s, '_taxon_names', return_value=(higher | {'Omnivore'}, species)):
            q = 'Turdus에서 Omnivore인 종을 알려줘.'
            self.assertNotEqual('answer', execution_gate(q, s.interpret(q, lambda *_: plan())))

    def test_bad_evidence_wrong_enum_trait_and_extra_names_within_surface_still_hold(self):
        cases = [
            ('Turdus에서 Omnivore인 종', plan(surface='Forest인')),
            ('Turdus에서 Forest인 종', plan(surface='Forest인')),
            ('Turdus에서 Omnivore인 종', plan(trait='habitat')),
            ('Turdus에서 Omnivore example인 종', plan(surface='Omnivore example인')),
            ('Turdus에서 Omnivore와 Pica pica인 종', plan(surface='Omnivore와 Pica pica인')),
            ('Turdus에서 Other_Omnivore인 종', plan(surface='Other_Omnivore인'))]
        for question, raw in cases:
            with self.subTest(question=question, raw=raw):
                self.assertNotEqual('answer', execution_gate(question, s.interpret(question, lambda *_: raw)))

    def test_negation_and_unsupported_constraints_still_veto_the_provider(self):
        for question in ('Turdus에서 Omnivore가 아닌 종을 알려줘.',
                         'Turdus에서 Omnivore인 종 중 밤에만 활동하는 종을 알려줘.'):
            provider = Mock(return_value=plan())
            result = s.graph_intent_handler(question, provider=provider)
            self.assertNotEqual('answer', execution_gate(question, result))
            provider.assert_not_called()

    def test_audit_false_remains_blocking_with_two_calls(self):
        raw = plan()
        def document(payload):
            return {'candidates': [{'content': {'parts': [{'text': json.dumps(payload)}]}}]}
        answerer = GeminiAnswerer('dummy', urlopen=Mock())
        answerer._request = Mock(side_effect=[document(raw), document({'faithful': False, 'issues': ['불일치']})])
        with self.assertRaises(GeminiAnswerError):
            answerer.propose_structured_graph_intent('Turdus에서 Omnivore인 종을 알려줘.', [], s.CONTRACT)
        self.assertEqual(2, answerer._request.call_count)
