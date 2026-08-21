from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

try:
    from . import vector_animation_engine as base
    from .google_image_fetcher import build_scene_queries, fetch_scene_image
except ImportError:
    import vector_animation_engine as base
    from google_image_fetcher import build_scene_queries, fetch_scene_image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "kids_animation"
FPS = 24
W = 1280
H = 720
SCENE_SECONDS = 6
W, H = 1280, 720
BEATS = base.SCENES
POEM = base.POEM
STORY = base.STORY


def _run(args):
    subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _make_image_video(image: Path, text: str, out: Path, scene_no: int):
    """Turn one discovered Google image into a moving 24fps scene."""
    # zoompan gives the still image continuous cinematic movement instead of a
    # static slideshow. The image is first scaled/cropped to the HD canvas.
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        "zoompan=z='min(zoom+0.0007,1.08)':"
        f"x='iw/2-(iw/zoom/2)+sin(on/35)*18':"
        f"y='ih/2-(ih/zoom/2)+cos(on/43)*12':"
        f"d={int(SCENE_SECONDS*FPS)}:s={W}x{H}:fps={FPS},"
        "format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image),
        "-vf", vf, "-t", str(SCENE_SECONDS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", str(out)
    ])


def _voice(text: str, out: Path):
    piper = shutil.which("piper")
    model = Path(os.environ.get("PIPER_MODEL", "voices/en_US-lessac-medium.onnx"))
    if not piper or not model.exists():
        raise RuntimeError("Pinned Piper neural voice is required")
    subprocess.run([
        piper, "--model", str(model), "--output_file", str(out),
        "--sentence-silence", "0.25"
    ], input=text, text=True, check=True, cwd=ROOT)


def _add_narration(video: Path, voice: Path, out: Path):
    _run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(voice),
        "-filter_complex",
        "[1:a]highpass=f=80,lowpass=f=12000,"
        "acompressor=threshold=-18dB:ratio=3:attack=5:release=80,"
        "volume=1.8,aresample=48000[a]",
        "-map", "0:v", "-map", "[a]", "-shortest",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(out)
    ])


def main():
    content = os.getenv("CONTENT_TYPE", "poem")
    topic = os.getenv("TOPIC", "Milo and the Little Flower").strip()
    duration = float(os.getenv("DURATION", "1"))
    if content not in {"poem", "story"}:
        raise RuntimeError("CONTENT_TYPE must be poem or story")
    if not 1 <= duration <= 10:
        raise RuntimeError("DURATION must be between 1 and 10 minutes")

    lines = POEM if content == "poem" else STORY
    OUT.mkdir(parents=True, exist_ok=True)
    scenes_dir = OUT / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    queries = build_scene_queries(topic, BEATS)
    rendered: list[Path] = []

    for i, query in enumerate(queries, 1):
        scene_dir = scenes_dir / f"{i:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        image = fetch_scene_image(query, i)
        if image is None:
            # Google can rate-limit or change markup. Keep production deterministic
            # by falling back to the existing original vector scene.
            fallback = scene_dir / "video.mp4"
            base.render_scene(BEATS[i - 1][0], BEATS[i - 1][1], fallback)
        else:
            fallback = scene_dir / "video.mp4"
            _make_image_video(image, lines[(i - 1) % len(lines)], fallback, i)

        voice = scene_dir / "voice.wav"
        final = scene_dir / "scene.mp4"
        _voice(lines[(i - 1) % len(lines)], voice)
        _add_narration(fallback, voice, final)
        rendered.append(final)

    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in rendered), encoding="utf-8")
    final = OUT / "kids-animation.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", "-movflags", "+faststart", str(final)
    ])
    if final.stat().st_size < 500_000:
        raise RuntimeError("rendered video failed quality gate")
    print(f"GOOGLE_VISUAL_RENDERED {final} {final.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
