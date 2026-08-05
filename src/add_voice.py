import asyncio
import subprocess
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VOICE = "en-US-AriaNeural"


async def make_voice(text: str, output: Path, timing_file: Path):
    communicate = edge_tts.Communicate(text, VOICE)
    words = []
    with output.open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                duration = chunk.get("duration", 0) / 10_000_000
                word = chunk.get("text", "").strip()
                if word:
                    words.append((start, start + duration, word))

    if not words:
        raise RuntimeError("Edge TTS returned no word-boundary timing data")

    lines = []
    current = []
    start = None
    for item in words:
        if start is None:
            start = item[0]
        current.append(item)
        if len(current) >= 6:
            lines.append((start, item[1], " ".join(x[2] for x in current)))
            current = []
            start = None
    if current:
        lines.append((start, current[-1][1], " ".join(x[2] for x in current)))

    timing_file.write_text(
        "\n".join(f"{s:.3f}|{e:.3f}|{text}" for s, e, text in lines),
        encoding="utf-8",
    )


def main():
    script_file = OUTPUT / "script.txt"
    video_file = OUTPUT / "test-video.mp4"
    audio_file = OUTPUT / "voice.mp3"
    timing_file = OUTPUT / "caption_timing.txt"
    final_file = OUTPUT / "final-video.mp4"

    text = script_file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Generated script is empty")

    asyncio.run(make_voice(text, audio_file, timing_file))

    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_file), "-i", str(audio_file),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(final_file),
    ], check=True)
    print(f"Created video with word-timed captions: {final_file}")


if __name__ == "__main__":
    main()
