from __future__ import annotations

from pathlib import Path
from .quality_loop import inspect_video, save_report


def produce_and_evaluate(render_fn, output: str | Path):
    """Run the renderer, inspect the resulting MP4, and return actionable feedback."""
    output = Path(output)
    render_fn()
    report = inspect_video(output)
    report_path = output.with_suffix(".quality.json")
    save_report(report, report_path)
    return report, report_path


def should_retry(report, attempt: int, max_attempts: int = 3) -> bool:
    return (not report.video_ok) and attempt < max_attempts
