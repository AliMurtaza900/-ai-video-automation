"""Structured production planner for original children's poems and stories.

This module deliberately separates creative planning from rendering. It produces a
machine-readable production bible that downstream renderers can consume, rather
than falling back to unrelated still images.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Character:
    name: str
    species: str
    personality: str
    visual_description: str
    voice_id: str
    color_palette: tuple[str, ...]


@dataclass(frozen=True)
class Scene:
    number: int
    duration_seconds: int
    location: str
    characters: tuple[str, ...]
    action: str
    dialogue: str
    camera: str
    animation_beats: tuple[str, ...]
    music: str
    sound_effects: tuple[str, ...]


@dataclass
class ProductionBible:
    title: str
    format: str
    audience: str
    visual_style: str
    characters: list[Character] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    consistency_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "format": self.format,
            "audience": self.audience,
            "visual_style": self.visual_style,
            "characters": [asdict(c) for c in self.characters],
            "scenes": [asdict(s) for s in self.scenes],
            "consistency_rules": self.consistency_rules,
        }

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()


def build_sample_poem() -> ProductionBible:
    """Return a complete, original short-form production plan used for dry runs."""
    bunny = Character(
        name="Milo",
        species="bunny",
        personality="curious, gentle, playful",
        visual_description="small cream bunny, teal overalls, round cheeks, expressive eyes",
        voice_id="child_milo_01",
        color_palette=("cream", "teal", "soft-yellow"),
    )
    bird = Character(
        name="Pip",
        species="songbird",
        personality="cheerful, encouraging",
        visual_description="small blue songbird with a yellow belly and rounded cartoon proportions",
        voice_id="child_pip_01",
        color_palette=("blue", "yellow", "white"),
    )
    scenes = [
        Scene(1, 20, "Milo's cozy bedroom", ("Milo",), "Milo wakes, stretches and looks through the window.", "Good morning, sunny day!", "wide shot to gentle push-in", ("blink", "stretch", "head turn", "smile"), "soft xylophone intro", ("birds", "room ambience")),
        Scene(2, 25, "flower meadow", ("Milo", "Pip"), "Milo hops through flowers while Pip flies down and lands beside him.", "Come along, Milo!", "tracking shot following the hop, then close-up", ("hop cycle", "ear bounce", "wing flap", "landing", "wave"), "bouncy children's melody", ("hops", "wing flutter", "meadow ambience")),
        Scene(3, 30, "meadow path", ("Milo", "Pip"), "They discover a tiny seed and plant it together.", "Little seed, grow with care!", "over-shoulder to close-up of seed", ("kneel", "dig", "drop seed", "pat soil", "hopeful look"), "warm marimba", ("soil", "sparkle", "gentle breeze")),
        Scene(4, 35, "magical garden", ("Milo", "Pip"), "A flower blooms; the friends dance around it while singing the refrain.", "Grow, grow, little flower, bright and free!", "orbiting medium shot with two close-ups", ("eyes widen", "smile", "dance", "spin", "clap"), "full original refrain", ("magic chime", "claps", "footsteps")),
        Scene(5, 25, "sunset meadow", ("Milo", "Pip"), "The friends wave goodbye as the sun sets.", "Tomorrow we'll care for it again!", "slow pull-back to wide sunset", ("wave", "blink", "small hop", "smile"), "gentle bedtime reprise", ("evening birds", "breeze")),
    ]
    return ProductionBible(
        title="Milo and the Little Flower",
        format="original animated children's poem",
        audience="preschool and early elementary",
        visual_style="original soft 3D cartoon animation, rounded shapes, expressive faces, warm storybook lighting",
        characters=[bunny, bird],
        scenes=scenes,
        consistency_rules=[
            "Use the exact character bible for every scene.",
            "Never substitute unrelated characters or image styles between scenes.",
            "Prefer continuous motion and camera movement over still-image slides.",
            "Dialogue must use the assigned character voice_id.",
            "Every scene must contain at least three explicit animation beats.",
            "Music and sound effects must be synchronized to scene timing.",
            "Reject a render when a scene falls back to an unrelated still image.",
        ],
    )


def write_bible(path: str | Path, bible: ProductionBible | None = None) -> str:
    bible = bible or build_sample_poem()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bible.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return bible.digest()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/production-bible.json")
    args = parser.parse_args()
    print(write_bible(args.output))
