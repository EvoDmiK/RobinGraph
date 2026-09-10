"""Neo4j reader for the AviList reference-taxonomy lineage.

Reads the reference-taxonomy graph produced by the AviList n8n ingest
workflow (`scripts/generate_n8n_reference_ingest.py`), never the fixture
graph or the GBIF operational graph. Every query below:

- is read-only, parameterized Cypher (no query text built from request input);
- is scoped to the currently active `reference-taxonomy` `IngestState` and
  its `active_concept_set_id`, so a superseded or partially loaded AviList
  release is never surfaced;
- matches only `Taxon:BirdTaxon` nodes. `ExternalTaxonConcept:BirdTaxon`
  (the GBIF operational taxonomy) shares the `BirdTaxon` label but never the
  `Taxon` label, so the label pair `Taxon:BirdTaxon` structurally excludes
  it -- the two taxonomies are never merged (see
  `docs/graph-database-schema.md`).
"""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from ..graph.settings import Neo4jSettings
from .taxonomy_lineage import LineageTaxon, TaxonomyLineage

# The active concept set for the reference taxonomy is read from IngestState,
# never guessed from "the newest TaxonConceptSet" -- a concept set that is
# loaded but not yet promoted to active must stay invisible here.
_ACTIVE_CONCEPT_SET_QUERY = """
MATCH (state:IngestState {id: 'reference-taxonomy'})
MATCH (conceptSet:TaxonConceptSet {id: state.active_concept_set_id})
RETURN conceptSet.id AS concept_set_id,
       coalesce(state.active_release, conceptSet.version) AS taxonomy_release
"""

# `target` is resolved first and pinned (ORDER BY ... LIMIT 1) before the
# ancestor walk, so a duplicate scientific name never turns into a fanned-out
# ancestor list. The ancestor walk matches strictly within the same concept
# set on every hop, and both `target` and `ancestor` require the
# `Taxon:BirdTaxon` label pair, so the walk can never cross into
# `ExternalTaxonConcept` nodes. `length(ancestorPath) DESC` orders root first
# (order, then family, then genus, ..., down to `target` itself at depth 0),
# preserving order->family->genus->species order in the collected list.
_LINEAGE_QUERY = """
MATCH (conceptSet:TaxonConceptSet {id: $concept_set_id})
MATCH (target:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(conceptSet)
WHERE toLower(target.scientific_name) = toLower($scientific_name)
WITH target
ORDER BY target.id
LIMIT 1
OPTIONAL MATCH ancestorPath =
  (target)<-[parentLinks:PARENT_OF*0..3]-(ancestor:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id: $concept_set_id})
WHERE all(parentLink IN parentLinks WHERE parentLink.concept_set_id = $concept_set_id)
WITH ancestor, length(ancestorPath) AS depth
ORDER BY depth DESC
RETURN collect({
  taxon_id: ancestor.id,
  rank: ancestor.rank,
  scientific_name: ancestor.scientific_name,
  authority: ancestor.authority
}) AS lineage_items
"""


class Neo4jTaxonomyLineageRepository:
    """Read the active AviList reference-taxonomy lineage graph."""

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jTaxonomyLineageRepository":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _run(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._settings.database) as session:
            return session.run(query, **parameters).data()

    def _single(self, query: str, **parameters: Any) -> dict[str, Any]:
        rows = self._run(query, **parameters)
        return rows[0] if rows else {}

    def lineage_for_scientific_name(self, scientific_name: str) -> TaxonomyLineage | None:
        cleaned = scientific_name.strip()
        if not cleaned:
            raise ValueError("scientific_name must not be blank")

        active = self._single(_ACTIVE_CONCEPT_SET_QUERY)
        concept_set_id = active.get("concept_set_id")
        if not concept_set_id:
            # The reference-taxonomy IngestState or its active concept set is
            # missing -- the AviList projection itself is unavailable, which
            # is a different failure than "this name doesn't exist".
            raise ValueError("Active AviList reference-taxonomy concept set is not available")
        taxonomy_release = active.get("taxonomy_release")
        if not taxonomy_release:
            raise ValueError("Active AviList reference-taxonomy release is not available")

        rows = self._run(_LINEAGE_QUERY, concept_set_id=concept_set_id, scientific_name=cleaned)
        if not rows:
            return None
        projection = rows[0]
        if not isinstance(projection, dict) or not isinstance(
            projection.get("lineage_items"), list
        ):
            raise ValueError("Invalid AviList lineage projection")
        raw_items = projection["lineage_items"]
        items: list[LineageTaxon] = []
        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("Invalid AviList lineage projection item")
            required = ("taxon_id", "rank", "scientific_name")
            if any(item.get(field) is None or not str(item[field]).strip() for field in required):
                raise ValueError("Invalid AviList lineage projection item")
            items.append(
                LineageTaxon(
                    taxon_id=str(item["taxon_id"]),
                    rank=str(item["rank"]),
                    scientific_name=str(item["scientific_name"]),
                    authority=None if item.get("authority") is None else str(item["authority"]),
                )
            )
        if not items:
            return None
        return TaxonomyLineage(
            query_scientific_name=cleaned,
            taxonomy_source="AviList",
            taxonomy_release=str(taxonomy_release),
            concept_set_id=str(concept_set_id),
            items=tuple(items),
        )
