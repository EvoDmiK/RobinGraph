import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('registry_deploy', Path(__file__).parents[1] / 'scripts/deploy_registry_test.py')
deploy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_module)
IMAGE = 'ghcr.io/evodmik/robingraph@sha256:' + 'a' * 64
REVISION = 'b' * 40


class RegistryTestDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.previous = self.base / 'releases' / 'previous'
        self.previous.mkdir(parents=True)
        for name in ['compose.nas.yml', 'compose.mac-test.yml']:
            (self.previous / name).write_text('services: {}\n')
        (self.previous / '.env.nas.test').write_text('ROBINGRAPH_IMAGE=old\nROBINGRAPH_PG_DATABASE=robingraph_test\n')
        (self.base / 'current').symlink_to(self.previous)

    def runner(self, verification_failure=False):
        calls = []
        def run(*args, capture=False):
            calls.append(args)
            if 'image' in args and 'inspect' in args:
                return json.dumps([{'Architecture': 'arm64', 'Config': {'Labels': {'org.opencontainers.image.revision': REVISION}}}])
            if 'inspect' in args:
                return json.dumps([{'Config': {'Env': ['ROBINGRAPH_DEPLOY_TARGET=test']}}])
            if args[-1] == 'verify' and verification_failure and sum(c[-1] == 'verify' for c in calls) == 1:
                raise RuntimeError('candidate API contract failed')
            return ''
        return calls, run

    def test_verification_failure_restores_previous_release_and_checks_rollback(self):
        calls, run = self.runner(verification_failure=True)
        with patch.object(deploy_module, 'run', side_effect=run), patch.object(deploy_module, 'wait_healthy'):
            with self.assertRaisesRegex(RuntimeError, 'candidate API'):
                deploy_module.deploy(IMAGE, REVISION, self.base)
        self.assertEqual((self.base / 'current').resolve(), self.previous)
        self.assertEqual(sum(c[-1] == 'start' for c in calls), 2)
        self.assertEqual(sum(c[-1] == 'verify' for c in calls), 2)
        receipt = json.loads(next(self.base.glob('releases/ci-*/RELEASE.json')).read_text())
        self.assertEqual(receipt['state'], 'rolled_back')

    def test_deployment_preserves_database_settings_and_uses_private_digest_release(self):
        _, run = self.runner()
        with patch.object(deploy_module, 'run', side_effect=run), patch.object(deploy_module, 'wait_healthy'):
            receipt = deploy_module.deploy(IMAGE, REVISION, self.base)
        self.assertEqual(receipt['state'], 'verified')
        secret_file = (self.base / 'current').resolve() / '.env.nas.test'
        self.assertEqual(secret_file.stat().st_mode & 0o777, 0o600)
        self.assertIn('ROBINGRAPH_PG_DATABASE=robingraph_test\n', secret_file.read_text())
        self.assertIn('ROBINGRAPH_IMAGE=' + IMAGE + '\n', secret_file.read_text())
        self.assertIn('ROBINGRAPH_IMAGE=old\n', (self.previous / '.env.nas.test').read_text())

    def test_mutable_or_foreign_image_is_rejected_before_docker_or_release_changes(self):
        for image in ['ghcr.io/evodmik/robingraph:latest', 'ghcr.io/another/image@sha256:' + 'a' * 64]:
            with self.subTest(image=image), patch.object(deploy_module, 'run') as run:
                with self.assertRaises(ValueError):
                    deploy_module.deploy(image, REVISION, self.base)
                run.assert_not_called()
        self.assertEqual((self.base / 'current').resolve(), self.previous)
