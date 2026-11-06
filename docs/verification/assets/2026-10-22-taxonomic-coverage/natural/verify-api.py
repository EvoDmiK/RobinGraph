"""Independent expected-meaning checks against actual TEST API responses."""
import argparse,json,time
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('phase');parser.add_argument('--base',default='http://127.0.0.1:18001');args=parser.parse_args()
cases=json.loads((p/'independent-cases.json').read_text())['cases'];rows=[];failures=[]
def normalized_expected(c):
 op=c['op'];value=c['value'];threshold=None
 if op.startswith('share_'):value,threshold=next(iter(value.items()))
 elif op in ('gte','lte','gt','lt'):op='num_'+op;threshold=value;value=None
 return (c['trait_name'],op,value,threshold,c['unit'])
def normalized_actual(c):return (c['trait_name'],c['op'],c.get('value'),c.get('threshold'),c.get('unit'))
for case in cases:
 errors=[];started=time.perf_counter()
 try:
  req=Request(args.base+'/v1/chat',data=json.dumps({'question':case['question'],'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 RobinGraph-Test-Verification'})
  response=json.load(urlopen(req,timeout=35));payload=response['result'].get('payload',{});status=payload.get('status');disposition=response['disposition']
  if case['outcome']=='hold':
   if disposition!='clarify' and status!='insufficient_data':errors.append('unsafe_execution_of_held_condition')
  elif case['outcome']=='insufficient':
   if status!='insufficient_data':errors.append('expected_explicit_insufficient')
  else:
   if status not in ('answer','empty','insufficient_data'):errors.append('supported_query_not_executed')
   actual=payload.get('taxon');expected=case['taxon']
   if expected and (not actual or actual.get('rank')!=case['rank'] or actual.get('scientific_name')!=expected):errors.append('taxon_scope_mismatch')
   if expected is None and actual is not None:errors.append('catalog_scope_changed')
   conditions=sorted([normalized_actual(c) for c in payload.get('conditions',[])],key=repr)
   if conditions!=sorted([normalized_expected(c) for c in case['conditions']],key=repr):errors.append('original_conditions_changed_or_lost')
   if case['outcome']=='empty' and status!='empty':errors.append('expected_empty_not_no_data')
  if case['id']=='IT-001' and (status!='answer' or not payload.get('items')):errors.append('original_user_failure_not_fixed')
  if case['rank']=='subspecies' and case['outcome']=='insufficient' and ('아종' not in payload.get('text','') or '부모 종' not in payload.get('text','')):errors.append('subspecies_limit_not_explained')
 except Exception as e:response=None;errors.append(type(e).__name__)
 rows.append({'case':case,'elapsed_ms':round((time.perf_counter()-started)*1000,3),'response':response,'errors':errors})
 if errors:failures.append({'id':case['id'],'question':case['question'],'errors':errors})
report={'phase':args.phase,'base':args.base,'response_mocking':False,'bird_db_writes':0,'count':len(rows),'passed':len(rows)-len(failures),'failures':failures,'rows':rows}
(p/f'independent-api-{args.phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False));assert not failures
