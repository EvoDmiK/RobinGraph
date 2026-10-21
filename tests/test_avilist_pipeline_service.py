"""n8n stage service tests.

All cases use a fake runner and temporary directories: they check routing,
auth, gating, concurrency and error mapping, not real AviList data, network,
PostgreSQL or Neo4j. RealRunnerInterfaceTest only imports the real runner.
"""
import asyncio
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(ROOT / 'tests') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tests'))

from asgi_client import TestClient  # noqa: E402

from robingraph.ingest.avilist_pipeline import ApprovalError, SourceVerificationError  # noqa: E402
from scripts import serve_avilist_pipeline as service  # noqa: E402

TOKEN = 't' * 40
AUTH = {'Authorization': 'Bearer ' + TOKEN}
SECRET = 'leak-me /private/path NEO4J_PASSWORD=hunter2'
NEO4J_ENV = {'NEO4J_URI': 'bolt://192.168.219.98:7687', 'NEO4J_USERNAME': 'neo4j',
             'NEO4J_PASSWORD': 'x', 'NEO4J_DATABASE': 'neo4j'}


class FakeRunner:
    def __init__(self):
        self.source = b'source-v1'
        self.calls = []
        self.prepare_error = None
        self.review_error = None
        self.verify_error = None
        self.verify_gate = None
        self.lock_error = None
        self.applied = set()

    def test_settings(self):
        self.calls.append('test_settings')
        return 'settings'

    def digest(self, value):
        return 'sha-' + json.dumps(value, sort_keys=True)

    def prepare(self, source_path, output):
        self.calls.append(('prepare', source_path))
        output.mkdir(parents=True, exist_ok=False)
        (output / 'source.json').write_bytes(self.source)
        if self.prepare_error:
            raise self.prepare_error
        (output / 'manifest.json').write_bytes(b'{"m":"' + self.source + b'"}')
        (output / 'bundle.json').write_bytes(b'{}')
        return {'status': 'review_required', 'manifest_sha256': 'm-' + self.source.decode(), 'counts': {'n': 1}}

    def load_review(self, package, approval_path):
        self.calls.append('load_review')
        if self.review_error:
            raise self.review_error
        manifest = json.loads((package / 'manifest.json').read_bytes())
        return manifest, {'b': 1}, json.loads(approval_path.read_bytes())

    def verify_runtime(self, bundle):
        self.calls.append('verify_runtime')
        if self.verify_gate:
            self.verify_gate()
        if self.verify_error:
            raise self.verify_error
        return {'search_regression': [{}, {}, {}, {}], 'projection_performed': False}

    @contextmanager
    def locked_store(self, settings):
        self.calls.append('locked_store')
        if self.lock_error:
            raise self.lock_error
        yield 'store'

    def store_bundle(self, store, manifest, bundle, approval, verification):
        self.calls.append('store_bundle')
        key = self.digest(manifest)
        status = 'already_applied' if key in self.applied else 'applied'
        self.applied.add(key)
        return {'status': status, 'release_id': 'rel-' + key, 'run_id': 'run-1'}


class ServiceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / 'work'
        self.root.mkdir()
        self.approval = base / 'approval.json'
        self.env = {service.TOKEN_ENV: TOKEN, service.ROOT_ENV: str(self.root),
                    service.APPROVAL_ENV: str(self.approval)}
        patcher = mock.patch.dict(os.environ, NEO4J_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.runner = FakeRunner()
        self.runner_file = base / 'runner.py'
        self.runner_file.write_text('# runner v1')
        self.runner.__file__ = str(self.runner_file)

    def client(self, **env):
        return TestClient(service.create_app({**self.env, **env}, self.runner))

    def post(self, client, path, body=b'{}', headers=None):
        return client.post(path, content=body,
                           headers={'Content-Type': 'application/json', **(AUTH if headers is None else headers)})

    def approve(self):
        self.approval.write_text('{"decision":"approved"}')

    def package_ready(self, client):
        response = self.post(client, '/prepare')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 'review_required')


class StartupTest(ServiceCase):
    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):
            self.client(**{service.TOKEN_ENV: 'x' * 31})

    def test_paths_required_absolute_and_separate(self):
        for override in ({service.ROOT_ENV: ''}, {service.APPROVAL_ENV: 'relative.json'},
                         {service.APPROVAL_ENV: str(self.root / 'approval.json')},
                         {service.ROOT_ENV: str(self.root / 'missing')}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.client(**override)

    def test_test_settings_enforced_before_serving(self):
        self.runner.test_settings = mock.Mock(side_effect=ValueError('TEST target required'))
        with self.assertRaises(ValueError):
            self.client()

    def test_neo4j_outside_allowlist_rejected(self):
        with mock.patch.dict(os.environ, {'NEO4J_URI': 'bolt://prod.example:7687'}), self.assertRaises(ValueError):
            self.client()

    def test_stale_partial_prepare_dir_removed(self):
        stale = self.root / (service.PREPARE_PREFIX + 'old')
        (stale / 'review-package').mkdir(parents=True)
        self.client()
        self.assertFalse(stale.exists())


class AuthAndBodyTest(ServiceCase):
    def test_health_is_public_and_minimal(self):
        response = self.client().get('/health')
        self.assertEqual(response.json(), {'status': 'ok', 'deployment_target': 'test', 'projection_performed': False})

    def test_missing_or_wrong_token_rejected(self):
        client = self.client()
        for headers in ({}, {'Authorization': TOKEN}, {'Authorization': 'Bearer ' + TOKEN[:-1] + 'x'},
                        {'Authorization': 'Bearer 한글토큰'.encode()}):
            for path in ('/prepare', '/verify', '/apply'):
                with self.subTest(headers=headers, path=path):
                    response = self.post(client, path, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertNotIn(TOKEN, response.text)
        self.assertEqual(self.runner.calls, ['test_settings'])

    def test_only_exact_empty_json_object_accepted(self):
        client = self.client()
        for body in (b'', b'[]', b'null', b'{"source": "/etc/passwd"}', b'{"approval": {"decision": "approved"}}',
                     b'{"env": "production"}', b'{', b'{}' + b' ' * 100):
            with self.subTest(body=body):
                self.assertIn(self.post(client, '/apply', body=body).status_code, (400, 413))
        response = client.post('/apply', content=b'{}', headers={**AUTH, 'Content-Type': 'text/plain'})
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.runner.calls, ['test_settings'])
        self.assertFalse(self.approval.exists())

    def test_unknown_route_and_method(self):
        client = self.client()
        self.assertEqual(client.get('/prepare', headers=AUTH).status_code, 405)
        self.assertEqual(self.post(client, '/run').status_code, 404)
        self.assertEqual(client.get('/docs').status_code, 404)


class DjangoTransportTest(ServiceCase):
    def test_trailing_slash_redirect_and_method_contract(self):
        client = self.client()
        for route in ('health', 'prepare', 'verify', 'apply'):
            response = client.get('/' + route + '/?q=1', follow_redirects=False)
            self.assertEqual(307, response.status_code)
            self.assertEqual('http://testserver/' + route + '?q=1', response.headers['location'])
        for method, path in (('POST', '/health'), ('HEAD', '/health'), ('OPTIONS', '/prepare')):
            self.assertEqual(405, client.request(method, path).status_code)

    def test_public_api_routes_are_not_exposed_by_runner(self):
        from robingraph.api.drf import create_django_app
        runner, public = self.client(), TestClient(create_django_app())
        for path in ('/v1/chat', '/openapi.json', '/docs', '/chat'):
            self.assertEqual(404, runner.get(path).status_code)
        self.assertEqual(404, public.post('/prepare').status_code)
        self.assertNotIn('mode', runner.get('/health').json())
        self.assertEqual('fixture', public.get('/health').json()['mode'])

    def test_untrusted_host_is_rejected_without_echo(self):
        client = self.client()
        for path in ('/health', '/health/', '/missing', '/apply'):
            response = client.get(path, headers={'host': 'untrusted.invalid'}, follow_redirects=False)
            self.assertEqual(400, response.status_code)
            self.assertEqual({'status': 'failed', 'error': 'rejected'}, response.json())
            self.assertNotIn('untrusted.invalid', response.text)

    def raw_request(self, chunks, *, authorization=True, content_length=None):
        app = service.create_app(self.env, self.runner)
        headers = [(b'host', b'testserver'), (b'content-type', b'application/json')]
        if authorization:
            headers.append((b'authorization', ('Bearer ' + TOKEN).encode()))
        if content_length is not None:
            headers.append((b'content-length', content_length.encode()))
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                 'method': 'POST', 'scheme': 'http', 'path': '/verify', 'raw_path': b'/verify',
                 'query_string': b'', 'root_path': '', 'headers': headers,
                 'server': ('testserver', 80), 'client': ('127.0.0.1', 1)}
        seen, sent = [], []

        async def invoke():
            async def receive():
                index = len(seen)
                if index >= len(chunks):
                    await asyncio.Event().wait()
                seen.append(index)
                return {'type': 'http.request', 'body': chunks[index], 'more_body': index < len(chunks) - 1}

            async def send(message):
                sent.append(message)
            await app(scope, receive, send)
        asyncio.run(invoke())
        status = next(m['status'] for m in sent if m['type'] == 'http.response.start')
        payload = json.loads(b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body'))
        return status, payload, len(seen)

    def test_actual_body_bytes_are_bounded_before_django_spooling(self):
        for declared in (None, '0', '2', '999999'):
            with self.subTest(content_length=declared):
                status, payload, received = self.raw_request([b'{}' + b' ' * 62, b' ', b'x' * 4096],
                                                             content_length=declared)
                self.assertEqual((413, 'body_too_large', 2), (status, payload['error'], received))
                self.assertNotIn('load_review', self.runner.calls)
                self.assertNotIn('store_bundle', self.runner.calls)
        status, payload, received = self.raw_request([b'{}', b' ' * 62])
        self.assertEqual((409, 'package_missing', 2), (status, payload['error'], received))

    def test_unauthorized_stream_is_not_read(self):
        status, payload, received = self.raw_request([b'x' * 4096] * 3, authorization=False)
        self.assertEqual((401, 'unauthorized', 0), (status, payload['error'], received))
        self.assertEqual(['test_settings'], self.runner.calls)

    def test_old_transport_binding_is_rejected(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        path = self.root / service.PACKAGE / service.CODE_FILE
        previous = json.loads(path.read_bytes())
        previous.pop('django_asgi')
        path.write_text(json.dumps(previous))
        for route in ('/prepare', '/verify', '/apply'):
            response = self.post(client, route)
            self.assertEqual((409, 'code_changed'), (response.status_code, response.json()['error']))
        self.assertNotIn('store_bundle', self.runner.calls)

    def test_django_transport_code_change_requires_review(self):
        from robingraph.api.drf import application
        code = Path(self.tmp.name) / 'django_asgi.py'
        code.write_text('# transport v1')
        with mock.patch.object(application, '__file__', str(code)):
            client = self.client()
            self.package_ready(client)
            self.approve()
            code.write_text('# transport v2')
            response = self.post(client, '/verify')
            self.assertEqual((409, 'code_changed'), (response.status_code, response.json()['error']))
            self.assertNotIn('store_bundle', self.runner.calls)


class PrepareTest(ServiceCase):
    def test_new_package_installed_then_requires_review(self):
        client = self.client()
        response = self.post(client, '/prepare')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['manifest_sha256'], 'm-source-v1')
        self.assertIn(('prepare', None), self.runner.calls)
        self.assertEqual((self.root / 'review-package/source.json').read_bytes(), b'source-v1')
        self.assertEqual(list(self.root.glob(service.PREPARE_PREFIX + '*')), [])

    def test_identical_rerun_reuses_existing_package(self):
        client = self.client()
        self.package_ready(client)
        response = self.post(client, '/prepare')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'prepared')
        self.assertTrue(response.json()['reused'])

    def test_different_result_stops_and_keeps_reviewed_package(self):
        client = self.client()
        self.package_ready(client)
        self.runner.source = b'source-v2'
        response = self.post(client, '/prepare')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 'review_required')
        self.assertEqual((self.root / 'review-package/source.json').read_bytes(), b'source-v1')
        self.assertEqual((self.root / 'candidates/m-source-v2/source.json').read_bytes(), b'source-v2')

    def test_failure_cleans_partial_dir_and_hides_message(self):
        client = self.client()
        self.runner.prepare_error = SourceVerificationError(SECRET)
        with self.assertLogs('robingraph.avilist_pipeline_service', 'WARNING') as logs:
            response = self.post(client, '/prepare')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'source_verification_failed')
        self.assertNotIn(SECRET, response.text + ''.join(logs.output))
        self.assertFalse((self.root / 'review-package').exists())
        self.assertEqual(list(self.root.glob(service.PREPARE_PREFIX + '*')), [])

    def test_network_failure_is_5xx(self):
        self.runner.prepare_error = OSError(SECRET)
        response = self.post(self.client(), '/prepare')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(SECRET, response.text)


class VerifyAndApplyTest(ServiceCase):
    def test_apply_without_approval_blocked(self):
        client = self.client()
        self.assertEqual(self.post(client, '/apply').json()['error'], 'package_missing')
        self.package_ready(client)
        for path in ('/verify', '/apply'):
            response = self.post(client, path)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['error'], 'approval_missing')
        self.assertNotIn('store_bundle', self.runner.calls)
        self.assertNotIn('locked_store', self.runner.calls)

    def test_rejected_approval_blocks_apply(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        self.runner.review_error = ApprovalError(SECRET)
        response = self.post(client, '/apply')
        self.assertEqual((response.status_code, response.json()['error']), (409, 'approval_rejected'))
        self.assertNotIn(SECRET, response.text)
        self.assertNotIn('verify_runtime', self.runner.calls)
        self.assertNotIn('store_bundle', self.runner.calls)

    def test_verify_returns_manifest_digest(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        response = self.post(client, '/verify')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'verified')
        self.assertEqual(body['manifest_sha256'], self.runner.digest({'m': 'source-v1'}))
        self.assertEqual(body['search_regression_passed'], 4)
        self.assertNotIn('store_bundle', self.runner.calls)

    def test_runtime_gate_failure_blocks_apply(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        self.runner.verify_error = ValueError(SECRET)
        response = self.post(client, '/apply')
        self.assertEqual((response.status_code, response.json()['error']), (409, 'gate_failed'))
        self.assertNotIn('locked_store', self.runner.calls)
        self.runner.verify_error = KeyError(SECRET)
        response = self.post(client, '/apply')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(SECRET, response.text)

    def test_apply_rechecks_and_rerun_is_idempotent(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        self.runner.calls.clear()
        first = self.post(client, '/apply')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['status'], 'applied')
        self.assertEqual(self.runner.calls,
                         ['test_settings', 'load_review', 'verify_runtime', 'locked_store', 'store_bundle'])
        second = self.post(client, '/apply')
        self.assertEqual(second.json()['status'], 'already_applied')
        self.assertEqual(second.json()['release_id'], first.json()['release_id'])

    def test_db_advisory_lock_busy_is_409(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        self.runner.lock_error = RuntimeError('Another pilot execution is running; retry later')
        response = self.post(client, '/apply')
        self.assertEqual((response.status_code, response.json()['error']), (409, 'busy'))
        self.assertNotIn('store_bundle', self.runner.calls)

    def test_concurrent_call_rejected_while_stage_runs(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        entered, release = threading.Event(), threading.Event()

        def gate():
            entered.set()
            release.wait(5)
        self.runner.verify_gate = gate
        results = {}
        worker = threading.Thread(target=lambda: results.update(first=self.post(client, '/apply')))
        worker.start()
        self.assertTrue(entered.wait(5))
        for path in ('/prepare', '/verify', '/apply'):
            response = self.post(client, path)
            self.assertEqual((response.status_code, response.json()['error']), (409, 'busy'))
        release.set()
        worker.join(5)
        self.assertEqual(results['first'].status_code, 200)
        self.assertEqual(self.runner.calls.count('store_bundle'), 1)
        self.runner.verify_gate = None
        self.assertEqual(self.post(client, '/verify').status_code, 200)


class CodeBindingAndContractTest(ServiceCase):
    def test_runner_code_change_blocks_later_stages(self):
        client = self.client()
        self.package_ready(client)
        self.approve()
        self.assertEqual(self.post(client, '/verify').status_code, 200)
        self.runner_file.write_text('# runner v2')
        for path in ('/prepare', '/verify', '/apply'):
            response = self.post(client, path)
            self.assertEqual((response.status_code, response.json()['error']), (409, 'code_changed'), path)
        self.assertNotIn('store_bundle', self.runner.calls)

    def test_out_of_band_package_bound_by_identical_prepare(self):
        client = self.client()
        self.package_ready(client)
        (self.root / 'review-package' / service.CODE_FILE).unlink()
        self.approve()
        response = self.post(client, '/apply')
        self.assertEqual((response.status_code, response.json()['error']), (409, 'code_unbound'))
        self.assertNotIn('store_bundle', self.runner.calls)
        self.assertEqual(self.post(client, '/prepare').status_code, 200)
        self.assertEqual(self.post(client, '/apply').status_code, 200)

    def test_every_stage_response_has_manifest_and_projection_fields(self):
        client = self.client()
        responses = [self.post(client, '/verify'), self.post(client, '/prepare'), self.post(client, '/verify')]
        self.approve()
        responses += [self.post(client, '/verify'), self.post(client, '/apply'), self.post(client, '/prepare'),
                      self.post(client, '/apply', headers={})]
        expected = self.runner.digest({'m': 'source-v1'})
        for response in responses:
            body = response.json()
            self.assertIs(body['projection_performed'], False)
            self.assertIn('manifest_sha256', body)
        self.assertEqual([r.json()['manifest_sha256'] for r in responses[2:5]], [expected] * 3)
        self.assertIsNone(responses[-1].json()['manifest_sha256'])

    def test_cli_defaults_to_local_port_8001(self):
        with mock.patch.object(service, 'create_app', return_value='app'), \
                mock.patch('uvicorn.run') as run:
            service.main([])
            service.main(['--port', '18001'])
        self.assertEqual(run.call_args_list[0], mock.call('app', host='127.0.0.1', port=8001, access_log=False))
        self.assertEqual(run.call_args_list[1].kwargs['port'], 18001)


def _real_runner_path():
    candidates = [ROOT / 'scripts/run_avilist_pipeline.py']
    if os.getenv('ROBINGRAPH_AVILIST_RUNNER_PATH'):
        candidates.insert(0, Path(os.environ['ROBINGRAPH_AVILIST_RUNNER_PATH']))
    return next((path for path in candidates if path.is_file()), None)


class RealRunnerInterfaceTest(unittest.TestCase):
    def test_runner_exposes_the_called_functions(self):
        path = _real_runner_path()
        if path is None:
            self.skipTest('scripts/run_avilist_pipeline.py not present; set ROBINGRAPH_AVILIST_RUNNER_PATH')
        spec = importlib.util.spec_from_file_location('avilist_runner_under_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ('prepare', 'load_review', 'verify_runtime', 'test_settings', 'locked_store',
                     'store_bundle', 'digest'):
            self.assertTrue(callable(getattr(module, name)), name)
        with mock.patch.dict(os.environ, {'ROBINGRAPH_DEPLOY_TARGET': 'production'}), self.assertRaises(ValueError):
            module.test_settings()


if __name__ == '__main__':
    unittest.main()
