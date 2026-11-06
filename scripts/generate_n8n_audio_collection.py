"""Generate the TEST review workflow or the Production daily collection workflow."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from generate_n8n_reference_ingest import node, node_id, code, boolean_if, edge

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'n8n/robingraph-audio-collection-test.json'
WORKFLOW_ID = 'rgAudioCollectionTest01'
CREDENTIAL_ID = 'rgAudioTestHeader01'
PRODUCTION_CURSOR_TABLE_ID = 'J49mL4EifvZ0Pres'
# Fixed trusted TEST LAN only; bearer transport here is intentionally HTTP, not TLS.
ORIGIN = 'http://192.168.219.97:8000'

CONFIG = '''
// Edit these explicit manual inputs. Collection never reviews or publishes.
const config = {action:'collect', limit:1, after_taxon_id:'', scientific_name:'', file_title:'', candidate_id:'', reviewer:'', taxon_verified:false, playback_verified:false, approved:false};
return [{json:config}];
'''
INITIALIZE = '''
const health = $input.first().json;
if (health.deployment_target !== 'test') throw new Error('Audio workflow requires deployment_target=test');
const c = $('Manual inputs').first().json;
if (!['collect','status','review','publish'].includes(c.action)) throw new Error('Unsupported manual action');
if (!Number.isInteger(c.limit) || c.limit < 1 || c.limit > 5) throw new Error('Batch limit must be 1..5');
const s = {action:c.action, queue:[], results:[], next_cursor:null, config:c};
function req(path, body) { return [{json:{state:s, request:{path,body},done:false,wait_seconds:0}}]; }
if (c.action !== 'collect') {
  if (!/^[a-f0-9]{64}$/.test(c.candidate_id)) throw new Error('Explicit candidate_id required');
  const body = {candidate_id:c.candidate_id};
  if (c.action === 'review') {
    if (!c.reviewer.trim() || c.taxon_verified !== true || c.playback_verified !== true || c.approved !== true) throw new Error('Explicit verified human review required');
    Object.assign(body,{reviewer:c.reviewer,taxon_verified:true,playback_verified:true,approved:true});
  }
  return req(c.action, body);
}
if (c.file_title && !c.scientific_name) throw new Error('File title requires scientific_name');
if (c.scientific_name) {
  s.queue = [{scientific_name:c.scientific_name}];
  return req(c.file_title ? 'stage':'discover', c.file_title ? {scientific_name:c.scientific_name,file_title:c.file_title}:{scientific_name:c.scientific_name,limit:3});
}
return req('targets',{limit:c.limit,...(c.after_taxon_id ? {after_taxon_id:c.after_taxon_id}:{})});
'''
TRANSITION = '''
const previous = $('Prepare request').item.json;
const s = previous.state, path = previous.request.path;
const response = $input.first().json;
const status = Number(response.statusCode);
const b = response.body;
function out(request, done=false, wait_seconds=0) { return [{json:{state:s,request,done,wait_seconds}}]; }
function next() {
  if (!s.queue.length) return out(null,true);
  return out({path:'discover',body:{scientific_name:s.queue[0].scientific_name,limit:3}});
}
if (s.deferred) { s.status_after_wait = status >= 200 && status < 300 ? b : {status:'unavailable',http_status:status}; return out(null,true); }
if (status === 429) {
  const raw = Number(response.headers?.['retry-after'] ?? b?.retry_after_seconds);
  if (!Number.isFinite(raw) || raw <= 0) throw new Error('429 without valid Retry-After');
  s.results.push({status:'deferred',scientific_name:s.queue[0]?.scientific_name,candidate_id:b?.candidate_id || null,retry_after_seconds:Math.ceil(raw)});
  s.queue = []; // Never continue this batch or automatically retry remote collection.
  s.deferred = true;
  return out(b?.candidate_id ? {path:'status',body:{candidate_id:b.candidate_id}}:null,false,Math.ceil(raw));
}
if (!(status >= 200 && status < 300) || !b || typeof b !== 'object') throw new Error('Audio API '+path+' failed: HTTP '+status);
if (s.action !== 'collect') { s.results.push(b); return out(null,true); }
if (path === 'targets') {
  if (!Array.isArray(b.targets) || b.targets.length > s.config.limit) throw new Error('Invalid target batch');
  s.queue = b.targets; s.next_cursor = b.next_cursor ?? null; return next();
}
if (path === 'discover') {
  if (!Array.isArray(b.candidates) || b.candidates.length > 3) throw new Error('Invalid discovery response');
  const candidate = b.candidates[0];
  if (!candidate) { s.results.push({scientific_name:s.queue.shift().scientific_name,status:'no_candidates'}); return next(); }
  if (candidate.scientific_name !== s.queue[0].scientific_name || typeof candidate.file_title !== 'string') throw new Error('Candidate species mismatch');
  return out({path:'stage',body:{scientific_name:candidate.scientific_name,file_title:candidate.file_title}});
}
if (path === 'stage') {
  if (!/^[a-f0-9]{64}$/.test(b.candidate_id || '')) throw new Error('Invalid stage candidate_id');
  return out({path:'status',body:{candidate_id:b.candidate_id}});
}
if (path === 'status') { s.results.push(b); s.queue.shift(); return next(); }
throw new Error('Unexpected collection operation');
'''


def http(name, path, method='POST', body=None, position=(0, 0), authenticated=True):
    params = {'method':method,'url':path,'options':{'redirect':{'redirect':{'followRedirects':False}},'timeout':60000,'response':{'response':{'fullResponse':method!='GET','neverError':method!='GET','responseFormat':'json'}}}}
    if authenticated:
        params.update(authentication='genericCredentialType',genericAuthType='httpHeaderAuth')
    if body is not None:
        params.update(sendBody=True,specifyBody='json',jsonBody=body)
    return node(name,'n8n-nodes-base.httpRequest',4.2,params,position,retryOnFail=False,**({'credentials':{'httpHeaderAuth':{'id':CREDENTIAL_ID,'name':'RobinGraph Audio TEST internal'}}} if authenticated else {}))


def workflow(target="test"):
    if target not in ("test", "prod"): raise ValueError("Unknown audio deployment target")
    nodes = [node('Manual trigger','n8n-nodes-base.manualTrigger',1,{},(0,0)),code('Manual inputs',CONFIG,(220,0)),http('Verify TEST health',ORIGIN+'/health','GET',position=(440,0),authenticated=False),code('Initialize request',INITIALIZE,(660,0)),code('Prepare request','return $input.all();',(880,0)),http('Audio API',"={{ '"+ORIGIN+"/internal/v1/audio/' + $json.request.path }}",body='={{ $json.request.body }}',position=(1100,0)),code('Advance state',TRANSITION,(1320,0)),boolean_if('Cooldown required','={{ $json.wait_seconds > 0 }}',(1540,0)),node('Respect Retry-After','n8n-nodes-base.wait',1.1,{'resume':'timeInterval','amount':'={{ $json.wait_seconds }}','unit':'seconds'},(1760,-180),webhookId=str(uuid5(NAMESPACE_URL,'robingraph-audio-cooldown'))),code('After cooldown','const x=$input.first().json; x.wait_seconds=0; x.done=!x.request; return [{json:x}];',(1980,-180)),boolean_if('Finished','={{ $json.done }}',(1760,100)),code('Execution summary',"const s=$input.first().json.state; return [{json:{action:s.action,status:s.deferred?'deferred':'finished',results:s.results,next_cursor:s.next_cursor,status_after_wait:s.status_after_wait || null,publication_automatic:false}}];",(1980,100))]
    connections={}
    def link(a,b,output=0):
        main=connections.setdefault(a,{'main':[]})['main']
        while len(main)<=output: main.append([])
        main[output].append(edge(b))
    for a,b in [('Manual trigger','Manual inputs'),('Manual inputs','Verify TEST health'),('Verify TEST health','Initialize request'),('Initialize request','Prepare request'),('Prepare request','Audio API'),('Audio API','Advance state'),('Advance state','Cooldown required'),('Cooldown required','Respect Retry-After'),('Respect Retry-After','After cooldown'),('After cooldown','Finished'),('Finished','Execution summary')]: link(a,b)
    link('Cooldown required','Finished',1);link('Finished','Prepare request',1)
    result={'id':WORKFLOW_ID,'name':'RobinGraph Audio Collection TEST (manual)','active':False,'nodes':nodes,'connections':connections,'settings':{'executionOrder':'v1','timezone':'Asia/Seoul','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','executionTimeout':86400},'pinData':{}}
    if target == 'prod':
        configure_production(result)
    result['versionId']=str(uuid5(NAMESPACE_URL,json.dumps(result,sort_keys=True)))
    return result

def configure_production(result):
    """Extend the shared collection graph; production has no review/publish action."""
    result.update(id='rgAudioCollectionProd01',name='RobinGraph Audio Collection PROD (daily 1 species)')
    by_name={n['name']:n for n in result['nodes']}
    for n in result['nodes']:
        if n['type']=='n8n-nodes-base.httpRequest':
            n['parameters']['url']=n['parameters']['url'].replace(ORIGIN,'http://robingraph-audio-collector:8000')
            if 'credentials' in n:
                n['credentials']={'httpHeaderAuth':{'id':'rgAudioProdHeader01','name':'RobinGraph Audio PROD collector internal'}}
    manual="""const config={action:'collect',limit:1,after_taxon_id:'',scientific_name:'',file_title:'',candidate_id:''};
return [{json:{...config,scheduled:false}}];"""
    by_name['Manual inputs']['parameters']['jsCode']=manual
    initial=INITIALIZE.replace("health.deployment_target !== 'test'", "health.deployment_target !== 'prod' || health.publication_enabled !== false")
    initial=initial.replace('Audio workflow requires deployment_target=test','Audio workflow requires prod collector with publication disabled')
    initial=initial.replace("$('Manual inputs').first().json;", "$('Execution inputs').first().json;\nc.scheduled=$('Scheduled collection inputs').isExecuted===true;")
    initial=initial.replace("['collect','status','review','publish']", "['collect','status']")
    begin=initial.index("  if (c.action === 'review') {")
    end=initial.index("  return req(c.action, body);",begin)
    initial=initial[:begin]+initial[end:]
    by_name['Initialize request']['parameters']['jsCode']=initial
    transition=TRANSITION.replace("if (!(status >= 200 && status < 300)","""if (status===422 && path==='stage') {
 const species=s.queue.shift();
 s.results.push({status:'skipped_source_validation',scientific_name:species.scientific_name,file_title:previous.request.body.file_title,http_status:422});
 return next();
}
if (!(status >= 200 && status < 300)""")
    by_name['Advance state']['parameters']['jsCode']=transition
    # Separate schedule inputs cannot inherit a manually edited action or approval flags.
    result['nodes'] += [node('Daily 03:00 Korea','n8n-nodes-base.scheduleTrigger',1.2,
        {'rule':{'interval':[{'field':'cronExpression','expression':'0 3 * * *'}]}},(0,300)),
        code('Scheduled collection inputs',"""const row=$input.first().json;
return [{json:{action:'collect',limit:1,after_taxon_id:row.after_taxon_id||'',scientific_name:'',file_title:'',candidate_id:'',approved:false,taxon_verified:false,playback_verified:false,scheduled:true}}];""",(220,300)),
        code('Execution inputs','return $input.all();',(440,150))]
    c=result['connections']
    c['Manual inputs']={'main':[[edge('Execution inputs')]]}
    c['Daily 03:00 Korea']={'main':[[edge('Read scheduled cursor')]]}
    c['Read scheduled cursor']={'main':[[edge('Scheduled collection inputs')]]}
    c['Scheduled collection inputs']={'main':[[edge('Execution inputs')]]}
    c['Execution inputs']={'main':[[edge('Verify TEST health')]]}
    by_name['Verify TEST health']['name']='Verify PROD collector health'
    c['Verify PROD collector health']=c.pop('Verify TEST health')
    for outputs in c.values():
        for branch in outputs['main']:
            for target in branch:
                if target['node']=='Verify TEST health': target['node']='Verify PROD collector health'
    by_name['Execution summary']['name']='Prepare execution summary'
    by_name['Execution summary']['id']=node_id('Prepare execution summary')
    by_name['Execution summary']['parameters']['jsCode']="""const s=$input.first().json.state;
return [{json:{action:s.action,status:s.deferred?'deferred':'finished',results:s.results,next_cursor:s.next_cursor,status_after_wait:s.status_after_wait||null,publication_automatic:false,scheduled:s.config.scheduled===true}}];"""
    for outputs in c.values():
        for branch in outputs['main']:
            for target in branch:
                if target['node']=='Execution summary': target['node']='Prepare execution summary'
    cursor={'dataTableId':{'__rl':True,'mode':'id','value':PRODUCTION_CURSOR_TABLE_ID},
            'matchType':'allConditions','filters':{'conditions':[{'keyName':'cursor_key','condition':'eq','keyValue':'prod'}]}}
    result['nodes'] += [
        node('Read scheduled cursor','n8n-nodes-base.dataTable',1.1,
             {'resource':'row','operation':'get',**cursor,'returnAll':False,'limit':1},(220,500),alwaysOutputData=True,retryOnFail=False),
        boolean_if('Checkpoint scheduled success',"={{ $json.scheduled === true && $json.status === 'finished' }}",(2200,100)),
        node('Save scheduled cursor','n8n-nodes-base.dataTable',1.1,
             {'resource':'row','operation':'upsert',**cursor,'columns':{'mappingMode':'defineBelow','value':{'cursor_key':'prod','after_taxon_id':"={{ $json.next_cursor || '' }}"}},'options':{'dryRun':False}},(2420,0),retryOnFail=False),
        code('Execution summary',"const s=$('Prepare execution summary').first().json;return [{json:{...s,cursor_saved:s.scheduled===true&&s.status==='finished'}}];",(2640,100))]
    c['Prepare execution summary']={'main':[[edge('Checkpoint scheduled success')]]}
    c['Checkpoint scheduled success']={'main':[[edge('Save scheduled cursor')],[edge('Execution summary')]]}
    c['Save scheduled cursor']={'main':[[edge('Execution summary')]]}



if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--target',choices=('test','prod'),default='test');args=parser.parse_args()
    output=OUTPUT if args.target=='test' else ROOT/'n8n/robingraph-audio-collection-prod.json'
    rendered=json.dumps(workflow(args.target),ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not output.exists() or output.read_text()!=rendered: raise SystemExit('Audio workflow artifact is stale')
    else: output.write_text(rendered)
