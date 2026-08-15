import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.factory_bridge import load_verified_upload_record


class FactoryBridgeValidationTests(unittest.TestCase):
    def test_accepts_matching_upload_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube_upload.json"
            expected = hashlib.sha256(b"video").hexdigest()
            path.write_text(json.dumps({"sha256": expected, "youtube_id": "abc123", "title": "Test"}), encoding="utf-8")
            data = load_verified_upload_record(path, expected)
            self.assertEqual(data["youtube_id"], "abc123")

    def test_rejects_stale_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube_upload.json"
            path.write_text(json.dumps({"sha256": "old", "youtube_id": "abc123"}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_verified_upload_record(path, "new")

    def test_rejects_missing_video_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube_upload.json"
            path.write_text(json.dumps({"sha256": "same"}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_verified_upload_record(path, "same")

    def test_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube_upload.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_verified_upload_record(path, "same")


if __name__ == "__main__":
    unittest.main()
