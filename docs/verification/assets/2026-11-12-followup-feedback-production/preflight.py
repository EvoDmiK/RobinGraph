import json,subprocess
from pathlib import Path
state=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0]
env=dict(x.split('=',1) for x in state['Config']['Env'])
assert env['ROBINGRAPH_DEPLOY_TARGET']=='prod' and env['MLFLOW_EXPERIMENT_ID']=='50' and env['MLFLOW_EXPERIMENT_NAME']=='robingraph-prod'
assert state['Config']['Image']=='ghcr.io/evodmik/robingraph@sha256:997ce4f410605011a17924b8ea1784849282f8931c22a27c4a11aa706c16e65f'
code="""import json,urllib.request
import os,requests
from pathlib import Path
headers={};auth=None
if os.getenv('MLFLOW_TRACKING_TOKEN'):headers['Authorization']='Bearer '+os.environ['MLFLOW_TRACKING_TOKEN']
elif os.getenv('MLFLOW_TRACKING_USERNAME'):auth=(os.environ['MLFLOW_TRACKING_USERNAME'],os.environ.get('MLFLOW_TRACKING_PASSWORD',''))
response=requests.get(os.environ['MLFLOW_TRACKING_URI'].rstrip('/')+'/api/2.0/mlflow/experiments/get',params={'experiment_id':'50'},headers=headers,auth=auth,timeout=20)
assert response.status_code==200,'MLflow experiment GET failed'
exp=response.json()['experiment'];assert exp['name']=='robingraph-prod'
h=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'));assert h['deployment_target']=='prod' and h['status']=='ok'
s=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json'));assert '/v1/chat/feedback' in s['paths']
print(json.dumps({'experiment_id':'50','experiment_name':exp['name'],'health':'ok','feedback_route':True}))
"""
checks=json.loads(subprocess.check_output(['docker','exec','robingraph-api','python','-c',code]))
record={'container_id':state['Id'],'image':state['Config']['Image'],'started_at':state['State']['StartedAt'],'health':state['State']['Health']['Status'],'target':'prod','checks':checks,'app_mutations':0,'domain_db_write_commands':0}
Path('preflight.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
