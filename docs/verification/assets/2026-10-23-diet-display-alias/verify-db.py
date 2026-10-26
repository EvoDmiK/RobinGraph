"""Independent read-only diet group oracle; source values remain unchanged."""
import json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent
source=Path('docs/verification/assets/2026-10-22-taxonomic-trait-generalization')
report=json.loads((p/'after.json').read_text());rows=[]
foodkeys={'곤충':'invertebrate','무척추동물':'invertebrate','고기':'meat','척추동물':'meat','물고기':'fish','사체':'carrion','열매':'fruit','씨앗':'seed'}
for i,row in enumerate(report['rows']):
 q=row['question'];r=row['response'];payload=r['result'].get('payload',{})
 if not payload.get('conditions'):continue
 key=next((v for k,v in sorted(foodkeys.items(),key=lambda pair:len(pair[0]),reverse=True) if k in q),None)
 if key is None:continue
 taxon=payload.get('taxon')
 conditions=[dict(trait_name='diet_distribution',op='share_gt',value={key:0})]
 if '숲' in q:conditions.append(dict(trait_name='habitat',op='eq',value='Forest'))
 rows.append({'case':{'id':str(i),'taxon':taxon['scientific_name'] if taxon else None,'rank':taxon['rank'] if taxon else None,'conditions':conditions,'outcome':'query'},'response':r})
code=(source/'verify-db-evidence.py').read_text()
old="""  key,threshold=next(iter(value.items()));raw=claim.get('value_json')
  try:amount=json.loads(raw).get(key)
  except (ValueError,TypeError,AttributeError):return False
"""
new="""  key,threshold=next(iter(value.items()));raw=claim.get('value_json')
  try:
   composition=json.loads(raw)
   keys=('endotherm_vertebrate','ectotherm_vertebrate','unknown_vertebrate') if key=='meat' else (key,)
   values=[composition.get(k) for k in keys]
   values=[v for v in values if type(v) in (int,float) and math.isfinite(v) and 0<=v<=100]
   amount=sum(values) if values else None
  except (ValueError,TypeError,AttributeError):return False
"""
assert old in code
code=code.replace(old,new)
files={'inventory.py':(source/'inventory.py').read_text(),'verify-db-evidence.py':code,'independent-api-live.json':json.dumps({'rows':rows},ensure_ascii=False)}
bootstrap="import json,sys;from pathlib import Path;p=Path('/tmp/diet-alias-evidence');p.mkdir(exist_ok=True);[(p/n).write_text(v) for n,v in json.load(sys.stdin).items()]"
subprocess.run(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-c',bootstrap],input=json.dumps(files),text=True,check=True)
r=subprocess.run(['docker','--context','orbstack','exec','robingraph-api-test','python','/tmp/diet-alias-evidence/inventory.py'],capture_output=True,text=True,check=True)
(p/'inventory.json').write_text(r.stdout)
subprocess.run(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-c',"import sys;open('/tmp/diet-alias-evidence/inventory.json','w').write(sys.stdin.read())"],input=r.stdout,text=True,check=True)
r=subprocess.run(['docker','--context','orbstack','exec','robingraph-api-test','python','/tmp/diet-alias-evidence/verify-db-evidence.py','/tmp/diet-alias-evidence','live'],capture_output=True,text=True)
(p/'db-evidence.json').write_text(r.stdout);(p/'db-evidence.stderr').write_text(r.stderr)
(p/'oracle-input.json').write_text(json.dumps({'rows':rows},ensure_ascii=False,indent=2))
(p/'oracle-code.py').write_text(code)
print(r.stdout);print(r.stderr[-500:]);raise SystemExit(r.returncode)
