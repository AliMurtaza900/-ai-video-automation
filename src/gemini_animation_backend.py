"""Gemini/Veo 3.1 scene backend for Kids Animation Studio.

The backend uses the repository's existing GEMINI_API_KEY. Veo 3.1 produces
short animated clips with native audio; the renderer concatenates those clips
into the production. Reference images can be supplied per character under
assets/characters/<character-name>.(png|jpg|webp) when available.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS = ROOT / "assets" / "characters"
MODEL = os.environ.get("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview")


def _image_for(name: str):
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = CHARACTERS / f"{name.lower().replace(' ', '_')}{ext}"
        if path.exists():
            return path
    return None


def build_prompt(scene: dict) -> str:
    characters = ", ".join(scene.get("characters", [])) or "the main characters"
    beats = "; ".join(scene.get("animation_beats", []))
    return (
        "Original preschool-friendly 3D cartoon animation, soft storybook lighting, "
        "rounded expressive characters, polished children's television quality. "
        f"Characters: {characters}. Location: {scene.get('location')}. "
        f"Action: {scene.get('action')}. Camera: {scene.get('camera')}. "
        f"Animation beats that must visibly occur: {beats}. "
        f"Dialogue/action audio cue: {scene.get('dialogue', '')}. "
        "Keep character appearance stable, clear readable body motion, natural facial expressions, "
        "continuous animation rather than a slideshow. No text overlays, no logos, no photorealism."
    )


def generate(scene_path: str, output_path: str) -> None:
    import json
    scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for the Gemini/Veo animation backend")

    client = genai.Client(api_key=api_key)
    references = []
    for name in scene.get("characters", [])[:3]:
        image_path = _image_for(name)
        if image_path:
            image = types.Image.from_file(location=str(image_path))
            references.append(types.VideoGenerationReferenceImage(image=image, reference_type="asset"))

    config = types.GenerateVideosConfig(aspect_ratio="9:16", resolution="720p")
    if references:
        config.reference_images = references

    operation = client.models.generate_videos(model=MODEL, prompt=build_prompt(scene), config=config)
    while not operation.done:
        time.sleep(10)
        operation = client.operations.get(operation)

    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError(f"Gemini/Veo returned no video for scene {scene['number']}")
    video = operation.response.generated_videos[0].video
    client.files.download(file=video)
    video.save(output_path)
    print(f"Generated animated scene {scene['number']} -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    generate(args.scene, args.output)
