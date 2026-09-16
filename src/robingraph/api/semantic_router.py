"""Small, fail-closed semantic intent router for the integrated chat API.

The router deliberately has no lexical fallback.  If embeddings are absent,
malformed, tied, or insufficiently confident, callers get ``None`` and can
ask the user to choose an explicit route instead.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from threading import Lock
from typing import Literal, Sequence

from ..embeddings import EmbeddingClient


ChatIntent = Literal["taxonomy", "observations", "evidence"]


# Keep these short: they are capability descriptions, not training data.  The
# Korean/English pairs make the routing intent legible and useful for both UI
# languages.  Bumping this version deliberately invalidates a warm cache.
PROTOTYPE_VERSION = "v1"
CAPABILITY_PROTOTYPES: tuple[tuple[ChatIntent, str], ...] = (
    ("taxonomy", "분류 계통 학명 국명 taxonomy lineage scientific name"),
    ("observations", "관찰 기록 장소 날짜 종 observations occurrence place date"),
    ("evidence", "근거 문헌 출처 인용 evidence document source citation"),
)
_REQUIRED_INTENTS = frozenset({"taxonomy", "observations", "evidence"})


@dataclass(frozen=True)
class SemanticRouterConfig:
    confidence_threshold: float = 0.70
    winner_margin_threshold: float = 0.08

    def __post_init__(self) -> None:
        for name in ("confidence_threshold", "winner_margin_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if not 0.0 <= self.winner_margin_threshold <= 2.0:
            raise ValueError("winner_margin_threshold must be between 0 and 2")


def _validated_vector(value: Sequence[object], *, dimensions: int | None = None) -> tuple[float, ...]:
    """Accept only usable numeric vectors; bools and non-finite values fail."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("embedding vector must be a sequence")
    if dimensions is not None and len(value) != dimensions:
        raise ValueError("embedding vector dimensions do not match")
    if not value:
        raise ValueError("embedding vector must not be empty")
    vector: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("embedding vector contains a non-numeric value")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError("embedding vector contains a non-finite value")
        vector.append(number)
    _vector_norm(vector)
    return tuple(vector)


def _vector_norm(vector: Sequence[float]) -> float:
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("embedding vector must have a finite non-zero norm")
    return norm


class SemanticRouter:
    """Lazy cosine classifier over a compact, versioned prototype set."""

    def __init__(
        self,
        client: EmbeddingClient,
        *,
        config: SemanticRouterConfig = SemanticRouterConfig(),
        prototypes: tuple[tuple[ChatIntent, str], ...] = CAPABILITY_PROTOTYPES,
    ) -> None:
        intents = {intent for intent, _text in prototypes}
        if len(intents) != len(prototypes) or intents != _REQUIRED_INTENTS:
            raise ValueError("semantic router prototypes must contain taxonomy, observations, and evidence exactly once")
        self._client = client
        self._config = config
        self._prototypes = prototypes
        self._cached_prototypes: tuple[tuple[ChatIntent, tuple[float, ...]], ...] | None = None
        self._cache_lock = Lock()

    @property
    def prototype_version(self) -> str:
        return PROTOTYPE_VERSION

    def _prototype_vectors(self) -> tuple[tuple[ChatIntent, tuple[float, ...]], ...]:
        if self._cached_prototypes is not None:
            return self._cached_prototypes
        with self._cache_lock:
            if self._cached_prototypes is not None:
                return self._cached_prototypes
            vectors = self._client.embed_documents([text for _intent, text in self._prototypes])
            if len(vectors) != len(self._prototypes):
                raise ValueError("embedding provider returned the wrong prototype count")
            validated: list[tuple[ChatIntent, tuple[float, ...]]] = []
            dimensions: int | None = None
            for (intent, _text), vector in zip(self._prototypes, vectors, strict=True):
                checked = _validated_vector(vector, dimensions=dimensions)
                dimensions = len(checked)
                validated.append((intent, checked))
            # Do not cache partially checked output. A failed first request may be
            # retried safely after the provider recovers.
            self._cached_prototypes = tuple(validated)
            return self._cached_prototypes

    def classify(self, question: str) -> ChatIntent | None:
        """Return a conservative winner, or ``None`` without exposing errors."""

        try:
            prototypes = self._prototype_vectors()
            query = _validated_vector(self._client.embed_query(question), dimensions=len(prototypes[0][1]))
            query_norm = _vector_norm(query)
            scores = []
            for intent, vector in prototypes:
                score = sum(left * right for left, right in zip(query, vector, strict=True))
                score /= query_norm * _vector_norm(vector)
                if not math.isfinite(score):
                    raise ValueError("embedding cosine similarity is not finite")
                scores.append((score, intent))
            scores.sort(key=lambda item: (-item[0], item[1]))
            winner_score, winner = scores[0]
            runner_up = scores[1][0] if len(scores) > 1 else -1.0
            if winner_score < self._config.confidence_threshold:
                return None
            if winner_score - runner_up < self._config.winner_margin_threshold:
                return None
            return winner
        except Exception:
            # Configuration, transport, and malformed-provider details are
            # diagnostics, never chat content.
            return None
