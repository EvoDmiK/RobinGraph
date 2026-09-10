"""CLI integration boundaries: explicit model calls, provenance, and failures."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest
from unittest.mock import patch

from robingraph.cli import main
from robingraph.embeddings import EmbeddingHTTPError
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.hybrid import HybridResult, HybridSearchOutcome
from robingraph.retrieval.repository import SourceCitation


class SearchCLITest(unittest.TestCase):
    def setUp(self):
        settings = Neo4jSettings('bolt://localhost:7687', 'neo4j', 'test-only', 'neo4j')
        self.settings = patch('robingraph.cli.Neo4jSettings.from_environment', return_value=settings)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.environment = patch('robingraph.cli.load_local_environment')
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def invoke(self, *args):
        out, err = StringIO(), StringIO()
        with patch('sys.argv', ['robingraph', *args]), redirect_stdout(out), redirect_stderr(err):
            code = main()
        return code, out.getvalue(), err.getvalue()

    def test_default_index_creates_only_keyword_schema_without_jina_configuration(self):
        with patch('robingraph.embeddings.JinaEmbeddingClient.from_env') as client, \
             patch('robingraph.retrieval.neo4j_hybrid.bootstrap_hybrid_search_schema') as schema, \
             patch('robingraph.retrieval.neo4j_hybrid.index_chunks') as index:
            code, out, err = self.invoke('index-neo4j-fixture')
        self.assertEqual((0, ''), (code, err))
        self.assertEqual('fulltext', json.loads(out)['mode'])
        self.assertIsNone(schema.call_args.kwargs['dimensions'])
        client.assert_not_called()
        index.assert_not_called()

    def test_keyword_search_preserves_citation_without_jina_calls(self):
        citation = SourceCitation('source', 'https://example.invalid/source', 'section 2', 'test license')
        outcome = HybridSearchOutcome((HybridResult('chunk-1', 'text', 0.01, ('fulltext',), citation),), ())
        with patch('robingraph.embeddings.JinaEmbeddingClient.from_env') as client, \
             patch('robingraph.retrieval.neo4j_hybrid.search', return_value=outcome) as search:
            code, out, err = self.invoke('search-neo4j', '--question', 'test')
        client.assert_not_called()
        self.assertIsNone(search.call_args.kwargs['query_embedder'])
        self.assertEqual((0, ''), (code, err))
        self.assertEqual('section 2', json.loads(out)['results'][0]['citation']['locator'])

    def test_explicit_hybrid_requires_valid_configuration(self):
        with patch.dict('os.environ', {}, clear=True), \
             patch('robingraph.retrieval.neo4j_hybrid.search') as search:
            code, out, err = self.invoke('search-neo4j', '--question', 'test', '--hybrid')
        self.assertEqual(1, code)
        self.assertEqual('', out)
        self.assertIn('ROBINGRAPH_JINA_ENDPOINT', err)
        search.assert_not_called()

    def test_provider_error_falls_back_with_warning_and_no_fake_vector(self):
        with patch('robingraph.embeddings.JinaEmbeddingClient.from_env'), \
             patch('robingraph.retrieval.neo4j_hybrid.search', side_effect=[
                 EmbeddingHTTPError(503), HybridSearchOutcome((), ())
             ]) as search:
            code, out, err = self.invoke('search-neo4j', '--question', 'test', '--hybrid')
        self.assertEqual((0, ''), (code, err))
        self.assertEqual(2, search.call_count)
        self.assertEqual({}, search.call_args.kwargs)
        self.assertIn('keyword-only', json.loads(out)['warnings'][0])

    def test_invalid_limit_is_rejected_before_search(self):
        with patch('robingraph.retrieval.neo4j_hybrid.search') as search:
            with self.assertRaises(SystemExit) as error:
                self.invoke('search-neo4j', '--question', 'test', '--limit', '101')
        self.assertEqual(2, error.exception.code)
        search.assert_not_called()

    def test_serve_neo4j_wires_and_closes_operational_observation_repository(self):
        with patch("robingraph.retrieval.neo4j_repository.Neo4jGraphRepository") as fixture_type, \
             patch(
                 "robingraph.retrieval.operational_neo4j.Neo4jOperationalObservationRepository"
             ) as operational_type, \
             patch("uvicorn.run") as run:
            code, out, err = self.invoke("serve-neo4j")
        self.assertEqual((0, "", ""), (code, out, err))
        app = run.call_args.args[0]
        self.assertIn("/v1/observations", app.openapi()["paths"])
        fixture_type.return_value.close.assert_called_once_with()
        operational_type.return_value.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
