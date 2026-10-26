"""Reviewed examples and canonical query contracts; mocks verify routing without DB or model calls."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from robingraph import tracing
from robingraph.generation import GeminiAnswerer
from robingraph.retrieval import semantic_graph_intent as sgi
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import canonical_graph_plan, execution_gate


def built(question, plan):
    return sgi.interpret(question, lambda *_: plan)


def condition(trait, op, surface, value=None, threshold=None, unit=None):
    return {'trait_name':trait,'op':op,'surface':surface,'value':value,'threshold':threshold,'unit':unit}


class VerifiedExampleTests(unittest.TestCase):
    def test_reviewed_pool_requires_executable_local_plan_and_fresh_copies(self):
        rows=sgi.verified_semantic_examples()
        self.assertEqual(13,len(rows))
        for row in rows:
            self.assertEqual('answer',execution_gate(row['question'],built(row['question'],row['intent'])))
        rows[0]['intent']['species']='invented'
        self.assertNotEqual('invented',sgi.verified_semantic_examples()[0]['intent']['species'])
        bad=('taxon_traits','Corvus 중 숲에 사는 새',{'kind':'taxon_traits','taxon':'Corvus','conditions':[
            condition('habitat','eq','숲에 사는','Wetland')]})
        with patch.object(sgi,'_EXAMPLES',(bad,)):
            self.assertEqual((),sgi.verified_semantic_examples())

    def test_retrieval_cannot_inject_plans_unreviewed_examples_or_wrong_kind(self):
        row=sgi.verified_semantic_examples()[0]
        supplied=[{**row,'intent':{'kind':'none'}},{'kind':'taxon_traits','question':'unreviewed'},
                  {**row,'kind':'taxon_traits'}, {'kind':'shared_diet','question':[]}]
        actual=sgi._examples('current question',lambda *a,**kw:supplied)
        self.assertEqual([row],actual)
        self.assertEqual(row['intent'],actual[0]['intent'])

    def test_nearest_example_is_context_not_current_answer_or_entity(self):
        row=sgi.verified_semantic_examples()[0]
        q='직박구리와 같은 먹이 생태를 가진 새를 찾아줘'
        provider=Mock(return_value=row['intent'])  # copied 까치 from the nearest reviewed question
        result=sgi.graph_intent_handler(q,provider=provider,retrieve=lambda *a,**kw:[row])
        provider.assert_called_once()
        self.assertEqual('clarify',execution_gate(q,result))

    def test_pool_validation_does_not_change_parent_failure_reason(self):
        with patch.object(tracing,'_mlflow',Mock()):
            token=tracing.begin_outcome()
            try:
                tracing.note_outcome('ambiguous_name','name_resolution')
                before=tracing.collected_outcome();sgi.verified_semantic_examples()
                self.assertEqual(before,tracing.collected_outcome())
            finally:
                tracing.end_outcome(token)


class CanonicalPlanTests(unittest.TestCase):
    def test_order_and_trait_fruit_queries_equal_but_qualifier_and_niche_differ(self):
        q='참새목 중 열매를 먹는 새는?'
        legacy=canonical_graph_plan(q,extract_graph_intent(q))
        semantic=canonical_graph_plan(q,built(q,{'kind':'taxon_traits','taxon':'참새목','conditions':[
            condition('diet_distribution','share_gt','열매를 먹는','fruit',0)]}))
        self.assertEqual(legacy,semantic)
        for other in ['참새목 중 나무 열매를 먹는 새는?','참새목 중 과실식 새는?']:
            different=canonical_graph_plan(other,extract_graph_intent(other))
            self.assertIsNotNone(different)
            self.assertNotEqual(legacy,different)
        json.dumps(legacy)

    def test_habitat_shared_diet_is_a_relation_with_an_explicit_habitat_condition(self):
        q='숲에 사는 새 중 직박구리와 같은 먹이 범주를 공유하는 새는?'
        plan=canonical_graph_plan(q,extract_graph_intent(q))
        self.assertEqual('shared_diet',plan['kind'])
        self.assertEqual('Forest',plan['conditions'][0]['value'])
        self.assertIsNone(plan['habitat'])

    def test_units_and_condition_order_normalize_but_operator_and_name_do_not(self):
        def make(q,taxon,mass,habitat):
            return canonical_graph_plan(q,built(q,{'kind':'taxon_traits','taxon':taxon,'conditions':[mass,habitat]}))
        a='Corvus 중 몸무게가 1000g 초과이고 숲에 사는 새'
        b='Corvus 중 숲에 사는 새 중 몸무게가 1kg 초과인 새'
        mass=lambda surface:condition('body_mass','num_gt',surface,threshold=1000,unit='g')
        habitat=condition('habitat','eq','숲에 사는','Forest')
        left=make(a,'Corvus',mass('몸무게가 1000g 초과이고'),habitat)
        right=make(b,'Corvus',mass('몸무게가 1kg 초과인'),habitat)
        self.assertIsNotNone(left);self.assertEqual(left,right)
        other_mass=mass('몸무게가 1kg 이하인');other_mass['op']='num_lte'
        changed=make(b.replace('초과인','이하인'),'Corvus',other_mass,habitat)
        self.assertIsNotNone(changed);self.assertNotEqual(left,changed)
        alias=make(a.replace('Corvus','까마귀속'),'까마귀속',mass('몸무게가 1000g 초과이고'),habitat)
        self.assertNotEqual(left,alias)  # only the execution resolver may equate aliases
        self.assertNotIn('source',left)
        self.assertNotIn('surface',json.dumps(left))

    def test_held_unsupported_and_specific_food_have_no_executable_canonical_plan(self):
        for q in ['참새목 중 열매를 먹지 않는 새','참새목 중 망고 열매를 먹는 새',
                  '청둥오리를 잡아먹는 새','참새목 중 숲이 기록된 열매를 먹는 새']:
            self.assertIsNone(canonical_graph_plan(q,extract_graph_intent(q)))


class SourceDiagnosticsTests(unittest.TestCase):
    def test_local_numeric_scope_and_unknown_relation_failures_keep_original_spans(self):
        q='Corvus 중 체중이 1kg 초과인 새'
        wrong={'kind':'taxon_traits','taxon':'Corvus','conditions':[
            condition('body_mass','num_gt','체중이 1kg 초과인',threshold=1,unit='g')]}
        self.assertEqual(['1kg'],[s.text for s in built(q,wrong).residual])
        wrong['conditions'][0]['threshold']=1000;wrong['taxon']=None
        self.assertEqual(['Corvus'],[s.text for s in built(q,wrong).residual])
        q='까치와 먹이 경쟁을 하는 새'
        intent=built(q,{'kind':'none','relation_text':'먹이 경쟁','unknown_relation':True})
        self.assertEqual(['먹이 경쟁'],[s.text for s in intent.residual])
        self.assertEqual('clarify',execution_gate(q,intent))

    def test_audit_exception_exposes_only_mentioned_exact_original_fragments(self):
        q='Corvus 중 숲에 사는 새'
        plan={'kind':'taxon_traits','taxon':'Corvus','conditions':[condition('habitat','eq','숲에 사는','Forest')]}
        answerer=GeminiAnswerer('dummy',urlopen=Mock())
        def document(value):
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}
        answerer._request=Mock(side_effect=[document(plan),document({'faithful':False,'issues':['Question condition 숲에 사는 is uncertain.']})])
        with self.assertRaises(sgi.SemanticIntentError) as caught:
            sgi.interpret(q,answerer.propose_structured_graph_intent)
        self.assertEqual('semantic_audit_rejected',caught.exception.reason)
        self.assertEqual(['숲에 사는'],[s.text for s in caught.exception.original_spans])
        self.assertEqual(2,answerer._request.call_count)
        self.assertEqual((),sgi.original_issue_spans(q,plan,['invented arbitrary model explanation']))


class ConsistentEligibilityTests(unittest.TestCase):
    def test_predicate_connectives_do_not_become_plants_and_enter_supported_family(self):
        for connective in ('기록되고','기록되며','관찰되면서','서식하고','생활하며','서식하지만'):
            q=f'Corvidae 중 숲에서 {connective} 열매를 먹는 새를 보여줘.'
            lexical=extract_graph_intent(q)
            with self.subTest(connective=connective):
                self.assertNotEqual('specific_fruit',lexical.kind)
                if execution_gate(q,lexical) == 'answer' or '관찰' in connective:
                    self.assertTrue(sgi._lexical_decides(q,lexical))
                else:
                    self.assertFalse(sgi._lexical_decides(q,lexical))
                    self.assertTrue(lexical.residual)

    def test_real_plants_species_conjunction_and_negative_veto_keep_existing_paths(self):
        for plant in ('망고','황금망고','새식물','은행나무'):
            q=f'참새목 중 {plant} 열매를 먹는 새는?'
            lexical=extract_graph_intent(q)
            self.assertEqual('specific_fruit',lexical.kind)
            self.assertTrue(sgi._lexical_decides(q,lexical))
        q='직박구리하고 동박새의 공통 상위 분류가 뭐야'
        lexical=extract_graph_intent(q)
        self.assertEqual({'직박구리','동박새'},{s.text for s in lexical.species})
        self.assertEqual('answer',execution_gate(q,lexical))
        for q in ('Corvidae 중 열매를 먹지 않는 새','까치와 먹이 경쟁을 하는 새',
                  '참새목에서 열매를 먹고 밤에만 활동하는 새'):
            provider=Mock()
            sgi.graph_intent_handler(q,provider=provider)
            provider.assert_not_called()
