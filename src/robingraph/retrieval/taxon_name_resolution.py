"""Graph-first taxon name resolution with embedding-only candidate suggestions.

A mention is matched only by the active reference graph: first the exact
(NFC-normalized) text, then, for Korean name-shaped input, the same text with
its internal spacing removed.  Embedding cosine similarity is used only when
the graph has no exact answer, and only to *suggest* up to three species whose
scientific names are re-resolved through the graph under the same active
context.  A suggestion is never a match: the score is a ranking signal, not a
confidence that the mention names that species.

Nothing here writes to a database or persists aliases/query nodes; the only
state is a bounded, process-local cache of candidate-name vectors.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import math
import re
import threading
import unicodedata
from typing import Any, Callable, Mapping, Sequence

from .taxonomy_lineage import TaxonomyLineage


MAX_MENTION_CHARS = 80
MAX_CANDIDATE_TEXT_CHARS = 200
MAX_INVENTORY = 1000
CACHE_MAX_ENTRIES = 1000
MAX_SUGGESTIONS = 3
# Verify at most this many above-floor candidates through the graph per call.
MAX_VERIFICATIONS = 10
# Cosine floor for *suggesting* a name, calibrated on TEST Jina vectors over
# Korean display names (typos scored 0.29-0.35 to the intended species,
# unrelated words at most 0.20). It is not a confidence or probability, and a
# suggestion above it never becomes a match.
SUGGESTION_COSINE_FLOOR = 0.25
# Only short, name-shaped mentions are embedded; a sentence is not a name.
MAX_VECTOR_MENTION_CHARS = 40
MAX_VECTOR_TOKENS = 4
_SENTENCE_MARKS = re.compile(r"[?!.,;:？！。\n]")

ResolveExact = Callable[[str], "TaxonomyLineage | None"]
LoadCandidates = Callable[[], Sequence[Mapping[str, Any]]]
ActiveContext = Callable[[], "tuple[str, str] | None"]

_KOREAN_NAME = re.compile(r"[가-힣]+(?:\s+[가-힣]+){1,3}")
_CANDIDATE_FIELDS = ("taxon_id", "scientific_name", "display_name", "text")


class _Unavailable(Exception):
    """Internal signal: a dependency failed or returned unusable data."""


def _result(mention: str, status: str, method: str, *, canonical_name: str | None = None,
            taxon_id: str | None = None, candidates: Sequence[dict] = (),
            context: tuple[str, str] | None = None) -> dict:
    # concept_set_id/taxonomy_release are set only for matched and candidates
    # results so callers can confirm the profile they load is the same context.
    return {"mention": mention, "status": status, "method": method,
            "canonical_name": canonical_name, "taxon_id": taxon_id,
            "concept_set_id": context[0] if context else None,
            "taxonomy_release": context[1] if context else None,
            "candidates": [dict(candidate) for candidate in candidates]}


def normalize_mention(mention: Any) -> str | None:
    """NFC-normalize and trim a mention; None when it is not a bounded name."""
    if not isinstance(mention, str):
        return None
    value = " ".join(unicodedata.normalize("NFC", mention).split())
    if not value or len(value) > MAX_MENTION_CHARS:
        return None
    return value


def compact_korean_name(value: str) -> str | None:
    """Remove spacing only inside a short, Korean name-shaped mention."""
    if _KOREAN_NAME.fullmatch(value):
        return re.sub(r"\s+", "", value)
    return None


def _valid_context(value: Any) -> tuple[str, str] | None:
    if (isinstance(value, tuple) and len(value) == 2
            and all(isinstance(part, str) and part.strip() for part in value)):
        return value
    return None


def _lineage_target(lineage: Any, context: tuple[str, str]):
    """The queried taxon of a lineage, or None if it is not from ``context``."""
    if not isinstance(lineage, TaxonomyLineage) or not lineage.items:
        return None
    if (lineage.concept_set_id, lineage.taxonomy_release) != context:
        return None
    target = lineage.items[-1]
    resolved = lineage.resolved_query_scientific_name
    if resolved is not None and resolved != target.scientific_name:
        return None
    if not target.taxon_id or not target.scientific_name:
        return None
    return target


def _validate_vector(vector: Any, dimensions: int) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        raise _Unavailable
    values = []
    for item in vector:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise _Unavailable
        item = float(item)
        if not math.isfinite(item):
            raise _Unavailable
        values.append(item)
    if len(values) != dimensions:
        raise _Unavailable
    # hypot avoids intermediate overflow; a norm that is still inf (or 0) is
    # unusable. Unit vectors keep every later dot product within [-1, 1].
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0.0:
        raise _Unavailable
    unit = tuple(item / norm for item in values)
    if not all(math.isfinite(item) for item in unit):
        raise _Unavailable
    return unit


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    score = math.fsum(a * b for a, b in zip(left, right))
    if not math.isfinite(score):
        raise _Unavailable
    return max(-1.0, min(1.0, score))


def _validate_inventory(raw: Any) -> list[dict]:
    if isinstance(raw, (str, bytes, Mapping)) or not isinstance(raw, Sequence):
        raise _Unavailable
    if len(raw) > MAX_INVENTORY:
        raise _Unavailable
    inventory, ids, names = [], set(), set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise _Unavailable
        values = {}
        for field in _CANDIDATE_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise _Unavailable
            values[field] = unicodedata.normalize("NFC", value.strip())
        if len(values["text"]) > MAX_CANDIDATE_TEXT_CHARS:
            raise _Unavailable
        key = values["scientific_name"].casefold()
        # A duplicated identity makes the inventory ambiguous; refuse it whole.
        if values["taxon_id"] in ids or key in names:
            raise _Unavailable
        ids.add(values["taxon_id"])
        names.add(key)
        inventory.append(values)
    return inventory


class TaxonNameResolver:
    """Resolve a single name mention against the active reference graph."""

    def __init__(self, resolve_exact: ResolveExact, load_candidates: LoadCandidates,
                 embedding_client: Any = None, active_context: ActiveContext | None = None) -> None:
        if not callable(resolve_exact) or not callable(load_candidates) or not callable(active_context):
            raise TypeError("resolve_exact, load_candidates and active_context must be callable")
        self._resolve_exact = resolve_exact
        self._load_candidates = load_candidates
        self._embedding_client = embedding_client
        self._active_context = active_context
        self._cache: OrderedDict[tuple, tuple[float, ...]] = OrderedDict()
        self._lock = threading.Lock()
        self._build_lock = threading.Lock()

    def resolve(self, mention: Any) -> dict:
        raw = mention if isinstance(mention, str) else ""
        value = normalize_mention(mention)
        if value is None:
            return _result(raw, "not_found", "none")
        try:
            return {**self._resolve(value), "mention": raw}
        except Exception:
            # Never surface dependency exception details or a guessed taxon.
            return _result(raw, "unavailable", "none")

    def _context(self) -> tuple[str, str]:
        context = _valid_context(self._active_context())
        if context is None:
            raise _Unavailable
        return context

    def _graph(self, name: str, context: tuple[str, str]):
        lineage = self._resolve_exact(name)
        if lineage is None:
            return None
        target = _lineage_target(lineage, context)
        if target is None:
            # A lineage from another release/concept set is stale, not absent.
            raise _Unavailable
        return target

    def _resolve(self, value: str) -> dict:
        context = self._context()
        target = self._graph(value, context)
        if target is not None:
            return _result(value, "matched", "graph_exact", context=context,
                           canonical_name=target.scientific_name, taxon_id=target.taxon_id)
        compact = compact_korean_name(value)
        if compact is not None and compact != value:
            target = self._graph(compact, context)
            if target is not None:
                return _result(value, "matched", "graph_normalized", context=context,
                               canonical_name=target.scientific_name, taxon_id=target.taxon_id)
        if (len(value) > MAX_VECTOR_MENTION_CHARS or len(value.split()) > MAX_VECTOR_TOKENS
                or _SENTENCE_MARKS.search(value)):
            return _result(value, "not_found", "none")
        if self._embedding_client is None:
            # The graph has no exact name, but suggestions cannot be checked:
            # report the lookup as incomplete rather than as a confirmed absence.
            return _result(value, "unavailable", "none")
        candidates = self._suggest(value, context)
        if not candidates:
            return _result(value, "not_found", "none")
        return _result(value, "candidates", "vector", candidates=candidates, context=context)

    def _profile_key(self) -> tuple[tuple, int]:
        """The client's embedding profile; an incomplete profile fails closed."""
        profile = getattr(self._embedding_client, "profile", None)
        model = getattr(profile, "model", None)
        dimensions = getattr(profile, "dimensions", None)
        normalized = getattr(profile, "normalized", None)
        if (not isinstance(model, str) or not model.strip() or isinstance(dimensions, bool)
                or not isinstance(dimensions, int) or dimensions < 1 or not isinstance(normalized, bool)):
            raise _Unavailable
        return (type(self._embedding_client).__qualname__, model, dimensions, normalized), dimensions

    def _name_vectors(self, inventory: list[dict], context: tuple[str, str],
                      profile_key: tuple, dimensions: int) -> list[tuple[float, ...]]:
        keys = [(context, profile_key, entry["taxon_id"],
                 hashlib.sha256(entry["text"].encode("utf-8")).hexdigest()) for entry in inventory]
        vectors = self._cached(keys)
        if len(vectors) == len(keys):
            return [vectors[index] for index in range(len(keys))]
        # Single-flight fill: concurrent cold misses wait here and reuse the
        # vectors the first caller embedded instead of re-embedding them.
        with self._build_lock:
            vectors = self._cached(keys)
            missing = [index for index in range(len(keys)) if index not in vectors]
            if missing:
                embedded = self._embedding_client.embed_documents([inventory[i]["text"] for i in missing])
                if isinstance(embedded, (str, bytes)) or len(embedded) != len(missing):
                    raise _Unavailable
                fresh = {index: _validate_vector(vector, dimensions) for index, vector in zip(missing, embedded)}
                vectors.update(fresh)
                with self._lock:
                    for index, vector in fresh.items():
                        self._cache[keys[index]] = vector
                        self._cache.move_to_end(keys[index])
                    while len(self._cache) > CACHE_MAX_ENTRIES:
                        self._cache.popitem(last=False)
        return [vectors[index] for index in range(len(keys))]

    def _cached(self, keys: list[tuple]) -> dict[int, tuple[float, ...]]:
        with self._lock:
            found = {}
            for index, key in enumerate(keys):
                if key in self._cache:
                    self._cache.move_to_end(key)
                    found[index] = self._cache[key]
            return found

    def _suggest(self, value: str, context: tuple[str, str]) -> list[dict]:
        profile_key, dimensions = self._profile_key()
        inventory = _validate_inventory(self._load_candidates())
        if not inventory:
            raise _Unavailable  # no reviewed inventory for this context: cannot suggest
        name_vectors = self._name_vectors(inventory, context, profile_key, dimensions)
        query = _validate_vector(self._embedding_client.embed_query(value), dimensions)
        if self._context() != context:
            raise _Unavailable
        scored = sorted(((_cosine(query, vector), entry) for vector, entry in zip(name_vectors, inventory)),
                        key=lambda pair: (-round(pair[0], 6), pair[1]["taxon_id"]))
        suggestions: list[dict] = []
        for score, entry in scored[:MAX_VERIFICATIONS]:
            if score < SUGGESTION_COSINE_FLOOR or len(suggestions) >= MAX_SUGGESTIONS:
                break
            if self._verified_species(entry, context):
                suggestions.append({"taxon_id": entry["taxon_id"], "scientific_name": entry["scientific_name"],
                                    "display_name": entry["display_name"], "score": round(score, 4)})
        if self._context() != context:
            raise _Unavailable
        return suggestions

    def _verified_species(self, entry: dict, context: tuple[str, str]) -> bool:
        lineage = self._resolve_exact(entry["scientific_name"])
        if lineage is None:
            return False  # revoked or no longer active
        target = _lineage_target(lineage, context)
        if target is None:
            return False  # stale lineage from another release/concept set
        return (target.taxon_id == entry["taxon_id"] and target.rank == "species"
                and target.scientific_name.casefold() == entry["scientific_name"].casefold())
