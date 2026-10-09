from __future__ import annotations

import os
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.fixture import load_fixture
from robingraph.retrieval.fixture_repository import FixtureRepository

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
ICON_PATHS = (
    ("/favicon.ico", "image/x-icon"),
    ("/static/favicon.ico", "image/x-icon"),
    ("/static/favicon-32.png", "image/png"),
    ("/static/favicon-192.png", "image/png"),
    ("/static/apple-touch-icon.png", "image/png"),
)
ICON_HREFS = (
    'href="/favicon.ico"',
    'href="/static/favicon-32.png"',
    'href="/static/favicon-192.png"',
    'rel="apple-touch-icon" href="/static/apple-touch-icon.png"',
)


class FaviconTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The real packaged static directory, not a temporary stand-in.
        cls.client = TestClient(create_app(FixtureRepository(load_fixture())))

    def test_icons_are_served_with_media_types_and_cache_header(self) -> None:
        for path, media_type in ICON_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
                self.assertEqual(media_type, response.headers["content-type"])
                self.assertIn("max-age", response.headers["cache-control"])
                self.assertGreater(len(response.content), 100)

    def test_png_icons_have_expected_dimensions(self) -> None:
        expected = {"/static/favicon-32.png": 32, "/static/favicon-192.png": 192, "/static/apple-touch-icon.png": 180}
        for path, size in expected.items():
            with self.subTest(path=path):
                content = self.client.get(path).content
                self.assertTrue(content.startswith(PNG_MAGIC))
                width, height = struct.unpack(">II", content[16:24])
                self.assertEqual((size, size), (width, height))

    def test_ico_contains_small_sizes_for_browser_tabs(self) -> None:
        content = self.client.get("/favicon.ico").content
        reserved, kind, count = struct.unpack("<HHH", content[:6])
        self.assertEqual((0, 1), (reserved, kind))
        sizes = {content[6 + 16 * index] or 256 for index in range(count)}
        self.assertTrue({16, 32}.issubset(sizes))

    def test_chat_and_birds_pages_link_the_icons(self) -> None:
        for path in ("/", "/chat", "/birds"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
                for href in ICON_HREFS:
                    self.assertIn(href, response.text)

    def test_only_allowlisted_icon_names_are_served(self) -> None:
        for path in ("/static/favicon.png", "/static/robin.png", "/static/apple-touch-icon.ico"):
            with self.subTest(path=path):
                self.assertEqual(404, self.client.get(path).status_code)

    def test_missing_icon_is_a_plain_404_and_does_not_break_the_chat_ui(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<!doctype html><body>RobinGraph 채팅</body>", encoding="utf-8")
            (root / "chat.js").write_text("console.log('chat');", encoding="utf-8")
            (root / "styles.css").write_text("body { color: #123; }", encoding="utf-8")
            client = TestClient(create_app(FixtureRepository(load_fixture()), static_dir=root))
            for path in ("/favicon.ico", "/static/favicon-32.png"):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(404, response.status_code)
                    self.assertNotIn(str(root), response.text)
            self.assertEqual(200, client.get("/chat").status_code)

    def test_empty_icon_file_is_not_served(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "favicon.ico").write_bytes(b"")
            client = TestClient(create_app(FixtureRepository(load_fixture()), static_dir=root))
            self.assertEqual(404, client.get("/favicon.ico").status_code)

    def test_test_deployment_serves_distinct_blue_icons_under_the_same_urls(self) -> None:
        for path, media_type in ICON_PATHS:
            with self.subTest(path=path):
                with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": "prod"}):
                    prod = self.client.get(path)
                with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": "test"}):
                    test = self.client.get(path)
                self.assertEqual(200, test.status_code)
                self.assertEqual(media_type, test.headers["content-type"])
                self.assertNotEqual(prod.content, test.content, "TEST must not look like PROD")
                if media_type == "image/png":
                    width, height = struct.unpack(">II", test.content[16:24])
                    self.assertEqual(width, struct.unpack(">II", prod.content[16:24])[0])
                    self.assertEqual(width, height)

    def test_other_targets_keep_the_default_icons(self) -> None:
        with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": "test"}):
            test = self.client.get("/static/favicon-32.png").content
        for target in ("prod", "legacy"):
            with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": target}):
                self.assertNotEqual(test, self.client.get("/static/favicon-32.png").content)
        with patch.dict(os.environ, clear=False):
            os.environ.pop("ROBINGRAPH_DEPLOY_TARGET", None)
            self.assertNotEqual(test, self.client.get("/static/favicon-32.png").content)

    def test_variant_file_names_are_not_directly_served_and_a_missing_variant_falls_back(self) -> None:
        for path in ("/static/favicon-32-test.png", "/static/favicon-test.ico", "/static/apple-touch-icon-test.png"):
            with self.subTest(path=path):
                self.assertEqual(404, self.client.get(path).status_code)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "favicon.ico").write_bytes(b"\x00\x00\x01\x00default-icon")
            client = TestClient(create_app(FixtureRepository(load_fixture()), static_dir=root))
            with patch.dict(os.environ, {"ROBINGRAPH_DEPLOY_TARGET": "test"}):
                response = client.get("/favicon.ico")
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.content.endswith(b"default-icon"))

    def test_icons_are_included_in_package_data(self) -> None:
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"api/static/*.png"', pyproject)
        self.assertIn('"api/static/*.ico"', pyproject)


if __name__ == "__main__":
    unittest.main()
