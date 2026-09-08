from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("/kaggle/working")
CONFIG = WORK / "job_config.json"
REPO_DIR = WORK / "ai-video-automation"
WAN_DIR = WORK / "Wan2GP"
EMBEDDED_CONFIG = None
WAN2GP_COMMIT = "362c3467a70e1136ceb52eec95907205a8f88543"
LOG = WORK / "kaggle_preflight.log"


def log(message: str) -> None:
    print(message, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    log("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True)
    if result.stdout:
        log(result.stdout.rstrip())
    if result.stderr:
        log(result.stderr.rstrip())
    if result.returncode:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


def find_config() -> Path:
    candidates = [CONFIG, Path("job_config.json"), Path("/kaggle/input/job-config/job_config.json")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for candidate in Path("/kaggle/src").glob("**/job_config.json"):
        if candidate.is_file():
            return candidate
    if EMBEDDED_CONFIG:
        embedded = WORK / "job_config.embedded.json"
        embedded.write_text(json.dumps(EMBEDDED_CONFIG), encoding="utf-8")
        return embedded
    raise FileNotFoundError("No job config found")


def check_internet() -> None:
    """Prove that this exact Kaggle worker can reach the services it needs."""
    log("=== KAGGLE NETWORK PREFLIGHT ===")
    log(f"HOSTNAME={socket.gethostname()}")
    log(f"KAGGLE_URL_BASE={os.environ.get('KAGGLE_URL_BASE', 'unset')}")
    log(f"HTTP_PROXY={os.environ.get('HTTP_PROXY', 'unset')}")
    log(f"HTTPS_PROXY={os.environ.get('HTTPS_PROXY', 'unset')}")
    for host in ("github.com", "raw.githubusercontent.com", "pypi.org", "huggingface.co"):
        try:
            ip = socket.gethostbyname(host)
            log(f"DNS_OK {host} -> {ip}")
        except OSError as exc:
            raise RuntimeError(
                f"KAGGLE_INTERNET_BLOCKED: DNS cannot resolve {host}: {exc}. "
                "The Kaggle kernel's Internet permission is OFF at runtime. "
                "Enable Internet for this Kaggle kernel/account, then rerun. "
                "No Python code can repair a disabled Kaggle network sandbox."
            ) from exc
    for url in ("https://github.com", "https://pypi.org", "https://huggingface.co"):
        try:
            run([sys.executable, "-c", f"import urllib.request; r=urllib.request.urlopen({url!r}, timeout=15); print(r.status)"])
        except Exception as exc:
            raise RuntimeError(f"KAGGLE_INTERNET_BLOCKED: HTTPS request failed for {url}: {exc}") from exc
    log("KAGGLE_NETWORK_OK")


def main() -> None:
    LOG.unlink(missing_ok=True)
    config_path = find_config()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    repo = cfg["repo"]
    ref = cfg["ref"]
    goal = cfg["goal"]
    max_shots = str(cfg.get("max_shots", 2))

    log(f"Using config: {config_path}")
    log(f"Python: {sys.version}")

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        run([nvidia_smi])
    else:
        log("nvidia-smi not available; continuing with PyTorch CUDA preflight")

    check_internet()

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    run(["git", "clone", "--depth", "1", repo, str(REPO_DIR)])
    run(["git", "fetch", "--depth", "1", "origin", ref], cwd=REPO_DIR)
    run(["git", "checkout", ref], cwd=REPO_DIR)

    if WAN_DIR.exists():
        shutil.rmtree(WAN_DIR)
    run(["git", "clone", "--depth", "1", "https://github.com/deepbeepmeep/Wan2GP.git", str(WAN_DIR)])
    run(["git", "checkout", WAN2GP_COMMIT], cwd=WAN_DIR)
    log(f"Wan2GP pinned to {WAN2GP_COMMIT}")

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

    run([sys.executable, "-c", "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'available', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"], env=env)
    run([sys.executable, "-c", "import torch; x=torch.randn((256,256), device='cuda'); print('CUDA_SMOKE_OK', x.mean().item())"], env=env)

    run([sys.executable, "src/factory_bridge.py"], cwd=REPO_DIR, env=env)

    bundle = WORK / "kaggle_output"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir()
    for relative in ("output/final-video.mp4", "output/voice.mp3", "output/script.txt", "factory_workspace/result.json", "assets/visuals/sources.txt"):
        source = REPO_DIR / relative
        if source.is_file():
            shutil.copy2(source, bundle / Path(relative).name)
    final = bundle / "final-video.mp4"
    if not final.is_file() or final.stat().st_size == 0:
        raise RuntimeError("Kaggle generation completed without final-video.mp4")
    log(f"KAGGLE_WAN_SUCCESS {final} {final.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"KAGGLE_FATAL: {type(exc).__name__}: {exc}")
        raise
