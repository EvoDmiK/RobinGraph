import json,hashlib
from collections import Counter,defaultdict
from pathlib import Path
p=Path(__file__).resolve().parent
r=json.loads((p/'independent-api-broad-final.json').read_text());byrank=defaultdict(Counter);bytrait=defaultdict(Counter)
for row in r['rows']:
 c=row['case'];status=(row.get('response') or {}).get('result',{}).get('payload',{}).get('status','no_status')
 byrank[c['rank']][status]+=1
 for condition in c['conditions']:bytrait[condition['trait_name']][c['rank']]+=1
out=dict(count=r['count'],passed=r['passed'],failures=r['failures'],rank_status=dict(byrank),trait_rank=dict(bytrait),unique_taxa=len({x['case']['taxon'] for x in r['rows']}),composite_cases=sum(len(x['case']['conditions'])>1 for x in r['rows']),corvidae_cases=sum(x['case']['taxon']=='Corvidae' for x in r['rows']),case_sha256=hashlib.sha256((p/'independent-cases.json').read_bytes()).hexdigest(),limitations=['Fixed reviewed phrases crossed with real taxonomy; not unseen natural language accuracy','All orders/families queried once, sampled genera/species/subspecies; not every taxon by every trait','Read-only bird DB queries; app telemetry may persist','TEST lifestyle phrasing fix deployed; no Production changes'])
(p/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
