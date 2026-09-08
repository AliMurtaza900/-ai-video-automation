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
# Kaggle script kernels do not reliably package arbitrary sidecar files.
# The GitHub workflow injects this value directly into the script before push.
EMBEDDED_CONFIG = None


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def find_config() -> Path:
    candidates = [CONFIG, Path("job_config.json"), Path("/kaggle/input/job-config/job_config.json")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Kaggle script kernels package local files next to /kaggle/src/script.py.
    for candidate in Path("/kaggle/src").glob("**/job_config.json"):
        if candidate.is_file():
            return candidate
    if EMBEDDED_CONFIG:
        embedded = WORK / "job_config.embedded.json"
        embedded.write_text(json.dumps(EMBEDDED_CONFIG), encoding="utf-8")
        return embedded
    raise FileNotFoundError("job_config.json was not packaged into the Kaggle kernel and no embedded config exists")


def main() -> None:
    config_path = find_config()
    print(f"Using config: {config_path}", flush=True)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    repo = cfg["repo"]
    ref = cfg["ref"]
    goal = cfg["goal"]
    max_shots = str(cfg.get("max_shots", 2))

    run(["nvidia-smi"])
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

    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")])
    run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-r", str(WAN_DIR / "requirements.txt")])

    env = os.environ.copy()
    env.update({
        "VIDEO_GOAL": goal,
        "WAN_ENABLED": "true",
        "WAN_ENGINE": "wangp",
        "WAN_HOME": str(WAN_DIR),
        "WAN_MAX_SHOTS": max_shots,
        "WAN_SIZE": "576*1024",
        "WAN_STEPS": "6",
        "WAN_FRAMES": "33",
        "WAN_OUTPUT_DIR": str(REPO_DIR / "output" / "wan-generated"),
        "SKIP_YOUTUBE_UPLOAD": "true",
        "PYTHONUNBUFFERED": "1",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    })

    print("Python:", sys.version, flush=True)
    run([sys.executable, "-c", "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'available', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"], env=env)

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
            shutil.copy2(source, bundle / Path(relative).name)
    final = bundle / "final-video.mp4"
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("Kaggle generation completed without final-video.mp4")
    print("KAGGLE_WAN_SUCCESS", final, final.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
