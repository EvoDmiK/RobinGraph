#!/usr/bin/env python3
"""Compare two isolated fixture runtimes, without following redirects or writing DBs.

Run: python scripts/check_ui_migration_contract.py BASELINE_URL CANDIDATE_URL
Both runtimes must use identical fixture data/configuration. This sends read-only
lookup/chat requests; do not point it at live DB-backed runtimes. Runtime setup
belongs to the caller. JSON is compared in full, including errors and nulls.
"""
import argparse
import http.client
import json
from urllib.parse import quote, urlencode, urlsplit


TAXA = ('profile', 'related', 'similar', 'ecological-related', 'subspecies', 'name-relations')
STATIC = {
    '/': 'text/html', '/chat': 'text/html', '/birds': 'text/html',
    '/static/index.html': 'text/html', '/static/birds.html': 'text/html',
    '/static/chat.js': 'application/javascript', '/static/birds.js': 'application/javascript',
    '/static/styles.css': 'text/css',
}


def cases():
    yield 'GET', '/health', None
    for path in STATIC:
        yield 'GET', path, None
    for path in ('/favicon.ico', '/static/favicon-32.png', '/static/favicon-192.png', '/static/apple-touch-icon.png'):
        yield 'GET', path, None
    for path in ('/static/missing.js', '/static/%2e%2e/app.py', '/static/..%2fapp.py', '/static/%2fetc%2fpasswd'):
        yield 'GET', path, None
    for endpoint in TAXA:
        for scope in ('all', 'korea', 'outside', 'unknown'):
            yield 'GET', '/v1/taxa/' + endpoint + '?' + urlencode({'name': 'Turdus merula', 'species_scope': scope}), None
        for query in ('', '?name=', '?name=' + quote(' '), '?name=DefinitelyUnknownBird', '?name=Turdus%20merula&species_scope=invalid'):
            yield 'GET', '/v1/taxa/' + endpoint + query, None
    for scope in ('all', 'korea', 'outside', 'unknown'):
        for intent in ('auto', 'profile', 'taxonomy', 'observations', 'evidence'):
            payload = {'question': 'Turdus merula에 대해 알려줘', 'intent': intent, 'defer_discovery': True}
            if scope != 'all':
                payload['species_scope'] = scope
            if intent != 'auto':
                payload['filters'] = {'kind': intent}
                if intent == 'profile':
                    payload['filters']['name'] = 'Turdus merula'
                if intent == 'taxonomy':
                    payload['filters']['scientific_name'] = 'Turdus merula'
                if intent in ('observations', 'evidence'):
                    payload['filters']['limit'] = 10
            yield 'POST', '/v1/chat', payload
    for payload in ({}, {'question': ''}, {'question': 'bird', 'species_scope': 'invalid'}, {'question': 'bird', 'intent': 'profile', 'filters': {'kind': 'evidence'}}):
        yield 'POST', '/v1/chat', payload


def request(base, method, path, payload):
    url = urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.hostname or url.path not in ('', '/') or url.query or url.fragment or url.username:
        raise ValueError('Use an http(s) origin without credentials, path, query or fragment')
    connection = (http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection)(url.hostname, url.port, timeout=90)
    try:
        connection.request(method, path, body=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'} if payload is not None else {})
        response = connection.getresponse()
        return response.status, {key.lower(): value for key, value in response.getheaders()}, response.read()
    finally:
        connection.close()


def compare(path, left, right):
    problems = []
    status, headers, body = right
    if status != left[0]:
        problems.append(f'status {left[0]} -> {status}')
    for key in ('content-type', 'cache-control', 'location'):
        if left[1].get(key) != headers.get(key):
            problems.append(key + ' differs')
    if 300 <= status < 400:
        problems.append('unexpected redirect')
    if path in STATIC:
        if status != 200 or not body:
            problems.append('UI asset unavailable')
        if headers.get('content-type', '').split(';')[0] != STATIC[path]:
            problems.append('wrong static MIME')
        if headers.get('cache-control') != 'no-cache, must-revalidate':
            problems.append('wrong UI cache policy')
        if body != left[2]:
            problems.append('UI asset bytes differ')
    elif path.startswith('/static/') and any(token in path for token in ('%2e', '%2f', 'missing.js')):
        if status != 404:
            problems.append('unlisted/traversal asset must return 404')
    if 'json' in left[1].get('content-type', ''):
        try:
            if json.loads(left[2]) != json.loads(body):
                problems.append('JSON contract differs')
        except (ValueError, UnicodeError):
            problems.append('invalid JSON')
    return problems


def self_test():
    response = (200, {'content-type': 'application/json'}, b'{"items":[],"nullable":null}')
    assert compare('/v1/taxa/profile', response, response) == []
    assert 'JSON contract differs' in compare('/v1/taxa/profile', response, (200, response[1], b'{"items":[]}'))
    assert 'unexpected redirect' in compare('/v1/chat', response, (301, {'location': '/v1/chat/'}, b''))
    assert 'unlisted/traversal asset must return 404' in compare('/static/%2e%2e/app.py', response, response)
    requests = list(cases())
    assert {payload['intent'] for method, _, payload in requests if method == 'POST' and payload and 'intent' in payload} >= {'auto', 'profile', 'taxonomy', 'observations', 'evidence'}
    print('self-test: passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', nargs='?')
    parser.add_argument('candidate', nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.baseline or not args.candidate:
        parser.error('provide baseline and candidate fixture origins')
    for base in (args.baseline, args.candidate):
        health = request(base, 'GET', '/health', None)
        if health[0] != 200 or json.loads(health[2]).get('mode') != 'fixture':
            parser.error('both origins must report mode=fixture before any chat requests')
    rows = []
    for method, path, payload in cases():
        try:
            left = request(args.baseline, method, path, payload)
            right = request(args.candidate, method, path, payload)
            problems = compare(path, left, right)
        except Exception as error:
            problems = [type(error).__name__ + ': ' + str(error)]
        rows.append({'method': method, 'path': path, 'payload': payload, 'problems': problems})
    print(json.dumps({'passed': all(not row['problems'] for row in rows), 'cases': rows}, ensure_ascii=False, indent=2))
    return int(any(row['problems'] for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
