"""Semantic plans may retain equivalent wording, never discard a distinct constraint."""
import unittest
from unittest.mock import patch
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate, to_graph_question
from test_semantic_graph_intent import P, C, TT, SD


class SemanticRestatementTests(unittest.TestCase):
    def gate(self, question, plan):
        return execution_gate(question, s.graph_intent_handler(question, provider=P(plan)))

    def test_three_part_name_and_separate_zero_share_keep_complete_scope(self):
        for name in ('Passer domesticus domesticus', 'Corvus corone cornix'):
            question=f'{name} 아종에서 씨앗을 먹는 기록을 찾아주세요. 먹이 비중은 0 초과면 됩니다.'
            food=C('diet_distribution','share_gt','씨앗을 먹는','seed',0)
            plan=TT(name,food)
            intent=s.graph_intent_handler(question,provider=P(plan))
            self.assertEqual(name,to_graph_question(question,intent).rank_name)
            self.assertEqual('clarify',self.gate(question,TT(' '.join(name.split()[:2]),food)))
            for extra in ('먹이 비중은 5 초과면 됩니다.', '먹이 비중은 0 이상이면 됩니다.', '비율은 0 초과면 됩니다.', '체중 비율은 0 초과면 됩니다.',
                          '확률은 0 초과면 됩니다.', '3종만 알려줘.'):
                self.assertEqual('clarify',self.gate(question.split('. ')[0]+'. '+extra,plan))
        question='참새목에서 씨앗과 열매를 먹는 새. 먹이 비중은 0 초과.'
        plan=TT('참새목',C('diet_distribution','share_gt','씨앗','seed',0),
                C('diet_distribution','share_gt','열매를 먹는','fruit',0))
        self.assertEqual('clarify',self.gate(question,plan))  # the repeated threshold's target is ambiguous

    def test_object_connective_auxiliary_is_a_request_but_taxon_subject_is_not(self):
        question='새를 대상으로 씨앗을 먹고 숲에 사는 경우만 모아 줘.'
        plan=TT(None,C('diet_distribution','share_gt','씨앗을 먹고','seed',0),C('habitat','eq','숲에 사는','Forest'))
        self.assertEqual('answer',self.gate(question,plan))
        for question in ('모아 중 숲에 사는 새', '모아를 기준으로 숲에 사는 새', '숲에 사는 모아 줘'):
            with self.subTest(question=question):
                self.assertIn('모아',[question[a:b] for a,b in s._named_taxa(question)])
                self.assertEqual('clarify',execution_gate(question,s.interpret(question,P(TT(None,C('habitat','eq','숲에 사는','Forest'))))))
        # The rule is grammatical, independent of a species-name list entry.
        with patch.object(s,'_taxon_names',return_value=(frozenset(),frozenset(('가어','나여')))):
            for token in ('가어','나여'):
                self.assertEqual([],s._named_taxa(f'결과를 {token} 주세요.'))
                self.assertNotEqual([],s._named_taxa(f'{token}의 서식지'))

    def test_reference_self_exclusion_is_identical_not_another_entity(self):
        for name in ('왜가리','직박구리','Anas platyrhynchos'):
            for exclusion in (f'{name} 말고',f'{name} 자신은 빼 주세요.',f'{name}를 제외하고'):
                question=f'{exclusion} {name}와 먹이 생태 범주가 같은 다른 새를 보여줘.'
                self.assertEqual('answer',self.gate(question,SD(name,'먹이 생태 범주가 같은')))
            question=f'고니 말고 {name}와 먹이 생태 범주가 같은 새.'
            self.assertEqual('clarify',self.gate(question,SD(name,'먹이 생태 범주가 같은')))
            question=f'{name} 말고 {name}와 먹이 생태 범주가 같은 새 중 곤충을 먹지 않는 새.'
            self.assertEqual('clarify',self.gate(question,SD(name,'먹이 생태 범주가 같은')))
            question=f'{name} 말고 {name}와 먹이 생태 범주가 같은 새.'
            self.assertEqual('clarify',self.gate(question,{'kind':'none'}))

    def test_equal_value_exclusion_requires_the_same_strict_numeric_boundary(self):
        for field,label in (('body_mass','몸무게'),('wing_length','날개 길이')):
            unit='g' if field=='body_mass' else 'mm'
            for op,comparison in (('num_gt','초과'),('num_lt','미만')):
                surface=f'{label}가 200{unit} {comparison}'
                question=f'참새목에서 {surface}인 새. 200{unit}인 기록은 제외해.'
                condition=C(field,op,surface,threshold=200,unit=unit)
                self.assertEqual('answer',self.gate(question,TT('참새목',condition)))
                for changed in (question.replace(f'200{unit}인',f'201{unit}인'),question+' 겨울에만 사는 새.'):
                    self.assertEqual('clarify',self.gate(changed,TT('참새목',condition)))
                inclusive_surface=surface.replace(comparison,'이상' if op=='num_gt' else '이하')
                inclusive=C(field,'num_gte' if op=='num_gt' else 'num_lte',inclusive_surface,threshold=200,unit=unit)
                self.assertEqual('clarify',self.gate(question.replace(surface,inclusive_surface),TT('참새목',inclusive)))
        question='참새목에서 체중이 0.2kg 초과인 새. 200g인 기록은 제외해.'
        condition=C('body_mass','num_gt','체중이 0.2kg 초과인',threshold=200,unit='g')
        self.assertEqual('answer',self.gate(question,TT('참새목',condition)))
        question='참새목에서 체중이 200g 이상인 새. 200g인 기록은 제외해.'
        # A provider cannot silently upgrade >= to > by appealing to the exclusion.
        condition=C('body_mass','num_gt','체중이 200g 이상인',threshold=200,unit='g')
        self.assertEqual('clarify',self.gate(question,TT('참새목',condition)))

    def test_other_birds_are_not_an_unlike_diet_relation(self):
        for name in ('왜가리','직박구리'):
            question=f'{name}랑 AVONET 먹이 생태 범주가 일치하는 다른 조류를 찾아줘요.'
            self.assertEqual('answer',self.gate(question,SD(name,'먹이 생태 범주가 일치하는')))
        def forbidden(*args):
            raise AssertionError('real negative/different relation must remain lexical')
        for question in ('왜가리랑 먹이가 다른 새', '직박구리와 식성이 같지 않은 새',
                         '까치와 서식지가 같고 먹이 범주가 다른 종'):
            intent=s.graph_intent_handler(question,provider=forbidden)
            self.assertEqual('extractor',intent.source)

    def test_exclusion_does_not_suppress_other_unsupported_constraints(self):
        plan=SD('왜가리','먹이 생태가 같은')
        for extra in ('겨울에 사는 새', '서울에서 관찰된 새', '먹이 경쟁하는 새', '가장 큰 새', '숲 또는 습지에 사는 새'):
            question='왜가리 말고 왜가리와 먹이 생태가 같은 '+extra
            self.assertNotEqual('answer',self.gate(question,plan))

    def test_unsupported_activity_filter_never_reaches_provider(self):
        def forbidden(*args):
            raise AssertionError('unsupported activity filter must stay unresolved')
        for condition in ('밤에만 활동하는', '낮에 활동하는', '야행성인', '새벽에 활동하는'):
            question = f'습지에 사는 새를 모아 줘. 단 {condition} 종으로.'
            intent = s.graph_intent_handler(question, provider=forbidden)
            self.assertNotEqual('answer', execution_gate(question, intent))

    def test_relation_surface_recovers_only_one_exact_reference_insertion(self):
        for species in ('왜가리','직박구리','Anas platyrhynchos'):
            for particle in ('와','랑','하고'):
                phrase=f'먹이 생태 범주가 {species}{particle} 같은'
                question=f'{species} 말고 {phrase} 다른 종을 알려줘.'
                intent=s.interpret(question,P(SD(species,'먹이 생태 범주가 같은')))
                self.assertEqual('answer',execution_gate(question,intent))
                for _, span in intent.evidence:
                    self.assertEqual(phrase,span.text)
                    self.assertEqual(span.text,question[span.start:span.end])
        plan=SD('왜가리','먹이 생태 범주가 같은')
        questions=(
            '왜가리 말고 먹이 생태 범주가 고니와 같은 새.',
            '왜가리 말고 먹이 생태 범주가 왜가리와 같지 않은 새.',
            '왜가리 말고 먹이 생태 범주가 숲에 사는 왜가리와 같은 새.',
            '왜가리 말고 먹이 생태 범주가 왜가리와 같은 새 또는 먹이 생태 범주가 왜가리와 같은 새.',
            '왜가리 말고 먹이 생태 범주가 왜가리 자신과 같은 새.',
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual('clarify',execution_gate(question,s.interpret(question,P(plan))))
