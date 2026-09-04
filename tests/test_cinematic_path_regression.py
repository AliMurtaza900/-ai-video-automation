import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.normal_visual_critic as critic


class CinematicPathRegressionTests(unittest.TestCase):
    def test_critic_accepts_visuals_outside_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "director_plan.json"
            report = root / "visual_critic_report.json"
            visuals = root / "visuals"
            visuals.mkdir()
            (visuals / "visual_00.jpg").write_bytes(b"x" * 120_000)
            plan.write_text(json.dumps({"scenes": [{"subject": "ancient ocean", "visual_prompt": "ancient ocean"}]}), encoding="utf-8")
            with patch.object(critic, "PLAN", plan), patch.object(critic, "REPORT", report), patch.object(critic, "VISUALS", visuals), patch.object(critic, "gemini_score", return_value=None):
                result = critic.main()
            self.assertEqual(result["scenes"][0]["file"], str(visuals / "visual_00.jpg"))
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
