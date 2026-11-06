"""Manage the explicitly selected, owned TEST or Production audio workflow.

Remote mutations require --apply. Never prints tokens or raw CLI outputs.
A waiting execution is not reported as a completed collection/publication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
from uuid import uuid4
from generate_n8n_audio_collection import CREDENTIAL_ID, WORKFLOW_ID, workflow as build_workflow

HOST='kimdove@192.168.219.98'
KEY=Path.home()/'.ssh/id_ed25519_mini32'
CONTAINER='n8n-test'
DOCKER='/usr/local/bin/docker'
NAME='RobinGraph Audio TEST internal'
TARGET='test'
DATABASE='n8n-test'


def select_target(target):
    global TARGET,HOST,KEY,CONTAINER,DOCKER,NAME,DATABASE,CREDENTIAL_ID,WORKFLOW_ID
    if target not in ('test','prod'): raise ValueError('Unknown n8n audio target')
    TARGET=target
    if target=='prod':
        HOST='kimdove@192.168.219.99';KEY=None;CONTAINER='n8n';DOCKER='docker';DATABASE='n8n'
        NAME='RobinGraph Audio PROD collector internal';CREDENTIAL_ID='rgAudioProdHeader01';WORKFLOW_ID='rgAudioCollectionProd01'
    else:
        HOST='kimdove@192.168.219.98';KEY=Path.home()/'.ssh/id_ed25519_mini32';CONTAINER='n8n-test';DOCKER='/usr/local/bin/docker';DATABASE='n8n-test'
        NAME='RobinGraph Audio TEST internal';CREDENTIAL_ID='rgAudioTestHeader01';WORKFLOW_ID='rgAudioCollectionTest01'


def workflow():
    return build_workflow(TARGET)


def ssh(args, *, content=None):
    transport=['ssh','-o','BatchMode=yes','-i',str(KEY)] if TARGET=='test' else ['ssh','-T','-p','99','-o','StrictHostKeyChecking=yes','-o','NumberOfPasswordPrompts=1']
    p=subprocess.run([*transport,HOST,shlex.join(args)],input=content,capture_output=True,text=True)
    if p.returncode: raise RuntimeError('Remote audio '+TARGET+' command failed (raw output suppressed)')
    return p.stdout


def guard():
    raw=json.loads(ssh([DOCKER,'inspect',CONTAINER]))[0]
    env=dict(x.split('=',1) for x in raw['Config'].get('Env',[]) if '=' in x)
    if env.get('DB_POSTGRESDB_DATABASE')!=DATABASE or not raw['State']['Running']:
        raise RuntimeError('Refusing wrong-target or stopped n8n container')


def cli(args):
    guard()
    return ssh([DOCKER,'exec',CONTAINER,'n8n',*args])


def json_output(raw):
    decoder=json.JSONDecoder()
    for i,c in enumerate(raw):
        if c in '[{':
            try:
                value,_=decoder.raw_decode(raw[i:])
                if isinstance(value,(dict,list)): return value
            except ValueError: pass
    raise RuntimeError('No structured CLI result (raw output suppressed)')


def credential_exists():
    rows=json_output(cli(['export:credentials','--all']))
    matches=[r for r in rows if r.get('id')==CREDENTIAL_ID or r.get('name')==NAME]
    if not matches: return False
    if len(matches)!=1 or matches[0].get('id')!=CREDENTIAL_ID or matches[0].get('name')!=NAME or matches[0].get('type')!='httpHeaderAuth':
        raise RuntimeError('Audio credential name/id ownership conflict')
    return True


def import_payload(kind, payload):
    guard()
    target='/tmp/robingraph-audio-'+str(uuid4())+'.json'
    try:
        ssh([DOCKER,'exec','-i',CONTAINER,'sh','-c','umask 077; cat > '+shlex.quote(target)],content=json.dumps(payload))
        cli(['import:'+kind,'--input='+target])
    finally:
        ssh([DOCKER,'exec',CONTAINER,'rm','-f',target])


def assert_owned(rows, *, allow_active=False, expected=None):
    expected=workflow() if expected is None else expected
    matches=[r for r in rows if r.get('id')==WORKFLOW_ID or r.get('name')==expected['name']]
    if not matches: return
    if len(matches)!=1 or matches[0].get('id')!=WORKFLOW_ID or matches[0].get('name')!=expected['name'] or (matches[0].get('active') and not allow_active):
        raise RuntimeError('Refusing workflow ownership conflict or active workflow')
    # Existing audio workflow may have explicitly edited manual inputs only.
    actual=matches[0]
    def shape(w):
        nodes=[]
        for n in w['nodes']:
            n={k:v for k,v in n.items() if k not in ('disabled',)}
            if n['type']=='n8n-nodes-base.httpRequest':
                expected_node=next(x for x in expected['nodes'] if x['name']==n['name'])
                new_url=expected_node['parameters']['url']
                old_url=new_url.replace('http://192.168.219.97:8000','https://robingraph-test.dove-nest.com')
                if n['parameters']['url']==old_url:
                    n={**n,'parameters':{**n['parameters'],'url':new_url}}
            if n['name']=='Manual inputs': n={**n,'parameters':expected['nodes'][1]['parameters']}
            nodes.append(n)
        return {'nodes':nodes,'connections':w['connections'],'settings':{k:w.get('settings',{}).get(k) for k in expected['settings']}}
    if shape(actual)!=shape(expected): raise RuntimeError('Remote audio workflow drift; review before replacing')


def install_workflow(config, previous_artifact=None):
    rows=json_output(cli(['export:workflow','--all']))
    if previous_artifact:
        content=Path(previous_artifact).read_bytes()
        if TARGET!='prod' or hashlib.sha256(content).hexdigest()!='40c2e72bb552df77a24a9a1f61a5d4d98d85710cf98415054293d8dca2900ea0':
            raise RuntimeError('Only the explicitly reviewed prior Production artifact can migrate')
        assert_owned(rows,expected=json.loads(content))
    else:
        assert_owned(rows)
    if not credential_exists(): raise RuntimeError('Install dedicated audio credential first')
    w=workflow()
    if config:
        c=json.loads(Path(config).read_text())
        if not isinstance(c,dict): raise ValueError('Manual inputs must be a JSON object')
        # CONFIG code validates the merged values before any authenticated call.
        w['nodes'][1]['parameters']['jsCode']='return [{json:{...'+json.dumps({'action':'collect','limit':1,'after_taxon_id':'','scientific_name':'','file_title':'','candidate_id':'','reviewer':'','taxon_verified':False,'playback_verified':False,'approved':False})+',...'+json.dumps(c)+'}}];'
    import_payload('workflow',[w])
    return {'workflow_id':WORKFLOW_ID,'active':False,'imported':True}


def install_credential(path):
    if credential_exists(): raise RuntimeError('Dedicated credential already exists; refusing overwrite')
    if TARGET=='prod':
        remote = '''import pathlib,sys,json
p=pathlib.Path(sys.argv[1]).resolve()
assert str(p)=='/volume3/Birds-Nest/docker-data/robingraph-audio/.env.audio-collector'
assert p.stat().st_mode & 0o077 == 0
v=dict(line.split('=',1) for line in p.read_text().splitlines() if line and not line.startswith('#') and '=' in line)
sys.stdout.write(v.get('ROBINGRAPH_INGEST_INTERNAL_TOKEN',''))'''
        token=ssh(['python3','-c',remote,path])
    else:
        p=Path(path)
        if p.stat().st_mode & 0o077: raise RuntimeError('Token env must be private (0600)')
        values=dict(line.split('=',1) for line in p.read_text().splitlines() if line and not line.startswith('#') and '=' in line)
        token=values.get('ROBINGRAPH_INGEST_INTERNAL_TOKEN','')
    if len(token)<32 or '\n' in token or '\r' in token: raise RuntimeError('Missing valid target-specific token')
    import_payload('credentials',[{'id':CREDENTIAL_ID,'name':NAME,'type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+token}}])
    return {'credential_id':CREDENTIAL_ID,'credential_name':NAME,'imported':True}


def database_receipt():
    """Read-only metadata/fingerprints, never returns credential ciphertext or secrets."""
    guard()
    js = r'''const {Client}=require(require.resolve('pg',{paths:['/usr/local/lib/node_modules/n8n']}));
const e=process.env;
if(e.DB_POSTGRESDB_DATABASE!=='n8n-test') process.exit(2);
const prefix=e.DB_TABLE_PREFIX||'';
if(!/^[A-Za-z0-9_]*$/.test(prefix)) process.exit(3);
const ssl=e.DB_POSTGRESDB_SSL_ENABLED==='true'?{rejectUnauthorized:e.DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED!=='false'}:undefined;
const c=new Client({host:e.DB_POSTGRESDB_HOST,port:Number(e.DB_POSTGRESDB_PORT||5432),user:e.DB_POSTGRESDB_USER,password:e.DB_POSTGRESDB_PASSWORD,database:e.DB_POSTGRESDB_DATABASE,ssl});
(async()=>{await c.connect();await c.query('BEGIN READ ONLY');
const workflows=(await c.query('SELECT id,name,active,md5(nodes::text || connections::text || coalesce(settings::text,\'\')) AS definition_hash FROM "'+prefix+'workflow_entity" ORDER BY id')).rows;
const credentials=(await c.query('SELECT id,name,type,md5(data::text) AS encrypted_data_hash FROM "'+prefix+'credentials_entity" ORDER BY id')).rows;
const executions=(await c.query('SELECT id,status,mode,"startedAt","stoppedAt","waitTill" FROM "'+prefix+'execution_entity" WHERE "workflowId"=$1 ORDER BY id DESC LIMIT 20',['rgAudioCollectionTest01'])).rows;
await c.query('ROLLBACK');await c.end();console.log(JSON.stringify({workflows,credentials,executions}));})().catch(()=>{console.error('Read-only TEST receipt query failed');process.exit(1)});'''
    js=js.replace("'n8n-test'",json.dumps(DATABASE)).replace("'rgAudioCollectionTest01'",json.dumps(WORKFLOW_ID))
    return json.loads(ssh([DOCKER,'exec',CONTAINER,'node','-e',js]))


def execute():
    assert_owned(json_output(cli(['export:workflow','--all'])),allow_active=True)
    # A separate broker port prevents conflict with the running n8n server.
    guard()
    cmd='test "$DB_POSTGRESDB_DATABASE" = '+shlex.quote(DATABASE)+' && N8N_RUNNERS_BROKER_PORT=15680 N8N_RUNNERS_MODE=internal n8n execute --id='+WORKFLOW_ID+' --rawOutput'
    before={str(row['id']) for row in database_receipt()['executions']}
    try:
        raw=ssh([DOCKER,'exec',CONTAINER,'sh','-c',cmd])
    except RuntimeError:
        fresh=[row for row in database_receipt()['executions'] if str(row['id']) not in before]
        if len(fresh)!=1: raise RuntimeError('Failed CLI execution identity ambiguous') from None
        return {'execution':fresh[0],'workflow_id':WORKFLOW_ID,'error_present':True,'completed':False,'cli_command_failed':True}
    result=json_output(raw); data=result.get('data',result); rd=data.get('resultData',{})
    summary=rd.get('runData',{}).get('Execution summary',[])
    items=summary[-1].get('data',{}).get('main',[[]])[0] if summary else []
    fresh=[row for row in database_receipt()['executions'] if str(row['id']) not in before]
    if len(fresh)!=1: raise RuntimeError('Execution identity ambiguous; inspect target execution receipts')
    return {'execution':fresh[0],'workflow_id':WORKFLOW_ID,'last_node':rd.get('lastNodeExecuted'),'error_present':bool(rd.get('error')),'waiting':bool(result.get('waitTill') or data.get('waitTill')),'completed':bool(items) and not rd.get('error') and fresh[0]['status']=='success','summary':[x['json'] for x in items]}


def production_api(action):
    """Use only the pre-existing, verified self API credential in remote memory."""
    if TARGET!='prod' or action not in ('check','activate','deactivate'):
        raise RuntimeError('Unsupported Production API operation')
    guard()
    if action!='check': assert_owned(json_output(cli(['export:workflow','--all'])),allow_active=action=='deactivate')
    remote = r'''import subprocess,json,urllib.parse,sys
x=json.loads(subprocess.check_output(['docker','inspect','n8n']))[0]
e=dict(v.split('=',1) for v in x['Config']['Env'] if '=' in v)
assert e.get('DB_POSTGRESDB_DATABASE')=='n8n'
p=subprocess.run(['docker','exec','n8n','n8n','export:credentials','--id=vryGLzQCz37PkUSW','--decrypted'],capture_output=True,text=True,check=True)
credential=None
for i,c in enumerate(p.stdout):
 if c=='[':
  try:
   a,_=json.JSONDecoder().raw_decode(p.stdout[i:])
   if isinstance(a,list) and len(a)==1 and a[0].get('id')=='vryGLzQCz37PkUSW': credential=a[0];break
  except ValueError:pass
assert credential and credential['type']=='n8nApi'
data=credential['data'];url=urllib.parse.urlsplit(data.get('baseUrl',''))
assert url.scheme=='https' and url.hostname==e.get('N8N_HOST')=='workflow.dove-nest.com' and not url.username and not url.password and url.path.rstrip('/')=='/api/v1'
action=sys.argv[1]
path='/api/v1/workflows?limit=1' if action=='check' else '/api/v1/workflows/rgAudioCollectionProd01/'+('activate' if action=='activate' else 'deactivate')
js="""const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));(async()=>{const r=await fetch('http://127.0.0.1:5678'+p.path,{method:p.method,headers:{'X-N8N-API-KEY':p.key},redirect:'error'});const b=await r.json().catch(()=>({}));const out={http_status:r.status};if(p.method==='GET')out.rows=(b.data||[]).map(x=>({id:x.id,name:x.name,active:x.active}));else{out.id=b.id;out.name=b.name;out.active=b.active;}console.log(JSON.stringify(out));})().catch(()=>process.exit(1));"""
r=subprocess.run(['docker','exec','-i','n8n','node','-e',js],input=json.dumps({'path':path,'method':'GET' if action=='check' else 'POST','key':data['apiKey']}),capture_output=True,text=True,check=True)
print(r.stdout)
'''
    result=json.loads(ssh(['python3','-c',remote,action]))
    if result.get('http_status')!=200: raise RuntimeError('Production n8n API operation failed: HTTP '+str(result.get('http_status')))
    if action!='check' and (result.get('id')!=WORKFLOW_ID or result.get('active')!=(action=='activate')):
        raise RuntimeError('Production workflow API state mismatch')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['inspect','audit','api-check','activate','deactivate','install-credential','import','execute'])
    p.add_argument('--target',choices=('test','prod'),default='test');p.add_argument('--apply',action='store_true');p.add_argument('--token-env');p.add_argument('--config');p.add_argument('--migrate-reviewed-artifact');p.add_argument('--output',type=Path)
    a=p.parse_args()
    select_target(a.target)
    if a.action not in ('inspect','audit','api-check') and not a.apply: p.error('Remote mutation/execution requires --apply after review')
    if a.action=='inspect':
        guard(); result={'target':CONTAINER,'version':cli(['--version']).strip(),'credential_present':credential_exists()}
    elif a.action=='audit': result=database_receipt()
    elif a.action in ('api-check','activate','deactivate'): result=production_api('check' if a.action=='api-check' else a.action)
    elif a.action=='install-credential':
        if not a.token_env: p.error('--token-env required')
        result=install_credential(a.token_env)
    elif a.action=='import': result=install_workflow(a.config,a.migrate_reviewed_artifact)
    else: result=execute()
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output: a.output.write_text(rendered)
    print(rendered,end='')

if __name__=='__main__': main()
