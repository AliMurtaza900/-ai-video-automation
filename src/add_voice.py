import asyncio
import re
import subprocess
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VOICE = "en-US-AriaNeural"


async def make_voice(text: str, output: Path):
    communicate = edge_tts.Communicate(text, VOICE)
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
    # Split at natural pauses first, then keep captions short enough for Shorts.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), 7):
            chunks.append(" ".join(words[i:i + 7]))

    if not chunks:
        return []

    # Allocate time by character count. This follows speech much better than
    # a fixed duration per caption because longer phrases generally take longer.
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
    video_file = OUTPUT / "test-video.mp4"
    audio_file = OUTPUT / "voice.mp3"
    timing_file = OUTPUT / "caption_timing.txt"
    final_file = OUTPUT / "final-video.mp4"

    text = script_file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Generated script is empty")

    if audio_file.exists():
        audio_file.unlink()
    asyncio.run(make_voice(text, audio_file))
    duration = duration_seconds(audio_file)

    timings = make_caption_timings(text, duration)
    timing_file.write_text(
        "\n".join(f"{s:.3f}|{e:.3f}|{caption}" for s, e, caption in timings),
        encoding="utf-8",
    )

    print(f"Created voice ({duration:.2f}s) and {len(timings)} caption segments")


if __name__ == "__main__":
    main()
