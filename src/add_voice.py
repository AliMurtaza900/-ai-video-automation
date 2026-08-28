import asyncio
import re
import subprocess
import time
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VOICES = ["en-US-AriaNeural", "en-US-JennyNeural", "en-US-GuyNeural"]


async def make_voice(text: str, output: Path, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    with output.open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])


def duration_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def make_caption_timings(text: str, duration: float):
    # Short, punchy captions are easier to read on a phone and leave less text
    # covering the visual. Split at natural pauses, then cap each caption at 6 words.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), 6):
            chunks.append(" ".join(words[i:i + 6]))

    if not chunks:
        return []

    # Allocate time by character count. This tracks speech length better than
    # giving every caption an identical duration.
    weights = [max(1, len(c.replace(" ", ""))) for c in chunks]
    total_weight = sum(weights)
    timings = []
    cursor = 0.0
    for i, chunk in enumerate(chunks):
        span = duration * weights[i] / total_weight
        end = duration if i == len(chunks) - 1 else cursor + span
        timings.append((cursor, end, chunk))
        cursor = end
    return timings


def main():
    script_file = OUTPUT / "script.txt"
    audio_file = OUTPUT / "voice.mp3"
    timing_file = OUTPUT / "caption_timing.txt"

    text = script_file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Generated script is empty")

    last_error = None
    for voice in VOICES:
        for attempt in range(1, 4):
            try:
                audio_file.unlink(missing_ok=True)
                asyncio.run(make_voice(text, audio_file))
                if audio_file.stat().st_size < 10000:
                    raise RuntimeError("TTS returned a tiny audio file")
                duration = duration_seconds(audio_file)
                if not 8 <= duration <= 55:
                    raise RuntimeError(f"TTS duration is {duration:.2f}s")
                timings = make_caption_timings(text, duration)
                timing_file.write_text(
                    "\n".join(f"{s:.3f}|{e:.3f}|{caption}" for s, e, caption in timings),
                    encoding="utf-8",
                )
                print(f"Created voice with {voice}: {duration:.2f}s, {len(timings)} captions")
                return
            except Exception as exc:
                last_error = exc
                print(f"TTS {voice} attempt {attempt} failed: {exc}")
                if attempt < 3:
                    time.sleep(min(30, 3 * (2 ** (attempt - 1))))
    raise RuntimeError(f"All Edge TTS attempts failed: {last_error}")


if __name__ == "__main__":
    main()
