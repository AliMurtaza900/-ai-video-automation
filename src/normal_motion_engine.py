"""Motion engine for the isolated normal-video pipeline.

Priority order per scene:
1. Existing free-source video clips (real motion).
2. Optional external I2V command via MOTION_ENGINE_COMMAND.
3. Procedural Pillow/FFmpeg cinematic animation fallback.

The kids-animation engines are intentionally untouched.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PLAN = OUTPUT / "normal_production" / "director_plan.json"
VISUALS = ROOT / "assets" / "visuals"
WORK = OUTPUT / "normal_production" / "motion_scenes"
MANIFEST = OUTPUT / "normal_production" / "motion_manifest.json"
FINAL = OUTPUT / "cinematic-video.mp4"
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".ogv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def normalize_video(source: Path, target: Path, seconds: float = 4.0) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source),
        "-t", str(max(1.8, min(8.0, seconds))),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", str(target),
    ])


def run_external_i2v(image: Path, target: Path, scene: dict, index: int) -> bool:
    """Run an optional local/free I2V backend; failure falls back automatically."""
    template = os.getenv("MOTION_ENGINE_COMMAND", "").strip()
    if not template:
        return False
    values = {
        "input": str(image),
        "output": str(target),
        "prompt": str(scene.get("visual_prompt", scene.get("action", "cinematic motion"))),
        "scene": str(index),
    }
    try:
        command = template.format(**values)
        print(f"Running optional I2V backend for scene {index}: {command}")
        subprocess.run(shlex.split(command), check=True, cwd=ROOT)
        return target.exists() and target.stat().st_size > 0
    except Exception as exc:
        print(f"Optional I2V backend failed for scene {index}: {exc}; using procedural fallback")
        target.unlink(missing_ok=True)
        return False


def concat(clips: list[Path]) -> None:
    if not clips:
        raise RuntimeError("No motion clips were produced")
    manifest = WORK / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in clips) + "\n", encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(FINAL),
    ])


def main() -> None:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json is missing")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    if not scenes or not VISUALS.exists():
        raise RuntimeError("Need director scenes and visual assets")

    WORK.mkdir(parents=True, exist_ok=True)
    media = sorted(p for p in VISUALS.iterdir() if p.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS)
    if not media:
        raise RuntimeError("No visual assets found")
    images = [p for p in media if p.suffix.lower() in IMAGE_EXTS]
    videos = [p for p in media if p.suffix.lower() in VIDEO_EXTS]

    clips: list[Path] = []
    records = []
    for i, scene in enumerate(scenes, 1):
        target = WORK / f"scene_{i:03d}.mp4"
        numbered = [p for p in media if p.stem == f"visual_{i-1:02d}"]
        source = numbered[0] if numbered else (videos[i - 1] if i <= len(videos) else (images[(i - 1) % len(images)] if images else media[0]))

        if source.suffix.lower() in VIDEO_EXTS:
            normalize_video(source, target, 4.0)
            backend = "free_source_video"
        elif run_external_i2v(source, target, scene, i):
            backend = "external_i2v"
        else:
            from normal_cinematic_renderer import render_scene, scene_seconds
            seconds = scene_seconds(OUTPUT / "voice.mp3", len(scenes))
            render_scene(source, target, scene, i, seconds)
            backend = "procedural_fallback"

        clips.append(target)
        records.append({"scene": i, "source": str(source.relative_to(ROOT)), "backend": backend, "output": str(target.relative_to(ROOT))})
        print(f"Motion scene {i}: {backend} <- {source.name}")

    concat(clips)
    report = {
        "backend_order": ["free_source_video", "external_i2v", "procedural_fallback"],
        "scenes": records,
        "final": str(FINAL.relative_to(ROOT)),
    }
    MANIFEST.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Motion engine ready: {FINAL}")


if __name__ == "__main__":
    main()
