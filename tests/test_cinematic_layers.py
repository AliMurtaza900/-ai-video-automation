import unittest
from src.normal_reference_engine import safe_name
from src.normal_scene_director import clamp_duration, fallback_plan


class CinematicLayerTests(unittest.TestCase):
    def test_safe_name_is_deterministic(self):
        self.assertEqual(safe_name("Milo The Fox!"), "milo_the_fox")
        self.assertEqual(safe_name("Milo The Fox!"), safe_name("Milo The Fox!"))

    def test_duration_is_bounded(self):
        self.assertEqual(clamp_duration(99), 3.5)
        self.assertEqual(clamp_duration(0.1), 0.8)

    def test_shot_plan_has_continuity_and_acting_fields(self):
        plan = {"scenes": [{"scene_id": 1, "subject": "Milo", "action": "walk", "emotion": "curious", "location": "forest"}]}
        result = fallback_plan(plan, {"characters": []}, {"characters": [], "scenes": []})
        shots = result["scenes"][0]["shots"]
        self.assertGreaterEqual(len(shots), 3)
        required = {"shot_type", "duration", "camera_movement", "character_action", "facial_expression", "gaze_eye_line", "body_gesture", "start_state", "end_state", "motion_prompt", "negative_prompt"}
        self.assertTrue(required.issubset(shots[0]))

    def test_reference_mode_falls_back_to_prompt_only_without_assets(self):
        from src.normal_reference_engine import build
        bible = {"characters": [{"id": "milo", "name": "Milo", "identity_lock": {}, "wardrobe_lock": {}}]}
        plan = {"scenes": [{"scene_id": 1, "subject": "Milo"}]}
        result = build(bible, plan)
        self.assertEqual(result["scenes"][0]["conditioning_mode"], "prompt_only")


if __name__ == "__main__":
    unittest.main()
