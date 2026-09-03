"""Command line entry points for fixture verification and evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fixture import default_fixture_root, load_fixture
from .graph.settings import Neo4jSettings
from .slice import FixtureQuestionService, validate_answer


def _gold_questions(root: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (root / "gold-questions.jsonl").read_text(encoding="utf-8").splitlines() if line]


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
    corpus = load_fixture(root)
    service = FixtureQuestionService(corpus)
    failures = []
    for gold in _gold_questions(root):
        answer = service.answer(str(gold["question_ko"]))
        try:
            validate_answer(answer, corpus)
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
    from .graph.neo4j_client import bootstrap_schema, load_fixture

    settings = Neo4jSettings.from_environment()
    corpus = load_fixture_data()
    bootstrap_schema(settings)
    counts = load_fixture(settings, corpus)
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


def load_fixture_data():
    return load_fixture()


def main() -> int:
    parser = argparse.ArgumentParser(prog="robingraph")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-fixture").set_defaults(handler=validate_fixture)
    commands.add_parser("evaluate-fixture").set_defaults(handler=evaluate)
    commands.add_parser("verify-neo4j").set_defaults(handler=verify_neo4j)
    commands.add_parser("load-neo4j-fixture").set_defaults(handler=load_neo4j_fixture)
    commands.add_parser("verify-neo4j-fixture").set_defaults(handler=verify_neo4j_fixture)
    serve = commands.add_parser("serve-fixture")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(handler=serve_fixture)
    arguments = parser.parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
