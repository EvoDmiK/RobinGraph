"""Runtime boundaries for the native Django migration (offline, no shared DB)."""
from __future__ import annotations

import importlib
import subprocess
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import unittest
from unittest.mock import patch


class DjangoRuntimeTest(unittest.TestCase):
    def test_settings_keep_existing_sql_schema_outside_django_orm(self):
        settings = importlib.import_module('robingraph.django_api.settings')
        # django.setup normalizes an empty mapping into the dummy backend.
        self.assertTrue(all(config.get("ENGINE") in (None, "django.db.backends.dummy")
                            for config in settings.DATABASES.values()))
        self.assertNotIn('django.contrib.auth', settings.INSTALLED_APPS)
        self.assertNotIn('django.contrib.admin', settings.INSTALLED_APPS)
        self.assertNotIn('django.contrib.sessions', settings.INSTALLED_APPS)
        self.assertIsNone(settings.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertFalse(settings.DEBUG)
        self.assertFalse(settings.APPEND_SLASH)
        self.assertNotIn('*', settings.ALLOWED_HOSTS)
        self.assertIsNone(settings.REST_FRAMEWORK['UNAUTHENTICATED_USER'])

    def test_fixture_cli_uses_django_asgi(self):
        from robingraph.cli import main
        with (patch('sys.argv', ['robingraph', 'serve-fixture']),
              patch('robingraph.cli.load_local_environment'),
              patch('robingraph.cli.configure_tracing'),
              patch('uvicorn.run') as run,
              redirect_stdout(StringIO()), redirect_stderr(StringIO())):
            self.assertEqual(0, main())
        self.assertEqual('robingraph.django_api.asgi:application', run.call_args.args[0])

    def test_native_entrypoint_does_not_import_fastapi_or_starlette(self):
        result = subprocess.run([sys.executable, "-c",
            "import sys; import robingraph.django_api.asgi; "
            "leaked = sorted(m for m in sys.modules if m.split('.')[0] in ('fastapi', 'starlette')); "
            "assert not leaked, leaked"],
            capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_fixture_serves_without_opening_database_connections(self):
        from asgi_client import TestClient
        from robingraph.api.drf import create_django_app
        with (patch('psycopg.connect', side_effect=AssertionError('unexpected PostgreSQL connection')),
              patch('neo4j.GraphDatabase.driver', side_effect=AssertionError('unexpected Neo4j connection'))):
            app = create_django_app()
            client = TestClient(app)
            self.assertEqual(200, client.get('/health').status_code)
            self.assertEqual(200, client.get('/chat').status_code)
            self.assertEqual(200, client.get('/openapi.json').status_code)


if __name__ == '__main__':
    unittest.main()
