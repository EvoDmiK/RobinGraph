import sys,json,hashlib,statistics,subprocess
from collections import Counter
from pathlib import Path
from dotenv import dotenv_values
import os
for k,v in dotenv_values(sys.argv[2]).items():
 if k.startswith('MLFLOW_') and v is not None:os.environ[k]=v
os.environ['MLFLOW_HTTP_REQUEST_TIMEOUT']='30';os.environ['MLFLOW_HTTP_REQUEST_MAX_RETRIES']='0'
import mlflow
from mlflow import MlflowClient
from mlflow.genai.datasets import get_dataset
p=Path(sys.argv[1]);summary=json.loads((p/'summary.json').read_text());rows=[json.loads(line) for line in (p/'results.jsonl').read_text().splitlines()]
table=json.loads((p/'mlflow-eval-results.json').read_text());assert len(table)==496
assert all(r.get('regression_contract/value') is True and r.get('baseline_consistent/value') is True for r in table), 'Missing or failed native MLflow scores'
evidence=json.loads((p/'db-evidence.json').read_text());safety=json.loads((p/'safety-audit.json').read_text())
assert len(rows)==496 and evidence['passed'] and safety['passed'] and safety['selfcheck']['passed']
# Never edit the published question set or its expectations to accommodate a result.
local=[json.loads(x) for x in Path('data/eval/graph_questions/taxonomic-regression-v1/questions.jsonl').read_text().splitlines()]
native=get_dataset(dataset_id=summary['dataset_id']).to_df().to_dict('records')
assert {x['inputs']['question']:x['expectations'] for x in native}=={x['inputs']['question']:x['expectations'] for x in local}
latencies=sorted(r['elapsed_ms'] for r in rows[1:]);p95=latencies[int(.95*(len(latencies)-1))]
routes=dict(Counter((r['response'] or {}).get('route_method','request_error') for r in rows))
extra=dict(db_evidence=evidence,safety_audit=safety,route_counts=routes,
 first_request_latency_ms=rows[0]['elapsed_ms'],subsequent_request_p50_ms=statistics.median(latencies),
 subsequent_request_p95_ms=p95,native_dataset_unchanged_verified=True,
 notes=['First request is not asserted to be cold; app was already running.',
        'All raw responses retain selected_intent/route_method/kind; semantic span scores were not independently audited.',
        'Only default species_scope=all; ordering and other species_scope modes are not re-evaluated.'])
(p/'extended-summary.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2)+'\n')
db_cases={r['case_id']:r for r in json.loads((p/'case-db-evidence.json').read_text())}
safe_cases={r['id']:r for r in safety['cases']}
assert set(db_cases)|set(safe_cases)=={r['case']['tags']['case_id'] for r in rows}
verified=[]
for row in rows:
 case_id=row['case']['tags']['case_id']
 passed=not row['errors'] and not db_cases.get(case_id,{}).get('errors',[]) and safe_cases.get(case_id,{'passed':True})['passed']
 verified.append(dict(case_id=case_id,suite=row['case']['tags']['suite'],question=row['case']['inputs']['question'],
                      contract_passed=not row['errors'],db_audited=case_id in db_cases,safety_audited=case_id in safe_cases,passed=passed))
(p/'verified-results.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
c=MlflowClient();run_id=summary['run_id'];assert c.get_run(run_id).info.status=='FINISHED'
c.log_metric(run_id,'verified_regression_pass_rate',sum(r['passed'] for r in verified)/len(verified))
for name,value in {'db_evidence_queries':evidence['checked_exact_scope_and_match_counts'],
 'db_evidence_condition_supports':evidence['checked_condition_supports'],
 'db_evidence_error_count':len(evidence['errors']),
 'safety_reason_audited':safety['audited'],'safety_reason_failures':len(safety['failed']),
 'safety_mutations_caught':safety['selfcheck']['caught'],
 'api_subsequent_p95_ms':p95}.items():c.log_metric(run_id,name,float(value))
for name in ('db-evidence.json','case-db-evidence.json','safety-audit.json','extended-summary.json','verify-db-evidence.py','verified-results.json'):
 c.log_artifact(run_id,str(p/name),'regression')
 downloaded=Path(c.download_artifacts(run_id,'regression/'+name))
 assert hashlib.sha256(downloaded.read_bytes()).digest()==hashlib.sha256((p/name).read_bytes()).digest()
print(json.dumps(extra,ensure_ascii=False))
