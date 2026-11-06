from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch

from asgi_client import TestClient
from robingraph.ingest.audio_collector import create_app,validate_target
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings


class CollectionOnlySidecarTests(TestCase):
    def setUp(self):
        self.audio=Mock()
        self.audio.require_internal_bearer.return_value=None
        self.client=TestClient(create_app(self.audio,'prod'))

    def test_health_explicitly_disables_publication_and_no_public_app_routes_exist(self):
        self.assertEqual({'status':'ok','service':'audio-collector','deployment_target':'prod','publication_enabled':False},self.client.get('/health').json())
        for route in ['/','/birds','/v1/taxa/profile','/media/audio/'+'a'*64+'.ogg','/internal/v1/audio/publish','/internal/v1/ingest/begin']:
            for method in ('get','post'):
                self.assertEqual(404,getattr(self.client,method)(route).status_code,route)
        self.audio.publish.assert_not_called()

    def test_collection_and_manual_review_keep_existing_bearer_boundary(self):
        self.audio.status.return_value={'candidate_id':'a'*64,'status':'awaiting_review'}
        response=self.client.post('/internal/v1/audio/status',json={'candidate_id':'a'*64},headers={'Authorization':'Bearer fixture'})
        self.assertEqual(200,response.status_code)
        self.audio.require_internal_bearer.assert_called_once_with('Bearer fixture')
        self.audio.status.assert_called_once_with(candidate_id='a'*64)
        self.assertEqual(422,self.client.post('/internal/v1/audio/review',json={'candidate_id':'a'*64}).status_code)
        self.audio.review.assert_not_called()

    def test_startup_opt_in_and_exact_prod_test_boundaries(self):
        with TemporaryDirectory() as directory:
            env={'ROBINGRAPH_DEPLOY_TARGET':'prod','ROBINGRAPH_AUDIO_COLLECTOR_ENABLED':'true',
                 'ROBINGRAPH_AUDIO_ROOT':directory,'ROBINGRAPH_INGEST_INTERNAL_TOKEN':'fixture'}
            pg=PostgresSettings('192.168.219.99',5433,'robingraph','ingest','fixture','fixture','prefer')
            neo=Neo4jSettings('bolt://neo4j:7687','fixture','fixture','neo4j')
            self.assertEqual('prod',validate_target(env,pg,neo))
            for change in ({'ROBINGRAPH_DEPLOY_TARGET':'legacy'},{'ROBINGRAPH_AUDIO_COLLECTOR_ENABLED':'false'},
                           {'ROBINGRAPH_AUDIO_ROOT':'relative'},{'ROBINGRAPH_INGEST_INTERNAL_TOKEN':''}):
                with self.assertRaises(ValueError):validate_target({**env,**change},pg,neo)
            with self.assertRaises(ValueError):validate_target(env,replace(pg,database='robingraph_test'),neo)
            with self.assertRaises(ValueError):validate_target(env,pg,replace(neo,uri='bolt://192.168.219.98:7687'))
            test={**env,'ROBINGRAPH_DEPLOY_TARGET':'test'}
            self.assertEqual('test',validate_target(test,replace(pg,database='robingraph_test'),replace(neo,uri='bolt://192.168.219.98:7687')))
            with self.assertRaises(ValueError):validate_target(test,pg,neo)
