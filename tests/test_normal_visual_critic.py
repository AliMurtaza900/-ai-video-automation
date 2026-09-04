import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.normal_visual_critic as critic


class TestNormalVisualCritic(unittest.TestCase):
    def test_local_score_returns_bounded_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "visual_00.jpg"
            path.write_bytes(b"x" * 120_000)
            result = critic.local_score({"subject": "ancient ocean"}, path)
            self.assertTrue(0 <= result["score"] <= 100)
            self.assertIn("repair_query", result)

    def test_main_writes_report_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "director_plan.json"
            report = root / "visual_critic_report.json"
            visuals = root / "visuals"
            visuals.mkdir()
            (visuals / "visual_00.jpg").write_bytes(b"x" * 120_000)
            plan.write_text(json.dumps({"scenes": [{"subject": "ancient ocean", "visual_prompt": "ancient ocean"}]}))
            with patch.object(critic, "PLAN", plan), patch.object(critic, "REPORT", report), patch.object(critic, "VISUALS", visuals), patch.object(critic, "gemini_score", return_value=None):
                result = critic.main()
            self.assertEqual(len(result["scenes"]), 1)
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
