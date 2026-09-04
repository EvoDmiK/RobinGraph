"""Tests for `robingraph.retrieval.neo4j_hybrid`.

`Neo4jHybridSchemaAndValidationTest` / `LuceneEscapingTest` run offline: the
validation in `index_chunks`/`bootstrap_hybrid_search_schema` is checked
*before* either function opens a Neo4j driver connection, so these run
without a live server or valid connection settings.

`Neo4jHybridSearchIntegrationTest` is opt-in against a real Neo4j server,
using the same `ROBINGRAPH_NEO4J_INTEGRATION_TESTS` convention as
`tests/test_neo4j_integration.py`: skipped unless
`ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1`, and a failure (not a skip) in
`setUpClass` if that flag is set but `NEO4J_URI`/`NEO4J_USERNAME`/
`NEO4J_PASSWORD`/`NEO4J_DATABASE` are missing or invalid. It never calls a
real embedding HTTP client -- `_FakeEmbeddedChunk`/`_FakeQueryEmbedder` are
deterministic, offline stand-ins that satisfy `EmbeddedChunkLike`/
`QueryEmbedderLike` structurally, exactly as a real
`robingraph.embeddings.EmbeddedChunk`/`EmbeddingClient` would.

    export ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1
    export NEO4J_URI=bolt://localhost:7687
    export NEO4J_USERNAME=neo4j
    export NEO4J_PASSWORD=<password>
    export NEO4J_DATABASE=neo4j
    uv run --locked --extra test python -m unittest tests.test_neo4j_hybrid -v
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
import unittest

from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, VECTOR_UNAVAILABLE_WARNING
from robingraph.retrieval.neo4j_hybrid import (
    ChunkIndexReport,
    HybridSchemaConfig,
    HybridSearchRequest,
    bootstrap_hybrid_search_schema,
    escape_lucene_query_text,
    index_chunks,
    validate_embedded_chunks,
)


# -- structural stand-ins for the shared embeddings contract (see module docstring) --


@dataclass(frozen=True)
class _FakeProfile:
    model: str
    dimensions: int
    normalized: bool


@dataclass(frozen=True)
class _FakeEmbeddedChunk:
    chunk_id: str
    content_hash: str
    vector: tuple[float, ...]
    profile: _FakeProfile


def _deterministic_vector(text: str, dimensions: int) -> tuple[float, ...]:
    """A reproducible, non-semantic, L2-normalized stand-in vector -- not a real embedding.

    Only used to exercise the indexing/search plumbing (Cypher, RRF, policy
    recheck) against a real Neo4j vector index; it says nothing about actual
    semantic similarity. Normalized because `_FakeProfile.normalized=True` in
    every test that uses this, and `validate_embedded_chunks` now checks that.
    """

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # +1 avoids an all-zero component (and, in the pathological case where
    # every byte were 0, an all-zero/unnormalizable vector).
    raw = tuple((digest[i % len(digest)] / 255.0) + 1.0 for i in range(dimensions))
    norm = math.hypot(*raw)
    return tuple(value / norm for value in raw)


class _FakeQueryEmbedder:
    def __init__(self, profile: _FakeProfile) -> None:
        self.profile = profile

    def embed_query(self, text: str) -> tuple[float, ...]:
        return _deterministic_vector(text, self.profile.dimensions)


class LuceneEscapingTest(unittest.TestCase):
    def test_escapes_every_reserved_character(self) -> None:
        raw = '+-&&||!(){}[]^"~*?:\\/'
        escaped = escape_lucene_query_text(raw)
        for character in set(raw):
            self.assertIn(f"\\{character}", escaped)

    def test_leaves_plain_korean_text_unescaped(self) -> None:
        text = "fixture 호수에서 흰뺨검둥오리 관찰"
        self.assertEqual(text, escape_lucene_query_text(text))

    def test_escapes_a_question_mark_common_in_korean_questions(self) -> None:
        self.assertEqual("관찰됐나\\?", escape_lucene_query_text("관찰됐나?"))


class IndexChunksValidationTest(unittest.TestCase):
    """These never open a Neo4j driver: validation runs before any connection."""

    _BOGUS_SETTINGS = Neo4jSettings(uri="bolt://unresolvable.invalid:7687", username="x", password="y", database="neo4j")

    def test_rejects_a_chunk_whose_profile_does_not_match_the_expected_profile(self) -> None:
        expected = _FakeProfile(model="text-a", dimensions=4, normalized=True)
        mismatched = _FakeEmbeddedChunk(
            chunk_id="c1", content_hash="h1", vector=(0.1, 0.2, 0.3, 0.4), profile=_FakeProfile("text-b", 4, True)
        )
        with self.assertRaises(ValueError):
            index_chunks(self._BOGUS_SETTINGS, [mismatched], expected_profile=expected, indexed_at="2026-09-04T00:00:00Z")

    def test_rejects_a_vector_whose_length_does_not_match_its_declared_dimensions(self) -> None:
        profile = _FakeProfile(model="text-a", dimensions=4, normalized=True)
        bad_length = _FakeEmbeddedChunk(chunk_id="c1", content_hash="h1", vector=(0.1, 0.2, 0.3), profile=profile)
        with self.assertRaises(ValueError):
            index_chunks(self._BOGUS_SETTINGS, [bad_length], expected_profile=profile, indexed_at="2026-09-04T00:00:00Z")

    def test_bootstrap_rejects_non_positive_dimensions_before_connecting(self) -> None:
        with self.assertRaises(ValueError):
            bootstrap_hybrid_search_schema(self._BOGUS_SETTINGS, dimensions=0)


class HybridSchemaConfigTest(unittest.TestCase):
    def test_defaults_name_the_dedicated_fixture_search_indexes(self) -> None:
        config = HybridSchemaConfig()
        self.assertEqual("robingraphFixtureChunkFulltext", config.fulltext_index_name)
        self.assertEqual("robingraphFixtureChunkVector", config.vector_index_name)
        self.assertEqual("cosine", config.similarity_function)


class RealEmbeddingContractInteropTest(unittest.TestCase):
    """Proves `robingraph.embeddings`'s real dataclasses satisfy this module's
    structural `EmbeddedChunkLike`/`EmbeddingProfileLike` Protocols without
    this module importing that package -- i.e. the decoupling described in
    neo4j_hybrid.py's module docstring does not silently drift from the
    actual shared contract now that `robingraph.embeddings` exists. Uses the
    pure `validate_embedded_chunks` precondition check directly, so this
    stays a fast offline test with no driver/network connection attempted.
    """

    def test_a_real_embeddedchunk_passes_validation_unchanged(self) -> None:
        from robingraph.embeddings import EmbeddedChunk, EmbeddingProfile

        profile = EmbeddingProfile(model="jina-embeddings-v4", dimensions=4, normalized=True)
        real_chunk = EmbeddedChunk(
            chunk_id="fixture-chunk-waterbirds-1", content_hash="h", vector=(0.5, 0.5, 0.5, 0.5), profile=profile
        )
        validate_embedded_chunks([real_chunk], expected_profile=profile)  # must not raise

    def test_a_real_embeddedchunk_with_a_mismatched_profile_is_still_rejected(self) -> None:
        from robingraph.embeddings import EmbeddedChunk, EmbeddingProfile

        indexed_profile = EmbeddingProfile(model="jina-embeddings-v4", dimensions=4, normalized=True)
        stale_chunk = EmbeddedChunk(
            chunk_id="fixture-chunk-waterbirds-1",
            content_hash="h",
            vector=(0.5, 0.5, 0.5, 0.5),
            profile=EmbeddingProfile(model="jina-embeddings-v3", dimensions=4, normalized=True),
        )
        with self.assertRaises(ValueError):
            validate_embedded_chunks([stale_chunk], expected_profile=indexed_profile)


def _integration_opt_in() -> bool:
    return os.getenv("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(
    _integration_opt_in(),
    "Set ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 (with NEO4J_URI/USERNAME/PASSWORD/DATABASE) to run against a real Neo4j server.",
)
class Neo4jHybridSearchIntegrationTest(unittest.TestCase):
    """Opt-in: writes are confined to :RobinGraph:Fixture chunk nodes plus the
    dedicated HybridSearchChunk/HybridVectorChunk labels and hybrid_* properties
    added by this module -- never to any node outside that scope. Restores the
    committed fixture (a plain reload) in tearDownClass.
    """

    PROFILE = _FakeProfile(model="fixture-test-embedder-v1", dimensions=3, normalized=True)

    @classmethod
    def setUpClass(cls) -> None:
        from robingraph.fixture import default_fixture_root, load_fixture
        from robingraph.graph.neo4j_client import bootstrap_schema, load_fixture as load_neo4j_fixture_graph

        # Explicit opt-in: a missing/malformed connection config must fail
        # loudly here, not skip -- same rule as test_neo4j_integration.py.
        cls.settings = Neo4jSettings.from_environment()
        cls.root = default_fixture_root()
        cls.corpus = load_fixture(cls.root)
        bootstrap_schema(cls.settings)
        load_neo4j_fixture_graph(cls.settings, cls.corpus)
        bootstrap_hybrid_search_schema(cls.settings, dimensions=cls.PROFILE.dimensions)

    @classmethod
    def tearDownClass(cls) -> None:
        from robingraph.fixture import load_fixture
        from robingraph.graph.neo4j_client import load_fixture as load_neo4j_fixture_graph

        # Restore the committed fixture graph so a full test run leaves the
        # disposable database as it found it (matches test_neo4j_integration.py).
        load_neo4j_fixture_graph(cls.settings, load_fixture(cls.root))

    def _embed_allowed_chunks(self) -> tuple[_FakeEmbeddedChunk, ...]:
        return tuple(
            _FakeEmbeddedChunk(
                chunk_id=chunk["chunk_id"],
                content_hash=chunk["content_hash"],
                vector=_deterministic_vector(chunk["text"], self.PROFILE.dimensions),
                profile=self.PROFILE,
            )
            for chunk in self.corpus.chunks
        )

    def test_bootstrap_with_dimensions_none_creates_only_the_fulltext_index(self) -> None:
        # The CLI's default (no --embeddings/--hybrid) path calls
        # bootstrap_hybrid_search_schema(settings, dimensions=None); this
        # must never attempt to create a vector index in that mode.
        from neo4j import GraphDatabase

        from robingraph.graph.neo4j_client import bootstrap_schema

        config = HybridSchemaConfig(
            fulltext_index_name="robingraphFixtureChunkFulltext",
            vector_index_name="robingraphFixtureChunkVectorKeywordOnly",
        )
        bootstrap_schema(self.settings)
        bootstrap_hybrid_search_schema(self.settings, dimensions=None, config=config)

        with GraphDatabase.driver(self.settings.uri, auth=(self.settings.username, self.settings.password)) as driver:
            with driver.session(database=self.settings.database) as session:
                vector_rows = session.run(
                    "SHOW VECTOR INDEXES YIELD name WHERE name = $name RETURN name", name=config.vector_index_name
                ).data()
                self.assertEqual([], vector_rows)
                fulltext_rows = session.run(
                    "SHOW FULLTEXT INDEXES YIELD name WHERE name = $name RETURN name", name=config.fulltext_index_name
                ).data()
                self.assertEqual(1, len(fulltext_rows))

    def test_index_chunks_indexes_every_allowed_chunk_and_reports_none_skipped(self) -> None:
        report = index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:00:00Z"
        )
        self.assertIsInstance(report, ChunkIndexReport)
        self.assertEqual(4, len(report.indexed))
        self.assertEqual((), report.skipped)

    def test_equivalent_schema_under_another_name_fails_explicitly(self) -> None:
        config = HybridSchemaConfig(fulltext_index_name="robingraphFixtureConflictingFulltext")
        with self.assertRaisesRegex(ValueError, "equivalent schema"):
            bootstrap_hybrid_search_schema(self.settings, dimensions=None, config=config)

    def test_reload_revokes_embeddings_and_rejects_a_stale_embedding_batch(self) -> None:
        from dataclasses import replace
        from neo4j import GraphDatabase
        from robingraph.graph.neo4j_client import load_fixture as load_graph

        original = self._embed_allowed_chunks()
        index_chunks(self.settings, original, expected_profile=self.PROFILE, indexed_at="test-before-revoke")
        document_id = self.corpus.documents[0]['document_id']
        target_ids = {chunk['chunk_id'] for chunk in self.corpus.chunks if chunk['document_id'] == document_id}
        documents = tuple({**doc, 'embedding_allowed': False} if doc['document_id'] == document_id else doc
                          for doc in self.corpus.documents)
        self.addCleanup(load_graph, self.settings, self.corpus)
        load_graph(self.settings, replace(self.corpus, documents=documents))

        def remaining_vector_ids():
            with GraphDatabase.driver(self.settings.uri, auth=(self.settings.username, self.settings.password)) as driver:
                records, _, _ = driver.execute_query(
                    'MATCH (c:Chunk:RobinGraph:Fixture) WHERE c.id IN $ids AND c.hybrid_vector IS NOT NULL RETURN c.id AS id',
                    ids=list(target_ids), database_=self.settings.database,
                )
                return {row['id'] for row in records}

        self.assertEqual(set(), remaining_vector_ids())
        report = index_chunks(self.settings, original, expected_profile=self.PROFILE, indexed_at="test-stale-batch")
        self.assertEqual(target_ids, set(report.skipped))
        self.assertEqual(set(), remaining_vector_ids())
        load_graph(self.settings, self.corpus)
        # Re-enabling permission must not resurrect vectors retained from before revocation.
        self.assertEqual(set(), remaining_vector_ids())

    def test_reload_changed_text_hash_invalidates_vector_before_reindex(self) -> None:
        from dataclasses import replace
        import hashlib
        from robingraph.graph.neo4j_client import load_fixture as load_graph
        from robingraph.retrieval.neo4j_hybrid import search

        original = self._embed_allowed_chunks()
        index_chunks(self.settings, original, expected_profile=self.PROFILE, indexed_at="test-before-change")
        target = self.corpus.chunks[0]
        text = target['text'] + ' changed evidence'
        chunks = tuple({**chunk, 'text': text, 'content_hash': hashlib.sha256(text.encode('utf-8')).hexdigest()}
                       if chunk['chunk_id'] == target['chunk_id'] else chunk for chunk in self.corpus.chunks)
        self.addCleanup(load_graph, self.settings, self.corpus)
        load_graph(self.settings, replace(self.corpus, chunks=chunks))
        outcome = search(self.settings, HybridSearchRequest('fixture'), query_embedder=_FakeQueryEmbedder(self.PROFILE))
        self.assertNotIn(target['chunk_id'], {hit.chunk_id for hit in outcome.results if VECTOR_CHANNEL in hit.channels})
        report = index_chunks(self.settings, original, expected_profile=self.PROFILE, indexed_at="test-stale-hash")
        self.assertIn(target['chunk_id'], report.skipped)

    def test_fulltext_only_search_returns_bounded_ranked_results_with_real_citation(self) -> None:
        index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:00:00Z"
        )
        from robingraph.retrieval.neo4j_hybrid import search

        outcome = search(self.settings, HybridSearchRequest(query_text="흰뺨검둥오리", limit=2))
        self.assertTrue(outcome.results)
        self.assertLessEqual(len(outcome.results), 2)
        top = outcome.results[0]
        self.assertEqual("fixture-chunk-waterbirds-1", top.chunk_id)
        self.assertEqual((FULLTEXT_CHANNEL,), top.channels)
        self.assertTrue(top.citation.source_url)
        self.assertNotEqual("unknown", top.citation.license_name)
        self.assertTrue(any(VECTOR_UNAVAILABLE_WARNING in warning for warning in outcome.warnings))

    def test_hybrid_search_with_a_query_embedder_adds_the_vector_channel(self) -> None:
        index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:00:00Z"
        )
        from robingraph.retrieval.neo4j_hybrid import search

        embedder = _FakeQueryEmbedder(self.PROFILE)
        outcome = search(self.settings, HybridSearchRequest(query_text="fixture 호수", limit=4), query_embedder=embedder)
        self.assertTrue(outcome.results)
        self.assertFalse(any(VECTOR_UNAVAILABLE_WARNING in warning for warning in outcome.warnings))
        self.assertTrue(any(VECTOR_CHANNEL in result.channels for result in outcome.results))

    def test_reindexing_after_a_content_change_invalidates_the_stale_vector(self) -> None:
        from robingraph.retrieval.neo4j_hybrid import search

        embedder = _FakeQueryEmbedder(self.PROFILE)
        index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:00:00Z"
        )
        target_id = self.corpus.chunks[0]["chunk_id"]

        # Simulate the chunk's text/hash changing without re-embedding it:
        # index_chunks is called with the *complete* remaining eligible set
        # minus this one chunk (as embed_fixture_chunks would produce if its
        # new hash hadn't been re-embedded yet).
        remaining = tuple(chunk for chunk in self._embed_allowed_chunks() if chunk.chunk_id != target_id)
        report = index_chunks(self.settings, remaining, expected_profile=self.PROFILE, indexed_at="2026-09-04T00:01:00Z")
        self.assertIn(target_id, report.invalidated)

        outcome = search(self.settings, HybridSearchRequest(query_text="fixture", limit=10), query_embedder=embedder)
        vector_hit_ids = {result.chunk_id for result in outcome.results if VECTOR_CHANNEL in result.channels}
        self.assertNotIn(target_id, vector_hit_ids)

        # Restore full indexing for any later test in this run/class.
        index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:02:00Z"
        )

    def test_search_never_writes(self) -> None:
        # A read-only session in this driver setup would raise if `search`
        # attempted a write; the more direct proof is behavioral: run search
        # many times and confirm the indexed/invalidated state (observable
        # via a subsequent index_chunks report) is unaffected by searching.
        from robingraph.retrieval.neo4j_hybrid import search

        index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:00:00Z"
        )
        for _ in range(3):
            search(self.settings, HybridSearchRequest(query_text="서식지", limit=5))
        report = index_chunks(
            self.settings, self._embed_allowed_chunks(), expected_profile=self.PROFILE, indexed_at="2026-09-04T00:03:00Z"
        )
        self.assertEqual((), report.invalidated)
        self.assertEqual(4, len(report.indexed))


if __name__ == "__main__":
    unittest.main()
