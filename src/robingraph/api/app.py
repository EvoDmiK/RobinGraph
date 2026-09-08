"""FastAPI application shared by fixture (offline) and Neo4j retrieval modes.

The active `GraphRepository` decides the retrieval backend; the Answer/
Citation response contract and provenance validation are identical either
way. `/health` discloses which mode is active so operators and tests do not
have to guess.
"""

from __future__ import annotations

from typing import Callable, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..fixture import load_fixture
from ..graph.settings import Neo4jSettings
from ..retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, HybridSearchOutcome
from ..retrieval.repository import GraphRepository
from ..retrieval.fixture_repository import FixtureRepository
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


def create_app(
    repository: GraphRepository | None = None,
    *,
    search_handler: SearchHandler | None = None,
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

    return app


app = create_app()
