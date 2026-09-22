from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from robingraph.cli import main
from robingraph.ingest.postgres import PostgresSettings


class IngestCliTest(unittest.TestCase):
    def invoke(self, *args: str) -> tuple[int, str, str]:
        out, err = StringIO(), StringIO()
        with (
            patch("sys.argv", ["robingraph", *args]),
            patch("robingraph.cli.load_local_environment"),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = main()
        return code, out.getvalue(), err.getvalue()

    def test_serve_ingest_explicitly_injects_postgres_store(self) -> None:
        settings = PostgresSettings(
            host="test-db.invalid",
            port=5432,
            database="robingraph_test",
            schema="ingest",
            username="test-user",
            password="test-password",
            sslmode="require",
        )
        with (
            patch.dict("os.environ", {"ROBINGRAPH_INGEST_INTERNAL_TOKEN": "test-token"}),
            patch(
                "robingraph.ingest.postgres.PostgresSettings.from_environment",
                return_value=settings,
            ),
            patch("uvicorn.run") as run,
        ):
            code, out, err = self.invoke("serve-ingest")

        self.assertEqual((0, "", ""), (code, out, err))
        app = run.call_args.args[0]
        self.assertIn("/internal/v1/ingest/begin", app.openapi()["paths"])
        self.assertEqual("127.0.0.1", run.call_args.kwargs["host"])
        self.assertEqual(8001, run.call_args.kwargs["port"])

    def test_serve_ingest_fails_closed_without_internal_token(self) -> None:
        settings = PostgresSettings(
            host="test-db.invalid",
            port=5432,
            database="robingraph_test",
            schema="ingest",
            username="test-user",
            password="test-password",
            sslmode="require",
        )
        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "robingraph.ingest.postgres.PostgresSettings.from_environment",
                return_value=settings,
            ),
            patch("uvicorn.run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "ROBINGRAPH_INGEST_INTERNAL_TOKEN"):
                self.invoke("serve-ingest")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
