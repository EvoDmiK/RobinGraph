"""Send TEST chat requests and verify their MLflow response tags are searchable.

For each case the script POSTs /v1/chat, then finds the new trace with the
server-side tag filter
``tags.response_reason = '<reason>' AND tags.response_disposition = '<disposition>'``
(the documented ``search_traces(filter_string=...)`` contract), keeping only
traces newer than the request whose span inputs contain a per-run marker.  It prints only
trace ids, tag values and pass/fail -- never credentials, URIs or answer text.

Needs MLFLOW_TRACKING_URI (+ MLFLOW_EXPERIMENT_NAME) in the environment and the
tracing extra.  Cases that need a model/Jina call are not included; the default
cases use explicit intents so no external provider is invoked.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any
from urllib.request import Request, urlopen

# name -> (request, disposition, reason, failure_stage, selected_intent, route_method)
CASES: dict[str, tuple[dict[str, Any], str, str, str, str, str]] = {
    "taxon_not_found": ({"question": "존재하지않는새-{n}", "intent": "profile"},
                        "abstain", "taxon_not_found", "name_resolution", "profile", "explicit"),
    "filter_missing": ({"question": "관찰 기록 {n}", "intent": "observations"},
                       "clarify", "filter_mismatch", "validation", "observations", "explicit"),
}


def _tags(trace: Any) -> dict[str, str]:
    return dict(getattr(trace.info, "tags", None) or {})


def _trace_id(trace: Any) -> str:
    return getattr(trace.info, "trace_id", getattr(trace.info, "request_id", ""))


def _post(base_url: str, body: dict[str, Any]) -> int:
    request = Request(
        base_url.rstrip("/") + "/v1/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "RobinGraph-Tag-Verifier/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        response.read()
        return response.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=int, default=45)
    parser.add_argument("--cases", nargs="*", default=sorted(CASES), choices=sorted(CASES))
    args = parser.parse_args()
    import mlflow

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    experiment = mlflow.set_experiment(os.environ["MLFLOW_EXPERIMENT_NAME"])
    results = []
    for name in args.cases:
        body, disposition, reason, stage, intent, method = CASES[name]
        marker = uuid.uuid4().hex[:10]
        body = {**body, "question": body["question"].format(n=marker)}
        started_ms = int(time.time() * 1000) - 1000
        status = _post(args.base_url, body)
        filter_string = f"tags.response_reason = '{reason}' AND tags.response_disposition = '{disposition}'"
        found = None
        deadline = time.monotonic() + args.wait_seconds
        while time.monotonic() < deadline and found is None:
            traces = mlflow.search_traces(
                experiment_ids=[experiment.experiment_id], filter_string=filter_string,
                return_type="list", max_results=50,
            )
            for trace in traces:
                if getattr(trace.info, "request_time", 0) < started_ms:
                    continue
                if any(marker in json.dumps(s.inputs, ensure_ascii=False, default=str) for s in trace.data.spans):
                    found = trace
                    break
            if found is None:
                time.sleep(1)
        tags = _tags(found) if found else {}
        expected = {"response_disposition": disposition, "response_reason": reason, "failure_stage": stage,
                    "selected_intent": intent, "route_method": method}
        ok = status == 200 and found is not None and all(tags.get(k) == v for k, v in expected.items())
        state = getattr(getattr(found.info, "state", None), "value", None) if found else None
        results.append({"case": name, "http_status": status, "trace_id": _trace_id(found) if found else None,
                        "trace_state": state, "found_by_tag_filter": found is not None,
                        "tags": {k: tags.get(k) for k in expected}, "passed": ok})
    print(json.dumps({"passed": all(r["passed"] for r in results), "cases": results}, ensure_ascii=False, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
