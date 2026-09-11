"""Mode 1: one fixed user-owned/licensed video + fresh narration.

The source is always assets/video_library/fixed_source.mp4. Each run generates
fresh, curiosity-driven narration with a different topic angle, while leaving
all existing animation engines untouched.
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
TOPIC_LANES = [
    "strange science and physics",
    "human brain and psychology",
    "space and cosmic mysteries",
    "animals and surprising biology",
    "everyday things with hidden explanations",
    "history's bizarre but factual mysteries",
    "technology and future mysteries",
    "Earth, oceans and extreme natural phenomena",
]


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
    if not 80 <= len(words) <= 135:
        raise RuntimeError(f"Invalid narration length: {len(words)} words; expected a natural Short narration")
    if any(token in text for token in ("```", "**", "#")):
        raise RuntimeError("Narration contains formatting")
    return text


def generate_narration(video: Path, run_number: int) -> tuple[str, str]:
    sidecar = video.with_suffix(".txt")
    context = sidecar.read_text(encoding="utf-8").strip() if sidecar.exists() else ""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Mode 1 to create fresh narration")
    client = genai.Client(api_key=api_key)
    frames = extract_frames(video)
    lane = TOPIC_LANES[(run_number - 1) % len(TOPIC_LANES)]
    prompt = f"""You are the writer for a high-retention YouTube Shorts channel.
The same user-owned or properly licensed source video is reused every run, so the narration must feel genuinely fresh.

Analyze all supplied frames first. Then choose ONE specific, factual, curiosity-driven topic or question that can be naturally connected to the visible footage.
Preferred topic lane for this run: {lane}.
Do not repeat the obvious topic from the previous runs if the state below contains recent topics.

Style:
- Start with a punchy curiosity hook in the first sentence.
- Sound cinematic, mysterious, intelligent and conversational — never like a school lecture or news report.
- Build a question or mystery, reveal useful facts, then finish with a memorable twist or final thought.
- Use simple spoken English, short sentences and natural pauses created by punctuation.
- Prefer surprising "what if", "why", "how", hidden-detail and counterintuitive topics.
- Never fabricate facts. If a claim is uncertain, choose another topic.
- The narration should work with the supplied visuals without pretending the footage shows something it does not.
- Target 80-125 spoken words. The final video will automatically be cropped to the actual narration duration, so do NOT pad with filler.
- Return narration only: no title, labels, bullets, markdown, emojis, topic names, or stage directions.
- Keep it advertiser-friendly and suitable for a general audience.

Examples of the kind of curiosity angle wanted (do not copy these): why humans cannot tickle themselves; what would happen if Earth stopped spinning; why time feels faster as we age; what actually happens near a black hole; why octopuses have three hearts; why some hot water can freeze faster than cold water.

Optional source note: {context or 'none'}
Run number: {run_number}
Video filename: {video.name}
"""
    last_error = None
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(model=model, contents=[prompt, *frames])
                return validate_script(response.text or ""), lane
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

    state = {}
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    run_number = int(state.get("runs", 0)) + 1
    script, lane = generate_narration(SOURCE, run_number)
    (OUTPUT / "library_source.txt").write_text(str(SOURCE.relative_to(ROOT)), encoding="utf-8")
    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
    state.update({
        "source": str(SOURCE.relative_to(ROOT)),
        "source_duration_seconds": round(source_duration, 3),
        "runs": run_number,
        "last_run_source": str(SOURCE.relative_to(ROOT)),
        "last_topic_lane": lane,
    })
    save_state(state)
    print(f"Mode 1 fixed source: {SOURCE} ({source_duration:.2f}s)")
    print(f"Curiosity topic lane: {lane}")
    print(f"Fresh narration: {len(script.split())} words")


def save_state(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
