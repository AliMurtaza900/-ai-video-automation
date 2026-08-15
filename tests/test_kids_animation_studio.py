import json
import tempfile
import unittest
from pathlib import Path

from src.kids_animation_studio import build_sample_poem, write_bible


class KidsAnimationStudioTests(unittest.TestCase):
    def test_bible_has_consistent_characters_and_motion(self):
        bible = build_sample_poem()
        names = {c.name for c in bible.characters}
        self.assertGreaterEqual(len(bible.scenes), 5)
        self.assertTrue(all(set(s.characters) <= names for s in bible.scenes))
        self.assertTrue(all(len(s.animation_beats) >= 3 for s in bible.scenes))
        self.assertTrue(all(s.duration_seconds > 0 for s in bible.scenes))

    def test_bible_is_deterministic_and_serializable(self):
        a = build_sample_poem()
        b = build_sample_poem()
        self.assertEqual(a.digest(), b.digest())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bible.json"
            digest = write_bible(output, a)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(digest, a.digest())
            self.assertEqual(data["title"], "Milo and the Little Flower")
            self.assertEqual(len(data["scenes"]), 5)


if __name__ == "__main__":
    unittest.main()
