"""Fixture-only FastAPI application.

The production provider will replace FixtureQuestionService after graph and LLM
contracts are approved; response provenance remains part of the API contract.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..fixture import FixtureCorpus, load_fixture
from ..slice import Answer, FixtureQuestionService, validate_answer


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


def create_app(corpus: FixtureCorpus | None = None) -> FastAPI:
    corpus = corpus or load_fixture()
    service = FixtureQuestionService(corpus)
    app = FastAPI(title="RobinGraph", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "fixture", "taxonomy_release": corpus.manifest["taxonomy_release"]}

    @app.post("/v1/answers", response_model=AnswerResponse)
    def answer_question(request: QuestionRequest) -> AnswerResponse:
        answer = service.answer(request.question)
        try:
            validate_answer(answer, corpus)
        except ValueError as error:
            raise HTTPException(status_code=500, detail="Answer provenance validation failed") from error
        return _response(answer)

    return app


app = create_app()
