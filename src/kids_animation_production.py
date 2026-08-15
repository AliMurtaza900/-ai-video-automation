from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "kids_animation"
CLIPS = OUTPUT / "clips"
MODEL = os.getenv("VEO_MODEL", "veo-3.1-fast-generate-preview")

CHARACTER = "Milo, a small friendly golden-brown cartoon puppy with floppy ears, a blue scarf, big expressive brown eyes, soft rounded proportions, and a warm cheerful personality."

POEM_SCENES = [
    ("sunrise", "Milo wakes in a cozy little bedroom, stretches, blinks happily, and looks out the window at a glowing sunrise."),
    ("garden", "Milo trots into a colorful garden, sniffs bright flowers, and waves his little paw to a butterfly."),
    ("path", "Milo follows a winding garden path, bouncing playfully while tiny birds hop beside him."),
    ("stream", "Milo reaches a sparkling stream, carefully steps across round stones, then laughs when a fish splashes."),
    ("meadow", "Milo runs into a sunny meadow filled with daisies, spins around, and watches fluffy clouds drift overhead."),
    ("flower", "Milo discovers one tiny drooping flower and gently notices that it needs help."),
    ("water", "Milo carries a little blue watering can, carefully waters the flower, and waits with a hopeful smile."),
    ("magic", "The flower slowly opens with colorful petals while warm golden sparkles swirl around Milo's delighted face."),
    ("friends", "Birds, butterflies, and a little rabbit gather around Milo and celebrate the blooming flower together."),
    ("dance", "Milo and his friends dance in a joyful circle around the flower, with playful hops and gentle camera movement."),
    ("sunset", "At sunset Milo sits beside the flower, peacefully watching the orange sky while the friends settle nearby."),
    ("goodbye", "Milo waves to the viewer beside the glowing flower, smiles warmly, and walks home under twinkling stars."),
]

POEM_LINES = [
    "Wake up, Milo, morning is bright, stretch your paws in the golden light.",
    "Through the garden, off we go, where happy little flowers grow.",
    "Follow the path and sing hello, with birds that flutter to and fro.",
    "Across the stream, step by step, Milo laughs at every splash and pep.",
    "In the meadow, soft winds play, clouds make pictures in the day.",
    "Then Milo finds a little flower, drooping sadly hour by hour.",
    "A little water, kind and slow, can help a tiny flower grow.",
    "Look! The petals open wide, with golden sparkles dancing by its side.",
    "Friends arrive from everywhere, happy wings float through the air.",
    "Dance together, laugh and sing, kindness makes the whole world ring.",
    "As the sunset paints the sky, Milo watches fireflies fly.",
    "Goodnight, friends, the day is through; a little kindness starts with you.",
]


def make_client() -> genai.Client:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for real animation generation")
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_clip(client: genai.Client, prompt: str, path: Path) -> None:
    operation = client.models.generate_videos(
        model=MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            resolution="720p",
            number_of_videos=1,
        ),
    )
    while not operation.done:
        time.sleep(10)
        operation = client.operations.get(operation)
    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError("Veo completed without returning a video")
    generated = operation.response.generated_videos[0]
    client.files.download(file=generated.video)
    generated.video.save(str(path))
    if not path.is_file() or path.stat().st_size < 10_000:
        raise RuntimeError(f"Generated clip is missing or too small: {path}")


def build_prompt(topic: str, location: str, action: str, index: int, total: int) -> str:
    return f"""Create an original high-quality children's 3D cartoon animation scene for the story/poem '{topic}'.
Scene {index} of {total}, location: {location}.
Main character: {CHARACTER}
Action: {action}
Visual style: polished modern preschool animation, colorful but tasteful, soft cinematic lighting, appealing rounded shapes, expressive faces, clean family-friendly design, professional children's TV quality.
Animation requirements: continuous character movement throughout the shot, natural walking or body motion where appropriate, blinking and facial expressions, moving environment, secondary characters with purposeful motion, gentle camera movement, clear foreground/midground/background separation. This must look like real animation, NOT a slideshow, NOT a still image montage, and NOT photorealistic.
Audio: gentle child-friendly musical accompaniment, subtle environment sounds, cheerful and calm mood. Do not use copyrighted characters, brands, or recognizable existing songs.
Keep Milo's appearance consistent with the character description. No text, captions, logos, watermarks, or UI elements."""


def write_metadata(topic: str, duration: float, clips: list[Path]) -> None:
    meta = {
        "status": "generated",
        "topic": topic,
        "duration_target_minutes": duration,
        "model": MODEL,
        "clip_count": len(clips),
        "character": CHARACTER,
        "animation_style": "original modern preschool 3D cartoon",
        "audio": "native Veo audio",
        "clips": [str(p.relative_to(ROOT)) for p in clips],
    }
    (OUTPUT / "production.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    topic = os.getenv("TOPIC", "Milo and the Little Flower").strip()
    content_type = os.getenv("CONTENT_TYPE", "poem").strip().lower()
    duration = float(os.getenv("DURATION", "3"))
    if content_type not in {"poem", "story"}:
        raise RuntimeError("CONTENT_TYPE must be poem or story")
    if not 1 <= duration <= 10:
        raise RuntimeError("DURATION must be between 1 and 10 minutes")

    client = make_client()
    CLIPS.mkdir(parents=True, exist_ok=True)
    scenes = POEM_SCENES
    lines = POEM_LINES
    target_seconds = duration * 60
    clip_count = max(1, round(target_seconds / 8))
    clips: list[Path] = []

    for i in range(clip_count):
        scene_index = i % len(scenes)
        location, action = scenes[scene_index]
        line = lines[scene_index]
        prompt = build_prompt(topic, location, action + f" The narration/poem beat is: '{line}'", i + 1, clip_count)
        clip = CLIPS / f"scene_{i + 1:03d}.mp4"
        generate_clip(client, prompt, clip)
        clips.append(clip)

    concat = OUTPUT / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'" for p in clips) + "\n", encoding="utf-8")
    final = OUTPUT / "kids-animation.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", "-movflags", "+faststart", str(final)
    ], check=True)
    if not final.is_file() or final.stat().st_size < 100_000:
        raise RuntimeError("Final animation was not produced")
    write_metadata(topic, duration, clips)
    print(f"Generated {len(clips)} animated clips -> {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
