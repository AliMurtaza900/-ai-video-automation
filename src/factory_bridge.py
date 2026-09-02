"""Run the existing video pipeline as an AI Factory production adapter."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
WORKSPACE = Path(os.environ.get("WORKSPACE", str(ROOT / "factory_workspace")))
GOAL = os.environ.get("GOAL") or os.environ.get("VIDEO_GOAL") or "Create the best current AI automation YouTube Short"
UPLOAD_RECORD = OUTPUT / "youtube_upload.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_upload_record(record_path: Path, expected_hash: str) -> dict:
    """Return a valid upload record only when it belongs to this exact video."""
    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("YouTube upload record is missing or invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("YouTube upload record must contain a JSON object")
    video_id = data.get("youtube_id")
    if not isinstance(video_id, str) or not video_id.strip():
        raise RuntimeError("YouTube upload record contains no youtube_id")
    if data.get("sha256") != expected_hash:
        raise RuntimeError("YouTube upload record does not match the current final video")
    return data


def run(command: list[str]) -> None:
    """Run a pipeline step and keep bridge stdout machine-readable."""
    env = os.environ.copy()
    log_dir = WORKSPACE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    name = Path(command[-1]).stem or "command"
    log = log_dir / f"{name}.log"
    with log.open("w", encoding="utf-8") as fh:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"pipeline step failed ({' '.join(command)}); see {log}")


def main() -> int:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    os.environ["VIDEO_GOAL"] = GOAL

    # Never delete youtube_upload.json: the uploader uses its matching SHA-256
    # record to make retries idempotent. All other transient outputs are rebuilt.
    for path in (OUTPUT / "final-video.mp4", OUTPUT / "test-video.mp4", OUTPUT / "voice.mp3", OUTPUT / "caption_timing.txt"):
        path.unlink(missing_ok=True)

    python = sys.executable
    run([python, "src/main.py"])
    run([python, "src/fetch_visuals.py"])
    run([python, "src/add_voice.py"])
    run([python, "src/render_video.py"])

    rendered = OUTPUT / "test-video.mp4"
    voice = OUTPUT / "voice.mp3"
    final = OUTPUT / "final-video.mp4"
    if not rendered.is_file() or rendered.stat().st_size == 0:
        raise RuntimeError("render stage did not create output/test-video.mp4")
    if not voice.is_file() or voice.stat().st_size == 0:
        raise RuntimeError("voice stage did not create output/voice.mp3")

    run(["ffmpeg", "-y", "-i", str(rendered), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(final)])
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("final video preparation failed")

    expected_hash = sha256_file(final)
    os.environ.setdefault("YOUTUBE_TITLE", GOAL[:100])
    run([python, "src/youtube_upload.py"])

    data = load_verified_upload_record(UPLOAD_RECORD, expected_hash)
    result = {
        "status": "completed",
        "video": str(final.resolve()),
        "title": data.get("title") or os.environ["YOUTUBE_TITLE"],
        "description": os.environ.get("YOUTUBE_DESCRIPTION", ""),
        "video_id": data["youtube_id"],
        "sha256": expected_hash,
    }
    (WORKSPACE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
