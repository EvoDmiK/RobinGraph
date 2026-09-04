"""Offline tests for backend-agnostic RRF fusion (`robingraph.retrieval.hybrid`).

No Neo4j dependency: `reciprocal_rank_fusion` and `fuse_hybrid_results` only
ever see rank-ordered chunk ID sequences, never channel-native scores, so
these tests exercise the fusion math and result shaping directly.
"""

from __future__ import annotations

import unittest

from robingraph.retrieval.hybrid import (
    FULLTEXT_CHANNEL,
    VECTOR_CHANNEL,
    VECTOR_UNAVAILABLE_WARNING,
    fuse_hybrid_results,
    rank_fused,
    reciprocal_rank_fusion,
)
from robingraph.retrieval.repository import SourceCitation


def _citation(chunk_id: str) -> SourceCitation:
    return SourceCitation(source_id="src", source_url="https://example.invalid", locator=chunk_id, license_name="lic")


class ReciprocalRankFusionTest(unittest.TestCase):
    def test_single_channel_score_matches_the_standard_formula(self) -> None:
        fused = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["a", "b", "c"]}, k=60)
        self.assertAlmostEqual(1.0 / 61, fused["a"][0])
        self.assertAlmostEqual(1.0 / 62, fused["b"][0])
        self.assertAlmostEqual(1.0 / 63, fused["c"][0])
        self.assertEqual((FULLTEXT_CHANNEL,), fused["a"][1])

    def test_never_sums_raw_channel_scores_only_ranks(self) -> None:
        # Two channels use wildly different "native" magnitudes in a caller's
        # own bookkeeping, but reciprocal_rank_fusion's signature never
        # accepts scores at all -- only rank-ordered ID sequences -- so there
        # is no way for a caller to smuggle raw scores into the fusion.
        fused_a = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["x", "y"], VECTOR_CHANNEL: ["y", "x"]}, k=60)
        fused_b = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["x", "y"], VECTOR_CHANNEL: ["y", "x"]}, k=60)
        self.assertEqual(fused_a, fused_b)

    def test_a_chunk_present_in_both_channels_outranks_single_channel_hits(self) -> None:
        fused = reciprocal_rank_fusion(
            {FULLTEXT_CHANNEL: ["shared", "fulltext-only"], VECTOR_CHANNEL: ["shared", "vector-only"]}
        )
        self.assertGreater(fused["shared"][0], fused["fulltext-only"][0])
        self.assertGreater(fused["shared"][0], fused["vector-only"][0])
        self.assertEqual((FULLTEXT_CHANNEL, VECTOR_CHANNEL), fused["shared"][1])

    def test_duplicate_chunk_id_within_one_channel_is_deduped_to_its_first_occurrence(self) -> None:
        fused = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["a", "b", "a"]})
        without_dup = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["a", "b"]})
        self.assertEqual(fused["a"][0], without_dup["a"][0])
        self.assertEqual((FULLTEXT_CHANNEL,), fused["a"][1])

    def test_channel_iteration_order_does_not_affect_the_result(self) -> None:
        first = reciprocal_rank_fusion({"z-channel": ["a"], "a-channel": ["a"]})
        second = reciprocal_rank_fusion({"a-channel": ["a"], "z-channel": ["a"]})
        self.assertEqual(first, second)
        self.assertEqual(("a-channel", "z-channel"), first["a"][1])

    def test_rejects_a_non_positive_k(self) -> None:
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["a"]}, k=0)


class RankFusedTest(unittest.TestCase):
    def test_orders_by_descending_score(self) -> None:
        fused = reciprocal_rank_fusion({FULLTEXT_CHANNEL: ["a", "b", "c"]})
        self.assertEqual(["a", "b", "c"], rank_fused(fused))

    def test_ties_break_deterministically_by_chunk_id(self) -> None:
        # "zeta" and "alpha" each appear only at rank 1 in their own,
        # otherwise-disjoint single-item channel, so they tie on fused
        # score; the ordering must not depend on dict/set iteration order
        # (hence the repeated assertion in the loop below).
        tied = reciprocal_rank_fusion({"chan-1": ["zeta"], "chan-2": ["alpha"]})
        self.assertEqual(tied["zeta"][0], tied["alpha"][0])
        self.assertEqual(["alpha", "zeta"], rank_fused(tied))
        for _ in range(5):
            self.assertEqual(["alpha", "zeta"], rank_fused(reciprocal_rank_fusion({"chan-1": ["zeta"], "chan-2": ["alpha"]})))


class FuseHybridResultsTest(unittest.TestCase):
    def test_bounds_results_to_limit(self) -> None:
        outcome = fuse_hybrid_results(
            {FULLTEXT_CHANNEL: ["a", "b", "c"]},
            chunk_text={"a": "A", "b": "B", "c": "C"},
            citation_for=_citation,
            limit=2,
        )
        self.assertEqual(("a", "b"), tuple(result.chunk_id for result in outcome.results))

    def test_result_shape_carries_chunk_id_text_score_channels_and_citation(self) -> None:
        outcome = fuse_hybrid_results(
            {FULLTEXT_CHANNEL: ["a"], VECTOR_CHANNEL: ["a"]},
            chunk_text={"a": "hello"},
            citation_for=_citation,
            limit=5,
        )
        result = outcome.results[0]
        self.assertEqual("a", result.chunk_id)
        self.assertEqual("hello", result.text)
        self.assertEqual((FULLTEXT_CHANNEL, VECTOR_CHANNEL), result.channels)
        self.assertIsInstance(result.score, float)
        self.assertEqual(_citation("a"), result.citation)

    def test_only_looks_up_text_and_citation_for_chunks_within_the_bound(self) -> None:
        # chunk_text/citation_for need not cover ranked-but-truncated IDs.
        calls: list[str] = []

        def _tracking_citation(chunk_id: str) -> SourceCitation:
            calls.append(chunk_id)
            return _citation(chunk_id)

        outcome = fuse_hybrid_results(
            {FULLTEXT_CHANNEL: ["a", "b", "c"]},
            chunk_text={"a": "A"},
            citation_for=_tracking_citation,
            limit=1,
        )
        self.assertEqual(1, len(outcome.results))
        self.assertEqual(["a"], calls)

    def test_keyword_only_fallback_carries_the_vector_unavailable_warning(self) -> None:
        outcome = fuse_hybrid_results(
            {FULLTEXT_CHANNEL: ["a"]},
            chunk_text={"a": "A"},
            citation_for=_citation,
            limit=5,
            warnings=(VECTOR_UNAVAILABLE_WARNING,),
        )
        self.assertIn(VECTOR_UNAVAILABLE_WARNING, outcome.warnings)
        self.assertEqual((FULLTEXT_CHANNEL,), outcome.results[0].channels)

    def test_rejects_a_non_positive_limit(self) -> None:
        with self.assertRaises(ValueError):
            fuse_hybrid_results({FULLTEXT_CHANNEL: ["a"]}, chunk_text={"a": "A"}, citation_for=_citation, limit=0)

    def test_empty_rankings_produce_an_empty_but_valid_outcome(self) -> None:
        outcome = fuse_hybrid_results({}, chunk_text={}, citation_for=_citation, limit=5)
        self.assertEqual((), outcome.results)


if __name__ == "__main__":
    unittest.main()
