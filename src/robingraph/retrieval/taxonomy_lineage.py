"""Read-only contract for the AviList reference-taxonomy lineage lookup.

This is deliberately its own small protocol, separate from `GraphRepository`
and `OperationalObservationRepository`: it reads the AviList reference
taxonomy graph (`Taxon:BirdTaxon`, gated by the `reference-taxonomy`
`IngestState`), which is a different data area from both the fixture
`Taxon` graph and the GBIF `ExternalTaxonConcept` operational graph. The two
taxonomies are never merged (see `docs/graph-database-schema.md`).

A lineage can be resolved two ways: by the exact (case-insensitive)
`Taxon.scientific_name`, or by an exact (case-insensitive) Korean
`VernacularName` (`language='ko'`) directly attached to the target `Taxon`
within the active concept set. The AviList ingest currently only loads
English vernacular names (`language='en'`) -- see
`docs/graph-database-schema.md` -- so the Korean path is a real, licensed
lookup key with no guaranteed data yet; it must fail closed (404) rather
than fabricate a translation when no Korean `VernacularName` exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
from typing import Literal, Protocol

MatchedBy = Literal["scientific_name", "korean_name", "english_name"]

# Reference English names; no invented Korean subspecies names.
SUBSPECIES_NAME_REFERENCES = {
    'avilist-taxon:v2025b:5421': {
        'scientific_name': 'Ardea cinerea jouyi',
        'english_name': 'Oriental Grey Heron',
        'source_title': 'Birds New Zealand · Checklist of the Birds of New Zealand (2022), p.175',
        'source_url': 'https://www.birdsnz.org.nz/wp-content/uploads/2022/05/checklist-2022.pdf',
    },
    'avilist-taxon:v2025b:5422': {
        'scientific_name': 'Ardea cinerea monicae',
        'english_name': 'Mauritanian Heron',
        'source_title': 'Dansk Ornitologisk Forening · Names of the birds of the World (2019)',
        'source_url': 'https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf',
    },
    'avilist-taxon:v2025b:546': {
        'scientific_name': 'Anas platyrhynchos conboschas',
        'english_name': 'Greenland Mallard',
        'source_title': 'Dansk Ornitologisk Forening · Names of the birds of the World (2019)',
        'source_url': 'https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf',
    },
    'avilist-taxon:v2025b:545': {
        'scientific_name': 'Anas platyrhynchos platyrhynchos',
        'english_name': 'Northern Mallard',
        'source_title': 'NCBI Taxonomy · Anas platyrhynchos platyrhynchos (8840)',
        'source_url': 'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=8840',
    },
}


@dataclass(frozen=True)
class LineageTaxon:
    taxon_id: str
    rank: str
    scientific_name: str
    authority: str | None
    korean_name: str | None = None
    # `VernacularName.status` for whichever Korean name won the deterministic
    # tie-break in the Neo4j reader (e.g. "community-sourced" for the
    # Wikidata ingest, "source-preferred" for a future official source).
    # `None` whenever `korean_name` is `None`. This tells a caller a name is
    # not (yet) an official Korean standard name -- see
    # docs/decisions/0002-taxonomy-backbone.md and
    # docs/n8n/korean-vernacular-ingest.md.
    korean_name_status: str | None = None
    korean_name_source_url: str | None = None
    english_name: str | None = None


@cache
def reference_korean_names() -> dict:
    """Pinned CC0 Wikidata display labels; never replace active graph names."""
    return json.loads(Path(__file__).with_name("taxonomy_ko_labels.json").read_text(encoding="utf-8"))["labels"]


@cache
def sourced_korean_names() -> dict:
    """Source-checked Korean names bound to the reviewed AviList release."""
    return json.loads(Path(__file__).with_name("species_ko_names.json").read_text(encoding="utf-8"))["labels"]


@cache
def sourced_subspecies_names() -> dict:
    """Source-audited common-name facts, bound to exact AviList subspecies IDs."""
    data = json.loads(Path(__file__).with_name('subspecies_name_references.json').read_text(encoding='utf-8'))
    if (data['schema_version'] != 1 or data['taxonomy']['release'] != 'v2025b'
            or data['taxonomy']['concept_set_id'] != 'rg:concept-set:avilist-v2025b'
            or data['taxonomy']['rank'] != 'subspecies'):
        raise ValueError('Subspecies name reference release mismatch')
    names = {}
    for taxon_id, reference in data['names'].items():
        evidence = reference['evidence'][0]
        source = data['sources'][evidence['source_id']]
        page = evidence['locator']['page']
        names[taxon_id] = {**reference, 'source_url': source['url'] + f'#page={page}',
                          'source_title': source['title'] + f' · PDF {page}쪽'}
    return names


def with_korean_display_name(taxon: dict) -> dict:
    """Use scoped Korean display names, preserving their source or manual status."""
    if taxon.get("rank") == "subspecies":
        if taxon.get('korean_name_status') == 'machine-translated':
            taxon = {**taxon, 'korean_name': None, 'korean_name_status': None, 'korean_name_source_url': None}
        reference = SUBSPECIES_NAME_REFERENCES.get(taxon.get("taxon_id")) or sourced_subspecies_names().get(taxon.get("taxon_id"))
        if (reference and reference['scientific_name'] == taxon.get('scientific_name')
                and taxon.get('english_name') in (None, '', reference['english_name'])):
            return {**taxon, 'english_name': reference['english_name'],
                    'english_name_source_url': reference['source_url'],
                    'english_name_source_title': reference['source_title'], 'english_name_status': 'source-reference'}
        return taxon
    if taxon.get("rank") != "species":
        return taxon
    display_english = None
    for taxon_id, science, canonical, display in (
            ('avilist-taxon:v2025b:20198', 'Pica pica', 'Eurasian Magpie', 'Eurasian magpie'),
            ('avilist-taxon:v2025b:20193', 'Pica serica', 'Oriental Magpie', 'Oriental magpie')):
        if (taxon.get('taxon_id') == taxon_id and taxon.get('scientific_name') == science
                and taxon.get('english_name') in (canonical, display)):
            display_english = display
            taxon = {**taxon, 'english_name':canonical}
            break
    label = sourced_korean_names().get(taxon.get("taxon_id"))
    if (label and label["scientific_name"] == taxon.get("scientific_name")
            and label["english_name"] == taxon.get("english_name")):
        return {**taxon, "english_name": display_english or taxon.get('english_name'),
                "korean_name": label["name"],
                "korean_name_status": label["status"],
                "korean_name_source_url": label["source_url"]}
    return {**taxon, "english_name": display_english or taxon.get('english_name'),
            "korean_name": None, "korean_name_status": None,
            "korean_name_source_url": None}


@dataclass(frozen=True)
class TaxonomyLineage:
    query_scientific_name: str
    taxonomy_source: str
    taxonomy_release: str
    concept_set_id: str
    items: tuple[LineageTaxon, ...]
    # New, additive fields (defaulted so existing positional/keyword
    # construction of this dataclass keeps working unchanged):
    query_name: str | None = None
    resolved_query_scientific_name: str | None = None
    matched_by: MatchedBy = "scientific_name"


class TaxonomyLineageRepository(Protocol):
    """Read-only access to the active AviList reference-taxonomy lineage."""

    def lineage_for_scientific_name(self, scientific_name: str) -> TaxonomyLineage | None:
        """Ordered order->family->genus->species[->subspecies] lineage for an exact name match.

        `scientific_name` is matched case-insensitively against the exact
        scientific name of a `Taxon:BirdTaxon` in the currently active
        `reference-taxonomy` concept set. Returns `None` when no such taxon
        exists -- callers should treat that as "not found", not as a backend
        failure.
        """
        ...

    def lineage_for_korean_name(self, korean_name: str) -> TaxonomyLineage | None:
        """Ordered order->family->genus->species[->subspecies] lineage for an exact Korean-name match.

        `korean_name` is matched case-insensitively against a
        `VernacularName {language: 'ko'}` directly attached
        (`HAS_VERNACULAR_NAME`) to a `Taxon:BirdTaxon` in the currently
        active `reference-taxonomy` concept set. Returns `None` when no such
        licensed Korean vernacular name exists -- callers should treat that
        as "not found", not as a backend failure.
        """
        ...
