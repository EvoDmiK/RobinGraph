import json,subprocess,sys
from pathlib import Path
root=Path.cwd();p=Path(__file__).resolve().parent
files={str(f.relative_to(root)):f.read_text() for f in (root/'src').rglob('*') if f.is_file() and f.suffix in ('.py','.json') and '__pycache__' not in f.parts}
case_name=sys.argv[1] if len(sys.argv)>1 else 'independent-cases.json'
prefix=sys.argv[2] if len(sys.argv)>2 else 'regression'
files['evaluate-plans.py']=(p/'evaluate-plans.py').read_text();files['independent-cases.json']=(p/case_name).read_text()
bootstrap="import json,sys;from pathlib import Path;p=Path('/tmp/semantic-plan-evaluation');p.mkdir(exist_ok=True);[(p/n).parent.mkdir(parents=True,exist_ok=True) or (p/n).write_text(v) for n,v in json.load(sys.stdin).items()]"
subprocess.run(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-c',bootstrap],input=json.dumps(files),text=True,check=True)
subprocess.run(['docker','--context','orbstack','exec','--env','PYTHONPATH=/tmp/semantic-plan-evaluation/src','robingraph-api-test','python','-u','/tmp/semantic-plan-evaluation/evaluate-plans.py'],check=True)
for name in ('plans.json','plans.jsonl'):
 result=subprocess.check_output(['docker','--context','orbstack','exec','robingraph-api-test','cat','/tmp/semantic-plan-evaluation/'+name],text=True);(p/(prefix+'-'+name)).write_text(result)
