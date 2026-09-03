"""A deterministic answer path for the synthetic fixture.

The production implementation will replace this in-memory repository with Neo4j
and the deterministic composer with a HermesAgent provider. The evidence and
policy boundary stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from .fixture import FixtureCorpus


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


PLACE_NAMES = {
    "fixture 호수": "fixture-place-lake",
    "fixture 하천": "fixture-place-river",
    "fixture 숲": "fixture-place-forest",
    "fixture 공원": "fixture-place-park",
    "fixture 해안": "fixture-place-coast",
}


class FixtureQuestionService:
    def __init__(self, corpus: FixtureCorpus) -> None:
        self.corpus = corpus

    def answer(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            return self._abstain(question, "질문이 비어 있습니다.")
        if "펭귄" in question:
            return self._abstain(question, "fixture 데이터에 펭귄 관찰 근거가 없습니다.")
        if "검토 문서" in question:
            return self._abstain(question, "검토 대기 자료는 검색과 답변 근거에서 제외됩니다.")
        if "물새" in question:
            candidates = ("rg:taxon:anas-zonorhyncha", "rg:taxon:phalacrocorax-carbo")
            return self._answer(
                question,
                "‘물새’는 fixture에서 둘 이상의 종을 가리킬 수 있습니다. 흰뺨검둥오리와 민물가마우지 중 어느 종인지 선택해 주세요.",
                candidates,
                (),
                "clarify",
                ("ambiguous_name",),
            )
        if "물가 조류 관찰 기록" in question:
            return self._document_answer(question, "fixture-doc-waterbirds", ("rg:taxon:anas-zonorhyncha", "rg:taxon:ardea-cinerea"))
        if "도시 숲 조류 관찰 기록" in question:
            return self._document_answer(question, "fixture-doc-woodland", ("rg:taxon:dendrocopos-kizuki",))

        taxa = self._resolve_taxa(question)
        if not taxa:
            return self._abstain(question, "fixture 데이터에서 질문의 종이나 근거를 찾지 못했습니다.")
        if len(taxa) == 1 and ("학명" in question or "한국어 이름" in question or "어떤 종" in question):
            return self._name_answer(question, taxa[0])
        if any(taxon["source_taxon_id"] == "rg:taxon:buteo-japonicus" for taxon in taxa) and (
            "정확한" in question or "좌표" in question
        ):
            observation = self._matching_observations(question, taxa)[0]
            return self._answer(
                question,
                "민감 관찰의 정확한 좌표는 공개하지 않습니다. 공개 가능한 일반화 위치만 제공할 수 있습니다. [1]",
                tuple(taxon["source_taxon_id"] for taxon in taxa),
                (observation["occurrence_id"],),
                "abstain",
                ("sensitive_coordinates_withheld",),
            )

        observations = self._matching_observations(question, taxa)
        if not observations:
            return self._abstain(question, "질문의 장소와 시기에 맞는 fixture 관찰 근거가 없습니다.")
        evidence = [record["occurrence_id"] for record in observations]
        if "근거" in question and observations[0]["source_taxon_id"] == "rg:taxon:ardea-cinerea":
            evidence.append("fixture-chunk-waterbirds-1")
        taxon_ids = tuple(dict.fromkeys(record["source_taxon_id"] for record in observations))
        lines = []
        for index, record in enumerate(observations, start=1):
            taxon = self._taxon(record["source_taxon_id"])
            korean_name = self._name_for(taxon, "ko")
            lines.append(f"{record['event_date_raw']}에 {record['locality_public']}에서 {korean_name} 관찰 기록이 있습니다. [{index}]")
        return self._answer(question, " ".join(lines), taxon_ids, tuple(evidence), "answer", ())

    def _resolve_taxa(self, question: str) -> list[dict[str, Any]]:
        normalized = question.casefold()
        matches = []
        for taxon in self.corpus.taxonomy:
            names = [taxon["scientific_name_raw"], *[name["name"] for name in taxon["vernacular_names"]]]
            if any(name.casefold() in normalized for name in names):
                matches.append(taxon)
        return matches

    def _matching_observations(self, question: str, taxa: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidate_ids = {taxon["source_taxon_id"] for taxon in taxa}
        records = [record for record in self.corpus.observations if record["source_taxon_id"] in candidate_ids]
        for display_name, place_id in PLACE_NAMES.items():
            if display_name in question:
                records = [record for record in records if record["place_external_id"] == place_id]
                break
        month_match = re.search(r"(2025)년\s*(\d{1,2})월", question)
        if month_match:
            month = int(month_match.group(2))
            records = [record for record in records if record["event_date_raw"][5:7] == f"{month:02d}"]
        return records

    def _name_answer(self, question: str, taxon: dict[str, Any]) -> Answer:
        evidence = (taxon["source_taxon_id"],)
        if "학명" in question:
            text = f"{self._name_for(taxon, 'ko')}의 학명은 {taxon['scientific_name_raw']}입니다. [1]"
        else:
            text = f"{taxon['scientific_name_raw']}의 한국어 이름은 {self._name_for(taxon, 'ko')}입니다. [1]"
        return self._answer(question, text, (taxon["source_taxon_id"],), evidence, "answer", ())

    def _document_answer(self, question: str, document_id: str, taxon_ids: tuple[str, ...]) -> Answer:
        chunks = [chunk for chunk in self.corpus.chunks if chunk["document_id"] == document_id]
        if document_id == "fixture-doc-waterbirds":
            text = "Fixture 물가 조류 관찰 기록은 흰뺨검둥오리와 왜가리의 fixture 호수·하천 관찰을 지지합니다. [1] 물가 서식지 설명도 제공합니다. [2]"
        else:
            text = "Fixture 도시 숲 조류 관찰 기록은 fixture 숲과 연결된 쇠딱다구리 관찰을 지지합니다. [1] 도시 녹지 서식지 설명도 제공합니다. [2]"
        return self._answer(question, text, taxon_ids, tuple(chunk["chunk_id"] for chunk in chunks), "answer", ())

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
            taxonomy_release=self.corpus.manifest["taxonomy_release"],
            data_cutoff=self.corpus.manifest["retrieved_at"],
        )

    def _citation(self, evidence_id: str) -> Citation:
        record = self.corpus.evidence_record(evidence_id)
        if record is None:
            raise ValueError(f"Unknown evidence ID: {evidence_id}")
        source = self.corpus.source_registry[record["source_id"]]
        locator = record.get("locator") or record.get("occurrence_id") or record.get("source_taxon_id")
        return Citation(
            evidence_id=evidence_id,
            source_id=record["source_id"],
            source_url=source["landing_uri"],
            locator=locator,
            license_name="fixture-test-license",
        )

    def _taxon(self, taxon_id: str) -> dict[str, Any]:
        for taxon in self.corpus.taxonomy:
            if taxon["source_taxon_id"] == taxon_id:
                return taxon
        raise ValueError(f"Unknown taxon ID: {taxon_id}")

    @staticmethod
    def _name_for(taxon: dict[str, Any], language: str) -> str:
        for name in taxon["vernacular_names"]:
            if name["language"] == language:
                return name["name"]
        raise ValueError(f"No {language} name for {taxon['source_taxon_id']}")


def validate_answer(answer: Answer, corpus: FixtureCorpus) -> None:
    """Reject nonexistent, policy-filtered, or coordinate-leaking citations."""

    if not set(answer.evidence_ids).issubset(corpus.evidence_ids):
        raise ValueError("Answer contains an evidence ID outside the allowed corpus")
    if tuple(citation.evidence_id for citation in answer.citations) != answer.evidence_ids:
        raise ValueError("Answer citations do not match evidence IDs")
    for record in corpus.observations:
        if record["sensitivity_class"] == "withheld":
            for private_value in (record["latitude_private"], record["longitude_private"]):
                if private_value is not None and str(private_value) in answer.answer_text:
                    raise ValueError("Answer leaks a private coordinate")
