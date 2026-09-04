"""Finalize the isolated normal cinematic layer with captions and voice."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VIDEO = OUTPUT / "cinematic-video.mp4"
AUDIO = OUTPUT / "voice.mp3"
TIMINGS = OUTPUT / "caption_timing.txt"
SRT = OUTPUT / "cinematic-captions.srt"
FINAL = OUTPUT / "final-video.mp4"


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def stamp(x: float) -> str:
    x = max(0.0, x)
    h = int(x // 3600); m = int((x % 3600) // 60); s = int(x % 60); ms = int(round((x - int(x)) * 1000))
    if ms >= 1000: s += 1; ms = 0
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt() -> Path:
    rows = []
    if TIMINGS.exists():
        for i, line in enumerate(TIMINGS.read_text(encoding="utf-8").splitlines(), 1):
            try:
                a, b, text = line.split("|", 2)
                a, b = float(a), float(b)
                if b > a and text.strip(): rows += [str(i), f"{stamp(a)} --> {stamp(b)}", text.strip(), ""]
            except ValueError:
                continue
    SRT.write_text("\n".join(rows), encoding="utf-8")
    return SRT


def main() -> None:
    for p in (VIDEO, AUDIO):
        if not p.exists() or p.stat().st_size == 0: raise RuntimeError(f"Missing cinematic artifact: {p}")
    target = min(45.0, duration(AUDIO), duration(VIDEO))
    srt = make_srt()
    captioned = OUTPUT / "cinematic-captioned.mp4"
    subtitle = f"subtitles={srt.as_posix()}:force_style='FontName=DejaVu Sans,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=250'"
    subprocess.run(["ffmpeg", "-y", "-i", str(VIDEO), "-t", str(target), "-vf", subtitle, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(captioned)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(AUDIO), "-t", str(target), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(FINAL)], check=True)
    final_duration = duration(FINAL)
    if not 10 <= final_duration <= 46: raise RuntimeError(f"Final video duration invalid: {final_duration:.2f}s")
    print(f"Final cinematic normal video: {FINAL} ({final_duration:.2f}s)")


if __name__ == "__main__": main()
