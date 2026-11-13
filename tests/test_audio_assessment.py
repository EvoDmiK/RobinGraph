"""Assessment-only writes never approve or publish a recording (offline fixtures)."""
import copy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock

from asgi_client import TestClient
from robingraph.api.drf import create_django_app
from robingraph.api.services import ApiError
from robingraph.ingest.audio import AudioService
from robingraph.ingest.audio_collector import create_app
from robingraph.ingest.audio_store import AudioStore
import test_audio_review as review_fixture
from test_audio_review import ReviewStore


class AssessmentStore(ReviewStore):
    def save_assessment(self,cursor,candidate_id,assessment):
        row=self.rows[candidate_id]
        row['data']['assessment']=copy.deepcopy(assessment)
        row['updated_at']=max(datetime.now(timezone.utc),row['updated_at']+timedelta(microseconds=1))
        return row['updated_at']


class AudioAssessmentTests(TestCase):
    def setUp(self):
        review_fixture.AudioReviewTests.setUp(self)
        self.store=AssessmentStore()
        self.store.rows=copy.deepcopy(self.service.store.rows)
        self.service=AudioService(self.store,self.directory.name,self.graph,self.resolve,'collection-fixture',
                                  review_token='readonly-fixture',assessment_token='assessment-fixture')
        self.client=TestClient(create_django_app(audio_service=self.service))
        self.write_headers={'Authorization':'Bearer assessment-fixture'}
        self.url='/internal/v1/audio/assessment'

    def body(self,**changes):
        return {'candidate_id':self.key,'expected_updated_at':self.store.rows[self.key]['updated_at'].isoformat(),
                'reviewer':'Reviewer','playback':'normal','source':'checked','identification':'uploader_only',
                'decision':'candidate','note':'','identification_note':'',**changes}

    def test_token_capability_matrix_and_distinct_configuration(self):
        for headers in ({},self.headers,{'Authorization':'Bearer collection-fixture'}):
            self.assertEqual(401,self.client.post(self.url,json=self.body(),headers=headers).status_code)
        with self.assertRaises(ApiError) as malformed:
            self.service.require_assessment_bearer('Bearer 비밀')
        self.assertEqual(401,malformed.exception.status_code)
        self.assertFalse(self.client.get('/internal/v1/audio/candidates',headers=self.headers).json()['can_assess'])
        self.assertTrue(self.client.get('/internal/v1/audio/candidates',headers=self.write_headers).json()['can_assess'])
        self.assertEqual(200,self.client.head('/internal/v1/audio/preview/'+self.key,headers=self.write_headers).status_code)
        for action in ('status','targets','discover','stage','review','publish'):
            self.assertEqual(401,self.client.post('/internal/v1/audio/'+action,json={},headers=self.write_headers).status_code)
        for review,assessment in (('collection-fixture','other'),('reader','collection-fixture'),('same','same')):
            with self.assertRaises(ValueError):
                AudioService(self.store,self.directory.name,self.graph,self.resolve,'collection-fixture',
                             review_token=review,assessment_token=assessment)
        self.service.assessment_token=None
        self.assertEqual(401,self.client.post(self.url,json=self.body(),headers=self.write_headers).status_code)
        self.assertFalse(self.client.get('/internal/v1/audio/candidates',headers=self.headers).json()['can_assess'])

    def test_assessment_update_preserves_raw_record_legacy_review_status_and_publication_gate(self):
        row=self.store.rows[self.key]
        row['data']['review']={'approved':False,'taxon_verified':False,'playback_verified':False,'reviewer':'original'}
        before=copy.deepcopy(row)
        self.assertIsNone(self.client.get('/internal/v1/audio/candidates',headers=self.headers).json()['items'][0]['assessment'])
        body=self.body(note='<img src=x onerror=alert(1)>',identification='additional_evidence',
                       identification_note='Observed field marks; corroboration needed')
        response=self.client.post(self.url,json=body,headers=self.write_headers)
        self.assertEqual(200,response.status_code)
        result=response.json();self.assertNotEqual(body['expected_updated_at'],result['updated_at'])
        assessment=result['assessment'];self.assertEqual(body['note'],assessment['note'])
        self.assertIsNotNone(datetime.fromisoformat(assessment['assessed_at']).utcoffset())
        for key,value in before.items():
            if key not in ('data','updated_at'):self.assertEqual(value,row[key])
        self.assertEqual(before['data'],{key:value for key,value in row['data'].items() if key!='assessment'})
        listed=self.client.get('/internal/v1/audio/candidates',headers=self.headers).json()['items'][0]
        self.assertEqual(assessment,listed['assessment']);self.assertEqual(result['updated_at'],listed['updated_at'])
        row['data']['assessment']['private_extra']='hidden'
        self.assertNotIn('private_extra',self.client.get('/internal/v1/audio/candidates',headers=self.headers).text)
        self.assertEqual(404,self.client.get('/media/audio/'+self.name).status_code)
        self.assertEqual(409,self.client.post('/internal/v1/audio/publish',json={'candidate_id':self.key},
                                            headers={'Authorization':'Bearer collection-fixture'}).status_code)
        self.graph._run.assert_not_called();self.resolve.assert_not_called()

    def test_optimistic_conflict_rejects_stale_editor_then_allows_explicit_latest_update(self):
        stale=self.body()
        first=self.client.post(self.url,json=stale,headers=self.write_headers)
        self.assertEqual(200,first.status_code)
        saved=copy.deepcopy(self.store.rows[self.key])
        conflict=self.client.post(self.url,json={**stale,'note':'second editor'},headers=self.write_headers)
        self.assertEqual(409,conflict.status_code);self.assertEqual(saved,self.store.rows[self.key])
        retry=self.client.post(self.url,json=self.body(note='reloaded edit'),headers=self.write_headers)
        self.assertEqual(200,retry.status_code);self.assertEqual('reloaded edit',retry.json()['assessment']['note'])
        self.assertNotEqual(first.json()['updated_at'],retry.json()['updated_at'])

    def test_body_time_text_enums_and_additional_evidence_validation_are_atomic(self):
        original=copy.deepcopy(self.store.rows)
        invalid=[{**self.body(),'unknown':'value'},self.body(expected_updated_at=None),
                 self.body(expected_updated_at='2026-11-09T00:00:00'),self.body(expected_updated_at='garbage'),
                 self.body(reviewer=' '),self.body(reviewer='x'*121),self.body(note='x'*2001),
                 self.body(identification_note='x'*1001),self.body(note=None),
                 self.body(identification='additional_evidence',identification_note=' \n'),
                 self.body(playback=True),self.body(source=['checked']),self.body(decision='publish'),
                 self.body(candidate_id='invalid')]
        for field in self.body():
            value=self.body();value.pop(field);invalid.append(value)
        for body in invalid:
            self.assertEqual(422,self.client.post(self.url,json=body,headers=self.write_headers).status_code)
            self.assertEqual(original,self.store.rows)
        missing=self.client.post(self.url,json=self.body(candidate_id='f'*64),headers=self.write_headers)
        self.assertEqual(404,missing.status_code)

    def test_secret_values_are_rejected_without_storage_or_reflection(self):
        before=copy.deepcopy(self.store.rows)
        for field in ('reviewer','note','identification_note'):
            for secret in ('collection-fixture','readonly-fixture','assessment-fixture'):
                response=self.client.post(self.url,json=self.body(**{field:'prefix '+secret+' suffix'}),headers=self.write_headers)
                self.assertEqual(422,response.status_code);self.assertNotIn(secret,response.text)
                self.assertEqual(before,self.store.rows)

    def test_every_choice_allows_notes_without_file_or_any_candidate_state_transition(self):
        # A reviewer can record a failed/missing file or defer judgment without approving it.
        for index,(playback,source,identification,decision,status) in enumerate(zip(
                ('unchecked','normal','silent','file_error'),('unchecked','checked','checked','unchecked'),
                ('unchecked','uploader_only','additional_evidence','uncertain'),
                ('pending','hold','candidate','exclude'),('deferred','awaiting_review','rejected','approved'))):
            row=self.store.rows[self.key];row['status']=status;row['data'].pop('file_name',None)
            result=self.client.post(self.url,json=self.body(playback=playback,source=source,identification=identification,
                decision=decision,identification_note='Explicit evidence' if identification=='additional_evidence' else ''),headers=self.write_headers)
            self.assertEqual(200,result.status_code);self.assertEqual(status,row['status']);self.assertNotIn('review',row['data'])
        self.graph._run.assert_not_called();self.resolve.assert_not_called()

    def test_collector_assessment_is_separate_from_publication_and_timestamp_offsets_compare(self):
        client=TestClient(create_app(self.service,'test'))
        expected=self.store.rows[self.key]['updated_at'].astimezone(timezone(timedelta(hours=9))).isoformat()
        response=client.post(self.url,json=self.body(expected_updated_at=expected),headers=self.write_headers)
        self.assertEqual(200,response.status_code)
        self.assertEqual(404,client.post('/internal/v1/audio/publish',json={},headers=self.write_headers).status_code)
        self.assertFalse(client.get('/health').json()['publication_enabled'])

    def test_store_locks_then_updates_only_assessment_json_with_returning_timestamp(self):
        cursor=Mock();updated=datetime.now(timezone.utc);cursor.fetchone.return_value={'updated_at':updated}
        payload={'note':'plain'}
        self.assertEqual(updated,AudioStore.save_assessment(cursor,self.key,payload))
        query,params=cursor.execute.call_args.args
        self.assertIn("data=jsonb_set(data,'{assessment}',%s)",query)
        self.assertIn('RETURNING updated_at',query);self.assertNotIn('status=',query)
        self.assertEqual(self.key,params[1]);self.assertEqual(payload,params[0].obj)
        AudioStore.get(cursor,self.key)
        self.assertIn('FOR UPDATE',cursor.execute.call_args.args[0])
