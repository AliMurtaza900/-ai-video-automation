import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import normal_production_engine as engine


class NormalProductionTests(unittest.TestCase):
    def test_local_storyboard_has_scenes(self):
        script = "Venus spins slowly. A day can be longer than its year. This strange world moves differently."
        plan = engine.local_storyboard(script)
        self.assertTrue(plan["scenes"])
        self.assertLessEqual(len(plan["scenes"]), engine.MAX_SCENES)
        for scene in plan["scenes"]:
            self.assertTrue(scene["visual_prompt"])
            self.assertTrue(scene["camera_motion"])
            self.assertTrue(scene["lighting"])

    def test_validate_repairs_missing_fields(self):
        plan = {"scenes": [{}]}
        result = engine.validate(plan, "A surprising fact.")
        self.assertEqual(result["scenes"][0]["scene_id"], 1)
        self.assertTrue(result["scenes"][0]["visual_prompt"])
        self.assertIsInstance(result["scenes"][0]["sfx"], list)


if __name__ == "__main__":
    unittest.main()
