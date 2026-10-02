"""Send one TEST chat question and verify its connected MLflow trace.

Run with the tracing extra installed. Never prints credentials or source text.
The request can invoke Gemini/Jina, as an ordinary chat request does.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--question', default='물가에 사는 새의 먹이와 서식지에 대한 근거를 알려줘.')
    parser.add_argument('--intent', choices=('auto', 'evidence', 'profile', 'taxonomy'), default='evidence')
    parser.add_argument('--require-model', action='store_true')
    parser.add_argument('--wait-seconds', type=int, default=30)
    args = parser.parse_args()
    import mlflow

    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    experiment = mlflow.set_experiment(os.environ['MLFLOW_EXPERIMENT_NAME'])
    started_ms = int(time.time() * 1000)
    request = Request(
        args.base_url.rstrip('/') + '/v1/chat',
        data=json.dumps({'question': args.question, 'intent': args.intent}).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'RobinGraph-Trace-Verifier/1.0'},
    )
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    def _parse_dict(val: Any) -> dict:
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def _span_matches(s: Any) -> bool:
        if s.name != 'POST /v1/chat':
            return False
        inputs = _parse_dict(s.inputs)
        req = inputs.get('request', {})
        if isinstance(req, dict) and req.get('question') == args.question:
            return True
        return inputs.get('question') == args.question

    deadline = time.monotonic() + args.wait_seconds
    matches = []
    while time.monotonic() < deadline:
        traces = mlflow.search_traces(
            experiment_ids=[experiment.experiment_id], return_type='list', max_results=50,
        )
        matches = [
            t for t in traces
            if getattr(t.info, 'request_time', getattr(t.info, 'timestamp_ms', 0)) >= started_ms
            and any(_span_matches(s) for s in t.data.spans)
        ]
        if matches:
            break
        time.sleep(1)
    if len(matches) != 1:
        print(json.dumps({'passed': False, 'reason': 'Expected exactly one request trace', 'matches': len(matches)}))
        return 1
    trace = matches[0]
    spans = trace.data.spans
    roots = [s for s in spans if s.parent_id is None]
    ids = {s.span_id for s in spans}
    connected = len(roots) == 1 and all(s.parent_id is None or s.parent_id in ids for s in spans)

    def _type_str(s: Any) -> str:
        raw = getattr(s, 'span_type', '')
        return getattr(raw, 'name', str(raw)).strip('"').upper()

    retrieval = any(_type_str(s) == 'RETRIEVER' for s in spans)
    model = any(_type_str(s) == 'LLM' for s in spans)
    passed = connected and retrieval and (model or not args.require_model)

    trace_id = getattr(trace.info, 'trace_id', getattr(trace.info, 'request_id', None))
    span_summaries = []
    for s in spans:
        attrs = _parse_dict(getattr(s, 'attributes', {}))
        status_obj = getattr(s, 'status', None)
        status_code = getattr(status_obj, 'status_code', status_obj)
        status_str = getattr(status_code, 'name', str(status_code)) if status_code is not None else 'UNKNOWN'
        duration = None
        if s.end_time_ns is not None and s.start_time_ns is not None:
            duration = round((s.end_time_ns - s.start_time_ns) / 1_000_000, 2)
        span_summaries.append({
            'name': s.name,
            'type': _type_str(s),
            'duration_ms': duration,
            'status': status_str,
            'has_inputs': s.inputs is not None,
            'has_outputs': s.outputs is not None,
            'token_usage': attrs.get('mlflow.chat.tokenUsage'),
        })

    summary = {
        'passed': passed,
        'trace_id': trace_id,
        'experiment_id': experiment.experiment_id,
        'disposition': result.get('disposition'),
        'connected': connected,
        'retrieval': retrieval,
        'model': model,
        'spans': span_summaries,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
