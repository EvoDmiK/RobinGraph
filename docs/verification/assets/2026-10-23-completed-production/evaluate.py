"""Read-only live release regression. No credentials or DB writes. Existing cases reused."""
import argparse,json,time
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--cases',default='/tmp/rg-completed-release-cases.json');p.add_argument('--out',required=True);p.add_argument('--target',default='test');p.add_argument('--only',default='');a=p.parse_args()
health=json.load(urlopen(a.base+'/health',timeout=15));assert health['deployment_target']==a.target,(health,a.target)
cases=json.loads(Path(a.cases).read_text())['cases'];rows=[]
if a.only:cases=[c for c in cases if c['check'] in a.only.split(',')]
def post(q,**kw):
 req=Request(a.base+'/v1/chat',data=json.dumps(dict(question=q,defer_enrichment=True,defer_discovery=True,**kw)).encode(),headers={'Content-Type':'application/json','User-Agent':'RobinGraph-Release-Regression'})
 with urlopen(req,timeout=65) as r:return json.load(r)
def norm(c):
 op=c['op'];value=c.get('value');threshold=c.get('threshold')
 if isinstance(value,dict) and op.startswith('share_'):value,threshold=next(iter(value.items()))
 elif op in ('gte','lte','gt','lt'):op='num_'+op;threshold=value;value=None
 return(c['trait_name'],op,value,threshold,c.get('unit'))
def signature(r):
 d=r['result'].get('payload',{});return {k:d.get(k) for k in ('status','taxon','conditions','coverage','items','has_more')}
def fingerprint(r):
 result=r['result'];d=result.get('payload',{})
 return dict(selected_intent=r['selected_intent'],disposition=r['disposition'],kind=result['kind'],status=d.get('status'),title=d.get('title'),ids=[x.get('taxon',{}).get('taxon_id') for x in d.get('items',[])],paths=d.get('paths',[]))
for c in cases:
 started=time.monotonic();errors=[];responses=[]
 try:
  extra={k:c[k] for k in ('intent','filters') if k in c};r=post(c['question'],**extra);responses.append(r);d=r['result'].get('payload',{});status=d.get('status');check=c['check']
  if check=='taxonomic':
   if c['outcome']=='hold':
    if r['disposition']!='clarify' and status!='insufficient_data':errors.append('unsafe_execution')
   elif c['outcome']=='insufficient':
    if status!='insufficient_data':errors.append('expected_insufficient')
    if c['rank']=='subspecies' and not all(x in d.get('text','') for x in ['아종','부모 종']):errors.append('subspecies_scope_not_explained')
   else:
    if status not in ('answer','empty','insufficient_data'):errors.append('not_queried')
    t=d.get('taxon') or {}
    if (t.get('scientific_name'),t.get('rank'))!=(c['taxon'],c['rank']):errors.append('taxon_scope_changed')
    if sorted(map(norm,d.get('conditions',[])),key=repr)!=sorted(map(norm,c['conditions']),key=repr):errors.append('conditions_changed')
    if c['outcome']=='empty' and status!='empty':errors.append('expected_empty')
   if c['id']=='IT-001' and (status!='answer' or not d.get('items')):errors.append('original_failure_not_fixed')
  elif check=='alias':
   raw=post(c['raw_question']);responses.append(raw)
   if signature(r)!=signature(raw):errors.append('alias_differs')
   if status not in ('answer','empty','insufficient_data') or not d.get('conditions'):errors.append('not_queried')
   if status=='answer' and any(x not in ' '.join([d.get('text',''),*d.get('limitations',[])]) for x in c['required_terms']):errors.append('raw_scope_not_explained')
  elif check=='food_gap':
   if status!='insufficient_data' or r['disposition']!='abstain' or d.get('items'):errors.append('unsupported_food_queried')
   if any(x not in json.dumps(r,ensure_ascii=False) for x in c['required_terms']):errors.append('food_gap_not_explained')
  elif check=='clarification_flow':
   choices=r['result'].get('choices',[])
   if r['disposition']!='clarify' or len(choices)!=2:raise AssertionError('expected_two_meaning_choices')
   r=post(choices[c['choice_index']]['question']);responses.append(r)
   candidates=(r.get('entity_resolution') or {}).get('candidates',[])
   if c['expect_name_confirmation'] and not candidates:errors.append('name_not_confirmed')
   if candidates:
    candidate=next(x for x in candidates if x['scientific_name']==c['expected_species'])
    r=post(candidate['question'],intent=candidate.get('route_intent','profile'));responses.append(r)
   result=r['result'];qa=result.get('question_answer') or {};groups=(qa.get('relations') or {}).get('groups',[])
   if r['disposition']!='answer' or qa.get('topic')!='ecological_related':errors.append('relation_not_answered')
   if not groups or any(g.get('relation')!=c['relation'] for g in groups):errors.append('relation_changed')
   if not any(g.get('items') for g in groups):errors.append('no_related_species')
  elif check=='legacy':
   if fingerprint(r)!=c['expected_fingerprint']:errors.append('legacy_fingerprint_changed_review_required')
  elif check=='explicit':
   if r['route_method']!='explicit' or r['result']['kind']!=c['result_kind']:errors.append('explicit_route_changed')
 except Exception as e:errors.append(type(e).__name__+': '+str(e)[:180])
 rows.append(dict(case=c,responses=responses,errors=errors,elapsed_ms=round((time.monotonic()-started)*1000)))
 print(c['id'],'PASS' if not errors else errors,flush=True)
 Path(a.out).write_text(json.dumps(dict(base=a.base,health=health,response_mocking=False,bird_db_writes=0,count=len(rows),passed=sum(not x['errors'] for x in rows),rows=rows),ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(rows),'passed':sum(not x['errors'] for x in rows),'failures':[{'id':x['case']['id'],'errors':x['errors']} for x in rows if x['errors']]},ensure_ascii=False))
raise SystemExit(int(any(x['errors'] for x in rows)))
