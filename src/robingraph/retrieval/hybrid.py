"""Backend-agnostic reciprocal rank fusion (RRF) for hybrid chunk search.

`reciprocal_rank_fusion` and `fuse_hybrid_results` never see channel-native
scores -- only rank-ordered chunk ID sequences. A Lucene fulltext score and a
cosine vector similarity live on unrelated, non-comparable scales, so
combining channels by summing raw scores would be arbitrary; RRF instead
credits each chunk `1 / (k + rank)` per channel it appears in and sums those
already-comparable contributions. This module has no Neo4j dependency --
`robingraph.retrieval.neo4j_hybrid` supplies the per-channel rankings (via
fulltext/vector index queries, already policy-rechecked) and this module only
fuses, bounds, and shapes them into `HybridResult`s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .repository import SourceCitation

FULLTEXT_CHANNEL = "fulltext"
VECTOR_CHANNEL = "vector"

VECTOR_UNAVAILABLE_WARNING = "vector search unavailable; results are keyword-only fulltext"

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class HybridResult:
    """One bounded, ranked hybrid search hit."""

    chunk_id: str
    text: str
    score: float
    channels: tuple[str, ...]
    citation: SourceCitation


@dataclass(frozen=True)
class HybridSearchOutcome:
    results: tuple[HybridResult, ...]
    warnings: tuple[str, ...]


def reciprocal_rank_fusion(
    channel_rankings: Mapping[str, Sequence[str]],
    *,
    k: int = DEFAULT_RRF_K,
) -> dict[str, tuple[float, tuple[str, ...]]]:
    """Fuse per-channel rankings into `{chunk_id: (fused_score, contributing_channels)}`.

    Each `channel_rankings[channel]` is already ranked best-first; a repeated
    chunk ID within one channel's sequence is deduped to its first (best)
    occurrence. Channels are iterated in sorted-name order so the result is
    identical regardless of the caller's mapping iteration order (dict
    insertion order is otherwise not guaranteed to be stable across callers).
    The returned `contributing_channels` tuple also follows this sorted order,
    so it is deterministic too.
    """

    if k < 1:
        raise ValueError("RRF k must be a positive integer")

    fused_scores: dict[str, float] = {}
    contributing_channels: dict[str, list[str]] = {}
    for channel in sorted(channel_rankings):
        seen: set[str] = set()
        for zero_based_rank, chunk_id in enumerate(channel_rankings[channel]):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank = zero_based_rank + 1
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            contributing_channels.setdefault(chunk_id, []).append(channel)
    return {chunk_id: (score, tuple(contributing_channels[chunk_id])) for chunk_id, score in fused_scores.items()}


def rank_fused(fused: Mapping[str, tuple[float, tuple[str, ...]]]) -> list[str]:
    """Chunk IDs ordered by fused score descending, ties broken by chunk_id ascending.

    The tie-break makes ordering deterministic even when two chunks land on
    the exact same fused score (e.g. both matched only one channel, at the
    same rank in it).
    """

    return sorted(fused, key=lambda chunk_id: (-fused[chunk_id][0], chunk_id))


def fuse_hybrid_results(
    channel_rankings: Mapping[str, Sequence[str]],
    *,
    chunk_text: Mapping[str, str],
    citation_for: Callable[[str], SourceCitation],
    limit: int,
    k: int = DEFAULT_RRF_K,
    warnings: Sequence[str] = (),
) -> HybridSearchOutcome:
    """Fuse, bound to `limit`, and attach text/citation for the top results.

    `chunk_text` and `citation_for` only need to cover chunk IDs that end up
    in the bounded top `limit` -- callers that already filtered
    `channel_rankings` down to policy-allowed, citable chunks (as
    `neo4j_hybrid.search` does) can build `chunk_text`/`citation_for` from
    that same filtered set.
    """

    if limit < 1:
        raise ValueError("limit must be a positive integer")
    fused = reciprocal_rank_fusion(channel_rankings, k=k)
    bounded_ids = rank_fused(fused)[:limit]
    results = tuple(
        HybridResult(
            chunk_id=chunk_id,
            text=chunk_text[chunk_id],
            score=fused[chunk_id][0],
            channels=fused[chunk_id][1],
            citation=citation_for(chunk_id),
        )
        for chunk_id in bounded_ids
    )
    return HybridSearchOutcome(results=results, warnings=tuple(warnings))
