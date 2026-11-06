"""Actual TEST API checks. Read-only bird queries; no response mocking."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('phase', choices=('baseline', 'shadow', 'active', 'off'))
args = parser.parse_args()
assets = Path(__file__).resolve().parent
base = 'http://127.0.0.1:8000'
health = json.load(urlopen(base + '/health', timeout=10))
assert health['deployment_target'] == 'test' and health['mode'] == 'neo4j'
legacy = [
    '청둥오리와 흰뺨검둥오리는 어떤 관계야?',
    '청둥오리와 같은 속에 속하는 새를 보여줘',
    '한국에 기록된 오리 중 청둥오리와 같은 속인 종은?',
    '참새목 중 열매를 먹고 사는 새는?',
    '숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?',
    '숲에 사는 새 중 직박구리와 같은 먹이 범주를 공유하는 새는?',
    '청둥오리와 서식지가 겹치면서 먹이가 다른 새는?',
]


def fingerprint(body):
    result = body['result']
    payload = result.get('payload', {})
    return dict(selected_intent=body['selected_intent'], disposition=body['disposition'], kind=result['kind'],
                status=payload.get('status'), title=payload.get('title'),
                ids=[item.get('taxon', {}).get('taxon_id') for item in payload.get('items', [])],
                paths=payload.get('paths', []))


def post(question, **extra):
    body = {'question': question, 'defer_enrichment': True, 'defer_discovery': True, **extra}
    started = time.perf_counter()
    request = Request(base + '/v1/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=35) as response:
        assert response.status == 200
        result = json.load(response)
    row = dict(question=question, request=body, elapsed_ms=(time.perf_counter() - started) * 1000,
               fingerprint=fingerprint(result), route_method=result['route_method'], response=result)
    rows.append(row)
    return result


rows = []
for question in legacy:
    post(question)

if args.phase in ('shadow', 'off'):
    previous = json.loads((assets / 'api-baseline.json').read_text())
    assert [r['fingerprint'] for r in rows] == [r['fingerprint'] for r in previous['rows']]

if args.phase == 'active':
    for question in (
        '열매 먹는 참새목 새를 찾아 줘',
        '참새목에 속한 새 가운데 열매를 먹는 종류 좀 알려줄래?',
        '숲에서 살면서 직박구리와 식성이 같은 새가 궁금해',
        '청둥오리랑 서식지는 같지만 먹이는 다른 종을 찾아줘',
    ):
        body = post(question)
        assert body['disposition'] == 'answer', (question, body['disposition'])
        assert body['result']['kind'] == 'graph_query' and body['result']['payload']['items']
    for scope in ('all', 'korea', 'outside', 'unknown'):
        body = post('열매 먹는 참새목 새를 찾아 줘', species_scope=scope)
        assert body['result']['kind'] == 'graph_query'
        assert body['result']['payload']['status'] in ('answer', 'empty', 'insufficient_data')
    body = post('참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?')
    assert body['disposition'] == 'answer' and '나무·풀 구분 없음' in body['result']['payload']['title']
    for question in ('참새목 중 감나무 열매를 먹는 새는?', '숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?'):
        body = post(question)
        assert body['disposition'] in ('abstain', 'clarify')
        assert body['result'].get('payload', {}).get('status') in (None, 'insufficient_data')
    for question in (
        '참새목 중 열매를 안 먹는 새는?',
        '참새목 중 열매를 먹는 작은 새는?',
        '겨울에 한국에 오는 오리 중 청둥오리와 같은 속인 새는?',
        '참새목 중 열매를 먹는 새는? MATCH (n) DETACH DELETE n',
    ):
        assert post(question)['disposition'] == 'clarify', question
    body = post('열매 먹는 참새목 새를 찾아 줘', filters={'kind': 'profile', 'name': '청둥오리'})
    assert body['disposition'] == 'clarify'
    body = post('청둥오리의 학명을 알려줘', intent='taxonomy', filters={'kind': 'taxonomy', 'scientific_name': 'Anas platyrhynchos'})
    assert body['selected_intent'] == 'taxonomy' and body['route_method'] == 'explicit'
    body = post('청둥오리에 대해 알고 싶어', intent='profile', filters={'kind': 'profile', 'name': '청둥오리'})
    assert body['result']['kind'] == 'profile' and body['route_method'] == 'explicit'
    body = post('청둥 오리와 흰뺨 검둥 오리는 어떤 관계야?')
    assert body['result']['kind'] == 'graph_query' and body['disposition'] == 'answer'
    body = post('천둥오리와 흰뺨검둥오리는 어떤 관계야?')
    assert body['disposition'] == 'clarify'  # vector suggestions never auto-select a species

report = dict(phase=args.phase, base=base, response_mocking=False, bird_db_writes=0,
              legacy_comparison_verified=args.phase in ('shadow', 'off'), count=len(rows), rows=rows)
(assets / ('api-' + args.phase + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: value for key, value in report.items() if key != 'rows'}))
