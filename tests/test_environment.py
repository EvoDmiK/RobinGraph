from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from robingraph.environment import load_local_environment


class LocalEnvironmentTest(unittest.TestCase):
    def test_loads_key_values_without_overriding_shell_environment(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / ".env"
            path.write_text(
                "# Local credentials\n"
                "NEO4J_URI=bolt://localhost:7687\n"
                "export ROBINGRAPH_JINA_API_KEY=test-key\n"
                "EXISTING=dotenv-value\n",
                encoding="utf-8",
            )
            environ = {"EXISTING": "shell-value"}
            self.assertTrue(load_local_environment(path, environ=environ))

        self.assertEqual("bolt://localhost:7687", environ["NEO4J_URI"])
        self.assertEqual("test-key", environ["ROBINGRAPH_JINA_API_KEY"])
        self.assertEqual("shell-value", environ["EXISTING"])

    def test_missing_file_is_ignored_and_invalid_lines_fail(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / ".env"
            self.assertFalse(load_local_environment(path, environ={}))
            path.write_text("NOT_VALID\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "KEY=VALUE"):
                load_local_environment(path, environ={})


if __name__ == "__main__":
    unittest.main()
