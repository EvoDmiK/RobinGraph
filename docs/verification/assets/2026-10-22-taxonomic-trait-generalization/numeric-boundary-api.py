"""Actual API safety/normalization probes; no dropped signs, operators, or units."""
import json,time
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent;base=json.loads((p/'candidate-release.json').read_text())['base'];rows=[];failures=[]
held=['-1g','−1g','+1g','.5g','1,000g','1e3g','NaNg','Infinityg','1.5.3g','100','100cm']
cases=[('까마귀과 중 체중이 '+n+' 이상인 새는?',None) for n in held]
cases += [
('까마귀과 중 체중이 100g 이상 50g 이하인 새는?',None),
('까마귀과 중 체중이 0.1kg 이상인 새는?',[('body_mass','num_gte',100,'g')]),
('까마귀과 중 체중이 100g 초과인 새는?',[('body_mass','num_gt',100,'g')]),
('까마귀과 중 체중이 100g 미만인 새는?',[('body_mass','num_lt',100,'g')]),
('까마귀과 중 접은 날개 길이가 10cm 미만인 새는?',[('wing_length','num_lt',100,'mm')]),
('까마귀과 중 체중이 100g 이상 500g 이하인 새는?',[('body_mass','num_gte',100,'g'),('body_mass','num_lte',500,'g')]),
]
for question,expected in cases:
 req=Request(base+'/v1/chat',data=json.dumps({'question':question,'defer_enrichment':True,'defer_discovery':True}).encode(),headers={'Content-Type':'application/json'});d=json.load(urlopen(req,timeout=35));error=None
 if expected is None:
  if d['disposition']!='clarify':error='malformed_measurement_executed'
 else:
  out=d['result'].get('payload',{});found=[(c['trait_name'],c['op'],c['threshold'],c['unit']) for c in out.get('conditions',[])]
  if sorted(found)!=sorted(expected) or out.get('status') not in ('answer','empty'):error='operator_or_normalized_threshold_changed'
 rows.append({'question':question,'expected_conditions':expected,'response':d,'error':error})
 if error:failures.append({'question':question,'error':error})
report={'response_mocking':False,'count':len(rows),'passed':len(rows)-len(failures),'failures':failures,'rows':rows};(p/'numeric-boundary-api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False));assert not failures
