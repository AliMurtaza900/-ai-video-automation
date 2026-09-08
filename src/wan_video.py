"""Optional local Wan 2.2 TI2V-5B adapter.

This module is intentionally disabled unless WAN_ENABLED=true. It keeps the
existing asset pipeline as a fallback on ordinary CPU/GitHub runners.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VISUALS = ROOT / "assets" / "visuals"


def scenes_from_script(script: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", script.strip()) if p.strip()]
    scenes: list[str] = []
    for part in parts:
        words = part.split()
        if len(words) > 18:
            step = max(9, (len(words) + 1) // 2)
            scenes.extend(" ".join(words[i:i + step]) for i in range(0, len(words), step))
        else:
            scenes.append(part)
    return scenes[: int(os.getenv("WAN_MAX_SHOTS", "10"))]


def command_for(prompt: str, save_file: Path) -> list[str]:
    wan_home = Path(os.environ.get("WAN_HOME", "")).expanduser()
    checkpoint = Path(os.environ.get("WAN_CHECKPOINT", str(wan_home / "Wan2.2-TI2V-5B"))).expanduser()
    generate = Path(os.environ.get("WAN_GENERATE", str(wan_home / "generate.py"))).expanduser()
    if not generate.is_file():
        raise RuntimeError(f"Wan generate.py not found: {generate}")
    if not checkpoint.is_dir():
        raise RuntimeError(f"Wan checkpoint not found: {checkpoint}")

    cmd = [
        os.environ.get("WAN_PYTHON", sys.executable), str(generate),
        "--task", "ti2v-5B",
        "--size", os.getenv("WAN_SIZE", "704*1280"),
        "--ckpt_dir", str(checkpoint),
        "--offload_model", os.getenv("WAN_OFFLOAD_MODEL", "True"),
        "--convert_model_dtype",
        "--t5_cpu",
        "--save_file", str(save_file),
        "--prompt", prompt,
    ]
    if os.getenv("WAN_BASE_SEED"):
        cmd += ["--base_seed", os.environ["WAN_BASE_SEED"]]
    return cmd


def main() -> int:
    if os.getenv("WAN_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        print("Wan 2.2 disabled (set WAN_ENABLED=true on a GPU runner to enable it)")
        return 0

    script_path = OUTPUT / "script.txt"
    if not script_path.is_file():
        raise RuntimeError("output/script.txt is missing")
    scenes = scenes_from_script(script_path.read_text(encoding="utf-8").strip())
    if not scenes:
        raise RuntimeError("No scenes could be created from script")

    VISUALS.mkdir(parents=True, exist_ok=True)
    # fetch_visuals.py already populated this directory. In Wan mode those
    # assets are replaced completely so the renderer sees only generated shots.
    for p in VISUALS.glob("visual_*"):
        p.unlink(missing_ok=True)
    (VISUALS / "sources.txt").unlink(missing_ok=True)

    work = Path(os.environ.get("WAN_OUTPUT_DIR", str(OUTPUT / "wan-generated"))).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    for index, scene in enumerate(scenes):
        prompt = (
            "Cinematic vertical 9:16 documentary-style shot for a YouTube Short. "
            "Photorealistic, coherent motion, professional lighting, natural camera movement, "
            "high detail, no text, no subtitles, no watermark. Scene: " + scene
        )
        shot_dir = work / f"shot_{index:02d}"
        shot_dir.mkdir(parents=True, exist_ok=True)
        save_file = shot_dir / "wan_output.mp4"
        save_file.unlink(missing_ok=True)
        print(f"Generating Wan 2.2 shot {index + 1}/{len(scenes)}")
        subprocess.run(command_for(prompt, save_file), cwd=str(Path(os.environ["WAN_HOME"]).expanduser()), check=True)
        if not save_file.is_file() or save_file.stat().st_size < 50000:
            raise RuntimeError(f"Wan 2.2 produced no valid MP4 for shot {index + 1}")
        target = VISUALS / f"visual_{index:02d}.mp4"
        shutil.copy2(save_file, target)
        generated_files.append(target)

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"Scene {i + 1} | source=Wan2.2 local | local_file={p.relative_to(ROOT)}"
            for i, p in enumerate(generated_files)
        ) + "\n",
        encoding="utf-8",
    )
    print(f"WAN_REPORT generated={len(generated_files)} total={len(scenes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
