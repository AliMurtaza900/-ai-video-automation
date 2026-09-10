"""Mode 1: one fixed user-owned/licensed video + fresh narration.

The source is always assets/video_library/fixed_source.mp4. Each run generates
fresh narration from sampled frames, while leaving all existing animation
engines untouched.
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
SOURCE = ROOT / "assets" / "video_library" / "fixed_source.mp4"
DATA = ROOT / "data"
STATE = DATA / "fixed_video_state.json"
MODELS = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]


def duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def extract_frames(video: Path, count: int = 6) -> list[Image.Image]:
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
    if not 90 <= len(words) <= 135:
        raise RuntimeError(f"Invalid narration length: {len(words)} words; expected about 60 seconds")
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
    prompt = f"""You are writing narration for a 60-second YouTube Short using an existing user-owned or properly licensed video.
Analyze all supplied frames and write ONE original narration that matches what is visibly happening across the clip.
Do not invent facts that cannot be supported by the video or optional source note.
Create a strong first-sentence hook, natural spoken pacing, useful or entertaining commentary, and a satisfying final line.
Target about 105-125 spoken words so the voice naturally fills roughly one minute.
Return narration only: no title, labels, bullets, markdown, emojis, or stage directions.
Keep it advertiser-friendly and suitable for a general audience.
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
    if not SOURCE.exists():
        raise RuntimeError("Missing fixed source video: assets/video_library/fixed_source.mp4")
    source_duration = duration(SOURCE)
    if source_duration < 10:
        raise RuntimeError(f"Fixed source video is too short: {source_duration:.2f}s")

    script = generate_narration(SOURCE)
    (OUTPUT / "library_source.txt").write_text(str(SOURCE.relative_to(ROOT)), encoding="utf-8")
    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
    state = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_duration_seconds": round(source_duration, 3),
        "runs": 0,
    }
    try:
        state.update(json.loads(STATE.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    state["runs"] = int(state.get("runs", 0)) + 1
    state["last_run_source"] = str(SOURCE.relative_to(ROOT))
    save_state(state)
    print(f"Mode 1 fixed source: {SOURCE} ({source_duration:.2f}s)")
    print(f"Fresh narration: {len(script.split())} words")


def save_state(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
