"""FastAPI application shared by fixture (offline) and Neo4j retrieval modes.

The active `GraphRepository` decides the retrieval backend; the Answer/
Citation response contract and provenance validation are identical either
way. `/health` discloses which mode is active so operators and tests do not
have to guess.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from ..fixture import load_fixture
from ..graph.settings import Neo4jSettings
from ..retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, HybridSearchOutcome
from ..retrieval.operational import (
    OperationalObservation,
    OperationalObservationQuery,
    OperationalObservationRepository,
)
from ..retrieval.repository import GraphRepository
from ..retrieval.fixture_repository import FixtureRepository
from ..retrieval.taxonomy_lineage import TaxonomyLineage, TaxonomyLineageRepository
from ..slice import Answer, QuestionService, validate_answer


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


class TaxonomyLineageResponse(BaseModel):
    query_name: str
    query_scientific_name: str
    resolved_query_scientific_name: str
    matched_by: Literal["scientific_name", "korean_name"]
    taxonomy_source: Literal["AviList"] = "AviList"
    taxonomy_release: str
    concept_set_id: str
    lineage: list[LineageTaxonResponse]


def _response(answer: Answer) -> AnswerResponse:
    return AnswerResponse(
        answer_id=answer.answer_id,
        answer_text=answer.answer_text,
        taxon_ids=list(answer.taxon_ids),
        evidence_ids=list(answer.evidence_ids),
        citations=[CitationResponse(**citation.__dict__) for citation in answer.citations],
        disposition=answer.disposition,
        warnings=list(answer.warnings),
        taxonomy_release=answer.taxonomy_release,
        data_cutoff=answer.data_cutoff,
    )


def _search_response(outcome: HybridSearchOutcome, *, requested_mode: SearchMode) -> DocumentSearchResponse:
    actual_mode: SearchMode = (
        "hybrid" if any(VECTOR_CHANNEL in result.channels for result in outcome.results) else "fulltext"
    )
    return DocumentSearchResponse(
        requested_mode=requested_mode,
        mode=actual_mode,
        fixture_only=True,
        results=[
            SearchResultResponse(
                chunk_id=result.chunk_id,
                text=result.text,
                score=result.score,
                channels=list(result.channels),
                citation=SearchCitationResponse(**result.citation.__dict__),
            )
            for result in outcome.results
        ],
        warnings=list(outcome.warnings),
    )


def _operational_observation_response(
    observation: OperationalObservation,
) -> OperationalObservationResponse:
    return OperationalObservationResponse(
        observation_id=observation.observation_id,
        occurrence_id=observation.occurrence_id,
        observed_at=observation.observed_at,
        count=observation.count,
        basis=observation.basis,
        sensitivity=observation.sensitivity,
        coordinate_disclosure=observation.coordinate_disclosure,
        latitude=observation.latitude,
        longitude=observation.longitude,
        coordinate_uncertainty_m=observation.coordinate_uncertainty_m,
        taxon=OperationalTaxonResponse(**observation.taxon.__dict__),
        place=OperationalPlaceResponse(**observation.place.__dict__),
        citation=OperationalCitationResponse(
            evidence_id=observation.citation.evidence_id,
            dataset_id=observation.citation.dataset_id,
            dataset_name=observation.citation.dataset_name,
            source_url=observation.citation.source_url,
            dataset_url=observation.citation.dataset_url,
            license_uris=list(observation.citation.license_uris),
            retrieved_at=observation.citation.retrieved_at,
            source_updated_at=observation.citation.source_updated_at,
        ),
        media=[OperationalMediaResponse(**value.__dict__) for value in observation.media],
    )


def _lineage_response(lineage: TaxonomyLineage) -> TaxonomyLineageResponse:
    return TaxonomyLineageResponse(
        query_name=lineage.query_name if lineage.query_name is not None else lineage.query_scientific_name,
        query_scientific_name=lineage.query_scientific_name,
        resolved_query_scientific_name=(
            lineage.resolved_query_scientific_name
            if lineage.resolved_query_scientific_name is not None
            else lineage.query_scientific_name
        ),
        matched_by=lineage.matched_by,
        taxonomy_release=lineage.taxonomy_release,
        concept_set_id=lineage.concept_set_id,
        lineage=[LineageTaxonResponse(**item.__dict__) for item in lineage.items],
    )


def create_neo4j_search_handler(settings: Neo4jSettings) -> SearchHandler:
    """Build the read-only Neo4j/Jina search boundary used by FastAPI."""

    def handle(question: str, limit: int, hybrid: bool) -> HybridSearchOutcome:
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        from ..embeddings import EmbeddingConfigurationError, EmbeddingError, JinaEmbeddingClient
        from ..retrieval.neo4j_hybrid import HybridSearchRequest, search

        top_k = max(25, limit)
        channels = (FULLTEXT_CHANNEL, VECTOR_CHANNEL) if hybrid else (FULLTEXT_CHANNEL,)
        request = HybridSearchRequest(
            query_text=question,
            limit=limit,
            fulltext_top_k=top_k,
            vector_top_k=top_k,
            channels=channels,
        )
        try:
            if not hybrid:
                return search(settings, request)
            try:
                client = JinaEmbeddingClient.from_env()
            except EmbeddingConfigurationError as error:
                raise SearchBackendUnavailableError(str(error)) from error
            try:
                return search(settings, request, query_embedder=client)
            except EmbeddingError:
                fallback_request = HybridSearchRequest(
                    query_text=question,
                    limit=limit,
                    fulltext_top_k=top_k,
                    vector_top_k=top_k,
                    channels=(FULLTEXT_CHANNEL,),
                )
                outcome = search(settings, fallback_request)
                return HybridSearchOutcome(
                    results=outcome.results,
                    warnings=(*outcome.warnings, "Embedding request failed; results are keyword-only fulltext"),
                )
        except (Neo4jError, ServiceUnavailable, SessionExpired) as error:
            raise SearchBackendUnavailableError("Neo4j search is unavailable") from error

    return handle


def create_neo4j_observation_handler(
    repository: OperationalObservationRepository,
) -> ObservationSearchHandler:
    """Map Neo4j and malformed-projection failures to a safe API boundary."""

    def handle(query: OperationalObservationQuery) -> tuple[OperationalObservation, ...]:
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            return repository.search_observations(query)
        except (Neo4jError, ServiceUnavailable, SessionExpired, ValueError) as error:
            raise OperationalBackendUnavailableError(
                "Operational GBIF observation search is unavailable"
            ) from error

    return handle


def create_neo4j_lineage_handler(repository: TaxonomyLineageRepository) -> LineageHandler:
    """Map Neo4j and missing-projection failures to a safe API boundary."""

    def handle(scientific_name: str) -> "TaxonomyLineage | None":
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            return repository.lineage_for_scientific_name(scientific_name)
        except (Neo4jError, ServiceUnavailable, SessionExpired, ValueError) as error:
            raise TaxonomyLineageBackendUnavailableError(
                "AviList reference-taxonomy lineage is unavailable"
            ) from error

    return handle


def create_neo4j_korean_lineage_handler(repository: TaxonomyLineageRepository) -> LineageHandler:
    """Map Neo4j and missing-projection failures to a safe API boundary.

    Mirrors `create_neo4j_lineage_handler` but resolves by the target's
    directly attached Korean `VernacularName` instead of by scientific name.
    """

    def handle(korean_name: str) -> "TaxonomyLineage | None":
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            return repository.lineage_for_korean_name(korean_name)
        except (Neo4jError, ServiceUnavailable, SessionExpired, ValueError) as error:
            raise TaxonomyLineageBackendUnavailableError(
                "AviList reference-taxonomy lineage is unavailable"
            ) from error

    return handle


def create_app(
    repository: GraphRepository | None = None,
    *,
    search_handler: SearchHandler | None = None,
    observation_handler: ObservationSearchHandler | None = None,
    lineage_handler: LineageHandler | None = None,
    korean_lineage_handler: LineageHandler | None = None,
) -> FastAPI:
    repository = repository or FixtureRepository(load_fixture())
    service = QuestionService(repository)
    app = FastAPI(title="RobinGraph", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": repository.mode, "taxonomy_release": repository.taxonomy_release}

    @app.post("/v1/answers", response_model=AnswerResponse)
    def answer_question(request: QuestionRequest) -> AnswerResponse:
        answer = service.answer(request.question)
        try:
            validate_answer(answer, repository)
        except ValueError as error:
            raise HTTPException(status_code=500, detail="Answer provenance validation failed") from error
        return _response(answer)

    @app.post(
        "/v1/search",
        response_model=DocumentSearchResponse,
        responses={503: {"description": "Neo4j mode or a configured search dependency is unavailable"}},
    )
    def search_documents(request: DocumentSearchRequest) -> DocumentSearchResponse:
        if search_handler is None:
            raise HTTPException(status_code=503, detail="Document search is available only in Neo4j mode")
        try:
            outcome = search_handler(request.question, request.limit, request.mode == "hybrid")
        except SearchBackendUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return _search_response(outcome, requested_mode=request.mode)

    @app.get(
        "/v1/observations",
        response_model=OperationalObservationSearchResponse,
        responses={503: {"description": "The operational GBIF observation graph is unavailable"}},
    )
    def search_operational_observations(
        taxon_key: str | None = Query(default=None, min_length=1, max_length=50),
        scientific_name: str | None = Query(default=None, min_length=1, max_length=200),
        place: str | None = Query(default=None, min_length=1, max_length=200),
        observed_from: date | None = None,
        observed_to: date | None = None,
        limit: int = Query(default=25, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> OperationalObservationSearchResponse:
        if observation_handler is None:
            raise HTTPException(
                status_code=503,
                detail="Operational GBIF observation search is available only in Neo4j mode",
            )
        for name, value in (
            ("taxon_key", taxon_key),
            ("scientific_name", scientific_name),
            ("place", place),
        ):
            if value is not None and not value.strip():
                raise HTTPException(status_code=422, detail=f"{name} must not be blank")
        if observed_from and observed_to and observed_from > observed_to:
            raise HTTPException(status_code=422, detail="observed_from must not be later than observed_to")
        query = OperationalObservationQuery(
            taxon_key=taxon_key,
            scientific_name=scientific_name,
            place=place,
            observed_from=observed_from.isoformat() if observed_from else None,
            observed_to=observed_to.isoformat() if observed_to else None,
            limit=limit,
            offset=offset,
        )
        try:
            observations = observation_handler(query)
        except OperationalBackendUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        warnings = []
        if any(observation.coordinate_disclosure == "withheld" for observation in observations):
            warnings.append("Coordinates for generalized observations are withheld")
        return OperationalObservationSearchResponse(
            limit=limit,
            offset=offset,
            returned=len(observations),
            results=[_operational_observation_response(value) for value in observations],
            warnings=warnings,
        )

    @app.get(
        "/v1/taxa/lineage",
        response_model=TaxonomyLineageResponse,
        responses={
            404: {"description": "No active AviList lineage exists for scientific_name or name"},
            422: {"description": "Exactly one nonblank scientific_name or name query parameter is required"},
            503: {"description": "The AviList reference-taxonomy projection is unavailable"},
        },
    )
    def get_taxonomy_lineage(
        scientific_name: str | None = Query(default=None, min_length=1, max_length=200),
        name: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> TaxonomyLineageResponse:
        provided = [
            (query_param, value)
            for query_param, value in (("scientific_name", scientific_name), ("name", name))
            if value is not None
        ]
        if len(provided) != 1:
            raise HTTPException(
                status_code=422,
                detail="Exactly one of scientific_name or name is required",
            )
        query_param, raw_value = provided[0]
        cleaned = raw_value.strip()
        if not cleaned:
            raise HTTPException(status_code=422, detail=f"{query_param} must not be blank")

        if query_param == "scientific_name":
            if lineage_handler is None:
                raise HTTPException(status_code=503, detail="Taxonomy lineage is available only in Neo4j mode")
            try:
                lineage = lineage_handler(cleaned)
            except TaxonomyLineageBackendUnavailableError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            if lineage is None:
                raise HTTPException(
                    status_code=404, detail="No active AviList lineage found for scientific_name"
                )
        else:
            if korean_lineage_handler is None:
                raise HTTPException(status_code=503, detail="Taxonomy lineage is available only in Neo4j mode")
            try:
                lineage = korean_lineage_handler(cleaned)
            except TaxonomyLineageBackendUnavailableError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            if lineage is None:
                raise HTTPException(
                    status_code=404, detail="No licensed Korean vernacular name found for name"
                )
        return _lineage_response(lineage)

    return app


app = create_app()
