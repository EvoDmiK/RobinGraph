"""Opt-in live, split-separated intent evaluation. No entity/DB success is inferred."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import statistics

from robingraph.api.app import _species_chat_question
from robingraph.api.jev_router import CRITERIA, JevRouter, JevSettings
from robingraph.api.question_entities import extract_name
from robingraph.api.semantic_router import SemanticRouter
from robingraph.embeddings import JinaEmbeddingClient
from robingraph.environment import load_local_environment
from robingraph.retrieval.species_questions import parse_species_question


def deterministic(question):
    focused = parse_species_question(question)
    if focused:
        return ("ecological_diet" if focused.category == "trophic_niche" else "ecological_habitat") if focused.topic == "ecological_related" else focused.topic
    recognized = _species_chat_question(question)
    return recognized[0] if recognized else None


def metrics(rows, field):
    per_label = {}
    for label in CRITERIA:
        tp = sum(r["expected"] == label and r[field] == label for r in rows)
        fp = sum(r["expected"] != label and r[field] == label for r in rows)
        fn = sum(r["expected"] == label and r[field] != label for r in rows)
        n = sum(r["expected"] == label for r in rows)
        per_label[label] = {"n": n, "accuracy": tp/n if n else None, "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0}
    total = len(rows)
    return {"n": total, "accuracy":sum(r[field] == r["expected"] for r in rows)/total,
            "macro_f1":statistics.mean(v["f1"] for v in per_label.values()),
            "automatic_rate":sum(r[field] != "uncertain" for r in rows)/total,
            "misclassification_rate":sum(r[field] != "uncertain" and r[field] != r["expected"] for r in rows)/total,
            "clarification_rate":sum(r[field] == "uncertain" for r in rows)/total, "per_label":per_label}


def percentile(values, percentile):
    values = sorted(values)
    return values[round((len(values)-1)*percentile)] if values else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true",help="Authorize paid Jev calls and embedding requests")
    parser.add_argument("--reuse-jev",type=Path,help="Reuse a saved split report; only rerun the embedding baseline (no Jev charge)")
    parser.add_argument("--split",choices=("calibration","heldout"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.live and not args.reuse_jev: parser.error("--live or --reuse-jev is required")
    load_local_environment()
    router=JevRouter(JevSettings.from_env())
    embedding_client=JinaEmbeddingClient.from_env()
    baseline=SemanticRouter(embedding_client)
    try:
        embedding_client.embed_query("분류 계통 확인")
        baseline_availability="available"
    except Exception as error:
        baseline_availability=type(error).__name__
    cases=json.loads(Path("tests/fixtures/jev_intent_eval.json").read_text())["cases"]
    cases=[c for c in cases if c["split"]==args.split]
    previous=json.loads(args.reuse_jev.read_text()) if args.reuse_jev else None
    previous_rows={r["id"]:r for r in previous["rows"]} if previous else {}
    if previous and (previous["split"] != args.split or set(previous_rows) != {c["id"] for c in cases}):
        parser.error("saved report does not match the requested split")
    def evaluate(case):
        question=case["question"]; rule=deterministic(question)
        legacy=rule or baseline.classify(question) or "uncertain"
        if previous:
            row=previous_rows[case["id"]]
            if row["question"] != question or row["expected"] != case["label"]:
                raise ValueError("saved report question/label mismatch")
            return {**row,"baseline":legacy}
        decision=None if rule else router.classify(question)
        prediction=rule or decision.label or "uncertain"
        entity=extract_name(question,prediction) if not rule else None
        return {"id":case["id"],"question":question,"expected":case["label"],"category":case["category"],
                "baseline":legacy,"jev":prediction,"deterministic":bool(rule),"entity_span":entity,
                "decision":asdict(decision) if decision else None}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(evaluate,cases))
    decisions=[r["decision"] for r in rows if r["decision"]]
    latency=[d["elapsed_ms"] for d in decisions]
    report={"scope":"Real API intent-only evaluation; deterministic routes preserved, no DB/entity resolution score. Single model annotator, not human gold standard.",
            "split":args.split,"model_requested":router.settings.model,"model_echoed":False,
            "thresholds":{"confidence":router.settings.confidence_threshold,"probability":router.settings.probability_threshold,"margin":router.settings.margin_threshold},
            "baseline_embedding_probe":baseline_availability,
            "baseline":metrics(rows,"baseline"),"jev":metrics(rows,"jev"),
            "api":{"calls":len(decisions),"attempts":sum(d["attempts"] for d in decisions),
                   "p50_ms":percentile(latency,.5),"p95_ms":percentile(latency,.95),
                   "input_tokens":sum(d["usage"].get("input_tokens",0) for d in decisions),
                   "output_tokens":sum(d["usage"].get("output_tokens",0) for d in decisions),
                   "credits_used":sum(d["credits_used"] or 0 for d in decisions),
                   "failures":{reason:sum(d["failure"]==reason for d in decisions) for reason in {d["failure"] for d in decisions} if reason}},
            "rows":rows}
    if previous:
        report["jev_reused_from"]=args.reuse_jev.name
        report["new_jev_calls"]=0
        report["previous_baseline"]=previous["baseline"]
        report["previous_baseline_embedding_probe"]=previous.get("baseline_embedding_probe")
        report["model_requested"]=previous["model_requested"]
        report["thresholds"]=previous["thresholds"]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},ensure_ascii=False))


if __name__ == "__main__": main()
