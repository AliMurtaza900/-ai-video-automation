"""Render a Kids Animation Studio production bible into validated scene clips.

The renderer is backend-neutral: AI animation providers are invoked through
AI_ANIMATION_COMMAND. The command receives a scene JSON file and must produce
one animated MP4 for that scene. Static images are never accepted as a scene
render. This keeps provider credentials outside the repository while making the
production pipeline deterministic and testable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
SCENES = OUTPUT / "animated_scenes"


def load_bible(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("characters") or not data.get("scenes"):
        raise ValueError("Production bible must contain characters and scenes")
    return data


def _run_backend(scene_path: Path, output_path: Path) -> None:
    command = os.environ.get("AI_ANIMATION_COMMAND", "").strip()
    if not command:
        raise RuntimeError(
            "AI_ANIMATION_COMMAND is required. Configure the image-to-video/"
            "animation provider instead of silently falling back to still images."
        )
    argv = shlex.split(command) + ["--scene", str(scene_path), "--output", str(output_path)]
    subprocess.run(argv, check=True)


def _probe(path: Path) -> tuple[float, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,nb_frames",
         "-of", "json", str(path)], capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    frames = sum(int(s.get("nb_frames") or 0) for s in data.get("streams", []) if s.get("codec_type") == "video")
    return duration, frames


def render_bible(bible_path: str | Path, output_dir: str | Path = SCENES) -> list[Path]:
    bible = load_bible(bible_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    known_characters = {c["name"] for c in bible["characters"]}

    for scene in bible["scenes"]:
        if not scene.get("animation_beats") or len(scene["animation_beats"]) < 3:
            raise ValueError(f"Scene {scene['number']} does not contain enough animation beats")
        unknown = set(scene.get("characters", [])) - known_characters
        if unknown:
            raise ValueError(f"Scene {scene['number']} references unknown characters: {sorted(unknown)}")

        scene_path = destination / f"scene_{scene['number']:03d}.json"
        scene_path.write_text(json.dumps(scene, indent=2, ensure_ascii=False), encoding="utf-8")
        output_path = destination / f"scene_{scene['number']:03d}.mp4"
        _run_backend(scene_path, output_path)
        if not output_path.exists() or output_path.stat().st_size < 50_000:
            raise RuntimeError(f"Animation backend produced no usable clip for scene {scene['number']}")
        duration, frames = _probe(output_path)
        if duration < 1 or frames < 30:
            raise RuntimeError(f"Scene {scene['number']} is not an animated video: duration={duration}, frames={frames}")
        rendered.append(output_path)

    return rendered


def assemble(clips: list[Path], output: str | Path) -> Path:
    if not clips:
        raise ValueError("No animated scene clips supplied")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    concat = destination.with_suffix(".concat.txt")
    concat.write_text("\n".join(f"file '{p.resolve().as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(destination)], check=True)
    return destination


def render(bible_path: str | Path, output: str | Path = OUTPUT / "animated-cartoon.mp4") -> Path:
    clips = render_bible(bible_path)
    return assemble(clips, output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bible", default="output/production-bible.json")
    parser.add_argument("--output", default="output/animated-cartoon.mp4")
    args = parser.parse_args()
    print(render(args.bible, args.output))
