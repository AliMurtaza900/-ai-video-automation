import unittest

from pathlib import Path
import tempfile

import src.main as main
import src.render_video as render_video


class PipelineTests(unittest.TestCase):
    def test_script_validator_accepts_normal_script(self):
        script = (
            "This is a surprisingly useful fact about our world. "
            "It sounds impossible at first, but the explanation is simple and measurable. "
            "Once you see how the pieces fit together, the strange result makes sense. "
            "And that is what makes this fact so memorable. It is the kind of detail that sounds unbelievable until the explanation clicks into place, which makes it perfect for a short video."
        )
        main.validate_script(script)

    def test_caption_timing_parser_converts_numbers(self):
        original = render_video.OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            render_video.OUTPUT = Path(tmp)
            (render_video.OUTPUT / "caption_timing.txt").write_text(
                "0.000|1.250|Hello world\n1.250|2.500|Second line\n",
                encoding="utf-8",
            )
            self.assertEqual(
                render_video.load_caption_timings(),
                [(0.0, 1.25, "Hello world"), (1.25, 2.5, "Second line")],
            )
        render_video.OUTPUT = original

    def test_srt_timestamp_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = render_video.OUTPUT
            render_video.OUTPUT = Path(tmp)
            path = render_video.make_srt([(0.0, 1.234, "Hello")])
            self.assertIn("00:00:00,000 --> 00:00:01,234", path.read_text())
            render_video.OUTPUT = original

    def test_voice_generation_passes_selected_voice(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "add_voice.py").read_text(encoding="utf-8")
        self.assertIn("async def make_voice(text: str, output: Path, voice: str)", source)
        self.assertIn("asyncio.run(make_voice(text, audio_file, voice))", source)

    def test_quota_errors_skip_the_exhausted_model(self):
        class QuotaError(Exception):
            code = 429

            def __str__(self):
                return "429 RESOURCE_EXHAUSTED quota exceeded free_tier"

        self.assertTrue(main.is_quota_exhausted(QuotaError()))


if __name__ == "__main__":
    unittest.main()
