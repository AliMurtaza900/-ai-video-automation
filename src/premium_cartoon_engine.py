from __future__ import annotations

"""Stable production facade for the Google-visual animation pipeline."""

try:
    from .vector_animation_engine import W, H, FPS, SCENE_SECONDS, SCENES, POEM, STORY
    from .google_visual_engine import main as _main
except ImportError:
    from vector_animation_engine import W, H, FPS, SCENE_SECONDS, SCENES, POEM, STORY
    from google_visual_engine import main as _main

BEATS = SCENES


def main():
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
