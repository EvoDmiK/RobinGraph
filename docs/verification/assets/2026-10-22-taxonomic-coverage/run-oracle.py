import subprocess,json,argparse
from pathlib import Path
args=argparse.ArgumentParser();args.add_argument('phase');args.add_argument('--natural',action='store_true');args=args.parse_args()
p=Path(__file__).resolve().parent
if args.natural:p=p/'natural'
files={n:(p/n).read_text() for n in ('inventory.json','independent-api-'+args.phase+'.json','verify-db-evidence.py')}
bootstrap="import json,sys;from pathlib import Path;p=Path('/tmp/broad-qa');p.mkdir(exist_ok=True);[(p/n).write_text(v) for n,v in json.load(sys.stdin).items()]"
subprocess.run(['docker','exec','-i','robingraph-api-test','python','-c',bootstrap],input=json.dumps(files),text=True,check=True)
r=subprocess.run(['docker','exec','robingraph-api-test','python','/tmp/broad-qa/verify-db-evidence.py','/tmp/broad-qa',args.phase],capture_output=True,text=True)
(p/(args.phase+'-db-evidence.json')).write_text(r.stdout);(p/(args.phase+'-db-evidence.stderr')).write_text(r.stderr)
print(r.stdout);print(r.stderr[-1000:]);raise SystemExit(r.returncode)
