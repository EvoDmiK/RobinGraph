"""Exercise the generator and integrity gate without rewriting versioned data."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from robingraph.fixture import default_fixture_root, load_fixture


class FixtureReproducibilityTest(unittest.TestCase):
    def test_regeneration_matches_committed_bytes_on_this_platform(self) -> None:
        committed = default_fixture_root()
        # Check the checkout first: regenerating it here would hide EOL corruption.
        load_fixture(committed)
        manifest = json.loads((committed / "fixture-manifest.json").read_text(encoding="utf-8"))
        generator = Path(__file__).resolve().parents[1] / "scripts" / "generate_eval_fixture.py"
        with tempfile.TemporaryDirectory(prefix="robingraph-generate-") as directory:
            generated = Path(directory) / "v1"
            subprocess.run(
                [sys.executable, str(generator), "--output", str(generated)],
                check=True, capture_output=True, text=True,
            )
            load_fixture(generated)
            for relative in ["fixture-manifest.json", *[entry["path"] for entry in manifest["files"]]]:
                with self.subTest(path=relative):
                    expected = (committed / relative).read_bytes()
                    self.assertNotIn(b"\r", expected)
                    self.assertEqual(expected, (generated / relative).read_bytes())

    def test_integrity_gate_rejects_content_and_line_ending_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="robingraph-corrupt-") as directory:
            copied = Path(directory) / "v1"
            shutil.copytree(default_fixture_root(), copied)
            target = copied / "input" / "taxonomy.jsonl"
            original = target.read_bytes()
            for corrupted in (original + b" ", original.replace(b"\n", b"\r\n")):
                with self.subTest(kind="content" if corrupted.endswith(b" ") else "CRLF"):
                    target.write_bytes(corrupted)
                    with self.assertRaisesRegex(ValueError, "Fixture checksum mismatch"):
                        load_fixture(copied)


if __name__ == "__main__":
    unittest.main()
