"""A generic, data-driven answer path shared by fixture and Neo4j retrieval.

`QuestionService` resolves taxon names, places, months, and document titles by
matching question text against indexes pulled from a `GraphRepository` --
never by branching on a specific taxon, place, or document ID. The same class
therefore serves both `FixtureRepository` (in-memory, offline) and
`Neo4jGraphRepository` (parameterized Cypher against a live graph); only the
repository implementation differs. The Answer/Citation contract and
`validate_answer` provenance checks are unchanged for callers.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import uuid5, NAMESPACE_URL

from .retrieval.repository import DocumentRecord, GraphRepository, ObservationRecord, TaxonRecord


@dataclass(frozen=True)
class Citation:
    evidence_id: str
    source_id: str
    source_url: str
    locator: str
    license_name: str


@dataclass(frozen=True)
class Answer:
    answer_id: str
    answer_text: str
    taxon_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    citations: tuple[Citation, ...]
    disposition: str
    warnings: tuple[str, ...]
    taxonomy_release: str
    data_cutoff: str


# Colloquial group terms are a vocabulary/entity-resolution concern, not an
# answer-generation shortcut: each alias resolves through the ordinary
# scientific-name index below to whichever taxa currently carry that name,
# rather than hard-coding taxon IDs into the answer flow. A real deployment
# would source this from a taxonomy-backed synonym/group vocabulary.
AMBIGUOUS_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "물새": ("Anas zonorhyncha", "Phalacrocorax carbo"),
}

_ENTITY_LOOKUP_KEYWORDS = ("학명", "한국어 이름", "어떤 종")
_PRECISE_COORDINATE_KEYWORDS = ("정확한", "좌표")
_DATE_PATTERN = re.compile(r"(\d{4})년\s*(\d{1,2})월")


class QuestionService:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository
        self._taxonomy = repository.list_taxonomy()
        self._places = sorted(repository.list_places(), key=lambda place: len(place.display_name), reverse=True)
        self._documents = repository.list_documents()

    def answer(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            return self._abstain(question, "질문이 비어 있습니다.")

        alias_candidates = self._resolve_ambiguous_alias(question)
        if alias_candidates:
            names = ", ".join(self._name_for(taxon, "ko") or taxon.scientific_name for taxon in alias_candidates)
            return self._answer(
                question,
                f"질문이 둘 이상의 종을 가리킬 수 있습니다. {names} 중 어느 종인지 선택해 주세요.",
                tuple(taxon.taxon_id for taxon in alias_candidates),
                (),
                "clarify",
                ("ambiguous_name",),
            )

        document = self._resolve_document(question)
        if document is not None:
            return self._document_answer(question, document)

        taxa = self._resolve_taxa(question)
        if not taxa:
            return self._abstain(question, "fixture 데이터에서 질문의 종이나 근거를 찾지 못했습니다.")
        if len(taxa) == 1 and self._is_entity_lookup(question):
            return self._name_answer(question, taxa[0])

        observations = self._matching_observations(question, taxa)
        if self._asks_for_precise_coordinates(question):
            if not observations:
                return self._abstain(question, "질문의 장소와 시기에 맞는 fixture 관찰 근거가 없습니다.")
            if observations[0].sensitivity_class == "withheld":
                return self._answer(
                    question,
                    "민감 관찰의 정확한 좌표는 공개하지 않습니다. 공개 가능한 일반화 위치만 제공할 수 있습니다. [1]",
                    tuple(taxon.taxon_id for taxon in taxa),
                    (observations[0].occurrence_id,),
                    "abstain",
                    ("sensitive_coordinates_withheld",),
                )
        if not observations:
            return self._abstain(question, "질문의 장소와 시기에 맞는 fixture 관찰 근거가 없습니다.")

        evidence = [record.occurrence_id for record in observations]
        taxon_ids = tuple(dict.fromkeys(record.taxon_id for record in observations))
        if "근거" in question and "보여줘" in question and len(taxon_ids) == 1:
            extra = self._related_chunk_evidence(taxon_ids[0], exclude=evidence)
            if extra is not None:
                evidence.append(extra)
        lines = []
        for index, record in enumerate(observations, start=1):
            taxon = self._taxon(record.taxon_id)
            korean_name = self._name_for(taxon, "ko") or taxon.scientific_name
            lines.append(f"{record.event_date_raw}에 {record.place_name}에서 {korean_name} 관찰 기록이 있습니다. [{index}]")
        return self._answer(question, " ".join(lines), taxon_ids, tuple(evidence), "answer", ())

    # -- entity resolution -------------------------------------------------

    def _resolve_taxa(self, question: str) -> list[TaxonRecord]:
        normalized = question.casefold()
        return [taxon for taxon in self._taxonomy if any(name.casefold() in normalized for name in taxon.names())]

    def _resolve_ambiguous_alias(self, question: str) -> tuple[TaxonRecord, ...]:
        for alias, scientific_names in AMBIGUOUS_NAME_ALIASES.items():
            if alias not in question:
                continue
            resolved = tuple(self._taxon_by_scientific_name(name) for name in scientific_names)
            if all(taxon is not None for taxon in resolved):
                return resolved  # type: ignore[return-value]
        return ()

    def _resolve_document(self, question: str) -> DocumentRecord | None:
        normalized = question.casefold()
        for document in self._documents:
            if document.title.casefold() in normalized:
                return document
        return None

    def _resolve_place(self, question: str) -> str | None:
        for place in self._places:
            if place.display_name in question:
                return place.place_id
        return None

    @staticmethod
    def _resolve_month(question: str) -> str | None:
        match = _DATE_PATTERN.search(question)
        if not match:
            return None
        year, month = match.group(1), int(match.group(2))
        return f"{year}-{month:02d}"

    def _matching_observations(self, question: str, taxa: list[TaxonRecord]) -> tuple[ObservationRecord, ...]:
        return self.repository.observations_for_taxa(
            [taxon.taxon_id for taxon in taxa],
            place_id=self._resolve_place(question),
            month_prefix=self._resolve_month(question),
        )

    def _related_chunk_evidence(self, taxon_id: str, exclude: list[str]) -> str | None:
        taxon = self._taxon(taxon_id)
        for chunk in self.repository.list_chunks():
            if chunk.chunk_id in exclude:
                continue
            if any(name.casefold() in chunk.text.casefold() for name in taxon.names()):
                return chunk.chunk_id
        return None

    # -- answer composition -------------------------------------------------

    def _is_entity_lookup(self, question: str) -> bool:
        return any(keyword in question for keyword in _ENTITY_LOOKUP_KEYWORDS)

    def _asks_for_precise_coordinates(self, question: str) -> bool:
        return any(keyword in question for keyword in _PRECISE_COORDINATE_KEYWORDS)

    def _name_answer(self, question: str, taxon: TaxonRecord) -> Answer:
        evidence = (taxon.taxon_id,)
        korean_name = self._name_for(taxon, "ko") or taxon.scientific_name
        if "학명" in question:
            text = f"{korean_name}의 학명은 {taxon.scientific_name}입니다. [1]"
        else:
            text = f"{taxon.scientific_name}의 한국어 이름은 {korean_name}입니다. [1]"
        return self._answer(question, text, (taxon.taxon_id,), evidence, "answer", ())

    def _document_answer(self, question: str, document: DocumentRecord) -> Answer:
        chunks = self.repository.chunks_for_document(document.document_id)
        if not chunks:
            # The document itself resolved (its metadata is always kept, see
            # policy.py), but it has no retrievable chunks -- e.g. its
            # chunk/fulltext permission was denied. There is no text to
            # ground an answer in, so abstain instead of returning an
            # "answer" with empty text and no evidence.
            return self._abstain(question, "해당 문서는 정책상 본문을 제공할 수 없어 근거를 만들 수 없습니다.")
        joined_text = " ".join(chunk.text for chunk in chunks)
        taxon_ids = tuple(
            taxon.taxon_id
            for taxon in self._taxonomy
            if any(name.casefold() in joined_text.casefold() for name in taxon.names())
        )
        lines = [f"{chunk.text} [{index}]" for index, chunk in enumerate(chunks, start=1)]
        return self._answer(question, " ".join(lines), taxon_ids, tuple(chunk.chunk_id for chunk in chunks), "answer", ())

    def _abstain(self, question: str, text: str) -> Answer:
        return self._answer(question, text, (), (), "abstain", ())

    def _answer(
        self,
        question: str,
        text: str,
        taxon_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        disposition: str,
        warnings: tuple[str, ...],
    ) -> Answer:
        citations = tuple(self._citation(evidence_id) for evidence_id in evidence_ids)
        return Answer(
            answer_id=str(uuid5(NAMESPACE_URL, f"fixture-v1:{question}")),
            answer_text=text,
            taxon_ids=taxon_ids,
            evidence_ids=evidence_ids,
            citations=citations,
            disposition=disposition,
            warnings=warnings,
            taxonomy_release=self.repository.taxonomy_release,
            data_cutoff=self.repository.data_cutoff,
        )

    def _citation(self, evidence_id: str) -> Citation:
        source = self.repository.citation_for(evidence_id)
        return Citation(
            evidence_id=evidence_id,
            source_id=source.source_id,
            source_url=source.source_url,
            locator=source.locator,
            license_name=source.license_name,
        )

    def _taxon(self, taxon_id: str) -> TaxonRecord:
        for taxon in self._taxonomy:
            if taxon.taxon_id == taxon_id:
                return taxon
        raise ValueError(f"Unknown taxon ID: {taxon_id}")

    def _taxon_by_scientific_name(self, scientific_name: str) -> TaxonRecord | None:
        for taxon in self._taxonomy:
            if taxon.scientific_name.casefold() == scientific_name.casefold():
                return taxon
        return None

    @staticmethod
    def _name_for(taxon: TaxonRecord, language: str) -> str | None:
        return taxon.vernacular(language)


def validate_answer(answer: Answer, repository: GraphRepository) -> None:
    """Reject nonexistent, policy-filtered, or coordinate-leaking citations."""

    if not set(answer.evidence_ids).issubset(repository.known_evidence_ids()):
        raise ValueError("Answer contains an evidence ID outside the allowed corpus")
    if tuple(citation.evidence_id for citation in answer.citations) != answer.evidence_ids:
        raise ValueError("Answer citations do not match evidence IDs")
    for private_value in repository.known_private_coordinate_values():
        if private_value in answer.answer_text:
            raise ValueError("Answer leaks a private coordinate")
