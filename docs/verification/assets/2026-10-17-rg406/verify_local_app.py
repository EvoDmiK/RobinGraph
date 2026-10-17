"""Local TEST DB/ASGI smoke test. Reads candidate archive on stdin inside TEST.

No daemon restart, schema change, or data writes; source files live in temporary
storage only. Jev/Jina and enabled optional enrichment may make paid requests.
"""
import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix='rg406-qa-') as directory:
    root=Path(directory)
    with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
        assert all(not m.name.startswith('/') and '..' not in Path(m.name).parts for m in archive.getmembers())
        archive.extractall(root)
    # Package import also initializes the unchanged fixture-mode app.
    (root/'data').symlink_to('/app/data', target_is_directory=True)
    sys.path.insert(0,str(root/'src'))
    import uvicorn
    from fastapi.testclient import TestClient
    from robingraph.cli import serve_neo4j
    from robingraph.retrieval.species_scope import distribution_for
    def check(app, **kwargs):
        rows=[]
        with TestClient(app) as client:
            for science,scope,status,expected in [
                ('Anas platyrhynchos','korea','answer','korea'),
                ('Anas platyrhynchos','outside','abstain',None),
                ('Nestor notabilis','outside','answer','outside'),
                ('Nestor notabilis','korea','abstain',None),
                ('Struthio camelus','unknown','answer','unknown'),
                ('Struthio camelus','outside','abstain',None),
                ('Saxicola maurus','korea','answer','korea'),
            ]:
                response=client.post('/v1/chat',json=dict(question=science+'에 대해 알려줘',
                    species_scope=scope,defer_enrichment=True,defer_discovery=True))
                body=response.json();taxon=(body.get('result',{}).get('profile') or {}).get('taxon',{})
                passed=response.status_code==200 and body.get('disposition')==status
                if expected:
                    passed=passed and taxon.get('distribution',{}).get('status')==expected and taxon.get('scientific_name')==science
                if science=='Nestor notabilis' and expected:
                    passed=passed and taxon.get('display_name')=='Kea'
                rows.append(dict(request='chat',science=science,species_scope=scope,passed=passed,
                    http_status=response.status_code,disposition=body.get('disposition'),taxon=taxon))
            for endpoint in ['related','similar','ecological-related']:
                response=client.get('/v1/taxa/'+endpoint,params={'name':'Anas platyrhynchos','species_scope':'korea'})
                body=response.json();items=[item for group in body.get('groups',[]) for item in group.get('items',[])]
                passed=response.status_code==200 and all(item.get('distribution',{}).get('status')=='korea' for item in items)
                rows.append(dict(request=endpoint,species_scope='korea',http_status=response.status_code,
                    passed=passed,item_count=len(items),items=items))
            # A known Korean name of a foreign species must display English.
            response=client.get('/v1/taxa/profile',params={'name':'Nestor notabilis','species_scope':'outside'})
            taxon=response.json().get('taxon',{})
            rows.append(dict(request='profile',species_scope='outside',passed=response.status_code==200 and taxon.get('display_name')=='Kea',taxon=taxon))
        print(json.dumps(dict(passed=all(row['passed'] for row in rows),scope='Real local TEST DB; in-process ASGI; temporary candidate source',rows=rows),ensure_ascii=False),flush=True)
    uvicorn.run=check
    serve_neo4j(argparse.Namespace(host='127.0.0.1',port=8002))
