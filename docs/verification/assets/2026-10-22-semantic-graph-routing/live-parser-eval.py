"""Run inside TEST with prepared /tmp/rg204-eval files; no DB or serving-code changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from dataclasses import replace

base = Path('/tmp/rg204-eval')
modules = (
    ('robingraph.embeddings', 'src/robingraph/embeddings/__init__.py'),
    ('robingraph.retrieval.graph_intent_schema', 'src/robingraph/retrieval/graph_intent_schema.py'),
    ('robingraph.retrieval.graph_semantic_router', 'src/robingraph/retrieval/graph_semantic_router.py'),
    ('robingraph.retrieval.graph_condition_extractor', 'src/robingraph/retrieval/graph_condition_extractor.py'),
    ('rg204_eval', 'scripts/eval_graph_questions.py'),
)
for name, path in modules:
    spec = importlib.util.spec_from_file_location(
        name, base / path,
        submodule_search_locations=[str((base / path).parent)] if name == 'robingraph.embeddings' else None,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

from robingraph.embeddings import JinaEmbeddingClient, JinaEmbeddingSettings
from robingraph.retrieval.graph_intent_schema import execution_gate
from robingraph.retrieval.graph_semantic_router import GraphSemanticRouter
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent

evaluator = sys.modules['rg204_eval']
settings = replace(JinaEmbeddingSettings.from_env(), timeout_seconds=2, max_retries=0)
router = GraphSemanticRouter(JinaEmbeddingClient(settings))
gold = base / 'data/eval/graph_questions/holdout.jsonl'
valid, errors = evaluator.check(evaluator.load(gold))
assert not errors, errors
started = time.perf_counter()
warm = router.warm()
warm_ms = (time.perf_counter() - started) * 1000
routes = []


def analyze(question):
    lexical = extract_graph_intent(question)
    if execution_gate(question, lexical) == 'not_graph':
        routes.append({'status': 'not_graph', 'embedding_calls': 0})
        return lexical, lexical.kind, False
    candidates = router.classify(question)
    routes.append({
        'status': candidates.status, 'top': candidates.top,
        'score': candidates.candidates[0][1] if candidates.candidates else None,
        'margin': candidates.margin, 'elapsed_ms': candidates.elapsed_ms,
        'embedding_calls': candidates.embedding_calls, 'prototype_calls': candidates.prototype_calls,
        'prototype_requests': candidates.prototype_requests, 'prototype_batches': candidates.prototype_batches,
    })
    intent = extract_graph_intent(question, candidates)
    return intent, intent.kind, execution_gate(question, intent) == 'answer'


items, times = evaluator.score(valid, analyze=analyze)
report = evaluator.report(items, times)
report.update(
    scope='Actual TEST self-hosted embeddings + new parser only; no DB, no serving app replacement',
    warm_success=warm, warm_ms=warm_ms, embedding_model=settings.model, dimensions=settings.dimensions,
    routes=routes, routes_include_one_unscored_warmup=True,
    holdout_sha256=hashlib.sha256(gold.read_bytes()).hexdigest(), db_writes=0,
)
print(json.dumps(report, ensure_ascii=False, indent=2))
