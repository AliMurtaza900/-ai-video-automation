"""Zero-cost cinematic animation layer for normal videos.

This module is intentionally isolated from every kids-animation renderer.
It turns the selected still visuals into moving cinematic shots using only
Pillow and FFmpeg: camera motion, simulated depth/parallax, lighting sweeps,
atmospheric particles, vignette and scene transitions.
"""
from __future__ import annotations

import json
import math
import os
import random
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
MAX_SECONDS = 45.0
DEFAULT_SCENE_SECONDS = float(os.getenv("SCENE_SECONDS", "2.7"))


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def media_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def fit_image(path: Path) -> Image.Image:
    try:
        image = ImageOps.exif_transpose(Image.open(path).convert("RGB"))
    except Exception:
        image = Image.new("RGB", (WIDTH, HEIGHT))
    scale = max(WIDTH / image.width, HEIGHT / image.height) * 1.30
    size = (int(image.width * scale), int(image.height * scale))
    return ImageOps.fit(image.resize(size, Image.Resampling.LANCZOS),
                        (int(WIDTH * 1.30), int(HEIGHT * 1.30)),
                        method=Image.Resampling.LANCZOS)


def move(image: Image.Image, progress: float, mode: str, strength: float = 1.0) -> Image.Image:
    cw, ch = image.size
    tx, ty = cw - WIDTH, ch - HEIGHT
    if mode == "push_in":
        zoom = 1.0 + 0.105 * strength * progress
        w, h = int(cw / zoom), int(ch / zoom)
        x, y = (cw - w) // 2, (ch - h) // 2
    elif mode == "pull_out":
        zoom = 1.105 - 0.105 * strength * progress
        w, h = int(cw / zoom), int(ch / zoom)
        x, y = (cw - w) // 2, (ch - h) // 2
    elif mode == "pan_left":
        x, y = tx * (1 - progress) * strength + tx * (1 - strength) * .5, ty * .5
    elif mode == "pan_right":
        x, y = tx * progress * strength + tx * (1 - strength) * .5, ty * .5
    elif mode == "tilt_up":
        x, y = tx * .5, ty * (1 - progress) * strength + ty * (1 - strength) * .5
    elif mode == "tilt_down":
        x, y = tx * .5, ty * progress * strength + ty * (1 - strength) * .5
    else:
        x = tx * (.50 + .16 * math.sin(progress * math.pi) * strength)
        y = ty * (.50 - .12 * math.cos(progress * math.pi) * strength)
    x = max(0, min(tx, x)); y = max(0, min(ty, y))
    return image.crop((int(x), int(y), int(x) + WIDTH, int(y) + HEIGHT))


def depth_frame(image: Image.Image, progress: float, mode: str, index: int) -> Image.Image:
    """Fake a restrained 2.5D camera move without paid AI or segmentation.

    The blurred full-frame plate behaves like a distant background while a
    feathered central plate moves slightly faster, creating perceived depth.
    It is deliberately subtle so ordinary documentary photos do not look like
    a duplicated/cut-out subject.
    """
    base = move(image, progress, mode, 0.78)
    background = base.filter(ImageFilter.GaussianBlur(radius=2.2))
    background = ImageEnhance.Brightness(background).enhance(0.92)
    frame = background.convert("RGBA")

    subject = move(image, min(1.0, progress * 1.12), mode, 1.0)
    scale = 1.045 + 0.018 * math.sin(progress * math.pi)
    subject = subject.resize((int(WIDTH * scale), int(HEIGHT * scale)), Image.Resampling.LANCZOS)
    left = (subject.width - WIDTH) // 2
    top = (subject.height - HEIGHT) // 2
    subject = subject.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGBA")

    # Soft ellipse mask gives the center visual a foreground-plane feel.
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    margin_x, margin_y = int(WIDTH * .10), int(HEIGHT * .10)
    draw.ellipse((margin_x, margin_y, WIDTH - margin_x, HEIGHT - margin_y), fill=190)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=85))
    frame.alpha_composite(subject, (0, 0), (0, 0, WIDTH, HEIGHT), mask)

    # Atmospheric particles are deterministic per scene, so reruns are stable.
    text = " ".join(str(index) + " " + str(mode)).lower()
    if index % 3 != 0:
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        rng = random.Random(index * 7919)
        for _ in range(22):
            px = rng.randint(0, WIDTH - 1)
            py = rng.randint(0, HEIGHT - 1)
            radius = rng.choice((1, 1, 2, 3))
            alpha = rng.randint(10, 28)
            d.ellipse((px-radius, py-radius, px+radius, py+radius), fill=(255, 255, 255, alpha))
        drift = int(18 * math.sin(progress * math.pi * 2))
        overlay = ImageChops_offset(overlay, drift, -drift)
        frame.alpha_composite(overlay)

    # Slow cinematic light sweep / vignette.
    light = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ld = ImageDraw.Draw(light)
    cx = int(WIDTH * (.12 + .76 * progress))
    ld.ellipse((cx - 520, int(HEIGHT * .08), cx + 520, int(HEIGHT * .92)), fill=(255, 235, 190, 18))
    light = light.filter(ImageFilter.GaussianBlur(120))
    frame.alpha_composite(light)

    vignette = Image.new("L", (WIDTH, HEIGHT), 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse((-WIDTH * .15, -HEIGHT * .10, WIDTH * 1.15, HEIGHT * 1.10), fill=215)
    vignette = vignette.filter(ImageFilter.GaussianBlur(140))
    dark = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 105))
    dark.putalpha(ImageOps.invert(vignette))
    frame.alpha_composite(dark)
    return frame.convert("RGB")


def ImageChops_offset(image: Image.Image, x: int, y: int) -> Image.Image:
    from PIL import ImageChops
    return ImageChops.offset(image, x, y)


def grade(image: Image.Image, progress: float) -> Image.Image:
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Color(image).enhance(1.05)
    image = ImageEnhance.Brightness(image).enhance(1.01)
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
    if "pull" in text or "reveal" in text:
        return "pull_out"
    if "hero" in text or "low-angle" in text:
        return "push_in"
    return ["push_in", "pan_right", "pan_left", "orbit", "tilt_up", "tilt_down"][index % 6]


def scene_seconds(audio: Path, count: int) -> float:
    if os.getenv("SCENE_SECONDS"):
        return max(1.8, min(4.0, DEFAULT_SCENE_SECONDS))
    try:
        total = min(MAX_SECONDS, media_duration(audio))
        return max(1.8, min(4.0, total / max(1, count)))
    except Exception:
        return DEFAULT_SCENE_SECONDS


def render_scene(image_path: Path, output: Path, scene: dict, index: int, seconds: float) -> None:
    image = fit_image(image_path)
    motion = motion_for(scene, index)
    frames = max(2, int(seconds * FPS))
    pattern = WORK / f"frame_{index:03d}_%05d.jpg"
    for n in range(frames):
        p = n / (frames - 1)
        frame = depth_frame(image, p, motion, index)
        grade(frame, p).save(pattern.as_posix() % n, quality=90)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(pattern),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-pix_fmt", "yuv420p", "-an", str(output)])
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
    audio = OUTPUT / "voice.mp3"
    seconds = scene_seconds(audio, len(scenes))
    rendered = []
    for i, scene in enumerate(scenes, 1):
        out = WORK / f"scene_{i:03d}.mp4"
        render_scene(visuals[(i - 1) % len(visuals)], out, scene, i, seconds)
        rendered.append(out)

    manifest = WORK / "concat.txt"
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in rendered) + "\n", encoding="utf-8")
    final = OUTPUT / "cinematic-video.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)])
    actual = media_duration(final)
    print(f"Cinematic animated normal video ready: {final} ({actual:.2f}s, depth/parallax/lighting/particles)")


if __name__ == "__main__":
    main()
