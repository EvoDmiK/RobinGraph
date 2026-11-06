"""Shared enum values stay bound to explicit original fields across query wording and split evidence."""
import unittest

from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


class ExplicitFieldBindingTests(unittest.TestCase):
    def test_common_enum_does_not_change_dimensions_with_other_request_verbs(self):
        fields = {'trophic_level': '영양 단계', 'trophic_niche': '먹이 생태 범주', 'diet_category': '먹이 유형'}
        for source, label in fields.items():
            for requested in fields:
                for ending in ('기록을 조회해 주세요', '인지 알고 싶어요', '인지 확인하고 싶어요'):
                    q = f'Turdus merula의 {label}가 Omnivore인 {ending}.'
                    raw = {'kind': 'taxon_traits', 'taxon': 'Turdus merula', 'conditions': [
                        {'trait_name': requested, 'op': 'eq', 'value': 'Omnivore',
                         'surface': label + '가 Omnivore인'}], 'unresolved': [], 'unknown_relation': False}
                    with self.subTest(source=source, requested=requested, ending=ending):
                        self.assertEqual('answer' if source == requested else 'clarify',
                                         execution_gate(q, s.interpret(q, lambda *_: raw)))

    def test_split_value_uses_unique_field_context_and_never_guesses_ambiguous_context(self):
        def plan(trait):
            return {'kind': 'taxon_traits', 'taxon': 'Turdus merula', 'conditions': [
                {'trait_name': trait, 'op': 'eq', 'value': 'Omnivore', 'surface': 'Omnivore'}],
                'unresolved': [], 'unknown_relation': False}

        q = 'Turdus merula의 영양 단계를 조회해 줘. Omnivore 기록을 찾고 싶어.'
        for trait, wanted in (('trophic_level', 'answer'), ('trophic_niche', 'clarify'), ('diet_category', 'clarify')):
            with self.subTest(trait=trait):
                self.assertEqual(wanted, execution_gate(q, s.interpret(q, lambda *_: plan(trait))))
        q = 'Turdus merula의 영양 단계와 먹이 유형을 조회해 줘. Omnivore 기록을 찾아줘.'
        for trait in ('trophic_level', 'diet_category'):
            self.assertEqual('clarify', execution_gate(q, s.interpret(q, lambda *_: plan(trait))))
