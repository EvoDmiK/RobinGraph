"""Record evidence proves its explicit source field, not merely a shared enum value (mock plans)."""
import copy
from unittest import TestCase
from robingraph.retrieval import semantic_graph_intent as s
from robingraph.retrieval.graph_intent_schema import execution_gate


class GraphRecordFieldProofTest(TestCase):
    def test_source_planned_field_and_unresolved_matrix(self):
        rows=[]
        fields={'trophic_level':'영양 단계','trophic_niche':'먹이 생태 범주','diet_category':'먹이 유형'}
        for source_field,label in fields.items():
         q=f'Larus argentatus 종의 {label}가 Omnivore로 기록되어 있는지 확인해 줘.'
         for planned_field in fields:
          for unresolved in ([],['종의'],['확인해 줘'],[q[q.index('종의'):].rstrip('.')]):
           for ending in ('로','인'):
            raw=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name=planned_field,op='eq',value='Omnivore',surface=label+'가 Omnivore'+ending)],unresolved=unresolved,unknown_relation=False)
            before=copy.deepcopy(raw);candidate,changes=s.reconcile_graph_plan(q,raw);actual=execution_gate(q,s.interpret(q,lambda *_:candidate));want='answer'if planned_field==source_field else'clarify';assert raw==before;assert actual==want,(source_field,planned_field,unresolved,ending,actual,candidate)
            rows.append(dict(source_field=source_field,planned_field=planned_field,unresolved=unresolved,ending=ending,actual=actual))
        for label in ('서식지 밀도 범주','서식지 밀도','서식지밀도범주'):
         q='Larus argentatus 종의 '+label+'가 open으로 기록되어 있는지 확인해 줘.'
         raw=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name='habitat_density_category',op='eq',value='open',surface=label+'가 open으로')],unresolved=[q[q.index('종의'):].rstrip('.')],unknown_relation=False)
         after,changes=s.reconcile_graph_plan(q,raw);actual=execution_gate(q,s.interpret(q,lambda *_:after));assert actual=='answer',(label,actual,after);rows.append(dict(label=label,actual=actual))
        for surface in ('Omnivore로','영양 단계가 Omnivore로 먹이 생태 범주가 Omnivore로','영양 단계가 Omnivore로 영양 단계가 Omnivore로'):
         q='Larus argentatus 종의 '+surface+' 기록되어 있는지 확인해 줘.'
         raw=dict(kind='taxon_traits',taxon='Larus argentatus',conditions=[dict(trait_name='trophic_level',op='eq',value='Omnivore',surface=surface)],unresolved=['확인해 줘'],unknown_relation=False)
         after,changes=s.reconcile_graph_plan(q,raw);assert changes==[];assert execution_gate(q,s.interpret(q,lambda *_:after))=='clarify';rows.append(dict(ambiguous_surface=surface,actual='clarify'))
