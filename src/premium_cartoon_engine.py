from __future__ import annotations

"""Premium production compatibility layer.

The maintained renderer is vector_animation_engine. This module re-exports its
production contract so the workflow and tests have one canonical renderer.
"""

try:
    from .vector_animation_engine import (
        W, H, FPS, SCENE_SECONDS, SCENES, POEM, STORY, main as _vector_main,
    )
except ImportError:
    from vector_animation_engine import (
        W, H, FPS, SCENE_SECONDS, SCENES, POEM, STORY, main as _vector_main,
    )

BEATS = SCENES


def main():
    return _vector_main()


if __name__ == "__main__":
    raise SystemExit(main())
