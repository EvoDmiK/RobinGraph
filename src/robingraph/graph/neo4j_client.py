"""Narrow Neo4j connectivity boundary for the MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase

from .settings import Neo4jSettings
from .fixture_projection import fixture_graph_payload
from ..fixture import FixtureCorpus


@dataclass(frozen=True)
class Neo4jServerInfo:
    name: str
    version: str
    edition: str | None


@dataclass(frozen=True)
class FixtureGraphCounts:
    taxa: int
    observations: int
    documents: int
    chunks: int


@dataclass(frozen=True)
class FixtureGraphVerification:
    counts: FixtureGraphCounts
    private_coordinate_properties: int
    restricted_observations: int


SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT robingraph_taxon_id_unique IF NOT EXISTS FOR (node:Taxon) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_concept_set_id_unique IF NOT EXISTS FOR (node:TaxonConceptSet) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_scientific_name_id_unique IF NOT EXISTS FOR (node:ScientificName) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_vernacular_name_id_unique IF NOT EXISTS FOR (node:VernacularName) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_observation_id_unique IF NOT EXISTS FOR (node:Observation) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_place_id_unique IF NOT EXISTS FOR (node:Place) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_document_id_unique IF NOT EXISTS FOR (node:Document) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_chunk_id_unique IF NOT EXISTS FOR (node:Chunk) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_source_record_id_unique IF NOT EXISTS FOR (node:SourceRecord) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_source_dataset_id_unique IF NOT EXISTS FOR (node:SourceDataset) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_evidence_unit_id_unique IF NOT EXISTS FOR (node:EvidenceUnit) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT robingraph_license_id_unique IF NOT EXISTS FOR (node:License) REQUIRE node.id IS UNIQUE",
)


def _run(session: Any, query: str, **parameters: Any) -> None:
    session.run(query, **parameters).consume()


# Dedicated fixture search label: added to every fixture Chunk (see the
# `SET chunk:HybridSearchChunk` in the chunk UNWIND block below, alongside
# the other literal label names already used throughout this function) so
# `retrieval.neo4j_hybrid`'s fulltext index can be scoped to exactly this
# label rather than the bare, more general `Chunk` label. The literal string
# must stay equal to retrieval.neo4j_hybrid.HYBRID_SEARCH_LABEL by hand --
# graph/ does not import retrieval/ (that dependency runs the other way), so
# there is no shared constant to import here.

# Every label a fixture load can create. Reconciliation (see
# _reconcile_stale_nodes) deletes any :RobinGraph:Fixture node carrying one of
# these labels whose id is not in the current payload's expected id set, so a
# record that becomes policy-denied (or a document whose chunk/fulltext
# permission is revoked) on a later load does not leave stale, still-citable
# content behind. The label scope keeps this strictly inside fixture data --
# a node without the :RobinGraph:Fixture label is never matched or deleted.
_RECONCILE_LABELS = (
    "TaxonConceptSet",
    "Taxon",
    "ScientificName",
    "VernacularName",
    "Observation",
    "Place",
    "Document",
    "Chunk",
    "SourceRecord",
    "SourceDataset",
    "License",
    "EvidenceUnit",
)


def _expected_ids(payload: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    """The id every node of each reconciled label is allowed to keep after this load."""

    taxa = payload["taxa"]
    names = payload["names"]
    observations = payload["observations"]
    documents = payload["documents"]
    chunks = payload["chunks"]
    licensed_rows = [*taxa, *observations, *documents, *chunks]
    return {
        "TaxonConceptSet": sorted({row["concept_set_id"] for row in taxa}),
        "Taxon": sorted({row["id"] for row in taxa}),
        "ScientificName": sorted({row["id"] + ":scientific" for row in taxa}),
        "VernacularName": sorted({row["id"] for row in names}),
        "Observation": sorted({row["id"] for row in observations}),
        "Place": sorted({row["place_id"] for row in observations}),
        "Document": sorted({row["id"] for row in documents}),
        "Chunk": sorted({row["id"] for row in chunks}),
        "SourceRecord": sorted({row["source_record_key"] for row in licensed_rows}),
        "SourceDataset": sorted({f"{row['source_id']}:{row['source_release']}" for row in licensed_rows}),
        "License": sorted({row["license_uri"] for row in licensed_rows}),
        "EvidenceUnit": sorted(
            {f"fixture-evidence:{row['id']}" for row in taxa}
            | {f"fixture-evidence:{row['occurrence_id']}" for row in observations}
            | {f"fixture-evidence:{row['id']}" for row in chunks}
        ),
    }


def _reconcile_stale_nodes(tx: Any, expected_ids: dict[str, list[str]]) -> None:
    """Delete :RobinGraph:Fixture nodes whose id fell out of the current payload.

    Runs in the same write transaction as the upserts in _load_fixture_tx, so
    a load is an atomic replace-to-snapshot rather than an upsert that can
    only ever grow. Every MATCH is scoped to :RobinGraph:Fixture, so nothing
    outside that label -- i.e. no unrelated, non-fixture data -- is ever
    touched.
    """

    for label in _RECONCILE_LABELS:
        _run(
            tx,
            f"""
            MATCH (node:RobinGraph:Fixture:{label})
            WHERE NOT node.id IN $ids
            DETACH DELETE node
            """,
            ids=expected_ids.get(label, []),
        )


# Shared by every category below: a SourceDataset/License pair with attribution
# and policy-status provenance, so no taxon, observation, document, or chunk
# node is ever created without a resolvable source and license. The trailing
# WITH * is required by the server's GQL-conformant parser: a MATCH may not
# immediately follow a MERGE without an intervening WITH.
#
# dataset.policy_status is set here (in addition to license.policy_status
# below) because License is keyed by `license_uri` alone: two unrelated
# SourceDatasets that happen to publish under the same license URI (e.g. two
# different sources both under CC-BY-4.0) would otherwise MERGE onto the
# *same* License node, so revoking one dataset's policy would silently flip
# `license.policy_status` for the other, unrelated dataset too. SourceDataset
# is keyed by `source_id + source_release`, which is per-source, so a policy
# recheck against `dataset.policy_status` cannot be perturbed by an unrelated
# dataset sharing a license URI the way one against `license.policy_status`
# alone can. record["license_policy_status"] is already verified equal to
# its source registry entry's status at fixture-load time (fixture.py), so
# every row from the same source+release agrees on this value.
_MERGE_SOURCE_AND_LICENSE = """
MERGE (dataset:SourceDataset:RobinGraph:Fixture {id: row.source_id + ':' + row.source_release})
SET dataset.name = row.source_id, dataset.version = row.source_release, dataset.landing_uri = row.landing_uri,
    dataset.policy_status = row.license_policy_status
MERGE (license:License:RobinGraph:Fixture {id: row.license_uri})
SET license.license_uri = row.license_uri, license.license_name = row.license_name,
    license.policy_status = row.license_policy_status
MERGE (dataset)-[:LICENSED_UNDER]->(license)
WITH *
"""


def _load_fixture_tx(tx: Any, payload: dict[str, list[dict[str, Any]]]) -> None:
    _run(
        tx,
        """
        UNWIND $rows AS row
        MERGE (set:TaxonConceptSet:RobinGraph:Fixture {id: row.concept_set_id})
        SET set.version = row.concept_set_id, set.title = 'RobinGraph synthetic fixture taxonomy'
        MERGE (taxon:Taxon:RobinGraph:Fixture {id: row.id})
        SET taxon.rank = row.rank, taxon.status = row.status, taxon.canonical_label = row.canonical_label
        MERGE (taxon)-[:IN_CONCEPT_SET]->(set)
        MERGE (scientific:ScientificName:RobinGraph:Fixture {id: row.id + ':scientific'})
        SET scientific.full_name = row.scientific_name, scientific.canonical = row.scientific_name,
            scientific.normalized_key = toLower(row.scientific_name)
        MERGE (taxon)-[:HAS_ACCEPTED_NAME]->(scientific)
        """
        + _MERGE_SOURCE_AND_LICENSE
        + """
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.id, source.record_type = 'taxon', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
        MERGE (taxon)-[:FROM_RECORD]->(source)
        MERGE (evidence:EvidenceUnit:RobinGraph:Fixture {id: 'fixture-evidence:' + row.id})
        SET evidence.evidence_type = 'taxon', evidence.locator = row.id, evidence.accessed_at = row.retrieved_at
        MERGE (evidence)-[:FROM_RECORD]->(source)
        """,
        rows=payload["taxa"],
    )
    _run(
        tx,
        """
        UNWIND $rows AS row
        MATCH (taxon:Taxon {id: row.taxon_id})
        MERGE (name:VernacularName:RobinGraph:Fixture {id: row.id})
        SET name.name = row.name, name.normalized_name = row.normalized_name, name.language = row.language,
            name.region = row.region, name.status = row.status
        MERGE (taxon)-[:HAS_VERNACULAR_NAME]->(name)
        """,
        rows=payload["names"],
    )
    _run(
        tx,
        """
        UNWIND $rows AS row
        """
        + _MERGE_SOURCE_AND_LICENSE
        + """
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.occurrence_id, source.record_type = 'observation', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
        WITH *
        MATCH (taxon:Taxon {id: row.taxon_id})
        MERGE (place:Place:RobinGraph:Fixture {id: row.place_id})
        SET place.name = row.place_name, place.place_type = 'fixture'
        MERGE (observation:Observation:RobinGraph:Fixture {id: row.id})
        SET observation.occurrence_id = row.occurrence_id, observation.observed_at = row.observed_at,
            observation.event_date_raw = row.event_date_raw, observation.event_date_precision = row.event_date_precision,
            observation.count = row.count, observation.basis = row.basis, observation.lat = row.lat, observation.lon = row.lon,
            observation.coordinate_uncertainty_m = row.coordinate_uncertainty_m, observation.sensitivity = row.sensitivity,
            observation.source_record_key = row.source_record_key
        MERGE (observation)-[:OBSERVED_TAXON]->(taxon)
        MERGE (observation)-[:WITHIN]->(place)
        MERGE (observation)-[:FROM_RECORD]->(source)
        MERGE (evidence:EvidenceUnit:RobinGraph:Fixture {id: 'fixture-evidence:' + row.occurrence_id})
        SET evidence.evidence_type = 'observation', evidence.locator = row.occurrence_id, evidence.accessed_at = row.retrieved_at
        MERGE (evidence)-[:FROM_RECORD]->(source)
        """,
        rows=payload["observations"],
    )
    _run(
        tx,
        """
        UNWIND $rows AS row
        """
        + _MERGE_SOURCE_AND_LICENSE
        + """
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.id, source.record_type = 'document', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
        MERGE (document:Document:RobinGraph:Fixture {id: row.id})
        SET document.title = row.title, document.language = row.language, document.retrieved_at = row.retrieved_at,
            document.embedding_allowed = row.embedding_allowed
        MERGE (document)-[:FROM_RECORD]->(source)
        """,
        rows=payload["documents"],
    )
    _run(
        tx,
        """
        UNWIND $rows AS row
        """
        + _MERGE_SOURCE_AND_LICENSE
        + """
        MATCH (document:Document {id: row.document_id})
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.id, source.record_type = 'chunk', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
        MERGE (chunk:Chunk:RobinGraph:Fixture {id: row.id})
        SET chunk.text = row.text, chunk.section = row.section, chunk.ordinal = row.ordinal,
            chunk.content_hash = row.content_hash
        SET chunk:HybridSearchChunk
        // Invalidate a hybrid_vector left over from before this text/hash
        // change immediately on fixture reload, not only on the next
        // explicit retrieval.neo4j_hybrid.index_chunks call -- otherwise a
        // vector computed for the chunk's *previous* text would keep
        // matching vector search queries until someone happens to
        // re-index. chunk.hybrid_content_hash is only ever set by
        // index_chunks (see retrieval/neo4j_hybrid.py), so IS NULL means
        // "never indexed" (nothing to invalidate).
        FOREACH (_ IN CASE WHEN document.embedding_allowed <> true OR
          (chunk.hybrid_content_hash IS NOT NULL AND chunk.hybrid_content_hash <> row.content_hash) THEN [1] ELSE [] END |
          REMOVE chunk:HybridVectorChunk
          REMOVE chunk.hybrid_vector, chunk.hybrid_model, chunk.hybrid_dimensions, chunk.hybrid_normalized,
                 chunk.hybrid_content_hash, chunk.hybrid_indexed_at
        )
        MERGE (document)-[:HAS_CHUNK]->(chunk)
        MERGE (chunk)-[:FROM_RECORD]->(source)
        MERGE (evidence:EvidenceUnit:RobinGraph:Fixture {id: 'fixture-evidence:' + row.id})
        SET evidence.evidence_type = 'chunk', evidence.locator = row.locator, evidence.accessed_at = row.retrieved_at
        MERGE (evidence)-[:FROM_CHUNK]->(chunk)
        MERGE (evidence)-[:FROM_RECORD]->(source)
        """,
        rows=payload["chunks"],
    )
    _reconcile_stale_nodes(tx, _expected_ids(payload))


def bootstrap_schema(settings: Neo4jSettings) -> None:
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            for statement in SCHEMA_STATEMENTS:
                _run(session, statement)


def load_fixture(settings: Neo4jSettings, corpus: FixtureCorpus) -> FixtureGraphCounts:
    """Idempotently load only policy-filtered synthetic fixture records."""

    payload = fixture_graph_payload(corpus)
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            session.execute_write(_load_fixture_tx, payload)
            record = session.run(
                """
                CALL () {
                  MATCH (node:Taxon:Fixture) RETURN count(node) AS taxa
                }
                CALL () {
                  MATCH (node:Observation:Fixture) RETURN count(node) AS observations
                }
                CALL () {
                  MATCH (node:Document:Fixture) RETURN count(node) AS documents
                }
                CALL () {
                  MATCH (node:Chunk:Fixture) RETURN count(node) AS chunks
                }
                RETURN taxa, observations, documents, chunks
                """
            ).single(strict=True)
    return FixtureGraphCounts(
        taxa=record["taxa"], observations=record["observations"], documents=record["documents"], chunks=record["chunks"]
    )


def verify_fixture(settings: Neo4jSettings) -> FixtureGraphVerification:
    """Read fixture counts and prove sensitive/policy-blocked values are absent."""

    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            record = session.run(
                """
                CALL () {
                  MATCH (node:Taxon:Fixture) RETURN count(node) AS taxa
                }
                CALL () {
                  MATCH (node:Observation:Fixture) RETURN count(node) AS observations
                }
                CALL () {
                  MATCH (node:Document:Fixture) RETURN count(node) AS documents
                }
                CALL () {
                  MATCH (node:Chunk:Fixture) RETURN count(node) AS chunks
                }
                CALL () {
                  MATCH (node:Observation:Fixture)
                  WITH node, keys(node) AS property_keys
                  WHERE 'latitude_private' IN property_keys OR 'longitude_private' IN property_keys
                  RETURN count(node) AS private_coordinate_properties
                }
                CALL () {
                  MATCH (node:Observation:Fixture {occurrence_id: 'fixture-occ-restricted-001'})
                  RETURN count(node) AS restricted_observations
                }
                RETURN taxa, observations, documents, chunks, private_coordinate_properties, restricted_observations
                """
            ).single(strict=True)
    counts = FixtureGraphCounts(
        taxa=record["taxa"], observations=record["observations"], documents=record["documents"], chunks=record["chunks"]
    )
    return FixtureGraphVerification(
        counts=counts,
        private_coordinate_properties=record["private_coordinate_properties"],
        restricted_observations=record["restricted_observations"],
    )


def verify_server(settings: Neo4jSettings) -> Neo4jServerInfo:
    """Authenticate and return the server version without changing graph state."""

    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        driver.verify_connectivity()
        records, _, _ = driver.execute_query(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions[0] AS version, edition "
            "LIMIT 1",
            database_=settings.database,
        )
    if not records:
        raise RuntimeError("Neo4j did not return component metadata")
    record = records[0]
    return Neo4jServerInfo(name=record["name"], version=record["version"], edition=record.get("edition"))
