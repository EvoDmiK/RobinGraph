"""Request-scoped identity and candidate confirmation API contracts (offline)."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from asgi_client import TestClient

from robingraph.api.drf import create_django_app
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent


PROFILE = {
    'taxon': {'taxon_id': 'duck', 'scientific_name': 'Anas zonorhyncha', 'rank': 'species',
              'korean_name': '흰뺨검둥오리'},
    'lineage': {'concept_set_id': 'active', 'taxonomy_release': 'v2025b'},
    'summary': '확인된 종 소개', 'traits': [], 'warnings': [],
}


def matched(mention='흰뺨검둥오리', method='graph_exact'):
    return dict(mention=mention, status='matched', method=method, taxon_id='duck',
                canonical_name='Anas zonorhyncha', concept_set_id='active',
                taxonomy_release='v2025b', candidates=[])


class EntityResolutionApiTests(unittest.TestCase):
    def client(self, response, profile=PROFILE):
        resolver = Mock(return_value=response)
        reader = Mock(return_value=deepcopy(profile))
        return TestClient(create_django_app(species_profile_handler=reader,
                                     taxon_name_resolution_handler=resolver)), resolver, reader

    def test_graph_identity_is_request_metadata_and_controls_profile_lookup(self):
        client, resolver, reader = self.client(matched())
        body = client.post('/v1/chat', json={'question': '흰뺨검둥오리에 대해 알고 싶어'}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertEqual('duck', body['entity_resolution']['taxon_id'])
        self.assertEqual('흰뺨검둥오리', body['entity_resolution']['mention'])
        resolver.assert_called_once_with('흰뺨검둥오리')
        reader.assert_called_once_with('Anas zonorhyncha')

    def test_vector_candidates_clarify_and_preserve_question_topic(self):
        response = dict(mention='흰뺨검둥오려', status='candidates', method='vector',
                        candidates=[dict(taxon_id='duck', scientific_name='Anas zonorhyncha',
                                         display_name='흰뺨검둥오리', score=.91)])
        client, resolver, reader = self.client(response)
        body = client.post('/v1/chat', json={'question': '흰뺨검둥오려는 뭘 먹어?'}).json()
        self.assertEqual('clarify', body['disposition'])
        self.assertEqual('clarify', body['result']['kind'])
        self.assertEqual('Anas zonorhyncha는 뭘 먹어?', body['entity_resolution']['candidates'][0]['question'])
        reader.assert_not_called()
        resolver.assert_called_once_with('흰뺨검둥오려')

    def test_candidate_confirmation_rechecks_scientific_name(self):
        client, resolver, reader = self.client(matched('Anas zonorhyncha'))
        body = client.post('/v1/chat', json={'question': 'Anas zonorhyncha에 대해 알려줘'}).json()
        self.assertEqual('answer', body['disposition'])
        resolver.assert_called_once_with('Anas zonorhyncha')
        reader.assert_called_once_with('Anas zonorhyncha')

    def test_changed_profile_id_or_release_fails_closed(self):
        for key in ('taxon_id', 'concept_set_id', 'taxonomy_release'):
            profile = deepcopy(PROFILE)
            profile['taxon' if key == 'taxon_id' else 'lineage'][key] = 'changed'
            client, _, _ = self.client(matched(), profile)
            body = client.post('/v1/chat', json={'question': '흰뺨검둥오리에 대해 알려줘'}).json()
            self.assertEqual('abstain', body['disposition'])
            self.assertIsNone(body['result']['profile'])

    def test_outage_and_invalid_resolver_output_never_guess_or_leak(self):
        for response in (dict(mention='다른이름', status='matched', method='graph_exact'),
                         dict(mention='흰뺨검둥오리', status='candidates', method='vector', candidates=[])):
            client, _, reader = self.client(response)
            body = client.post('/v1/chat', json={'question': '흰뺨검둥오리에 대해 알려줘'}).json()
            self.assertEqual('abstain', body['disposition'])
            reader.assert_not_called()
        client, resolver, reader = self.client(None)
        resolver.side_effect = RuntimeError('private provider details')
        response = client.post('/v1/chat', json={'question': '흰뺨검둥오리에 대해 알려줘'})
        self.assertNotIn('private provider', response.text)
        reader.assert_not_called()

    def test_vector_service_unavailable_is_explicit_and_does_not_call_profile(self):
        client, _, reader = self.client(dict(mention='흰뺨검둥오려', status='unavailable', method='none'))
        body = client.post('/v1/chat', json={'question': '흰뺨검둥오려에 대해 알려줘'}).json()
        self.assertEqual('abstain', body['disposition'])
        self.assertEqual('unavailable', body['entity_resolution']['status'])
        reader.assert_not_called()

    def test_invalid_identity_never_reaches_profile_or_graph_lookup(self):
        name = '흰뺨검둥오리'
        invalid = [dict(matched(), **{field: None}) for field in
                   ('canonical_name', 'taxon_id', 'concept_set_id', 'taxonomy_release')]
        invalid += [matched('다른새'), matched(method='vector'),
                    dict(mention=name, status='candidates', method='vector', candidates=[]),
                    dict(mention=name, status='candidates', method='graph_exact', candidates=[
                        dict(taxon_id='duck', scientific_name='Anas zonorhyncha', score=.91)])]
        for question, disposition in ((name + '에 대해 알려줘', 'abstain'),
                (name + '와 서식지가 겹치면서 먹이가 다른 새는?', 'clarify')):
            for raw in invalid:
                with self.subTest(question=question, resolution=raw):
                    reader, graph, resolver = Mock(), Mock(), Mock(return_value=raw)
                    client = TestClient(create_django_app(species_profile_handler=reader,
                        graph_question_handler=graph, taxon_name_resolution_handler=resolver,
                        graph_intent_mode='active', graph_intent_handler=extract_graph_intent))
                    response = client.post('/v1/chat', json={'question': question, 'species_scope': 'korea'})
                    self.assertEqual(200, response.status_code)
                    self.assertEqual(disposition, response.json()['disposition'])
                    resolver.assert_called_once_with(name, species_scope='korea')
                    reader.assert_not_called()
                    graph.assert_not_called()

    def test_explicit_evidence_does_not_attempt_taxon_resolution(self):
        client, resolver, _ = self.client(None)
        client.post('/v1/chat', json={'question': '흰뺨검둥오리 문헌', 'intent': 'evidence'})
        resolver.assert_not_called()

    def test_legacy_handler_without_resolver_remains_usable(self):
        client = TestClient(create_django_app(species_profile_handler=lambda _: PROFILE))
        body = client.post('/v1/chat', json={'question': '흰뺨검둥오리에 대해 알려줘'}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertIsNone(body['entity_resolution'])

    def test_whole_question_without_entity_is_not_embedded(self):
        client, resolver, reader = self.client(None)
        body = client.post('/v1/chat', json={'question': '알려줘', 'intent': 'profile'}).json()
        self.assertEqual('clarify', body['disposition'])
        resolver.assert_not_called()
        reader.assert_not_called()

    def test_bare_explicit_korean_name_can_still_be_resolved(self):
        client, resolver, reader = self.client(matched())
        body = client.post('/v1/chat', json={'question': '흰뺨검둥오리', 'intent': 'profile'}).json()
        self.assertEqual('answer', body['disposition'])
        resolver.assert_called_once_with('흰뺨검둥오리')

    def test_confirmed_subspecies_keeps_its_own_identity(self):
        science = 'Anas platyrhynchos conboschas'
        profile = deepcopy(PROFILE)
        profile['taxon'].update(taxon_id='subspecies', scientific_name=science, rank='subspecies')
        resolution = matched(science)
        resolution.update(taxon_id='subspecies', canonical_name=science)
        client, _, reader = self.client(resolution, profile)
        body = client.post('/v1/chat', json={'question': science + '에 대해 알려줘'}).json()
        self.assertEqual('answer', body['disposition'])
        self.assertEqual('subspecies', body['entity_resolution']['taxon_id'])
        reader.assert_called_once_with(science)
