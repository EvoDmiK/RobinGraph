"""Run via docker exec -i robingraph-api-test python - < this file on NAS."""
import json
from types import SimpleNamespace
import urllib.request
import urllib.parse

from robingraph.retrieval.evaluation import SearchQuestion, evaluate_search


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8000' + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw


checks = []
health = request('/health')
assert health['deployment_target'] == 'test' and health['status'] == 'ok'
checks.append('health_test_ok')
assert b'<html' in request('/chat').lower()
checks.append('chat_html')
name = urllib.parse.quote('청둥오리')
lineage = request('/v1/taxa/lineage?name=' + name)
assert any(item['scientific_name'] == 'Anas platyrhynchos' for item in lineage['lineage'])
checks.append('live_korean_lineage')
assert request('/v1/taxa/profile?name=' + name)
checks.append('live_profile')
chat = request('/v1/chat', {'question': '청둥오리에 대해 알려줘'})
assert chat['disposition'] == 'answer' and chat['result']['kind'] == 'profile'
checks.append('live_chat_profile')
searches = {}
for mode in ('fulltext', 'hybrid'):
    response = request('/v1/search', {'question': 'fixture 호수', 'mode': mode, 'limit': 5})
    assert response['mode'] == mode and response['results']
    assert all('fixture-chunk-review' not in item['chunk_id'] for item in response['results'])
    searches[mode] = {'returned': len(response['results']), 'actual_mode': response['mode'],
                      'channels': sorted({c for item in response['results'] for c in item['channels']})}
    checks.append('live_search_' + mode)

def outcome(*ids):
    return SimpleNamespace(results=[SimpleNamespace(chunk_id=chunk_id) for chunk_id in ids])

mixed = (SearchQuestion('hit', 'hit', ('a',)), SearchQuestion('miss', 'miss', ('b',)))
report = evaluate_search(mixed, lambda q, limit: outcome('a') if q == 'hit' else outcome(), limit=5)
assert report.mean_reciprocal_rank == .5
checks.append('deployed_mrr_mixed_hit_miss')
assert evaluate_search(mixed, lambda q, limit: outcome(), limit=5).mean_reciprocal_rank == 0
checks.append('deployed_mrr_all_miss')
assert evaluate_search((SearchQuestion('empty', 'empty', ()),),
                       lambda q, limit: outcome(), limit=5).mean_reciprocal_rank is None
checks.append('deployed_mrr_no_answerable_questions')
print(json.dumps({'passed': True, 'checks': checks, 'count': len(checks), 'health': health,
                  'searches': searches, 'mrr_selfchecks': 'synthetic inputs against deployed evaluator'},
                 ensure_ascii=False, indent=2))
