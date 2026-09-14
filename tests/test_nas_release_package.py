from __future__ import annotations

import hashlib
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "scripts" / "package_nas_release.sh"

SECRET_LIKE_SUFFIXES = (".pem", ".key")
SECRET_LIKE_SUBSTRINGS = ("credential", "secret")


def _looks_secret(path: str) -> bool:
    if path.endswith(".example"):
        return False
    name = path.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env."):
        return True
    lowered = path.lower()
    if any(lowered.endswith(suffix) for suffix in SECRET_LIKE_SUFFIXES):
        return True
    if any(token in lowered for token in SECRET_LIKE_SUBSTRINGS):
        return True
    return False


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_package_script(output_dir: Path, ref: str = "HEAD") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(PACKAGE_SCRIPT), "--ref", ref, "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )


class NasReleasePackageTest(unittest.TestCase):
    def test_script_is_valid_posix_sh(self) -> None:
        result = subprocess.run(
            ["sh", "-n", str(PACKAGE_SCRIPT)], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_never_touches_docker_deploy_or_the_network(self) -> None:
        text = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("docker", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("wget ", text)
        self.assertNotIn("git push", text)

    def test_refuses_an_output_directory_inside_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as inside:
            result = _run_package_script(Path(inside) / "release")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("outside the worktree", result.stderr)

    def test_refuses_an_unresolvable_ref(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            result = _run_package_script(Path(outside), ref="not-a-real-ref-xyz")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("not a valid commit", result.stderr)

    def test_package_twice_in_clean_destinations_is_byte_for_byte_deterministic(self) -> None:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        with tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
            out1_path, out2_path = Path(out1), Path(out2)
            result1 = _run_package_script(out1_path, ref=head)
            result2 = _run_package_script(out2_path, ref=head)

            self.assertEqual(0, result1.returncode, result1.stderr)
            self.assertEqual(0, result2.returncode, result2.stderr)

            archives1 = sorted(out1_path.glob("*.tar.gz"))
            archives2 = sorted(out2_path.glob("*.tar.gz"))
            manifests1 = sorted(out1_path.glob("*.manifest.txt"))
            manifests2 = sorted(out2_path.glob("*.manifest.txt"))
            self.assertEqual(1, len(archives1))
            self.assertEqual(1, len(archives2))
            self.assertEqual(1, len(manifests1))
            self.assertEqual(1, len(manifests2))

            # Deterministic naming: same commit -> same filenames.
            self.assertEqual(archives1[0].name, archives2[0].name)
            self.assertEqual(manifests1[0].name, manifests2[0].name)
            self.assertIn(head, archives1[0].name)

            # Deterministic bytes: same commit -> byte-identical archive and manifest.
            self.assertEqual(archives1[0].read_bytes(), archives2[0].read_bytes())
            self.assertEqual(manifests1[0].read_text(), manifests2[0].read_text())

            self.assertEqual(_sha256_of(archives1[0]), _sha256_of(archives2[0]))

    def test_manifest_records_source_commit_and_matching_archive_checksum(self) -> None:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        with tempfile.TemporaryDirectory() as out:
            out_path = Path(out)
            result = _run_package_script(out_path, ref=head)
            self.assertEqual(0, result.returncode, result.stderr)

            manifest_path = next(out_path.glob("*.manifest.txt"))
            archive_path = next(out_path.glob("*.tar.gz"))
            manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()

            fields = dict(
                line.split("=", 1) for line in manifest_lines if "=" in line and line != "---"
            )
            self.assertEqual(head, fields["source_commit"])
            self.assertEqual(archive_path.name, fields["archive"])
            self.assertEqual(_sha256_of(archive_path), fields["archive_sha256"])

            file_lines = manifest_lines[manifest_lines.index("---") + 1 :]
            self.assertEqual(int(fields["file_count"]), len(file_lines))
            self.assertGreater(len(file_lines), 0)
            for line in file_lines:
                checksum, path = line.split("  ", 1)
                self.assertEqual(64, len(checksum))
                int(checksum, 16)  # must be valid hex
                self.assertFalse(
                    _looks_secret(path), f"manifest lists a secret-like path: {path}"
                )

    def test_archive_contains_no_secret_like_members(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            out_path = Path(out)
            result = _run_package_script(out_path)
            self.assertEqual(0, result.returncode, result.stderr)

            archive_path = next(out_path.glob("*.tar.gz"))
            with tarfile.open(archive_path, "r:gz") as archive:
                names = archive.getnames()
            self.assertGreater(len(names), 0)
            for name in names:
                relative = name.split("/", 1)[1] if "/" in name else name
                if not relative:
                    continue
                self.assertFalse(
                    _looks_secret(relative), f"archive contains a secret-like member: {name}"
                )
            self.assertTrue(any(n.endswith("Dockerfile") for n in names))
            self.assertTrue(any(n.endswith("compose.nas.yml") for n in names))
            self.assertTrue(any(n.endswith("scripts/deploy_nas.sh") for n in names))

    def test_uncommitted_worktree_changes_are_never_included(self) -> None:
        # The archive comes only from the git object database for the given
        # commit, so local-only changes (e.g. a populated secret file sitting
        # in the worktree) must never reach the archive.
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        sentinel = ROOT / ".env.nas.package-test-sentinel"
        self.assertFalse(sentinel.exists(), "sentinel file unexpectedly pre-exists")
        sentinel.write_text("ROBINGRAPH_TEST_SECRET=should-never-be-packaged\n", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as out:
                out_path = Path(out)
                result = _run_package_script(out_path, ref=head)
                self.assertEqual(0, result.returncode, result.stderr)

                archive_path = next(out_path.glob("*.tar.gz"))
                with tarfile.open(archive_path, "r:gz") as archive:
                    names = archive.getnames()
                self.assertFalse(any("package-test-sentinel" in n for n in names))
        finally:
            sentinel.unlink()


if __name__ == "__main__":
    unittest.main()
