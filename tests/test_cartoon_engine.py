from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import src.cartoon_engine as engine


class CartoonEngineTests(unittest.TestCase):
    def test_episode_has_continuity_and_unique_beats(self):
        self.assertGreaterEqual(len(engine.EPISODE), 10)
        kinds = [kind for kind, _ in engine.EPISODE]
        self.assertEqual(len(kinds), len(set(kinds)))
        text = " ".join(line for _, line in engine.EPISODE).lower()
        # Validate the story semantically: the ending must contain a sunset/evening beat,
        # even when the prose uses a natural equivalent such as "sun sets".
        required_groups = {
            "milo": ("milo",),
            "lumi": ("lumi",),
            "flower": ("flower",),
            "stream": ("stream",),
            "sunset": ("sunset", "sun sets", "sunset/evening", "evening"),
        }
        for name, alternatives in required_groups.items():
            self.assertTrue(any(term in text for term in alternatives), f"missing story beat: {name}")

        self.assertEqual(kinds[-2:], ["sunset", "night"])
        self.assertIn("sun sets", engine.EPISODE[-2][1].lower())
        self.assertIn("goodnight", engine.EPISODE[-1][1].lower())

    def test_poem_and_story_match_scene_count(self):
        self.assertEqual(len(engine.POEM), len(engine.EPISODE))
        self.assertEqual(len(engine.STORY), len(engine.EPISODE))

    def test_inputs_are_rejected_outside_production_range(self):
        with patch.dict(os.environ, {"CONTENT_TYPE": "invalid", "TOPIC": "x", "DURATION": "1"}, clear=False):
            with self.assertRaises(RuntimeError):
                engine.main()

    def test_zero_cost_engine_does_not_require_paid_provider(self):
        source = Path(engine.__file__).read_text(encoding="utf-8")
        for forbidden in ("GEMINI_API_KEY", "VEO_MODEL", "OPENAI_API_KEY", "ELEVENLABS_API_KEY"):
            self.assertNotIn(forbidden, source)

    def test_wrapper_points_to_single_engine(self):
        wrapper = Path(__file__).parents[1] / "src" / "kids_animation_production.py"
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("from cartoon_engine import main", text)


if __name__ == "__main__":
    unittest.main()
