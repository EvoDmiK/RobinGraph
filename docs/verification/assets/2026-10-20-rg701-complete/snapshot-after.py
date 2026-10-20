from pathlib import Path
import json,subprocess
assets=Path('docs/verification/assets/2026-10-20-rg701-complete')
r=subprocess.run(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-'],input=Path('/tmp/rg-avilist-pipeline/snapshot.py').read_text(),text=True,capture_output=True,check=True)
after=json.loads(r.stdout);before=json.loads((assets/'db-before.json').read_text())
(assets/'db-after.json').write_text(json.dumps(after,indent=2)+'\n')
assert before==after, 'TEST data state changed'
(assets/'db-comparison.json').write_text(json.dumps({'target':'test','read_only_snapshots':True,'unchanged':True,'before':'db-before.json','after':'db-after.json'},indent=2)+'\n')
print('Actual TEST DB snapshots unchanged.')
