from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from robingraph.fixture import default_fixture_root
from robingraph.retrieval.evaluation import SearchQuestion, evaluate_search, load_search_questions
from robingraph.retrieval.hybrid import HybridResult, HybridSearchOutcome
from robingraph.retrieval.repository import SourceCitation


def _outcome(*chunk_ids: str) -> HybridSearchOutcome:
    citation = SourceCitation("fixture-document", "https://example.invalid", "section 1", "test")
    return HybridSearchOutcome(
        tuple(HybridResult(chunk_id, "text", 1.0, ("vector",), citation) for chunk_id in chunk_ids), ()
    )


class SearchEvaluationTest(unittest.TestCase):
    def test_fixture_search_questions_are_loadable(self) -> None:
        questions = load_search_questions(default_fixture_root() / "search-questions.jsonl")
        self.assertEqual(5, len(questions))
        self.assertEqual("SQ-005", questions[-1].question_id)
        self.assertEqual(("fixture-chunk-review-1",), questions[-1].forbidden_chunk_ids)

    def test_reports_recall_rank_latency_and_policy_separately(self) -> None:
        questions = (
            SearchQuestion("one", "first", ("a", "b")),
            SearchQuestion("two", "second", (), ("blocked",)),
        )
        outcomes = {"first": _outcome("x", "b"), "second": _outcome("blocked")}
        report = evaluate_search(questions, lambda question, limit: outcomes[question], limit=3)
        self.assertEqual(0.5, report.recall_at_k)
        self.assertEqual(0.5, report.mean_reciprocal_rank)
        self.assertFalse(report.policy_safe)
        self.assertFalse(report.cases[1].policy_safe)
        self.assertGreaterEqual(report.p95_latency_ms, report.mean_latency_ms)

    def test_rejects_invalid_question_file_and_limit(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "search.jsonl"
            path.write_text('{"question_id":"x","question_ko":"q","relevant_chunk_ids":["a"],"forbidden_chunk_ids":["a"]}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overlap"):
                load_search_questions(path)
        with self.assertRaisesRegex(ValueError, "positive"):
            evaluate_search((SearchQuestion("x", "q", ("a",)),), lambda question, limit: _outcome(), limit=0)

    def test_mrr_counts_missed_answerable_questions_as_zero(self) -> None:
        questions = (SearchQuestion("hit", "hit", ("a",)),
                     SearchQuestion("miss", "miss", ("b",)),
                     SearchQuestion("empty", "empty", ()))
        report = evaluate_search(questions, lambda q, limit: _outcome("a") if q == "hit" else _outcome(), limit=3)
        self.assertEqual(0.5, report.mean_reciprocal_rank)
        self.assertEqual(0.5, report.recall_at_k)
        self.assertIsNone(report.cases[1].reciprocal_rank)

    def test_mrr_is_zero_when_all_answerable_questions_miss(self) -> None:
        report = evaluate_search((SearchQuestion("miss", "miss", ("a",)),),
                                 lambda q, limit: _outcome(), limit=3)
        self.assertEqual(0.0, report.mean_reciprocal_rank)

    def test_mrr_is_undefined_without_answerable_questions(self) -> None:
        report = evaluate_search((SearchQuestion("empty", "empty", ()),),
                                 lambda q, limit: _outcome(), limit=3)
        self.assertIsNone(report.mean_reciprocal_rank)


if __name__ == "__main__":
    unittest.main()
