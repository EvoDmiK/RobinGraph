import json,subprocess,sys
from pathlib import Path
p=Path(sys.argv[1]);source=Path('docs/verification/assets/2026-10-22-taxonomic-trait-generalization')
rows=[json.loads(line) for line in (p/'results.jsonl').read_text().splitlines()]
assert len(rows)==496
report={'rows':[{'case':dict(id=r['case']['tags']['case_id'],question=r['case']['inputs']['question'],**r['case']['expectations']), 'response':r['response']} for r in rows]}
(p/'independent-api-live.json').write_text(json.dumps(report,ensure_ascii=False))
code=(source/'verify-db-evidence.py').read_text()
code=code.replace("if case['outcome'] not in ('query','empty') or not response:continue", "if not response or not (case['outcome'] in ('query','empty') or (case['outcome']=='insufficient' and case['rank']=='subspecies')):continue")
code=code.replace("print(json.dumps({'scope':", "case_results=[{'case_id':r['case']['id'],'errors':[e for e in errors if e[0]==r['case']['id']]} for r in report['rows'] if r['case']['outcome'] in ('query','empty') or (r['case']['outcome']=='insufficient' and r['case']['rank']=='subspecies')]\n(p/'case-db-evidence.json').write_text(json.dumps(case_results,ensure_ascii=False,indent=2))\nprint(json.dumps({'scope':")
code=code.replace("'bird_db_writes':0", "'bird_db_writes':0,'active_trait_sources':sources,'taxonomy_release':inventory['taxonomy_release'],'concept_set_id':inventory['concept_set_id']")
assert 'case_results=' in code and 'active_trait_sources' in code
(p/'verify-db-evidence.py').write_text(code)
files={'inventory.py':(source/'inventory.py').read_text(),'verify-db-evidence.py':code,'independent-api-live.json':json.dumps(report,ensure_ascii=False)}
bootstrap="import json,sys;from pathlib import Path;p=Path('/tmp/dataset-evidence');p.mkdir(exist_ok=True);[(p/n).write_text(v) for n,v in json.load(sys.stdin).items()]"
subprocess.run(['docker','exec','-i','robingraph-api-test','python','-c',bootstrap],input=json.dumps(files),text=True,check=True)
r=subprocess.run(['docker','exec','robingraph-api-test','python','/tmp/dataset-evidence/inventory.py'],capture_output=True,text=True,check=True)
(p/'inventory.json').write_text(r.stdout)
subprocess.run(['docker','exec','-i','robingraph-api-test','python','-c',"import sys;open('/tmp/dataset-evidence/inventory.json','w').write(sys.stdin.read())"],input=r.stdout,text=True,check=True)
r=subprocess.run(['docker','exec','robingraph-api-test','python','/tmp/dataset-evidence/verify-db-evidence.py','/tmp/dataset-evidence','live'],capture_output=True,text=True)
(p/'db-evidence.json').write_text(r.stdout);(p/'db-evidence.stderr').write_text(r.stderr)
s=subprocess.check_output(['docker','exec','robingraph-api-test','cat','/tmp/dataset-evidence/case-db-evidence.json'],text=True);(p/'case-db-evidence.json').write_text(s)
print(r.stdout);print(r.stderr[-800:]);raise SystemExit(r.returncode)
