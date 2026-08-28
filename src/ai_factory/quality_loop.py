from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import subprocess


@dataclass
class QualityReport:
    video_ok: bool
    duration: float
    width: int
    height: int
    fps: float
    audio_present: bool
    audio_db: float | None
    issues: list[str]
    recommendations: list[str]


def inspect_video(path: str | Path) -> QualityReport:
    path = Path(path)
    if not path.exists() or path.stat().st_size < 500_000:
        return QualityReport(False, 0, 0, 0, 0, False, None, ["missing_or_tiny_video"], ["rerender"])

    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    data = json.loads(subprocess.check_output(cmd, text=True))
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    issues: list[str] = []
    recs: list[str] = []
    if not video:
        issues.append("no_video_stream")
    width = int(video.get("width", 0)) if video else 0
    height = int(video.get("height", 0)) if video else 0
    if (width, height) != (1280, 720):
        issues.append("wrong_resolution"); recs.append("render_at_1280x720")
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    fps_text = (video or {}).get("r_frame_rate", "0/1")
    n, d = (fps_text.split("/") + ["1"])[:2]
    fps = float(n) / float(d or 1)
    if fps < 23:
        issues.append("low_fps"); recs.append("render_at_24fps_or_higher")
    audio_present = audio is not None
    if not audio_present:
        issues.append("missing_audio"); recs.append("regenerate_narration")
    report = QualityReport(not issues, duration, width, height, fps, audio_present, None, issues, recs)
    return report


def save_report(report: QualityReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
