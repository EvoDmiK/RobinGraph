"""Graph-first taxon name resolution with embedding-only candidate suggestions.

A mention is matched only by the active reference graph: first the exact
(NFC-normalized) text, then, for Korean name-shaped input, the same text with
its internal spacing removed.  Embedding cosine similarity is used only when
the graph has no exact answer, and only to *suggest* up to three species whose
scientific names are re-resolved through the graph under the same active
context.  A suggestion is never a match: the score is a ranking signal, not a
confidence that the mention names that species.

Nothing here writes to a database or persists aliases/query nodes. Candidate
vectors are indexed separately; the request path embeds only the mention.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Callable, Mapping, Sequence

from .taxonomy_lineage import LineageTaxon, TaxonomyLineage
from .species_scope import scope_matches, with_species_scope


MAX_MENTION_CHARS = 80
MAX_CANDIDATE_TEXT_CHARS = 200
MAX_INVENTORY = 1000
MAX_SUGGESTIONS = 3
# Verify at most this many above-floor candidates through the graph per call.
MAX_VERIFICATIONS = 10
# Cosine floor for *suggesting* a name, calibrated on TEST Jina vectors over
# Korean display names (typos scored 0.29-0.35 to the intended species,
# unrelated words at most 0.20). It is not a confidence or probability, and a
# suggestion above it never becomes a match.
SUGGESTION_COSINE_FLOOR = 0.25
# A lower score is usable only as a confirmation candidate with one-jamo spelling support.
SPELLING_COSINE_FLOOR = 0.20
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


def _one_jamo_substitution(value: str, display_name: str) -> bool:
    left, right = "".join(value.split()), "".join(display_name.split())
    # shortcut: only >=4-syllable names with one substituted jamo, not general edit correction.
    if (not re.fullmatch(r"[가-힣]{4,40}", left) or len(left) != len(right)
            or not re.fullmatch(r"[가-힣]+", right)):
        return False
    left, right = unicodedata.normalize("NFD", left), unicodedata.normalize("NFD", right)
    return len(left) == len(right) and sum(a != b for a, b in zip(left, right)) == 1


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


def _one_latin_edit(value: str, canonical: str | None) -> bool:
    """Confirmation only: one edit in a bounded Latin source name."""
    if not canonical or len(value) < 4 or len(canonical) < 3:
        return False
    if not all(re.fullmatch(r"[A-Za-z]+(?:[ -][A-Za-z]+)*", text) for text in (value, canonical)):
        return False
    left, right = value.casefold(), canonical.casefold()
    if left == right or abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        different = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return (len(different) == 1 or (len(different) == 2
            and different[1] == different[0] + 1
            and left[different[0]] == right[different[1]]
            and left[different[1]] == right[different[0]]))
    short, long = (left, right) if len(left) < len(right) else (right, left)
    first = next((i for i, (a, b) in enumerate(zip(short, long)) if a != b), len(short))
    return short[first:] == long[first + 1:]


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
                 embedding_client: Any = None, active_context: ActiveContext | None = None,
                 candidate_search: Callable[..., Sequence[Mapping[str, Any]]] | None = None) -> None:
        if not callable(resolve_exact) or not callable(load_candidates) or not callable(active_context):
            raise TypeError("resolve_exact, load_candidates and active_context must be callable")
        self._resolve_exact = resolve_exact
        self._load_candidates = load_candidates
        self._embedding_client = embedding_client
        self._active_context = active_context
        self._candidate_search = candidate_search

    def resolve(self, mention: Any, species_scope="all") -> dict:
        raw = mention if isinstance(mention, str) else ""
        value = normalize_mention(mention)
        if value is None:
            return _result(raw, "not_found", "none")
        try:
            return {**self._resolve(value, species_scope), "mention": raw}
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

    def _resolve(self, value: str, species_scope="all") -> dict:
        context = self._context()
        target = self._graph(value, context)
        if target is not None:
            if not scope_matches(vars(target), species_scope, *context):
                return _result(value, "not_found", "none")
            return _result(value, "matched", "graph_exact", context=context,
                           canonical_name=target.scientific_name, taxon_id=target.taxon_id)
        compact = compact_korean_name(value)
        if compact is not None and compact != value:
            target = self._graph(compact, context)
            if target is not None:
                if not scope_matches(vars(target), species_scope, *context):
                    return _result(value, "not_found", "none")
                return _result(value, "matched", "graph_normalized", context=context,
                               canonical_name=target.scientific_name, taxon_id=target.taxon_id)
        if (len(value) > MAX_VECTOR_MENTION_CHARS or len(value.split()) > MAX_VECTOR_TOKENS
                or _SENTENCE_MARKS.search(value)):
            return _result(value, "not_found", "none")
        if self._embedding_client is None or not callable(self._candidate_search):
            # The graph has no exact name, but suggestions cannot be checked:
            # report the lookup as incomplete rather than as a confirmed absence.
            return _result(value, "unavailable", "none")
        candidates = self._suggest(compact or value, context, species_scope)
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

    def _suggest(self, value: str, context: tuple[str, str], species_scope="all",
                 *, query_vector=None) -> list[dict]:
        profile_key, dimensions = self._profile_key()
        inventory = _validate_inventory(self._load_candidates())
        if not inventory:
            raise _Unavailable  # no reviewed inventory for this context: cannot suggest
        query = _validate_vector(self._embedding_client.embed_query(value)
                                 if query_vector is None else query_vector, dimensions)
        if self._context() != context:
            raise _Unavailable
        parameters = {}
        if species_scope != 'all':
            parameters['eligible_taxon_ids'] = [entry['taxon_id'] for entry in inventory
                if scope_matches({**entry, 'rank': 'species'}, species_scope, *context)]
            if not parameters['eligible_taxon_ids']:
                return []
        hits = self._candidate_search(query, self._embedding_client.profile, context, inventory,
                                      limit=MAX_VERIFICATIONS, **parameters)
        if isinstance(hits, (str, bytes, Mapping)) or not isinstance(hits, Sequence) or len(hits) > MAX_VERIFICATIONS:
            raise _Unavailable
        allowed = {entry["taxon_id"]: entry for entry in inventory}
        scored, seen = [], set()
        for hit in hits:
            if not isinstance(hit, Mapping):
                raise _Unavailable
            entry = allowed.get(hit.get("taxon_id"))
            score = hit.get("score")
            if (entry is None or entry["taxon_id"] in seen
                    or any(hit.get(key) != entry[key] for key in _CANDIDATE_FIELDS)
                    or isinstance(score, bool) or not isinstance(score, (int, float))
                    or not math.isfinite(score) or not -1 <= score <= 1):
                raise _Unavailable
            seen.add(entry["taxon_id"])
            scored.append((float(score), entry))
        if self._profile_key()[0] != profile_key:
            raise _Unavailable
        # Recheck scope defensively even when the repository ranked within it.
        scored = [(score, entry) for score, entry in scored
                  if scope_matches({**entry, "rank":"species"}, species_scope, *context)]
        scored.sort(key=lambda pair: (-round(pair[0], 6), pair[1]["taxon_id"]))
        eligible = [(score, entry) for score, entry in scored[:MAX_VERIFICATIONS]
                    if score >= SUGGESTION_COSINE_FLOOR]
        if not eligible:
            eligible = [(score, entry) for score, entry in scored[:MAX_VERIFICATIONS]
                        if score >= SPELLING_COSINE_FLOOR
                        and _one_jamo_substitution(value, entry["display_name"])]
        verified = {}
        # Latin source names in the reviewed outside set may need spelling
        # support below the vector floor. Keep the measured cosine unchanged.
        if not eligible and species_scope == 'outside':
            for score, entry in scored[:MAX_VERIFICATIONS]:
                target = self._verified_target(entry, context)
                verified[entry['taxon_id']] = target
                if target is not None and any(_one_latin_edit(value, name)
                        for name in (target.english_name, target.scientific_name)):
                    eligible.append((score, entry))
        if (not eligible and species_scope == 'all' and len(value) >= 4
                and re.fullmatch(r"[A-Za-z]+(?:[ -][A-Za-z]+)*", value)):
            # Reuse the query vector; only the reviewed outside set supplies
            # this spelling fallback, and all keeps its Korean-first labels.
            outside = self._suggest(value, context, 'outside', query_vector=query)
            for candidate in outside:
                entry = allowed.get(candidate['taxon_id'])
                if entry is None or entry['scientific_name'] != candidate['scientific_name']:
                    raise _Unavailable
                candidate['display_name'] = entry['display_name']
            if self._profile_key()[0] != profile_key or self._context() != context:
                raise _Unavailable
            return outside
        suggestions: list[dict] = []
        for score, entry in eligible:
            if len(suggestions) >= MAX_SUGGESTIONS:
                break
            target = (verified[entry['taxon_id']] if entry['taxon_id'] in verified
                      else self._verified_target(entry, context))
            if target is not None:
                suggestions.append({"taxon_id": entry["taxon_id"], "scientific_name": entry["scientific_name"],
                                    "display_name": (entry["display_name"] if species_scope == "all" else
                                        with_species_scope({**vars(target), "korean_name":target.korean_name or entry["display_name"]}, species_scope, *context)["display_name"]), "score": round(score, 4)})
        if self._context() != context:
            raise _Unavailable
        return suggestions

    def _verified_target(self, entry: dict, context: tuple[str, str]) -> LineageTaxon | None:
        lineage = self._resolve_exact(entry["scientific_name"])
        if lineage is None:
            return None  # revoked or no longer active
        target = _lineage_target(lineage, context)
        if target is None:
            return None  # stale lineage from another release/concept set
        if (target.taxon_id == entry["taxon_id"] and target.rank == "species"
                and target.scientific_name.casefold() == entry["scientific_name"].casefold()):
            return target
        return None
