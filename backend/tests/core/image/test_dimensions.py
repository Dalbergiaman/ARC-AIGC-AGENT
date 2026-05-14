from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from config import settings
from core.image.dimensions import (
    aspect_ratio_string,
    canvas_from_image_url,
    default_canvas,
    normalize_canvas_size,
    read_image_size,
)


class TestImageDimensions(unittest.TestCase):
    def test_normalize_landscape_to_2k_long_edge(self) -> None:
        self.assertEqual(normalize_canvas_size(400, 200), (2048, 1024))

    def test_normalize_portrait_to_2k_long_edge(self) -> None:
        self.assertEqual(normalize_canvas_size(100, 200), (1024, 2048))

    def test_normalize_square_to_2k_canvas(self) -> None:
        self.assertEqual(normalize_canvas_size(64, 64), (2048, 2048))

    def test_normalize_rounds_to_provider_friendly_multiple(self) -> None:
        self.assertEqual(normalize_canvas_size(300, 200), (2048, 1344))

    def test_aspect_ratio_string_reduces_dimensions(self) -> None:
        self.assertEqual(aspect_ratio_string(400, 200), "2:1")
        self.assertEqual(aspect_ratio_string(300, 200), "3:2")

    def test_read_image_size_supports_png_jpeg_and_webp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cases = [
                (root / "demo.png", "PNG"),
                (root / "demo.jpg", "JPEG"),
                (root / "demo.webp", "WEBP"),
            ]
            for path, image_format in cases:
                with self.subTest(image_format=image_format):
                    Image.new("RGB", (320, 180), color="white").save(path, format=image_format)
                    self.assertEqual(read_image_size(path), (320, 180))

    def test_canvas_from_local_upload_url_uses_image_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_upload_dir = settings.UPLOAD_DIR
            settings.UPLOAD_DIR = temp_dir
            try:
                path = Path(temp_dir) / "control.png"
                Image.new("RGB", (300, 200), color="white").save(path, format="PNG")

                canvas = canvas_from_image_url("/static/uploads/control.png")
            finally:
                settings.UPLOAD_DIR = original_upload_dir

        self.assertEqual(canvas.width, 2048)
        self.assertEqual(canvas.height, 1344)
        self.assertEqual(canvas.aspect_ratio, "3:2")
        self.assertEqual(canvas.source_width, 300)
        self.assertEqual(canvas.source_height, 200)
        self.assertFalse(canvas.used_default)

    def test_canvas_from_invalid_or_external_url_uses_default(self) -> None:
        self.assertEqual(canvas_from_image_url("https://example.com/control.png"), default_canvas())
        self.assertEqual(canvas_from_image_url("/static/uploads/missing.png"), default_canvas())


if __name__ == "__main__":
    unittest.main()
