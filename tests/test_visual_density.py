import unittest

from src.fetch_visuals import scene_sentences


class VisualDensityTests(unittest.TestCase):
    def test_long_script_gets_more_than_twelve_visual_beats(self):
        script = " ".join(
            f"This is narration sentence number {i} with enough words to create a distinct visual beat."
            for i in range(1, 9)
        )
        scenes = scene_sentences(script)
        self.assertGreater(len(scenes), 12)
        self.assertLessEqual(len(scenes), 18)


if __name__ == "__main__":
    unittest.main()
