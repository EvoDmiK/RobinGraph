"""Read back only routing attributes, never trace inputs, bodies, or credentials."""
import os,json,mlflow
os.environ['MLFLOW_HTTP_REQUEST_MAX_RETRIES']='0';os.environ['MLFLOW_HTTP_REQUEST_TIMEOUT']='20'
traces=mlflow.search_traces(experiment_ids=['33'],max_results=3,return_type='list')
rows=[{'span':s.name,'attributes':{k:v for k,v in s.attributes.items() if k.startswith('graph_intent.')}} for t in traces for s in t.data.spans if s.name in ('graph_intent.route','graph_intent.candidates')]
assert rows,'No graph intent spans persisted'
print(json.dumps({'experiment_id':'33','spans':rows}))
