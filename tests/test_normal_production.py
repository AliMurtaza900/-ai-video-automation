import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from src import normal_production_engine as engine
from src import normal_cinematic_renderer as cinematic
from src import normal_motion_engine as motion


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

    def test_motion_selection_is_deterministic(self):
        scene = {"shot": "wide landscape", "camera_motion": "slow drift", "action": "show the horizon"}
        self.assertEqual(cinematic.motion_for(scene, 1), "pan_right")
        self.assertEqual(cinematic.motion_for(scene, 2), "pan_left")

    def test_depth_frame_preserves_vertical_size(self):
        image = Image.new("RGB", (1400, 2200), (40, 50, 70))
        frame = cinematic.depth_frame(image, 0.5, "push_in", 1)
        self.assertEqual(frame.size, (cinematic.WIDTH, cinematic.HEIGHT))
        self.assertEqual(frame.mode, "RGB")

    def test_motion_engine_media_types(self):
        self.assertIn(".mp4", motion.VIDEO_EXTS)
        self.assertIn(".jpg", motion.IMAGE_EXTS)
        self.assertNotEqual(motion.VIDEO_EXTS, motion.IMAGE_EXTS)


if __name__ == "__main__":
    unittest.main()
