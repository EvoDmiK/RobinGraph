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

Two independent read paths are exposed: `lineage_for_scientific_name`
(matches `Taxon.scientific_name`) and `lineage_for_korean_name` (matches a
directly attached `VernacularName {language: 'ko'}`). Both walk the same
ancestor chain and both project each ancestor's own Korean vernacular name
(nullable) into `LineageTaxon.korean_name`. Neither path ever reads or
writes `ExternalTaxonConcept`, and neither ever invents a Korean name that
is not already present as a licensed `VernacularName` node.
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
# preserving order->family->genus->species order in the collected list. Each
# ancestor's own Korean vernacular name (if any) is projected alongside it --
# this is an additive OPTIONAL MATCH on the existing bound `$concept_set_id`,
# so it introduces no new query parameter. If malformed source data attaches
# multiple Korean names to one taxon, `min` deterministically retains one name
# instead of duplicating that lineage node.
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
OPTIONAL MATCH (ancestor)-[:HAS_VERNACULAR_NAME]->(koreanName:VernacularName {language: 'ko'})
WITH ancestor, depth, min(koreanName.name) AS korean_name
ORDER BY depth DESC, ancestor.id
RETURN collect({
  taxon_id: ancestor.id,
  rank: ancestor.rank,
  scientific_name: ancestor.scientific_name,
  authority: ancestor.authority,
  korean_name: korean_name
}) AS lineage_items
"""

# The Korean-name path resolves `target` via its own directly attached
# `VernacularName {language: 'ko'}` (within the active concept set, since
# `target` is required to be `IN_CONCEPT_SET` first) instead of by
# `scientific_name`, then walks the identical deterministic ancestor chain.
# `target.scientific_name` is carried through as `targetScientificName` so
# the caller can report the resolved canonical scientific name alongside the
# Korean query that produced it.
_LINEAGE_BY_KOREAN_NAME_QUERY = """
MATCH (conceptSet:TaxonConceptSet {id: $concept_set_id})
MATCH (target:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(conceptSet)
MATCH (target)-[:HAS_VERNACULAR_NAME]->(vernacular:VernacularName {language: 'ko'})
WHERE toLower(vernacular.name) = toLower($korean_name)
WITH DISTINCT target
ORDER BY target.id
LIMIT 1
WITH target, target.scientific_name AS targetScientificName
OPTIONAL MATCH ancestorPath =
  (target)<-[parentLinks:PARENT_OF*0..3]-(ancestor:Taxon:BirdTaxon)-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id: $concept_set_id})
WHERE all(parentLink IN parentLinks WHERE parentLink.concept_set_id = $concept_set_id)
WITH targetScientificName, ancestor, length(ancestorPath) AS depth
OPTIONAL MATCH (ancestor)-[:HAS_VERNACULAR_NAME]->(koreanName:VernacularName {language: 'ko'})
WITH targetScientificName, ancestor, depth, min(koreanName.name) AS korean_name
ORDER BY depth DESC, ancestor.id
RETURN targetScientificName,
       collect({
         taxon_id: ancestor.id,
         rank: ancestor.rank,
         scientific_name: ancestor.scientific_name,
         authority: ancestor.authority,
         korean_name: korean_name
       }) AS lineage_items
"""


def _parse_lineage_items(raw_items: Any) -> tuple[LineageTaxon, ...]:
    if not isinstance(raw_items, list):
        raise ValueError("Invalid AviList lineage projection")
    items: list[LineageTaxon] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Invalid AviList lineage projection item")
        required = ("taxon_id", "rank", "scientific_name")
        if any(item.get(field) is None or not str(item[field]).strip() for field in required):
            raise ValueError("Invalid AviList lineage projection item")
        korean_name = item.get("korean_name")
        items.append(
            LineageTaxon(
                taxon_id=str(item["taxon_id"]),
                rank=str(item["rank"]),
                scientific_name=str(item["scientific_name"]),
                authority=None if item.get("authority") is None else str(item["authority"]),
                korean_name=None if korean_name is None or not str(korean_name).strip() else str(korean_name),
            )
        )
    return tuple(items)


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

    def _active_concept_set(self) -> tuple[str, str]:
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
        return str(concept_set_id), str(taxonomy_release)

    def lineage_for_scientific_name(self, scientific_name: str) -> TaxonomyLineage | None:
        cleaned = scientific_name.strip()
        if not cleaned:
            raise ValueError("scientific_name must not be blank")

        concept_set_id, taxonomy_release = self._active_concept_set()

        rows = self._run(_LINEAGE_QUERY, concept_set_id=concept_set_id, scientific_name=cleaned)
        if not rows:
            return None
        projection = rows[0]
        if not isinstance(projection, dict) or not isinstance(
            projection.get("lineage_items"), list
        ):
            raise ValueError("Invalid AviList lineage projection")
        items = _parse_lineage_items(projection["lineage_items"])
        if not items:
            return None
        return TaxonomyLineage(
            query_scientific_name=cleaned,
            taxonomy_source="AviList",
            taxonomy_release=taxonomy_release,
            concept_set_id=concept_set_id,
            items=items,
            query_name=cleaned,
            resolved_query_scientific_name=items[-1].scientific_name,
            matched_by="scientific_name",
        )

    def lineage_for_korean_name(self, korean_name: str) -> TaxonomyLineage | None:
        cleaned = korean_name.strip()
        if not cleaned:
            raise ValueError("korean_name must not be blank")

        concept_set_id, taxonomy_release = self._active_concept_set()

        rows = self._run(_LINEAGE_BY_KOREAN_NAME_QUERY, concept_set_id=concept_set_id, korean_name=cleaned)
        if not rows:
            return None
        projection = rows[0]
        if not isinstance(projection, dict) or not isinstance(
            projection.get("lineage_items"), list
        ):
            raise ValueError("Invalid AviList lineage projection")
        target_scientific_name = projection.get("targetScientificName")
        if not target_scientific_name or not str(target_scientific_name).strip():
            raise ValueError("Invalid AviList lineage projection")
        items = _parse_lineage_items(projection["lineage_items"])
        if not items:
            return None
        return TaxonomyLineage(
            query_scientific_name=str(target_scientific_name),
            taxonomy_source="AviList",
            taxonomy_release=taxonomy_release,
            concept_set_id=concept_set_id,
            items=items,
            query_name=cleaned,
            resolved_query_scientific_name=str(target_scientific_name),
            matched_by="korean_name",
        )
