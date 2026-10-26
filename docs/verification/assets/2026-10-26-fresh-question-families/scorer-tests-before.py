"""Synthetic scorer mutation tests; these are not live question-success measurements."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('family_score', ROOT / 'scripts/evaluate_graph_question_families.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CATALOG = {'taxa': [{'id': 'family-1', 'scientific_name': 'Corvidae', 'korean_name': '까마귀과', 'rank': 'family'},
                     {'id': 'species-1', 'scientific_name': 'Corvus corax', 'korean_name': '큰까마귀', 'rank': 'species'}]}


def case(id='A', op='num_gt', role='equivalent'):
    return {'id': id, 'semantic_group_id': 'G1', 'role': role, 'category': 'supported',
            'expected': {'kind': 'taxon_traits', 'taxon_name': 'Corvidae', 'rank': 'family',
                         'conditions': [{'trait_name': 'wing_length', 'op': op, 'threshold': 100, 'unit': 'mm'}]}}


def row(c, status='answer'):
    return {'case': c['id'], 'http_status': 200, 'request': {'species_scope': 'all'},
            'response': {'disposition': 'abstain' if status == 'insufficient_data' else 'answer',
                         'result': {'kind': 'graph_query', 'payload': {'status': status,
                         'taxon': {'scientific_name': 'Corvidae', 'rank': 'family'},
                         'conditions': copy.deepcopy(c['expected']['conditions'])}}}}


class FamilyScorerTests(unittest.TestCase):
    def test_whole_family_needs_equivalence_and_distinct_contrast(self):
        cases = [case('A'), case('B'), case('C', 'num_gte', 'contrast')]
        rows = [row(c) for c in cases]
        good = s.evaluate(cases, rows, CATALOG)
        self.assertEqual(good['case_counts'], {'pass': 3})
        self.assertEqual(good['group_counts'], {'pass': 1})
        rows[2]['response']['result']['payload']['conditions'] = cases[0]['expected']['conditions']
        bad = s.evaluate(cases, rows, CATALOG)
        self.assertEqual(bad['case_counts'], {'pass': 2, 'fail': 1})
        self.assertEqual(bad['group_counts'], {'fail': 1})

    def test_condition_deletion_changed_threshold_rank_or_bool_never_passes(self):
        c = case()
        for mutation in ('delete', 'threshold', 'rank', 'bool'):
            r = row(c); p = r['response']['result']['payload']
            if mutation == 'delete': p['conditions'] = []
            if mutation == 'threshold': p['conditions'][0]['threshold'] = 101
            if mutation == 'rank': p['taxon']['rank'] = 'genus'
            if mutation == 'bool': p['conditions'][0]['threshold'] = True
            with self.subTest(mutation=mutation): self.assertEqual(s.assess(c, r, CATALOG)['status'], 'fail')

    def test_missing_execution_evidence_cannot_be_replaced_by_plan(self):
        c = case(); r = row(c); del r['response']['result']['payload']['conditions']
        r['diagnostic_spans'] = [{'name': 'graph_intent.route', 'attributes': {'canonical_plan': {
            'kind': 'taxon_traits', 'rank_name': '까마귀과', 'conditions': c['expected']['conditions']}}}]
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'unverifiable')

    def test_source_no_data_and_name_failure_are_distinct(self):
        c = case(); r = row(c, 'insufficient_data')
        self.assertEqual(s.assess(c, r, CATALOG)['classification'], 'supported_source_no_data')
        del r['response']['result']['payload']['taxon'];r['response']['result']['payload']['taxon_resolution'] = 'not_found'
        verdict = s.assess(c, r, CATALOG)
        self.assertEqual(verdict['status'], 'fail');self.assertEqual(verdict['classification'], 'name_resolution_failure')

    def test_canonical_metadata_must_agree_with_actual_scope_and_all_conditions(self):
        c = case(); r = row(c)
        plan = {'kind': 'taxon_traits', 'rank_name': '까마귀과', 'conditions': copy.deepcopy(c['expected']['conditions'])}
        r['diagnostic_spans'] = [{'name': 'graph_intent.route', 'attributes': {'canonical_plan': plan}}]
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'pass')
        plan['conditions'] = []
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'fail')

    def test_explicit_negative_hold_needs_reason_and_clarification(self):
        c = {**case(), 'category': 'hold', 'expected': {}, 'expected_hold_class': 'negated_condition'}
        r = {'case': 'A', 'response': {'disposition': 'clarify', 'result': {'kind': 'clarify', 'prompt': '부정 조건을 확인해 주세요.'}},
             'tags': {'response_reason': 'negated_conditions'}}
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'pass')
        r['tags']['response_reason'] = 'ambiguous_conditions'
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'fail')
        r['response']['disposition'] = 'answer'
        self.assertEqual(s.assess(c, r, CATALOG)['classification'], 'unsafe_answer')

    def test_duplicate_observations_cannot_select_best_attempt(self):
        c = case()
        with self.assertRaises(ValueError): s.evaluate([c], [row(c), row(c)], CATALOG)

    def test_missing_member_fails_entire_family(self):
        cases = [case('A'), case('B'), case('C', 'num_gte', 'contrast')]
        result = s.evaluate(cases, [row(cases[0]), row(cases[2])], CATALOG)
        self.assertEqual(result['group_counts'], {'fail': 1});self.assertEqual(result['case_counts']['missing'], 1)

    def test_relation_requires_complete_executor_reference_and_exclusion(self):
        c = {**case(), 'expected': {'kind': 'relation', 'reference_taxon_name': 'Corvus corax',
                                  'share_basis': 'trophic_niche', 'exclude_reference': True, 'habitat': None}}
        summary = {'kind': 'shared_diet', 'reference_name': 'Corvus corax', 'target_id': 'species-1',
                   'species_scope': 'all', 'share_basis': 'trophic_niche', 'match': 'same', 'exclude_reference': True,
                   'habitat': None, 'niche_value': 'Omnivore', 'dataset_id': 'test-source', 'release': 'v1',
                   'concept_set_id': 'test-taxonomy', 'taxonomy_release': 'v1'}
        r = {'case': 'A', 'response': {'disposition': 'answer', 'result': {'kind': 'graph_query', 'payload': {
            'status': 'answer', 'taxon': {'scientific_name': 'Corvus corax', 'taxon_id': 'species-1'},
            'execution_summary': summary, 'items': []}}}}
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'pass')
        summary['exclude_reference'] = 1
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'fail')
        summary['exclude_reference'] = True; del summary['habitat']
        self.assertEqual(s.assess(c, r, CATALOG)['status'], 'unverifiable')


if __name__ == '__main__': unittest.main(verbosity=2)
