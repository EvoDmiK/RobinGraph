"""Early immutable module-load smoke; no server replacement and no DB."""
import hashlib,importlib.util,json,sys
from pathlib import Path
source=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-claude/src/robingraph/retrieval')
modules=('graph_questions','graph_intent_schema','graph_condition_extractor','graph_semantic_router')
before={n:hashlib.sha256((source/(n+'.py')).read_bytes()).hexdigest() for n in modules}
for n in modules:
 name='robingraph.retrieval.'+n;spec=importlib.util.spec_from_file_location(name,source/(n+'.py'));mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_intent_schema import execution_gate
rows=[]
for q in ['까마귀과면서 열매를 먹는 새는 어떤 종이 있어?','Corvus 중 숲에 사는 새는?','Corvus corone corone 중 숲에 사는 새는?','까마귀과 중 숲에 살고 열매를 먹는 새는?']:
 i=extract_graph_intent(q);rows.append({'question':q,'kind':i.kind,'gate':execution_gate(q,i),'taxon':i.rank.text if i.rank else None,'conditions':repr(i.conditions),'residual':[s.text for s in i.residual]})
after={n:hashlib.sha256((source/(n+'.py')).read_bytes()).hexdigest() for n in modules}
assert before==after,'Source changed during smoke'
print(json.dumps({'scope':'early parser-only smoke against in-progress implementation; not final acceptance','file_sha256':before,'rows':rows},ensure_ascii=False,indent=2))
