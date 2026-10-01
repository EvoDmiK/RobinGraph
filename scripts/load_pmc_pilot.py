"""Load one CC BY PMC article into the disposable Neo4j search corpus.

The nodes carry both :Fixture and :PmcPilot. A later load-neo4j-fixture run
removes them; this is an end-to-end pilot, not an operational literature loader.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree

from neo4j import GraphDatabase

from robingraph.environment import load_local_environment
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.validation import validate_source_registry_record
from robingraph.retrieval.neo4j_hybrid import bootstrap_hybrid_search_schema


PMCID = "PMC9946348"
SOURCE_ID = "pmc-oa-ccby-pilot-9946348"
LICENSE_URI = "https://creativecommons.org/licenses/by/4.0/"
ARTICLE_URL = f"https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/"
OAI_URL = (
    "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
    "?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:9946348&metadataPrefix=pmc"
)
ROOT = Path(__file__).resolve().parents[1]


def _fetch(url: str) -> bytes:
    with urlopen(url, timeout=20) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError("PMC response exceeded 5 MB")
    return data


def _source() -> dict:
    records = json.loads((ROOT / "config/source-registry.json").read_text(encoding="utf-8"))
    source = next((row for row in records if row.get("source_id") == SOURCE_ID), None)
    if source is None or validate_source_registry_record(source):
        raise ValueError("PMC pilot source registry entry is missing or invalid")
    if source.get("enabled") is not True or source.get("license_policy_status") != "allowed":
        raise ValueError("PMC pilot source is not approved")
    if source.get("license_uri") != LICENSE_URI or source.get("landing_uri") != ARTICLE_URL:
        raise ValueError("PMC pilot registry article or license does not match")
    return source


def parse_article(oai_xml: bytes) -> tuple[str, str, list[dict]]:
    """Check article identity and rights, then retain abstract/body paragraphs."""

    def local(element: ElementTree.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    root = ElementTree.fromstring(oai_xml)
    article_meta = next((element for element in root.iter() if local(element) == "article-meta"), None)
    if article_meta is None:
        raise ValueError("PMC article metadata was missing")
    license_statements = [
        " ".join(element.itertext())
        for element in article_meta.iter()
        if local(element) == "license"
    ]
    if not any(LICENSE_URI in statement for statement in license_statements):
        raise ValueError("PMC article does not declare the expected CC BY 4.0 license")
    ids = {
        element.attrib.get("pub-id-type"): "".join(element.itertext()).strip()
        for element in article_meta.iter() if local(element) == "article-id"
    }
    if ids.get("pmcid") != PMCID:
        raise ValueError("PMC OAI record did not match the requested PMCID")
    title_element = next((element for element in article_meta.iter() if local(element) == "article-title"), None)
    title = " ".join(" ".join(title_element.itertext()).split()) if title_element is not None else ""
    doi = ids.get("doi", "")
    if not title or not doi:
        raise ValueError("PMC title/DOI was missing")

    section_counts: dict[str, int] = {}
    chunks: list[dict] = []

    def walk(element: ElementTree.Element, section: str) -> None:
        tag = local(element)
        if tag in {"fig", "table-wrap", "supplementary-material", "ref-list", "boxed-text"}:
            return
        if tag == "sec":
            heading = next((child for child in element if local(child) == "title"), None)
            if heading is not None:
                section = " ".join(" ".join(heading.itertext()).split()) or section
        if tag == "p":
            body = " ".join(" ".join(element.itertext()).split())
            if body:
                section_counts[section] = section_counts.get(section, 0) + 1
                ordinal = len(chunks) + 1
                chunks.append({
                    "id": f"pmc-pilot:{PMCID}:p{ordinal:03d}",
                    "ordinal": ordinal,
                    "section": section,
                    "locator": f"{section} paragraph {section_counts[section]}",
                    "text": body,
                    "content_hash": sha256(body.encode("utf-8")).hexdigest(),
                })
            return
        for child in element:
            walk(child, section)

    for element in root.iter():
        if local(element) in {"abstract", "body"}:
            walk(element, "Abstract" if local(element) == "abstract" else "Body")
    if not chunks:
        raise ValueError("PMC article had no permitted body paragraphs")
    return title, doi, chunks


def article_hash(oai_xml: bytes) -> str:
    """Hash the article, excluding OAI responseDate and envelope metadata."""

    root = ElementTree.fromstring(oai_xml)
    article = next(
        (element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "article"),
        None,
    )
    if article is None:
        raise ValueError("PMC OAI record did not contain an article")
    return sha256(ElementTree.tostring(article, encoding="utf-8")).hexdigest()


def _write(settings: Neo4jSettings, title: str, doi: str, chunks: list[dict], raw_hash: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    _source()
    release = f"{PMCID}-{raw_hash[:12]}"
    dataset_id = f"{SOURCE_ID}:{release}"
    bootstrap_hybrid_search_schema(settings, dimensions=None)
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database) as session:
            def write(tx):
                tx.run("MATCH (node:PmcPilot) DETACH DELETE node").consume()
                tx.run(
                    """
                    MERGE (dataset:SourceDataset:RobinGraph:Fixture:PmcPilot {id: $dataset_id})
                    SET dataset.name = $source_id, dataset.version = $release,
                        dataset.landing_uri = $article_url, dataset.policy_status = 'allowed'
                    MERGE (license:License:RobinGraph:Fixture {id: $license_uri})
                    SET license.license_uri = $license_uri, license.license_name = 'CC BY 4.0',
                        license.policy_status = 'allowed'
                    MERGE (dataset)-[:LICENSED_UNDER]->(license)
                    MERGE (source:SourceRecord:RobinGraph:Fixture:PmcPilot {id: $document_source_id})
                    SET source.external_id = $pmcid, source.record_type = 'document',
                        source.raw_uri = $oai_url, source.raw_hash = $raw_hash,
                        source.retrieved_at = $timestamp
                    MERGE (source)-[:IN_DATASET]->(dataset)
                    MERGE (document:Document:RobinGraph:Fixture:PmcPilot {id: $document_id})
                    SET document.title = $title, document.language = 'en',
                        document.doi = $doi, document.retrieved_at = $timestamp,
                        document.embedding_allowed = false
                    MERGE (document)-[:FROM_RECORD]->(source)
                    """,
                    dataset_id=dataset_id, source_id=SOURCE_ID, release=release,
                    article_url=ARTICLE_URL, license_uri=LICENSE_URI,
                    document_source_id=f"pmc-pilot:{PMCID}:record",
                    pmcid=PMCID, oai_url=OAI_URL, raw_hash=raw_hash,
                    timestamp=timestamp, document_id=f"pmc-pilot:{PMCID}",
                    title=title, doi=doi,
                ).consume()
                tx.run(
                    """
                    UNWIND $chunks AS row
                    MATCH (dataset:SourceDataset:PmcPilot {id: $dataset_id})
                    MATCH (document:Document:PmcPilot {id: $document_id})
                    MERGE (source:SourceRecord:RobinGraph:Fixture:PmcPilot {id: row.id + ':record'})
                    SET source.external_id = row.id, source.record_type = 'chunk',
                        source.raw_uri = $oai_url, source.raw_hash = $raw_hash,
                        source.retrieved_at = $timestamp
                    MERGE (source)-[:IN_DATASET]->(dataset)
                    MERGE (chunk:Chunk:RobinGraph:Fixture:PmcPilot {id: row.id})
                    SET chunk.text = row.text, chunk.section = row.section,
                        chunk.ordinal = row.ordinal, chunk.content_hash = row.content_hash
                    SET chunk:HybridSearchChunk
                    MERGE (document)-[:HAS_CHUNK]->(chunk)
                    MERGE (chunk)-[:FROM_RECORD]->(source)
                    MERGE (evidence:EvidenceUnit:RobinGraph:Fixture:PmcPilot {id: 'fixture-evidence:' + row.id})
                    SET evidence.evidence_type = 'chunk', evidence.locator = row.locator,
                        evidence.accessed_at = $timestamp
                    MERGE (evidence)-[:FROM_CHUNK]->(chunk)
                    MERGE (evidence)-[:FROM_RECORD]->(source)
                    """,
                    chunks=chunks, dataset_id=dataset_id,
                    document_id=f"pmc-pilot:{PMCID}", oai_url=OAI_URL,
                    raw_hash=raw_hash, timestamp=timestamp,
                ).consume()
            session.execute_write(write)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write to the configured disposable Neo4j database")
    args = parser.parse_args()
    source = _source()
    oai_xml = _fetch(OAI_URL)
    title, doi, chunks = parse_article(oai_xml)
    raw_hash = article_hash(oai_xml)
    if args.apply:
        load_local_environment()
        _write(Neo4jSettings.from_environment(), title, doi, chunks, raw_hash)
    print(json.dumps({
        "pmcid": PMCID, "title": title, "doi": doi,
        "source_id": source["source_id"], "license": source["license_name"],
        "chunks": len(chunks), "raw_sha256": raw_hash,
        "applied": args.apply,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
