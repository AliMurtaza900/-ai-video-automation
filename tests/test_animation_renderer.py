import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.animation_renderer import load_bible, render_bible
from src.kids_animation_studio import build_sample_poem


class AnimationRendererTests(unittest.TestCase):
    def test_missing_backend_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            bible_path = Path(tmp) / "bible.json"
            bible_path.write_text(json.dumps(build_sample_poem().to_dict()), encoding="utf-8")
            with patch.dict(os.environ, {"AI_ANIMATION_COMMAND": ""}, clear=False):
                with self.assertRaises(RuntimeError):
                    render_bible(bible_path, Path(tmp) / "scenes")

    def test_bible_loader_rejects_empty_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_bible(path)


if __name__ == "__main__":
    unittest.main()
