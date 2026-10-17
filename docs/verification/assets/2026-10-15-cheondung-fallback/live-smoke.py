"""Opt-in actual TEST graph/Jina regression for 천둥오리, no route mocks."""
import json
import os
import time
import urllib.request

base = os.environ.get('ENTITY_QA_BASE', 'http://127.0.0.1:8001')
records = []


def ask(question):
    request = urllib.request.Request(base + '/v1/chat', data=json.dumps({
        'question': question, 'defer_enrichment': True, 'defer_discovery': True,
    }).encode(), headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)
    records.append({'question': question, 'seconds': round(time.monotonic() - started, 3),
                    'disposition': data['disposition'], 'resolution': data.get('entity_resolution'),
                    'taxon': (data['result'].get('profile') or {}).get('taxon'),
                    'topic': (data['result'].get('question_answer') or {}).get('topic')})
    return data


with urllib.request.urlopen(base + '/health', timeout=10) as response:
    assert json.load(response)['deployment_target'] == 'test'
for question in ['천둥오리에 대해 알려줘', '천둥 오리에 대해 알려줘', '천둥오리는 뭘 먹어?']:
    data = ask(question)
    resolution = data['entity_resolution']
    assert data['disposition'] == 'clarify' and resolution['method'] == 'vector', records[-1]
    assert resolution['taxon_id'] is None and data['result'].get('profile') is None
    assert [c['scientific_name'] for c in resolution['candidates']] == ['Anas platyrhynchos']
    candidate = resolution['candidates'][0]
    confirmed = ask(candidate['question'])
    assert confirmed['disposition'] == 'answer', records[-1]
    assert confirmed['result']['profile']['taxon']['taxon_id'] == candidate['taxon_id']
    assert confirmed['entity_resolution']['method'] == 'graph_exact'
    if '먹어' in question:
        assert confirmed['result']['question_answer']['topic'] == 'diet'
for question in ['천둥에 대해 알려줘', '우주선에 대해 알려줘', '아무새에 대해 알려줘', '아무오리에 대해 알려줘']:
    data = ask(question)
    assert data['disposition'] == 'abstain' and not data['entity_resolution']['candidates'], records[-1]
data = ask('청둥오리에 대해 알려줘')
assert data['disposition'] == 'answer' and data['entity_resolution']['method'] == 'graph_exact'
data = ask('청둥오려에 대해 알려줘')
assert data['disposition'] == 'clarify'
assert data['entity_resolution']['candidates'][0]['scientific_name'] == 'Anas platyrhynchos'
print(json.dumps({'passed': True, 'mode': 'actual TEST graph/Jina/HTTP; no route mocks',
                  'records': records}, ensure_ascii=False, indent=2))
