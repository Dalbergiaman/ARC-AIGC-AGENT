import io
import tempfile
import unittest
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from config import settings
from services.storage_service import save_upload, validate_image_mime_type


class TestStorageService(unittest.IsolatedAsyncioTestCase):
    def test_validate_image_mime_type_rejects_unsupported_type(self):
        with self.assertRaises(ValueError):
            validate_image_mime_type("application/pdf")

    async def test_save_upload_local_writes_file_and_returns_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_storage = settings.STORAGE
            original_upload_dir = settings.UPLOAD_DIR
            settings.STORAGE = "local"
            settings.UPLOAD_DIR = temp_dir
            try:
                upload = UploadFile(
                    file=io.BytesIO(b"fake-image-bytes"),
                    filename="demo.png",
                    headers=Headers({"content-type": "image/png"}),
                )
                file_id, url = await save_upload(upload)
            finally:
                settings.STORAGE = original_storage
                settings.UPLOAD_DIR = original_upload_dir

            self.assertTrue(file_id)
            self.assertTrue(url.startswith("/static/uploads/"))

            filename = url.split("/static/uploads/")[1]
            file_path = Path(temp_dir) / filename
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), b"fake-image-bytes")


if __name__ == "__main__":
    unittest.main()
