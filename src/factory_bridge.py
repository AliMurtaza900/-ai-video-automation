"""Run the Kids Animation Studio pipeline as an AI Factory production adapter."""
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
GOAL = os.environ.get("GOAL") or os.environ.get("VIDEO_GOAL") or "Create an original animated children's poem"
UPLOAD_RECORD = OUTPUT / "youtube_upload.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_upload_record(record_path: Path, expected_hash: str) -> dict:
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
    env = os.environ.copy()
    log_dir = WORKSPACE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    name = Path(command[1]).stem if len(command) > 1 else "command"
    log = log_dir / f"{name}.log"
    with log.open("w", encoding="utf-8") as fh:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"pipeline step failed ({' '.join(command)}); see {log}")


def main() -> int:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    os.environ["VIDEO_GOAL"] = GOAL

    # The new animation renderer must be explicitly configured. There is no
    # silent image/slideshow fallback for production children's content.
    if not os.environ.get("AI_ANIMATION_COMMAND", "").strip():
        raise RuntimeError("AI_ANIMATION_COMMAND is required for animated children's production")

    for path in (OUTPUT / "final-video.mp4", OUTPUT / "test-video.mp4", OUTPUT / "voice.mp3", OUTPUT / "caption_timing.txt"):
        path.unlink(missing_ok=True)

    python = sys.executable
    run([python, "src/kids_animation_studio.py", "--output", str(OUTPUT / "production-bible.json")])
    run([python, "src/animation_renderer.py", "--bible", str(OUTPUT / "production-bible.json"), "--output", str(OUTPUT / "animated-cartoon.mp4")])

    animated = OUTPUT / "animated-cartoon.mp4"
    if not animated.is_file() or animated.stat().st_size == 0:
        raise RuntimeError("animation renderer did not create animated-cartoon.mp4")

    # Existing audio/caption generation remains the publishing layer, but the
    # final video now comes from validated animated scene clips.
    run([python, "src/main.py"])
    run([python, "src/add_voice.py"])
    voice = OUTPUT / "voice.mp3"
    if not voice.is_file() or voice.stat().st_size == 0:
        raise RuntimeError("voice stage did not create output/voice.mp3")

    final = OUTPUT / "final-video.mp4"
    run(["ffmpeg", "-y", "-i", str(animated), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(final)])
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("final animated video preparation failed")

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
        "content_type": "animated_kids",
    }
    (WORKSPACE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
