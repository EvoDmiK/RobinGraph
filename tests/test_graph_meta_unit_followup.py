"""Original-span query framing, unit labels and redundant exclusions remain fail-closed (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval import graph_condition_extractor as e
from robingraph.retrieval import graph_intent_schema as schema


class GraphMetaUnitFollowupTest(TestCase):
    def test_original_evidence_and_counterexamples(self):
        def cond(name,op,surface,**kw):return dict(trait_name=name,op=op,surface=surface,**kw)
        def tt(*conditions,unresolved=(),taxon=None):return dict(kind='taxon_traits',taxon=taxon,conditions=list(conditions),unresolved=list(unresolved),unknown_relation=False)
        def gate(q,p):return schema.execution_gate(q,s.interpret(q,lambda *_:p))
        rows=[]
        def test(label,q,p,expect):
         before=copy.deepcopy(p);after,changes=s.reconcile_graph_plan(q,p);actual=gate(q,after);assert p==before
         rows.append(dict(label=label,gate=actual,expected=expect,changes=changes));assert actual==expect,(label,actual,after,changes)
        p=tt(cond('body_mass','num_gt','몸무게가 0.2kg보다 무겁다는',threshold=200,unit='g'))
        test('descriptive_comparison','몸무게가 0.2kg보다 무겁다는 새를 찾아줘',p,'answer')
        p=tt(cond('beak_width','num_lt','부리 너비 2cm 미만',threshold=20,unit='cm'))
        test('unit_label_only','자료를 펼쳐서 부리 너비 2cm 미만인 새를 찾아줘',p,'answer')
        for n in (2,30):
         p=tt(cond('beak_width','num_lt','부리 너비 2cm 미만',threshold=n,unit='cm'))
         test('wrong_threshold_not_repaired','자료를 펼쳐서 부리 너비 2cm 미만인 새를 찾아줘',p,'clarify')
        q='부척 길이가 20mm 이상인 새를 찾아줘. 날개 길이 제한은 두지 않을게.'
        p=tt(cond('tarsus_length','num_gte','부척 길이가 20mm 이상인',threshold=20,unit='mm'),unresolved=['날개 길이 제한은 두지 않을게.'])
        test('unrestricted_other_measure',q,p,'answer')
        p=tt(cond('wing_length','num_gte','날개 길이가 20mm 이상인',threshold=20,unit='mm'),unresolved=['날개 길이 제한은 두지 않을게.'])
        test('unrestricted_conflicting_measure','날개 길이가 20mm 이상인 새. 날개 길이 제한은 두지 않을게.',p,'clarify')
        q='사는 곳은 제한하지 말고 몸무게 100g 이상인 새를 찾아줘'
        p=tt(cond('body_mass','num_gte','몸무게 100g 이상인',threshold=100,unit='g'),unresolved=['사는 곳은 제한하지 말고'])
        test('unrestricted_habitat',q,p,'answer')
        p=tt(cond('habitat','eq','숲에 사는',value='Forest'),unresolved=['숲에 살지 않는'])
        test('biological_negation_not_removed','숲에 사는 새. 숲에 살지 않는',p,'clarify')
        q='자료를 펼쳐서 먹이 유형이 식물·씨앗인 새를 찾아줘. 비율 조건을 뜻하는 건 아니야.'
        p=tt(cond('diet_category','eq','먹이 유형이 식물·씨앗인',value='PlantSeed'),unresolved=['자료를 펼쳐서','비율 조건을 뜻하는 건 아니야.'])
        test('category_discourse',q,p,'answer')
        p=tt(cond('diet_distribution','share_gt','씨앗을 먹는',value='seed',threshold=0),unresolved=['비율 조건을 뜻하는 건 아니야.'])
        test('rate_denial_not_removed_for_share','씨앗을 먹는 새. 비율 조건을 뜻하는 건 아니야.',p,'clarify')
        q='황조롱이와 먹이 생태 범주가 같은 새. 황조롱이는 빼고'
        p=dict(kind='shared_diet',species='황조롱이',relation_text='먹이 생태 범주가 같은',conditions=[],unresolved=['황조롱이는 빼고'],unknown_relation=False)
        test('self_exclusion',q,p,'answer')
        p['unresolved']=['직박구리는 빼고'];test('other_species_exclusion',q.replace('황조롱이는 빼고','직박구리는 빼고'),p,'clarify')
        for dimension in ('서식환경','서식 환경','사는곳','사는 곳'):
         q=dimension+' 제한하지 말고 몸무게 100g 이상인 새를 찾아줘'
         p=tt(cond('body_mass','num_gte','몸무게 100g 이상인',threshold=100,unit='g'),unresolved=[dimension+' 제한하지 말고'])
         test('whitespace_dimension',q,p,'answer')
        q='부리 길이는 제한하지 말고 몸무게 100g 이상인 새를 찾아줘'
        p=tt(cond('body_mass','num_gte','몸무게 100g 이상인',threshold=100,unit='g'),unresolved=['부리 길이는 제한하지 말고'])
        test('ambiguous_dimension_not_proved',q,p,'clarify')
        q='숲에 사는 새. 비율 조건을 뜻하는 건 아니야.'
        p=tt(cond('habitat','eq','숲에 사는',value='Forest'))
        test('ratio_explanation_requires_category',q,p,'clarify')
        q='먹이 범주는 제한하지 말고 청둥오리와 같은 먹이 생태 범주를 가진 새'
        p=dict(kind='shared_diet',species='청둥오리',relation_text='같은 먹이 생태 범주를 가진',conditions=[],unresolved=['먹이 범주는 제한하지 말고'],unknown_relation=False)
        test('unrestricted_conflicts_with_relation',q,p,'clarify')
        for q in ('황조롱이와 같은 식물 종의 열매를 먹는 새는?', '해안에 사는 새 중 황조롱이와 정확히 같은 식물 종의 열매를 먹는 새는?', '황조롱이와 같은 식물 종의 열매를 먹지 않는 새는?'):
         i=e.extract_graph_intent(q);g=schema.execution_gate(q,i);rows.append(dict(label='specific_food',question=q,gate=g,kind=i.kind,residual=[x.text for x in i.residual]))
         assert g==('clarify'if '않는'in q else'insufficient_data')
