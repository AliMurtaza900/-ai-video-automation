from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import src.premium_cartoon_engine as engine


class CartoonEngineTests(unittest.TestCase):
    def test_episode_has_continuity_and_unique_beats(self):
        self.assertGreaterEqual(len(engine.BEATS), 10)
        kinds = [kind for kind, _ in engine.BEATS]
        self.assertEqual(len(kinds), len(set(kinds)))
        text = " ".join(line for _, line in engine.BEATS).lower()
        for required in ("milo", "lumi", "flower", "stream", "sun"):
            self.assertIn(required, text)
        self.assertEqual(kinds[-2:], ["sunset", "night"])

    def test_poem_and_story_match_scene_count(self):
        self.assertEqual(len(engine.POEM), len(engine.BEATS))
        self.assertEqual(len(engine.STORY), len(engine.BEATS))

    def test_inputs_are_rejected_outside_production_range(self):
        with patch.dict(os.environ, {"CONTENT_TYPE": "invalid", "TOPIC": "x", "DURATION": "1"}, clear=False):
            with self.assertRaises(RuntimeError):
                engine.main()

    def test_zero_cost_engine_does_not_require_paid_provider(self):
        source = Path(engine.__file__).read_text(encoding="utf-8")
        for forbidden in ("GEMINI_API_KEY", "VEO_MODEL", "OPENAI_API_KEY", "ELEVENLABS_API_KEY"):
            self.assertNotIn(forbidden, source)

    def test_wrapper_points_to_premium_engine(self):
        wrapper = Path(__file__).parents[1] / "src" / "kids_animation_production.py"
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("from premium_cartoon_engine import main", text)

    def test_premium_output_targets_hd(self):
        self.assertEqual((engine.W, engine.H), (1280, 720))
        self.assertEqual(engine.FPS, 24)


if __name__ == "__main__":
    unittest.main()
