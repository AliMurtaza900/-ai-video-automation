"""Wan 2.2 TI2V-5B scene generator."""
from __future__ import annotations
import os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAN_DIR = ROOT / "models" / "Wan2.2-TI2V-5B"
WAN_REPO = ROOT / "third_party" / "Wan2.2"
OUT = ROOT / "output" / "wan_scenes"
MODEL_ID = os.getenv("WAN_MODEL_ID", "Wan-AI/Wan2.2-TI2V-5B")
SIZE = os.getenv("WAN_SIZE", "1280*704")

def ensure_model():
    if (WAN_DIR / "config.json").exists():
        return
    WAN_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["huggingface-cli", "download", MODEL_ID, "--local-dir", str(WAN_DIR)], check=True)

def ensure_code():
    if (WAN_REPO / "generate.py").exists():
        return
    WAN_REPO.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Wan-Video/Wan2.2.git", str(WAN_REPO)], check=True)

def scene_prompts():
    script = (ROOT / "output" / "script.txt").read_text(encoding="utf-8").strip()
    sentences = [x.strip() for x in script.replace("\n", " ").split(".") if x.strip()]
    if not sentences:
        raise RuntimeError("No narration available for Wan scene generation")
    return sentences

def generate(prompt, index):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"scene_{index:02d}.mp4"
    before = {p.resolve() for p in WAN_REPO.glob("*.mp4")}
    subprocess.run([
        "python", str(WAN_REPO / "generate.py"), "--task", "ti2v-5B",
        "--size", SIZE, "--ckpt_dir", str(WAN_DIR), "--offload_model", "True",
        "--convert_model_dtype", "--t5_cpu", "--prompt", prompt
    ], cwd=WAN_REPO, check=True)
    candidates = [p for p in WAN_REPO.glob("*.mp4") if p.resolve() not in before]
    if not candidates:
        candidates = list(WAN_REPO.glob("*.mp4"))
    if not candidates:
        raise RuntimeError("Wan completed without producing an MP4")
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    newest.replace(target)
    return target

def main():
    if os.getenv("VIDEO_ENGINE", "wan").lower() != "wan":
        print("Wan engine disabled by VIDEO_ENGINE")
        return
    probe = subprocess.run(["python", "-c", "import torch; print(torch.cuda.is_available())"], capture_output=True, text=True)
    if probe.stdout.strip() != "True":
        raise RuntimeError("Wan 2.2 requires a CUDA GPU; configure a self-hosted GPU runner or GPU VM.")
    ensure_code()
    ensure_model()
    prompts = scene_prompts()
    for i, prompt in enumerate(prompts[:12], 1):
        generate("Cinematic original family-friendly 3D animated short film; consistent characters; expressive faces; natural body motion; professional lighting; smooth cinematic camera movement. " + prompt, i)
    print(f"Wan generated {len(list(OUT.glob('scene_*.mp4')))} scenes")

if __name__ == "__main__":
    main()
