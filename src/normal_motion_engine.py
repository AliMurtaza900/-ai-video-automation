"""Motion orchestrator for the normal-video pipeline.

The normal pipeline now prefers the zero-dollar Blender 3D backend. Existing
free-source video and Pillow motion remain available only as explicit opt-in
fallbacks. Kids-animation engines are untouched.
"""
from __future__ import annotations

import json
import os
import shutil
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


def run_3d() -> bool:
    """Run the real 3D backend and make its result the canonical cinematic layer."""
    required = os.getenv("ZERO_DOLLAR_3D_REQUIRED", "true").lower() not in {"0", "false", "no", "off"}
    blender = os.getenv("BLENDER_BIN") or shutil.which("blender")
    if not blender:
        if required:
            raise RuntimeError("ZERO_DOLLAR_3D_REQUIRED=true but Blender is not installed")
        return False
    try:
        run(["python", "-m", "src.zero_dollar_3d_engine"])
        produced = OUTPUT / "normal_production" / "3d-animation.mp4"
        if not produced.exists() or produced.stat().st_size == 0:
            raise RuntimeError("3D backend produced no video")
        shutil.copy2(produced, FINAL)
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        rows = []
        for i, _ in enumerate(plan.get("scenes", []), 1):
            rows.append({"scene": i, "source": "procedural-3d", "backend": "blender_eevee", "output": str(FINAL.relative_to(ROOT))})
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({"version": 4, "backend_order": ["blender_eevee"], "scenes": rows, "final": str(FINAL.relative_to(ROOT))}, indent=2) + "\n", encoding="utf-8")
        print(f"3D animation backend ready: {FINAL}")
        return True
    except Exception as exc:
        if required:
            raise RuntimeError(f"Zero-dollar Blender 3D backend failed: {exc}") from exc
        print(f"3D backend unavailable: {exc}")
        return False


def render_procedural_fallback() -> None:
    """Legacy still-image motion fallback; disabled by default for normal production."""
    media = sorted(p for p in VISUALS.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS) if VISUALS.exists() else []
    if not media:
        raise RuntimeError("No visual assets found for fallback renderer")
    try:
        from src.normal_cinematic_renderer import render_scene, scene_seconds
    except ModuleNotFoundError:
        from normal_cinematic_renderer import render_scene, scene_seconds
    scenes = json.loads(PLAN.read_text(encoding="utf-8")).get("scenes", [])
    WORK.mkdir(parents=True, exist_ok=True)
    clips = []
    seconds = scene_seconds(OUTPUT / "voice.mp3", len(scenes))
    for i, scene in enumerate(scenes, 1):
        out = WORK / f"scene_{i:03d}.mp4"
        render_scene(media[(i - 1) % len(media)], out, scene, i, seconds)
        clips.append(out)
    manifest = WORK / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in clips) + "\n", encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(FINAL)])


def main() -> None:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json is missing")
    scenes = json.loads(PLAN.read_text(encoding="utf-8")).get("scenes", [])
    if not scenes:
        raise RuntimeError("Director plan contains no scenes")
    WORK.mkdir(parents=True, exist_ok=True)
    if run_3d():
        return
    if os.getenv("ALLOW_LEGACY_VISUAL_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}:
        render_procedural_fallback()
        return
    raise RuntimeError("No real animation backend succeeded; legacy visual fallback is disabled")


if __name__ == "__main__":
    main()
