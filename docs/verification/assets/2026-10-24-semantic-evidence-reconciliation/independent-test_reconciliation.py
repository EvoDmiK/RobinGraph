"""Independent deterministic normalization checks; no provider/API/DB call."""
import copy,importlib.util,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'tests'))
from robingraph import tracing
from robingraph.retrieval.graph_intent_schema import execution_gate
from test_graph_diagnostics import Fake
PATH=Path(os.environ.get('RG_RECON_MODULE', '/tmp/rg-semantic-evidence-reconciliation/src/robingraph/retrieval/semantic_graph_intent.py'))
spec=importlib.util.spec_from_file_location('robingraph.retrieval.review_candidate',PATH);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
ART=ROOT/'docs/verification/assets/2026-10-24-blocked-response-tracing/live-traces.json'
originals={r['case']:r for r in json.loads(ART.read_text())['rows']}
def raw(case):return copy.deepcopy(next(x['outputs'] for x in originals[case]['diagnostic_spans'] if x['name']=='graph_intent.plan'))
def example(case):return originals[case]['question'],raw(case)
class Tests(unittest.TestCase):
 def reconcile(self,q,p,changes):
  before=copy.deepcopy(p);candidate,proof=s.reconcile_graph_plan(q,p);self.assertEqual(before,p)
  self.assertEqual(changes,bool(proof),(q,p,candidate,proof))
  if changes:
   self.assertEqual('answer',execution_gate(q,s._build(q,candidate)))
   self.assertEqual({k:v for k,v in p.items() if k not in ('conditions','relation_text','unresolved')},{k:v for k,v in candidate.items() if k not in ('conditions','relation_text','unresolved')})
  else:self.assertEqual(before,candidate)
  return candidate,proof
 def test_original_three_repaired(self):
  for key in ('known_false_hold','shared_reference','numeric_restatement'):
   with self.subTest(key=key):self.reconcile(*example(key),True)
 def test_endings_positive_and_boundary_guards(self):
  q,p=example('known_false_hold')
  for ending in ('있고','있으며','있는'):
   with self.subTest(ending=ending):self.reconcile(q.replace('있고',ending),p,True)
  for ending in ('있고만','있고도','있지만','없고','있지 않고','있고는','있던','아니고'):
   with self.subTest(ending=ending):self.reconcile(q.replace('있고',ending),p,False)
  duplicated=q+' 숲이 서식지로 기록돼 있고 또 숲이 서식지로 기록돼 있고.'
  self.reconcile(duplicated,p,False)
  altered=copy.deepcopy(p);altered['conditions'][0]['value']='Wetland';self.reconcile(q,altered,False)
 def test_reference_recovery_unique_same_and_immediate_only(self):
  q,p=example('shared_reference')
  for relation in ('같은','동일한','일치하는','비슷한','유사한'):
   with self.subTest(relation=relation):self.reconcile(q.replace('같은',relation),p,True)
  for replacement in ('다른','같지 않은','같은듯한','같은만','같은데 아닌'):
   with self.subTest(relation=replacement):
    # An affirmative recovered span may exist in the final case, but the
    # whole question must still fail existing guards/audit before execution.
    candidate,proof=s.reconcile_graph_plan(q.replace('같은',replacement),p)
    if replacement!='같은데 아닌':self.assertFalse(proof)
  self.reconcile(q.replace('직박구리와','까치와'),p,False)
  self.reconcile(q.replace('직박구리와','숲의 직박구리와'),p,False)
  self.reconcile(q+' 먹이 생태 범주가 직박구리와 같은 새도 알려줘.',p,False)
  self.reconcile(q.replace('먹이 생태 범주가 직박구리와','먹이 생태 범주가. 별도로 직박구리와'),p,False)
 def test_recovery_does_not_start_inside_a_word_or_override_known_negation(self):
  q,p=example('known_false_hold')
  for prefix in ('열대숲이','가짜숲이','바다숲이'):
   with self.subTest(prefix=prefix):self.reconcile(q.replace('숲이',prefix),p,False)
  q,p=example('shared_reference')
  for prefix in ('가짜먹이 생태 범주가','먹이 생태 범주가 아니라 먹이 생태 범주가'):
   with self.subTest(prefix=prefix):self.reconcile(q.replace('먹이 생태 범주가',prefix),p,False)
 def test_numeric_normalization_only_proves_same_strict_bound(self):
  q,p=example('numeric_restatement')
  self.reconcile(q,p,True)
  for op,comparison in [('num_lt','미만인'),('num_gt','초과인')]:
   pp=copy.deepcopy(p);pp['conditions'][0]['op']=op;pp['conditions'][0]['surface']='몸무게가 180g '+comparison
   qq=q.replace('몸무게가 180g을 넘는',pp['conditions'][0]['surface']);self.reconcile(qq,pp,True)
  pp=copy.deepcopy(p);pp['conditions'][0]['surface']='몸무게가 0.18kg 초과인';self.reconcile(q.replace('몸무게가 180g을 넘는',pp['conditions'][0]['surface']),pp,True)
  for op,comparison in [('num_gte','이상인'),('num_lte','이하인')]:
   pp=copy.deepcopy(p);pp['conditions'][0]['op']=op;pp['conditions'][0]['surface']='몸무게가 180g '+comparison
   self.reconcile(q.replace('몸무게가 180g을 넘는',pp['conditions'][0]['surface']),pp,False)
  for phrase in ('181g인 기록은 제외해','180kg인 기록은 제외해','부리 길이가 180mm인 기록은 제외해','꼬리 길이가 180g인 기록은 제외해'):
   qq=q.replace('180g인 기록은 제외해',phrase);pp=copy.deepcopy(p);pp['unresolved']=[phrase];self.reconcile(qq,pp,False)
 def test_other_unresolved_or_unknown_relation_never_dropped(self):
  q,p=example('numeric_restatement')
  p['unresolved'].append('밤에만 활동하는');self.reconcile(q+' 밤에만 활동하는 종.',p,False)
  q,p=example('shared_reference');p['unknown_relation']=True;self.reconcile(q,p,False)
 def test_speculative_validation_preserves_parent_outcome(self):
  fake=Fake()
  with patch.object(tracing,'_mlflow',fake):
   token=tracing.begin_outcome()
   try:
    tracing.note_outcome('semantic_audit_rejected','semantic_audit');before=tracing.collected_outcome()
    for key in ('known_false_hold','shared_reference','numeric_restatement'):
     self.reconcile(*example(key),True);self.assertEqual(before,tracing.collected_outcome())
    q,p=example('numeric_restatement');p['unresolved'].append('extra');self.reconcile(q,p,False);self.assertEqual(before,tracing.collected_outcome())
   finally:tracing.end_outcome(token)
if __name__=='__main__':unittest.main()
