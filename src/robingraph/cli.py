"""Command line entry points for fixture verification, evaluation, and serving."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .environment import load_local_environment
from .fixture import default_fixture_root, load_fixture
from .graph.settings import Neo4jSettings
from .retrieval.fixture_repository import FixtureRepository
from .slice import QuestionService, validate_answer


def _gold_questions(root: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (root / "gold-questions.jsonl").read_text(encoding="utf-8").splitlines() if line]


def list_collection_points(arguments: argparse.Namespace) -> int:
    """Print validated collection boundaries without fetching external data."""

    from .ingest.collection_points import load_collection_points, serialize_points

    registry = load_collection_points()
    points = registry.select(scope=arguments.scope, include_blocked=arguments.include_blocked)
    print(
        json.dumps(
            {
                "registry_version": registry.registry_version,
                "selected_design": registry.selected_design,
                "collection_points": serialize_points(points),
            },
            ensure_ascii=False,
        )
    )
    return 0


def validate_fixture(_: argparse.Namespace) -> int:
    corpus = load_fixture()
    print(
        "Fixture valid: "
        f"{len(corpus.taxonomy)} taxa, {len(corpus.observations)} allowed observations, "
        f"{len(corpus.documents)} allowed documents, {len(corpus.chunks)} allowed chunks"
    )
    return 0


def evaluate(_: argparse.Namespace) -> int:
    root = default_fixture_root()
    repository = FixtureRepository(load_fixture(root))
    service = QuestionService(repository)
    failures = []
    for gold in _gold_questions(root):
        answer = service.answer(str(gold["question_ko"]))
        try:
            validate_answer(answer, repository)
            if answer.disposition != gold["expected_disposition"]:
                raise ValueError(f"expected {gold['expected_disposition']}, got {answer.disposition}")
            if not set(gold["expected_taxon_ids"]).issubset(answer.taxon_ids):
                raise ValueError("missing expected taxon")
            accepted = set(gold["acceptable_evidence_ids"])
            if accepted and not set(answer.evidence_ids).issubset(accepted):
                raise ValueError("unexpected evidence")
            if accepted and not set(answer.evidence_ids):
                raise ValueError("missing expected evidence")
            for forbidden in gold["must_not_include"]:
                if str(forbidden) in answer.answer_text or str(forbidden) in answer.evidence_ids:
                    raise ValueError(f"forbidden value present: {forbidden}")
        except ValueError as error:
            failures.append(f"{gold['question_id']}: {error}")
    if failures:
        print("Gold evaluation failed:")
        print("\n".join(failures))
        return 1
    print("Gold evaluation passed: 15/15 questions")
    return 0


def verify_neo4j(_: argparse.Namespace) -> int:
    from .graph.neo4j_client import verify_server

    settings = Neo4jSettings.from_environment()
    server = verify_server(settings)
    edition = f", {server.edition}" if server.edition else ""
    print(f"Neo4j reachable: {server.name} {server.version}{edition}; database={settings.database}")
    return 0


def load_neo4j_fixture(_: argparse.Namespace) -> int:
    from .graph.neo4j_client import bootstrap_schema, load_fixture as load_neo4j_fixture_graph

    settings = Neo4jSettings.from_environment()
    corpus = load_fixture()
    bootstrap_schema(settings)
    counts = load_neo4j_fixture_graph(settings, corpus)
    print(
        "Neo4j fixture loaded: "
        f"{counts.taxa} taxa, {counts.observations} observations, "
        f"{counts.documents} documents, {counts.chunks} chunks"
    )
    return 0


def verify_neo4j_fixture(_: argparse.Namespace) -> int:
    from .graph.neo4j_client import verify_fixture

    verification = verify_fixture(Neo4jSettings.from_environment())
    counts = verification.counts
    print(
        "Neo4j fixture verified: "
        f"{counts.taxa} taxa, {counts.observations} observations, {counts.documents} documents, {counts.chunks} chunks; "
        f"private_coordinates={verification.private_coordinate_properties}, "
        f"restricted_observations={verification.restricted_observations}"
    )
    if verification.private_coordinate_properties or verification.restricted_observations:
        return 1
    return 0


def serve_fixture(arguments: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("robingraph.api.app:app", host=arguments.host, port=arguments.port)
    return 0


def serve_neo4j(arguments: argparse.Namespace) -> int:
    import uvicorn

    from .api.app import (
        create_app,
        create_neo4j_lineage_handler,
        create_neo4j_observation_handler,
        create_neo4j_search_handler,
    )
    from .retrieval.neo4j_repository import Neo4jGraphRepository
    from .retrieval.operational_neo4j import Neo4jOperationalObservationRepository
    from .retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository

    settings = Neo4jSettings.from_environment()
    repository = Neo4jGraphRepository(settings)
    operational_repository = Neo4jOperationalObservationRepository(settings)
    lineage_repository = Neo4jTaxonomyLineageRepository(settings)
    try:
        app = create_app(
            repository,
            search_handler=create_neo4j_search_handler(settings),
            observation_handler=create_neo4j_observation_handler(operational_repository),
            lineage_handler=create_neo4j_lineage_handler(lineage_repository),
        )
        uvicorn.run(app, host=arguments.host, port=arguments.port)
    finally:
        lineage_repository.close()
        operational_repository.close()
        repository.close()
    return 0


def ask_neo4j(arguments: argparse.Namespace) -> int:
    """Answer one question against the live Neo4j graph without starting the API.

    Useful for smoke-testing a `load-neo4j-fixture` load and for the opt-in
    Neo4j integration tests (`tests/test_neo4j_integration.py`).
    """

    from .retrieval.neo4j_repository import Neo4jGraphRepository

    with Neo4jGraphRepository(Neo4jSettings.from_environment()) as repository:
        service = QuestionService(repository)
        answer = service.answer(arguments.question)
        validate_answer(answer, repository)
        print(
            json.dumps(
                {
                    "answer_text": answer.answer_text,
                    "disposition": answer.disposition,
                    "taxon_ids": list(answer.taxon_ids),
                    "evidence_ids": list(answer.evidence_ids),
                    "warnings": list(answer.warnings),
                },
                ensure_ascii=False,
            )
        )
    return 0


def index_neo4j_fixture(arguments: argparse.Namespace) -> int:
    """Explicit search schema/vector write for the already loaded fixture."""
    from .embeddings import JinaEmbeddingClient, embed_fixture_chunks
    from .retrieval.neo4j_hybrid import bootstrap_hybrid_search_schema, index_chunks

    settings = Neo4jSettings.from_environment()
    client = JinaEmbeddingClient.from_env() if arguments.embeddings else None
    bootstrap_hybrid_search_schema(settings, dimensions=client.profile.dimensions if client else None)
    output: dict[str, object] = {"mode": "fulltext", "fixture_only": True}
    if client:
        embedded = embed_fixture_chunks(load_fixture(), client)
        report = index_chunks(
            settings, embedded, expected_profile=client.profile,
            indexed_at=datetime.now(timezone.utc).isoformat(),
        )
        output.update(mode="hybrid", profile=asdict(client.profile), report=asdict(report))
        print(json.dumps(output, ensure_ascii=False))
        return 1 if report.skipped else 0
    print(json.dumps(output, ensure_ascii=False))
    return 0


def search_neo4j(arguments: argparse.Namespace) -> int:
    """Read-only document search; Jina is used only with explicit --hybrid."""
    from .embeddings import EmbeddingError, JinaEmbeddingClient
    from .retrieval.neo4j_hybrid import HybridSearchRequest, search

    settings = Neo4jSettings.from_environment()
    client = JinaEmbeddingClient.from_env() if arguments.hybrid else None
    request = HybridSearchRequest(
        query_text=arguments.question, limit=arguments.limit,
        fulltext_top_k=max(25, arguments.limit), vector_top_k=max(25, arguments.limit),
    )
    warnings: list[str] = []
    try:
        outcome = search(settings, request, query_embedder=client)
    except EmbeddingError:
        # Provider failures must never be replaced with fabricated vectors.
        outcome = search(settings, request)
        warnings.append("Embedding request failed; results are keyword-only fulltext")
    output = asdict(outcome)
    output["warnings"] = [*outcome.warnings, *warnings]
    output["mode"] = "hybrid" if any("vector" in result.channels for result in outcome.results) else "fulltext"
    output["fixture_only"] = True
    print(json.dumps(output, ensure_ascii=False))
    return 0


def evaluate_search_neo4j(arguments: argparse.Namespace) -> int:
    """Compare fixture fulltext, vector, and fused retrieval quality."""
    from .embeddings import JinaEmbeddingClient
    from .retrieval.evaluation import evaluate_search, load_search_questions
    from .retrieval.hybrid import FULLTEXT_CHANNEL, VECTOR_CHANNEL
    from .retrieval.neo4j_hybrid import HybridSearchRequest, search

    settings = Neo4jSettings.from_environment()
    questions = load_search_questions(default_fixture_root() / "search-questions.jsonl")
    requested_modes = ("fulltext", "vector", "hybrid") if arguments.mode == "all" else (arguments.mode,)
    client = JinaEmbeddingClient.from_env() if any(mode != "fulltext" for mode in requested_modes) else None
    channels = {
        "fulltext": (FULLTEXT_CHANNEL,),
        "vector": (VECTOR_CHANNEL,),
        "hybrid": (FULLTEXT_CHANNEL, VECTOR_CHANNEL),
    }
    reports: dict[str, object] = {}
    for mode in requested_modes:
        reports[mode] = evaluate_search(
            questions,
            lambda question, limit, mode=mode: search(
                settings,
                HybridSearchRequest(
                    question,
                    limit=limit,
                    fulltext_top_k=max(25, limit),
                    vector_top_k=max(25, limit),
                    channels=channels[mode],
                ),
                query_embedder=client if mode != "fulltext" else None,
            ),
            limit=arguments.limit,
        ).as_dict()
    print(json.dumps({"fixture_only": True, "modes": reports}, ensure_ascii=False))
    return 0


def _search_limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return number


def main() -> int:
    try:
        load_local_environment()
    except (OSError, ValueError) as error:
        print(f"Local environment configuration failed: {error}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(prog="robingraph")
    commands = parser.add_subparsers(dest="command", required=True)
    collection_points = commands.add_parser(
        "collection-points",
        help="List policy-validated taxonomy, trait, habitat, and vegetation collection points",
    )
    collection_points.add_argument(
        "--scope",
        choices=("taxonomy", "traits", "habitat", "vegetation", "conservation"),
    )
    collection_points.add_argument(
        "--include-blocked",
        action="store_true",
        help="Include disabled review-required and restricted collection points",
    )
    collection_points.set_defaults(handler=list_collection_points)
    commands.add_parser("validate-fixture").set_defaults(handler=validate_fixture)
    commands.add_parser("evaluate-fixture").set_defaults(handler=evaluate)
    commands.add_parser("verify-neo4j").set_defaults(handler=verify_neo4j)
    commands.add_parser("load-neo4j-fixture").set_defaults(handler=load_neo4j_fixture)
    commands.add_parser("verify-neo4j-fixture").set_defaults(handler=verify_neo4j_fixture)
    serve = commands.add_parser("serve-fixture")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(handler=serve_fixture)
    serve_graph = commands.add_parser("serve-neo4j")
    serve_graph.add_argument("--host", default="127.0.0.1")
    serve_graph.add_argument("--port", type=int, default=8000)
    serve_graph.set_defaults(handler=serve_neo4j)
    ask = commands.add_parser("ask-neo4j")
    ask.add_argument("--question", required=True)
    ask.set_defaults(handler=ask_neo4j)
    index = commands.add_parser("index-neo4j-fixture", help="Create fixture search indexes; optionally call Jina and store vectors")
    index.add_argument("--embeddings", action="store_true", help="Embed allowed fixture chunks using configured Jina server")
    index.set_defaults(handler=index_neo4j_fixture)
    search_parser = commands.add_parser("search-neo4j", help="Search fixture document chunks with citations")
    search_parser.add_argument("--question", required=True)
    search_parser.add_argument("--limit", type=_search_limit, default=10)
    search_parser.add_argument("--hybrid", action="store_true", help="Use the configured Jina server for the query vector")
    search_parser.set_defaults(handler=search_neo4j)
    evaluate_search_parser = commands.add_parser("evaluate-search-neo4j", help="Compare fixture fulltext, vector, and hybrid retrieval")
    evaluate_search_parser.add_argument("--mode", choices=("all", "fulltext", "vector", "hybrid"), default="all")
    evaluate_search_parser.add_argument("--limit", type=_search_limit, default=3)
    evaluate_search_parser.set_defaults(handler=evaluate_search_neo4j)
    arguments = parser.parse_args()
    if arguments.command in {"index-neo4j-fixture", "search-neo4j", "evaluate-search-neo4j"}:
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            return arguments.handler(arguments)
        except ValueError as error:
            print(f"Search configuration or validation failed: {error}", file=sys.stderr)
            return 1
        except (Neo4jError, ServiceUnavailable, SessionExpired):
            print("Neo4j search failed; check connectivity and run the fixture load/index commands.", file=sys.stderr)
            return 1
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
