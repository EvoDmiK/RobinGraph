#!/usr/bin/env python3
"""Deploy an immutable GHCR image to the existing Mac TEST stack, with rollback."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

REPOSITORY = 'ghcr.io/evodmik/robingraph'


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else None


def switch_current(base, destination):
    temporary = base / ('.current-' + uuid.uuid4().hex)
    temporary.symlink_to(destination)
    os.replace(temporary, base / 'current')


def wait_healthy():
    for _ in range(45):
        state = json.loads(run('docker', '--context', 'orbstack', 'inspect',
                              'robingraph-api-test', capture=True))[0]['State']
        if state.get('Health', {}).get('Status') == 'healthy':
            return
        if not state.get('Running'):
            raise RuntimeError('TEST container exited')
        time.sleep(2)
    raise RuntimeError('TEST health check timed out')


def deploy(image, revision, base):
    if not re.fullmatch(re.escape(REPOSITORY) + r'@sha256:[a-f0-9]{64}', image):
        raise ValueError('An immutable RobinGraph GHCR digest is required')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('A full Git commit is required')
    base = Path(base).resolve()
    previous = (base / 'current').resolve(strict=True)
    if previous.parent != base / 'releases':
        raise ValueError('Current release must belong to the TEST release directory')
    existing = json.loads(run('docker', '--context', 'orbstack', 'inspect',
                             'robingraph-api-test', capture=True))[0]
    env = dict(value.split('=', 1) for value in existing['Config']['Env'])
    if env.get('ROBINGRAPH_DEPLOY_TARGET') != 'test':
        raise ValueError('Refusing to replace a non-TEST container')
    run('docker', '--context', 'orbstack', 'pull', '--platform', 'linux/arm64', image)
    inspected = json.loads(run('docker', '--context', 'orbstack', 'image', 'inspect', image, capture=True))[0]
    if (inspected['Architecture'] != 'arm64' or
            inspected['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != revision):
        raise ValueError('Image platform or Git revision does not match the approved build')
    release = base / 'releases' / ('ci-' + revision[:12] + '-' + image.rsplit(':', 1)[1][:12] + '-' + uuid.uuid4().hex[:8])
    release.mkdir(mode=0o700, exist_ok=False)
    for name in ['compose.nas.yml', 'compose.mac-test.yml']:
        shutil.copyfile(previous / name, release / name)
    lines = []
    for line in (previous / '.env.nas.test').read_text().splitlines():
        if line.startswith(('ROBINGRAPH_IMAGE=', 'ROBINGRAPH_VCS_REF=')):
            continue
        lines.append(line)
    lines.extend(['ROBINGRAPH_IMAGE=' + image, 'ROBINGRAPH_VCS_REF=' + revision])
    secret_file = release / '.env.nas.test'
    secret_file.touch(mode=0o600)
    secret_file.write_text('\n'.join(lines) + '\n')
    receipt = {'image': image, 'revision': revision, 'previous_release': str(previous),
               'state': 'prepared', 'deployment_target': 'test'}
    def save():
        (release / 'RELEASE.json').write_text(json.dumps(receipt, indent=2) + '\n')
    save()
    switch_current(base, release)
    try:
        run(str(base / 'manage.sh'), 'start')
        wait_healthy()
        run(str(base / 'manage.sh'), 'verify')
        run('curl', '--fail', '--silent', '--show-error', '--max-time', '30',
            'https://robingraph-test.dove-nest.com/health')
        receipt['state'] = 'verified'
        save()
    except Exception:
        switch_current(base, previous)
        receipt['state'] = 'rollback_started'
        save()
        run(str(base / 'manage.sh'), 'start')
        wait_healthy()
        run(str(base / 'manage.sh'), 'verify')
        receipt['state'] = 'rolled_back'
        save()
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    base = Path.home() / 'robingraph-test'
    with (base / '.registry-deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(deploy(args.image, args.revision, base)))


if __name__ == '__main__':
    main()
