"""Contract supplied by the user's API-USAGE.md; no live calls by default."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from robingraph.embeddings import EmbeddingConfigurationError, EmbeddingHTTPError, JinaEmbeddingClient, JinaEmbeddingSettings


class Response:
    def __init__(self, count):
        self.body = json.dumps({'model': 'jinaai/jina-embeddings-v3', 'data': [
            {'index': i, 'embedding': [1.0] + [0.0] * 511} for i in range(count)
        ]}).encode()

    def read(self, size):
        return self.body

    def close(self):
        pass


class BirdsNestContractTest(unittest.TestCase):
    def setUp(self):
        self.settings = JinaEmbeddingSettings('http://localhost/v1/embeddings', 'jina-embeddings-v3', 512,
                                               api_format='birdsnest', batch_size=64)

    def test_documented_fields_canonical_model_and_tasks(self):
        requests = []

        def transport(request, timeout):
            body = json.loads(request.data)
            requests.append(body)
            self.assertEqual('RobinGraph/0.1', request.get_header('User-agent'))
            self.assertNotIn('normalized', body)
            self.assertEqual('float', body['encoding_format'])
            self.assertEqual(1024, body['max_length'])
            return Response(len(body['input']))

        client = JinaEmbeddingClient(self.settings, urlopen=transport)
        self.assertEqual('jinaai/jina-embeddings-v3', client.profile.model)
        self.assertEqual(512, len(client.embed_query('물가 서식지')))
        self.assertEqual(2, len(client.embed_documents(['호수', '숲'])))
        self.assertEqual(['retrieval.query', 'retrieval.passage'], [row['task'] for row in requests])

    def test_all_inputs_are_preflighted_before_sending_and_batches_respect_total_characters(self):
        batches = []

        def transport(request, timeout):
            values = json.loads(request.data)['input']
            batches.append(values)
            return Response(len(values))

        client = JinaEmbeddingClient(self.settings, urlopen=transport)
        for invalid in ('', '  ', 'x' * 20001):
            with self.assertRaises(EmbeddingConfigurationError):
                client.embed_documents(['valid', invalid])
        self.assertEqual([], batches)
        client.embed_documents(['x' * 20000] * 11)
        self.assertEqual([10, 1], [len(batch) for batch in batches])
        self.assertTrue(all(sum(map(len, batch)) <= 200000 for batch in batches))

    def test_profile_and_service_limits_fail_before_http(self):
        for changes in ({'dimensions': 3}, {'normalized': False}, {'batch_size': 65},
                        {'max_length': 1025}, {'model': 'other-model'}):
            with self.subTest(changes=changes), self.assertRaises(EmbeddingConfigurationError):
                replace(self.settings, **changes)

    def test_birdsnest_environment_defaults(self):
        settings = JinaEmbeddingSettings.from_env({
            'ROBINGRAPH_JINA_ENDPOINT': 'http://localhost/v1/embeddings',
            'ROBINGRAPH_JINA_MODEL': 'jina-embeddings-v3', 'ROBINGRAPH_JINA_DIMENSIONS': '512',
            'ROBINGRAPH_JINA_API_FORMAT': 'birdsnest',
        })
        self.assertEqual(120, settings.timeout_seconds)
        self.assertEqual(2, settings.max_retries)

    def test_transient_errors_retry_but_authentication_errors_do_not(self):
        attempts = []

        def transient(request, timeout):
            attempts.append(1)
            if len(attempts) < 3:
                raise HTTPError('http://localhost', 503, 'unavailable', {}, None)
            return Response(1)

        with patch('robingraph.embeddings.time.sleep') as sleep:
            client = JinaEmbeddingClient(replace(self.settings, max_retries=2), urlopen=transient)
            client.embed_query('test')
        self.assertEqual(3, len(attempts))
        self.assertEqual([0.5, 1.0], [call.args[0] for call in sleep.call_args_list])

        attempts.clear()

        def rejected(request, timeout):
            attempts.append(1)
            raise HTTPError('http://localhost', 401, 'unauthorized', {}, None)

        with patch('robingraph.embeddings.time.sleep') as sleep:
            client = JinaEmbeddingClient(replace(self.settings, max_retries=2), urlopen=rejected)
            with self.assertRaises(EmbeddingHTTPError):
                client.embed_query('test')
        self.assertEqual(1, len(attempts))
        sleep.assert_not_called()

    def test_transient_retries_are_bounded(self):
        def rejected(request, timeout):
            raise HTTPError('http://localhost', 503, 'unavailable', {}, None)

        with patch('robingraph.embeddings.time.sleep') as sleep:
            client = JinaEmbeddingClient(replace(self.settings, max_retries=2), urlopen=rejected)
            with self.assertRaises(EmbeddingHTTPError):
                client.embed_query('test')
        self.assertEqual(2, sleep.call_count)


if __name__ == '__main__':
    unittest.main()
