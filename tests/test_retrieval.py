"""Tests for the backend-agnostic QuestionService and its repository shapes.

`_SyntheticRepository` implements the same `GraphRepository` shape consumed
by `QuestionService` with data that never appeared in any previous
hard-coded lookup table (place names, a document title, and a taxon not
covered by the old species-specific branches). If `QuestionService` still
resolves them correctly, its resolution is genuinely data-driven rather than
special-cased for the shipped fixture content.
"""

from __future__ import annotations

import unittest

from robingraph.fixture import default_fixture_root, load_fixture
from robingraph.retrieval.fixture_repository import FixtureRepository
from robingraph.retrieval.repository import (
    ChunkRecord,
    DocumentRecord,
    ObservationRecord,
    PlaceRecord,
    SourceCitation,
    TaxonRecord,
    VernacularName,
)
from robingraph.slice import QuestionService, validate_answer


class _SyntheticRepository:
    """A minimal, hand-built `GraphRepository` for entity-resolution tests."""

    mode = "synthetic"
    taxonomy_release = "synthetic-release"
    data_cutoff = "2026-09-04T00:00:00Z"

    def __init__(self) -> None:
        self._taxonomy = (
            TaxonRecord(
                taxon_id="rg:taxon:synthetic-heron",
                scientific_name="Testus heronicus",
                vernacular_names=(VernacularName("ko", "테스트해오라기"),),
            ),
        )
        self._documents = (
            DocumentRecord("doc-synth-1", "테스트 조류 조사 보고서"),
            # Metadata-only: resolvable by title, but its chunk/fulltext
            # permission was denied, so it has no chunks at all.
            DocumentRecord("doc-synth-empty", "테스트 메타데이터 전용 문서"),
        )
        self._chunks = (ChunkRecord("chunk-synth-1", "doc-synth-1", 1, "테스트해오라기는 테스트 습지에서 기록됐다."),)
        self._places = (
            PlaceRecord("place-synth-wetland", "테스트 습지"),
            PlaceRecord("place-synth-mountain", "테스트 산지"),
        )
        self._observations = (
            ObservationRecord(
                occurrence_id="occ-synth-open-1",
                taxon_id="rg:taxon:synthetic-heron",
                place_id="place-synth-wetland",
                place_name="테스트 습지",
                event_date_raw="2025-05-01",
                sensitivity_class="public",
            ),
            ObservationRecord(
                occurrence_id="occ-synth-withheld-1",
                taxon_id="rg:taxon:synthetic-heron",
                place_id="place-synth-mountain",
                place_name="테스트 산지",
                event_date_raw="2025-03-01",
                sensitivity_class="withheld",
            ),
        )

    def list_taxonomy(self):
        return self._taxonomy

    def list_places(self):
        return self._places

    def list_documents(self):
        return self._documents

    def list_chunks(self):
        return self._chunks

    def chunks_for_document(self, document_id: str):
        return tuple(chunk for chunk in self._chunks if chunk.document_id == document_id)

    def observations_for_taxa(self, taxon_ids, place_id=None, month_prefix=None):
        candidates = set(taxon_ids)
        records = [record for record in self._observations if record.taxon_id in candidates]
        if place_id is not None:
            records = [record for record in records if record.place_id == place_id]
        if month_prefix is not None:
            records = [record for record in records if record.event_date_raw[:7] == month_prefix]
        return tuple(records)

    def citation_for(self, evidence_id: str) -> SourceCitation:
        return SourceCitation(
            source_id="synthetic-source",
            source_url="https://example.invalid/synthetic",
            locator=evidence_id,
            license_name="Synthetic Test License",
        )

    def known_evidence_ids(self) -> frozenset[str]:
        return frozenset({"rg:taxon:synthetic-heron", "occ-synth-open-1", "occ-synth-withheld-1", "chunk-synth-1"})

    def known_private_coordinate_values(self) -> frozenset[str]:
        return frozenset({"37.999999", "127.999999"})


class DataDrivenResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = _SyntheticRepository()
        self.service = QuestionService(self.repository)

    def test_place_resolution_is_derived_from_repository_data_not_a_fixed_table(self) -> None:
        # "테스트 습지" is not one of the shipped fixture's five place names, so
        # this only resolves if place matching is built from repository data.
        answer = self.service.answer("2025년 5월 테스트 습지에서 테스트해오라기가 관찰됐나?")
        self.assertEqual("answer", answer.disposition)
        self.assertEqual(("occ-synth-open-1",), answer.evidence_ids)

    def test_document_answer_derives_taxon_ids_from_chunk_text_not_a_per_document_branch(self) -> None:
        answer = self.service.answer("테스트 조류 조사 보고서에서 어떤 종이 기록됐나?")
        self.assertEqual("answer", answer.disposition)
        self.assertIn("rg:taxon:synthetic-heron", answer.taxon_ids)
        self.assertEqual(("chunk-synth-1",), answer.evidence_ids)

    def test_a_metadata_only_document_with_no_chunks_abstains_instead_of_answering_empty(self) -> None:
        # Regression test: a document can resolve by title (its metadata is
        # always kept, see policy.py) while having zero retrievable chunks
        # (e.g. chunk_storage_allowed revoked). That used to fall through to
        # an "answer" disposition with empty text and no evidence.
        answer = self.service.answer("테스트 메타데이터 전용 문서에는 어떤 내용이 있나?")
        self.assertEqual("abstain", answer.disposition)
        self.assertTrue(answer.answer_text)
        self.assertEqual((), answer.evidence_ids)

    def test_precise_coordinate_request_with_no_matching_observation_abstains_without_crashing(self) -> None:
        # Regression test: a sensitivity-withheld taxon combined with a
        # place/month filter that matches zero observations used to raise
        # IndexError instead of abstaining gracefully.
        answer = self.service.answer("테스트 산지에서 2025년 12월 테스트해오라기의 정확한 좌표를 알려줘.")
        self.assertEqual("abstain", answer.disposition)
        self.assertEqual((), answer.evidence_ids)

    def test_precise_coordinate_request_with_a_withheld_match_abstains_with_sensitivity_warning(self) -> None:
        answer = self.service.answer("테스트 산지의 테스트해오라기의 정확한 관찰 좌표를 알려줘.")
        self.assertEqual("abstain", answer.disposition)
        self.assertIn("sensitive_coordinates_withheld", answer.warnings)
        self.assertEqual(("occ-synth-withheld-1",), answer.evidence_ids)
        validate_answer(answer, self.repository)

    def test_precise_coordinate_request_matching_a_non_sensitive_observation_still_answers(self) -> None:
        answer = self.service.answer("테스트 습지의 테스트해오라기의 정확한 관찰 좌표를 알려줘.")
        self.assertEqual("answer", answer.disposition)
        self.assertEqual(("occ-synth-open-1",), answer.evidence_ids)


class FixtureRepositoryProvenanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_fixture(default_fixture_root())
        cls.repository = FixtureRepository(cls.corpus)

    def test_citation_license_name_is_sourced_from_the_registry_not_a_hard_coded_literal(self) -> None:
        source = self.corpus.source_registry["fixture-taxonomy"]
        citation = self.repository.citation_for("rg:taxon:passer-montanus")
        self.assertNotEqual("fixture-test-license", citation.license_name)
        self.assertEqual(source.get("license_name") or source["license_uri"], citation.license_name)
        self.assertEqual(source["landing_uri"], citation.source_url)

    def test_taxonomy_observation_and_chunk_evidence_all_resolve_to_a_citation(self) -> None:
        for evidence_id in ("rg:taxon:passer-montanus", "fixture-occ-001", "fixture-chunk-waterbirds-1"):
            with self.subTest(evidence_id=evidence_id):
                citation = self.repository.citation_for(evidence_id)
                self.assertTrue(citation.source_url)
                self.assertTrue(citation.license_name)


class GraphPayloadPolicyReapplicationTest(unittest.TestCase):
    """fixture_graph_payload must not trust that a FixtureCorpus was pre-filtered.

    These build a `FixtureCorpus` by hand (not via `fixture.load_fixture`) so
    they exercise the projection's own defense-in-depth policy checks, which
    matter for any caller -- such as a test simulating a policy revocation --
    that constructs or mutates a corpus directly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_fixture(default_fixture_root())

    def test_a_chunk_marked_denied_after_load_is_dropped_from_the_graph_payload(self) -> None:
        from dataclasses import replace

        from robingraph.graph.fixture_projection import fixture_graph_payload

        target_chunk_id = self.corpus.chunks[0]["chunk_id"]
        revoked_chunks = tuple(
            {**chunk, "license_policy_status": "denied"} if chunk["chunk_id"] == target_chunk_id else chunk
            for chunk in self.corpus.chunks
        )
        payload = fixture_graph_payload(replace(self.corpus, chunks=revoked_chunks))
        self.assertNotIn(target_chunk_id, {row["id"] for row in payload["chunks"]})
        self.assertEqual(len(self.corpus.chunks) - 1, len(payload["chunks"]))

    def test_a_source_registry_entry_marked_denied_excludes_its_records_even_if_the_record_itself_says_allowed(
        self,
    ) -> None:
        from dataclasses import replace

        from robingraph.graph.fixture_projection import fixture_graph_payload

        tampered_registry = dict(self.corpus.source_registry)
        tampered_registry["fixture-taxonomy"] = {
            **tampered_registry["fixture-taxonomy"],
            "license_policy_status": "denied",
        }
        payload = fixture_graph_payload(replace(self.corpus, source_registry=tampered_registry))
        self.assertEqual(0, len(payload["taxa"]))
        # Other categories, whose source registry entries were untouched, are unaffected.
        self.assertEqual(len(self.corpus.observations), len(payload["observations"]))

    def test_a_missing_source_registry_entry_is_treated_as_denied_not_a_crash(self) -> None:
        from dataclasses import replace

        from robingraph.graph.fixture_projection import fixture_graph_payload

        tampered_registry = dict(self.corpus.source_registry)
        del tampered_registry["fixture-taxonomy"]
        payload = fixture_graph_payload(replace(self.corpus, source_registry=tampered_registry))
        self.assertEqual(0, len(payload["taxa"]))


if __name__ == "__main__":
    unittest.main()
