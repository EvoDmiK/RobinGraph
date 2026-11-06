import ast,concurrent.futures,io,json,tempfile,time
from pathlib import Path
from threading import Lock
from urllib.request import Request
source=ast.parse(Path('scripts/evaluate_graph_question_dataset.py').read_text());main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main');fn=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='predict');fn.decorator_list=[]
active=maximum=calls=0;guard=Lock()
def fake_open(*a,**k):
 global active,maximum,calls
 with guard:active+=1;maximum=max(maximum,active);calls+=1
 time.sleep(.003)
 with guard:active-=1
 return io.StringIO(json.dumps({'result':{'payload':{}},'disposition':'answer'}))
with tempfile.TemporaryDirectory() as temp:
 q=[f'fixture-{i}' for i in range(16)];previous={'response_status':None,'disposition':'answer','coverage':None}
 ns=dict(cache={},cases={s:{} for s in q},baseline={s:previous for s in q},rows=[],request_lock=Lock(),time=time,json=json,Request=Request,urlopen=fake_open,BASE='https://fixture.invalid',out=Path(temp),contract=lambda *a:[],fingerprint=lambda r:previous,HTTPError=Exception)
 exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual predict function>','exec'),ns)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(ns['predict'],q))
 ns['predict'](q[0])
 assert maximum==1 and calls==16 and len(ns['rows'])==16
 print(json.dumps({'mock_tasks':16,'worker_threads':4,'max_concurrent_api_calls':maximum,'cache_hit_sent_no_request':True,'actual_test_api_calls':0,'passed':True}))
