"""Deploy only the local TEST app. Domain DBs, n8n and Production are never managed here."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

root = Path(__file__).resolve().parents[4]
assets = Path(__file__).resolve().parent
base = Path('/Users/kimdove/robingraph-test')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('deploy-shadow', 'activate', 'off'))
args = parser.parse_args()


def docker(*arguments):
    return subprocess.check_output(['docker', '--context', 'orbstack', *arguments], text=True)


def inspect_test():
    state = json.loads(docker('inspect', 'robingraph-api-test'))[0]
    assert 'ROBINGRAPH_DEPLOY_TARGET=test' in state['Config']['Env']
    return state


def set_mode(env, mode, image=None):
    values = {'ROBINGRAPH_GRAPH_INTENT_MODE': mode, 'ROBINGRAPH_GRAPH_INTERPRETER': 'semantic'}
    if image:
        values['ROBINGRAPH_IMAGE'] = image
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
    link = base / ('.semantic-current-' + uuid.uuid4().hex)
    link.symlink_to(path)
    os.replace(link, base / 'current')


old = (base / 'current').resolve(strict=True)
assert old.parent == base / 'releases'
prior = inspect_test()
receipt_path = assets / 'test-release.json'

if args.action != 'deploy-shadow':
    receipt = json.loads(receipt_path.read_text())
    assert old == Path(receipt['release']) and prior['Config']['Image'] == receipt['image']
    if args.action == 'activate':
        checks = json.loads((assets / 'activation-gates.json').read_text())
        assert checks['all_passed'] and checks['shadow_api_verified']
    mode = 'active' if args.action == 'activate' else 'off'
    previous_mode = receipt['graph_intent_mode']
    env = old / '.env.nas.test'
    set_mode(env, mode)
    try:
        start_and_verify()
    except Exception:
        set_mode(env, previous_mode)
        start_and_verify()
        raise
    receipt['graph_intent_mode'] = mode
    receipt.setdefault('mode_history', []).append(mode)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    (old / 'RELEASE.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'target': 'test', 'mode': mode, 'image': receipt['image'], 'state': 'verified'}))
    raise SystemExit(0)

files = [root / name for name in ('pyproject.toml', 'uv.lock', 'Dockerfile', 'README.md', '.python-version', '.dockerignore')]
for folder in ('src', 'scripts', 'config', 'data', 'n8n'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix != '.pyc'
                 and not any(part.endswith('.egg-info') for part in p.parts))
hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
image = 'robingraph-api:test-taxonomic-traits-' + digest[:12]
with (base / 'taxonomic-traits-build.log').open('w') as log:
    subprocess.run(['docker', '--context', 'orbstack', 'build', '--platform', 'linux/arm64',
                    '--build-arg', 'VCS_REF=' + revision, '--label', 'org.robingraph.test.source-sha256=' + digest,
                    '-t', image, '.'], cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
absence = json.loads(docker('run', '--rm', '--network', 'none', image, 'python', '-c',
    "import importlib.util,json; r={n:importlib.util.find_spec(n) is None for n in ('fastapi','starlette')}; assert all(r.values()); print(json.dumps(r))"))
(assets / 'image-packages.json').write_text(json.dumps(absence, indent=2) + '\n')
smoke = 'taxonomic-traits-fixture-smoke'
try:
    subprocess.run(['docker', '--context', 'orbstack', 'run', '-d', '--name', smoke, '--network', 'none',
                    '--read-only', '--tmpfs', '/tmp', image], check=True, stdout=subprocess.DEVNULL)
    for _ in range(45):
        result = subprocess.run(['docker', '--context', 'orbstack', 'exec', smoke, 'python', '-c',
            "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'))['mode']=='fixture'; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Isolated Django fixture smoke failed')
finally:
    subprocess.run(['docker', '--context', 'orbstack', 'rm', '-f', smoke],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
release = base / 'releases' / ('taxonomic-traits-' + digest[:12] + '-' + uuid.uuid4().hex[:6])
shutil.copytree(old, release)
release.chmod(0o700)
# Keep TEST secrets/deployment manifests, but refresh all source files as well as the image.
for folder in ('src', 'scripts', 'config', 'data', 'n8n'):
    target = release / folder
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(root / folder, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info'))
for path in files:
    if len(path.relative_to(root).parts) == 1:
        shutil.copy2(path, release / path.name)
assert all(hashlib.sha256((release / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
set_mode(release / '.env.nas.test', 'shadow', image)
receipt = dict(image=image, source_sha256=digest, file_sha256=hashes, base_revision=revision,
               previous_image=prior['Config']['Image'], previous_release=str(old), release=str(release),
               state='prepared', target='test', graph_intent_mode='shadow', mode_history=['shadow'],
               uncommitted_source_snapshot=True, production_changed=False, fixture_network_none_smoke=True,
               release_source_manifest_verified=True)


def save():
    text = json.dumps(receipt, indent=2) + '\n'
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
print(json.dumps({key: value for key, value in receipt.items() if key != 'file_sha256'}))
