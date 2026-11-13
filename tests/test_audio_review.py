"""Read-only review auth, safe paging and private preview regressions (offline)."""
import copy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.ingest.audio import AudioService
from robingraph.ingest.audio_collector import create_app
from robingraph.ingest.audio_store import AudioStore
from robingraph.retrieval.recordings import _reviewed_data, reviewed_record
from test_audio_collection import MemoryStore


class ReviewStore(MemoryStore):
    def candidates(self, *, limit, offset, status=None):
        rows = sorted(self.rows.values(),key=lambda row:(row['updated_at'],row['id']),reverse=True)
        return copy.deepcopy([row for row in rows if status is None or row['status']==status][offset:offset+limit])


class AudioReviewTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.store=ReviewStore();self.graph=Mock();self.resolve=Mock()
        self.service=AudioService(self.store,self.directory.name,self.graph,self.resolve,'collection-fixture',
                                  review_token='readonly-fixture')
        self.client=TestClient(create_django_app(audio_service=self.service))
        self.headers={'Authorization':'Bearer readonly-fixture'}
        self.key='a'*64
        content=b'OggSfixture';digest=sha256(content).hexdigest()
        self.name=digest+'.ogg';(Path(self.directory.name)/self.name).write_bytes(content)
        raw=copy.deepcopy(next(row for row in _reviewed_data()['records'] if row['scientific_name']=='Passer montanus'))
        record=reviewed_record(raw,_reviewed_data()['retrieved_at'])
        record['private_extra']='not for browser';record['evidence']['private_extra']='hidden evidence'
        self.store.rows[self.key]={'id':self.key,'scientific_name':record['scientific_name'],
            'file_title':record['title'],'status':'awaiting_review','updated_at':datetime(2026,11,9,tzinfo=timezone.utc),
            'data':{'recording':record,'file_name':self.name,'file_sha256':digest,'mime':'audio/ogg',
                    'raw_record':{'html':'<script>secret</script>'},'private_path':'/private/test/path',
                    'metadata_fetched_at':'2026-11-05T02:33:43.046130+00:00',
                    'target':{'taxon_id':'avilist-taxon:v2025b:29772','concept_set_id':'rg:concept-set:avilist-v2025b','taxonomy_release':'v2025b'}}}

    def test_list_requires_distinct_review_bearer_and_missing_configuration_fails_closed(self):
        for headers in ({},{'Authorization':'Bearer wrong'},{'Authorization':'Bearer collection-fixture'}):
            self.assertEqual(401,self.client.get('/internal/v1/audio/candidates',headers=headers).status_code)
        self.assertEqual(200,self.client.get('/internal/v1/audio/candidates',headers=self.headers).status_code)
        self.service.review_token=None
        self.assertEqual(401,self.client.get('/internal/v1/audio/candidates',headers=self.headers).status_code)
        with self.assertRaises(ValueError):
            AudioService(self.store,self.directory.name,self.graph,self.resolve,'same',review_token='same')
        self.graph.assert_not_called();self.resolve.assert_not_called()

    def test_readonly_key_never_authorizes_status_or_writes_and_requests_do_not_mutate(self):
        before=copy.deepcopy(self.store.rows)
        for action in ('status','targets','discover','stage','review','publish'):
            self.assertEqual(401,self.client.post('/internal/v1/audio/'+action,json={},headers=self.headers).status_code)
        self.assertEqual(405,self.client.post('/internal/v1/audio/candidates',json={},headers=self.headers).status_code)
        self.assertEqual(200,self.client.get('/internal/v1/audio/candidates',headers=self.headers).status_code)
        self.assertEqual(before,self.store.rows)
        self.graph._run.assert_not_called();self.resolve.assert_not_called()

    def test_metadata_whitelist_exact_name_missing_file_and_nullable_preview(self):
        response=self.client.get('/internal/v1/audio/candidates',headers=self.headers)
        self.assertEqual('private, no-store',response.headers['cache-control'])
        data=response.json();item=data['items'][0]
        self.assertEqual({'has_more':False,'next_offset':None},{key:data[key] for key in ('has_more','next_offset')})
        self.assertEqual('참새',item['korean_name']);self.assertEqual(11,item['file_bytes'])
        self.assertEqual('2026-11-05T02:33:43.046130+00:00',item['collected_at'])
        self.assertNotEqual(item['recording']['evidence']['retrieved_at'],item['collected_at'])
        self.assertEqual('/internal/v1/audio/preview/'+self.key,item['preview_url'])
        for forbidden in ('private_extra','hidden evidence','private_path','/private/test/path','<script>secret','raw_record','file_name'):
            self.assertNotIn(forbidden,response.text)
        self.assertEqual(self.store.rows[self.key]['data']['recording']['evidence']['metadata_sha256'],item['recording']['evidence']['metadata_sha256'])
        (Path(self.directory.name)/self.name).unlink()
        self.store.rows[self.key]['data']['target']['taxonomy_release']='future'
        self.store.rows[self.key]['data'].pop('metadata_fetched_at')
        item=self.client.get('/internal/v1/audio/candidates',headers=self.headers).json()['items'][0]
        self.assertIsNone(item['korean_name']);self.assertIsNone(item['file_bytes']);self.assertIsNone(item['preview_url'])
        self.assertIsNone(item['collected_at'])
        self.assertEqual(404,self.client.get('/internal/v1/audio/preview/'+self.key,headers=self.headers).status_code)

    def test_stable_tie_pages_status_filter_empty_and_query_guards(self):
        for key,status in (('b'*64,'deferred'),('c'*64,'awaiting_review')):
            row=copy.deepcopy(self.store.rows[self.key]);row.update(id=key,status=status)
            self.store.rows[key]=row
        first=self.client.get('/internal/v1/audio/candidates?limit=1',headers=self.headers).json()
        self.assertEqual('c'*64,first['items'][0]['candidate_id']);self.assertEqual(1,first['next_offset'])
        second=self.client.get('/internal/v1/audio/candidates?limit=1&offset=1',headers=self.headers).json()
        self.assertEqual('b'*64,second['items'][0]['candidate_id']);self.assertTrue(second['has_more'])
        last=self.client.get('/internal/v1/audio/candidates?limit=1&offset=2',headers=self.headers).json()
        self.assertEqual(self.key,last['items'][0]['candidate_id']);self.assertFalse(last['has_more'])
        filtered=self.client.get('/internal/v1/audio/candidates?status=deferred',headers=self.headers).json()
        self.assertEqual(['b'*64],[item['candidate_id'] for item in filtered['items']])
        self.assertEqual([],self.client.get('/internal/v1/audio/candidates?status=approved',headers=self.headers).json()['items'])
        for query in ('limit=0','limit=51','offset=-1','offset=10001','offset=x','limit=1.5','status=unknown','status=','token=oops','limit=1&limit=2'):
            self.assertEqual(422,self.client.get('/internal/v1/audio/candidates?'+query,headers=self.headers).status_code,query)

    def test_both_tokens_allow_preview_head_and_range_but_not_unauthorized(self):
        url='/internal/v1/audio/preview/'+self.key
        for token in ('readonly-fixture','collection-fixture'):
            headers={'Authorization':'Bearer '+token}
            self.assertEqual(200,self.client.head(url,headers=headers).status_code)
            response=self.client.get(url,headers={**headers,'Range':'bytes=0-3'})
            self.assertEqual(206,response.status_code);self.assertEqual(b'OggS',response.content)
            self.assertEqual('private, no-store',response.headers['cache-control'])
        self.assertEqual(401,self.client.head(url).status_code)
        self.assertEqual(401,self.client.get(url).status_code)
        self.assertEqual(404,self.client.get('/media/audio/'+self.name).status_code)

    def test_collector_supports_same_readonly_contract_without_publication(self):
        client=TestClient(create_app(self.service,'test'))
        self.assertEqual(200,client.get('/internal/v1/audio/candidates',headers=self.headers).status_code)
        self.assertEqual(401,client.post('/internal/v1/audio/stage',json={},headers=self.headers).status_code)
        self.assertEqual(404,client.post('/internal/v1/audio/publish',json={},headers=self.headers).status_code)
        self.assertFalse(client.get('/health').json()['publication_enabled'])

    def test_review_page_route_exists_only_with_optin_audio_service(self):
        self.assertEqual(404,TestClient(create_django_app()).get('/audio-review').status_code)
        with TemporaryDirectory() as empty_assets:
            client=TestClient(create_django_app(audio_service=self.service,static_dir=Path(empty_assets)))
            self.assertEqual(503,client.get('/audio-review').status_code)
            for name,content in (('audio-review.html','<script src="/static/audio-review.js"></script>'),
                                 ('audio-review.js','console.log("fixture")'),('audio-review.css','body{}'),('styles.css','html{}')):
                (Path(empty_assets)/name).write_text(content)
            response=client.get('/audio-review')
            self.assertEqual(200,response.status_code)
            self.assertIn('/static/audio-review.js?v=',response.text)
            for name,mime in (('audio-review.js','application/javascript'),('audio-review.css','text/css'),('audio-review.html','text/html')):
                asset=client.get('/static/'+name)
                self.assertEqual(200,asset.status_code)
                self.assertTrue(asset.headers['content-type'].startswith(mime))

    def test_pg_list_is_parameterized_stable_select_without_write_or_lock(self):
        store=AudioStore(Mock());cursor=Mock();cursor.fetchall.return_value=[]
        with patch.object(store,'session') as session:
            session.return_value.__enter__.return_value=cursor
            self.assertEqual([],store.candidates(limit=21,offset=40,status='approved'))
        query,params=cursor.execute.call_args.args
        self.assertIn('ORDER BY updated_at DESC,id DESC',query)
        self.assertNotIn('FOR UPDATE',query);self.assertNotIn('INSERT',query)
        self.assertEqual(('approved','approved',21,40),params)
