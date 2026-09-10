"""Mode 1: reuse user-owned/licensed video with fresh AI narration.

The engine selects an unused local video, samples frames for visual context,
asks Gemini for a fresh narration, and records the selected source. It never
modifies or removes the existing kids-animation engines.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from google import genai
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
LIBRARY = ROOT / "assets" / "video_library"
DATA = ROOT / "data"
STATE = DATA / "video_library_state.json"

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MODELS = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]


def duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def choose_video() -> Path:
    LIBRARY.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in LIBRARY.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        raise RuntimeError("No source videos found. Put your owned/licensed videos in assets/video_library/")
    state = load_state()
    used = set(state.get("used", []))
    unused = [p for p in videos if str(p.relative_to(ROOT)) not in used]
    candidates = unused or videos
    # Prefer a clip that can become a 10-46s Short. Otherwise trim safely.
    candidates.sort(key=lambda p: (duration(p) < 10, str(p)))
    return candidates[0]


def extract_frames(video: Path, count: int = 4) -> list[Image.Image]:
    d = max(0.1, duration(video))
    tmp = OUTPUT / "library_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    for i in range(count):
        t = min(max(0.05, d * (i + 0.5) / count), max(0.05, d - 0.05))
        out = tmp / f"frame_{i}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
            "-vf", "scale=720:-2", "-q:v", "3", str(out)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        frames.append(Image.open(out).convert("RGB"))
    return frames


def validate_script(text: str) -> str:
    text = " ".join(text.strip().split())
    words = text.split()
    if not 55 <= len(words) <= 115:
        raise RuntimeError(f"Invalid narration length: {len(words)} words")
    if any(token in text for token in ("```", "**", "#")):
        raise RuntimeError("Narration contains formatting")
    return text


def generate_narration(video: Path) -> str:
    sidecar = video.with_suffix(".txt")
    context = sidecar.read_text(encoding="utf-8").strip() if sidecar.exists() else ""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Mode 1 to create fresh narration")
    client = genai.Client(api_key=api_key)
    frames = extract_frames(video)
    prompt = f"""You are writing narration for a YouTube Short using an existing user-owned or licensed video.
Analyze the supplied frames and write ONE original narration that matches what is visibly happening.
Do not claim things that cannot be supported by the video or the optional source note.
Create a strong curiosity hook, natural pacing, and a satisfying ending.
Return narration only: no title, labels, bullets, markdown, emojis, or stage directions.
Target 65-100 spoken words. Keep it advertiser-friendly and suitable for a general audience.
Optional source note: {context or 'none'}
Video filename: {video.name}
"""
    last_error = None
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(model=model, contents=[prompt, *frames])
                return validate_script(response.text or "")
            except Exception as exc:
                last_error = exc
                print(f"Mode 1 Gemini {model} attempt {attempt + 1} failed: {exc}")
                if attempt == 0:
                    time.sleep(2)
    raise RuntimeError(f"Mode 1 narration generation failed: {last_error}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = choose_video()
    script = generate_narration(source)
    (OUTPUT / "library_source.txt").write_text(str(source.relative_to(ROOT)), encoding="utf-8")
    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
    state = load_state()
    used = list(state.get("used", []))
    rel = str(source.relative_to(ROOT))
    if rel not in used:
        used.append(rel)
    # Once every source has been used, the next run starts a fresh rotation.
    all_sources = [str(p.relative_to(ROOT)) for p in LIBRARY.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    if all_sources and set(all_sources).issubset(set(used)):
        state["last_cycle_completed"] = used[-len(all_sources):]
        used = []
    state["used"] = used[-500:]
    save_state(state)
    print(f"Mode 1 selected: {source}")
    print(f"Fresh narration: {len(script.split())} words")


if __name__ == "__main__":
    main()
