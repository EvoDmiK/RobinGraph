"""Pilot orchestration ordering and environment guards; all DB operations mocked."""
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scripts import run_avilist_pipeline as runner


class PipelineRunnerTest(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.active_release_context.return_value = None
        self.store.pipeline_state_version.return_value = 0
        self.store.activate_release.return_value = 1
        self.bundle = {'counts': {'active_species': 11131}, 'taxa': {}, 'sources': {}, 'inputs': {}}

    def apply(self):
        return runner.store_bundle(self.store, {'input': 'fixed'}, self.bundle,
                                   {'reviewer': 'fixture-agent'}, {'projection_performed': False})

    def test_same_release_is_noop_without_new_run(self):
        expected = 'rg:release:avilist-pilot:' + runner.digest({'input': 'fixed'})
        self.store.active_release_context.return_value = SimpleNamespace(
            dataset=SimpleNamespace(id=runner.DATASET, source_id=runner.builder.AVILIST_SOURCE['id']),
            release=SimpleNamespace(id=expected, dataset_id=runner.DATASET,
                                    content_sha256=runner.digest(self.bundle),
                                    metadata={'manifest_sha256': runner.digest({'input': 'fixed'})}),
            last_successful_run_id='first-run')
        self.assertEqual(self.apply()['status'], 'already_applied')
        self.store.begin_run.assert_not_called()
        self.store.append_batch.assert_not_called()

    def test_existing_pointer_to_other_dataset_is_not_a_successful_noop(self):
        self.store.active_release_context.return_value = SimpleNamespace(
            dataset=SimpleNamespace(id='unrelated'), release=SimpleNamespace(id='same-key'))
        with self.assertRaisesRegex(ValueError, 'another dataset'):
            self.apply()
        self.store.begin_run.assert_not_called()

    def test_failed_append_never_activates_and_retry_keeps_record_identity(self):
        self.store.append_batch.side_effect = RuntimeError('fixture interruption')
        with self.assertRaises(RuntimeError):
            self.apply()
        first_run = self.store.begin_run.call_args.args[2].id
        first_record = self.store.append_batch.call_args.kwargs['records'][0]
        self.store.activate_release.assert_not_called()
        self.store.fail_run.assert_called_once()
        self.store.append_batch.side_effect = None
        self.assertEqual(self.apply()['status'], 'applied')
        second_record = self.store.append_batch.call_args.kwargs['records'][0]
        self.assertEqual(first_record.id, second_record.id)
        self.assertNotEqual(first_run, second_record.ingestion_run_id)

    def test_activate_after_append_with_cas_and_pilot_pointer_only(self):
        self.apply()
        self.assertEqual(self.store.begin_run.call_args.args[2].pipeline_id, runner.PIPELINE)
        self.assertEqual(self.store.activate_release.call_args.kwargs['expected_state_version'], 0)
        self.assertFalse(self.store.activate_release.call_args.kwargs['cursor_value']['projection_performed'])
        self.assertEqual(self.store.append_batch.call_args.kwargs['records'][0].payload, self.bundle)
        self.assertEqual([call[0] for call in self.store.method_calls], [
            'active_release_context', 'pipeline_state_version', 'begin_run', 'append_batch', 'activate_release'])

    def test_commit_response_loss_reconciles_successful_pointer(self):
        self.store.activate_release.side_effect = ConnectionError('fixture lost response')

        def active(_pipeline):
            if not self.store.begin_run.called:
                return None
            run = self.store.begin_run.call_args.args[2]
            return SimpleNamespace(last_successful_run_id=run.id, release=SimpleNamespace(id=run.source_release_id))

        self.store.active_release_context.side_effect = active
        self.assertEqual(self.apply()['status'], 'applied_reconciled')
        self.store.fail_run.assert_not_called()

    def test_failure_recording_does_not_mask_original_error(self):
        self.store.append_batch.side_effect = RuntimeError('fixture original failure')
        self.store.fail_run.side_effect = ConnectionError('fixture disconnected')
        with self.assertRaisesRegex(RuntimeError, 'original failure'):
            self.apply()

    def test_failed_readiness_performs_no_database_write(self):
        with patch.object(runner, 'test_settings'), patch.object(runner, 'load_review',
                return_value=({}, self.bundle, {})), patch.object(runner, 'verify_runtime',
                side_effect=ValueError('index stale')), patch.object(runner, 'locked_store') as locked:
            with self.assertRaisesRegex(ValueError, 'index stale'):
                runner.main(['apply', '--package', '/fixture', '--approval', '/fixture/approval', '--apply'])
            locked.assert_not_called()

    def test_dry_run_verifies_but_does_not_enter_write_lock(self):
        with patch.object(runner, 'test_settings'), patch.object(runner, 'load_review',
                return_value=({}, self.bundle, {})), patch.object(runner, 'verify_runtime', return_value={}), \
                patch.object(runner, 'locked_store') as locked, patch('builtins.print'):
            self.assertEqual(runner.main(['apply', '--package', '/fixture', '--approval', '/fixture/review']), 0)
            locked.assert_not_called()

    def test_production_flag_rejected_before_settings_or_connection(self):
        with patch.dict('os.environ', {'ROBINGRAPH_DEPLOY_TARGET': 'production'}), \
                patch.object(runner.PostgresSettings, 'from_environment') as settings:
            with self.assertRaisesRegex(ValueError, 'TEST target'):
                runner.test_settings()
            settings.assert_not_called()

    def test_test_flag_with_wrong_database_rejected(self):
        wrong = SimpleNamespace(host='192.168.219.99', port=5433, database='robingraph',
                                username='robingraph_test_app', schema='ingest')
        with patch.dict('os.environ', {'ROBINGRAPH_DEPLOY_TARGET': 'test'}), \
                patch.object(runner.PostgresSettings, 'from_environment', return_value=wrong):
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                runner.test_settings()

    def test_live_database_identity_mismatch_never_takes_lock(self):
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = ('robingraph', 'production_user')
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        settings = Mock()
        settings.connection_kwargs.return_value = {}
        with patch('psycopg.connect', return_value=context):
            with self.assertRaisesRegex(ValueError, 'Connected PostgreSQL identity'):
                with runner.locked_store(settings):
                    self.fail('Wrong database admitted')
        self.assertEqual(connection.execute.call_count, 1)

    def test_busy_lock_stops_without_creating_store_or_unlocking_other_owner(self):
        connection = Mock()
        connection.execute.return_value.fetchone.side_effect = [
            ('robingraph_test', 'robingraph_test_app'), (False,)]
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        settings = Mock()
        settings.connection_kwargs.return_value = {}
        with patch('psycopg.connect', return_value=context), patch.object(runner, 'IngestionStore') as store:
            with self.assertRaisesRegex(RuntimeError, 'Another pilot'):
                with runner.locked_store(settings):
                    self.fail('Busy lock admitted')
            store.assert_not_called()
        self.assertEqual(connection.execute.call_count, 2)

    def test_denied_policy_releases_acquired_lock_and_never_opens_store(self):
        connection = Mock()
        connection.execute.return_value.fetchone.side_effect = [
            ('robingraph_test', 'robingraph_test_app'), (True,), ('avilist-v2025b', 'denied')]
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        settings = Mock(schema='ingest')
        settings.connection_kwargs.return_value = {}
        with patch('psycopg.connect', return_value=context), patch.object(runner, 'IngestionStore') as store:
            with self.assertRaisesRegex(ValueError, 'license policy'):
                with runner.locked_store(settings):
                    self.fail('Denied policy admitted')
            store.assert_not_called()
        self.assertIn('pg_advisory_unlock', str(connection.execute.call_args.args[0]))

    def test_unreviewed_download_redirect_rejected_before_reading_body(self):
        response = Mock(url='https://unreviewed.example/source.json')
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch.object(runner, 'urlopen', return_value=context):
            with self.assertRaisesRegex(ValueError, 'Unexpected source redirect'):
                runner.prepare(None, Path('/unused-review-package'))
        response.read.assert_not_called()

    def test_oversize_download_is_bounded_and_rejected_before_output(self):
        response = Mock(url=runner.builder.AVILIST_SOURCE['url'])
        response.read.return_value = b'x' * 11
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch.object(runner, 'urlopen', return_value=context), patch.object(runner, 'MAX_SOURCE_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                runner.prepare(None, Path('/unused-review-package'))
        response.read.assert_called_once_with(11)


if __name__ == '__main__':
    unittest.main()
