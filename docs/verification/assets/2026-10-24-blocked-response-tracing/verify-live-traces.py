"""Actual TEST calls followed by same-request MLflow trace/tag inspection; no mocks."""
import os,json,subprocess,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
out=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-24-blocked-response-tracing')
s=json.loads(subprocess.check_output(['docker','--context','orbstack','inspect','robingraph-api-test']))[0]
env=dict(v.split('=',1) for v in s['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='test'
assert env['ROBINGRAPH_GRAPH_INTERPRETER']=='semantic'
for k,v in env.items():
 if k.startswith('MLFLOW_'):os.environ[k]=v
os.environ.update(MLFLOW_HTTP_REQUEST_TIMEOUT='30',MLFLOW_HTTP_REQUEST_MAX_RETRIES='0')
assert os.environ['MLFLOW_TRACKING_URI'].rstrip('/')=='https://mlflow.dove-nest.com'
from mlflow import MlflowClient
c=MlflowClient()
cases=[
 ('meaning_choice',{'question':'청둥오리랑 비슷한 식생을 가진 새들을 알려줘'},'ambiguous_conditions'),
 ('missing_filter',{'question':'관찰 기록','intent':'observations'},'filter_mismatch'),
 ('normal_diet',{'question':'참새목 중 열매를 먹는 새는?'},None),
 ('empty_numeric',{'question':'참새목 중 몸무게가 1000000g을 넘는 새는?'},None),
 ('missing_reference_data',{'question':'까치랑 AVONET 먹이 생태 범주가 일치하는 다른 조류를 찾아줘요.'},None),
 ('unsupported_activity',{'question':'습지에 사는 새를 모아 줘. 단 밤에만 활동하는 종으로.'},None),
 ('known_false_hold',{'question':'참새목 안에서 골라 줘. 숲이 서식지로 기록돼 있고 과일도 먹는 새를 찾고 있어.'},None),
 ('shared_reference',{'question':'직박구리 말고 먹이 생태 범주가 직박구리와 같은 다른 종을 알려줘.'},None),
 ('numeric_restatement',{'question':'까치속에서 몸무게가 180g을 넘는 새를 찾아줘. 180g인 기록은 제외해.'},None),
]
resume='--resume' in sys.argv
rows=json.loads((out/'live-traces.json').read_text())['rows'] if resume else []
for label,body,want in cases:
 if any(r['case']==label for r in rows):continue
 body={**body,'defer_enrichment':True,'defer_discovery':True};start=int(time.time()*1000)-1000
 if resume:
  pending=json.loads((out/'live-pending.json').read_text());assert pending['case']==label
  response=pending['response'];http=pending['http_status'];start=pending['search_start_ms']
 else:
  with urlopen(Request('http://127.0.0.1:8000/v1/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=90) as r:
   response=json.load(r);http=r.status
 (out/'live-pending.json').write_text(json.dumps({'case':label,'search_start_ms':start,'http_status':http,'response':response},ensure_ascii=False)+'\n')
 found=None
 for attempt in range(45):
  traces=c.search_traces(locations=['33'],filter_string=f'timestamp_ms >= {start}',max_results=50,include_spans=True)
  found=next((t for t in traces if any(s.name=='POST /v1/chat' and body['question'] in json.dumps(s.inputs,ensure_ascii=False) for s in t.data.spans)),None)
  if found and found.info.tags.get('response_api_disposition')==response['disposition'] and all(k in found.info.tags for k in ('response_reason','failure_stage')):break
  found=None
  time.sleep(2)
 assert found is not None,label+' missing trace'
 tags={k:found.info.tags.get(k) for k in ('response_disposition','response_reason','failure_stage','response_api_disposition','route_method','selected_intent')}
 reason=tags['response_reason'];stage=tags['failure_stage']
 # The actual returned disposition, not SDK trace state OK, decides whether this was answered.
 assert tags['response_api_disposition']==response['disposition'],label
 if response['disposition']!='answer':assert reason not in (None,'none','unknown') and stage not in (None,'none','unknown'),(label,tags)
 else:assert (reason,stage)==('none','none'),(label,tags)
 if want:assert reason==want,(label,tags)
 filtered=c.search_traces(locations=['33'],filter_string=f"timestamp_ms >= {start} AND tags.response_reason = '{reason}' AND tags.failure_stage = '{stage}'",max_results=50,include_spans=False)
 assert found.info.trace_id in [t.info.trace_id for t in filtered],label+' tag search failed'
 children=[{'name':p.name,'span_id':p.span_id,'parent_id':p.parent_id,'inputs':p.inputs,'outputs':p.outputs,'attributes':{k:v for k,v in p.attributes.items() if k.startswith('graph_intent.') or k in ('reason','stage','rejection_detail','selected_interpreter','judgment_source')}} for p in found.data.spans if p.name.startswith('graph_intent.')]
 row={'case':label,'question':body['question'],'http_status':http,'api_disposition':response['disposition'],'result_kind':response.get('result',{}).get('kind'),'result_status':response.get('result',{}).get('payload',{}).get('status'),'trace_id':found.info.trace_id,'trace_state':str(found.info.state),'tags':tags,'found_by_tag_filter':True,'diagnostic_spans':children,'passed':True}
 rows.append(row)
 (out/'live-traces.json').write_text(json.dumps({'image':s['Config']['Image'],'response_mocking':False,'bird_db_writes':0,'rows':rows},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k not in ('question','diagnostic_spans')},ensure_ascii=False),flush=True)
print(json.dumps({'passed':len(rows),'total':len(cases)}),flush=True)
