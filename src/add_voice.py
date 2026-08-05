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


def main():
    script_file = OUTPUT / "script.txt"
    video_file = OUTPUT / "test-video.mp4"
    audio_file = OUTPUT / "voice.mp3"
    final_file = OUTPUT / "final-video.mp4"

    text = script_file.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Generated script is empty")

    asyncio.run(make_voice(text, audio_file))

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

    print(f"Created video with AI voice: {final_file}")


if __name__ == "__main__":
    main()
