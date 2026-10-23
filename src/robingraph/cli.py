"""Command line entry points for fixture verification, evaluation, and serving."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from .environment import load_local_environment
from .fixture import default_fixture_root, load_fixture
from .graph.settings import Neo4jSettings
from .retrieval.fixture_repository import FixtureRepository
from .slice import QuestionService, validate_answer
from .tracing import configure_tracing


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


def migrate_postgres(_: argparse.Namespace) -> int:
    """Apply the forward-only ingest control-plane migrations."""

    from .ingest.postgres import PostgresSettings, apply_migrations

    report = apply_migrations(PostgresSettings.from_environment())
    print(json.dumps(asdict(report), ensure_ascii=False))
    return 0


def verify_postgres(_: argparse.Namespace) -> int:
    """Verify that the configured PostgreSQL ingest schema is complete."""

    from .ingest.postgres import PostgresSettings, verify_schema

    settings = PostgresSettings.from_environment()
    tables = verify_schema(settings)
    print(
        json.dumps(
            {"database": settings.database, "schema": settings.schema, "tables": tables},
            ensure_ascii=False,
        )
    )
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

    configure_tracing()

    uvicorn.run("robingraph.django_api.asgi:application", host=arguments.host, port=arguments.port)
    return 0


def serve_ingest(arguments: argparse.Namespace) -> int:
    """Serve only the explicitly enabled PostgreSQL ingest control boundary."""

    import uvicorn

    from .api.drf import create_django_app
    from .ingest.postgres import PostgresSettings
    from .ingest.store import IngestionStore

    settings = PostgresSettings.from_environment()
    configure_tracing()
    app = create_django_app(ingest_store=IngestionStore(settings))
    uvicorn.run(app, host=arguments.host, port=arguments.port)
    return 0


def serve_neo4j(arguments: argparse.Namespace) -> int:
    import uvicorn

    from .api.drf import create_django_app
    from .api.services import (
        create_neo4j_korean_lineage_handler,
        create_neo4j_lineage_handler,
        create_neo4j_observation_handler,
        create_neo4j_search_handler,
    )
    from .api.semantic_router import SemanticRouter
    from .embeddings import EmbeddingConfigurationError, JinaEmbeddingClient
    from .ingest.postgres import PostgresSettings
    from .ingest.store import IngestionStore
    from .retrieval.neo4j_repository import Neo4jGraphRepository
    from .retrieval.operational_neo4j import Neo4jOperationalObservationRepository
    from .retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository

    settings = Neo4jSettings.from_environment()
    # Fail-open and synchronous: autolog must be enabled before the LCEL
    # flows run, and an unreachable tracking server only disables tracing.
    configure_tracing()
    ingest_store = IngestionStore(PostgresSettings.from_environment())
    repository = Neo4jGraphRepository(settings)
    operational_repository = Neo4jOperationalObservationRepository(settings)
    def active_taxonomy_context() -> tuple[str, str] | None:
        context = ingest_store.active_release_context("reference-taxonomy-traits")
        if context is None:
            return None
        concept_set_id = context.cursor.get("concept_set_id")
        taxonomy_release = context.cursor.get("taxonomy_release")
        if not isinstance(concept_set_id, str) or not isinstance(taxonomy_release, str):
            return None
        return concept_set_id, taxonomy_release

    lineage_repository = Neo4jTaxonomyLineageRepository(
        settings,
        lambda: ingest_store.active_dataset_id("korean-vernacular-names"),
        active_taxonomy_context,
    )
    from .retrieval.species_profile import create_species_flow, read_traits, read_conservation

    def resolve_species(name):
        if any("\uac00" <= char <= "\ud7a3" for char in name):
            return lineage_repository.lineage_for_korean_name(name)
        lineage = lineage_repository.lineage_for_scientific_name(name)
        return lineage if lineage is not None else lineage_repository.lineage_for_english_name(name)

    # Constructing the stdlib client is configuration-only: it makes no HTTP
    # request.  A missing/invalid non-secret embedding configuration merely
    # disables auto routing; explicit chat routes and all legacy endpoints
    # remain available.
    embedding_client = None
    semantic_router = None
    try:
        embedding_client = JinaEmbeddingClient.from_env()
        semantic_router = SemanticRouter(embedding_client)
    except EmbeddingConfigurationError:
        pass
    from .retrieval.taxon_name_resolution import TaxonNameResolver
    from .retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository
    name_vectors = Neo4jTaxonNameVectorRepository(settings)
    name_resolver = TaxonNameResolver(
        resolve_species, lineage_repository.reviewed_name_candidates,
        embedding_client=embedding_client, active_context=active_taxonomy_context,
        candidate_search=name_vectors.search,
    )
    graph_intent_mode = os.getenv("ROBINGRAPH_GRAPH_INTENT_MODE", "off").strip().lower()
    if graph_intent_mode not in ("off", "shadow", "active"):
        raise ValueError("ROBINGRAPH_GRAPH_INTENT_MODE must be off, shadow or active")
    graph_intent_handler = None
    graph_plan_handler = None
    graph_resolve_species = resolve_species
    if graph_intent_mode != "off":
        from . import tracing
        from .retrieval.graph_condition_extractor import extract_graph_intent
        from .retrieval.graph_intent_schema import execution_gate
        from .retrieval.graph_semantic_router import GraphSemanticRouter
        from .retrieval.species_profile import SpeciesNotFoundError

        # Graph interpretation has a short budget; other embedding consumers
        # retain their existing settings. No request is made during construction.
        graph_client = (JinaEmbeddingClient(replace(embedding_client.settings, timeout_seconds=2, max_retries=0))
                        if embedding_client is not None else None)
        graph_router = GraphSemanticRouter(graph_client) if graph_client is not None else None

        def graph_intent_handler(question):
            with tracing.span("graph_intent.candidates", tracing.CHAIN) as candidate_span:
                lexical = extract_graph_intent(question)
                if execution_gate(question, lexical) == "not_graph":
                    candidate_span.set_attributes({"graph_intent.status": "not_graph",
                                                   "graph_intent.embedding_calls": 0,
                                                   "graph_intent.prototype_calls": 0})
                    return lexical
                candidates = graph_router.classify(question) if graph_router is not None else ()
                if graph_router is not None:
                    candidate_span.set_attributes({
                        "graph_intent.status": candidates.status, "graph_intent.top": candidates.top,
                        "graph_intent.score": candidates.candidates[0][1] if candidates.candidates else None,
                        "graph_intent.margin": candidates.margin, "graph_intent.elapsed_ms": candidates.elapsed_ms,
                        "graph_intent.embedding_calls": candidates.embedding_calls,
                        "graph_intent.prototype_calls": candidates.prototype_calls,
                        "graph_intent.prototype_requests": candidates.prototype_requests,
                        "graph_intent.prototype_batches": candidates.prototype_batches,
                        "graph_intent.model": candidates.model,
                        "graph_intent.prototype_version": candidates.prototype_version,
                    })
                return extract_graph_intent(question, candidates)

        graph_name_resolver = TaxonNameResolver(
            resolve_species, lineage_repository.reviewed_name_candidates,
            embedding_client=graph_client, active_context=active_taxonomy_context,
            candidate_search=name_vectors.search,
        )

        def graph_resolve_species(name):
            # Vector suggestions remain suggestions. Never auto-select a typo candidate.
            match = graph_name_resolver.resolve(name)
            if match.get("status") != "matched":
                if match.get("status") == "unavailable":
                    raise RuntimeError("Graph name resolution unavailable")
                raise SpeciesNotFoundError(name)
            lineage = resolve_species(match["canonical_name"])
            target = lineage.items[-1] if lineage is not None and lineage.items else None
            if (target is None or target.taxon_id != match.get("taxon_id")
                    or target.scientific_name != match.get("canonical_name")
                    or lineage.concept_set_id != match.get("concept_set_id")
                    or lineage.taxonomy_release != match.get("taxonomy_release")):
                raise RuntimeError("Graph name identity changed")
            return lineage
    from .api.jev_router import configured_jev_router
    jev_router = configured_jev_router()
    # Gemini answer generation is opt-in: only a configured API key wires it
    # in, and construction alone makes no request, consistent with the lazy
    # embedding client above. Unconfigured deployments keep the legacy
    # retrieval-only evidence response untouched.
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    answer_generator = None
    if gemini_api_key:
        from .generation import GeminiAnswerer

        gemini_model = os.getenv("ROBINGRAPH_GEMINI_MODEL", "gemini-3.8-flash")
        answer_generator = GeminiAnswerer(gemini_api_key, gemini_model)
    graph_interpreter = os.getenv("ROBINGRAPH_GRAPH_INTERPRETER", "lexical").strip().lower()
    if graph_interpreter not in ("lexical", "semantic"):
        raise ValueError("ROBINGRAPH_GRAPH_INTERPRETER must be lexical or semantic")
    if graph_interpreter == "semantic" and graph_intent_mode != "off":
        from .retrieval.semantic_graph_intent import SEMANTIC_PROTOTYPES, graph_intent_handler as interpret_graph
        from .retrieval.graph_semantic_router import PROTOTYPES

        if answer_generator is None or graph_client is None:
            raise ValueError("Semantic graph interpretation requires configured generation and embedding clients")
        interpretation_router = GraphSemanticRouter(graph_client, prototypes=PROTOTYPES + SEMANTIC_PROTOTYPES)

        def graph_plan_handler(question):
            lexical = extract_graph_intent(question)
            if execution_gate(question, lexical) == "answer":
                return graph_intent_handler(question)
            with tracing.span("graph_intent.interpret", tracing.CHAIN) as span:
                result = interpret_graph(question, provider=answer_generator.propose_structured_graph_intent,
                                         retrieve=interpretation_router.retrieve)
                span.set_attributes({"graph_intent.source": result.source, "graph_intent.kind": result.kind,
                                     "graph_intent.disposition": execution_gate(question, result)})
                return result
    from .retrieval.species_notes import create_species_notes

    from .retrieval.related_species import related_species
    from .retrieval.similar_species import similar_species
    from .retrieval.ecological_relations import ecological_relations
    from .retrieval.graph_questions import graph_question_answer
    from .retrieval.subspecies import subspecies_for, subspecies_metadata
    from .retrieval.name_relations import NameRelationRepository, PIPELINE as NAME_RELATIONS_PIPELINE

    name_relations_repository = NameRelationRepository(
        lineage_repository, lambda: ingest_store.active_release_context(NAME_RELATIONS_PIPELINE),
    )

    summarize_notes = getattr(answer_generator, 'species_notes', None)
    species_flow = create_species_flow(
        resolve_species, lambda lineage: read_traits(lineage_repository, ingest_store, lineage),
        conservation=lambda lineage: read_conservation(lineage_repository, lineage),
        notes=create_species_notes(summarize_notes) if callable(summarize_notes) else None,
        subspecies_info=lambda lineage: subspecies_metadata(lineage_repository,lineage),
    )
    basic_species_flow = create_species_flow(
        resolve_species, lambda lineage: read_traits(lineage_repository, ingest_store, lineage),
        conservation=lambda lineage: read_conservation(lineage_repository, lineage),
        subspecies_info=lambda lineage: subspecies_metadata(lineage_repository,lineage),
        include_enrichment=False,
    )
    from .retrieval.species_scope import with_species_scope

    def annotated_profile(flow, name):
        profile = flow.invoke(name)
        context = profile.get("lineage") or {}
        return {**profile, "taxon": with_species_scope(profile.get("taxon") or {}, "all",
                context.get("concept_set_id"), context.get("taxonomy_release"))}

    try:
        app = create_django_app(
            repository,
            search_handler=create_neo4j_search_handler(
                settings, embedding_client=embedding_client,
                english_search_terms=answer_generator.english_search_terms if answer_generator is not None else None,
            ),
            answer_generator=answer_generator,
            observation_handler=create_neo4j_observation_handler(operational_repository),
            lineage_handler=create_neo4j_lineage_handler(lineage_repository),
            korean_lineage_handler=create_neo4j_korean_lineage_handler(lineage_repository),
            semantic_router=semantic_router,
            jev_router=jev_router,
            species_profile_handler=lambda name: annotated_profile(species_flow, name),
            species_basic_profile_handler=lambda name: annotated_profile(basic_species_flow, name),
            taxon_name_resolution_handler=name_resolver.resolve,
            related_species_handler=lambda name, species_scope="all": related_species(lineage_repository, resolve_species, name, species_scope),
            similar_species_handler=lambda name, species_scope="all": similar_species(lineage_repository, ingest_store, resolve_species, name, species_scope),
            ecological_relations_handler=lambda name, species_scope="all": ecological_relations(lineage_repository, ingest_store, resolve_species, name, species_scope),
            graph_question_handler=lambda parsed, species_scope="all": graph_question_answer(
                lineage_repository, graph_resolve_species if graph_intent_mode == "active" else resolve_species,
                parsed, species_scope=species_scope, store=ingest_store),
            graph_intent_handler=graph_intent_handler,
            graph_plan_handler=graph_plan_handler,
            graph_intent_mode=graph_intent_mode,
            name_relations_handler=name_relations_repository.for_name,
            subspecies_handler=lambda name: subspecies_for(lineage_repository,resolve_species,name),
        )
        uvicorn.run(app, host=arguments.host, port=arguments.port)
    finally:
        name_vectors.close()
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
    commands.add_parser("migrate-postgres").set_defaults(handler=migrate_postgres)
    commands.add_parser("verify-postgres").set_defaults(handler=verify_postgres)
    commands.add_parser("load-neo4j-fixture").set_defaults(handler=load_neo4j_fixture)
    commands.add_parser("verify-neo4j-fixture").set_defaults(handler=verify_neo4j_fixture)
    serve = commands.add_parser("serve-fixture")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(handler=serve_fixture)
    serve_ingest_api = commands.add_parser(
        "serve-ingest",
        help="Serve the authenticated PostgreSQL source/control ingest API",
    )
    serve_ingest_api.add_argument("--host", default="127.0.0.1")
    serve_ingest_api.add_argument("--port", type=int, default=8001)
    serve_ingest_api.set_defaults(handler=serve_ingest)
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
    if arguments.command in {"migrate-postgres", "verify-postgres"}:
        from psycopg import Error as PostgresError

        try:
            return arguments.handler(arguments)
        except (PostgresError, ValueError) as error:
            print(f"PostgreSQL migration or verification failed: {error}", file=sys.stderr)
            return 1
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
