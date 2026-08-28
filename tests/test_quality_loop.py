import unittest
from unittest.mock import patch
from pathlib import Path

from src.ai_factory.improver import improve_settings
from src.ai_factory.quality_loop import QualityReport


class QualityLoopTests(unittest.TestCase):
    def test_improver_repairs_common_failures(self):
        report = QualityReport(False, 60, 640, 360, 15, False, None, ["wrong_resolution", "low_fps", "missing_audio"], [])
        settings = improve_settings(report, {})
        self.assertEqual((settings["WIDTH"], settings["HEIGHT"]), (1280, 720))
        self.assertGreaterEqual(settings["FPS"], 24)
        self.assertTrue(settings["REGENERATE_AUDIO"])

    def test_attempt_is_incremented(self):
        report = QualityReport(False, 0, 0, 0, 0, False, None, ["missing_or_tiny_video"], [])
        self.assertEqual(improve_settings(report, {})["QUALITY_ATTEMPT"], 1)
