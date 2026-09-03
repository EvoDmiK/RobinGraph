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
)


def _run(session: Any, query: str, **parameters: Any) -> None:
    session.run(query, **parameters).consume()


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
        MERGE (dataset:SourceDataset:RobinGraph:Fixture {id: row.source_id + ':' + row.source_release})
        SET dataset.name = row.source_id, dataset.version = row.source_release
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.occurrence_id, source.record_type = 'observation', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
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
        MERGE (dataset:SourceDataset:RobinGraph:Fixture {id: row.source_id + ':' + row.source_release})
        SET dataset.name = row.source_id, dataset.version = row.source_release
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.id, source.record_type = 'document', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (source)-[:IN_DATASET]->(dataset)
        MERGE (document:Document:RobinGraph:Fixture {id: row.id})
        SET document.title = row.title, document.language = row.language, document.retrieved_at = row.retrieved_at
        MERGE (document)-[:FROM_RECORD]->(source)
        """,
        rows=payload["documents"],
    )
    _run(
        tx,
        """
        UNWIND $rows AS row
        MATCH (document:Document {id: row.document_id})
        MERGE (source:SourceRecord:RobinGraph:Fixture {id: row.source_record_key})
        SET source.external_id = row.id, source.record_type = 'chunk', source.raw_uri = row.raw_uri,
            source.raw_hash = row.raw_hash, source.retrieved_at = row.retrieved_at
        MERGE (chunk:Chunk:RobinGraph:Fixture {id: row.id})
        SET chunk.text = row.text, chunk.section = row.section, chunk.ordinal = row.ordinal,
            chunk.content_hash = row.content_hash
        MERGE (document)-[:HAS_CHUNK]->(chunk)
        MERGE (evidence:EvidenceUnit:RobinGraph:Fixture {id: 'fixture-evidence:' + row.id})
        SET evidence.evidence_type = 'chunk', evidence.locator = row.locator, evidence.accessed_at = row.retrieved_at
        MERGE (evidence)-[:FROM_CHUNK]->(chunk)
        MERGE (evidence)-[:FROM_RECORD]->(source)
        """,
        rows=payload["chunks"],
    )


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
