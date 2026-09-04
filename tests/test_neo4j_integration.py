"""Opt-in integration tests against a real Neo4j server.

These are skipped by default. They only run when explicitly enabled with
``ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1``, so a plain
``uv run --locked --extra test python -m unittest discover -s tests`` never
touches a live database by accident. Once that flag is set, this is an
explicit request to run against a real server: a missing or invalid
``NEO4J_URI`` / ``NEO4J_USERNAME`` / ``NEO4J_PASSWORD`` / ``NEO4J_DATABASE``
(see `robingraph.graph.settings.Neo4jSettings`) is a test failure (raised in
`setUpClass`), never a silent skip -- a broken connection must not be able to
masquerade as "not opted in".

All writes here are confined to nodes labeled `:RobinGraph:Fixture` with
deterministic fixture IDs -- see `robingraph.graph.neo4j_client`. A load also
reconciles (deletes) `:RobinGraph:Fixture` nodes that fell out of the current
payload, e.g. after a policy revocation, but that reconciliation is scoped to
the same label, so this is safe to run against a database that also holds
unrelated, non-fixture data. Every test that mutates fixture content restores
the committed fixture (a plain reload) before returning, so a full run leaves
the graph in the same state it found it in.

Exact invocation (see docs/current-implementation.md for the full write-up)::

    export ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1
    export NEO4J_URI=bolt://localhost:7687
    export NEO4J_USERNAME=neo4j
    export NEO4J_PASSWORD=<password>
    export NEO4J_DATABASE=neo4j
    uv run --locked --extra test python -m unittest tests.test_neo4j_integration -v
"""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import unittest

from robingraph.fixture import default_fixture_root, load_fixture
from robingraph.graph.settings import Neo4jSettings
from robingraph.slice import QuestionService, validate_answer


def _integration_opt_in() -> bool:
    return os.getenv("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(
    _integration_opt_in(),
    "Set ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 (with NEO4J_URI/USERNAME/PASSWORD/DATABASE) to run against a real Neo4j server.",
)
class Neo4jIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from robingraph.graph.neo4j_client import bootstrap_schema, load_fixture as load_neo4j_fixture_graph
        from robingraph.retrieval.neo4j_repository import Neo4jGraphRepository

        # Explicit opt-in (ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1): a missing or
        # malformed connection configuration must fail loudly here, not skip.
        cls.settings = Neo4jSettings.from_environment()
        cls.root = default_fixture_root()
        corpus = load_fixture(cls.root)
        bootstrap_schema(cls.settings)
        cls.graph_counts = load_neo4j_fixture_graph(cls.settings, corpus)
        cls.repository = Neo4jGraphRepository(cls.settings)
        cls.service = QuestionService(cls.repository)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.repository.close()

    def _gold_questions(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in (self.root / "gold-questions.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_fixture_graph_counts_match_the_policy_filtered_corpus(self) -> None:
        self.assertEqual(10, self.graph_counts.taxa)
        self.assertEqual(100, self.graph_counts.observations)
        self.assertEqual(2, self.graph_counts.documents)
        self.assertEqual(4, self.graph_counts.chunks)

    def test_neo4j_backed_repository_reports_neo4j_mode(self) -> None:
        self.assertEqual("neo4j", self.repository.mode)
        self.assertEqual("fixture-avlist-2025", self.repository.taxonomy_release)

    def test_gold_questions_pass_through_real_parameterized_cypher_retrieval(self) -> None:
        for gold in self._gold_questions():
            with self.subTest(question_id=gold["question_id"]):
                answer = self.service.answer(str(gold["question_ko"]))
                validate_answer(answer, self.repository)
                self.assertEqual(gold["expected_disposition"], answer.disposition)
                self.assertTrue(set(gold["expected_taxon_ids"]).issubset(answer.taxon_ids))
                accepted = set(gold["acceptable_evidence_ids"])
                if accepted:
                    self.assertTrue(answer.evidence_ids)
                    self.assertTrue(set(answer.evidence_ids).issubset(accepted))
                for forbidden in gold["must_not_include"]:
                    self.assertNotIn(str(forbidden), answer.answer_text)
                    self.assertNotIn(str(forbidden), answer.evidence_ids)

    def test_citations_carry_a_real_source_and_license_from_the_graph(self) -> None:
        citation = self.repository.citation_for("rg:taxon:passer-montanus")
        self.assertTrue(citation.source_url)
        self.assertNotEqual("unknown", citation.license_name)

    def test_chunk_citation_locator_is_the_readable_section_not_the_chunk_id(self) -> None:
        # Regression test: the citation locator used to read the Chunk
        # node's own `.locator` property, which load never sets, so it fell
        # back to the chunk's opaque id/external_id instead of the
        # human-readable section string recorded on the EvidenceUnit.
        citation = self.repository.citation_for("fixture-chunk-waterbirds-1")
        self.assertEqual("section 1", citation.locator)
        self.assertNotEqual("fixture-chunk-waterbirds-1", citation.locator)

    def test_no_private_coordinates_are_reachable_through_the_graph_backed_repository(self) -> None:
        from robingraph.graph.neo4j_client import verify_fixture

        verification = verify_fixture(self.settings)
        self.assertEqual(0, verification.private_coordinate_properties)
        self.assertEqual(0, verification.restricted_observations)
        self.assertEqual(frozenset(), self.repository.known_private_coordinate_values())


@unittest.skipUnless(
    _integration_opt_in(),
    "Set ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 (with NEO4J_URI/USERNAME/PASSWORD/DATABASE) to run against a real Neo4j server.",
)
class Neo4jPolicyReconciliationTest(unittest.TestCase):
    """Exercises reload reconciliation and fail-closed license enforcement live.

    Every test restores the committed fixture (a plain reload of the
    unmodified corpus) before it returns, via addCleanup, so a full test run
    leaves the disposable database in the same state it found it in.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from robingraph.graph.neo4j_client import bootstrap_schema

        # Same fail-loudly-on-bad-config rule as Neo4jIntegrationTest.
        cls.settings = Neo4jSettings.from_environment()
        cls.root = default_fixture_root()
        bootstrap_schema(cls.settings)

    def _load(self, corpus):
        from robingraph.graph.neo4j_client import load_fixture as load_neo4j_fixture_graph

        return load_neo4j_fixture_graph(self.settings, corpus)

    def _restore_committed_fixture(self) -> None:
        self._load(load_fixture(self.root))

    def setUp(self) -> None:
        self._restore_committed_fixture()
        self.addCleanup(self._restore_committed_fixture)

    def test_repeated_load_of_the_same_fixture_is_idempotent(self) -> None:
        corpus = load_fixture(self.root)
        first = self._load(corpus)
        second = self._load(corpus)
        self.assertEqual(first, second)
        self.assertEqual(4, second.chunks)

    def test_revoking_a_chunk_removes_it_and_its_evidence_on_reload(self) -> None:
        from robingraph.retrieval.neo4j_repository import Neo4jGraphRepository

        corpus = load_fixture(self.root)
        target_chunk_id = corpus.chunks[0]["chunk_id"]
        revoked_chunks = tuple(
            {**chunk, "license_policy_status": "denied"} if chunk["chunk_id"] == target_chunk_id else chunk
            for chunk in corpus.chunks
        )
        revoked_corpus = replace(corpus, chunks=revoked_chunks)

        counts = self._load(revoked_corpus)
        self.assertEqual(len(corpus.chunks) - 1, counts.chunks)

        with Neo4jGraphRepository(self.settings) as repository:
            # Fail-closed at both layers: retrieval itself (list_chunks),
            # not only the later citation lookup.
            self.assertNotIn(target_chunk_id, {chunk.chunk_id for chunk in repository.list_chunks()})
            self.assertNotIn(target_chunk_id, repository.known_evidence_ids())
            with self.assertRaises(ValueError):
                repository.citation_for(target_chunk_id)

        # Restore before the next assertion so a failure above still leaves
        # the fixture intact for tearDown/other tests in this run.
        self._restore_committed_fixture()
        restored = self._load(corpus)
        self.assertEqual(4, restored.chunks)

    def test_revoking_a_taxon_removes_it_from_retrieval_directly_not_only_citation(self) -> None:
        from robingraph.retrieval.neo4j_repository import Neo4jGraphRepository

        corpus = load_fixture(self.root)
        target_taxon_id = corpus.taxonomy[0]["source_taxon_id"]
        revoked_taxonomy = tuple(
            {**taxon, "license_policy_status": "denied"} if taxon["source_taxon_id"] == target_taxon_id else taxon
            for taxon in corpus.taxonomy
        )
        revoked_corpus = replace(corpus, taxonomy=revoked_taxonomy)
        self._load(revoked_corpus)

        with Neo4jGraphRepository(self.settings) as repository:
            self.assertNotIn(target_taxon_id, {taxon.taxon_id for taxon in repository.list_taxonomy()})
            self.assertNotIn(target_taxon_id, repository.known_evidence_ids())
            with self.assertRaises(ValueError):
                repository.citation_for(target_taxon_id)
            # Observations of the now-denied taxon are also unreachable, even
            # though the Observation records themselves were never revoked.
            self.assertEqual((), repository.observations_for_taxa([target_taxon_id], None, None))

    def test_revoking_a_documents_chunk_storage_removes_only_its_chunks(self) -> None:
        corpus = load_fixture(self.root)
        target_document_id = corpus.documents[0]["document_id"]
        revoked_documents = tuple(
            {**document, "chunk_storage_allowed": False} if document["document_id"] == target_document_id else document
            for document in corpus.documents
        )
        revoked_corpus = replace(corpus, documents=revoked_documents)

        expected_remaining_chunks = sum(
            1 for chunk in corpus.chunks if chunk["document_id"] != target_document_id
        )
        counts = self._load(revoked_corpus)
        self.assertEqual(expected_remaining_chunks, counts.chunks)
        # The document's own metadata is preserved even though its chunks are gone.
        self.assertEqual(2, counts.documents)


if __name__ == "__main__":
    unittest.main()
