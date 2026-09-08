from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path("/kaggle/working")
CONFIG = WORK / "job_config.json"
REPO_DIR = WORK / "ai-video-automation"
WAN_DIR = WORK / "Wan2GP"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    repo = cfg["repo"]
    ref = cfg["ref"]
    goal = cfg["goal"]
    max_shots = str(cfg.get("max_shots", 4))

    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "ffmpeg", "git"])

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    run(["git", "clone", "--depth", "1", repo, str(REPO_DIR)])
    run(["git", "fetch", "--depth", "1", "origin", ref], cwd=REPO_DIR)
    run(["git", "checkout", ref], cwd=REPO_DIR)

    if WAN_DIR.exists():
        shutil.rmtree(WAN_DIR)
    run(["git", "clone", "--depth", "1", "https://github.com/deepbeepmeep/Wan2GP.git", str(WAN_DIR)])

    # Keep Kaggle's CUDA/PyTorch base and install WanGP dependencies around it.
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")])
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(WAN_DIR / "requirements.txt")])

    env = os.environ.copy()
    env.update({
        "VIDEO_GOAL": goal,
        "WAN_ENABLED": "true",
        "WAN_ENGINE": "wangp",
        "WAN_HOME": str(WAN_DIR),
        "WAN_MAX_SHOTS": max_shots,
        "WAN_SIZE": "704*1280",
        "WAN_STEPS": "8",
        "WAN_FRAMES": "49",
        "WAN_OUTPUT_DIR": str(REPO_DIR / "output" / "wan-generated"),
        "SKIP_YOUTUBE_UPLOAD": "true",
        "PYTHONUNBUFFERED": "1",
    })

    # Run the user's complete pipeline on Kaggle's GPU, but leave YouTube upload
    # to GitHub Actions so YouTube credentials never enter the Kaggle notebook.
    subprocess.run([sys.executable, "src/factory_bridge.py"], cwd=str(REPO_DIR), env=env, check=True)

    bundle = WORK / "kaggle_output"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir()
    for relative in (
        "output/final-video.mp4",
        "output/voice.mp3",
        "output/script.txt",
        "factory_workspace/result.json",
        "assets/visuals/sources.txt",
    ):
        source = REPO_DIR / relative
        if source.is_file():
            destination = bundle / Path(relative).name
            shutil.copy2(source, destination)
    final = bundle / "final-video.mp4"
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("Kaggle generation completed without final-video.mp4")
    print("KAGGLE_WAN_SUCCESS", final, final.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
