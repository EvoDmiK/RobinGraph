"""Opt-in actual TEST graph/Jina checks. Run from repo root with a running API."""
import json
import os
import time
import urllib.request

BASE = os.environ.get('ENTITY_QA_BASE', 'http://127.0.0.1:8001')


def ask(question):
    body = {'question': question, 'defer_enrichment': True, 'defer_discovery': True}
    request = urllib.request.Request(BASE + '/v1/chat', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)
    records.append({'question': question, 'elapsed_seconds': round(time.monotonic()-started, 3),
                    'disposition': data['disposition'], 'resolution': data.get('entity_resolution'),
                    'taxon': (data['result'].get('profile') or {}).get('taxon'),
                    'topic': (data['result'].get('question_answer') or {}).get('topic')})
    return data


records = []
with urllib.request.urlopen(BASE + '/health', timeout=10) as response:
    assert json.load(response)['deployment_target'] == 'test'

for question, method in [('흰뺨검둥오리에 대해 알고 싶어', 'graph_exact'),
                         ('흰뺨 검둥 오리에 대해 알고 싶어', 'graph_normalized')]:
    data = ask(question)
    assert data['disposition'] == 'answer', records[-1]
    assert data['entity_resolution']['method'] == method
    assert data['result']['profile']['taxon']['scientific_name'] == 'Anas zonorhyncha'

for question in ['흰뺨검둥오려에 대해 알고 싶어', '흰뺨검둥오려는 뭘 먹어?']:
    data = ask(question)
    assert data['disposition'] == 'clarify' and data['result']['kind'] == 'clarify', records[-1]
    resolution = data['entity_resolution']
    assert resolution['method'] == 'vector' and resolution['taxon_id'] is None
    candidate = next(c for c in resolution['candidates'] if c['scientific_name'] == 'Anas zonorhyncha')
    confirmed = ask(candidate['question'])
    assert confirmed['result']['profile']['taxon']['taxon_id'] == candidate['taxon_id']
    if '먹어' in question:
        assert confirmed['result']['question_answer']['topic'] == 'diet'

data = ask('우주선에 대해 알고 싶어')
assert data['disposition'] == 'abstain' and not data['entity_resolution']['candidates']
assert data['result'].get('profile') is None
data = ask('까치에 대해 알려줘')
assert data['result']['profile']['taxon']['scientific_name'] == 'Pica serica'

print(json.dumps({'passed': True, 'mode': 'actual TEST graph and Jina, no route mocks',
                  'records': records}, ensure_ascii=False, indent=2))
