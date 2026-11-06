"""Parser-only evaluation of graph-question gold sets (RG-205). No network, no DB.

Two scores are kept apart:
- raw: the parser's own decision to run (regex: any match; extractor: the gate's answer);
- gated: the parser output as a GraphIntent passed through the execution gate.
``--parser regex`` (default) is the baseline; ``--parser extractor`` is the RG-207 rule extractor.
Explicit intents, filters and the request species_scope are service concerns, validated by root's
mock and real-API checks, not here.
"""
import argparse
import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from robingraph.retrieval.graph_intent_schema import (
    SCHEMA_VERSION, execution_gate, from_graph_question, intent_from_expected, slot_values)
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent
from robingraph.retrieval.graph_questions import parse_graph_question

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / 'data/eval/graph_questions'
CONDITIONS = ('negation', 'residual', 'specific_plant', 'scope', 'unsupported')
SLOTS = ('species', 'rank', 'group', 'diet', 'habitat', 'relation', 'scope', 'specific_plant',
         'negation', 'residual', 'unsupported', 'ambiguity')


def load(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            rows.append((number, json.loads(line)))
    return rows


def normalized(question):
    return re.sub(r'[\s.,!?？~]+', '', question)


def check(rows):
    """(valid records with their gold intent, errors). Records with errors are not scored."""
    valid, errors, ids = [], [], set()
    for number, record in rows:
        try:
            if record.get('id') in ids:
                raise ValueError('duplicate id')
            ids.add(record.get('id'))
            if not isinstance(record.get('question'), str) or not record['question'].strip():
                raise ValueError('question missing')
            if not isinstance(record.get('categories'), list) or not isinstance(record.get('provenance'), dict):
                raise ValueError('categories/provenance missing')
            valid.append((record, intent_from_expected(record['question'], record['expected'])))
        except (ValueError, KeyError, TypeError) as error:
            errors.append({'line': number, 'id': record.get('id'), 'error': str(error)})
    return valid, errors


def _rate(numerator, denominator):
    return {'n': denominator, 'hits': numerator, 'rate': round(numerator / denominator, 4) if denominator else None}


def _percentile(values, fraction):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(fraction * len(ordered)))], 3) if ordered else None


def regex_analyze(question, parse=parse_graph_question):
    """(intent, raw kind, raw executes) for the current regex parser: any match runs today."""
    parsed = parse(question)
    kind = parsed.kind if parsed else None
    return from_graph_question(question, parsed), kind, kind not in (None, 'specific_fruit')


def extractor_analyze(question):
    intent = extract_graph_intent(question)
    return intent, intent.kind, execution_gate(question, intent) == 'answer'


def score(valid, parse=None, analyze=None):
    if analyze is None:
        analyze = (lambda q: regex_analyze(q, parse)) if parse else regex_analyze
    items, latencies = [], []
    if valid:
        analyze(valid[0][0]['question'])  # warm-up: compile and import costs are not per-question
    for record, gold in valid:
        question, expected = record['question'], record['expected']
        started = time.perf_counter()
        intent, raw_kind, raw_executes = analyze(question)
        latencies.append((time.perf_counter() - started) * 1000)
        disposition = execution_gate(question, intent)
        want, got = slot_values(gold), slot_values(intent)
        items.append({
            'id': record['id'], 'question': question, 'categories': record['categories'],
            'expected_kind': gold.kind, 'expected_disposition': expected['disposition'],
            'raw_kind': raw_kind, 'raw_executes': raw_executes,
            'gated_disposition': disposition,
            'slot_ok': {slot: want[slot] == got[slot] for slot in SLOTS},
            'lost_conditions': [c for c in CONDITIONS if want[c] and not got[c]],
        })
    return items, latencies


def metrics(items):
    answer = [i for i in items if i['expected_disposition'] == 'answer']
    hold = [i for i in items if i['expected_disposition'] != 'answer']
    typed = [i for i in items if i['expected_kind'] is not None]
    exact = lambda i: all(i['slot_ok'].values())  # noqa: E731
    # Same definition for both: an execution is right only with the right kind and every slot exact.
    raw_right = lambda i: i['raw_executes'] and i['raw_kind'] == i['expected_kind'] and exact(i)  # noqa: E731
    gated_right = lambda i: i['gated_disposition'] == 'answer' and i['raw_kind'] == i['expected_kind'] and exact(i)  # noqa: E731
    return {
        'n': len(items),
        'raw': {
            'kind_accuracy': _rate(sum(i['raw_kind'] == i['expected_kind'] for i in typed), len(typed)),
            'coverage': _rate(sum(raw_right(i) for i in answer), len(answer)),
            'false_execution': _rate(sum(i['raw_executes'] and not (i in answer and raw_right(i)) for i in items),
                                     len(items)),
            'appropriate_hold': _rate(sum(not i['raw_executes'] for i in hold), len(hold)),
            'condition_loss_executed': sum(bool(i['lost_conditions']) and i['raw_executes'] for i in items),
        },
        'gated': {
            'kind_accuracy': _rate(sum(i['raw_kind'] == i['expected_kind'] for i in typed), len(typed)),
            'slot_accuracy': {slot: _rate(sum(i['slot_ok'][slot] for i in typed), len(typed)) for slot in SLOTS},
            'all_slots_exact': _rate(sum(exact(i) for i in typed), len(typed)),
            'disposition_accuracy': _rate(sum(i['gated_disposition'] == i['expected_disposition'] for i in items),
                                          len(items)),
            'coverage': _rate(sum(gated_right(i) for i in answer), len(answer)),
            'false_execution': _rate(sum(i['gated_disposition'] == 'answer' and not (i in answer and gated_right(i))
                                         for i in items), len(items)),
            'appropriate_hold': _rate(sum(i['gated_disposition'] != 'answer' for i in hold), len(hold)),
            'condition_loss_executed': sum(bool(i['lost_conditions']) and i['gated_disposition'] == 'answer'
                                           for i in items),
        },
    }


def report(items, latencies):
    categories = sorted({c for i in items for c in i['categories']})
    return {'schema_version': SCHEMA_VERSION, 'scope': 'parser-only (no service, filters or request scope)',
            'overall': metrics(items),
            'by_category': {c: metrics([i for i in items if c in i['categories']]) for c in categories},
            'parser_latency_ms': {'p50': _percentile(latencies, 0.5), 'p95': _percentile(latencies, 0.95),
                                  'n': len(latencies)},
            'mismatches': [i for i in items if i['gated_disposition'] != i['expected_disposition']
                           or i['raw_kind'] != i['expected_kind'] or not all(i['slot_ok'].values())]}


def literals(path):
    """Normalized questions from a gold JSONL file or the string literals of a Python test file."""
    if str(path).endswith('.jsonl'):
        return {normalized(r['question']) for _, r in load(path)}
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    return {normalized(n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and len(n.value) >= 8}


def leaks(rows, against):
    seen = set().union(*(literals(p) for p in against)) if against else set()
    return [r['id'] for _, r in rows if normalized(r['question']) in seen]


def manifest(directory):
    path = Path(directory) / 'manifest.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    files = {}
    for name in ('tuning.jsonl', 'holdout.jsonl'):
        source = Path(directory) / name
        if source.exists():
            rows = [r for _, r in load(source)]
            counts = {}
            for row in rows:
                for category in row['categories']:
                    counts[category] = counts.get(category, 0) + 1
            files[name] = {'count': len(rows), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                           'categories': dict(sorted(counts.items())),
                           'review_status': sorted({r['provenance'].get('review_status') for r in rows})}
    data = {**previous, 'schema_version': SCHEMA_VERSION, 'files': files}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--gold', type=Path, default=GOLD_DIR / 'tuning.jsonl')
    parser.add_argument('--parser', choices=('regex', 'extractor'), default='regex')
    parser.add_argument('--leak-against', type=Path, nargs='*', default=(),
                        help='JSONL gold files or Python test files whose questions must not reappear')
    parser.add_argument('--json', type=Path, help='write the full report here')
    parser.add_argument('--write-manifest', type=Path, metavar='DIR', help='recompute counts/sha256 in DIR')
    args = parser.parse_args(argv)
    if args.write_manifest:
        print(json.dumps(manifest(args.write_manifest), ensure_ascii=False, indent=2))
        return 0
    rows = load(args.gold)
    valid, errors = check(rows)
    leaked = leaks(rows, args.leak_against)
    items, latencies = score(valid, analyze=extractor_analyze if args.parser == 'extractor' else regex_analyze)
    result = {'gold': str(args.gold), 'parser': args.parser, 'records': len(rows), 'invalid': errors, 'leaked_ids': leaked,
              **report(items, latencies)}
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    overall = result['overall']
    print(f"records={len(rows)} valid={len(valid)} invalid={len(errors)} leaked={len(leaked)}")
    for mode in ('raw', 'gated'):
        print(mode, json.dumps({k: (v['rate'], f"{v['hits']}/{v['n']}") if isinstance(v, dict) and 'rate' in v else v
                                for k, v in overall[mode].items() if k != 'slot_accuracy'}, ensure_ascii=False))
    print('parser_latency_ms', result['parser_latency_ms'])
    for error in errors:
        print('INVALID', error)
    for item in result['mismatches']:
        print('MISS', item['id'], item['expected_kind'], '->', item['raw_kind'], item['expected_disposition'],
              '->', item['gated_disposition'], [s for s, ok in item['slot_ok'].items() if not ok], item['question'])
    return 1 if errors or leaked else 0  # invalid or leaked gold is a reproduction failure


if __name__ == '__main__':
    sys.exit(main())
