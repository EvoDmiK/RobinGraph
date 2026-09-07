"""Neo4j fixture-only fulltext/vector chunk indexing and hybrid search.

Consumes the shared embedding contract documented in
`docs/next-implementation-batch.md` (`EmbeddingProfile` / `EmbeddedChunk` /
`EmbeddingClient`, owned and implemented by `robingraph.embeddings`)
structurally, via the `EmbeddingProfileLike` / `EmbeddedChunkLike` /
`QueryEmbedderLike` `Protocol`s below, instead of importing those concrete
classes. This module never imports `robingraph.embeddings` and never speaks
HTTP: it only reads the `chunk_id` / `content_hash` / `vector` / `profile`
shape off whatever embedded-chunk objects it is given. Any real
`robingraph.embeddings.EmbeddedChunk` instance already satisfies these
Protocols without modification, so this module has no build-order or import
dependency on that concurrently-developed adapter.

Two index-time write paths and one search-time read path, kept strictly
separate:

- `bootstrap_hybrid_search_schema` -- explicit schema write. Creates the
  fulltext and vector indexes if absent. Never called implicitly by indexing
  or search.
- `index_chunks` -- explicit data write. Given the *complete current* set of
  eligible `EmbeddedChunk`s (as `embed_fixture_chunks` produces after
  rechecking policy), atomically (one write transaction) writes a current
  vector onto every chunk in that set and clears the vector off every
  previously-indexed chunk that is *not* in it. Because eligibility, content
  hash, and profile compatibility are exactly the conditions the input set
  already encodes, this one full-replace pass is what invalidates vectors
  after a changed chunk text/hash, a revoked embedding permission, or an
  embedding-profile change -- there is no separate "diff against the old
  vector" step that could observe a half-updated state.
- `search` -- read-only. Runs fulltext (always) and vector (only given a
  `query_embedder` and a compatible index), re-verifies the two-sided
  chunk+document license chain for every hit before it can appear in a
  result (fail-closed, matching `retrieval.neo4j_repository`'s pattern), and
  fuses the surviving rankings via `retrieval.hybrid`.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Protocol, Sequence

from neo4j import GraphDatabase

from ..graph.settings import Neo4jSettings
from .hybrid import (
    FULLTEXT_CHANNEL,
    VECTOR_CHANNEL,
    VECTOR_UNAVAILABLE_WARNING,
    DEFAULT_RRF_K,
    HybridSearchOutcome,
    fuse_hybrid_results,
)
from .repository import SourceCitation


# -- shared embedding contract, consumed structurally (see module docstring) --


class EmbeddingProfileLike(Protocol):
    model: str
    dimensions: int
    normalized: bool


class EmbeddedChunkLike(Protocol):
    chunk_id: str
    content_hash: str
    vector: Sequence[float]
    profile: EmbeddingProfileLike


class QueryEmbedderLike(Protocol):
    profile: EmbeddingProfileLike

    def embed_query(self, text: str) -> Sequence[float]: ...


# -- schema (dedicated fixture search label/property) -------------------------

# Every fixture Chunk already carries this label (added alongside
# Chunk/RobinGraph/Fixture in neo4j_client._load_fixture_tx), so the fulltext
# index is scoped to exactly -- and only -- the fixture chunk corpus, never to
# an unrelated `:Chunk` node a future feature might create outside this
# label. Reconciliation deletes the whole node (see neo4j_client.py), so a
# chunk losing eligibility loses this label automatically without any extra
# bookkeeping here.
HYBRID_SEARCH_LABEL = "HybridSearchChunk"

# Applied only to chunks that currently carry a content-hash-matched,
# profile-compatible vector (set/cleared by index_chunks). A chunk can be
# HYBRID_SEARCH_LABEL without HYBRID_VECTOR_LABEL (fulltext-only, no
# embedding yet or embedding denied) but never the reverse.
HYBRID_VECTOR_LABEL = "HybridVectorChunk"

HYBRID_VECTOR_PROPERTY = "hybrid_vector"

DEFAULT_FULLTEXT_INDEX_NAME = "robingraphFixtureChunkFulltext"
DEFAULT_VECTOR_INDEX_NAME = "robingraphFixtureChunkVector"

# Neo4j's fulltext indexes are Lucene-backed. `standard-no-stop-words` is the
# built-in default and is what earlier Neo4j releases exposed as
# `db.index.fulltext.listAvailableAnalyzers()`'s first/default entry -- it
# tokenizes on Unicode word boundaries and removes no stop words. It has no
# Korean-specific handling: Korean text has no whitespace between words the
# way English does, and the standard analyzer's word-boundary tokenizer does
# not segment Korean morphemes, so a query for a substring of a compound
# Korean word/phrase will often fail to match even though the same substring
# would match a `LIKE`-style scan. Neo4j does ship a Lucene `cjk` analyzer
# (bigram-based, covers Chinese/Japanese/Korean together) which is more
# forgiving for unsegmented Korean than the default, but it is not a
# linguistically-aware Korean analyzer (no morphological analysis, unlike
# e.g. Elasticsearch's Nori) -- expect materially worse fulltext recall/
# precision on Korean phrasing than on English, with either analyzer. This
# was not independently re-verified against a live server in this session;
# `CALL db.index.fulltext.listAvailableAnalyzers()` should be run against the
# actual disposable Neo4j 2026.07.1 instance to confirm `cjk` is present
# before relying on it, and a Korean-specific analyzer plugin should be
# evaluated before this ships past the fixture stage.
DEFAULT_FULLTEXT_ANALYZER = "standard-no-stop-words"
DEFAULT_SIMILARITY_FUNCTION = "cosine"


# Index/label names are interpolated directly into `CREATE FULLTEXT/VECTOR
# INDEX <name> ...` below because Cypher DDL does not allow parameterizing
# identifiers -- only values. `HybridSchemaConfig` is caller-supplied, so
# without this check a config carrying attacker- or bug-controlled index
# names could inject arbitrary Cypher into that DDL statement.
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class HybridSchemaConfig:
    fulltext_index_name: str = DEFAULT_FULLTEXT_INDEX_NAME
    vector_index_name: str = DEFAULT_VECTOR_INDEX_NAME
    fulltext_analyzer: str = DEFAULT_FULLTEXT_ANALYZER
    similarity_function: str = DEFAULT_SIMILARITY_FUNCTION

    def __post_init__(self) -> None:
        for field_name in ("fulltext_index_name", "vector_index_name"):
            value = getattr(self, field_name)
            if not _SAFE_IDENTIFIER.match(value):
                raise ValueError(f"HybridSchemaConfig.{field_name} must match {_SAFE_IDENTIFIER.pattern!r}: {value!r}")


def _run(session: Any, query: str, **parameters: Any) -> list[dict[str, Any]]:
    return session.run(query, **parameters).data()


def _verify_search_index(session: Any, name: str, index_type: str, label: str, property_name: str,
                         expected_config: dict[str, Any]) -> None:
    rows = _run(session, "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options "
                "WHERE name = $name RETURN type, labelsOrTypes, properties, options", name=name)
    if not rows:
        raise ValueError("Requested search index was not created; an equivalent schema may exist under another name")
    row = rows[0]
    if row['type'] != index_type or row['labelsOrTypes'] != [label] or row['properties'] != [property_name]:
        raise ValueError("Existing search index does not match the configured fixture schema")
    actual = row['options']['indexConfig']
    if 'vector.similarity_function' in actual:
        actual['vector.similarity_function'] = actual['vector.similarity_function'].lower()
    if any(actual.get(key) != value for key, value in expected_config.items()):
        raise ValueError("Existing search index configuration is incompatible; migrate it explicitly")
    _run(session, "CALL db.awaitIndex($name, 30)", name=name)


def bootstrap_hybrid_search_schema(
    settings: Neo4jSettings,
    *,
    dimensions: int | None,
    config: HybridSchemaConfig = HybridSchemaConfig(),
) -> None:
    """Explicit schema write: create the fixture fulltext/vector indexes if absent.

    The fulltext index is always created. `dimensions=None` means no
    embedding client is configured (the keyword-only default) -- this
    creates *only* the fulltext index and leaves the vector index alone,
    matching `search`'s keyword-only fallback: without a vector index there
    is nothing for `index_chunks` to write into and no fabricated vector
    fills the gap.

    When `dimensions` is given, it must equal the active
    `EmbeddingProfile.dimensions` used by `index_chunks`; a vector index is
    fixed to one dimensionality for its lifetime. If a vector index by this
    name already exists with a *different* `vector.dimensions`, this raises
    rather than silently leaving the old, now-incompatible index in place --
    `CREATE VECTOR INDEX ... IF NOT EXISTS` alone would no-op and mask the
    mismatch.
    """

    if dimensions is not None and dimensions < 1:
        raise ValueError("dimensions must be a positive integer or None")

    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            _run(
                session,
                f"CREATE FULLTEXT INDEX {config.fulltext_index_name} IF NOT EXISTS "
                f"FOR (n:{HYBRID_SEARCH_LABEL}) ON EACH [n.text] "
                "OPTIONS {indexConfig: {`fulltext.analyzer`: $analyzer, `fulltext.eventually_consistent`: false}}",
                analyzer=config.fulltext_analyzer,
            )
            _verify_search_index(session, config.fulltext_index_name, 'FULLTEXT', HYBRID_SEARCH_LABEL, 'text',
                                 {'fulltext.analyzer': config.fulltext_analyzer, 'fulltext.eventually_consistent': False})
            if dimensions is None:
                return
            existing = _run(
                session,
                "SHOW VECTOR INDEXES YIELD name, options WHERE name = $name RETURN options",
                name=config.vector_index_name,
            )
            if existing:
                index_config = (existing[0].get("options") or {}).get("indexConfig") or {}
                existing_dimensions = index_config.get("vector.dimensions")
                if existing_dimensions is not None and int(existing_dimensions) != dimensions:
                    raise ValueError(
                        f"Vector index {config.vector_index_name!r} already exists with "
                        f"vector.dimensions={existing_dimensions}, which does not match the "
                        f"requested dimensions={dimensions}. Drop the existing index explicitly "
                        "before bootstrapping with a new embedding profile."
                    )
            _run(
                session,
                f"CREATE VECTOR INDEX {config.vector_index_name} IF NOT EXISTS "
                f"FOR (n:{HYBRID_VECTOR_LABEL}) ON (n.{HYBRID_VECTOR_PROPERTY}) "
                "OPTIONS {indexConfig: {`vector.dimensions`: toInteger($dimensions), "
                "`vector.similarity_function`: $similarity_function}}",
                dimensions=dimensions,
                similarity_function=config.similarity_function,
            )
            _verify_search_index(session, config.vector_index_name, 'VECTOR', HYBRID_VECTOR_LABEL, HYBRID_VECTOR_PROPERTY,
                                 {'vector.dimensions': dimensions, 'vector.similarity_function': config.similarity_function})


# -- indexing (explicit data write, atomic invalidation) -----------------------


@dataclass(frozen=True)
class ChunkIndexReport:
    indexed: tuple[str, ...]
    invalidated: tuple[str, ...]
    skipped: tuple[str, ...]


# Fail-closed at the write itself, not just at search time: even though
# index_chunks's caller is expected to have already restricted
# embedded_chunks to the currently policy-/embedding-eligible set (see
# embeddings.embed_fixture_chunks), this query does not trust that -- an
# untrusted or stale-computed EmbeddedChunk batch cannot write a vector onto
# a chunk whose live two-sided license chain is not 'allowed' (dataset.
# policy_status, per-source rather than the URI-shared License node -- see
# neo4j_client._MERGE_SOURCE_AND_LICENSE) or whose document no longer has
# embedding_allowed. A row failing this MATCH/WHERE simply is not in
# written_ids and is reported back to the caller via ChunkIndexReport.skipped.
_INDEX_WRITE_QUERY = f"""
UNWIND $rows AS row
MATCH (d:Document:RobinGraph:Fixture)-[:HAS_CHUNK]->(c:Chunk:RobinGraph:Fixture:{HYBRID_SEARCH_LABEL} {{id: row.chunk_id}})
MATCH (c)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(chunkDataset:SourceDataset)-[:LICENSED_UNDER]->(:License)
MATCH (d)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(documentDataset:SourceDataset)-[:LICENSED_UNDER]->(:License)
WHERE c.content_hash = row.content_hash
  AND chunkDataset.policy_status = 'allowed'
  AND documentDataset.policy_status = 'allowed'
  AND d.embedding_allowed = true
SET c.{HYBRID_VECTOR_PROPERTY} = row.vector,
    c.hybrid_model = row.model,
    c.hybrid_dimensions = row.dimensions,
    c.hybrid_normalized = row.normalized,
    c.hybrid_content_hash = row.content_hash,
    c.hybrid_indexed_at = $indexed_at
SET c:{HYBRID_VECTOR_LABEL}
RETURN collect(c.id) AS written_ids
"""

_INVALIDATE_STALE_QUERY = f"""
MATCH (c:Chunk:RobinGraph:Fixture:{HYBRID_VECTOR_LABEL})
WHERE NOT c.id IN $keep_ids
WITH c, c.id AS stale_id
REMOVE c:{HYBRID_VECTOR_LABEL}
REMOVE c.{HYBRID_VECTOR_PROPERTY}, c.hybrid_model, c.hybrid_dimensions, c.hybrid_normalized,
       c.hybrid_content_hash, c.hybrid_indexed_at
RETURN collect(stale_id) AS invalidated_ids
"""


def validate_embedded_chunks(
    embedded_chunks: Sequence[EmbeddedChunkLike], *, expected_profile: EmbeddingProfileLike
) -> None:
    """Pure precondition check for `index_chunks`: no I/O, no driver connection.

    Every chunk must carry exactly `expected_profile` (model, dimensions,
    normalized), a unique `chunk_id` within the batch, and a vector that is
    the right length, entirely finite (no NaN/Inf), and -- when
    `expected_profile.normalized` -- L2-normalized to within a small
    tolerance. `embedded_chunks` is treated as untrusted input (it may come
    from a stale computation or a buggy/adversarial caller, not only from
    `embeddings.embed_fixture_chunks`), so this is checked here rather than
    assumed. Raises `ValueError` on the first violation. Exposed separately
    so callers -- and this module's own offline tests -- can verify a batch
    of embedded chunks (including a real `robingraph.embeddings.EmbeddedChunk`)
    satisfies this precondition without opening a connection.
    """

    seen_chunk_ids: set[str] = set()
    for chunk in embedded_chunks:
        if chunk.chunk_id in seen_chunk_ids:
            raise ValueError(f"Duplicate embedded chunk id: {chunk.chunk_id!r}")
        seen_chunk_ids.add(chunk.chunk_id)

        profile = chunk.profile
        if (profile.model, profile.dimensions, profile.normalized) != (
            expected_profile.model,
            expected_profile.dimensions,
            expected_profile.normalized,
        ):
            raise ValueError(f"Embedded chunk {chunk.chunk_id!r} uses an incompatible embedding profile")
        if len(chunk.vector) != profile.dimensions:
            raise ValueError(
                f"Embedded chunk {chunk.chunk_id!r} vector length {len(chunk.vector)} "
                f"does not match its declared dimensions {profile.dimensions}"
            )
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in chunk.vector):
            raise ValueError(f"Embedded chunk {chunk.chunk_id!r} vector contains a non-finite or non-numeric value")
        if profile.normalized:
            norm = math.hypot(*chunk.vector)
            if not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
                raise ValueError(f"Embedded chunk {chunk.chunk_id!r} vector is not L2-normalized as its profile declares")


def _index_rows(embedded_chunks: Sequence[EmbeddedChunkLike]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "content_hash": chunk.content_hash,
            "vector": list(chunk.vector),
            "model": chunk.profile.model,
            "dimensions": chunk.profile.dimensions,
            "normalized": chunk.profile.normalized,
        }
        for chunk in embedded_chunks
    ]


def _index_chunks_tx(tx: Any, rows: list[dict[str, Any]], indexed_at: str) -> tuple[list[str], list[str]]:
    written = _run(tx, _INDEX_WRITE_QUERY, rows=rows, indexed_at=indexed_at)
    written_ids: list[str] = written[0]["written_ids"] if written else []
    invalidated = _run(tx, _INVALIDATE_STALE_QUERY, keep_ids=written_ids)
    invalidated_ids: list[str] = invalidated[0]["invalidated_ids"] if invalidated else []
    return written_ids, invalidated_ids


def index_chunks(
    settings: Neo4jSettings,
    embedded_chunks: Sequence[EmbeddedChunkLike],
    *,
    expected_profile: EmbeddingProfileLike,
    indexed_at: str,
) -> ChunkIndexReport:
    """Write path: (re)index `embedded_chunks` as the complete current eligible set.

    Every `embedded_chunks` entry must carry exactly `expected_profile`
    (model, dimensions, normalized) and a vector whose length matches its own
    `profile.dimensions`; a mismatch raises before any write happens (no
    partial index). Validation runs before opening a driver connection, so a
    caller can unit test it without a live Neo4j server.

    Within one write transaction: every chunk in `embedded_chunks` whose
    `content_hash` still matches the live `Chunk.content_hash`, and whose
    current two-sided (chunk + document) `SourceDataset.policy_status` and
    document `embedding_allowed` are still `'allowed'`/`true` on the live
    graph, gets its vector (re)written; any chunk currently carrying a
    vector that fell out of `embedded_chunks` -- or whose row failed one of
    those live rechecks -- has its vector cleared and is reported in
    `ChunkIndexReport.skipped`, not silently written anyway. This is the
    same one-transaction, full-replace-to-snapshot shape as
    `neo4j_client._reconcile_stale_nodes`, so no reader can ever observe a
    vector that is stale relative to the chunk's current text/hash or
    permission, and no untrusted or stale-computed `embedded_chunks` batch
    can write a vector the live graph would no longer permit.
    """

    validate_embedded_chunks(embedded_chunks, expected_profile=expected_profile)
    rows = _index_rows(embedded_chunks)

    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            written_ids, invalidated_ids = session.execute_write(_index_chunks_tx, rows, indexed_at)

    skipped_ids = sorted({row["chunk_id"] for row in rows} - set(written_ids))
    return ChunkIndexReport(
        indexed=tuple(sorted(written_ids)),
        invalidated=tuple(sorted(invalidated_ids)),
        skipped=tuple(skipped_ids),
    )


# -- search (read-only, fail-closed policy recheck) -----------------------------

_LUCENE_SPECIAL_CHARACTERS = '+-&|!(){}[]^"~*?:\\/'

# Lucene's standard QueryParser recognizes these as boolean/range operators
# only in ALL CAPS, outside a quoted phrase -- backslash-escaping (which
# handles _LUCENE_SPECIAL_CHARACTERS above) does not neutralize a keyword
# token like this the way it neutralizes a symbol. Lower-casing a
# whole-word match turns it back into an ordinary search term without
# affecting how the rest of the (typically Korean, case-insensitive-in-
# effect) query text is tokenized.
_LUCENE_BOOLEAN_KEYWORDS = re.compile(r"\b(AND|OR|NOT|TO)\b")


def escape_lucene_query_text(text: str) -> str:
    """Neutralize Lucene query-syntax operators/special characters in raw question text.

    `db.index.fulltext.queryNodes` parses its query-string argument as a full
    Lucene query (booleans, wildcards, field syntax, ...), not as literal
    text. Passing unescaped natural-language text -- Korean questions
    included, which routinely contain `?`, `(`, `)`, `~`, `-`, and
    occasionally a literal capitalized "AND"/"OR"/"NOT" -- can throw a Lucene
    parse error or silently change matching semantics (a literal search for
    the word "AND" would otherwise be parsed as the boolean operator).
    """

    without_operators = _LUCENE_BOOLEAN_KEYWORDS.sub(lambda match: match.group(0).lower(), text)
    return "".join(
        f"\\{character}" if character in _LUCENE_SPECIAL_CHARACTERS else character for character in without_operators
    )


_FULLTEXT_SEARCH_QUERY = """
CALL db.index.fulltext.queryNodes($index_name, $query_text) YIELD node, score
RETURN node.id AS chunk_id, score
ORDER BY score DESC, chunk_id ASC
LIMIT $top_k
"""

# Re-verifies model/dimensions/normalized/content_hash directly on the node
# that matched, not merely that the index itself is dimensionally
# compatible: an index-level dimension check alone would not catch a chunk
# whose *own* hybrid_content_hash fell behind its current content_hash (e.g.
# a fixture reload landed a text/hash change a split second before this
# query -- neo4j_client._load_fixture_tx clears hybrid_* on that path too,
# but this is defense in depth, not a replacement for that) or one indexed
# under a since-superseded profile. A node failing this WHERE simply isn't
# returned -- there is no fallback vector to fabricate for it.
_VECTOR_SEARCH_QUERY = """
CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector) YIELD node, score
WHERE node.hybrid_content_hash = node.content_hash
  AND node.hybrid_model = $expected_model
  AND node.hybrid_dimensions = $expected_dimensions
  AND node.hybrid_normalized = $expected_normalized
RETURN node.id AS chunk_id, score
ORDER BY score DESC, chunk_id ASC
"""

# Fail-closed re-verification: even though only currently-eligible chunks
# should ever carry HYBRID_SEARCH_LABEL/HYBRID_VECTOR_LABEL, this recheck
# does not trust that -- it re-derives citability from the same two-sided
# chunk+document policy chain retrieval.neo4j_repository._CHUNKS_QUERY uses
# (checked against SourceDataset.policy_status, not License.policy_status --
# see neo4j_client._MERGE_SOURCE_AND_LICENSE for why License, keyed only by
# URI, can be shared across unrelated datasets), independently of whatever
# the fulltext/vector indexes returned. A chunk whose id is not returned
# here is dropped from every channel's ranking before fusion, never just
# from its citation. `embedding_allowed` is returned (not filtered here) so
# callers can additionally restrict the *vector* channel to it without
# affecting the fulltext channel, which only requires chunk/document
# storage permission, not embedding permission.
_RECHECK_AND_CITE_QUERY = """
UNWIND $chunk_ids AS chunk_id
MATCH (d:Document:RobinGraph:Fixture)-[:HAS_CHUNK]->(c:Chunk:RobinGraph:Fixture {id: chunk_id})
MATCH (c)-[:FROM_RECORD]->(sr:SourceRecord)-[:IN_DATASET]->(chunkDataset:SourceDataset)-[:LICENSED_UNDER]->(chunkLicense:License)
MATCH (d)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(documentDataset:SourceDataset)-[:LICENSED_UNDER]->(:License)
MATCH (e:EvidenceUnit:RobinGraph:Fixture {id: 'fixture-evidence:' + chunk_id})
WHERE chunkDataset.policy_status = 'allowed' AND documentDataset.policy_status = 'allowed'
RETURN c.id AS chunk_id, c.text AS text, chunkDataset.name AS source_id, chunkDataset.landing_uri AS source_url,
       coalesce(e.locator, sr.external_id) AS locator, chunkLicense.license_name AS license_name,
       d.embedding_allowed AS embedding_allowed
"""

_VECTOR_INDEX_CONFIG_QUERY = "SHOW VECTOR INDEXES YIELD name, options WHERE name = $name RETURN options"


# A fixture-scale sanity cap, not a product limit: bounds how many rows a
# single search call can pull through the Neo4j procedures/RRF before
# fusion, so a request built from unchecked input (this dataclass is public
# API, not only CLI-constructed with its own [1, 100] --limit clamp) cannot
# ask this module to rank an unbounded number of rows.
_MAX_SEARCH_BOUND = 500


@dataclass(frozen=True)
class HybridSearchRequest:
    query_text: str
    limit: int = 10
    fulltext_top_k: int = 25
    vector_top_k: int = 25
    rrf_k: int = DEFAULT_RRF_K
    channels: tuple[str, ...] = (FULLTEXT_CHANNEL, VECTOR_CHANNEL)

    def __post_init__(self) -> None:
        if not isinstance(self.query_text, str) or not self.query_text.strip():
            raise ValueError("Hybrid search question must not be blank")
        for field_name in ("limit", "fulltext_top_k", "vector_top_k"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_SEARCH_BOUND:
                raise ValueError(f"HybridSearchRequest.{field_name} must be between 1 and {_MAX_SEARCH_BOUND}: {value}")
        if isinstance(self.rrf_k, bool) or not isinstance(self.rrf_k, int) or self.rrf_k < 1:
            raise ValueError("HybridSearchRequest.rrf_k must be a positive integer")
        if not self.channels or any(channel not in {FULLTEXT_CHANNEL, VECTOR_CHANNEL} for channel in self.channels):
            raise ValueError("HybridSearchRequest.channels must contain fulltext and/or vector")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("HybridSearchRequest.channels must not contain duplicates")


class Neo4jHybridSearch:
    """Owns one driver connection for repeated `index_chunks`/`search` calls."""

    def __init__(self, settings: Neo4jSettings, *, config: HybridSchemaConfig = HybridSchemaConfig()) -> None:
        self._settings = settings
        self._config = config
        self._driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jHybridSearch":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def bootstrap_schema(self, *, dimensions: int | None) -> None:
        bootstrap_hybrid_search_schema(self._settings, dimensions=dimensions, config=self._config)

    def index_chunks(
        self, embedded_chunks: Sequence[EmbeddedChunkLike], *, expected_profile: EmbeddingProfileLike, indexed_at: str
    ) -> ChunkIndexReport:
        return index_chunks(self._settings, embedded_chunks, expected_profile=expected_profile, indexed_at=indexed_at)

    def _vector_index_dimensions(self, session: Any) -> int | None:
        rows = _run(session, _VECTOR_INDEX_CONFIG_QUERY, name=self._config.vector_index_name)
        if not rows:
            return None
        index_config = (rows[0].get("options") or {}).get("indexConfig") or {}
        dimensions = index_config.get("vector.dimensions")
        return int(dimensions) if dimensions is not None else None

    def search(self, request: HybridSearchRequest, *, query_embedder: QueryEmbedderLike | None = None) -> HybridSearchOutcome:
        """Read-only hybrid search: never writes, even to warm a missing index.

        Returns a bounded, deterministically-ranked, policy-rechecked result
        set. If `query_embedder` is omitted, or its profile does not match
        the live vector index's configured dimensions, or the vector index
        does not exist yet, this degrades to fulltext-only and reports why in
        `warnings` -- it never fabricates a vector to fill the gap.
        """

        warnings: list[str] = []
        with self._driver.session(database=self._settings.database) as session:
            fulltext_rows = (
                _run(
                    session,
                    _FULLTEXT_SEARCH_QUERY,
                    index_name=self._config.fulltext_index_name,
                    query_text=escape_lucene_query_text(request.query_text),
                    top_k=request.fulltext_top_k,
                )
                if FULLTEXT_CHANNEL in request.channels
                else []
            )
            fulltext_ranking = [row["chunk_id"] for row in fulltext_rows]

            vector_ranking: list[str] = []
            if VECTOR_CHANNEL not in request.channels:
                pass
            elif query_embedder is None:
                warnings.append(VECTOR_UNAVAILABLE_WARNING + ": no query embedder was provided")
            else:
                index_dimensions = self._vector_index_dimensions(session)
                if index_dimensions is None:
                    warnings.append(VECTOR_UNAVAILABLE_WARNING + ": the vector index has not been bootstrapped yet")
                elif index_dimensions != query_embedder.profile.dimensions:
                    warnings.append(
                        VECTOR_UNAVAILABLE_WARNING + ": query embedder dimensions "
                        f"({query_embedder.profile.dimensions}) do not match the vector index "
                        f"({index_dimensions})"
                    )
                else:
                    query_vector = list(query_embedder.embed_query(request.query_text))
                    vector_rows = _run(
                        session,
                        _VECTOR_SEARCH_QUERY,
                        index_name=self._config.vector_index_name,
                        top_k=request.vector_top_k,
                        query_vector=query_vector,
                        expected_model=query_embedder.profile.model,
                        expected_dimensions=query_embedder.profile.dimensions,
                        expected_normalized=query_embedder.profile.normalized,
                    )
                    vector_ranking = [row["chunk_id"] for row in vector_rows]

            candidate_ids = sorted({*fulltext_ranking, *vector_ranking})
            recheck_rows = _run(session, _RECHECK_AND_CITE_QUERY, chunk_ids=candidate_ids) if candidate_ids else []

        eligible: dict[str, dict[str, Any]] = {row["chunk_id"]: row for row in recheck_rows}
        dropped_count = len(candidate_ids) - len(eligible)
        if dropped_count:
            # Deliberately no chunk IDs in this message: the IDs that failed
            # the recheck are exactly the ones whose content/citation this
            # response is already withholding, and naming them would leak
            # their existence back to the caller through the warning text.
            warnings.append(f"{dropped_count} search hit(s) failed the license policy recheck and were excluded")

        # embedding_allowed gates the vector channel only -- a chunk can
        # remain fulltext-eligible (chunk/document storage permission) after
        # its document's embedding permission is revoked; see
        # _RECHECK_AND_CITE_QUERY's docstring comment.
        vector_eligible = {chunk_id for chunk_id in vector_ranking if eligible.get(chunk_id, {}).get("embedding_allowed")}
        if query_embedder is not None and not vector_eligible and not warnings:
            warnings.append(VECTOR_UNAVAILABLE_WARNING + ": no eligible vectors match the requested profile")

        channel_rankings: dict[str, Sequence[str]] = {}
        if FULLTEXT_CHANNEL in request.channels:
            channel_rankings[FULLTEXT_CHANNEL] = tuple(chunk_id for chunk_id in fulltext_ranking if chunk_id in eligible)
        if vector_eligible:
            channel_rankings[VECTOR_CHANNEL] = tuple(chunk_id for chunk_id in vector_ranking if chunk_id in vector_eligible)

        chunk_text = {chunk_id: row["text"] for chunk_id, row in eligible.items()}

        def _citation_for(chunk_id: str) -> SourceCitation:
            row = eligible[chunk_id]
            return SourceCitation(
                source_id=row["source_id"], source_url=row["source_url"], locator=row["locator"], license_name=row["license_name"]
            )

        return fuse_hybrid_results(
            channel_rankings,
            chunk_text=chunk_text,
            citation_for=_citation_for,
            limit=request.limit,
            k=request.rrf_k,
            warnings=warnings,
        )


def search(
    settings: Neo4jSettings,
    request: HybridSearchRequest,
    *,
    query_embedder: QueryEmbedderLike | None = None,
    config: HybridSchemaConfig = HybridSchemaConfig(),
) -> HybridSearchOutcome:
    """One-shot convenience wrapper around `Neo4jHybridSearch.search` for a single call."""

    with Neo4jHybridSearch(settings, config=config) as hybrid:
        return hybrid.search(request, query_embedder=query_embedder)
