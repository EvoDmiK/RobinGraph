"""Exhaustive catalog surface substitution audit, NOT natural-language accuracy."""
import argparse,json,time
from pathlib import Path
from collections import Counter
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate
parser=argparse.ArgumentParser();parser.add_argument('--condition',choices=('fruit','habitat'),default='habitat');args=parser.parse_args();p=Path(__file__).resolve().parent
d=json.loads((p/'inventory.json').read_text());counts=Counter();failures=[];n=0;t=time.perf_counter()
for taxon in d['taxa']:
 for language,name in [('scientific',taxon['scientific_name']),('korean',taxon.get('korean_name'))]:
  if not name:continue
  question=f'{name} 중 '+('열매를 먹는 새는?' if args.condition=='fruit' else '숲에 사는 새는?');intent=extract_graph_intent(question);gate=execution_gate(question,intent)
  ok=intent.rank is not None and intent.rank.text==name and gate=='answer' and ((intent.kind=='taxon_traits' and bool(intent.conditions)) or (args.condition=='fruit' and intent.kind=='order_fruit' and intent.diet=='fruit_share'))
  counts[taxon['rank']+':'+language]+=1;n+=1
  if not ok:failures.append({'id':taxon['id'],'rank':taxon['rank'],'question':question,'actual_kind':intent.kind,'gate':gate,'actual_taxon':intent.rank.text if intent.rank else None})
report={'purpose':'All catalog names substituted into one fixed supported '+args.condition+' template; no embeddings, no DB execution, not independent natural-language accuracy','count':n,'counts':dict(counts),'failures':failures,'elapsed_seconds':round(time.perf_counter()-t,3)}
(p/('catalog-'+args.condition+'-parse-audit.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'count':n,'failures':len(failures),'elapsed_seconds':report['elapsed_seconds']}));assert not failures,failures[:5]
