"""Run the existing video pipeline as an AI Factory production adapter.

The bridge keeps the existing generator/uploader intact while exposing the
stable GOAL/WORKSPACE -> JSON contract expected by AI Factory.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
WORKSPACE = Path(os.environ.get("WORKSPACE", str(ROOT / "factory_workspace")))
GOAL = os.environ.get("GOAL", "Create the best current AI automation YouTube Short")


def run(command: list[str]) -> None:
    env = os.environ.copy()
    # Keep the bridge stdout machine-readable. Individual pipeline logs are
    # retained in the workspace for diagnosis.
    log_dir = WORKSPACE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    name = command[-1].replace(".py", "")
    log = log_dir / f"{name}.log"
    with log.open("w", encoding="utf-8") as fh:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"pipeline step failed ({' '.join(command)}); see {log}")


def main() -> int:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Let the existing script generator use the Factory's job goal.
    os.environ["VIDEO_GOAL"] = GOAL

    # Remove only transient render artifacts. Keep youtube_upload.json so the
    # existing uploader can prove a duplicate upload is already complete after
    # an interrupted/retried Factory job.
    for path in (OUTPUT / "final-video.mp4", OUTPUT / "test-video.mp4"):
        path.unlink(missing_ok=True)

    run(["python", "src/main.py"])
    run(["python", "src/fetch_visuals_v2.py"])
    run(["python", "src/add_voice.py"])
    run(["python", "src/render_video.py"])

    rendered = OUTPUT / "test-video.mp4"
    voice = OUTPUT / "voice.mp3"
    final = OUTPUT / "final-video.mp4"
    if not rendered.is_file() or rendered.stat().st_size == 0:
        raise RuntimeError("render stage did not create output/test-video.mp4")
    if not voice.is_file() or voice.stat().st_size == 0:
        raise RuntimeError("voice stage did not create output/voice.mp3")

    run([
        "ffmpeg", "-y", "-i", str(rendered), "-i", str(voice),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(final),
    ])

    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("final video preparation failed")

    # Reuse the production uploader already present in this repository.
    os.environ.setdefault("YOUTUBE_TITLE", GOAL[:100])
    run(["python", "src/youtube_upload.py"])

    record = OUTPUT / "youtube_upload.json"
    if not record.is_file():
        raise RuntimeError("YouTube uploader completed without creating output/youtube_upload.json")
    data = json.loads(record.read_text(encoding="utf-8"))
    video_id = data.get("youtube_id")
    if not video_id:
        raise RuntimeError("YouTube upload record contains no youtube_id")

    result = {
        "status": "completed",
        "video": str(final.resolve()),
        "title": data.get("title") or os.environ["YOUTUBE_TITLE"],
        "description": os.environ.get("YOUTUBE_DESCRIPTION", ""),
        "video_id": video_id,
    }
    (WORKSPACE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
