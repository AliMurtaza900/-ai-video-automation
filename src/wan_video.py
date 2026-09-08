"""Wan 2.2 video adapter with a free-Kaggle/WanGP backend.

WAN_ENGINE=wangp uses WanGP's in-process API so a Kaggle T4 can run a
quantized/low-VRAM Wan 2.2 setup instead of requiring a self-hosted 24 GB GPU.
The existing native Wan CLI backend remains available as WAN_ENGINE=native.
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
    return scenes[: int(os.getenv("WAN_MAX_SHOTS", "6"))]


def clean_visuals() -> None:
    VISUALS.mkdir(parents=True, exist_ok=True)
    for p in VISUALS.glob("visual_*"):
        p.unlink(missing_ok=True)
    (VISUALS / "sources.txt").unlink(missing_ok=True)


def cinematic_prompt(scene: str) -> str:
    return (
        "Cinematic vertical YouTube Short shot, photorealistic documentary film look, "
        "coherent natural motion, professional lighting, realistic depth of field, "
        "smooth camera movement, high detail, no text, no subtitles, no watermark. "
        f"Scene: {scene}"
    )


def run_native(scenes: list[str]) -> list[Path]:
    wan_home = Path(os.environ.get("WAN_HOME", "")).expanduser()
    checkpoint = Path(os.environ.get("WAN_CHECKPOINT", str(wan_home / "Wan2.2-TI2V-5B"))).expanduser()
    generate = Path(os.environ.get("WAN_GENERATE", str(wan_home / "generate.py"))).expanduser()
    if not generate.is_file():
        raise RuntimeError(f"Wan generate.py not found: {generate}")
    if not checkpoint.is_dir():
        raise RuntimeError(f"Wan checkpoint not found: {checkpoint}")

    work = Path(os.environ.get("WAN_OUTPUT_DIR", str(OUTPUT / "wan-generated"))).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for index, scene in enumerate(scenes):
        save_file = work / f"wan_{index:02d}.mp4"
        save_file.unlink(missing_ok=True)
        cmd = [
            os.environ.get("WAN_PYTHON", sys.executable), str(generate),
            "--task", "ti2v-5B", "--size", os.getenv("WAN_SIZE", "704*1280"),
            "--ckpt_dir", str(checkpoint),
            "--offload_model", os.getenv("WAN_OFFLOAD_MODEL", "True"),
            "--convert_model_dtype", "--t5_cpu", "--save_file", str(save_file),
            "--prompt", cinematic_prompt(scene),
        ]
        if os.getenv("WAN_BASE_SEED"):
            cmd += ["--base_seed", os.environ["WAN_BASE_SEED"]]
        print(f"Generating native Wan shot {index + 1}/{len(scenes)}")
        subprocess.run(cmd, cwd=str(wan_home), check=True)
        if not save_file.is_file() or save_file.stat().st_size < 50000:
            raise RuntimeError(f"Native Wan produced no valid MP4 for shot {index + 1}")
        target = VISUALS / f"visual_{index:02d}.mp4"
        shutil.copy2(save_file, target)
        generated.append(target)
    return generated


def choose_wangp_model(session) -> str:
    defs = session.list_model_defs()
    candidates = []
    for item in defs:
        text = str(item).lower()
        model_type = item.get("model_type") if isinstance(item, dict) else None
        if model_type and "wan" in text and "2.2" in text and "5b" in text and "ti2v" in text:
            candidates.append(model_type)
    if not candidates:
        available = [d.get("model_type") for d in defs if isinstance(d, dict) and d.get("model_type")]
        raise RuntimeError("WanGP did not expose a Wan 2.2 TI2V-5B model. Available models: " + ", ".join(map(str, available[:80])))
    return candidates[0]


def run_wangp(scenes: list[str]) -> list[Path]:
    wan_home = Path(os.environ.get("WAN_HOME", "")).expanduser()
    if not (wan_home / "shared" / "api.py").is_file():
        raise RuntimeError(f"WanGP API not found under WAN_HOME={wan_home}")
    sys.path.insert(0, str(wan_home))
    from shared.api import init  # type: ignore

    work = Path(os.environ.get("WAN_OUTPUT_DIR", str(OUTPUT / "wan-generated"))).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    session = init(root=wan_home, output_dir=work, cli_args=["--attention", "sdpa", "--profile", "4"], console_output=True)
    model_type = os.getenv("WAN_MODEL_TYPE") or choose_wangp_model(session)
    print(f"WanGP model: {model_type}")

    resolution = os.getenv("WAN_SIZE", "704*1280").replace("*", "x")
    steps = int(os.getenv("WAN_STEPS", "8"))
    frames = int(os.getenv("WAN_FRAMES", "49"))
    generated: list[Path] = []

    for index, scene in enumerate(scenes):
        settings = session.get_default_settings(model_type) or {}
        settings.update({
            "model_type": model_type,
            "prompt": cinematic_prompt(scene),
            "resolution": resolution,
            "num_inference_steps": steps,
            "video_length": frames,
            "duration_seconds": max(1, round(frames / 24)),
            "force_fps": 24,
            "seed": int(os.getenv("WAN_SEED", str(10000 + index))),
        })
        print(f"Generating WanGP shot {index + 1}/{len(scenes)}")
        result = session.submit_task(settings).result()
        if not result.success or not result.generated_files:
            errors = [getattr(e, "message", str(e)) for e in getattr(result, "errors", [])]
            raise RuntimeError(f"WanGP failed for shot {index + 1}: {'; '.join(errors)}")
        source = next((Path(p) for p in result.generated_files if str(p).lower().endswith(".mp4")), None)
        if source is None or not source.is_file() or source.stat().st_size < 50000:
            raise RuntimeError(f"WanGP returned no valid MP4 for shot {index + 1}: {result.generated_files}")
        target = VISUALS / f"visual_{index:02d}.mp4"
        shutil.copy2(source, target)
        generated.append(target)
    return generated


def main() -> int:
    if os.getenv("WAN_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        print("Wan 2.2 disabled")
        return 0
    script_path = OUTPUT / "script.txt"
    if not script_path.is_file():
        raise RuntimeError("output/script.txt is missing")
    scenes = scenes_from_script(script_path.read_text(encoding="utf-8").strip())
    if not scenes:
        raise RuntimeError("No scenes could be created from script")

    clean_visuals()
    engine = os.getenv("WAN_ENGINE", "native").lower()
    generated = run_wangp(scenes) if engine == "wangp" else run_native(scenes)
    (VISUALS / "sources.txt").write_text(
        "\n".join(f"Scene {i + 1} | source=Wan2.2 via {engine} | local_file={p.relative_to(ROOT)}" for i, p in enumerate(generated)) + "\n",
        encoding="utf-8",
    )
    print(f"WAN_REPORT generated={len(generated)} total={len(scenes)} engine={engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
