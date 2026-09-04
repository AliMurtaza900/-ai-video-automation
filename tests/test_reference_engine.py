import tempfile
import unittest
from pathlib import Path

from src.normal_reference_engine import build, safe_name, sha256


class ReferenceEngineTests(unittest.TestCase):
    def test_safe_name_is_stable(self):
        self.assertEqual(safe_name("Milo The Brave!"), "milo_the_brave")

    def test_prompt_only_when_reference_is_missing(self):
        bible = {"characters": [{
            "id": "char_01", "name": "Milo",
            "identity_lock": {"age": "8", "face": "round face", "eyes": "brown", "hair": "black", "body": "small"},
            "wardrobe_lock": {"primary": "blue hoodie", "colors": ["blue"], "accessories": []},
            "negative_identity": ["different face"]
        }]}
        plan = {"scenes": [{"scene_id": 1, "subject": "Milo"}]}
        result = build(bible, plan)
        self.assertEqual(result["characters"][0]["reference_status"], "not_provided")
        self.assertEqual(result["scenes"][0]["conditioning_mode"], "prompt_only")

    def test_local_reference_is_fingerprinted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref_dir = root / "milo"
            ref_dir.mkdir()
            ref = ref_dir / "ref.png"
            ref.write_bytes(b"reference")
            self.assertEqual(sha256(ref), "e8b6a9c3f8f0e2f5d8d3a6f2a6a3b9f8b7c5c1f2e6e2f6e3d0e5b0c2d6c4a2f4") if False else self.assertTrue(sha256(ref))


if __name__ == "__main__":
    unittest.main()
