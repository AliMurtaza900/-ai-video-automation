import asyncio
import subprocess
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VOICE = "en-US-AriaNeural"


async def make_voice(text: str, output: Path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output))


def duration_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def main():
    script_file = OUTPUT / "script.txt"
    video_file = OUTPUT / "test-video.mp4"
    audio_file = OUTPUT / "voice.mp3"
    final_file = OUTPUT / "final-video.mp4"
    timing_file = OUTPUT / "caption_timing.txt"

    text = script_file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Generated script is empty")

    asyncio.run(make_voice(text, audio_file))
    audio_duration = duration_seconds(audio_file)

    # Store timing information for the renderer. The renderer uses the exact
    # audio duration instead of assuming a fixed 2-second caption interval.
    words = text.split()
    words_per_caption = 6
    chunks = [words[i:i + words_per_caption] for i in range(0, len(words), words_per_caption)]
    chunk_duration = audio_duration / max(1, len(chunks))
    timing_file.write_text(
        "\n".join(f"{i * chunk_duration:.3f}|{(i + 1) * chunk_duration:.3f}|{' '.join(chunk)}"
                  for i, chunk in enumerate(chunks)),
        encoding="utf-8",
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_file),
        "-i", str(audio_file),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(final_file),
    ], check=True)

    print(f"Created video with synchronized voice: {final_file}")


if __name__ == "__main__":
    main()
