"""Actual TEST API fixture baseline, not a multi-document literature evaluation.

Run with PYTHONPATH=src from repo root. No mocked routes or DB writes.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics
from types import SimpleNamespace
import urllib.request

from robingraph.retrieval.evaluation import evaluate_search, load_search_questions


BASE = 'http://127.0.0.1:8000'


def fetch(path, body=None):
    request = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json', 'User-Agent': 'RobinGraph-RG202-Audit/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    health = fetch('/health')
    assert health['deployment_target'] == 'test' and health['mode'] == 'neo4j'
    path = Path('data/eval/v1/search-questions.jsonl')
    questions = load_search_questions(path)
    output = {'scope': 'synthetic fixture; actual TEST API, DB and configured embedding service',
              'health': health, 'question_count': len(questions), 'multihop_questions': 0,
              'questions_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'repeats': 3, 'limit': 5, 'modes': {}}
    for mode in ('fulltext', 'hybrid'):
        calls = []

        def search(question, limit):
            data = fetch('/v1/search', {'question': question, 'mode': mode, 'limit': limit})
            # Keep backend/fallback information; never export document text.
            calls.append({'requested_mode': mode, 'actual_mode': data['mode'],
                          'warnings': data['warnings'],
                          'result_channels': [r['channels'] for r in data['results']]})
            return SimpleNamespace(results=[SimpleNamespace(chunk_id=r['chunk_id']) for r in data['results']])

        search(questions[0].question_ko, 5)  # Warmup excluded from measurements.
        calls.clear()
        reports = [evaluate_search(questions, search, limit=5).as_dict() for _ in range(3)]
        latencies = sorted(c['elapsed_ms'] for r in reports for c in r['cases'])
        output['modes'][mode] = {
            'runs': reports, 'calls': calls,
            'p50_ms': statistics.median(latencies),
            'p95_ms': latencies[math.ceil(len(latencies) * .95) - 1],
            'all_runs_policy_safe': all(r['policy_safe'] for r in reports),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
