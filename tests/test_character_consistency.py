import unittest
from src.normal_character_consistency import build


class CharacterConsistencyTests(unittest.TestCase):
    def test_builds_locked_character_and_scene_prompt(self):
        plan = {
            "character_bible": [{
                "name": "Milo", "age": "8", "face": "round face",
                "eyes": "large brown eyes", "hair": "short black hair",
                "wardrobe_lock": {"primary": "blue hoodie", "colors": ["blue"], "accessories": ["red cap"]}
            }],
            "scenes": [{"scene_id": 1, "subject": "Milo", "visual_prompt": "Milo walks through a forest"}]
        }
        bible, prompts = build(plan)
        self.assertEqual(bible["characters"][0]["name"], "Milo")
        self.assertIn("IDENTITY LOCK", prompts["scenes"][0]["prompt"])
        self.assertIn("blue hoodie", prompts["scenes"][0]["prompt"])
        self.assertIn("different face", prompts["scenes"][0]["negative_prompt"])

    def test_fallback_subjects_become_characters(self):
        plan = {"scenes": [{"subject": "Milo"}, {"subject": "Milo"}, {"subject": "Lumi"}]}
        bible, _ = build(plan)
        self.assertEqual([c["name"] for c in bible["characters"]], ["Milo", "Lumi"])


if __name__ == "__main__":
    unittest.main()
