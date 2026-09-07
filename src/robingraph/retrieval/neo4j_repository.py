"""`GraphRepository` backed by a live Neo4j graph, using parameterized Cypher.

This reads the same `:RobinGraph:Fixture`-labeled graph produced by
`robingraph.graph.neo4j_client.load_fixture`. Every query is a fixed,
reviewed Cypher template with bound parameters -- no query text is built
from question content, matching the "LLM never writes Cypher" design
principle in `docs/system-design.md`.
"""

from __future__ import annotations

from typing import Any, Sequence

from neo4j import GraphDatabase

from ..graph.settings import Neo4jSettings
from .repository import (
    ChunkRecord,
    DocumentRecord,
    ObservationRecord,
    PlaceRecord,
    SourceCitation,
    TaxonRecord,
    VernacularName,
)


# Fail-closed retrieval: every query below requires its own node's
# FROM_RECORD -> SourceRecord -> IN_DATASET -> SourceDataset -> LICENSED_UNDER
# -> License chain to resolve with policy_status = 'allowed'. This is
# deliberately redundant with the policy filtering already applied at load
# time (fixture_graph_payload / _load_fixture_tx's reconciliation): retrieval
# must not surface a node's name, text, or existence -- not just its later
# citation -- on the strength of "it shouldn't be there" alone. A stale or
# manually-inserted node without a valid allowed-license chain is invisible
# to every read here, not only to citation_for/known_evidence_ids.
_TAXONOMY_QUERY = """
MATCH (t:Taxon:RobinGraph:Fixture)-[:HAS_ACCEPTED_NAME]->(sci:ScientificName)
MATCH (t)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE lic.policy_status = 'allowed'
OPTIONAL MATCH (t)-[:HAS_VERNACULAR_NAME]->(v:VernacularName)
WITH t, sci, collect(CASE WHEN v IS NULL THEN null ELSE {language: v.language, name: v.name} END) AS names
RETURN t.id AS taxon_id, sci.full_name AS scientific_name, names AS vernacular_names
"""

# Place has no license of its own -- it is only ever a spatial reference on
# an Observation -- so a place is visible exactly when at least one allowed
# observation is WITHIN it.
_PLACES_QUERY = """
MATCH (o:Observation:RobinGraph:Fixture)-[:WITHIN]->(p:Place:RobinGraph:Fixture)
MATCH (o)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE lic.policy_status = 'allowed'
RETURN DISTINCT p.id AS place_id, p.name AS display_name
"""

_DOCUMENTS_QUERY = """
MATCH (d:Document:RobinGraph:Fixture)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE lic.policy_status = 'allowed'
RETURN d.id AS document_id, d.title AS title
"""

# A chunk requires both its own license chain and its document's -- the same
# two-sided requirement policy.chunk_allowed applies at load time.
_CHUNKS_QUERY = """
MATCH (d:Document:RobinGraph:Fixture)-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(chunkLicense:License)
MATCH (d)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(documentLicense:License)
WHERE chunkLicense.policy_status = 'allowed' AND documentLicense.policy_status = 'allowed'
RETURN c.id AS chunk_id, d.id AS document_id, c.ordinal AS ordinal, c.text AS text
ORDER BY d.id, c.ordinal
"""

_CHUNKS_FOR_DOCUMENT_QUERY = """
MATCH (d:Document:RobinGraph:Fixture {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(chunkLicense:License)
MATCH (d)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(documentLicense:License)
WHERE chunkLicense.policy_status = 'allowed' AND documentLicense.policy_status = 'allowed'
RETURN c.id AS chunk_id, d.id AS document_id, c.ordinal AS ordinal, c.text AS text
ORDER BY c.ordinal
"""

_OBSERVATIONS_QUERY = """
MATCH (o:Observation:RobinGraph:Fixture)-[:OBSERVED_TAXON]->(t:Taxon)
MATCH (o)-[:WITHIN]->(place:Place)
MATCH (o)-[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE t.id IN $taxon_ids
  AND lic.policy_status = 'allowed'
  AND ($place_id IS NULL OR place.id = $place_id)
  AND ($month_prefix IS NULL OR substring(o.event_date_raw, 0, 7) = $month_prefix)
RETURN o.occurrence_id AS occurrence_id, t.id AS taxon_id, place.id AS place_id, place.name AS place_name,
       o.event_date_raw AS event_date_raw, o.sensitivity AS sensitivity_class
ORDER BY o.occurrence_id
"""

# Fail-closed: the LICENSED_UNDER hop is a plain (non-OPTIONAL) MATCH and the
# license's own policy_status is checked again here, so evidence with a
# missing license -- or a license that is not (or no longer) 'allowed' --
# returns zero rows instead of a citation with a placeholder license. The
# locator always comes from the EvidenceUnit's own `locator` property
# (set at load time to the human-readable page/section/occurrence id for
# every evidence type), never from the Chunk node, which carries no locator
# property of its own.
_CITATION_QUERY = """
MATCH (e:EvidenceUnit:RobinGraph:Fixture {id: $evidence_node_id})
      -[:FROM_RECORD]->(sr:SourceRecord)-[:IN_DATASET]->(sd:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE lic.policy_status = 'allowed'
RETURN sd.name AS source_id, sd.landing_uri AS source_url,
       coalesce(e.locator, sr.external_id) AS locator,
       lic.license_name AS license_name
"""

# Fail-closed for the same reason as _CITATION_QUERY: an evidence unit whose
# license chain is missing or not 'allowed' is not "known" evidence at all.
_EVIDENCE_IDS_QUERY = """
MATCH (e:EvidenceUnit:RobinGraph:Fixture)
      -[:FROM_RECORD]->(:SourceRecord)-[:IN_DATASET]->(:SourceDataset)-[:LICENSED_UNDER]->(lic:License)
WHERE lic.policy_status = 'allowed'
RETURN DISTINCT e.id AS evidence_node_id
"""

_TAXONOMY_RELEASE_QUERY = """
MATCH (set:TaxonConceptSet:RobinGraph:Fixture)
RETURN set.version AS taxonomy_release
ORDER BY set.version
LIMIT 1
"""

_DATA_CUTOFF_QUERY = "MATCH (sr:SourceRecord:RobinGraph:Fixture) RETURN max(sr.retrieved_at) AS data_cutoff"

_EVIDENCE_PREFIX = "fixture-evidence:"


class Neo4jGraphRepository:
    """Serves the fixture graph already loaded into Neo4j, via parameterized Cypher."""

    mode = "neo4j"

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))
        self.taxonomy_release = self._single(_TAXONOMY_RELEASE_QUERY).get("taxonomy_release") or "unknown"
        self.data_cutoff = self._single(_DATA_CUTOFF_QUERY).get("data_cutoff") or "unknown"

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jGraphRepository":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _run(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._settings.database) as session:
            return session.run(query, **parameters).data()

    def _single(self, query: str, **parameters: Any) -> dict[str, Any]:
        rows = self._run(query, **parameters)
        return rows[0] if rows else {}

    def list_taxonomy(self) -> tuple[TaxonRecord, ...]:
        taxa = []
        for row in self._run(_TAXONOMY_QUERY):
            vernacular_names = tuple(
                VernacularName(name["language"], name["name"])
                for name in (row["vernacular_names"] or [])
                if name is not None
            )
            taxa.append(TaxonRecord(row["taxon_id"], row["scientific_name"], vernacular_names))
        return tuple(taxa)

    def list_places(self) -> tuple[PlaceRecord, ...]:
        return tuple(PlaceRecord(row["place_id"], row["display_name"]) for row in self._run(_PLACES_QUERY))

    def list_documents(self) -> tuple[DocumentRecord, ...]:
        return tuple(DocumentRecord(row["document_id"], row["title"]) for row in self._run(_DOCUMENTS_QUERY))

    def list_chunks(self) -> tuple[ChunkRecord, ...]:
        return tuple(
            ChunkRecord(row["chunk_id"], row["document_id"], row["ordinal"], row["text"])
            for row in self._run(_CHUNKS_QUERY)
        )

    def chunks_for_document(self, document_id: str) -> tuple[ChunkRecord, ...]:
        rows = self._run(_CHUNKS_FOR_DOCUMENT_QUERY, document_id=document_id)
        return tuple(ChunkRecord(row["chunk_id"], row["document_id"], row["ordinal"], row["text"]) for row in rows)

    def observations_for_taxa(
        self, taxon_ids: Sequence[str], place_id: str | None, month_prefix: str | None
    ) -> tuple[ObservationRecord, ...]:
        rows = self._run(
            _OBSERVATIONS_QUERY,
            taxon_ids=list(taxon_ids),
            place_id=place_id,
            month_prefix=month_prefix,
        )
        return tuple(
            ObservationRecord(
                occurrence_id=row["occurrence_id"],
                taxon_id=row["taxon_id"],
                place_id=row["place_id"],
                place_name=row["place_name"],
                event_date_raw=row["event_date_raw"],
                sensitivity_class=row["sensitivity_class"],
            )
            for row in rows
        )

    def citation_for(self, evidence_id: str) -> SourceCitation:
        row = self._single(_CITATION_QUERY, evidence_node_id=_EVIDENCE_PREFIX + evidence_id)
        if not row:
            raise ValueError(f"Unknown evidence ID: {evidence_id}")
        return SourceCitation(
            source_id=row["source_id"],
            source_url=row["source_url"],
            locator=row["locator"],
            license_name=row["license_name"],
        )

    def known_evidence_ids(self) -> frozenset[str]:
        return frozenset(
            row["evidence_node_id"][len(_EVIDENCE_PREFIX) :]
            for row in self._run(_EVIDENCE_IDS_QUERY)
            if row["evidence_node_id"].startswith(_EVIDENCE_PREFIX)
        )

    def known_private_coordinate_values(self) -> frozenset[str]:
        # Private coordinates are never projected into the graph (see
        # graph/fixture_projection.py), so there is nothing here that could leak.
        return frozenset()
