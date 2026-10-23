#!/usr/bin/env python3
"""Promote an approved immutable image locally or over SSH; no DB writes."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPOSITORY = 'ghcr.io/evodmik/robingraph'


def production_context():
    previous = json.loads(subprocess.check_output(['docker', 'inspect', 'robingraph-api']))[0]
    existing_env = dict(item.split('=', 1) for item in previous['Config']['Env'])
    if existing_env.get('ROBINGRAPH_DEPLOY_TARGET') != 'prod':
        raise ValueError('Refusing to change a non-Production container')
    root = Path(previous['Config']['Labels']['com.docker.compose.project.working_dir'])
    env_path = root / '.env.nas.prod'
    original = env_path.read_bytes()
    values = dict(line.split('=', 1) for line in original.decode().splitlines()
                  if '=' in line and not line.startswith('#'))
    for key in ['NEO4J_URI', 'ROBINGRAPH_PG_HOST', 'ROBINGRAPH_PG_DATABASE']:
        if values.get(key) != existing_env.get(key):
            raise ValueError('Production database configuration mismatch: ' + key)
    if not (root / 'compose.nas.yml').is_file():
        raise ValueError('Production compose file is not mounted at its host path')
    return previous, root, env_path, original, values


def validate(image, revision):
    if not re.fullmatch(re.escape(REPOSITORY) + r'@sha256:[a-f0-9]{64}', image):
        raise ValueError('An immutable RobinGraph digest is required')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('A full Git commit is required')


def remote_deploy(request):
    image, revision = request['image'], request['revision']
    validate(image, revision)
    runtime = {}
    for option, key, allowed in (
        ('graph_intent_mode', 'ROBINGRAPH_GRAPH_INTENT_MODE', ('off', 'shadow', 'active')),
        ('graph_interpreter', 'ROBINGRAPH_GRAPH_INTERPRETER', ('lexical', 'semantic')),
    ):
        if request.get(option) is not None:
            if request[option] not in allowed:
                raise ValueError('Invalid runtime option: ' + option)
            runtime[key] = request[option]
    def inspect(name, image=False, environment=None):
        args = ['docker', 'image', 'inspect', name] if image else ['docker', 'inspect', name]
        return json.loads(subprocess.check_output(args, env=environment))[0]
    previous, root, env_path, original, values = production_context()
    labels = previous['Config']['Labels']
    with tempfile.TemporaryDirectory(prefix='robingraph-registry-') as auth_dir:
        plugins = Path.home() / '.docker' / 'cli-plugins'
        if plugins.is_dir():
            (Path(auth_dir) / 'cli-plugins').symlink_to(plugins, target_is_directory=True)
        environment = dict(os.environ, DOCKER_CONFIG=auth_dir)
        subprocess.run(['docker', 'login', 'ghcr.io', '--username', request['registry_user'], '--password-stdin'],
                       input=request['registry_token'], text=True, capture_output=True, check=True, env=environment)
        subprocess.run(['docker', 'pull', '--platform', 'linux/amd64', image], check=True, env=environment)
        candidate = inspect(image, image=True, environment=environment)
        if (candidate['Architecture'] != 'amd64' or
                candidate['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != revision):
            raise ValueError('Production image platform or revision mismatch')
        environment.update(ROBINGRAPH_DEPLOY_TARGET='prod',
                           ROBINGRAPH_COMPOSE_PROJECT=labels['com.docker.compose.project'],
                           ROBINGRAPH_API_CONTAINER='robingraph-api', ROBINGRAPH_ENV_FILE=str(env_path),
                           ROBINGRAPH_API_MODE=values['ROBINGRAPH_API_MODE'],
                           ROBINGRAPH_EDGE_NETWORK=values.get('ROBINGRAPH_EDGE_NETWORK', 'robingraph-edge'))
        def write_env(content):
            fd, temporary = tempfile.mkstemp(prefix='.env.nas.prod.ci-', dir=root)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(content)
                os.replace(temporary, env_path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        def apply(target_image):
            environment['ROBINGRAPH_IMAGE'] = target_image
            subprocess.run(['docker', 'compose', '--env-file', str(env_path), '-f', str(root / 'compose.nas.yml'),
                            'up', '-d', '--no-build', '--no-deps', 'api'], check=True, env=environment)
            for _ in range(45):
                state = inspect('robingraph-api')['State']
                if state.get('Health', {}).get('Status') == 'healthy':
                    break
                if not state.get('Running'):
                    raise RuntimeError('Production container exited')
                time.sleep(2)
            else:
                raise RuntimeError('Production health timeout')
            subprocess.run(['docker', 'exec', 'robingraph-api', 'python', 'scripts/verify_api_deployment.py',
                            '--base-url', 'http://127.0.0.1:8000', '--json'], check=True, env=environment)
        updates = {'ROBINGRAPH_IMAGE': image, 'ROBINGRAPH_VCS_REF': revision, **runtime}
        lines = [line for line in original.decode().splitlines()
                 if line.partition('=')[0] not in updates]
        lines.extend(key + '=' + value for key, value in updates.items())
        record_dir = root / '.registry-deployments'
        record_dir.mkdir(mode=0o700, exist_ok=True)
        record_dir.chmod(0o700)
        record_path = record_dir / (revision + '-' + str(time.time_ns()) + '.json')
        backup_path = record_path.with_suffix('.env.previous')
        backup_fd = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(backup_fd, 'wb') as backup:
            backup.write(original)
        receipt = {'image': image, 'revision': revision, 'previous_image': previous['Config']['Image'],
                   'previous_env_backup': str(backup_path), 'runtime_overrides': runtime, 'state': 'prepared'}
        def save():
            record_path.write_text(json.dumps(receipt, indent=2) + '\n')
        save()
        write_env(('\n'.join(lines) + '\n').encode())
        try:
            apply(image)
            receipt['state'] = 'verified'
            save()
        except Exception:
            write_env(original)
            receipt['state'] = 'rollback_started'
            save()
            apply(previous['Config']['Image'])
            receipt['state'] = 'rolled_back'
            save()
            raise
        print(json.dumps(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image')
    parser.add_argument('--revision')
    parser.add_argument('--graph-intent-mode', choices=('off', 'shadow', 'active'))
    parser.add_argument('--graph-interpreter', choices=('lexical', 'semantic'))
    parser.add_argument('--local', action='store_true', help='Run on the NAS deployment agent without SSH')
    parser.add_argument('--check-only', action='store_true', help='Read-only NAS context check; requires --local')
    args = parser.parse_args()
    if args.check_only:
        if not args.local:
            parser.error('--check-only requires --local')
        previous, *_ = production_context()
        subprocess.run(['docker', 'compose', 'version'], check=True)
        print(json.dumps({'production_context_verified': True, 'container_id': previous['Id'],
                          'started_at': previous['State']['StartedAt'], 'mutations': 0}))
        return
    if not args.image or not args.revision:
        parser.error('--image and --revision are required for deployment')
    validate(args.image, args.revision)
    # Password and registry token travel in SSH input/environment, never argv.
    request = {'image': args.image, 'revision': args.revision,
               'registry_user': os.environ['GHCR_USERNAME'], 'registry_token': os.environ['GHCR_TOKEN']}
    for option in ('graph_intent_mode', 'graph_interpreter'):
        if getattr(args, option) is not None:
            request[option] = getattr(args, option)
    if args.local:
        remote_deploy(request)
        return
    if os.environ['NAS_USERNAME'] != 'kimdove':
        raise ValueError('Unexpected NAS deployment account')
    source = 'import json\n_DEPLOY_REQUEST=json.loads(' + repr(json.dumps(request)) + ')\n' + Path(__file__).read_text()
    with tempfile.TemporaryDirectory(prefix='robingraph-ssh-') as directory:
        askpass = Path(directory) / 'askpass'
        askpass.write_text('#!/bin/sh\nprintf "%s\\n" "$NAS_PASSWORD"\n')
        askpass.chmod(0o700)
        environment = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force', DISPLAY='jenkins')
        subprocess.run(['ssh', '-T', '-p', '99', '-o', 'StrictHostKeyChecking=yes',
                        '-o', 'NumberOfPasswordPrompts=1', '-o', 'ConnectTimeout=10',
                        'kimdove@192.168.219.99', 'python3', '-'],
                       input=source, text=True, env=environment, check=True)


if __name__ == '__main__':
    if '_DEPLOY_REQUEST' in globals():
        remote_deploy(_DEPLOY_REQUEST)
    else:
        main()
