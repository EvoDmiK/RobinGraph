import json,sys,datetime
from pathlib import Path
a,b=[json.loads(Path(p).read_text(encoding='utf-8')) for p in sys.argv[1:3]]
normalize=lambda cs:[{**c,'type':c['type'].replace('NODE_PROPERTY_UNIQUENESS','UNIQUENESS')} for c in cs]
checks={}
for k in ['schemas','tables','hashes','running_ingestions']:
 checks['pg_'+k]=a['postgres'][k]==b['postgres'][k]
for k in ['nodes','relationships','labels','types','indexes','node_content','relationship_content']:
 checks['neo4j_'+k]=a['neo4j'][k]==b['neo4j'][k]
checks['neo4j_constraints']=normalize(a['neo4j']['constraints'])==normalize(b['neo4j']['constraints'])
checks['quiescent_ingestion']=a['postgres']['running_ingestions']==b['postgres']['running_ingestions']==0
checks['indexes_online']=all(i['state']=='ONLINE' for s in [a,b] for i in s['neo4j']['indexes'])
print(json.dumps({'equal':all(checks.values()),'checks':checks,'compared_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
if not all(checks.values()):sys.exit(2)
