"""HTTP/service + real generator/parser instrumentation; mocked transport/graph/MLflow only."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'tests'))
from asgi_client import TestClient
from robingraph import tracing
from robingraph.api.drf import create_django_app
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
from robingraph.retrieval import semantic_graph_intent as sgi
from test_graph_diagnostics import Fake
from test_graph_semantic_api import payload
Q='AVONET에서 까치와 같은 먹이 생태 범주로 묶인 다른 종을 찾아 줘.'
PLAN={'kind':'shared_diet','species':'까치','relation_text':'같은 먹이 생태 범주'}
AUDIT={'faithful':True,'issues':[]}
def document(x):return {'candidates':[{'content':{'parts':[{'text':json.dumps(x)}]}}]}
def app(plan=PLAN,audit=AUDIT,fail_stage=None):
 answerer=GeminiAnswerer('mock-key',urlopen=Mock(side_effect=AssertionError('no transport permitted')))
 seq=[document(plan),document(audit)]
 if fail_stage=='plan':seq=[GeminiAnswerError('PRIVATE_TRANSPORT_DETAIL')]
 if fail_stage=='audit':seq=[document(plan),GeminiAnswerError('PRIVATE_TRANSPORT_DETAIL')]
 answerer._request=Mock(side_effect=seq)
 handler=lambda q:sgi.interpret(q,answerer.propose_structured_graph_intent)
 graph=Mock(return_value=payload())
 return create_django_app(graph_intent_mode='active',graph_intent_handler=handler,graph_plan_handler=handler,graph_question_handler=graph),graph,answerer
class Tests(unittest.TestCase):
 def tearDown(self):self.assertEqual({},tracing.collected_outcome())
 def run_case(self,**kwargs):
  sdk=Fake();a,graph,answerer=app(**kwargs)
  with patch.object(tracing,'_mlflow',sdk):r=TestClient(a).post('/v1/chat',json={'question':Q})
  self.assertEqual(200,r.status_code)
  root=next(s for s in sdk.spans if s.root is s)
  return r.json(),root,sdk.spans,graph,answerer
 def test_lower_real_instrumentation_propagates_same_request_causes(self):
  cases=[({},('answer','none','none'),True),
   ({'audit':{'faithful':False,'issues':['omitted constraint']}},('clarify','semantic_audit_rejected','semantic_audit'),False),
   ({'audit':{'faithful':True,'issues':['invented predicate']}},('clarify','semantic_audit_rejected','semantic_audit'),False),
   ({'plan':{**PLAN,'species':'까마귀'}},('clarify','plan_validation_rejected','plan_validation'),False),
   ({'fail_stage':'plan'},('error','interpretation_error','interpretation'),False),
   ({'fail_stage':'audit'},('error','interpretation_error','semantic_audit'),False),
   ({'plan':[]},('error','invalid_plan','interpretation'),False)]
  for kwargs,expected,executes in cases:
   with self.subTest(kwargs=kwargs):
    body,root,spans,graph,answerer=self.run_case(**kwargs)
    self.assertEqual(expected,tuple(root.tags[k] for k in ('response_disposition','response_reason','failure_stage')))
    self.assertTrue(all(s.root is root for s in spans))
    if executes:graph.assert_called_once()
    else:graph.assert_not_called()
    self.assertNotIn('PRIVATE_TRANSPORT_DETAIL',json.dumps(root.tags))
    if expected[1]=='semantic_audit_rejected':
     self.assertEqual(PLAN,next(s.outputs for s in spans if s.name=='graph_intent.plan'))
     self.assertEqual(kwargs['audit'],next(s.outputs for s in spans if s.name=='graph_intent.audit'))
     self.assertEqual(2,answerer._request.call_count)
     self.assertFalse(any(s.name=='graph_intent.validation' for s in spans))
    if expected[1]=='plan_validation_rejected':
     validation=next(s for s in spans if s.name=='graph_intent.validation')
     self.assertEqual('surface not in question',validation.attrs['rejection_detail'])
     self.assertEqual(kwargs['plan'],validation.inputs)
     route=next(s for s in spans if s.name=='graph_intent.route')
     self.assertIsNotNone(route.outputs)
    with patch.object(tracing,'_mlflow',None):
     before_app,_,_=app(**kwargs);before=TestClient(before_app).post('/v1/chat',json={'question':Q}).json()
    self.assertEqual(before,body)
 def test_rejected_request_does_not_poison_next_success(self):
  self.run_case(audit={'faithful':False,'issues':[]})
  body,root,spans,graph,_=self.run_case()
  self.assertEqual('answer',body['disposition']);self.assertEqual('none',root.tags['response_reason']);graph.assert_called_once()
if __name__=='__main__':unittest.main()
