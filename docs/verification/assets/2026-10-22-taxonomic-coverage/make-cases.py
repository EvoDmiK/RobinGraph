import json,collections
from pathlib import Path
p=Path('docs/verification/assets/2026-10-22-taxonomic-coverage')
inv=json.loads((p/'inventory.json').read_text());taxa={t['id']:t for t in inv['taxa']};parent={e['child']:e['parent'] for e in inv['parent_edges']}
old=json.loads(Path('docs/verification/assets/2026-10-22-taxonomic-trait-generalization/independent-cases.json').read_text())['cases']
# Reuse reviewed literal conditions; vary taxonomy independently, never API output.
patterns=[]
seen=set()
for c in old:
 if c['taxon']=='Corvidae' and ' 중 ' in c['question'] and len(c['conditions'])==1 and c['outcome']=='query':
  field=c['conditions'][0]['trait_name']
  if field not in seen:patterns.append(c);seen.add(field)
assert len({c['conditions'][0]['trait_name'] for c in patterns})==15
orders=sorted([t for t in taxa.values() if t['rank']=='order'],key=lambda t:t['scientific_name'])
selected=orders+sorted([t for t in taxa.values() if t['rank']=='family'],key=lambda t:t['scientific_name'])
def order_of(t):
 while t['rank']!='order' and t['id'] in parent:t=taxa[parent[t['id']]]
 return t['id']
for rank in ('genus','species','subspecies'):
 for order in orders:
  candidates=sorted([t for t in taxa.values() if t['rank']==rank and order_of(t)==order['id']],key=lambda t:t['scientific_name'])
  if candidates:selected.append(candidates[len(candidates)//2])
cases=[]
for i,t in enumerate(selected):
 pattern=patterns[i%len(patterns)];suffix=pattern['question'].split(' 중 ',1)[1]
 conditions=list(pattern['conditions'])
 question=t['scientific_name']+' 중 '+suffix
 if i%5==0:
  second=patterns[(i+3)%len(patterns)]
  if second['conditions'][0]['trait_name']!=conditions[0]['trait_name']:
   question=t['scientific_name']+' 중 '+suffix.removesuffix(' 새는?')+' 그리고 '+second['question'].split(' 중 ',1)[1]
   conditions+=second['conditions']
 cases.append(dict(id=f'BROAD-{i+1:04}',question=question,taxon=t['scientific_name'],rank=t['rank'],conditions=conditions,outcome='query'))
(p/'independent-cases.json').write_text(json.dumps(dict(author='Codex stratified real-catalog API matrix; fixed reviewed phrases, not unseen natural language',cases=cases),ensure_ascii=False,indent=2))
print(len(cases),collections.Counter(c['rank'] for c in cases));print(collections.Counter(x['trait_name'] for c in cases for x in c['conditions']))
