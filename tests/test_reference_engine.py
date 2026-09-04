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

    def test_hash_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.png"
            ref.write_bytes(b"reference")
            first = sha256(ref)
            self.assertEqual(first, sha256(ref))
            self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
