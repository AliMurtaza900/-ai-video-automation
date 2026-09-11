import asyncio
import os
import re
import subprocess
import time
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VOICES = ["en-US-AriaNeural", "en-US-JennyNeural", "en-US-GuyNeural"]


async def make_voice(text: str, output: Path, voice: str, rate: str = "+0%"):
    # Mode 1 targets a ~60s finished Short. A normal Edge TTS rate can make
    # 105-125 words finish in ~45s, so slow the fixed-video narration enough
    # to fill the supplied ~60s source without adding dead silence.
    communicate = edge_tts.Communicate(text, voice, rate=rate)
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
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), 6):
            chunks.append(" ".join(words[i:i + 6]))

    if not chunks:
        return []

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

    library_mode = os.environ.get("VIDEO_MODE", "normal").strip().lower() == "library"
    # Prefer a ~60s narration for Mode 1. If a voice still lands outside the
    # target, the fallback rates keep the job robust rather than failing late.
    rates = ["-20%", "-15%", "-10%", "+0%"] if library_mode else ["+0%"]
    last_error = None
    for voice in VOICES:
        for rate in rates:
            for attempt in range(1, 3 if rate == rates[0] else 2):
                try:
                    audio_file.unlink(missing_ok=True)
                    asyncio.run(make_voice(text, audio_file, voice, rate=rate))
                    if audio_file.stat().st_size < 10000:
                        raise RuntimeError("TTS returned a tiny audio file")
                    duration = duration_seconds(audio_file)
                    if not 8 <= duration <= 70:
                        raise RuntimeError(f"TTS duration is {duration:.2f}s")
                    if library_mode and not 54 <= duration <= 62:
                        raise RuntimeError(f"Mode 1 TTS duration is {duration:.2f}s; expected approximately 60s")
                    timings = make_caption_timings(text, duration)
                    timing_file.write_text(
                        "\n".join(f"{s:.3f}|{e:.3f}|{caption}" for s, e, caption in timings),
                        encoding="utf-8",
                    )
                    print(f"Created voice with {voice} at {rate}: {duration:.2f}s, {len(timings)} captions")
                    return
                except Exception as exc:
                    last_error = exc
                    print(f"TTS {voice} {rate} attempt {attempt} failed: {exc}")
                    if attempt < (3 if rate == rates[0] else 2):
                        time.sleep(min(20, 3 * (2 ** (attempt - 1))))
    raise RuntimeError(f"All Edge TTS attempts failed: {last_error}")


if __name__ == "__main__":
    main()
