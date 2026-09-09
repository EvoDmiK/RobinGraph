from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from robingraph.ingest.collection_points import load_collection_points


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


class CollectionPointTest(unittest.TestCase):
    def test_default_registry_selects_only_allowed_enabled_points(self) -> None:
        registry = load_collection_points()
        self.assertEqual("terra-claim-first", registry.selected_design)
        self.assertEqual(
            {
                "taxonomy-avilist-v2025b",
                "taxonomy-checklistbank-release",
                "traits-eltontraits-v1",
            },
            {point.collection_point_id for point in registry.select()},
        )
        self.assertTrue(all(point.collectable for point in registry.select()))

    def test_blocked_points_remain_visible_for_review(self) -> None:
        registry = load_collection_points()
        vegetation = registry.select(scope="vegetation", include_blocked=True)
        self.assertEqual(1, len(vegetation))
        self.assertFalse(vegetation[0].collectable)
        self.assertEqual("spatial_inference", vegetation[0].payload_mode)
        self.assertEqual("spatial_inference", vegetation[0].evidence_kind)

    def test_enabled_point_cannot_bypass_source_policy(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = json.loads((CONFIG / "source-registry.json").read_text(encoding="utf-8"))
            points = json.loads((CONFIG / "collection-points.json").read_text(encoding="utf-8"))
            altered = deepcopy(points)
            blocked = next(
                point for point in altered["collection_points"]
                if point["collection_point_id"] == "vegetation-ecobank-spatial-join"
            )
            blocked["enabled"] = True
            (root / "source-registry.json").write_text(json.dumps(sources), encoding="utf-8")
            (root / "collection-points.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "only allowed collection points may be enabled"):
                load_collection_points(root)

    def test_point_and_source_policy_must_match(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = json.loads((CONFIG / "source-registry.json").read_text(encoding="utf-8"))
            points = json.loads((CONFIG / "collection-points.json").read_text(encoding="utf-8"))
            altered = deepcopy(points)
            altered["collection_points"][0]["license_policy_status"] = "review_required"
            altered["collection_points"][0]["enabled"] = False
            (root / "source-registry.json").write_text(json.dumps(sources), encoding="utf-8")
            (root / "collection-points.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "enabled mismatch"):
                load_collection_points(root)

    def test_enabled_download_requires_a_pinned_sha256(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = json.loads((CONFIG / "source-registry.json").read_text(encoding="utf-8"))
            points = json.loads((CONFIG / "collection-points.json").read_text(encoding="utf-8"))
            altered = deepcopy(points)
            download = next(
                point for point in altered["collection_points"]
                if point["collection_point_id"] == "taxonomy-avilist-v2025b"
            )
            download["expected_sha256"] = None
            (root / "source-registry.json").write_text(json.dumps(sources), encoding="utf-8")
            (root / "collection-points.json").write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "enabled download requires expected_sha256"):
                load_collection_points(root)


if __name__ == "__main__":
    unittest.main()
