import subprocess,json,base64
from pathlib import Path
before=json.loads(Path('preflight.json').read_text());state=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0]
assert state['Id']==before['container_id'] and state['State']['StartedAt']==before['started_at'] and state['Config']['Image']==before['image']
script=Path('readback_inside.py').read_text().replace("spec=json.loads(Path('/tmp/rg213-rg603-browser-results.json').read_text())",'spec=SPEC');browser=Path('browser-results.json').read_bytes()
# Passing the verification input over stdin avoids auth values in command arguments or artifacts.
code="import base64,json;SPEC=json.loads(base64.b64decode('"+base64.b64encode(browser).decode()+"'))\n"+script
result=subprocess.check_output(['docker','exec','-i','robingraph-api','python','-'],input=code.encode())
record=json.loads(result);assert record['passed'];Path('trace-readback.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
end=json.loads(subprocess.check_output(['docker','inspect','robingraph-api']))[0];assert end['Id']==before['container_id'] and end['State']['StartedAt']==before['started_at'] and end['Config']['Image']==before['image']
Path('runtime-after.json').write_text(json.dumps({'container_id':end['Id'],'image':end['Config']['Image'],'started_at':end['State']['StartedAt'],'health':end['State']['Health']['Status'],'unchanged':True,'domain_db_write_commands':0,'mlflow_test_assessments':record['assessment_count']},indent=2)+'\n')
print(json.dumps({'passed':True,'trace_count':record['trace_count'],'assessment_count':record['assessment_count'],'experiment_id':'50','app_unchanged':True}))
