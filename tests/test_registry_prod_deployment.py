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
        (self.root / 'compose.nas.yml').write_text('services: {}\n')
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

    def test_local_check_needs_no_credentials_and_does_not_mutate(self):
        self.container['Id'] = 'fixture-container'
        self.container['State']['StartedAt'] = 'fixture-start'
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), \
                patch.object(module.subprocess, 'run') as run, \
                patch.object(module.sys, 'argv', ['deploy', '--local', '--check-only']), \
                patch.dict(module.os.environ, {}, clear=True):
            module.main()
        self.assertEqual(run.call_args.args[0], ['docker', 'compose', 'version'])
        self.assertEqual(self.env.read_bytes(), self.original)
        self.assertFalse((self.root / '.registry-deployments').exists())

    def test_local_deploy_does_not_require_ssh_credentials(self):
        with patch.object(module, 'remote_deploy') as deploy, \
                patch.object(module.sys, 'argv', ['deploy', '--local', '--image', IMAGE, '--revision', REVISION]), \
                patch.dict(module.os.environ, {'GHCR_USERNAME': 'fixture', 'GHCR_TOKEN': 'fixture-token'}, clear=True):
            module.main()
        deploy.assert_called_once_with(self.request)

    def test_runtime_flags_are_in_same_environment_update_as_approved_image(self):
        self.env.write_bytes(self.original + b'ROBINGRAPH_GRAPH_INTENT_MODE=off\nROBINGRAPH_GRAPH_INTERPRETER=semantic\n')
        before = self.env.read_bytes()
        snapshots = []
        def run(args, **kwargs):
            if args[:2] == ['docker', 'compose']:
                snapshots.append(self.env.read_text())
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), \
                patch.object(module.subprocess, 'run', side_effect=run):
            module.remote_deploy(dict(self.request, graph_intent_mode='active', graph_interpreter='lexical'))
        self.assertEqual(len(snapshots), 1)
        lines = snapshots[0].splitlines()
        for line in ('ROBINGRAPH_IMAGE=' + IMAGE, 'ROBINGRAPH_GRAPH_INTENT_MODE=active',
                     'ROBINGRAPH_GRAPH_INTERPRETER=lexical'):
            self.assertEqual(lines.count(line), 1)
        self.assertNotIn('ROBINGRAPH_GRAPH_INTENT_MODE=off', lines)
        self.assertNotIn('ROBINGRAPH_GRAPH_INTERPRETER=semantic', lines)
        receipt = json.loads(next(self.root.glob('.registry-deployments/*.json')).read_text())
        self.assertEqual(receipt['state'], 'verified')
        self.assertEqual(Path(receipt['previous_env_backup']).read_bytes(), before)
        self.assertEqual(receipt['runtime_overrides'], {
            'ROBINGRAPH_GRAPH_INTENT_MODE': 'active', 'ROBINGRAPH_GRAPH_INTERPRETER': 'lexical'})

    def test_failed_runtime_verification_restores_original_flags_before_rollback(self):
        self.env.write_bytes(self.original + b'ROBINGRAPH_GRAPH_INTENT_MODE=shadow\nROBINGRAPH_GRAPH_INTERPRETER=semantic\n')
        before = self.env.read_bytes()
        snapshots, verifications = [], []
        def run(args, **kwargs):
            if args[:2] == ['docker', 'compose']:
                snapshots.append(self.env.read_bytes())
            if args[:2] == ['docker', 'exec']:
                verifications.append(args)
                if len(verifications) == 1:
                    raise subprocess.CalledProcessError(1, args)
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), \
                patch.object(module.subprocess, 'run', side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                module.remote_deploy(dict(self.request, graph_intent_mode='active', graph_interpreter='lexical'))
        self.assertIn(b'ROBINGRAPH_GRAPH_INTENT_MODE=active\n', snapshots[0])
        self.assertIn(b'ROBINGRAPH_GRAPH_INTERPRETER=lexical\n', snapshots[0])
        self.assertEqual(snapshots[1], before)
        self.assertEqual(self.env.read_bytes(), before)
        self.assertEqual(len(verifications), 2)
        receipt = json.loads(next(self.root.glob('.registry-deployments/*.json')).read_text())
        self.assertEqual(receipt['state'], 'rolled_back')

    def test_invalid_runtime_flag_is_rejected_before_any_external_call(self):
        for option in ('graph_intent_mode', 'graph_interpreter'):
            with self.subTest(option=option), patch.object(module, 'production_context') as context, \
                    patch.object(module.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Invalid runtime option'):
                    module.remote_deploy(dict(self.request, **{option: 'invalid\nNEO4J_URI=other'}))
                context.assert_not_called()
                run.assert_not_called()
        self.assertEqual(self.env.read_bytes(), self.original)

    def test_local_deploy_forwards_only_explicit_runtime_flags(self):
        with patch.object(module, 'remote_deploy') as deploy, \
                patch.object(module.sys, 'argv', ['deploy', '--local', '--image', IMAGE, '--revision', REVISION,
                                                 '--graph-intent-mode', 'active', '--graph-interpreter', 'lexical']), \
                patch.dict(module.os.environ, {'GHCR_USERNAME': 'fixture', 'GHCR_TOKEN': 'fixture-token'}, clear=True):
            module.main()
        deploy.assert_called_once_with(dict(self.request, graph_intent_mode='active', graph_interpreter='lexical'))

    def test_omitted_runtime_options_preserve_existing_settings(self):
        self.env.write_bytes(self.original + b'ROBINGRAPH_GRAPH_INTENT_MODE=shadow\nROBINGRAPH_GRAPH_INTERPRETER=lexical\n')
        with patch.object(module.subprocess, 'check_output', side_effect=self.inspect), \
                patch.object(module.subprocess, 'run'):
            module.remote_deploy(self.request)
        self.assertIn(b'ROBINGRAPH_GRAPH_INTENT_MODE=shadow\n', self.env.read_bytes())
        self.assertIn(b'ROBINGRAPH_GRAPH_INTERPRETER=lexical\n', self.env.read_bytes())
