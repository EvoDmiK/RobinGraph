"""Framework-independent request/response DTOs for the public RobinGraph API.

These Pydantic models are the request/response contract of the native
Django/DRF views; the frozen OpenAPI document is checked against them.
They are pure data/validation types: nothing here imports a web framework.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..retrieval.hybrid import HybridResult, HybridSearchOutcome
from ..retrieval.operational import OperationalObservation, OperationalObservationQuery
from ..retrieval.species_scope import SpeciesScope
from ..retrieval.taxonomy_lineage import TaxonomyLineage
from .semantic_router import ChatIntent

if TYPE_CHECKING:
    from ..generation import GeneratedAnswer


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class CitationResponse(BaseModel):
    evidence_id: str
    source_id: str
    source_url: str
    locator: str
    license_name: str


class AnswerResponse(BaseModel):
    answer_id: str
    answer_text: str
    taxon_ids: list[str]
    evidence_ids: list[str]
    citations: list[CitationResponse]
    disposition: str
    warnings: list[str]
    taxonomy_release: str
    data_cutoff: str


SearchMode = Literal["fulltext", "hybrid"]
SearchHandler = Callable[[str, int, bool], HybridSearchOutcome]
AnswerGenerator = Callable[[str, "tuple[HybridResult, ...]"], "GeneratedAnswer"]


class DocumentSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    mode: SearchMode = "fulltext"
    limit: int = Field(default=10, ge=1, le=100)


class SearchCitationResponse(BaseModel):
    source_id: str
    source_url: str
    locator: str
    license_name: str


class SearchResultResponse(BaseModel):
    chunk_id: str
    text: str
    score: float
    channels: list[str]
    citation: SearchCitationResponse


class DocumentSearchResponse(BaseModel):
    requested_mode: SearchMode
    mode: SearchMode
    fixture_only: bool
    results: list[SearchResultResponse]
    warnings: list[str]


class SearchBackendUnavailableError(RuntimeError):
    """Search could not run because a configured external dependency failed."""


class OperationalBackendUnavailableError(RuntimeError):
    """The operational GBIF observation graph could not be read safely."""


ObservationSearchHandler = Callable[
    [OperationalObservationQuery], tuple[OperationalObservation, ...]
]


class OperationalTaxonResponse(BaseModel):
    taxon_id: str
    external_key: str
    scientific_name: str
    canonical_name: str | None
    vernacular_name_raw: str | None
    rank: str


class OperationalPlaceResponse(BaseModel):
    place_id: str
    name: str
    country_code: str


class OperationalCitationResponse(BaseModel):
    evidence_id: str
    dataset_id: str
    dataset_name: str
    source_url: str
    dataset_url: str
    license_uris: list[str]
    retrieved_at: str
    source_updated_at: str | None


class OperationalMediaResponse(BaseModel):
    media_id: str
    media_type: str
    format: str | None
    landing_uri: str
    asset_uri: str | None
    creator: str | None
    publisher: str | None
    attribution: str
    license_uri: str


class OperationalObservationResponse(BaseModel):
    observation_id: str
    occurrence_id: str
    observed_at: str
    count: int | None
    basis: str
    sensitivity: str
    coordinate_disclosure: Literal["public", "withheld"]
    latitude: float | None
    longitude: float | None
    coordinate_uncertainty_m: float | None
    taxon: OperationalTaxonResponse
    place: OperationalPlaceResponse
    citation: OperationalCitationResponse
    media: list[OperationalMediaResponse]


class OperationalObservationSearchResponse(BaseModel):
    mode: Literal["operational"] = "operational"
    data_source: Literal["gbif"] = "gbif"
    fixture_only: Literal[False] = False
    limit: int
    offset: int
    returned: int
    results: list[OperationalObservationResponse]
    warnings: list[str]


class TaxonomyLineageBackendUnavailableError(RuntimeError):
    """The AviList reference-taxonomy graph could not be read safely."""


LineageHandler = Callable[[str], "TaxonomyLineage | None"]


class LineageTaxonResponse(BaseModel):
    taxon_id: str
    rank: str
    scientific_name: str
    authority: str | None
    korean_name: str | None
    korean_name_status: str | None = None
    korean_name_source_url: str | None = None
    english_name: str | None = None
    display_name: str | None = None


class TaxonomyLineageResponse(BaseModel):
    query_name: str
    query_scientific_name: str
    resolved_query_scientific_name: str
    matched_by: Literal["scientific_name", "korean_name", "english_name"]
    taxonomy_source: Literal["AviList"] = "AviList"
    taxonomy_release: str
    concept_set_id: str
    lineage: list[LineageTaxonResponse]


# Integrated chat is intentionally additive.  It exposes only filters the
# established bounded handlers understand; it never accepts arbitrary Cypher,
# coordinates, or a common-name observation filter the operational handler
# cannot promise to honor.
class _ChatModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxonomyChatFilters(_ChatModel):
    kind: Literal["taxonomy"] = "taxonomy"
    scientific_name: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def exactly_one_name(self) -> "TaxonomyChatFilters":
        values = [value for value in (self.scientific_name, self.name) if value is not None]
        if len(values) > 1:
            raise ValueError("only one taxonomy name filter is allowed")
        if values and not values[0].strip():
            raise ValueError("taxonomy name must not be blank")
        return self


class ProfileChatFilters(_ChatModel):
    kind: Literal["profile"] = "profile"
    name: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("profile name must not be blank")
        return value


class ObservationChatFilters(_ChatModel):
    kind: Literal["observations"] = "observations"
    taxon_key: str | None = Field(default=None, max_length=50)
    scientific_name: str | None = Field(default=None, max_length=200)
    place: str | None = Field(default=None, max_length=200)
    observed_from: date | None = None
    observed_to: date | None = None
    limit: int = Field(default=10, ge=1, le=10)

    @model_validator(mode="after")
    def valid_dates_and_text(self) -> "ObservationChatFilters":
        if self.observed_from and self.observed_to and self.observed_from > self.observed_to:
            raise ValueError("observed_from must not be later than observed_to")
        for value in (self.taxon_key, self.scientific_name, self.place):
            if value is not None and not value.strip():
                raise ValueError("observation text filters must not be blank")
        return self


class EvidenceChatFilters(_ChatModel):
    kind: Literal["evidence"] = "evidence"
    limit: int = Field(default=10, ge=1, le=10)


ChatFilters = Annotated[
    TaxonomyChatFilters | ProfileChatFilters | ObservationChatFilters | EvidenceChatFilters,
    Field(discriminator="kind"),
]


class ChatRequest(_ChatModel):
    question: str = Field(min_length=1, max_length=2_000)
    intent: Literal["auto", "taxonomy", "profile", "observations", "evidence"] = "auto"
    filters: ChatFilters | None = None
    defer_enrichment: bool = False
    defer_discovery: bool = False
    species_scope: SpeciesScope = "all"

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be blank")
        return cleaned

    @model_validator(mode="after")
    def route_filter_matches_explicit_intent(self) -> "ChatRequest":
        if self.filters is not None and self.intent != "auto" and self.filters.kind != self.intent:
            raise ValueError("filters must match the selected intent")
        return self


class ChatTaxonomyResult(_ChatModel):
    kind: Literal["taxonomy"] = "taxonomy"
    lineage: TaxonomyLineageResponse | None


class ChatSpeciesResult(_ChatModel):
    kind: Literal["profile"] = "profile"
    profile: dict | None
    question_answer: dict | None = None
    similar_species: dict | None = None
    subspecies: dict | None = None


class ChatObservationsResult(_ChatModel):
    kind: Literal["observations"] = "observations"
    results: list[OperationalObservationResponse]
    limit: int


class ChatEvidenceResult(_ChatModel):
    kind: Literal["evidence"] = "evidence"
    search: DocumentSearchResponse


class ChatClarifyChoice(_ChatModel):
    label: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2_000)


class ChatClarifyResult(_ChatModel):
    kind: Literal["clarify"] = "clarify"
    prompt: str
    choices: list[ChatClarifyChoice] = Field(default_factory=list, max_length=3, exclude_if=lambda value: not value)


class EntityCandidateResponse(_ChatModel):
    taxon_id: str = Field(min_length=1, max_length=256)
    scientific_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=-1, le=1, allow_inf_nan=False)
    question: str | None = None
    route_intent: Literal["auto", "profile"] = Field(default="profile", exclude_if=lambda value: value == "profile")


class EntityResolutionResponse(_ChatModel):
    mention: str
    status: Literal["matched", "candidates", "not_found", "unavailable"]
    method: Literal["graph_exact", "graph_normalized", "vector", "none"]
    canonical_name: str | None = None
    taxon_id: str | None = None
    concept_set_id: str | None = None
    taxonomy_release: str | None = None
    candidates: list[EntityCandidateResponse] = Field(default_factory=list, max_length=3)


class ChatNameRelationsResult(_ChatModel):
    kind: Literal["name_relations"] = "name_relations"
    relationships: dict


class ChatGraphResult(_ChatModel):
    kind: Literal["graph_query"] = "graph_query"
    payload: dict


ChatResult = Annotated[
    ChatTaxonomyResult | ChatSpeciesResult | ChatObservationsResult | ChatEvidenceResult | ChatClarifyResult | ChatNameRelationsResult | ChatGraphResult,
    Field(discriminator="kind"),
]


class ChatResponse(_ChatModel):
    selected_intent: ChatIntent | None
    route_method: Literal["semantic", "explicit", "deterministic", "jev"]
    disposition: Literal["answer", "abstain", "clarify"]
    answer_text: str
    warnings: list[str]
    result: ChatResult
    entity_resolution: EntityResolutionResponse | None = None
