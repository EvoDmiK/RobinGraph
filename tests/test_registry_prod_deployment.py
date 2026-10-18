import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('registry_prod', Path(__file__).parents[1] / 'scripts/deploy_registry_prod.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
IMAGE = 'ghcr.io/evodmik/robingraph@sha256:' + 'a' * 64
REVISION = 'b' * 40


class RegistryProductionDeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.original = b'ROBINGRAPH_IMAGE=old\nROBINGRAPH_API_MODE=serve-neo4j\nNEO4J_URI=bolt://prod\nROBINGRAPH_PG_HOST=prod\nROBINGRAPH_PG_DATABASE=robingraph\n'
        self.env = self.root / '.env.nas.prod'
        self.env.write_bytes(self.original)
        self.request = dict(image=IMAGE, revision=REVISION, registry_user='fixture', registry_token='fixture-token')
        self.container = {'Config': {'Image': 'old', 'Env': ['ROBINGRAPH_DEPLOY_TARGET=prod', 'NEO4J_URI=bolt://prod', 'ROBINGRAPH_PG_HOST=prod', 'ROBINGRAPH_PG_DATABASE=robingraph'], 'Labels': {'com.docker.compose.project.working_dir': str(self.root), 'com.docker.compose.project': 'robingraph'}}, 'State': {'Running': True, 'Health': {'Status': 'healthy'}}}

    def inspect(self, args, **kwargs):
        if args[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([{'Architecture': 'amd64', 'Config': {'Labels': {'org.opencontainers.image.revision': REVISION}}}]).encode()
        return json.dumps([self.container]).encode()

    def test_failed_production_start_restores_environment_and_verifies_previous_image(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[:2] == ['docker', 'compose'] and sum(c[:2] == ['docker', 'compose'] for c in calls) == 1:
                raise subprocess.CalledProcessError(1, args)
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), patch.object(module.subprocess, 'run', side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                module.remote_deploy(self.request)
        self.assertEqual(self.env.read_bytes(), self.original)
        self.assertEqual(sum(c[:2] == ['docker', 'compose'] for c in calls), 2)
        self.assertTrue(any(c[:2] == ['docker', 'exec'] for c in calls))
        receipt = json.loads(next(self.root.glob('.registry-deployments/*.json')).read_text())
        self.assertEqual(receipt['state'], 'rolled_back')
        backup = Path(receipt['previous_env_backup'])
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.env.stat().st_mode & 0o777, 0o600)

    def test_non_production_target_is_rejected_before_registry_login_or_mutation(self):
        self.container['Config']['Env'][0] = 'ROBINGRAPH_DEPLOY_TARGET=test'
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), patch.object(module.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'non-Production'):
                module.remote_deploy(self.request)
            run.assert_not_called()
        self.assertEqual(self.env.read_bytes(), self.original)

    def test_mutable_image_is_rejected_before_ssh_or_docker(self):
        with patch.object(module.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                module.validate('ghcr.io/evodmik/robingraph:latest', REVISION)
            run.assert_not_called()
