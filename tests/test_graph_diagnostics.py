"""Independent injected-handler tests: no external MLflow/provider/API/DB calls."""
import json,sys,threading,unittest
from contextlib import contextmanager
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock,patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from asgi_client import TestClient
from robingraph import tracing
from robingraph.api.drf import create_django_app
from robingraph.api.services import ApiService
from robingraph.api.schemas import ChatRequest
from robingraph.retrieval.graph_intent_schema import GraphIntent,span_of
from test_graph_semantic_api import NEW,OLD,new_intent,payload
from robingraph.retrieval.hybrid import HybridSearchOutcome
from test_mlflow_tracing import _result
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from test_chat_clarification import CANDIDATE

SECRET='PRIVATE_FAKE_SECRET_3984'
class Live:
 def __init__(self,name,root,attrs,sdk):self.name=name;self.root=root;self.attrs=attrs;self.sdk=sdk;self.inputs=None;self.outputs=None;self.tags=None
 def set_inputs(self,v):self.inputs=v
 def set_outputs(self,v):self.outputs=v
 def set_attribute(self,k,v):self.set_attributes({k:v})
 def set_attributes(self,v):
  if self.sdk.failure=='attribute':raise RuntimeError(SECRET)
  self.attrs.update(v)
class Fake:
 def __init__(self,failure=None):self.failure=failure;self.requestid=ContextVar('fake_request_id',default=None);self.stack=ContextVar('fake_span_stack',default=());self.spans=[];self.lock=threading.Lock()
 @contextmanager
 def start_span(self,*,name,span_type,attributes):
  if self.failure=='start':raise RuntimeError(SECRET)
  old=self.stack.get();s=Live(name,old[0] if old else None,dict(attributes),self);s.root=s.root or s;s.requestid=self.requestid.get()
  with self.lock:self.spans.append(s)
  token=self.stack.set(old+(s,))
  try:yield s
  finally:
   self.stack.reset(token)
   if self.failure=='end':raise RuntimeError(SECRET)
 def update_current_trace(self,*,tags):
  if self.failure=='tags':raise RuntimeError(SECRET)
  self.stack.get()[0].tags=dict(tags)

def scenario(case,barrier=None):
 q=NEW;mode='active';expected=None
 def plan(question):
  with tracing.span('graph_intent.plan') as s:
   if case in ('audit','proposal','invalid_plan','surface','unsupported_relation'):
    reason,stage={'audit':('semantic_audit_rejected','semantic_audit'),'proposal':('interpretation_error','interpretation'),'invalid_plan':('invalid_plan','interpretation'),'surface':('plan_validation_rejected','plan_validation'),'unsupported_relation':('unsupported_relation','plan_validation')}[case]
    tracing.note_outcome(reason,stage);s.set_attributes({'diagnostic.reason':reason})
    if barrier:barrier.wait(10)
    if case in ('audit','proposal','invalid_plan'):raise RuntimeError(SECRET)
    return GraphIntent(None,ambiguity=('other',),source='semantic')
   if case=='unsupported':return replace(new_intent(question),unsupported=('ranking',))
   if case=='residual':return replace(new_intent(question),residual=(span_of(question,'열매'),))
   if case=='negation':return replace(new_intent(question),negation=(span_of(question,'열매'),))
   if case=='ambiguity':return replace(new_intent(question),ambiguity=('other',))
   if case in ('delegate','delegate_answer'):return GraphIntent(None,source='semantic')
   return new_intent(question)
 def graph(parsed,**kw):
  with tracing.span('graph_query.lookup'):
   if barrier:barrier.wait(10)
   if case=='upstream':raise RuntimeError(SECRET)
   return payload({'empty':'empty','insufficient':'insufficient_data'}.get(case,'answer'))
 opts=dict(graph_intent_handler=plan,graph_plan_handler=plan,graph_intent_mode=mode,graph_question_handler=graph)
 if case=='absent':opts['graph_question_handler']=None
 if case=='meaning':q='청둥오리랑 비슷한 식생을 가진 새를 알려줘'
 if case in ('delegate','delegate_answer'):
  q='기후변화 관련 조류 문헌을 찾아줘';opts['semantic_router']=Mock();opts['semantic_router'].classify.return_value='evidence';opts['search_handler']=lambda *args,**kw:HybridSearchOutcome((_result(),) if case=='delegate_answer' else (),())
 if case=='shadow':
  q=OLD;opts['graph_intent_mode']='shadow'
  def shadow(question):
   tracing.note_outcome('semantic_audit_rejected','semantic_audit')
   raise RuntimeError(SECRET)
  opts['graph_intent_handler']=shadow
 expected={'audit':('clarify','semantic_audit_rejected','semantic_audit'),
 'proposal':('error','interpretation_error','interpretation'),'invalid_plan':('error','invalid_plan','interpretation'),
 'surface':('clarify','plan_validation_rejected','plan_validation'),'unsupported_relation':('clarify','unsupported_relation','plan_validation'),
 'unsupported':('clarify','unsupported_conditions','plan_validation'),'residual':('clarify','unresolved_conditions','plan_validation'),
 'negation':('clarify','negated_conditions','plan_validation'),'ambiguity':('clarify','ambiguous_conditions','plan_validation'),
 'meaning':('clarify','ambiguous_conditions','routing'),'empty':('abstain','no_matching_results','retrieval'),
 'insufficient':('abstain','insufficient_data','retrieval'),'upstream':('error','upstream_error','retrieval'),
 'absent':('error','handler_unavailable','retrieval'),'answer':('answer','none','none'),'shadow':('answer','none','none'),
 'delegate_answer':('answer','none','none'),'delegate':('abstain','evidence_not_found','retrieval')}[case]
 return q,opts,expected
CASES=['audit','proposal','invalid_plan','surface','unsupported_relation','unsupported','residual','negation','ambiguity','meaning','empty','insufficient','upstream','absent','answer','shadow','delegate','delegate_answer']
class Tests(unittest.TestCase):
 def tearDown(self):self.assertEqual({},tracing.collected_outcome())
 def run_case(self,case,sdk,http=False,barrier=None):
  q,opts,expected=scenario(case,barrier)
  if http:
   r=TestClient(create_django_app(**opts)).post('/v1/chat',json={'question':q,'defer_enrichment':True,'defer_discovery':True});self.assertEqual(200,r.status_code);return r.json(),expected
  return ApiService(**opts).chat(request=ChatRequest(question=q,defer_enrichment=True,defer_discovery=True)).model_dump(mode='json'),expected
 def test_reason_matrix_and_exact_body_preservation(self):
  for case in CASES:
   with self.subTest(case=case):
    with patch.object(tracing,'_mlflow',None):before,_=self.run_case(case,None,http=True)
    sdk=Fake()
    with patch.object(tracing,'_mlflow',sdk):after,expected=self.run_case(case,sdk,http=True)
    self.assertEqual(before,after);roots=[x for x in sdk.spans if x.root is x];self.assertEqual(1,len(roots));root=roots[0]
    self.assertEqual(expected,tuple(root.tags[k] for k in ('response_disposition','response_reason','failure_stage')))
    self.assertEqual(after['disposition'],root.tags['response_api_disposition']);self.assertNotIn(SECRET,json.dumps(root.tags))
    self.assertTrue(all(s.root is root for s in sdk.spans))
 def test_export_failures_preserve_every_response(self):
  for case in CASES:
   with patch.object(tracing,'_mlflow',None):expected,_=self.run_case(case,None)
   for failure in ('start','attribute','tags','end'):
    with self.subTest(case=case,failure=failure),patch.object(tracing,'_mlflow',Fake(failure)):
     actual,_=self.run_case(case,None);self.assertEqual(expected,actual)
 def test_concurrent_requests_are_matched_to_their_own_root(self):
  sdk=Fake();cases=['audit','proposal','empty','answer'];barrier=threading.Barrier(len(cases))
  def run(case):
   token=sdk.requestid.set(case)
   try:body,expected=self.run_case(case,sdk,barrier=barrier)
   finally:sdk.requestid.reset(token)
   root=next(s for s in sdk.spans if s.root is s and s.requestid==case)
   self.assertEqual(body,root.outputs)
   return root,expected
  with patch.object(tracing,'_mlflow',sdk),ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,cases))
  self.assertEqual(4,len({id(r) for r,e in results}))
  for root,expected in results:
   children=[s for s in sdk.spans if s.root is root]
   self.assertGreaterEqual(len(children),2)
   self.assertEqual(expected,tuple(root.tags[k] for k in ('response_disposition','response_reason','failure_stage')))
 def test_all_name_resolution_statuses_keep_distinct_outcomes(self):
  q='천둥오리와 서식지가 겹치면서 먹이가 다른 새는?'
  matched=dict(mention='천둥오리',status='matched',method='graph_exact',canonical_name='Anas platyrhynchos',taxon_id='mallard',concept_set_id='active',taxonomy_release='v2025b')
  cases=[(matched,('answer','none','none')),(CANDIDATE,('clarify','ambiguous_name','name_resolution')),
   (dict(mention='천둥오리',status='not_found',method='none'),('clarify','taxon_not_found','name_resolution')),
   (dict(mention='천둥오리',status='unavailable',method='none'),('error','upstream_error','name_resolution')),
   (RuntimeError(SECRET),('error','upstream_error','name_resolution'))]
  for resolved,expected in cases:
   with self.subTest(status=str(resolved)[:40]):
    graph=Mock(return_value=payload());resolver=Mock(side_effect=resolved) if isinstance(resolved,Exception) else Mock(return_value=resolved)
    app=create_django_app(graph_intent_mode='active',graph_intent_handler=extract_graph_intent,taxon_name_resolution_handler=resolver,graph_question_handler=graph)
    with patch.object(tracing,'_mlflow',None):before=TestClient(app).post('/v1/chat',json={'question':q}).json()
    graph.reset_mock();sdk=Fake()
    with patch.object(tracing,'_mlflow',sdk):response=TestClient(app).post('/v1/chat',json={'question':q})
    self.assertEqual(200,response.status_code);self.assertEqual(before,response.json())
    root=next(s for s in sdk.spans if s.root is s)
    self.assertEqual(expected,tuple(root.tags[k] for k in ('response_disposition','response_reason','failure_stage')))
    if expected[0]=='answer':
     graph.assert_called_once();self.assertEqual(('Anas platyrhynchos',),graph.call_args.args[0].names)
    else:graph.assert_not_called()
    self.assertNotIn(SECRET,json.dumps(root.tags))
 def test_tag_allowlist_rejects_raw_values(self):
  sdk=Fake()
  with patch.object(tracing,'_mlflow',sdk):
   token=tracing.begin_outcome()
   try:tracing.note_outcome(SECRET,'https://user:password@example.invalid');found=tracing.collected_outcome()
   finally:tracing.end_outcome(token)
  self.assertEqual({'reason':'unknown','stage':'unknown'},found)
  self.assertNotIn(SECRET,json.dumps(tracing.resolve_response_tags('clarify',reason=SECRET,stage=SECRET)))
if __name__=='__main__':unittest.main()
