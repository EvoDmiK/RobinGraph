"""Deploy only the local TEST app from a hashed snapshot of root's final source.

Domain DBs, n8n, Neo4j and Production are never managed here. `prepare` only snapshots and hashes;
`deploy` builds ARM64, runs an isolated fixture smoke, then swaps TEST `current` with automatic rollback.
Adapted from /tmp/robingraph-followup-20261028/deploy_followup_test.py (reviewed); only names/paths changed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

work = Path('/tmp/robingraph-n8n-audio-20261105')
base = Path('/Users/kimdove/robingraph-test')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('prepare', 'deploy'))
parser.add_argument('--source', default='/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
parser.add_argument('--expect-source-sha256', help='deploy refuses a snapshot whose digest differs')
args = parser.parse_args()
root = Path(args.source)
TOP = ('pyproject.toml', 'uv.lock', 'Dockerfile', 'README.md', '.python-version', '.dockerignore')
FOLDERS = ('src', 'scripts', 'config', 'data', 'n8n')


def docker(*arguments):
    return subprocess.check_output(['docker', '--context', 'orbstack', *arguments], text=True)


def inspect_test():
    state = json.loads(docker('inspect', 'robingraph-api-test'))[0]
    assert 'ROBINGRAPH_DEPLOY_TARGET=test' in state['Config']['Env']
    return state


def source_files(folder):
    files = [folder / name for name in TOP]
    for sub in FOLDERS:
        files.extend(p for p in (folder / sub).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc'
                     and not any(part.endswith('.egg-info') for part in p.parts))
    return sorted(files)


def manifest(folder):
    hashes = {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files(folder)}
    return hashes, hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def snapshot():
    hashes, digest = manifest(root)
    target = work / ('snapshot-' + digest[:12])
    if not target.exists():
        staging = work / ('.snapshot-' + uuid.uuid4().hex)
        for path in source_files(root):
            dest = staging / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        os.replace(staging, target)
    copied, copied_digest = manifest(target)
    assert copied == hashes and copied_digest == digest, 'snapshot differs from source'
    return target, hashes, digest


def env_values(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))


def set_mode(env, image):
    current = env_values(env)
    # The stable signing key keeps feedback and follow-up tokens valid; it is never generated or printed here.
    assert current.get('ROBINGRAPH_DJANGO_SECRET_KEY', '').strip(), 'stable Django key missing'
    values = {'ROBINGRAPH_IMAGE': image}
    lines = [line for line in env.read_text().splitlines() if line.split('=', 1)[0] not in values]
    env.write_text('\n'.join(lines + [key + '=' + value for key, value in values.items()]) + '\n')
    env.chmod(0o600)


def start_and_verify():
    subprocess.run([str(base / 'manage.sh'), 'start'], check=True, stdout=subprocess.DEVNULL)
    for _ in range(45):
        if inspect_test()['State'].get('Health', {}).get('Status') == 'healthy':
            break
        time.sleep(2)
    else:
        raise RuntimeError('TEST health timeout')
    subprocess.run([str(base / 'manage.sh'), 'verify'], check=True, stdout=subprocess.DEVNULL)


def switch(path):
    link = base / ('.n8n-audio-current-' + uuid.uuid4().hex)
    link.symlink_to(path)
    os.replace(link, base / 'current')


old = (base / 'current').resolve(strict=True)
assert old.parent == base / 'releases'
prior = inspect_test()
prior_env = dict(item.split('=', 1) for item in prior['Config']['Env'])
assert prior_env.get('MLFLOW_EXPERIMENT_ID') == '33' and prior_env['MLFLOW_EXPERIMENT_NAME'] == 'robingraph-test'
assert prior_env['ROBINGRAPH_MLFLOW_TRACING'] == 'true' and prior_env['ROBINGRAPH_GRAPH_INTENT_MODE'] == 'active'
assert bool(env_values(old / '.env.nas.test').get('ROBINGRAPH_DJANGO_SECRET_KEY'))
snap, hashes, digest = snapshot()
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
summary = {'source': str(root), 'snapshot': str(snap), 'source_sha256': digest, 'files': len(hashes),
           'base_revision': revision, 'current_release': str(old), 'current_image': prior['Config']['Image'],
           'followup_module_sha256': hashes.get('src/robingraph/api/followup.py'),
           'chat_js_sha256': hashes.get('src/robingraph/api/static/chat.js')}
if args.action == 'prepare':
    (work / 'test-release-prepare.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    raise SystemExit
if args.expect_source_sha256 and args.expect_source_sha256 != digest:
    raise SystemExit(f'source digest {digest} differs from the approved {args.expect_source_sha256}')

image = 'robingraph-api:test-n8n-audio-' + digest[:12]
with (base / 'n8n-audio-build.log').open('w') as log:
    subprocess.run(['docker', '--context', 'orbstack', 'build', '--platform', 'linux/arm64',
                    '--build-arg', 'VCS_REF=' + revision, '--label', 'org.robingraph.test.source-sha256=' + digest,
                    '-t', image, '.'], cwd=snap, stdout=log, stderr=subprocess.STDOUT, check=True)
image_id = docker('image', 'inspect', '--format', '{{.Id}} {{.Architecture}}', image).split()
assert image_id[1] == 'arm64'
smoke = 'n8n-audio-fixture-smoke'
try:
    subprocess.run(['docker', '--context', 'orbstack', 'run', '-d', '--name', smoke, '--network', 'none',
                    '--read-only', '--tmpfs', '/tmp', image], check=True, stdout=subprocess.DEVNULL)
    for _ in range(45):
        result = subprocess.run(['docker', '--context', 'orbstack', 'exec', smoke, 'python', '-c',
            "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'))['mode']=='fixture'; "
            "d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')); assert 'ChatFollowupInfo' in d['components']['schemas']"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Isolated Django fixture smoke failed')
finally:
    subprocess.run(['docker', '--context', 'orbstack', 'rm', '-f', smoke], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
release = base / 'releases' / ('n8n-audio-' + digest[:12] + '-' + uuid.uuid4().hex[:6])
shutil.copytree(old, release)
release.chmod(0o700)
# Keep TEST secrets/deployment manifests (env, compose); refresh every source file and the image.
for folder in FOLDERS:
    target = release / folder
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(snap / folder, target)
for name in TOP:
    shutil.copy2(snap / name, release / name)
assert all(hashlib.sha256((release / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
set_mode(release / '.env.nas.test', image)
# New TEST-only media cache/auth; no existing n8n container or credentials are touched.
private = base / 'private'
private.mkdir(mode=0o700, exist_ok=True)
private.chmod(0o700)
audio_env = private / 'audio.env'
if not audio_env.exists():
    import secrets
    fd = os.open(audio_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('ROBINGRAPH_INGEST_INTERNAL_TOKEN=' + secrets.token_urlsafe(48) + '\n')
assert audio_env.stat().st_mode & 0o077 == 0
assert len(env_values(audio_env).get('ROBINGRAPH_INGEST_INTERNAL_TOKEN', '')) >= 32
cache = base / 'media/audio'
cache.mkdir(parents=True, mode=0o700, exist_ok=True)
# Docker performs UID initialization only inside the explicitly named TEST cache.
subprocess.run(['docker', '--context', 'orbstack', 'run', '--rm', '--network', 'none',
    '--user', '0:0', '--entrypoint', 'python', '--mount', 'type=bind,source='+str(cache)+',target=/audio', image,
    '-c', 'import os; os.chown("/audio",10001,10001); os.chmod("/audio",0o700)'], check=True, stdout=subprocess.DEVNULL)
compose = release / 'compose.mac-test.yml'
prior_compose = compose.read_text()
assert prior_compose.strip() == 'services:\n  api:\n    ports:\n      - "192.168.219.97:8000:8000"\n      - "127.0.0.1:8000:8000"' or 'ROBINGRAPH_AUDIO_ROOT' in prior_compose
compose.write_text('services:\n  api:\n    ports:\n      - "192.168.219.97:8000:8000"\n      - "127.0.0.1:8000:8000"\n    env_file:\n      - ${ROBINGRAPH_ENV_FILE:-.env.nas}\n      - /Users/kimdove/robingraph-test/private/audio.env\n    environment:\n      ROBINGRAPH_AUDIO_ROOT: /var/lib/robingraph/audio\n    volumes:\n      - type: bind\n        source: /Users/kimdove/robingraph-test/media/audio\n        target: /var/lib/robingraph/audio\n')
# Render the final compose model privately before changing current/TEST app.
compose_env = dict(os.environ, ROBINGRAPH_ENV_FILE=str(release / '.env.nas.test'),
    ROBINGRAPH_DEPLOY_TARGET='test', ROBINGRAPH_COMPOSE_PROJECT='robingraph-test',
    ROBINGRAPH_API_CONTAINER='robingraph-api-test')
rendered = subprocess.check_output(['docker', '--context', 'orbstack', 'compose',
    '--env-file', str(release / '.env.nas.test'), '-f', str(release / 'compose.nas.yml'),
    '-f', str(release / 'compose.mac-test.yml'), 'config', '--format', 'json'], env=compose_env, text=True)
model = json.loads(rendered)
api = model['services']['api']
assert api['container_name'] == 'robingraph-api-test'
assert api['environment']['ROBINGRAPH_DEPLOY_TARGET'] == 'test'
assert api['environment']['ROBINGRAPH_AUDIO_ROOT'] == '/var/lib/robingraph/audio'
assert api['environment'].get('ROBINGRAPH_INGEST_INTERNAL_TOKEN') == env_values(audio_env)['ROBINGRAPH_INGEST_INTERNAL_TOKEN']
assert any(v.get('type') == 'bind' and v.get('source') == str(cache) and
           v.get('target') == '/var/lib/robingraph/audio' and not v.get('read_only',False)
           for v in api.get('volumes',[]))
del rendered, model, api
receipt = dict(summary, image=image, image_id=image_id[0], architecture=image_id[1],
               previous_image=prior['Config']['Image'], previous_release=str(old), release=str(release),
               state='prepared', target='test', graph_intent_mode='active', production_changed=False,
               fixture_network_none_smoke=True, audio_cache=str(cache), audio_private_env=str(audio_env), compose_model_verified=True, feedback_experiment_id='33', signing_key_preserved=True,
               release_source_manifest_verified=True)
receipt_path = work / 'test-release.json'


def save():
    text = json.dumps(dict(receipt, file_sha256=hashes), indent=2) + '\n'
    (release / 'RELEASE.json').write_text(text)
    receipt_path.write_text(text)


save()
switch(release)
try:
    start_and_verify()
    receipt['state'] = 'verified'
    save()
except Exception:
    receipt['state'] = 'rollback_started'
    save()
    switch(old)
    subprocess.run([str(base / 'manage.sh'), 'start'], check=True, stdout=subprocess.DEVNULL)
    receipt['state'] = 'rolled_back'
    save()
    raise
print(json.dumps(receipt))
