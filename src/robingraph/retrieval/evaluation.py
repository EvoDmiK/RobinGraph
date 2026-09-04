"""Deterministic retrieval-quality measurements for the synthetic search fixture."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter

from .hybrid import HybridSearchOutcome


@dataclass(frozen=True)
class SearchQuestion:
    question_id: str
    question_ko: str
    relevant_chunk_ids: tuple[str, ...]
    forbidden_chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchCaseResult:
    question_id: str
    returned_chunk_ids: tuple[str, ...]
    recall_at_k: float | None
    reciprocal_rank: float | None
    policy_safe: bool
    elapsed_ms: float


@dataclass(frozen=True)
class SearchEvaluationReport:
    limit: int
    cases: tuple[SearchCaseResult, ...]
    recall_at_k: float | None
    mean_reciprocal_rank: float | None
    mean_latency_ms: float
    p95_latency_ms: float
    policy_safe: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def load_search_questions(path: Path) -> tuple[SearchQuestion, ...]:
    questions: list[SearchQuestion] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            question_id = record["question_id"]
            question_ko = record["question_ko"]
            relevant = record["relevant_chunk_ids"]
            forbidden = record.get("forbidden_chunk_ids", [])
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ValueError(f"Invalid search question at {path}:{line_number}") from error
        if not isinstance(question_id, str) or not question_id or question_id in seen:
            raise ValueError(f"Search question IDs must be unique non-empty strings: {path}:{line_number}")
        if not isinstance(question_ko, str) or not question_ko.strip():
            raise ValueError(f"Search question must not be blank: {path}:{line_number}")
        if not isinstance(relevant, list) or not isinstance(forbidden, list) or not all(
            isinstance(chunk_id, str) and chunk_id for chunk_id in [*relevant, *forbidden]
        ):
            raise ValueError(f"Search chunk IDs must be non-empty strings: {path}:{line_number}")
        if set(relevant) & set(forbidden):
            raise ValueError(f"Search relevance and exclusion IDs overlap: {path}:{line_number}")
        seen.add(question_id)
        questions.append(SearchQuestion(question_id, question_ko, tuple(relevant), tuple(forbidden)))
    if not questions:
        raise ValueError(f"No search questions found in {path}")
    return tuple(questions)


def evaluate_search(
    questions: Sequence[SearchQuestion], search: Callable[[str, int], HybridSearchOutcome], *, limit: int
) -> SearchEvaluationReport:
    """Measure recall and ranking while separately recording policy exclusions."""
    if limit < 1:
        raise ValueError("Search evaluation limit must be positive")
    cases: list[SearchCaseResult] = []
    relevant_total = 0
    relevant_retrieved = 0
    reciprocal_ranks: list[float] = []
    for question in questions:
        started = perf_counter()
        outcome = search(question.question_ko, limit)
        elapsed_ms = (perf_counter() - started) * 1000
        returned = tuple(result.chunk_id for result in outcome.results)
        relevant = set(question.relevant_chunk_ids)
        hits = relevant & set(returned)
        recall = len(hits) / len(relevant) if relevant else None
        reciprocal_rank = next((1 / index for index, chunk_id in enumerate(returned, start=1) if chunk_id in relevant), None)
        policy_safe = not (set(returned) & set(question.forbidden_chunk_ids))
        cases.append(SearchCaseResult(question.question_id, returned, recall, reciprocal_rank, policy_safe, elapsed_ms))
        if relevant:
            relevant_total += len(relevant)
            relevant_retrieved += len(hits)
            if reciprocal_rank is not None:
                reciprocal_ranks.append(reciprocal_rank)
    latencies = sorted(case.elapsed_ms for case in cases)
    p95_index = max(0, (len(latencies) * 95 + 99) // 100 - 1)
    return SearchEvaluationReport(
        limit, tuple(cases), relevant_retrieved / relevant_total if relevant_total else None,
        sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None,
        sum(latencies) / len(latencies), latencies[p95_index], all(case.policy_safe for case in cases),
    )
