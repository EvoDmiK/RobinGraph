"""TEST-only HTTP wrapper so n8n HTTP Request nodes can call the AviList pilot stages.

Routes are fixed: POST /prepare, /verify, /apply (JSON body must be exactly {})
and GET /health. Callers never choose a source, path, approval or environment:
the package lives under ROBINGRAPH_AVILIST_PIPELINE_ROOT and the review record
is the server-side file ROBINGRAPH_AVILIST_APPROVAL_PATH, written out of band.
All gates are the ones in scripts/run_avilist_pipeline.py; this module only
sequences them, serialises calls and maps failures to fixed error codes.
Each package records the SHA-256 of the runner, core, builder and this service
when prepared; every stage refuses to run if any of them changed since.
Every stage response carries manifest_sha256 and projection_performed=false.
Run as `python -m scripts.serve_avilist_pipeline [--host 127.0.0.1] [--port 8001]`.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import threading

from asgiref.sync import sync_to_async
from django.core.exceptions import DisallowedHost
from django.core.handlers.asgi import ASGIHandler
from django.http import HttpResponse, JsonResponse
from django.urls import Resolver404, get_urlconf, path, resolve

from robingraph.api.drf.application import DjangoApiApplication, configure_default_settings

TOKEN_ENV = 'ROBINGRAPH_AVILIST_PIPELINE_TOKEN'
ROOT_ENV = 'ROBINGRAPH_AVILIST_PIPELINE_ROOT'
APPROVAL_ENV = 'ROBINGRAPH_AVILIST_APPROVAL_PATH'
MIN_TOKEN_LENGTH = 32
MAX_BODY_BYTES = 64
PACKAGE = 'review-package'
CANDIDATES = 'candidates'
PREPARE_PREFIX = '.prepare-'
PACKAGE_FILES = ('source.json', 'manifest.json', 'bundle.json')
CODE_FILE = 'code.json'

log = logging.getLogger('robingraph.avilist_pipeline_service')


class StageFailure(Exception):
    """A gate refused the stage; carries only a fixed, caller-safe code."""

    def __init__(self, status_code, error, **extra):
        super().__init__(error)
        self.status_code, self.error, self.extra = status_code, error, extra


def _load_runner():
    from scripts import run_avilist_pipeline
    return run_avilist_pipeline


def _check_startup(environ, runner):
    """Fail before serving unless token, paths and both DB targets are TEST."""
    from robingraph.graph.settings import Neo4jSettings
    from robingraph.ingest.avilist_pipeline import TEST_TARGET

    token = environ.get(TOKEN_ENV, '')
    if len(token) < MIN_TOKEN_LENGTH:
        raise ValueError(f'{TOKEN_ENV} must be at least {MIN_TOKEN_LENGTH} characters')
    root_value, approval_value = environ.get(ROOT_ENV, ''), environ.get(APPROVAL_ENV, '')
    if not root_value or not approval_value:
        raise ValueError(f'{ROOT_ENV} and {APPROVAL_ENV} are required')
    root, approval = Path(root_value), Path(approval_value)
    if not root.is_absolute() or not approval.is_absolute():
        raise ValueError('Pipeline root and approval path must be absolute')
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Pipeline root must be an existing directory')
    approval = approval.resolve()
    # prepare writes only under root, so it can never create or replace the review record.
    if approval.is_relative_to(root):
        raise ValueError('Approval path must be outside the pipeline root')
    runner.test_settings()
    graph = Neo4jSettings.from_environment()
    if (graph.uri, graph.database) != (TEST_TARGET['neo4j']['uri'], TEST_TARGET['neo4j']['database']):
        raise ValueError('Neo4j target is outside the TEST allowlist')
    return token, root, approval


def _classify(error):
    from robingraph.ingest.avilist_pipeline import AmbiguousIdentityError, ApprovalError, SourceVerificationError

    if isinstance(error, StageFailure):
        return error.status_code, error.error
    for kind, code in ((ApprovalError, 'approval_rejected'), (SourceVerificationError, 'source_verification_failed'),
                       (AmbiguousIdentityError, 'identity_ambiguous')):
        if isinstance(error, kind):
            return 409, code
    if isinstance(error, ValueError):
        return 409, 'gate_failed'
    if isinstance(error, RuntimeError):
        # locked_store raises this when another process holds the advisory lock.
        return 409, 'busy'
    if isinstance(error, (OSError, TimeoutError)):
        return 503, 'dependency_unavailable'
    return 500, 'internal_error'


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _code_fingerprint(runner):
    """SHA-256 of every source file that decides a stage, read fresh on each call."""
    from robingraph.ingest import avilist_pipeline as core

    from robingraph.api.drf import application as django_application

    paths = {'runner': runner.__file__, 'core': core.__file__, 'service': __file__,
             'django_asgi': django_application.__file__}
    builder = getattr(runner, 'builder', None)
    if builder is not None:
        paths['builder'] = builder.__file__
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in sorted(paths.items())}


def _same_package(left, right):
    try:
        return all((left / name).read_bytes() == (right / name).read_bytes() for name in PACKAGE_FILES)
    except FileNotFoundError:
        return False


def create_app(environ=None, runner=None):
    environ = os.environ if environ is None else environ
    runner = _load_runner() if runner is None else runner
    token, root, approval_path = _check_startup(environ, runner)
    package = root / PACKAGE
    lock = threading.Lock()
    # A crash during an earlier prepare may leave a partial temp directory.
    for stale in root.glob(PREPARE_PREFIX + '*'):
        shutil.rmtree(stale, ignore_errors=True)

    configure_default_settings()

    def authorize(request):
        header = request.headers.get('authorization', '')
        supplied = header[7:] if header.startswith('Bearer ') else ''
        # Compare bytes so non-ASCII input cannot raise inside compare_digest.
        if not secrets.compare_digest(supplied.encode(), token.encode()):
            raise StageFailure(401, 'unauthorized')

    def empty_body(request):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            raise StageFailure(415, 'json_body_required')
        body = request.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise StageFailure(413, 'body_too_large')
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, ValueError):
            raise StageFailure(400, 'invalid_json') from None
        if value != {}:
            raise StageFailure(400, 'body_must_be_empty_object')

    @contextmanager
    def exclusive():
        if not lock.acquire(blocking=False):
            raise StageFailure(409, 'busy')
        try:
            yield
        finally:
            lock.release()

    def bind_code(package_dir, rebind=False):
        """Pin the runner/core/builder/service sources a package was prepared with."""
        current = _code_fingerprint(runner)
        path = package_dir / CODE_FILE
        if not path.is_file():
            if not rebind:
                raise StageFailure(409, 'code_unbound')
            # A package installed out of band is bound on the first prepare that rebuilds it identically.
            partial = package_dir / (CODE_FILE + '.partial')
            partial.write_bytes(_encoded(current))
            partial.replace(path)
        elif json.loads(path.read_bytes()) != current:
            raise StageFailure(409, 'code_changed')

    def reviewed():
        if not package.is_dir():
            raise StageFailure(409, 'package_missing')
        bind_code(package)
        if not approval_path.is_file():
            raise StageFailure(409, 'approval_missing')
        return runner.load_review(package, approval_path)

    def package_manifest():
        try:
            return runner.digest(json.loads((package / 'manifest.json').read_bytes()))
        except Exception:  # noqa: BLE001 - best effort for failure responses only
            return None

    def do_prepare():
        workdir = Path(tempfile.mkdtemp(prefix=PREPARE_PREFIX, dir=root))
        try:
            candidate = workdir / PACKAGE
            # Always the official pinned URL; never a caller-supplied or cached source.
            result = runner.prepare(None, candidate)
            key = result['manifest_sha256']
            (candidate / CODE_FILE).write_bytes(_encoded(_code_fingerprint(runner)))
            if package.exists():
                if _same_package(candidate, package):
                    bind_code(package, rebind=True)
                    return 200, {'status': 'prepared', 'reused': True, 'manifest_sha256': key,
                                 'counts': result['counts']}
                # Keep the differing package for review; the reviewed one stays in place.
                held = root / CANDIDATES / key
                if not held.exists():
                    held.parent.mkdir(exist_ok=True)
                    candidate.rename(held)
                raise StageFailure(409, 'review_required', manifest_sha256=key, counts=result['counts'])
            candidate.rename(package)
            raise StageFailure(409, 'review_required', manifest_sha256=key, counts=result['counts'])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def do_verify():
        manifest, bundle, _ = reviewed()
        verification = runner.verify_runtime(bundle)
        return 200, {'status': 'verified', 'manifest_sha256': runner.digest(manifest),
                     'bundle_sha256': runner.digest(bundle),
                     'search_regression_passed': len(verification.get('search_regression', ()))}

    def do_apply():
        settings = runner.test_settings()
        # Approval binding, code binding and runtime freshness are re-checked; an earlier /verify is not trusted.
        manifest, bundle, approval = reviewed()
        verification = runner.verify_runtime(bundle)
        with runner.locked_store(settings) as store:
            result = runner.store_bundle(store, manifest, bundle, approval, verification)
        return 200, {'status': result['status'], 'manifest_sha256': runner.digest(manifest),
                     'release_id': result['release_id'], 'run_id': result['run_id']}

    async def run_stage(request, stage, action):
        authorized = False
        try:
            authorize(request)
            authorized = True
            empty_body(request)

            # Sync gates do network and DB I/O; run them off the event loop.
            def guarded():
                with exclusive():
                    return action()
            status_code, payload = await sync_to_async(guarded, thread_sensitive=False)()
        except Exception as error:  # noqa: BLE001 - every failure becomes a fixed code
            status_code, code = _classify(error)
            # Only stage, code and type: messages may carry paths or environment details.
            log.warning('avilist pipeline %s failed: %s (%s)', stage, code, type(error).__name__)
            extra = error.extra if isinstance(error, StageFailure) else {}
            payload = {'status': 'review_required' if code == 'review_required' else 'failed',
                       'stage': stage, 'error': code, **extra}
            if 'manifest_sha256' not in payload:
                payload['manifest_sha256'] = package_manifest() if authorized and stage != 'prepare' else None
            payload['projection_performed'] = False
            headers = {'WWW-Authenticate': 'Bearer'} if status_code == 401 else None
            return JsonResponse(payload, status=status_code, headers=headers)
        log.info('avilist pipeline %s: %s', stage, payload['status'])
        # The service never projects into domain stores; n8n checks this on every node.
        return JsonResponse({**payload, 'stage': stage, 'projection_performed': False}, status=status_code)

    def rejected(status, error):
        return JsonResponse({'status': 'failed', 'error': error}, status=status)

    def handler400(request=None, exception=None):
        return rejected(400, 'rejected')

    def handler404(request, exception=None):
        route = request.path_info
        if route != '/':
            alternative = route.rstrip('/') if route.endswith('/') else route + '/'
            try:
                resolve(alternative, urlconf=get_urlconf())
            except Resolver404:
                pass
            else:
                location = f"{request.scheme}://{request.get_host()}{request.script_name.rstrip('/')}{alternative}"
                query = request.META.get('QUERY_STRING')
                response = HttpResponse(status=307)
                response['Location'] = f'{location}?{query}' if query else location
                del response['Content-Type']
                return response
        return rejected(404, 'not_found')

    def handler500(request):
        return rejected(500, 'internal_error')

    class PipelineUrlConf:
        # The runner's routes and errors are isolated from the public API.
        pass

    urlconf = PipelineUrlConf()
    urlconf.handler400 = handler400
    urlconf.handler404 = handler404
    urlconf.handler500 = handler500

    async def health(request):
        if request.method != 'GET':
            return rejected(405, 'rejected')
        return JsonResponse({'status': 'ok', 'deployment_target': 'test', 'projection_performed': False})

    def stage_view(stage, action):
        async def view(request):
            if request.method != 'POST':
                return rejected(405, 'rejected')
            return await run_stage(request, stage, action)
        return view

    urlconf.urlpatterns = [
        path('health', health),
        path('prepare', stage_view('prepare', do_prepare)),
        path('verify', stage_view('verify', do_verify)),
        path('apply', stage_view('apply', do_apply)),
    ]

    class PipelineApplication(DjangoApiApplication):
        async def __call__(self, scope, receive, send):
            if scope['type'] != 'http':
                return await super().__call__(scope, receive, send)
            route = scope.get('path', '')
            stage = route[1:] if route in ('/prepare', '/verify', '/apply') and scope.get('method') == 'POST' else None
            authorized = False

            async def refuse(status, code):
                if stage is None:
                    payload = {'status': 'failed', 'error': code}
                else:
                    payload = {'status': 'failed', 'stage': stage, 'error': code,
                               'manifest_sha256': package_manifest() if authorized and stage != 'prepare' else None,
                               'projection_performed': False}
                response = JsonResponse(payload, status=status)
                if status == 401:
                    response['WWW-Authenticate'] = 'Bearer'
                await send({'type': 'http.response.start', 'status': status,
                            'headers': [(k.lower().encode('ascii'), v.encode('latin-1')) for k, v in response.items()]})
                await send({'type': 'http.response.body', 'body': response.content})

            if stage is not None:
                values = [v.decode('latin-1') for k, v in scope.get('headers', []) if k.lower() == b'authorization']
                header = ','.join(values)
                supplied = header[7:] if header.startswith('Bearer ') else ''
                if not secrets.compare_digest(supplied.encode(), token.encode()):
                    return await refuse(401, 'unauthorized')
                authorized = True

            # Bound real received bytes before Django can spool the request body.
            # Content-Length may be absent or false, so it is not the authority.
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                if message['type'] != 'http.request':
                    return await refuse(400, 'invalid_request')
                chunk = message.get('body', b'')
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    return await refuse(413, 'body_too_large')
                body.extend(chunk)
                if not message.get('more_body', False):
                    break
            pending = True

            async def replay():
                nonlocal pending
                if pending:
                    pending = False
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()

            return await super().__call__(scope, replay, send)

        async def get_response_async(self, request):
            try:
                request.get_host()
            except DisallowedHost:
                return handler400()
            request.urlconf = self.urlconf
            return await ASGIHandler.get_response_async(self, request)

    return PipelineApplication(urlconf, {})


def main(argv=None):
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
