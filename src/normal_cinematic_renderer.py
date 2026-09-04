"""Cinematic motion renderer for the normal-video engine.

Uses only local Pillow/FFmpeg processing. It does not alter the kids-animation
renderers. Each director scene gets its own visual treatment and camera move.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PLAN = OUTPUT / "normal_production" / "director_plan.json"
VISUALS = ROOT / "assets" / "visuals"
WORK = OUTPUT / "normal_production" / "rendered_scenes"
WORK.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1080, 1920
FPS = int(os.getenv("VIDEO_FPS", "30"))
SCENE_SECONDS = float(os.getenv("SCENE_SECONDS", "2.7"))


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def fit_image(path: Path) -> Image.Image:
    try:
        image = ImageOps.exif_transpose(Image.open(path).convert("RGB"))
    except Exception:
        image = Image.new("RGB", (WIDTH, HEIGHT))
    scale = max(WIDTH / image.width, HEIGHT / image.height) * 1.22
    size = (int(image.width * scale), int(image.height * scale))
    return ImageOps.fit(image.resize(size, Image.Resampling.LANCZOS), (int(WIDTH * 1.22), int(HEIGHT * 1.22)), method=Image.Resampling.LANCZOS)


def move(image: Image.Image, progress: float, mode: str) -> Image.Image:
    cw, ch = image.size
    tx, ty = cw - WIDTH, ch - HEIGHT
    if mode == "push_in":
        zoom = 1.0 + 0.10 * progress
        w, h = int(cw / zoom), int(ch / zoom)
        x, y = (cw - w) // 2, (ch - h) // 2
        return image.crop((x, y, x + w, y + h)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    if mode == "pull_out":
        zoom = 1.10 - 0.10 * progress
        w, h = int(cw / zoom), int(ch / zoom)
        x, y = (cw - w) // 2, (ch - h) // 2
        return image.crop((x, y, x + w, y + h)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    if mode == "pan_left":
        x, y = tx * (1 - progress), ty * .5
    elif mode == "pan_right":
        x, y = tx * progress, ty * .5
    elif mode == "tilt_up":
        x, y = tx * .5, ty * (1 - progress)
    elif mode == "tilt_down":
        x, y = tx * .5, ty * progress
    else:
        x = tx * (.35 + .30 * math.sin(progress * math.pi))
        y = ty * (.50 - .16 * math.cos(progress * math.pi))
    return image.crop((int(x), int(y), int(x) + WIDTH, int(y) + HEIGHT))


def grade(image: Image.Image, progress: float) -> Image.Image:
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Color(image).enhance(1.04)
    if progress < .08:
        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=105, threshold=3))
    return image


def motion_for(scene: dict, index: int) -> str:
    text = " ".join(str(scene.get(k, "")) for k in ("shot", "camera_motion", "action")).lower()
    if "wide" in text or "landscape" in text:
        return "pan_right" if index % 2 else "pan_left"
    if "close" in text or "macro" in text or "detail" in text:
        return "push_in"
    if "overhead" in text:
        return "tilt_down"
    if "hero" in text or "low-angle" in text:
        return "push_in"
    return ["push_in", "pan_right", "pan_left", "orbit", "tilt_up", "tilt_down"][index % 6]


def render_scene(image_path: Path, output: Path, scene: dict, index: int) -> None:
    image = fit_image(image_path)
    motion = motion_for(scene, index)
    frames = max(2, int(SCENE_SECONDS * FPS))
    pattern = WORK / f"frame_{index:03d}_%05d.jpg"
    for n in range(frames):
        p = n / (frames - 1)
        grade(move(image, p, motion), p).save(pattern.as_posix() % n, quality=90)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(pattern), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-an", str(output)])
    for f in WORK.glob(f"frame_{index:03d}_*.jpg"):
        f.unlink(missing_ok=True)


def main() -> None:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json is missing")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    visuals = sorted(p for p in VISUALS.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}) if VISUALS.exists() else []
    if not scenes or not visuals:
        raise RuntimeError("Need director scenes and downloaded visuals")
    rendered = []
    for i, scene in enumerate(scenes, 1):
        out = WORK / f"scene_{i:03d}.mp4"
        render_scene(visuals[(i - 1) % len(visuals)], out, scene, i)
        rendered.append(out)
    manifest = WORK / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in rendered) + "\n", encoding="utf-8")
    final = OUTPUT / "cinematic-video.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(final)])
    print(f"Cinematic normal video ready: {final}")


if __name__ == "__main__":
    main()
