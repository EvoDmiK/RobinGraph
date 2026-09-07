"""Real localhost HTTP round-trip; this is not a live Jina service test."""

from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Thread
import unittest

from robingraph.embeddings import (
    EmbeddingHTTPError, EmbeddingResponseError, JinaEmbeddingClient,
    JinaEmbeddingSettings, embed_fixture_chunks,
)
from robingraph.fixture import load_fixture


@contextmanager
def jina_stub(*, respond=None):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, self.headers.get('Authorization'), payload))
            response = respond(payload) if respond else {
                'model': payload['model'],
                'data': [
                    {'index': i, 'embedding': [1.0, 0.0, 0.0]}
                    for i in reversed(range(len(payload['input'])))
                ],
            }
            body = json.dumps(response).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        worker = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        worker.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}/v1/embeddings', requests
        finally:
            server.shutdown()
            worker.join(timeout=2)


class EmbeddingHTTPFlowTest(unittest.TestCase):
    def test_fixture_and_question_use_real_http_and_distinct_tasks(self):
        with jina_stub() as (endpoint, requests):
            settings = JinaEmbeddingSettings(endpoint, 'fixture-http-model', 3, api_key='test-only', batch_size=2)
            client = JinaEmbeddingClient(settings)
            embedded = embed_fixture_chunks(load_fixture(), client)
            query_vector = client.embed_query('호수의 물새')
        self.assertEqual(4, len(embedded))
        self.assertEqual((1.0, 0.0, 0.0), query_vector)
        self.assertEqual(['retrieval.passage', 'retrieval.passage', 'retrieval.query'],
                         [item[2]['task'] for item in requests])
        self.assertEqual('호수의 물새', requests[-1][2]['input'][0])
        self.assertTrue(all(path == '/v1/embeddings' and auth == 'Bearer test-only'
                            for path, auth, _ in requests))
        self.assertNotIn('test-only', repr(settings))

    def test_incompatible_model_zero_and_non_normalized_vectors_are_rejected(self):
        for response in (
            {'model': 'different-model', 'data': [{'index': 0, 'embedding': [1, 0, 0]}]},
            {'data': [{'index': 0, 'embedding': [0, 0, 0]}]},
            {'data': [{'index': 0, 'embedding': [1, 2, 3]}]},
            {'data': [{'index': 0, 'embedding': [True, 0, 0]}]},
        ):
            with self.subTest(response=response), jina_stub(respond=lambda _: response) as (endpoint, _):
                client = JinaEmbeddingClient(JinaEmbeddingSettings(endpoint, 'fixture-http-model', 3))
                with self.assertRaises(EmbeddingResponseError):
                    client.embed_query('test')

    def test_duplicate_indexes_are_rejected_even_when_response_count_matches(self):
        response = {'data': [{'index': 0, 'embedding': [1, 0, 0]}] * 2}
        with jina_stub(respond=lambda _: response) as (endpoint, _):
            client = JinaEmbeddingClient(JinaEmbeddingSettings(endpoint, 'fixture-http-model', 3))
            with self.assertRaisesRegex(EmbeddingResponseError, 'duplicate'):
                client.embed_documents(('first', 'second'))

    def test_malformed_permission_does_not_send_content(self):
        corpus = load_fixture()
        for value in ('false', 1, None):
            documents = tuple({**document, 'embedding_allowed': value} for document in corpus.documents)
            with self.subTest(value=value), jina_stub() as (endpoint, requests):
                client = JinaEmbeddingClient(JinaEmbeddingSettings(endpoint, 'fixture-http-model', 3))
                self.assertEqual((), embed_fixture_chunks(replace(corpus, documents=documents), client))
                self.assertEqual([], requests)

    def test_upstream_http_reason_is_not_exposed(self):
        from urllib.error import HTTPError

        def fail(*args, **kwargs):
            raise HTTPError('http://localhost', 401, 'echoed secret-token', {}, None)

        client = JinaEmbeddingClient(
            JinaEmbeddingSettings('http://localhost/v1/embeddings', 'fixture-http-model', 3), urlopen=fail
        )
        with self.assertRaises(EmbeddingHTTPError) as error:
            client.embed_query('test')
        self.assertEqual(401, error.exception.status)
        self.assertNotIn('secret-token', str(error.exception))


@unittest.skipUnless(os.getenv('ROBINGRAPH_NEO4J_INTEGRATION_TESTS') == '1', 'Opt in to run against disposable Neo4j')
class EmbeddingNeo4jFlowTest(unittest.TestCase):
    def test_http_embeddings_are_indexed_searched_and_cited_with_profile_isolation(self):
        from robingraph.graph.settings import Neo4jSettings
        from robingraph.graph.neo4j_client import bootstrap_schema, load_fixture as load_graph
        from robingraph.retrieval.neo4j_hybrid import (
            HybridSchemaConfig, HybridSearchRequest, bootstrap_hybrid_search_schema,
            index_chunks, search,
        )

        settings = Neo4jSettings.from_environment()
        corpus = load_fixture()
        bootstrap_schema(settings)
        load_graph(settings, corpus)
        config = HybridSchemaConfig()
        bootstrap_hybrid_search_schema(settings, dimensions=3, config=config)
        with jina_stub() as (endpoint, requests):
            client_settings = JinaEmbeddingSettings(endpoint, 'fixture-http-model', 3)
            client = JinaEmbeddingClient(client_settings)
            self.addCleanup(load_graph, settings, corpus)
            self.addCleanup(index_chunks, settings, (), expected_profile=client.profile, indexed_at='test-cleanup')
            report = index_chunks(settings, embed_fixture_chunks(corpus, client),
                                  expected_profile=client.profile, indexed_at='test-http-flow')
            self.assertEqual(4, len(report.indexed))
            outcome = search(settings, HybridSearchRequest('fixture', limit=4), query_embedder=client, config=config)
            self.assertEqual(4, len(outcome.results))
            self.assertTrue(all(set(hit.channels) == {'fulltext', 'vector'} for hit in outcome.results))
            self.assertTrue(all(hit.citation.source_url and hit.citation.license_name for hit in outcome.results))
            self.assertTrue(all(hit.citation.locator.startswith('section ') for hit in outcome.results))
            wrong_model = JinaEmbeddingClient(replace(client_settings, model='incompatible-fixture-model'))
            mismatched = search(settings, HybridSearchRequest('fixture'), query_embedder=wrong_model, config=config)
            self.assertTrue(all('vector' not in hit.channels for hit in mismatched.results))
            self.assertIn('retrieval.passage', [item[2]['task'] for item in requests])
            self.assertIn('retrieval.query', [item[2]['task'] for item in requests])


if __name__ == '__main__':
    unittest.main()
