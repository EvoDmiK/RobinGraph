import json,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent;phase=sys.argv[1];base=sys.argv[2] if len(sys.argv)>2 else 'https://robingraph-test.dove-nest.com'
rows=[]
for c in json.loads((p/'cases.json').read_text())['cases']:
 start=time.perf_counter();errors=[];r=None
 try:
  req=Request(base+'/v1/chat',data=json.dumps({'question':c['question'],'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 RobinGraph-Regression'})
  r=json.load(urlopen(req,timeout=25));payload=r['result'].get('payload',{});status=payload.get('status')
  if c['outcome']=='clarify':
   if r['disposition']!='clarify':errors.append('unsafe_condition_ignored')
  elif c['outcome']=='food_guidance':
   if status!='insufficient_data' or r['disposition']!='abstain':errors.append('food_gap_not_explained_as_insufficient')
   if payload.get('items') or payload.get('has_more'):errors.append('unsupported_food_silently_queried')
   text=' '.join([r.get('answer_text',''),payload.get('text',''),*payload.get('limitations',[])])
   if c['requested_food'] not in text or c['broader_category'] not in text:errors.append('requested_food_or_broader_category_not_explained')
  else:
   if r['result']['kind']!='graph_query' or status not in ('answer','empty','insufficient_data'):errors.append('supported_food_not_queried')
   if c['outcome']=='query':
    taxon=payload.get('taxon') or {}
    if (taxon.get('scientific_name'),taxon.get('rank'))!=(c['taxon'],c['rank']):errors.append('taxon_scope_changed')
    expected=c['conditions']
   else:expected=[{'trait_name':c['trait'],'value':c['value']}]
   expected_keys=sorted((e['trait_name'],next(iter(e['value'])),0) for e in expected)
   actual_keys=sorted((e['trait_name'],e.get('value'),e.get('threshold')) for e in payload.get('conditions',[]))
   if actual_keys!=expected_keys:errors.append('food_conditions_changed')
 except Exception as e:errors.append(type(e).__name__)
 rows.append({'case':c,'response':r,'errors':errors,'elapsed_ms':round((time.perf_counter()-start)*1000,2)})
report={'phase':phase,'base':base,'count':len(rows),'passed':sum(not r['errors'] for r in rows),'failures':[{'id':r['case']['id'],'errors':r['errors']} for r in rows if r['errors']],'rows':rows,'response_mocking':False}
(p/f'{phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))
