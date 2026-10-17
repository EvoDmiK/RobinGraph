"""Neo4j-backed vectors for reviewed Korean taxon display names.

Graph model (all nodes are owned by this module; taxa are only read):

* ``(:TaxonNameVectorEntry {key, ...})-[:NAME_VECTOR_OF]->(:Taxon:BirdTaxon)``
  one entry per (taxon, embedding profile, taxonomy context).
* Entries of the current catalog additionally carry the ``TaxonNameVector``
  label and the ``name_vector`` property, which is the only thing the
  ``robingraphTaxonNameVector`` vector index sees. Stale entries lose both in
  the same transaction that switches the catalog, so they never compete.
* ``(:TaxonNameVectorCatalog {id})`` records the inventory fingerprint and
  the profile/context the active entries were built for.

``search`` is read-only: no DDL, no writes and no embedding calls. Only the
explicit ``index_names`` (with ``dry_run=False``) creates the index, embeds
missing or changed names and reconciles entries in one write transaction.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from neo4j import GraphDatabase

from ..graph.settings import Neo4jSettings


INDEX_NAME = "robingraphTaxonNameVector"
FEATURE_LABEL = "TaxonNameVector"
ENTRY_LABEL = "TaxonNameVectorEntry"
VECTOR_PROPERTY = "name_vector"
CATALOG_ID = "reviewed-korean-taxon-names"
MAX_INVENTORY = 1000
MAX_TEXT_CHARS = 200
MAX_SEARCH_LIMIT = 50
_FIELDS = ("taxon_id", "scientific_name", "display_name", "text")


class TaxonNameVectorUnavailable(ValueError):
    """Schema, catalog or input does not match; callers must not guess."""


_SHOW_INDEX = """
SHOW INDEXES YIELD name, type, state, labelsOrTypes, properties, options
WHERE name = $name
RETURN type, state, labelsOrTypes, properties, options
"""

_CREATE_INDEX = f"""
CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
FOR (n:{FEATURE_LABEL}) ON (n.{VECTOR_PROPERTY})
OPTIONS {{indexConfig: {{`vector.dimensions`: toInteger($dimensions), `vector.similarity_function`: 'cosine'}}}}
"""

_AWAIT_INDEX = "CALL db.awaitIndex($name, 30)"

CONSTRAINT_NAME = "robingraphTaxonNameVectorEntryKey"
_SHOW_CONSTRAINT = """
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties
WHERE name = $name
RETURN type, labelsOrTypes, properties
"""
_CREATE_CONSTRAINT = (f"CREATE CONSTRAINT {CONSTRAINT_NAME} IF NOT EXISTS "
                      f"FOR (n:{ENTRY_LABEL}) REQUIRE n.key IS UNIQUE")

# The caller supplies the authoritative active context (PostgreSQL release
# state); the graph only has to hold exactly one allowed concept set for it.
_ACTIVE_CONTEXT = """
MATCH (s:TaxonConceptSet {id: $concept_set_id, version: $release, policy_status: 'allowed'})
RETURN s.id AS concept_set_id, s.version AS taxonomy_release
"""

# Each reviewed name must point at the same active, allowed species taxon.
_ALLOWED_TAXA = """
UNWIND $rows AS row
MATCH (s:TaxonConceptSet {id: $concept_set_id, version: $release, policy_status: 'allowed'})
MATCH (t:Taxon:BirdTaxon {id: row.taxon_id, rank: 'species', source_release: $release,
                         policy_status: 'allowed'})-[:IN_CONCEPT_SET]->(s)
WHERE t.dataset_id = s.dataset_id AND t.scientific_name = row.scientific_name
RETURN DISTINCT t.id AS taxon_id
"""

_EXISTING_ENTRIES = f"""
UNWIND $keys AS key
MATCH (n:{ENTRY_LABEL} {{key: key}})
RETURN n.key AS key, n.text_hash AS text_hash, n.taxon_id AS taxon_id,
       n.scientific_name AS scientific_name, n.{VECTOR_PROPERTY} AS vector
"""

_ACTIVE_KEYS = f"""
MATCH (n:{FEATURE_LABEL}:{ENTRY_LABEL})
RETURN n.key AS key
"""

_CATALOG = """
MATCH (c:TaxonNameVectorCatalog {id: $catalog_id})
RETURN c.fingerprint AS fingerprint, c.model AS model, c.dimensions AS dimensions,
       c.normalized AS normalized, c.concept_set_id AS concept_set_id,
       c.taxonomy_release AS taxonomy_release, c.count AS count
"""

# One transaction: upsert current entries, link them to their taxon, retire
# stale feature entries (own nodes only) and switch the catalog.
_UPSERT_ENTRIES = f"""
UNWIND $rows AS row
MATCH (s:TaxonConceptSet {{id: $concept_set_id, version: $release, policy_status: 'allowed'}})
MATCH (t:Taxon:BirdTaxon {{id: row.taxon_id, rank: 'species', source_release: $release,
                         policy_status: 'allowed'}})-[:IN_CONCEPT_SET]->(s)
WHERE t.dataset_id = s.dataset_id AND t.scientific_name = row.scientific_name
MERGE (n:{ENTRY_LABEL} {{key: row.key}})
WITH n, t, row WHERE NOT n:Taxon
SET n:{FEATURE_LABEL}, n += row.properties, n.{VECTOR_PROPERTY} = row.vector
WITH n, t
OPTIONAL MATCH (n)-[old:NAME_VECTOR_OF]->(other)
WHERE other <> t
DELETE old
MERGE (n)-[:NAME_VECTOR_OF]->(t)
RETURN count(DISTINCT n) AS written
"""

_RETIRE_STALE = f"""
MATCH (n:{FEATURE_LABEL}:{ENTRY_LABEL})
WHERE NOT n.key IN $keys AND NOT n:Taxon
REMOVE n:{FEATURE_LABEL}, n.{VECTOR_PROPERTY}
RETURN count(n) AS retired
"""

_SWITCH_CATALOG = """
MERGE (c:TaxonNameVectorCatalog {id: $catalog_id})
SET c.fingerprint = $fingerprint, c.model = $model, c.dimensions = $dimensions,
    c.normalized = $normalized, c.concept_set_id = $concept_set_id,
    c.taxonomy_release = $release, c.count = $count, c.index_name = $index_name
"""

# Catalog, active context and allowed taxon links are compared in Cypher;
# Python then re-checks every returned field against the reviewed inventory.
_SEARCH = f"""
MATCH (c:TaxonNameVectorCatalog {{id: $catalog_id, fingerprint: $fingerprint, model: $model,
       dimensions: $dimensions, normalized: $normalized, concept_set_id: $concept_set_id,
       taxonomy_release: $release}})
MATCH (s:TaxonConceptSet {{id: $concept_set_id, version: $release, policy_status: 'allowed'}})
CALL db.index.vector.queryNodes($index_name, $limit, $vector) YIELD node, score
WITH node, score, s
WHERE node:{ENTRY_LABEL} AND node.catalog_fingerprint = $fingerprint AND node.model = $model
  AND node.dimensions = $dimensions AND node.normalized = $normalized
  AND node.concept_set_id = $concept_set_id AND node.taxonomy_release = $release
MATCH (node)-[:NAME_VECTOR_OF]->(t:Taxon:BirdTaxon {{id: node.taxon_id, rank: 'species',
       source_release: $release, policy_status: 'allowed'}})-[:IN_CONCEPT_SET]->(s)
WHERE t.dataset_id = s.dataset_id AND t.scientific_name = node.scientific_name
RETURN node.taxon_id AS taxon_id, node.scientific_name AS scientific_name,
       node.display_name AS display_name, node.text AS text, node.text_hash AS text_hash, score
"""


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _profile(profile: Any) -> tuple[str, int, bool]:
    model = getattr(profile, "model", None)
    dimensions = getattr(profile, "dimensions", None)
    normalized = getattr(profile, "normalized", None)
    if (not isinstance(model, str) or not model.strip() or isinstance(dimensions, bool)
            or not isinstance(dimensions, int) or dimensions < 1 or not isinstance(normalized, bool)):
        raise TaxonNameVectorUnavailable("Embedding profile is incomplete")
    return model, dimensions, normalized


def _context(context: Any) -> tuple[str, str]:
    if (isinstance(context, tuple) and len(context) == 2
            and all(isinstance(part, str) and part.strip() for part in context)):
        return context
    raise TaxonNameVectorUnavailable("Taxonomy context is invalid")


def _inventory(raw: Any) -> list[dict]:
    # An empty inventory would retire every active entry; never accept it.
    if (isinstance(raw, (str, bytes, Mapping)) or not isinstance(raw, Sequence)
            or not 1 <= len(raw) <= MAX_INVENTORY):
        raise TaxonNameVectorUnavailable("Reviewed name inventory is invalid")
    rows, ids, names = [], set(), set()
    for entry in raw:
        if not isinstance(entry, Mapping) or not all(
                isinstance(entry.get(field), str) and entry[field].strip() for field in _FIELDS):
            raise TaxonNameVectorUnavailable("Reviewed name inventory is invalid")
        row = {field: entry[field] for field in _FIELDS}
        if len(row["text"]) > MAX_TEXT_CHARS or row["taxon_id"] in ids or row["scientific_name"] in names:
            raise TaxonNameVectorUnavailable("Reviewed name inventory is invalid")
        ids.add(row["taxon_id"])
        names.add(row["scientific_name"])
        rows.append(row)
    return sorted(rows, key=lambda row: row["taxon_id"])


def _vector(value: Any, dimensions: int) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != dimensions:
        raise TaxonNameVectorUnavailable("Embedding vector is invalid")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise TaxonNameVectorUnavailable("Embedding vector is invalid")
    values = [float(item) for item in value]
    norm = math.hypot(*values)
    if not all(math.isfinite(item) for item in values) or not math.isfinite(norm) or norm == 0.0:
        raise TaxonNameVectorUnavailable("Embedding vector is invalid")
    # Stored and query vectors are unit length, so cosine is well-defined.
    unit = [item / norm for item in values]
    if not all(math.isfinite(item) for item in unit):
        raise TaxonNameVectorUnavailable("Embedding vector is invalid")
    return unit


def catalog_fingerprint(inventory: Sequence[dict], profile: tuple[str, int, bool], context: tuple[str, str]) -> str:
    payload = {"inventory": [[row[field] for field in _FIELDS] for row in inventory],
               "profile": list(profile), "context": list(context)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _entry_key(taxon_id: str, profile: tuple[str, int, bool], context: tuple[str, str]) -> str:
    return hashlib.sha256(json.dumps([taxon_id, list(profile), list(context)]).encode("utf-8")).hexdigest()


def _index_state(tx: Any, dimensions: int, *, require_online: bool) -> str:
    """'absent' or 'compatible'; anything else fails without changing schema."""
    rows = tx.run(_SHOW_INDEX, name=INDEX_NAME).data()
    if not rows:
        if require_online:
            raise TaxonNameVectorUnavailable("Taxon name vector index is missing")
        return "absent"
    row = rows[0]
    config = (row.get("options") or {}).get("indexConfig") or {}
    function = config.get("vector.similarity_function")
    if (row.get("type") != "VECTOR" or row.get("labelsOrTypes") != [FEATURE_LABEL]
            or row.get("properties") != [VECTOR_PROPERTY] or config.get("vector.dimensions") != dimensions
            or not isinstance(function, str) or function.lower() != "cosine"):
        raise TaxonNameVectorUnavailable("Existing taxon name vector index is incompatible; migrate it explicitly")
    if require_online and row.get("state") != "ONLINE":
        raise TaxonNameVectorUnavailable("Taxon name vector index is not online")
    return "compatible"


def _constraint_state(tx: Any) -> str:
    """Unique entry keys keep concurrent MERGEs from duplicating entries."""
    rows = tx.run(_SHOW_CONSTRAINT, name=CONSTRAINT_NAME).data()
    if not rows:
        return "absent"
    row = rows[0]
    if (row.get("type") not in ("UNIQUENESS", "NODE_PROPERTY_UNIQUENESS")
            or row.get("labelsOrTypes") != [ENTRY_LABEL] or row.get("properties") != ["key"]):
        raise TaxonNameVectorUnavailable("Existing taxon name vector constraint is incompatible")
    return "compatible"


def _check_concept_set(tx: Any, context: tuple[str, str]) -> None:
    rows = tx.run(_ACTIVE_CONTEXT, concept_set_id=context[0], release=context[1]).data()
    if len(rows) != 1 or (rows[0].get("concept_set_id"), rows[0].get("taxonomy_release")) != context:
        raise TaxonNameVectorUnavailable("Expected taxonomy concept set is missing or not allowed")


def _check_taxa(tx: Any, inventory: list[dict], context: tuple[str, str]) -> None:
    _check_concept_set(tx, context)
    found = {row.get("taxon_id") for row in tx.run(
        _ALLOWED_TAXA, rows=[{"taxon_id": row["taxon_id"], "scientific_name": row["scientific_name"]}
                             for row in inventory],
        concept_set_id=context[0], release=context[1]).data()}
    if found != {row["taxon_id"] for row in inventory}:
        raise TaxonNameVectorUnavailable("Reviewed names do not match active allowed species taxa")


class Neo4jTaxonNameVectorRepository:
    """Reviewed-name vectors stored in a dedicated Neo4j feature index."""

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver = None

    def _session(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(self._settings.uri,
                                                auth=(self._settings.username, self._settings.password))
        return self._driver.session(database=self._settings.database)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> "Neo4jTaxonNameVectorRepository":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def search(self, vector: Any, profile: Any, context: Any, inventory: Any, limit: int = 10) -> list[dict]:
        """Read-only cosine search; every hit is checked against the current inventory."""
        model, dimensions, normalized = profile_key = _profile(profile)
        context = _context(context)
        rows = _inventory(inventory)
        query = _vector(vector, dimensions)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise TaxonNameVectorUnavailable("Search limit is invalid")
        fingerprint = catalog_fingerprint(rows, profile_key, context)
        expected = {row["taxon_id"]: row for row in rows}

        def read(tx):
            _index_state(tx, dimensions, require_online=True)
            _check_concept_set(tx, context)
            catalog = tx.run(_CATALOG, catalog_id=CATALOG_ID).data()
            if len(catalog) != 1 or catalog[0] != {
                    "fingerprint": fingerprint, "model": model, "dimensions": dimensions, "normalized": normalized,
                    "concept_set_id": context[0], "taxonomy_release": context[1], "count": len(rows)}:
                raise TaxonNameVectorUnavailable("Taxon name vector catalog is stale")
            return tx.run(_SEARCH, catalog_id=CATALOG_ID, fingerprint=fingerprint, model=model,
                          dimensions=dimensions, normalized=normalized, concept_set_id=context[0],
                          release=context[1], index_name=INDEX_NAME, limit=limit, vector=query).data()

        with self._session() as session:
            hits = session.execute_read(read)
        results, seen = [], set()
        for hit in hits:
            row = expected.get(hit.get("taxon_id"))
            score = hit.get("score")
            if (row is None or hit["taxon_id"] in seen
                    or any(hit.get(field) != row[field] for field in _FIELDS)
                    or hit.get("text_hash") != _text_hash(row["text"])
                    or isinstance(score, bool) or not isinstance(score, (int, float))
                    or not math.isfinite(score) or not 0.0 <= score <= 1.0):
                continue  # stale, foreign or malformed hit
            seen.add(hit["taxon_id"])
            # Neo4j reports cosine indexes as (1 + cosine) / 2; return raw cosine.
            results.append({**{field: row[field] for field in _FIELDS},
                            "score": max(-1.0, min(1.0, 2.0 * float(score) - 1.0))})
        return sorted(results, key=lambda item: (-item["score"], item["taxon_id"]))

    def index_names(self, inventory: Any, embedding_client: Any, context: Any, *, dry_run: bool = True) -> dict:
        """Explicit indexing. ``dry_run`` only reads and never calls the model."""
        profile_key = _profile(getattr(embedding_client, "profile", None))
        model, dimensions, normalized = profile_key
        context = _context(context)
        rows = _inventory(inventory)
        fingerprint = catalog_fingerprint(rows, profile_key, context)
        keys = {row["taxon_id"]: _entry_key(row["taxon_id"], profile_key, context) for row in rows}

        def plan(tx):
            schema = _index_state(tx, dimensions, require_online=False)
            constraint = _constraint_state(tx)
            _check_taxa(tx, rows, context)
            existing = {item["key"]: item for item in tx.run(_EXISTING_ENTRIES, keys=list(keys.values())).data()}
            active = {item["key"] for item in tx.run(_ACTIVE_KEYS).data()}
            catalog = tx.run(_CATALOG, catalog_id=CATALOG_ID).data()
            return schema, constraint, existing, active, catalog

        with self._session() as session:
            schema, constraint, existing, active, catalog = session.execute_read(plan)
        reused: dict[str, list[float]] = {}
        for row in rows:
            item = existing.get(keys[row["taxon_id"]])
            if (item and item.get("text_hash") == _text_hash(row["text"]) and item.get("taxon_id") == row["taxon_id"]
                    and item.get("scientific_name") == row["scientific_name"]):
                try:
                    reused[row["taxon_id"]] = _vector(item.get("vector"), dimensions)
                except TaxonNameVectorUnavailable:
                    pass  # a malformed stored vector is re-embedded
        missing = [row for row in rows if row["taxon_id"] not in reused]
        stale = len(active - set(keys.values()))
        report = {"dry_run": dry_run, "inventory": len(rows), "reused": len(reused), "to_embed": len(missing),
                  "embedded": 0, "stale": stale, "schema": schema, "constraint": constraint,
                  "catalog_current": bool(catalog) and catalog[0].get("fingerprint") == fingerprint}
        if dry_run:
            return report

        vectors = dict(reused)
        if missing:
            embedded = embedding_client.embed_documents([row["text"] for row in missing])
            if isinstance(embedded, (str, bytes)) or len(embedded) != len(missing):
                raise TaxonNameVectorUnavailable("Embedding response count does not match")
            for row, vector in zip(missing, embedded):
                vectors[row["taxon_id"]] = _vector(vector, dimensions)
        payload = [{"key": keys[row["taxon_id"]], "taxon_id": row["taxon_id"],
                    "scientific_name": row["scientific_name"], "vector": vectors[row["taxon_id"]],
                    "properties": {**row, "text_hash": _text_hash(row["text"]), "model": model,
                                   "dimensions": dimensions, "normalized": normalized,
                                   "concept_set_id": context[0], "taxonomy_release": context[1],
                                   "catalog_fingerprint": fingerprint}} for row in rows]

        def apply(tx):
            # Re-check inside the write transaction; any mismatch rolls back.
            _check_taxa(tx, rows, context)
            written = tx.run(_UPSERT_ENTRIES, rows=payload, concept_set_id=context[0], release=context[1]).data()
            if not written or written[0].get("written") != len(payload):
                raise TaxonNameVectorUnavailable("Reviewed names do not match graph taxa")
            retired = tx.run(_RETIRE_STALE, keys=[item["key"] for item in payload]).data()
            tx.run(_SWITCH_CATALOG, catalog_id=CATALOG_ID, fingerprint=fingerprint, model=model,
                   dimensions=dimensions, normalized=normalized, concept_set_id=context[0],
                   release=context[1], count=len(payload), index_name=INDEX_NAME)
            return retired[0].get("retired", 0) if retired else 0

        with self._session() as session:
            if constraint == "absent":
                session.run(_CREATE_CONSTRAINT).consume()
            if schema == "absent":
                session.run(_CREATE_INDEX, dimensions=dimensions).consume()
            session.execute_read(lambda tx: _verify_created_schema(tx, dimensions))
            session.run(_AWAIT_INDEX, name=INDEX_NAME).consume()
            retired = session.execute_write(apply)
        return {**report, "embedded": len(missing), "stale": retired, "schema": "created" if schema == "absent"
                else schema, "constraint": "created" if constraint == "absent" else constraint,
                "catalog_current": True}


def _verify_created_schema(tx: Any, dimensions: int) -> None:
    if _constraint_state(tx) != "compatible" or _index_state(tx, dimensions, require_online=False) != "compatible":
        raise TaxonNameVectorUnavailable("Taxon name vector schema was not created")
