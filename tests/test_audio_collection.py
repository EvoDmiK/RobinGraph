import copy
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from hashlib import sha1
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.api.services import ApiError
from robingraph.ingest.audio import AudioService, retry_seconds, validate_file
from robingraph.retrieval import recordings
from test_species_profile import LINEAGE


class MemoryStore:
    def __init__(self):
        self.rows = {}

    @contextmanager
    def session(self,**kwargs):
        before=copy.deepcopy(self.rows)
        try:
            yield None
        except Exception:
            self.rows=before
            raise

    def get(self,cursor,key):
        return copy.deepcopy(self.rows.get(key))

    def save(self,cursor,key,science,title,status,data):
        self.rows[key]={'id':key,'scientific_name':science,'file_title':title,'status':status,'data':copy.deepcopy(data)}

    def cooldown(self,cursor):
        values=[datetime.fromisoformat(r['data']['retry_at']) for r in self.rows.values() if r['status']=='deferred']
        return max(values) if values else None

    def pending_species(self):
        return {r['scientific_name'] for r in self.rows.values() if r['status'] in ('awaiting_review','approved','published')}

    def published(self,scientific_name=None,file_name=None):
        return [copy.deepcopy(r) for r in self.rows.values() if r['status']=='published'
                and (scientific_name is None or r['scientific_name']==scientific_name)
                and (file_name is None or r['data'].get('file_name')==file_name)][:3]


class AudioCollectionTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=MemoryStore();self.graph=Mock()
        self.target={'taxon_id':LINEAGE.items[-1].taxon_id,'concept_set_id':LINEAGE.concept_set_id,'taxonomy_release':LINEAGE.taxonomy_release}
        self.resolve=Mock(return_value=self.target)
        self.service=AudioService(self.store,self.tmp.name,self.graph,self.resolve,'test-token')
        data=recordings._reviewed_data()
        self.raw=copy.deepcopy(data['records'][0])
        self.audio=b'OggS'+b'\x00'*24+b'\x01vorbis'+b'\x00'*40
        self.raw['imageinfo'].update(size=len(self.audio),sha1=sha1(self.audio).hexdigest())
        self.metadata={'query':{'pages':[{'pageid':self.raw['page_id'],'title':self.raw['title'],
                                       'revisions':[{'revid':self.raw['revision_id']}],'imageinfo':[self.raw['imageinfo']]}]}}
        self.client=TestClient(create_django_app(audio_service=self.service))
        self.headers={'Authorization':'Bearer test-token'}

    def stage(self):
        with patch('robingraph.ingest.audio.provider_bytes',side_effect=[json.dumps(self.metadata).encode(),self.audio]) as provider:
            result=self.service.stage(self.raw['scientific_name'],self.raw['title'])
            self.assertEqual(2,provider.call_count)
        return result

    def approve(self,key):
        return self.service.review(key,'human-reviewer',True,True,True)

    def test_stage_stores_source_and_exact_bytes_but_is_not_public_and_replay_never_fetches(self):
        result=self.stage();key=result['candidate_id']
        self.assertEqual('awaiting_review',result['status'])
        data=self.store.rows[key]['data']
        self.assertEqual(self.audio,(Path(self.tmp.name)/data['file_name']).read_bytes())
        self.assertEqual(self.raw['imageinfo'],self.store.rows[key]['data']['raw_record']['imageinfo'])
        self.assertEqual(self.raw['revision_id'],self.store.rows[key]['data']['raw_record']['revision_id'])
        self.assertEqual(404,self.client.get('/media/audio/'+data['file_name']).status_code)
        with patch('robingraph.ingest.audio.provider_bytes') as provider:
            self.assertEqual(result,self.service.stage(self.raw['scientific_name'],self.raw['title']))
            provider.assert_not_called()
        self.graph._run.assert_not_called()

    def test_manual_preview_requires_bearer_and_supports_head_range(self):
        result=self.stage();url=result['preview_url']
        self.assertEqual(401,self.client.get(url).status_code)
        partial=self.client.get(url,headers={**self.headers,'Range':'bytes=0-3'})
        self.assertEqual(206,partial.status_code);self.assertEqual(b'OggS',partial.content)
        self.assertEqual('private, no-store',partial.headers['cache-control'])
        response=self.client.head(url,headers=self.headers)
        self.assertEqual(200,response.status_code);self.assertEqual(b'',response.content)
        self.assertEqual(str(len(self.audio)),response.headers['content-length'])
        for value in ('bytes=1000-2000','bytes=1-0','bytes=0-1,4-5','bytes=-0','bytes='+('9'*5000)+'-'):
            response=self.client.get(url,headers={**self.headers,'Range':value})
            self.assertEqual(416,response.status_code)

    def test_no_automatic_approval_or_publication(self):
        key=self.stage()['candidate_id']
        with self.assertRaises(ApiError):self.service.publish(key)
        for taxon,played in ((False,True),(True,False),(1,True)):
            with self.assertRaises(ApiError):self.service.review(key,'human',taxon,played,True)
        self.assertEqual('awaiting_review',self.store.rows[key]['status'])
        self.graph._run.assert_not_called()

    def test_publish_retries_after_graph_or_pg_failure_and_uses_separate_ids(self):
        key=self.stage()['candidate_id'];self.approve(key)
        self.graph._run.side_effect=RuntimeError('graph unavailable')
        with self.assertRaises(RuntimeError):self.service.publish(key)
        self.assertEqual('approved',self.store.rows[key]['status'])
        self.graph._run.side_effect=None;self.graph._run.return_value=[{'recordings':1}]
        original=self.store.save
        with patch.object(self.store,'save',side_effect=RuntimeError('PG unavailable')):
            with self.assertRaises(RuntimeError):self.service.publish(key)
        self.assertEqual('approved',self.store.rows[key]['status'])
        self.assertEqual('published',self.service.publish(key)['status'])
        query, = self.graph._run.call_args.args
        self.assertIn('size(targets)=1',query)
        self.assertEqual('commons-stored:'+key,self.graph._run.call_args.kwargs['rows'][0]['id'])
        before=self.graph._run.call_count
        self.assertEqual('published',self.service.publish(key)['status']);self.assertEqual(before,self.graph._run.call_count)
        data=self.store.rows[key]['data'];name=data['file_name']
        self.graph._run.return_value=[{'id':'commons-stored:'+key,'payload_json':json.dumps(data['recording']),
                                      'metadata_sha256':data['recording']['evidence']['metadata_sha256']}]
        self.assertEqual(self.audio,self.client.get('/media/audio/'+name).content)

    def test_integrity_tampering_or_context_change_prevents_publish(self):
        key=self.stage()['candidate_id'];self.approve(key)
        self.resolve.return_value={**self.target,'taxonomy_release':'next'}
        with self.assertRaises(ApiError):self.service.publish(key)
        self.resolve.return_value=self.target
        (Path(self.tmp.name)/self.store.rows[key]['data']['file_name']).write_bytes(b'changed')
        with self.assertRaises(ApiError):self.service.publish(key)
        self.graph._run.assert_not_called()

    def test_429_persists_provider_global_cooldown_and_blocks_other_species_without_request(self):
        error=HTTPError('https://commons.wikimedia.org',429,'limited',{'Retry-After':'600'},BytesIO())
        with patch('robingraph.ingest.audio.provider_bytes',side_effect=error):
            result=self.service.stage(self.raw['scientific_name'],self.raw['title'])
        self.assertEqual('deferred',result['status']);self.assertGreaterEqual(result['retry_after_seconds'],599)
        with patch('robingraph.ingest.audio.provider_bytes') as provider:
            with self.assertRaises(ApiError) as caught:self.service.stage('Picus canus','File:Picus canus.ogg')
            self.assertEqual(429,caught.exception.status_code)
            with self.assertRaises(ApiError):self.service.discover('Corvus corone')
            provider.assert_not_called()
        self.assertEqual(1,len(self.store.rows))

    def test_official_metadata_species_license_redirect_hash_size_and_magic_guards(self):
        with self.assertRaises(ValueError):validate_file(self.audio,{**self.raw['imageinfo'],'sha1':'bad'})
        for info in ({**self.raw['imageinfo'],'size':1},{**self.raw['imageinfo'],'mime':'video/ogg'}):
            with self.assertRaises(ValueError):validate_file(self.audio,info)
        fake=b'not real audio';info={**self.raw['imageinfo'],'size':len(fake),'sha1':sha1(fake).hexdigest()}
        with self.assertRaises(ValueError):validate_file(fake,info)
        self.metadata['query']['pages'][0]['imageinfo'][0]['url']='https://127.0.0.1/private.ogg'
        with patch('robingraph.ingest.audio.provider_bytes',return_value=json.dumps(self.metadata).encode()) as provider:
            with self.assertRaises(ApiError):self.service.stage(self.raw['scientific_name'],self.raw['title'])
            self.assertEqual(1,provider.call_count)
        from robingraph.ingest.audio import NoRedirect
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None,None,302,'',{},'https://evil.invalid')
        self.assertEqual({},self.store.rows)

    def test_http_auth_body_limits_and_stage_contract(self):
        self.assertEqual(401,self.client.post('/internal/v1/audio/stage',json={}).status_code)
        self.assertEqual(422,self.client.post('/internal/v1/audio/stage',json={'scientific_name':'Anas platyrhynchos','file_title':'File:x.ogg','approved':True},headers=self.headers).status_code)
        self.assertEqual(422,self.client.post('/internal/v1/audio/targets',json={'limit':6},headers=self.headers).status_code)
        self.assertEqual(422,self.client.post('/internal/v1/audio/status',json={'candidate_id':'../private'},headers=self.headers).status_code)
        self.assertEqual(404,self.client.get('/media/audio/invalid.ogg').status_code)

    def test_discovery_candidates_are_unreviewed_and_cooldown_is_not_bypassed(self):
        value={'query':{'search':[{'title':self.raw['title']},{'title':'File:NotAudio.jpg'}]}}
        with patch('robingraph.ingest.audio.provider_bytes',return_value=json.dumps(value).encode()):
            result=self.service.discover(self.raw['scientific_name'])
        self.assertEqual('unreviewed_search_results',result['verification'])
        self.assertEqual([{'scientific_name':self.raw['scientific_name'],'file_title':self.raw['title']}],result['candidates'])
        self.assertEqual({},self.store.rows)

    def test_retry_after_seconds_and_http_date_never_shortens_provider_limit(self):
        now=datetime(2026,11,5,0,0,tzinfo=timezone.utc)
        self.assertEqual(600,retry_seconds('600',now))
        self.assertEqual(600,retry_seconds('Thu, 05 Nov 2026 00:10:00 GMT',now))
        self.assertEqual(600,retry_seconds('invalid',now))

    def test_pinned_source_metadata_dates_and_optional_facts_are_preserved_when_mirrored(self):
        pinned=recordings._reviewed_data();original=pinned['records'][0]
        self.metadata['query']['pages'][0]['imageinfo']=[original['imageinfo']]
        from hashlib import sha256
        file_name=sha256(self.audio).hexdigest()+'.ogg'
        with patch('robingraph.ingest.audio.provider_bytes',side_effect=[json.dumps(self.metadata).encode(),self.audio]), patch('robingraph.ingest.audio.validate_file',return_value=(file_name,'audio/ogg')):
            result=self.service.stage(original['scientific_name'],original['title'])
        expected=recordings.reviewed_catalog()[result['recording']['id']]
        self.assertEqual(expected,result['recording'])
        data=self.store.rows[result['candidate_id']]['data']
        self.assertEqual(original,data['raw_record'])
        self.assertEqual(expected['evidence']['retrieved_at'],data['retrieved_at'])
        self.assertTrue(data['metadata_fetched_at'].startswith('2026-'))

    def test_pg_or_local_file_outage_preserves_pinned_fallback_without_duplicate_page(self):
        key=self.stage()['candidate_id'];self.approve(key)
        self.graph._run.return_value=[{'recordings':1}];self.service.publish(key)
        data=self.store.rows[key]['data'];record=data['recording']
        graphrow={'id':'commons-stored:'+key,'payload_json':json.dumps(record),
                  'metadata_sha256':record['evidence']['metadata_sha256']}
        self.graph._run.return_value=[graphrow]
        with patch('robingraph.ingest.audio.read_recordings',return_value=[record]):
            actual=self.service.recordings(LINEAGE)
            self.assertEqual(1,len(actual));self.assertEqual('/media/audio/'+data['file_name'],actual[0]['audio_url'])
            self.assertEqual(record['evidence'],actual[0]['evidence'])
            self.assertNotIn('file_name',actual[0])
            with patch.object(self.store,'published',side_effect=RuntimeError('PG unavailable')):
                self.assertEqual([record],self.service.recordings(LINEAGE))
            (Path(self.tmp.name)/data['file_name']).unlink()
            self.assertEqual([record],self.service.recordings(LINEAGE))

    def test_targets_skip_already_awaiting_review_and_remain_bounded(self):
        self.stage()
        science=self.raw['scientific_name']
        entries={'taxa':{'taxon:1':{'status':'korea','scientific_name':science},
                         'taxon:2':{'status':'korea','scientific_name':'Picus canus'},
                         'taxon:3':{'status':'outside','scientific_name':'Other taxon'}}}
        self.resolve.return_value={**self.target,'taxon_id':'taxon:2'}
        with patch('robingraph.retrieval.species_scope._bundle',return_value=entries):
            result=self.service.targets(limit=1)
        self.assertEqual([{'taxon_id':'taxon:2','scientific_name':'Picus canus'}],result['targets'])
        self.assertEqual('taxon:2',result['next_cursor'])

    def test_discovery_429_returns_cooldown_contract_and_stops_other_stage(self):
        error=HTTPError('https://commons.wikimedia.org',429,'limited',{'Retry-After':'600'},BytesIO())
        with patch('robingraph.ingest.audio.provider_bytes',side_effect=error):
            response=self.client.post('/internal/v1/audio/discover',json={'scientific_name':'Picus canus'},headers=self.headers)
        self.assertEqual(429,response.status_code)
        self.assertGreaterEqual(int(response.headers['retry-after']),599)
        with patch('robingraph.ingest.audio.provider_bytes') as provider:
            response=self.client.post('/internal/v1/audio/stage',json={'scientific_name':self.raw['scientific_name'],'file_title':self.raw['title']},headers=self.headers)
            self.assertEqual(429,response.status_code);provider.assert_not_called()

    def test_audio_routes_are_opt_in_and_documented_only_when_enabled(self):
        disabled=TestClient(create_django_app())
        self.assertEqual(404,disabled.post('/internal/v1/audio/targets',json={}).status_code)
        self.assertNotIn('/internal/v1/audio/stage',disabled.app.openapi()['paths'])
        self.assertIn('/internal/v1/audio/stage',self.client.app.openapi()['paths'])
        self.assertIn('/media/audio/{file_name}',self.client.app.openapi()['paths'])

    def test_private_preview_rejects_symlink_and_modified_storage(self):
        result=self.stage();data=self.store.rows[result['candidate_id']]['data']
        path=Path(self.tmp.name)/data['file_name']
        other=Path(self.tmp.name)/'other';other.write_bytes(self.audio)
        path.unlink();path.symlink_to(other)
        self.assertEqual(404,self.client.get(result['preview_url'],headers=self.headers).status_code)
        path.unlink();path.write_bytes(b'modified')
        self.assertEqual(404,self.client.get(result['preview_url'],headers=self.headers).status_code)

    def test_public_bytes_require_active_exact_target_and_graph_payload_hash(self):
        key=self.stage()['candidate_id'];self.approve(key)
        self.graph._run.return_value=[{'recordings':1}];self.service.publish(key)
        data=self.store.rows[key]['data'];record=data['recording'];url='/media/audio/'+data['file_name']
        proof={'id':'commons-stored:'+key,'payload_json':json.dumps(record),
               'metadata_sha256':record['evidence']['metadata_sha256']}
        self.graph._run.return_value=[proof]
        self.assertEqual(200,self.client.get(url).status_code)
        self.assertEqual(206,self.client.head(url,headers={'Range':'bytes=0-3'}).status_code)
        for rows in ([],[{**proof,'metadata_sha256':'changed'}],[{**proof,'payload_json':'{}'}]):
            self.graph._run.return_value=rows
            self.assertEqual(404,self.client.get(url).status_code)
            with patch('robingraph.ingest.audio.read_recordings',return_value=[record]):
                self.assertEqual([record],self.service.recordings(LINEAGE))
        self.graph._run.return_value=[proof]
        self.resolve.return_value={**self.target,'taxonomy_release':'withdrawn'}
        self.assertEqual(404,self.client.get(url).status_code)
        self.resolve.side_effect=ApiError(422,'Target withdrawn')
        self.assertEqual(404,self.client.get(url).status_code)

    def test_discovery_maps_malformed_and_timeout_provider_responses_safely(self):
        for raw in (b'{',b'[]',b'{"query":{"search":[1]}}',b'{"error":{"info":"provider details"}}'):
            with patch('robingraph.ingest.audio.provider_bytes',return_value=raw):
                response=self.client.post('/internal/v1/audio/discover',json={'scientific_name':'Picus canus'},headers=self.headers)
                self.assertEqual(422,response.status_code)
                self.assertNotIn('provider details',response.text)
        with patch('robingraph.ingest.audio.provider_bytes',side_effect=TimeoutError('private endpoint details')):
            response=self.client.post('/internal/v1/audio/discover',json={'scientific_name':'Picus canus'},headers=self.headers)
            self.assertEqual(502,response.status_code)
            self.assertNotIn('private endpoint',response.text)

    def test_provider_uses_read1_and_remaining_socket_timeout_for_slow_trickle(self):
        from robingraph.ingest.audio import provider_bytes
        response=Mock();response.status=200;response.headers={}
        response.read1.return_value=b'x'
        opened=Mock();opened.__enter__=Mock(return_value=response);opened.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=opened
        with patch('robingraph.ingest.audio.time.monotonic',side_effect=[0,29,31]):
            with self.assertRaisesRegex(ValueError,'deadline'):
                provider_bytes('https://commons.wikimedia.org',100,opener)
        response.read.assert_not_called()
        response.read1.assert_called_once()
        response.fp.raw._sock.settimeout.assert_called_once_with(1)

    def test_real_http_content_length_eof_closes_socket_without_breaking_download(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from robingraph.ingest.audio import provider_bytes
        expected=b'complete buffered response'
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length',str(len(expected)))
                self.end_headers()
                self.wfile.write(expected)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.assertEqual(expected,provider_bytes(f'http://127.0.0.1:{server.server_port}',100))
        finally:
            server.shutdown();server.server_close();thread.join()
