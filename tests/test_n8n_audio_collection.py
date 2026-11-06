"""Exercise the generated Code nodes without contacting n8n or a provider."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import generate_n8n_audio_collection as audio
import manage_n8n_audio as management
from copy import deepcopy


def run_js(source, incoming, previous=None, config=None, persistent=None):
    payload={'source':source,'incoming':incoming,'previous':previous,'config':config,'persistent':persistent or {}}
    js="""const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const $input={first:()=>({json:p.incoming})};const $=name=>({item:{json:p.previous},first:()=>({json:p.config})});try {console.log(JSON.stringify({output:new Function('$input','$','$getWorkflowStaticData',p.source)($input,$,()=>p.persistent),static_data:p.persistent}));}catch(e){console.log(JSON.stringify({error:e.message}));}"""
    return json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(payload),text=True))


class AudioWorkflowTests(unittest.TestCase):
    def config(self,**values):
        return dict(action='collect',limit=1,after_taxon_id='',scientific_name='',file_title='',candidate_id='',reviewer='',taxon_verified=False,playback_verified=False,approved=False,**values)

    def initial(self,**values):
        c=self.config();c.update(values)
        return run_js(audio.INITIALIZE,{'deployment_target':'test'},config=c)['output'][0]['json']

    def advance(self,previous,status,body,headers=None):
        return run_js(audio.TRANSITION,{'statusCode':status,'body':body,'headers':headers or {}},previous=previous)['output'][0]['json']

    def test_generated_artifact_and_security(self):
        self.assertEqual(json.loads(audio.OUTPUT.read_text()),audio.workflow())
        self.assertEqual(audio.ORIGIN,'http://192.168.219.97:8000')
        w=audio.workflow();self.assertFalse(w['active'])
        self.assertEqual([n['type'] for n in w['nodes'] if 'Trigger' in n['type']],['n8n-nodes-base.manualTrigger'])
        for n in w['nodes']:
            if n['type']=='n8n-nodes-base.httpRequest':
                self.assertFalse(n['retryOnFail'])
                self.assertFalse(n['parameters']['options']['redirect']['redirect']['followRedirects'])
        self.assertNotIn('Authorization',json.dumps(w))
        self.assertNotIn('discord',json.dumps(w).lower())

    def test_import_ownership_allows_only_exact_previous_test_origin(self):
        old=deepcopy(audio.workflow())
        for n in old['nodes']:
            if n['type']=='n8n-nodes-base.httpRequest':
                n['parameters']['url']=n['parameters']['url'].replace(audio.ORIGIN,'https://robingraph-test.dove-nest.com')
        management.assert_owned([old])
        evil=deepcopy(old)
        next(n for n in evil['nodes'] if n['name']=='Audio API')['parameters']['url']='https://evil.example/collect'
        with self.assertRaises(RuntimeError): management.assert_owned([evil])
        active=deepcopy(old);active['active']=True
        with self.assertRaises(RuntimeError): management.assert_owned([active])

    def test_production_schedule_cannot_inherit_manual_review_or_publish(self):
        w=audio.workflow('prod');nodes={n['name']:n for n in w['nodes']}
        ids=[n['id'] for n in w['nodes']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertFalse(w['active'])
        self.assertEqual(nodes['Daily 03:00 Korea']['parameters']['rule']['interval'][0]['expression'],'0 3 * * *')
        for action in ['review','publish']:
            config={**self.config(),'action':action,'candidate_id':'a'*64,'approved':True}
            scheduled=run_js(nodes['Scheduled collection inputs']['parameters']['jsCode'],{'after_taxon_id':'old'},config=config)['output'][0]['json']
            self.assertEqual(scheduled['action'],'collect');self.assertEqual(scheduled['limit'],1)
            self.assertFalse(scheduled['approved']);self.assertEqual(scheduled['candidate_id'],'')
            self.assertEqual(scheduled['after_taxon_id'],'old')
            initial=nodes['Initialize request']['parameters']['jsCode']
            self.assertIn('error',run_js(initial,{'deployment_target':'prod','publication_enabled':False},config=config))
            self.assertIn('error',run_js(initial,{'deployment_target':'prod','publication_enabled':True},config=scheduled))
        self.assertEqual(json.loads((ROOT/'n8n/robingraph-audio-collection-prod.json').read_text()),w)

    def test_production_cursor_checkpoint_preserves_results_and_requires_scheduled_success(self):
        w=audio.workflow('prod');nodes={n['name']:n for n in w['nodes']}
        self.assertNotIn('$getWorkflowStaticData',json.dumps(w))
        self.assertTrue(nodes['Read scheduled cursor']['alwaysOutputData'])
        self.assertEqual(nodes['Save scheduled cursor']['type'],'n8n-nodes-base.dataTable')
        condition=nodes['Checkpoint scheduled success']['parameters']['conditions']['conditions'][0]['leftValue'][3:-2].strip()
        for scheduled,deferred in [(True,False),(True,True),(False,False)]:
            state={'config':{'scheduled':scheduled},'deferred':deferred,'action':'collect','next_cursor':'next','results':[{'status':'awaiting_review'}]}
            prepared=run_js(nodes['Prepare execution summary']['parameters']['jsCode'],{'state':state})['output'][0]['json']
            guard='const $json=$input.first().json;return [{json:{save:('+condition+')}}];'
            allowed=run_js(guard,prepared)['output'][0]['json']['save']
            self.assertEqual(allowed,scheduled and not deferred)
            final=run_js(nodes['Execution summary']['parameters']['jsCode'],{'id':1,'after_taxon_id':'next'},config=prepared)['output'][0]['json']
            self.assertEqual(final['results'],state['results']);self.assertEqual(final['cursor_saved'],allowed)
        self.assertEqual(nodes['Save scheduled cursor']['parameters']['columns']['value']['after_taxon_id'],"={{ $json.next_cursor || '' }}")

    def test_production_permanent_source422_skips_once_but_provider_failure_stops(self):
        nodes={n['name']:n for n in audio.workflow('prod')['nodes']}
        state={'action':'collect','config':{'scheduled':True},'queue':[{'scientific_name':'A a'}],'results':[],'next_cursor':'next'}
        previous={'state':state,'request':{'path':'stage','body':{'scientific_name':'A a','file_title':'File:bad.ogg'}}}
        r=run_js(nodes['Advance state']['parameters']['jsCode'],{'statusCode':422,'body':{}},previous=previous)['output'][0]['json']
        self.assertTrue(r['done']);self.assertEqual(r['state']['results'][0]['status'],'skipped_source_validation')
        self.assertEqual(r['state']['results'][0]['file_title'],'File:bad.ogg')
        prepared=run_js(nodes['Prepare execution summary']['parameters']['jsCode'],r)['output'][0]['json']
        self.assertEqual(prepared['next_cursor'],'next');self.assertEqual(prepared['status'],'finished')
        failed=run_js(nodes['Advance state']['parameters']['jsCode'],{'statusCode':502,'body':{}},previous=previous,persistent={'audio_cursor':'old'})
        self.assertIn('error',failed)

    def test_guards_and_explicit_review(self):
        self.assertIn('error',run_js(audio.INITIALIZE,{'deployment_target':'production'},config=self.config()))
        self.assertIn('error',run_js(audio.INITIALIZE,{'deployment_target':'test'},config={**self.config(),'limit':6}))
        self.assertIn('error',run_js(audio.INITIALIZE,{'deployment_target':'test'},config={**self.config(),'action':'review','candidate_id':'a'*64}))
        r=self.initial(action='review',candidate_id='a'*64,reviewer='Human',taxon_verified=True,playback_verified=True,approved=True)
        self.assertEqual(r['request']['path'],'review')
        self.assertTrue(self.advance(r,200,{'status':'approved'})['done'])

    def test_batch_cursor_and_one_file_per_species(self):
        r=self.initial(after_taxon_id='prior',limit=2)
        self.assertEqual(r['request']['body'],{'limit':2,'after_taxon_id':'prior'})
        r=self.advance(r,200,{'targets':[{'scientific_name':'A a'},{'scientific_name':'B b'}],'next_cursor':'next'})
        r=self.advance(r,200,{'candidates':[{'scientific_name':'A a','file_title':'File:first.ogg'},{'scientific_name':'A a','file_title':'File:second.ogg'}]})
        self.assertEqual(r['request']['body']['file_title'],'File:first.ogg')
        r=self.advance(r,200,{'candidate_id':'a'*64,'status':'awaiting_review'})
        self.assertEqual(r['request']['path'],'status')
        r=self.advance(r,200,{'candidate_id':'a'*64,'status':'awaiting_review'})
        self.assertEqual(r['request']['body']['scientific_name'],'B b')
        r=self.advance(r,200,{'candidates':[]})
        self.assertTrue(r['done']);self.assertEqual(r['state']['next_cursor'],'next')
        self.assertEqual(len(r['state']['results']),2)

    def test_stage_429_stops_batch_waits_exactly_then_status_only(self):
        r=self.initial(scientific_name='Passer montanus',file_title='File:exact.ogg')
        r=self.advance(r,429,{'candidate_id':'a'*64,'retry_after_seconds':600},{'retry-after':'601'})
        self.assertEqual(r['wait_seconds'],601);self.assertEqual(r['state']['queue'],[])
        self.assertEqual(r['request']['path'],'status')
        waiting=r
        r=self.advance(r,200,{'status':'deferred'})
        self.assertTrue(r['done']);self.assertTrue(r['state']['deferred'])
        r=self.advance(waiting,429,{'retry_after_seconds':600})
        self.assertTrue(r['done']);self.assertEqual(r['wait_seconds'],0)

    def test_discovery_429_has_no_status_candidate(self):
        r=self.initial(scientific_name='A a')
        r=self.advance(r,429,{'retry_after_seconds':600})
        self.assertIsNone(r['request']);self.assertEqual(r['wait_seconds'],600)
        self.assertIn('error',run_js(audio.TRANSITION,{'statusCode':429,'body':{}},previous=self.initial()))

    def test_collection_never_auto_publishes(self):
        r=self.initial(scientific_name='A a',file_title='File:x.ogg')
        r=self.advance(r,200,{'candidate_id':'a'*64,'status':'awaiting_review'})
        r=self.advance(r,200,{'candidate_id':'a'*64,'status':'awaiting_review'})
        self.assertTrue(r['done']);self.assertEqual(r['state']['results'][0]['status'],'awaiting_review')

    def test_transport_and_cross_species_fail_closed(self):
        r=self.initial(scientific_name='A a')
        self.assertIn('error',run_js(audio.TRANSITION,{'statusCode':401,'body':{}},previous=r))
        self.assertIn('error',run_js(audio.TRANSITION,{'statusCode':200,'body':{'candidates':[{'scientific_name':'B b','file_title':'File:x.ogg'}]}},previous=r))

if __name__=='__main__': unittest.main()
