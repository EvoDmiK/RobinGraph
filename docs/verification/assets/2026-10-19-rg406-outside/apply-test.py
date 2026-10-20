from pathlib import Path
import json,subprocess
backup=json.loads(Path('/Users/kimdove/robingraph-test/backups/2026-10-19-outside-before.json').read_text())
payload=json.loads(Path('/Users/kimdove/robingraph-test/backups/2026-10-19-outside-prepared.json').read_text())
source=Path('/tmp/rg406-outside-index-cached.py').read_text()
def apply(data,expected):
 code='payload='+repr(data)+'\nexpected_fingerprint='+repr(expected)+'\n'+source
 return subprocess.check_output(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-'],input=code,text=True)
report=apply(payload,backup['catalogs'][0]['properties']['fingerprint'])
Path('docs/verification/assets/2026-10-19-rg406-outside/index-apply.json').write_text(report)
try:
 subprocess.run(['python3','/tmp/rg406-outside-deploy.py'],check=True)
except Exception:
 props=[row['properties'] for row in backup['nodes']]
 old={'inventory':[{k:n[k] for k in ['taxon_id','scientific_name','display_name','text']} for n in props],
      'profile':payload['profile'],'context':payload['context'],'vectors':{n['text']:n['name_vector'] for n in props}}
 # New catalog fingerprint is deterministic for the prepared inventory.
 from hashlib import sha256
 # Read the installed new fingerprint without exporting vectors or credentials.
 query="import json,os;from neo4j import GraphDatabase;d=GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD']));s=d.session(database=os.environ.get('NEO4J_DATABASE','neo4j'));print(s.run('MATCH(c:TaxonNameVectorCatalog) RETURN c.fingerprint AS fingerprint').single()['fingerprint']);s.close();d.close()"
 fingerprint=subprocess.check_output(['docker','--context','orbstack','exec','-i','robingraph-api-test','python','-'],input=query,text=True).strip()
 apply(old,fingerprint)
 raise
print('TEST catalog and app updated')
