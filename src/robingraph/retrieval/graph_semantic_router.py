"""Embedding nearest-prototype candidates for the seven graph question kinds (RG-206).

Candidates are only a hint about the question kind. They never pick species,
conditions or an answer, and nothing is cached except the prototype vectors.
Every failure is closed: callers get ``status="unavailable"`` and no candidates.
The client (graph-only: short timeout, no retry) is built by the caller.
"""
from dataclasses import dataclass
import math
from threading import Lock
import time

from .graph_questions import GRAPH_QUESTION_KINDS

PROTOTYPE_VERSION = 'graph-rg206-v1'
# Answerable/insufficient tuning paraphrases only (data/eval/graph_questions/tuning.jsonl); never holdout.
PROTOTYPES = (
    ('order_fruit', '참새목 새중에서 열매를 먹는 새는?'),
    ('order_fruit', '참새목 새 중에서 나무열매를 먹는 새는?'),
    ('order_fruit', '참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?'),
    ('order_fruit', '참새목에 속한 새 가운데 열매를 먹는 종류 좀 알려줄래?'),
    ('order_fruit', '열매 먹는 참새목 새를 찾아 줘'),
    ('order_fruit', '참새목 중에서 과실식 하는 새 알려줘'),
    ('order_fruit', 'Passeriformes 중 열매를 먹는 종은?'),
    ('order_fruit', '참새목 새 가운데 열매 섭식 범주인 종'),
    ('order_fruit', '열매를 먹고 사는 참새목 새들은 어떤 게 있나요'),
    ('order_fruit', '비둘기목 중 열매를 먹는 새는?'),
    ('order_fruit', '참새목중 열매먹는 새'),
    ('common_taxonomy', '청둥오리와 흰뺨검둥오리는 분류상 어떤 사이야?'),
    ('common_taxonomy', '까치랑 어치의 분류 계통을 비교해줘'),
    ('common_taxonomy', '직박구리하고 동박새의 공통 상위 분류가 뭐야'),
    ('common_taxonomy', 'Anas platyrhynchos와 Anas zonorhyncha는 어떤 관계인가요?'),
    ('common_taxonomy', '청둥 오리와 흰뺨검둥오리 공통분류 알려줘'),
    ('common_taxonomy', '까치와 물까치는 같은 과야?'),
    ('same_genus', '청둥오리랑 속이 같은 새는 뭐가 있어?'),
    ('same_genus', '직박구리와 동일한 속에 들어가는 종을 알려줘'),
    ('same_genus', 'Anas platyrhynchos와 같은 속인 새는?'),
    ('same_genus', '청둥오리와 같은속에 속하는 새들'),
    ('same_genus', '박새랑 같은 속으로 분류되는 새가 궁금해'),
    ('korea_same_genus', '국내에서 기록된 청둥오리와 같은 속 새는?'),
    ('korea_same_genus', '한국에서 관찰된 적 있는 청둥오리 같은 속 종 알려줘'),
    ('korea_same_genus', '우리나라에 기록된 오리 중에 청둥오리랑 같은 속인 종은 뭐야?'),
    ('korea_same_genus', '청둥오리와 같은 속 가운데 한국 기록이 있는 새는?'),
    ('korea_same_genus', '한국에 기록된 직박구리와 같은 속인 새는?'),
    ('korea_same_genus', '국내 관찰 기록이 있는 청둥오리와 같은 속인 종'),
    ('habitat_shared_diet', '숲에서 살면서 직박구리와 식성이 같은 새가 궁금해'),
    ('habitat_shared_diet', '습지에 사는 새 중 청둥오리와 먹이 범주가 같은 새는?'),
    ('habitat_shared_diet', '초원에서 사는 새들 가운데 종다리랑 식성이 같은 종'),
    ('habitat_shared_diet', '숲에 서식하는 새 중에서 직박구리와 같은 먹이 범주의 새를 보여줘'),
    ('habitat_shared_diet', '직박구리처럼 숲에 살고 먹이 범주도 같은 새는?'),
    ('habitat_shared_diet', '해안에 사는 새 중 괭이갈매기와 먹이 습성이 같은 새'),
    ('habitat_different_diet', '청둥오리랑 서식지는 같지만 먹이는 다른 종을 찾아줘'),
    ('habitat_different_diet', '청둥오리와 사는 곳은 같은데 먹는 건 다른 새는?'),
    ('habitat_different_diet', '직박구리와 서식 환경이 겹치지만 식성이 다른 종 알려줘'),
    ('habitat_different_diet', '서식지는 청둥오리와 겹치고 먹이 범주는 다른 새'),
    ('habitat_different_diet', '왜가리랑 같은 서식지인데 먹이가 다른 새들은 뭐가 있어?'),
    ('specific_fruit', '참새목 중 산수유 열매를 먹는 새는?'),
    ('specific_fruit', '마가목 열매 먹는 새 알려줘'),
    ('specific_fruit', '직박구리랑 같은 열매를 먹는 새는?'),
    ('specific_fruit', '숲에 사는 새 중 직박구리와 똑같은 열매를 먹는 새'),
    ('specific_fruit', '감나무 열매를 먹는 참새목 새는?'),
    ('specific_fruit', '참새목 중에서 감 먹는 새 있어?'),
)
TOP_K = 3
# Leave-one-out on tuning with the TEST Jina model (jina-embeddings-v3, 512 dims), query-task prototypes:
# at 0.80/0.06, 30 of 67 typed questions were confident and 28 of those correct; both errors were
# non-executing items (specific_fruit vs order_fruit, a contrastive clarify). Not yet holdout-verified.
CONFIDENCE = 0.80
MARGIN = 0.06


@dataclass(frozen=True)
class KindCandidates:
    candidates: tuple[tuple[str, float], ...] = ()
    margin: float | None = None
    status: str = 'unavailable'          # ok | below_threshold | unavailable
    prototype_version: str = PROTOTYPE_VERSION
    model: str | None = None
    elapsed_ms: float = 0.0
    embedding_calls: int = 0             # query embedding requests attempted in this classify()
    prototype_calls: int = 0             # prototype cache loads attempted in this classify() (0 when warm)
    prototype_requests: int = 0          # client method calls those loads attempted (embed_queries or embed_query)
    prototype_batches: int | None = None # HTTP batches implied by the client's batch_size; None when unknown

    @property
    def top(self):
        return self.candidates[0][0] if self.status == 'ok' and self.candidates else None


def _number(name, value, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or not 0.0 <= value <= upper:
        raise ValueError(f'{name} must be a finite number in [0, {upper}]')
    return float(value)


def _profile_key(client):
    """(model, dimensions, normalized) from the client profile; raises when unusable."""
    profile = client.profile
    model, dimensions, normalized = profile.model, profile.dimensions, profile.normalized
    if not isinstance(model, str) or not model.strip():
        raise ValueError('embedding model must be named')
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
        raise ValueError('embedding dimensions must be a positive integer')
    if not isinstance(normalized, bool):
        raise ValueError('embedding normalized flag must be boolean')
    return model, dimensions, normalized


def _unit(value, dimensions):
    if isinstance(value, (str, bytes)) or not hasattr(value, '__len__') or len(value) != dimensions:
        raise ValueError('embedding vector has the wrong shape')
    vector = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError('embedding vector has a non-finite or non-numeric value')
        vector.append(float(item))
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError('embedding vector norm must be finite and non-zero')
    return tuple(v / norm for v in vector)


def rank_kinds(query, prototype_vectors):
    """[(kind, best cosine)] best first, from unit vectors; nearest prototype per kind."""
    best = {}
    for kind, vector in prototype_vectors:
        score = sum(a * b for a, b in zip(query, vector, strict=True))
        if not math.isfinite(score):
            raise ValueError('cosine is not finite')
        best[kind] = max(score, best.get(kind, -1.0))
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))


class GraphSemanticRouter:
    def __init__(self, client, *, prototypes=PROTOTYPES, confidence=CONFIDENCE, margin=MARGIN):
        prototypes = tuple(prototypes)
        if not prototypes or len({kind for kind, _ in prototypes}) < 2 or any(
                kind not in GRAPH_QUESTION_KINDS or not isinstance(text, str) or not text.strip()
                for kind, text in prototypes):
            raise ValueError('prototypes must be texts for at least two graph question kinds')
        self._client = client
        self._prototypes = prototypes
        self._confidence = _number('confidence', confidence, 1.0)
        self._margin = _number('margin', margin, 2.0)
        self._cache = None                 # ((version, model, dimensions, normalized), vectors)
        self._lock = Lock()

    def _prototype_vectors(self, key, counts):
        """Cached unit vectors for ``key``. Query-task embeddings, as questions are compared with questions.

        Uses the client's batch ``embed_queries`` when it has one, else one ``embed_query`` per prototype.
        ``counts`` records attempts even when the load fails; a failed or partial load is never cached.
        """
        with self._lock:
            if self._cache is not None and self._cache[0] == key:
                return self._cache[1]
            counts['prototype_calls'] += 1
            texts = [text for _, text in self._prototypes]
            embed_queries = getattr(self._client, 'embed_queries', None)
            if callable(embed_queries):
                counts['prototype_requests'] += 1
                batch_size = getattr(getattr(self._client, 'settings', None), 'batch_size', None)
                counts['prototype_batches'] = (math.ceil(len(texts) / batch_size) if isinstance(batch_size, int)
                                               and not isinstance(batch_size, bool) and batch_size > 0 else None)
                raw = embed_queries(texts)
                if isinstance(raw, (str, bytes)) or len(raw) != len(texts):
                    raise ValueError('wrong prototype vector count')
            else:
                raw = []
                for text in texts:
                    counts['prototype_requests'] += 1
                    counts['prototype_batches'] = counts['prototype_requests']
                    raw.append(self._client.embed_query(text))
            vectors = tuple((kind, _unit(value, key[2])) for (kind, _), value in zip(self._prototypes, raw, strict=True))
            self._cache = (key, vectors)
            return vectors

    def warm(self):
        """Load the prototype cache now; never raises."""
        try:
            self._prototype_vectors((PROTOTYPE_VERSION,) + _profile_key(self._client),
                                    {'prototype_calls': 0, 'prototype_requests': 0, 'prototype_batches': None})
            return True
        except Exception:
            return False

    def retrieve(self, question, limit=5):
        """Retrieve individual examples for structured interpretation, including low-margin kind matches.

        Returns no examples on an embedding failure; a caller must never reuse an example's answer or slots.
        """
        try:
            if not isinstance(question, str) or not question.strip() or type(limit) is not int or not 1 <= limit <= 8:
                return []
            model, dimensions, normalized = _profile_key(self._client)
            vectors = self._prototype_vectors(
                (PROTOTYPE_VERSION, model, dimensions, normalized),
                {'prototype_calls': 0, 'prototype_requests': 0, 'prototype_batches': None})
            query = _unit(self._client.embed_query(question), dimensions)
            ranked = sorted(zip(self._prototypes, vectors, strict=True),
                            key=lambda pair: -sum(a*b for a, b in zip(query, pair[1][1], strict=True)))
            return [{'kind': kind, 'question': text,
                     'score': round(sum(a*b for a, b in zip(query, vector, strict=True)), 6)}
                    for (kind, text), (_, vector) in ranked[:limit]]
        except Exception:
            return []

    def classify(self, question):
        """KindCandidates for ``question``; never raises."""
        started = time.perf_counter()
        counts = {'embedding_calls': 0, 'prototype_calls': 0, 'prototype_requests': 0, 'prototype_batches': None}
        model = None
        try:
            model, dimensions, normalized = _profile_key(self._client)
            if not isinstance(question, str) or not question.strip():
                raise ValueError('question must be text')
            vectors = self._prototype_vectors((PROTOTYPE_VERSION, model, dimensions, normalized), counts)
            counts['embedding_calls'] += 1
            query = _unit(self._client.embed_query(question), dimensions)
            ranked = rank_kinds(query, vectors)[:TOP_K]
            margin = ranked[0][1] - ranked[1][1]
            confident = ranked[0][1] >= self._confidence and margin >= self._margin
            return KindCandidates(tuple((kind, round(score, 6)) for kind, score in ranked), round(margin, 6),
                                  'ok' if confident else 'below_threshold', PROTOTYPE_VERSION, model,
                                  (time.perf_counter() - started) * 1000, **counts)
        except Exception:
            # Transport/configuration details are diagnostics, never chat content.
            return KindCandidates(status='unavailable', model=model if isinstance(model, str) else None,
                                  elapsed_ms=(time.perf_counter() - started) * 1000, **counts)
