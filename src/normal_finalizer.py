"""Finalize normal video output.

Mode 1 keeps one fixed user-owned/licensed source video, replaces its audio
with fresh narration, reframes it for Shorts, and burns synchronized captions.
Existing animation modes remain unchanged.
"""
from pathlib import Path
import subprocess
import os

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


def run(cmd):
    subprocess.run(cmd, check=True)


def finalize_library(source: Path, audio: Path, srt: Path) -> None:
    source_duration = duration(source)
    audio_duration = duration(audio)
    # The supplied source is ~60 seconds. Use the shorter stream so neither
    # video nor narration is padded with silence or frozen frames.
    target = min(60.0, source_duration, audio_duration)
    if target < 10:
        raise RuntimeError(f"Mode 1 source/audio is too short: {target:.2f}s")

    captioned = OUTPUT / "library-captioned.mp4"
    subtitle = f"subtitles={srt.as_posix()}:force_style='FontName=DejaVu Sans,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=250'"
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1," + subtitle
    run(["ffmpeg", "-y", "-i", str(source), "-t", f"{target:.3f}", "-vf", vf,
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(captioned)])
    run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(audio), "-t", f"{target:.3f}",
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(FINAL)])


def main() -> None:
    mode = os.environ.get("VIDEO_MODE", "normal").strip().lower()
    if mode == "library":
        source_file = OUTPUT / "library_source.txt"
        if not source_file.exists():
            raise RuntimeError("Mode 1 is enabled but output/library_source.txt is missing")
        source = ROOT / source_file.read_text(encoding="utf-8").strip()
        if not source.exists():
            raise RuntimeError(f"Selected fixed video does not exist: {source}")
        if not AUDIO.exists() or AUDIO.stat().st_size == 0:
            raise RuntimeError(f"Missing narration audio: {AUDIO}")
        finalize_library(source, AUDIO, make_srt())
        final_duration = duration(FINAL)
        if not 10 <= final_duration <= 61: raise RuntimeError(f"Final video duration invalid: {final_duration:.2f}s")
        print(f"Final Mode 1 fixed video: {FINAL} ({final_duration:.2f}s)")
        return

    for p in (VIDEO, AUDIO):
        if not p.exists() or p.stat().st_size == 0: raise RuntimeError(f"Missing cinematic artifact: {p}")
    target = min(45.0, duration(AUDIO), duration(VIDEO))
    srt = make_srt()
    captioned = OUTPUT / "cinematic-captioned.mp4"
    subtitle = f"subtitles={srt.as_posix()}:force_style='FontName=DejaVu Sans,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=250'"
    run(["ffmpeg", "-y", "-i", str(VIDEO), "-t", str(target), "-vf", subtitle, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(captioned)])
    run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(AUDIO), "-t", str(target), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(FINAL)])
    final_duration = duration(FINAL)
    if not 10 <= final_duration <= 46: raise RuntimeError(f"Final video duration invalid: {final_duration:.2f}s")
    print(f"Final cinematic normal video: {FINAL} ({final_duration:.2f}s)")


if __name__ == "__main__": main()
