"""Resolve all catalog names against an exported-data fixture (not live DB calls)."""
import json,time
from pathlib import Path
from collections import defaultdict,Counter
from robingraph.retrieval.graph_questions import _taxon_candidates,TAXON_BY_NAME_QUERY,TAXON_QUERY
p=Path(__file__).resolve().parent;d=json.loads((p/'inventory.json').read_text());by=defaultdict(list);ko=defaultdict(list)
for taxon in d['taxa']:
 by[taxon['scientific_name']].append(taxon)
 if taxon.get('korean_name'):ko[taxon['korean_name']].append(taxon)
class ExportedCatalog:
 def _run(self,query,**params):
  assert query in (TAXON_BY_NAME_QUERY,TAXON_QUERY),'Unexpected query in name-resolution fixture'
  rows=by[params['scientific_name']]
  if 'rank' in params:rows=[t for t in rows if t['rank']==params['rank']]
  return [dict(taxon_id=t['id'],rank=t['rank'],scientific_name=t['scientific_name']) for t in rows]
repo=ExportedCatalog();failures=[];counts=Counter();holds=[];t=time.perf_counter()
for taxon in d['taxa']:
 found,reason=_taxon_candidates(repo,None,taxon['scientific_name'],d['concept_set_id'],d['taxonomy_release']);counts[taxon['rank']+':scientific']+=1
 if not found or found['taxon_id']!=taxon['id']:failures.append({'name':taxon['scientific_name'],'rank':taxon['rank'],'result':found})
for name,taxa in ko.items():
 found,reason=_taxon_candidates(repo,None,name,d['concept_set_id'],d['taxonomy_release']);counts['korean_unique_surfaces']+=1
 suffix={'목':'order','과':'family','속':'genus'}.get(name[-1:]);expected_conflict=suffix and any(t['rank']!=suffix for t in taxa)
 if len(taxa)>1 or expected_conflict:
  if found:failures.append({'name':name,'reason':'ambiguous_or_conflicting_label_executed','result':found})
  else:holds.append({'name':name,'reason':'rank_conflict' if expected_conflict else 'ambiguous','ranks':[t['rank'] for t in taxa]})
 elif not found or found['taxon_id']!=taxa[0]['id']:failures.append({'name':name,'reason':'catalog_label_not_resolved','result':found})
report={'scope':'Exhaustive resolver test with actual exported taxonomy as a fixture; zero live DB calls, not natural-language accuracy','counts':dict(counts),'holds':holds,'failures':failures,'elapsed_seconds':round(time.perf_counter()-t,3)}
(p/'catalog-resolution-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'counts':dict(counts),'holds':len(holds),'failures':len(failures)}));assert not failures,failures[:5]
