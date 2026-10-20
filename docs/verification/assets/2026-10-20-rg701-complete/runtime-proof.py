from pathlib import Path
import subprocess,json
assets=Path('docs/verification/assets/2026-10-20-rg701-complete')
def docker(*args,input=None):return subprocess.check_output(['docker','--context','orbstack',*args],input=input,text=True)
rows=[]
for name,module,factory in [('robingraph-api-test','robingraph.api.drf','create_django_app'),('robingraph-avilist-runner-test','scripts.serve_avilist_pipeline','create_app')]:
 d=json.loads(docker('inspect',name))[0]
 assert 'ROBINGRAPH_DEPLOY_TARGET=test' in d['Config']['Env']
 source=f'''import importlib,importlib.util,json
from django.core.handlers.asgi import ASGIHandler
app=getattr(importlib.import_module({module!r}),{factory!r})()
absent={{name:importlib.util.find_spec(name) is None for name in ('fastapi','starlette')}}
assert all(absent.values()) and isinstance(app,ASGIHandler)
print(json.dumps({{'asgi_class':type(app).__module__+'.'+type(app).__qualname__,'native_django_asgi':True,'packages_absent':absent}}))
'''
 proof=json.loads(docker('exec','-i',name,'python','-',input=source))
 rows.append({'container':name,'image_id':d['Image'],'healthy':d['State']['Health']['Status']=='healthy',**proof})
assert rows[0]['image_id']==rows[1]['image_id'] and all(row['healthy'] for row in rows)
(assets/'runtime-proof.json').write_text(json.dumps({'target':'test','containers':rows},indent=2)+'\n')
print('Both TEST runtimes use native Django ASGI; FastAPI and Starlette absent.')
