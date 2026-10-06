"""FastAPI application shared by fixture (offline) and Neo4j retrieval modes.

The active `GraphRepository` decides the retrieval backend; the Answer/
Citation response contract and provenance validation are identical either
way. `/health` discloses which mode is active so operators and tests do not
have to guess.
"""

from __future__ import annotations

from datetime import date
import functools
from hashlib import sha256
import logging
import os
import re
from pathlib import Path
import stat
from typing import TYPE_CHECKING, Annotated, Callable, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from langchain_core.runnables import RunnableLambda
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .. import tracing
from ..embeddings import EmbeddingClient
from ..fixture import load_fixture
from ..graph.settings import Neo4jSettings
from ..retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL, HybridResult, HybridSearchOutcome
from ..retrieval.operational import (
    OperationalObservation,
    OperationalObservationQuery,
    OperationalObservationRepository,
)
from ..retrieval.repository import GraphRepository
from ..retrieval.fixture_repository import FixtureRepository
from ..retrieval.species_profile import SpeciesNotFoundError, species_summary
from ..retrieval.species_questions import parse_species_question, focused_answer
from ..retrieval.name_relations import reviewed_search_terms
from ..retrieval.taxonomy_lineage import TaxonomyLineage, TaxonomyLineageRepository
from ..slice import Answer, QuestionService, validate_answer
from .ingest_router import IngestStore, create_ingest_router
from .semantic_router import ChatIntent, SemanticRouter

if TYPE_CHECKING:
    # The evidence-route answer generator is an optional integration seam.
    # Typing it against the real adapter without importing it at runtime
    # keeps this module loadable in deployments that never configure
    # generation (fixture mode, unconfigured Neo4j serving).
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


class TaxonomyLineageResponse(BaseModel):
    query_name: str
    query_scientific_name: str
    resolved_query_scientific_name: str
    matched_by: Literal["scientific_name", "korean_name"]
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


class ChatObservationsResult(_ChatModel):
    kind: Literal["observations"] = "observations"
    results: list[OperationalObservationResponse]
    limit: int


class ChatEvidenceResult(_ChatModel):
    kind: Literal["evidence"] = "evidence"
    search: DocumentSearchResponse


class ChatClarifyResult(_ChatModel):
    kind: Literal["clarify"] = "clarify"
    prompt: str


class ChatNameRelationsResult(_ChatModel):
    kind: Literal["name_relations"] = "name_relations"
    relationships: dict


ChatResult = Annotated[
    ChatTaxonomyResult | ChatSpeciesResult | ChatObservationsResult | ChatEvidenceResult | ChatClarifyResult | ChatNameRelationsResult,
    Field(discriminator="kind"),
]


class ChatResponse(_ChatModel):
    selected_intent: ChatIntent | None
    route_method: Literal["semantic", "explicit", "deterministic"]
    disposition: Literal["answer", "abstain", "clarify"]
    answer_text: str
    warnings: list[str]
    result: ChatResult


_DEFAULT_STATIC_ROOT = Path(__file__).resolve().parent / "static"
_CHAT_UI_UNAVAILABLE = "Chat UI is temporarily unavailable."
_SEARCH_UNAVAILABLE = "Document search is temporarily unavailable."
_REQUIRED_CHAT_ASSETS = ("index.html", "chat.js", "styles.css")
_CHAT_ASSET_MEDIA_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "chat.js": "application/javascript",
    "styles.css": "text/css; charset=utf-8",
    "birds.html": "text/html; charset=utf-8",
    "birds.js": "application/javascript",
}


def _read_chat_asset_bundle(asset_root: Path, asset_names: tuple[str, ...] = _REQUIRED_CHAT_ASSETS) -> dict[str, bytes] | None:
    """Read a complete, non-empty chat bundle or return ``None`` without leaking errors.

    Each response reads every required asset before serving anything.  Reading the
    bytes from the validated file descriptor keeps the validation/use window small:
    a replacement or removal after opening cannot turn a checked bundle into a
    partial response.
    """

    assets: dict[str, bytes] = {}
    try:
        for asset_name in asset_names:
            descriptor = os.open(asset_root / asset_name, os.O_RDONLY)
            try:
                with os.fdopen(descriptor, "rb") as asset_file:
                    descriptor = -1
                    metadata = os.fstat(asset_file.fileno())
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0:
                        return None
                    content = asset_file.read()
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            if not content or len(content) != metadata.st_size:
                return None
            assets[asset_name] = content
    except OSError:
        return None
    return assets


def _chat_asset_response(assets: dict[str, bytes], name: str) -> Response:
    content = assets[name]
    if name.endswith(".html"):
        for asset_name, asset_content in assets.items():
            if asset_name.endswith((".js", ".css")):
                url = f"/static/{asset_name}".encode()
                version = sha256(asset_content).hexdigest()[:16].encode()
                content = content.replace(url, url + b"?v=" + version)
    return Response(content, media_type=_CHAT_ASSET_MEDIA_TYPES[name],
                    headers={"Cache-Control": "no-cache, must-revalidate"})


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


def _generated_evidence_answer(
    generator: AnswerGenerator, question: str, results: tuple[HybridResult, ...]
) -> str | None:
    """Return a citation-qualified answer, or ``None`` to fail closed.

    A provider error, a blank/duplicate evidence id, or an evidence id
    outside the retrieved chunk set must never surface as an invented
    answer or leak provider details -- the caller falls back to the
    existing retrieval-only response text in every such case.
    """

    try:
        generated = generator(question, results)
        evidence_ids = tuple(generated.evidence_ids)
        answer_text = generated.text
    except Exception:
        return None
    if not evidence_ids or any(
        not isinstance(evidence_id, str) or not evidence_id.strip()
        for evidence_id in evidence_ids
    ):
        return None
    if len(set(evidence_ids)) != len(evidence_ids):
        return None
    retrieved_ids = {result.chunk_id for result in results}
    if not set(evidence_ids) <= retrieved_ids:
        return None
    if not isinstance(answer_text, str) or not answer_text.strip():
        return None
    return f"{answer_text} [{', '.join(evidence_ids)}]"


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


_KOREAN_RANKS = {"order": "목", "family": "과", "genus": "속", "species": "종", "subspecies": "아종"}
_RANK_QUESTION = re.compile(r"(?:무슨|어느|어떤)\s*(아종|목|과|속|종)(?=에|이|인|야|입|\s|[?？]|$)")
_SPECIES_NAME = r"(?P<name>[가-힣]+?|[A-Za-z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)"
_TAXONOMY_QUESTION = re.compile(
    rf"^{_SPECIES_NAME}(?:의|은|는|이|가)?\s+(?:분류\s*체계|분류|계통)(?:에\s*대해)?\s*(?:알려줘|알려주세요|설명해줘|설명해주세요|알고\s*싶어(?:요)?)[.!?？]*$"
)
_PROFILE_QUESTION = re.compile(
    rf"^{_SPECIES_NAME}(?:에\s*대해|에\s*관해)\s*(?:알고\s*싶어(?:요)?|알려줘|알려주세요|설명해줘|설명해주세요)[.!?？]*$"
)
_AUTO_RANK_QUESTION = re.compile(
    rf"^{_SPECIES_NAME}(?:은|는|이|가)\s+(?:무슨|어느|어떤)\s*(?:아종|목|과|속|종)(?:에\s*속해|이야|인가요|입니까|인가|입니까)?[.!?？]*$"
)


def _species_chat_question(question: str) -> tuple[Literal["taxonomy", "profile"], str] | None:
    for pattern, intent in ((_TAXONOMY_QUESTION, "taxonomy"), (_AUTO_RANK_QUESTION, "taxonomy"), (_PROFILE_QUESTION, "profile")):
        match = pattern.fullmatch(question)
        if match:
            return intent, match.group("name")
    # Reviewed usages may contain spaces or a domestic-form trinomial.
    # Only allow listed names, rather than widening free-form species parsing.
    match = re.fullmatch(
        r"(?P<name>.+?)(?:에\s*대해|에\s*관해)\s*(?:알고\s*싶어(?:요)?|알려줘|알려주세요|설명해줘|설명해주세요)[.!?？]*",
        question,
    )
    if match and match.group("name").strip().lower() in reviewed_search_terms():
        return "profile", match.group("name").strip()
    return None


def _taxonomy_answer(question: str, lineage: TaxonomyLineage) -> tuple[str, bool]:
    requested = _RANK_QUESTION.search(question)
    if requested is None:
        return "분류 계통을 확인했습니다.", True
    rank_label = requested.group(1)
    target = next((item for item in lineage.items if _KOREAN_RANKS.get(item.rank) == rank_label), None)
    if target is None:
        return f"조회된 계보에 {rank_label} 정보가 없어 답변을 확인하지 못했습니다.", False
    subject = lineage.items[-1].korean_name or lineage.items[-1].english_name or lineage.resolved_query_scientific_name or lineage.query_scientific_name
    common_name = target.korean_name or target.english_name
    name = f"{common_name}({target.scientific_name})" if common_name else target.scientific_name
    return f"{subject}의 {rank_label} 분류는 {name}입니다.", True


def _trace_payload(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _traced_route(name: str) -> Callable[[Callable], Callable]:
    """Make each API request one MLflow trace whose children are its retrieval/model calls.

    FastAPI runs sync endpoints in a worker thread; opening the parent span
    inside that thread keeps every child span (including LangChain autolog
    spans) in the same context.  Disabled tracing adds one attribute check.
    """

    def decorate(endpoint: Callable) -> Callable:
        @functools.wraps(endpoint)
        def traced(*args, **kwargs):
            if not tracing.is_enabled():
                return endpoint(*args, **kwargs)
            with tracing.span(name, tracing.CHAIN, {"http.route": name}) as span:
                span.set_inputs({key: _trace_payload(value) for key, value in kwargs.items()})
                try:
                    result = endpoint(*args, **kwargs)
                except HTTPException as error:
                    span.set_attribute("http.status_code", error.status_code)
                    raise
                if isinstance(result, ChatResponse):
                    span.set_attributes({
                        "robingraph.selected_intent": result.selected_intent or "none",
                        "robingraph.route_method": result.route_method,
                        "robingraph.disposition": result.disposition,
                    })
                span.set_outputs(_trace_payload(result))
                return result

        return traced

    return decorate


def create_neo4j_search_handler(
    settings: Neo4jSettings, *, embedding_client: EmbeddingClient | None = None,
    english_search_terms: Callable[[str], str] | None = None,
) -> SearchHandler:
    """Build the read-only Neo4j/Jina search boundary used by FastAPI."""

    def handle(question: str, limit: int, hybrid: bool) -> HybridSearchOutcome:
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        from ..embeddings import EmbeddingConfigurationError, EmbeddingError, JinaEmbeddingClient
        from ..retrieval.neo4j_hybrid import HybridSearchRequest, QueryEmbedderLike, search

        search_question = question
        translation_warning = None
        if not hybrid and english_search_terms is not None and any("\uac00" <= char <= "\ud7a3" for char in question):
            try:
                terms = english_search_terms(question)
                if not isinstance(terms, str) or not terms.strip() or len(terms) > 300:
                    raise ValueError("Invalid translated search terms")
                search_question = f"{question} {terms}"
                translation_warning = "한국어 질문에 영어 검색어를 추가해 문헌을 검색했습니다."
            except Exception as error:
                logging.getLogger(__name__).warning("English search-term conversion failed (%s)", type(error).__name__)
                translation_warning = "영어 검색어 변환에 실패해 원래 질문으로만 검색했습니다."
        top_k = max(25, limit)
        channels = (FULLTEXT_CHANNEL, VECTOR_CHANNEL) if hybrid else (FULLTEXT_CHANNEL,)
        request = HybridSearchRequest(
            query_text=search_question,
            limit=limit,
            fulltext_top_k=top_k,
            vector_top_k=top_k,
            channels=channels,
        )
        def traced_search(search_request: HybridSearchRequest, query_embedder=None, *, fallback: bool = False):
            # Parameterized Cypher stays inside `search`; the span records only
            # the bounded request shape and the policy-checked result ids.
            with tracing.span(
                "neo4j.hybrid_search",
                tracing.RETRIEVER,
                {
                    "retrieval.backend": "neo4j",
                    "retrieval.channels": list(search_request.channels),
                    "retrieval.limit": search_request.limit,
                    "retrieval.top_k": search_request.fulltext_top_k,
                    "retrieval.embedding_fallback": fallback,
                },
            ) as span:
                span.set_inputs({"query_text": search_request.query_text})
                if query_embedder is None:
                    outcome = search(settings, search_request)
                else:
                    outcome = search(settings, search_request, query_embedder=query_embedder)
                if tracing.is_enabled():
                    span.set_attributes({"retrieval.result_count": len(outcome.results), "retrieval.warnings": list(outcome.warnings)})
                    span.set_outputs([
                        {"chunk_id": item.chunk_id, "score": item.score, "channels": list(item.channels)}
                        for item in outcome.results
                    ])
                return outcome

        try:
            if not hybrid:
                outcome = traced_search(request)
                return HybridSearchOutcome(
                    results=outcome.results,
                    warnings=(*outcome.warnings, translation_warning) if translation_warning else outcome.warnings,
                )
            try:
                client = embedding_client if embedding_client is not None else JinaEmbeddingClient.from_env()
            except EmbeddingConfigurationError as error:
                # Configuration errors can contain deployment-specific details.
                # Keep them out of the HTTP contract while retaining the cause
                # for server-side diagnostics.
                raise SearchBackendUnavailableError(_SEARCH_UNAVAILABLE) from error
            try:
                return traced_search(request, cast(QueryEmbedderLike, client))
            except EmbeddingError:
                fallback_request = HybridSearchRequest(
                    query_text=question,
                    limit=limit,
                    fulltext_top_k=top_k,
                    vector_top_k=top_k,
                    channels=(FULLTEXT_CHANNEL,),
                )
                outcome = traced_search(fallback_request, fallback=True)
                return HybridSearchOutcome(
                    results=outcome.results,
                    warnings=(*outcome.warnings, "Embedding request failed; results are keyword-only fulltext"),
                )
        except (Neo4jError, ServiceUnavailable, SessionExpired) as error:
            raise SearchBackendUnavailableError(_SEARCH_UNAVAILABLE) from error

    return handle


def create_neo4j_observation_handler(
    repository: OperationalObservationRepository,
) -> ObservationSearchHandler:
    """Map Neo4j and malformed-projection failures to a safe API boundary."""

    def handle(query: OperationalObservationQuery) -> tuple[OperationalObservation, ...]:
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            with tracing.span("neo4j.operational_observations", tracing.RETRIEVER, {"retrieval.backend": "neo4j"}) as span:
                span.set_inputs(query.__dict__)
                observations = repository.search_observations(query)
                span.set_outputs({"returned": len(observations)})
                return observations
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
            with tracing.span("neo4j.taxonomy_lineage", tracing.RETRIEVER, {"retrieval.backend": "neo4j", "lineage.matched_by": "scientific_name"}) as span:
                span.set_inputs({"scientific_name": scientific_name})
                lineage = repository.lineage_for_scientific_name(scientific_name)
                span.set_outputs({"found": lineage is not None})
                return lineage
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
            with tracing.span("neo4j.taxonomy_lineage", tracing.RETRIEVER, {"retrieval.backend": "neo4j", "lineage.matched_by": "korean_name"}) as span:
                span.set_inputs({"korean_name": korean_name})
                lineage = repository.lineage_for_korean_name(korean_name)
                span.set_outputs({"found": lineage is not None})
                return lineage
        except (Neo4jError, ServiceUnavailable, SessionExpired, ValueError) as error:
            raise TaxonomyLineageBackendUnavailableError(
                "AviList reference-taxonomy lineage is unavailable"
            ) from error

    return handle


def create_app(
    repository: GraphRepository | None = None,
    *,
    search_handler: SearchHandler | None = None,
    answer_generator: AnswerGenerator | None = None,
    observation_handler: ObservationSearchHandler | None = None,
    lineage_handler: LineageHandler | None = None,
    korean_lineage_handler: LineageHandler | None = None,
    semantic_router: SemanticRouter | None = None,
    species_profile_handler: Callable[[str], dict] | None = None,
    related_species_handler: Callable[[str], dict] | None = None,
    similar_species_handler: Callable[[str], dict] | None = None,
    ecological_relations_handler: Callable[[str], dict] | None = None,
    subspecies_handler: Callable[[str], dict] | None = None,
    name_relations_handler: Callable[[str], dict | None] | None = None,
    static_dir: Path | None = None,
    ingest_store: IngestStore | None = None,
) -> FastAPI:
    """Create the API and, when the packaged asset bundle is complete, the chat shell.

    ``static_dir`` is an internal test/integration seam. Production callers use
    the package-local ``robingraph.api/static`` directory included in the wheel.
    A missing, empty, or unreadable required chat asset deliberately does not
    stop the API from starting: all UI requests receive a generic 503 rather
    than an absolute server path or a partial chat shell.

    ``answer_generator`` is an optional integration seam for the `/v1/chat`
    evidence route only: when configured, it runs after retrieval to turn
    already-fetched hybrid results into a cited answer. Any generator error,
    or output that fails citation validation, falls back to the existing
    retrieval-only response rather than inventing an answer.
    """

    repository = repository or FixtureRepository(load_fixture())
    service = QuestionService(repository)
    app = FastAPI(title="RobinGraph", version="0.1.0")
    # The public application never discovers PostgreSQL credentials or opens
    # a write path from ambient configuration.  A private caller must inject
    # the control-plane repository explicitly, and the router independently
    # requires its internal bearer token from the environment.
    if ingest_store is not None:
        app.include_router(create_ingest_router(ingest_store))
    asset_root = static_dir if static_dir is not None else _DEFAULT_STATIC_ROOT

    def retrieve_evidence(state):
        return {**state, "outcome": search_handler(state["question"], state["limit"], state["hybrid"])}

    def answer_evidence(state):
        outcome = state["outcome"]
        text = "근거 문서를 확인했습니다." if outcome.results else "일치하는 근거 문서를 확인하지 못했습니다."
        if answer_generator is not None and outcome.results:
            text = _generated_evidence_answer(answer_generator, state["question"], outcome.results) or text
        return {**state, "answer_text": text}

    evidence_flow = RunnableLambda(retrieve_evidence) | RunnableLambda(answer_evidence)

    @app.get("/v1/taxa/name-relations")
    @_traced_route("GET /v1/taxa/name-relations")
    def name_relations(name: Annotated[str, Query(min_length=1, max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422, detail="A name is required")
        if name_relations_handler is None:
            raise HTTPException(status_code=503, detail="Name relationships are unavailable")
        try:
            result = name_relations_handler(name.strip())
        except Exception:
            raise HTTPException(status_code=503, detail="Name relationships are unavailable") from None
        if result is None:
            raise HTTPException(status_code=503, detail="No active reviewed name relationship snapshot")
        return result

    @app.get("/v1/taxa/related")
    @_traced_route("GET /v1/taxa/related")
    def species_relations(name: Annotated[str, Query(min_length=1, max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422, detail="A species name is required")
        if related_species_handler is None:
            raise HTTPException(status_code=503, detail="Species relations are unavailable")
        try:
            return related_species_handler(name.strip())
        except SpeciesNotFoundError as error:
            raise HTTPException(status_code=404, detail="Species not found in active taxonomy") from error
        except Exception as error:
            raise HTTPException(status_code=503, detail="Species relations are temporarily unavailable") from error

    @app.get("/v1/taxa/similar")
    @_traced_route("GET /v1/taxa/similar")
    def similar_species_results(name: Annotated[str, Query(min_length=1,max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422,detail="A species name is required")
        if similar_species_handler is None:
            raise HTTPException(status_code=503,detail="Species similarity is unavailable")
        try:
            return similar_species_handler(name.strip())
        except SpeciesNotFoundError:
            raise HTTPException(status_code=404,detail="Species not found in active taxonomy") from None
        except Exception:
            raise HTTPException(status_code=503,detail="Species similarity is temporarily unavailable") from None

    @app.get("/v1/taxa/ecological-related")
    @_traced_route("GET /v1/taxa/ecological-related")
    def ecological_species_relations(name: Annotated[str, Query(min_length=1,max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422,detail="A species name is required")
        if ecological_relations_handler is None:
            raise HTTPException(status_code=503,detail="Ecological relations are unavailable")
        try:
            return ecological_relations_handler(name.strip())
        except SpeciesNotFoundError:
            raise HTTPException(status_code=404,detail="Species not found in active taxonomy") from None
        except Exception:
            raise HTTPException(status_code=503,detail="Ecological relations are temporarily unavailable") from None

    @app.get("/v1/taxa/subspecies")
    @_traced_route("GET /v1/taxa/subspecies")
    def subspecies(name: Annotated[str, Query(min_length=1,max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422,detail="A taxon name is required")
        if subspecies_handler is None:
            raise HTTPException(status_code=503,detail="Subspecies lookup is unavailable")
        try:
            return subspecies_handler(name.strip())
        except SpeciesNotFoundError as error:
            raise HTTPException(status_code=404,detail="Taxon not found in active taxonomy") from error
        except Exception as error:
            raise HTTPException(status_code=503,detail="Subspecies lookup is temporarily unavailable") from error

    @app.get("/v1/taxa/profile")
    @_traced_route("GET /v1/taxa/profile")
    def species_profile(name: Annotated[str, Query(min_length=1, max_length=200)]):
        if not name.strip():
            raise HTTPException(status_code=422, detail="A species name is required")
        if species_profile_handler is None:
            raise HTTPException(status_code=503, detail="Species profiles are unavailable")
        try:
            return species_profile_handler(name.strip())
        except SpeciesNotFoundError as error:
            raise HTTPException(status_code=404, detail="Species not found in active taxonomy") from error
        except Exception as error:
            raise HTTPException(status_code=503, detail="Species profiles are temporarily unavailable") from error

    @app.get("/birds", include_in_schema=False, response_model=None)
    def birds_ui():
        assets = _read_chat_asset_bundle(asset_root, ("birds.html", "birds.js", "styles.css"))
        if assets is None:
            return PlainTextResponse(_CHAT_UI_UNAVAILABLE, status_code=503)
        return _chat_asset_response(assets, "birds.html")

    def unavailable_chat_ui() -> PlainTextResponse:
        return PlainTextResponse(_CHAT_UI_UNAVAILABLE, status_code=503)

    def chat_ui() -> Response | PlainTextResponse:
        assets = _read_chat_asset_bundle(asset_root)
        if assets is None:
            return unavailable_chat_ui()
        return _chat_asset_response(assets, "index.html")

    @app.get("/static/{asset_path:path}", include_in_schema=False, response_model=None)
    def static_asset(asset_path: str) -> Response | PlainTextResponse:
        names = ("birds.html", "birds.js", "styles.css") if asset_path in ("birds.html", "birds.js") else _REQUIRED_CHAT_ASSETS
        assets = _read_chat_asset_bundle(asset_root, names)
        if assets is None:
            # Do not reflect asset_path: it could contain deployment details or
            # be used to probe the server's filesystem layout.
            return unavailable_chat_ui()
        if asset_path not in assets:
            raise HTTPException(status_code=404, detail="Not Found")
        return _chat_asset_response(assets, asset_path)

    @app.get("/", include_in_schema=False, response_model=None)
    def root() -> Response | PlainTextResponse:
        return chat_ui()

    @app.get("/chat", include_in_schema=False, response_model=None)
    def chat() -> Response | PlainTextResponse:
        return chat_ui()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "mode": repository.mode,
            "taxonomy_release": repository.taxonomy_release,
            "deployment_target": os.getenv("ROBINGRAPH_DEPLOY_TARGET", "legacy"),
        }

    @app.post("/v1/answers", response_model=AnswerResponse)
    @_traced_route("POST /v1/answers")
    def answer_question(request: QuestionRequest) -> AnswerResponse:
        answer = service.answer(request.question)
        try:
            validate_answer(answer, repository)
        except ValueError as error:
            raise HTTPException(status_code=500, detail="Answer provenance validation failed") from error
        return _response(answer)

    @app.post("/v1/chat", response_model=ChatResponse)
    @_traced_route("POST /v1/chat")
    def integrated_chat(request: ChatRequest) -> ChatResponse:
        """Route a bounded chat request without inventing facts or filters.

        Explicit routes never read the router, so a missing embedding setting
        or provider outage cannot affect established operational workflows.
        """

        species_question = parse_species_question(request.question) if request.intent in ("auto", "profile") else None
        recognized = ("profile", species_question.name) if species_question else _species_chat_question(request.question) if request.intent == "auto" else None
        focused_name = None
        name_context = None
        if species_question and request.filters is not None and (
                not isinstance(request.filters, ProfileChatFilters)
                or request.filters.name is not None
                and request.filters.name.strip().casefold() != species_question.name.casefold()):
            return ChatResponse(
                selected_intent="profile", route_method="deterministic" if request.intent=="auto" else "explicit",
                disposition="clarify", answer_text="질문의 종 이름과 조회 필터가 다릅니다. 같은 종 이름으로 다시 질문해 주세요.",
                warnings=["다른 종의 자료로 질문에 답하지 않았습니다."],
                result=ChatClarifyResult(prompt="질문과 필터의 종 이름을 맞춰 주세요."),
            )
        # A reviewed common-name graph takes precedence over semantic routing,
        # but never over explicit evidence/observation or scientific-name filters.
        relation_question = recognized or _species_chat_question(request.question)
        relation_name = relation_question[1] if relation_question else request.question
        if isinstance(request.filters, ProfileChatFilters) and request.filters.name:
            relation_name = request.filters.name
        elif isinstance(request.filters, TaxonomyChatFilters) and request.filters.name:
            relation_name = request.filters.name
        scientific_filter = isinstance(request.filters, TaxonomyChatFilters) and request.filters.scientific_name is not None
        relevant_filter = request.filters is None or isinstance(request.filters, (ProfileChatFilters, TaxonomyChatFilters))
        scientific_query = (re.fullmatch(r"[A-Za-z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?", relation_name.strip()) is not None
                            and relation_name.strip().lower() not in reviewed_search_terms())
        if name_relations_handler is not None and request.intent in ("auto", "profile", "taxonomy") and relevant_filter and not scientific_filter and not scientific_query:
            try:
                relationships = name_relations_handler(relation_name)
            except Exception as error:
                logging.getLogger(__name__).warning("Name relationship lookup failed (%s)", type(error).__name__)
                is_name_request = request.intent in ("profile", "taxonomy") or relation_question is not None or request.filters is not None or re.fullmatch(r"[가-힣]+|[A-Za-z][A-Za-z .-]+", relation_name) is not None
                if is_name_request:
                    return ChatResponse(
                        selected_intent="taxonomy" if request.intent == "taxonomy" or relation_question and relation_question[0] == "taxonomy" else "profile",
                        route_method="deterministic" if request.intent == "auto" else "explicit",
                        disposition="abstain", answer_text="이 이름의 관계 정보를 현재 확인할 수 없어 관련 종을 임의로 선택하지 않았습니다.",
                        warnings=["통칭·가축형 관계 조회 기능을 사용할 수 없습니다."],
                        result=ChatSpeciesResult(profile=None),
                    )
                relationships = None
            if relationships and relationships.get("is_search_term") and relationships.get("relations"):
                relations=relationships["relations"]
                targets={r.get("taxon",{}).get("taxon_id") for r in relations}
                single_common=(len(targets)==1 and None not in targets and all(r.get("entity_kind")=="common_name" for r in relations))
                if single_common and species_question:
                    focused_name = relations[0]["taxon"]["scientific_name"]
                    name_context = relationships
                else:
                    return ChatResponse(
                        selected_intent="taxonomy" if request.intent == "taxonomy" or relation_question and relation_question[0] == "taxonomy" else "profile", route_method="deterministic" if request.intent == "auto" else "explicit",
                        disposition="answer" if single_common else "clarify", answer_text=relationships["summary"], warnings=[],
                        result=ChatNameRelationsResult(relationships=relationships),
                    )
            if not focused_name and relation_name.strip().lower() in reviewed_search_terms():
                return ChatResponse(
                    selected_intent="profile", route_method="deterministic" if request.intent == "auto" else "explicit",
                    disposition="abstain", answer_text="이 이름의 검토된 관계를 현재 조회할 수 없습니다. 관련 종을 임의로 선택하지 않았습니다.",
                    warnings=["활성 통칭·가축형 관계 데이터가 없거나 조회에 실패했습니다."],
                    result=ChatSpeciesResult(profile=None),
                )
        if request.intent == "auto":
            if recognized:
                selected = recognized[0]
            elif semantic_router is not None:
                with tracing.span("semantic_router.classify", tracing.CHAIN) as route_span:
                    route_span.set_inputs({"question": request.question})
                    selected = semantic_router.classify(request.question)
                    route_span.set_outputs({"selected_intent": selected})
            else:
                selected = None
            method: Literal["semantic", "explicit", "deterministic"] = "deterministic" if recognized else "semantic"
            if selected is None:
                return ChatResponse(
                    selected_intent=None,
                    route_method=method,
                    disposition="clarify",
                    answer_text="질문의 종류를 판단하지 못했습니다. 종 정보, 분류, 관찰, 근거 중 하나를 선택해 주세요.",
                    warnings=["자동 분류가 확실하지 않아 조회하지 않았습니다."],
                    result=ChatClarifyResult(prompt="종 정보, 분류, 관찰, 근거 중 하나를 선택해 주세요."),
                )
        else:
            selected = request.intent
            method = "explicit"

        if request.filters is not None and request.filters.kind != selected:
            return ChatResponse(
                selected_intent=selected,
                route_method=method,
                disposition="clarify",
                answer_text="선택된 조회 유형과 필터가 일치하지 않습니다. 필터를 다시 선택해 주세요.",
                warnings=["다른 조회 유형의 필터는 적용하지 않았습니다."],
                result=ChatClarifyResult(prompt="선택된 조회 유형에 맞는 필터를 사용해 주세요."),
            )

        if selected == "profile":
            filters = request.filters if isinstance(request.filters, ProfileChatFilters) else None
            name = (focused_name or (filters.name if filters and filters.name is not None else recognized[1] if recognized else request.question)).strip()
            if species_profile_handler is None:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="종 정보를 현재 조회할 수 없습니다.",
                    warnings=["종 정보 조회 기능을 사용할 수 없습니다."],
                    result=ChatSpeciesResult(profile=None),
                )
            try:
                profile = species_profile_handler(name)
            except SpeciesNotFoundError:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="입력한 이름의 종 정보를 확인하지 못했습니다.",
                    warnings=["활성 분류 개념집합에서 일치 항목을 찾지 못했습니다."],
                    result=ChatSpeciesResult(profile=None),
                )
            except Exception:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="종 정보를 현재 조회할 수 없습니다.",
                    warnings=["종 정보 조회 기능을 사용할 수 없습니다."],
                    result=ChatSpeciesResult(profile=None),
                )
            if species_question:
                if name_context is not None:
                    lineage = profile.get("lineage") or {}
                    expected = name_context["relations"][0]["taxon"]
                    if (profile.get("taxon",{}).get("taxon_id") != expected.get("taxon_id")
                            or lineage.get("concept_set_id") != name_context.get("concept_set_id")
                            or lineage.get("taxonomy_release") != name_context.get("taxonomy_release")):
                        return ChatResponse(
                            selected_intent=selected, route_method=method, disposition="abstain",
                            answer_text="이름 관계와 종 자료의 분류판이 달라 현재 답변을 제공하지 않았습니다. 다시 질문해 주세요.",
                            warnings=["종의 식별자·활성 분류판을 다시 확인해야 합니다."],
                            result=ChatSpeciesResult(profile=None),
                        )
                relations = None
                if species_question.topic in ("related", "ecological_related"):
                    handler = (similar_species_handler if species_question.topic == "related" and species_question.category is None
                               else related_species_handler if species_question.topic == "related"
                               else ecological_relations_handler)
                    try:
                        if handler is None:
                            raise ValueError("Relation lookup unavailable")
                        relations = handler(name)
                        lineage = profile.get("lineage") or {}
                        if (relations.get("taxon", {}).get("taxon_id") != profile.get("taxon", {}).get("taxon_id")
                                or relations.get("concept_set_id") != lineage.get("concept_set_id")
                                or relations.get("taxonomy_release") != lineage.get("taxonomy_release")):
                            raise ValueError("Relation context changed")
                        if species_question.category:
                            relations = {**relations, "groups":[g for g in relations.get("groups",[]) if g.get("relation" if species_question.topic=="ecological_related" else "rank")==species_question.category]}
                    except Exception:
                        relations = None
                answer, supported = focused_answer(profile, species_question, relations)
                if name_context is not None:
                    answer["name_context"] = name_context
                    answer["text"] = name_context["summary"] + " " + answer["text"]
                return ChatResponse(
                    selected_intent=selected, route_method=method,
                    disposition="answer" if supported else "abstain",
                    answer_text=answer["text"] + ("\n" + "\n".join(item["text"] for item in answer["items"]) if answer["items"] else ""),
                    warnings=profile.get("warnings", []),
                    result=ChatSpeciesResult(profile=profile, question_answer=answer),
                )
            summary = profile.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                summary = species_summary(profile.get("taxon") or {}, profile.get("traits") or [])
            return ChatResponse(
                selected_intent=selected, route_method=method, disposition="answer",
                answer_text=summary,
                warnings=profile.get("warnings", []),
                result=ChatSpeciesResult(profile=profile),
            )

        if selected == "taxonomy":
            filters = request.filters if isinstance(request.filters, TaxonomyChatFilters) else None
            query = (
                (filters.scientific_name or filters.name or (recognized[1] if recognized else request.question))
                if filters
                else (recognized[1] if recognized else request.question)
            )
            if recognized and (not filters or not (filters.scientific_name or filters.name)):
                handler = korean_lineage_handler if any("\uac00" <= char <= "\ud7a3" for char in query) else lineage_handler
            elif not filters or not (filters.scientific_name or filters.name):
                # Only strip a recognizable rank question; exact-name lookups stay unchanged.
                prefix = re.match(r"^(.+?)(?:은|는|이|가)\s+(?:무슨|어느|어떤)\s*(?:아종|목|과|속|종)", query)
                if prefix:
                    query = prefix.group(1).strip()
                handler = korean_lineage_handler if prefix and any("\uac00" <= char <= "\ud7a3" for char in query) else lineage_handler
            else:
                handler = korean_lineage_handler if filters.name is not None else lineage_handler
            if handler is None:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="분류 계통 정보를 현재 조회할 수 없습니다.",
                    warnings=["분류 계통 조회 기능을 사용할 수 없습니다."],
                    result=ChatTaxonomyResult(lineage=None),
                )
            try:
                lineage = handler(query)
            except Exception:
                # A chat response must not disclose provider/configuration
                # details.  The public lineage endpoint keeps its legacy 503.
                return ChatResponse(
                    selected_intent=selected,
                    route_method=method,
                    disposition="abstain",
                    answer_text="분류 계통 정보를 현재 조회할 수 없습니다.",
                    warnings=["분류 계통 조회 기능을 사용할 수 없습니다."],
                    result=ChatTaxonomyResult(lineage=None),
                )
            if lineage is None:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="입력한 이름의 분류 계통을 확인하지 못했습니다.",
                    warnings=["활성 분류 개념집합에서 일치 항목을 찾지 못했습니다."],
                    result=ChatTaxonomyResult(lineage=None),
                )
            answer_text, supported = _taxonomy_answer(request.question, lineage)
            return ChatResponse(
                selected_intent=selected, route_method=method, disposition="answer" if supported else "abstain",
                answer_text=answer_text, warnings=[],
                result=ChatTaxonomyResult(lineage=_lineage_response(lineage)),
            )

        if selected == "observations":
            filters = request.filters if isinstance(request.filters, ObservationChatFilters) else ObservationChatFilters()
            has_bounded_filter = any(
                value is not None
                for value in (
                    filters.taxon_key,
                    filters.scientific_name,
                    filters.place,
                    filters.observed_from,
                    filters.observed_to,
                )
            )
            if not has_bounded_filter:
                return ChatResponse(
                    selected_intent=selected,
                    route_method=method,
                    disposition="clarify",
                    answer_text="관찰 기록을 조회하려면 분류 키, 학명, 장소 또는 날짜 필터를 입력해 주세요.",
                    warnings=["필터 없는 전체 관찰 기록 조회는 실행하지 않았습니다."],
                    result=ChatObservationsResult(results=[], limit=filters.limit),
                )
            if observation_handler is None:
                return ChatResponse(
                    selected_intent=selected, route_method=method, disposition="abstain",
                    answer_text="관찰 기록을 현재 조회할 수 없습니다.",
                    warnings=["관찰 기록 조회 기능을 사용할 수 없습니다."],
                    result=ChatObservationsResult(results=[], limit=filters.limit),
                )
            query = OperationalObservationQuery(
                taxon_key=filters.taxon_key, scientific_name=filters.scientific_name, place=filters.place,
                observed_from=filters.observed_from.isoformat() if filters.observed_from else None,
                observed_to=filters.observed_to.isoformat() if filters.observed_to else None,
                limit=filters.limit, offset=0,
            )
            try:
                observations = observation_handler(query)
            except Exception:
                return ChatResponse(
                    selected_intent=selected,
                    route_method=method,
                    disposition="abstain",
                    answer_text="관찰 기록을 현재 조회할 수 없습니다.",
                    warnings=["관찰 기록 조회 기능을 사용할 수 없습니다."],
                    result=ChatObservationsResult(results=[], limit=filters.limit),
                )
            warnings = []
            if any(value.coordinate_disclosure == "withheld" for value in observations):
                warnings.append("일반화된 관찰 기록의 좌표는 공개하지 않습니다.")
            if observations:
                first = observations[0]
                answer_text = (
                    f"조회된 관찰 기록 {len(observations)}건 중 첫 기록: "
                    f"{first.taxon.scientific_name}, 관찰일 {first.observed_at}, "
                    f"장소 {first.place.name}. [{first.citation.evidence_id}]"
                )
            else:
                answer_text = "일치하는 관찰 기록을 확인하지 못했습니다."
            return ChatResponse(
                selected_intent=selected, route_method=method,
                disposition="answer" if observations else "abstain",
                answer_text=answer_text,
                warnings=warnings,
                result=ChatObservationsResult(
                    results=[_operational_observation_response(value) for value in observations], limit=filters.limit
                ),
            )

        # The only remaining selected intent is evidence.  Preserve the
        # established hybrid handler and its truthful vector/fulltext fallback
        # warnings; similarity is presented as retrieval support, never fact.
        filters = request.filters if isinstance(request.filters, EvidenceChatFilters) else EvidenceChatFilters()
        requested_mode: SearchMode = "hybrid" if method == "semantic" else "fulltext"
        if search_handler is None:
            return ChatResponse(
                selected_intent="evidence", route_method=method, disposition="abstain",
                answer_text="근거 문서를 현재 조회할 수 없습니다.",
                warnings=["근거 문서 조회 기능을 사용할 수 없습니다."],
                result=ChatEvidenceResult(search=DocumentSearchResponse(
                    requested_mode=requested_mode,
                    mode="fulltext",
                    fixture_only=True,
                    results=[],
                    warnings=[],
                )),
            )
        try:
            flow_result = evidence_flow.invoke({"question":request.question, "limit":filters.limit, "hybrid":requested_mode == "hybrid"})
            outcome = flow_result["outcome"]
        except Exception:
            return ChatResponse(
                selected_intent="evidence", route_method=method, disposition="abstain",
                answer_text="근거 문서를 현재 조회할 수 없습니다.",
                warnings=["근거 문서 조회 기능을 사용할 수 없습니다."],
                result=ChatEvidenceResult(search=DocumentSearchResponse(
                    requested_mode=requested_mode,
                    mode="fulltext",
                    fixture_only=True,
                    results=[],
                    warnings=[],
                )),
            )
        evidence = _search_response(outcome, requested_mode=requested_mode)
        answer_text = flow_result["answer_text"]
        return ChatResponse(
            selected_intent="evidence", route_method=method,
            disposition="answer" if evidence.results else "abstain",
            answer_text=answer_text,
            warnings=list(evidence.warnings), result=ChatEvidenceResult(search=evidence),
        )

    @app.post(
        "/v1/search",
        response_model=DocumentSearchResponse,
        responses={503: {"description": "Neo4j mode or a configured search dependency is unavailable"}},
    )
    @_traced_route("POST /v1/search")
    def search_documents(request: DocumentSearchRequest) -> DocumentSearchResponse:
        if search_handler is None:
            raise HTTPException(status_code=503, detail="Document search is available only in Neo4j mode")
        try:
            outcome = search_handler(request.question, request.limit, request.mode == "hybrid")
        except SearchBackendUnavailableError as error:
            # Search handlers may wrap provider/configuration exceptions. Do
            # not turn their messages into a client-visible information leak.
            raise HTTPException(status_code=503, detail=_SEARCH_UNAVAILABLE) from error
        return _search_response(outcome, requested_mode=request.mode)

    @app.get(
        "/v1/observations",
        response_model=OperationalObservationSearchResponse,
        responses={503: {"description": "The operational GBIF observation graph is unavailable"}},
    )
    @_traced_route("GET /v1/observations")
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
    @_traced_route("GET /v1/taxa/lineage")
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
