"""Offline checks that generators reuse images saved in a different format.

Gemini may return JPEG when PNG was requested, so a previous (possibly interrupted)
run can leave stressor-x.jpg where the generator expects stressor-x.png.

Run with: python3 -B -m unittest discover -s _config/scripts/image-generation -p 'test_*.py'
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from generate_customer_icons_gemini_nanobanana_api import find_existing_image
import generate_residuality_images_gemini_nanobanana_api as residuality


class FindExistingImageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="productscape-image-formats-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_prefers_the_requested_path(self):
        (self.root / "a.png").write_bytes(b"png")
        (self.root / "a.jpg").write_bytes(b"jpg")
        self.assertEqual(find_existing_image(self.root / "a.png"), self.root / "a.png")

    def test_falls_back_to_another_format(self):
        (self.root / "a.jpg").write_bytes(b"jpg")
        self.assertEqual(find_existing_image(self.root / "a.png"), self.root / "a.jpg")

    def test_ignores_empty_files_and_returns_the_requested_path_when_missing(self):
        (self.root / "a.jpg").write_bytes(b"")
        self.assertEqual(find_existing_image(self.root / "a.png"), self.root / "a.png")

    def test_residuality_reuses_an_unlinked_jpeg(self):
        residuality_dir = self.root / "demo" / "residuality"
        (residuality_dir / "media").mkdir(parents=True)
        (residuality_dir / "media" / "stressor-outage.jpg").write_bytes(b"jpg")
        path = residuality_dir / "residuality.json"
        path.write_text(json.dumps({
            "metadata": {"title": "Demo"},
            "stressors": [{"id": "outage", "name": "Outage"}],
        }))

        targets, _ = residuality.build_targets_for_file(path, "png")

        self.assertEqual(targets[0].image_path.name, "stressor-outage.jpg")
        self.assertEqual(targets[0].media_src, "media/stressor-outage.jpg")


if __name__ == "__main__":
    unittest.main()
