"""Run frozen independent questions with the actual configured embedding and generation providers."""
import json,os,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict,replace
from pathlib import Path
from robingraph.embeddings import JinaEmbeddingClient
from robingraph.generation import GeminiAnswerer
from robingraph.retrieval.graph_semantic_router import GraphSemanticRouter,PROTOTYPES
from robingraph.retrieval.semantic_graph_intent import SEMANTIC_PROTOTYPES,graph_intent_handler
from robingraph.retrieval.graph_intent_schema import execution_gate,to_graph_question
from robingraph.retrieval.species_questions import parse_species_question
p=Path(__file__).resolve().parent
cases=json.loads((p/'independent-cases.json').read_text())['cases']
client=JinaEmbeddingClient.from_env();router=GraphSemanticRouter(client,prototypes=PROTOTYPES+SEMANTIC_PROTOTYPES)
assert router.warm(),'embedding examples unavailable'
model=os.getenv('ROBINGRAPH_GEMINI_MODEL','gemini-3.8-flash');provider=GeminiAnswerer(os.environ['GEMINI_API_KEY'],model,timeout_seconds=20)
def run(case):
 start=time.perf_counter();calls=[];retrieved=[];raw=[];responses=[]
 provider=GeminiAnswerer(os.environ["GEMINI_API_KEY"],model,timeout_seconds=20)
 original_request=provider._request
 def request(prompt,*,schema=None,operation=None):
  document=original_request(prompt,schema=schema,operation=operation);responses.append({"operation":operation,"document":document});return document
 provider._request=request
 def propose(q,examples,contract):
  calls.append(q);out=provider.propose_structured_graph_intent(q,examples,contract);raw.append(out);return out
 def retrieve(q,limit=5):
  found=router.retrieve(q,limit);retrieved.extend(found);return found
 try:
  intent=graph_intent_handler(case['question'],provider=propose,retrieve=retrieve)
  parsed=to_graph_question(case['question'],intent)
  result={'intent':asdict(intent),'gate':execution_gate(case['question'],intent),'parsed':asdict(parsed) if parsed else None}
 except Exception as error:result={'error_type':type(error).__name__,'error':str(error)[:200], 'cause':str(error.__cause__)[:200] if error.__cause__ else None}
 return {'case':case,'result':result,'provider_calls':len(calls),'retrieved_examples':retrieved,'raw_plans':raw,'provider_responses':responses,'elapsed_ms':round((time.perf_counter()-start)*1000,2)}
rows=[]
with (p/'plans.jsonl').open('w') as f,ThreadPoolExecutor(max_workers=2) as executor:
 futures=[executor.submit(run,c) for c in cases]
 for future in as_completed(futures):
  row=future.result();rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
rows.sort(key=lambda r:r['case']['id'])
(p/'plans.json').write_text(json.dumps({'model':model,'response_mocking':False,'bird_db_writes':0,'count':len(rows),'rows':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(rows),'provider_calls':sum(r['provider_calls'] for r in rows),'errors':[r['case']['id'] for r in rows if 'error_type' in r['result']]},ensure_ascii=False))
