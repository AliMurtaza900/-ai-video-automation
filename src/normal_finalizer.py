"""Finalize normal video output with centered captions and background audio."""
from pathlib import Path
import subprocess
import os

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VIDEO = OUTPUT / "cinematic-video.mp4"
AUDIO = OUTPUT / "voice.mp3"
TIMINGS = OUTPUT / "caption_timing.txt"
SRT = OUTPUT / "cinematic-captions.srt"
ASS = OUTPUT / "cinematic-captions.ass"
FINAL = OUTPUT / "final-video.mp4"
MUSIC = ROOT / "assets" / "background_music.mp3"


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def stamp(x: float) -> str:
    x = max(0.0, x)
    h = int(x // 3600); m = int((x % 3600) // 60); s = int(x % 60); ms = int(round((x - int(x)) * 1000))
    if ms >= 1000: s += 1; ms = 0
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def ass_time(x: float) -> str:
    x = max(0.0, x)
    h = int(x // 3600); m = int((x % 3600) // 60); s = int(x % 60); cs = int(round((x - int(x)) * 100))
    if cs >= 100: s += 1; cs = 0
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def read_timings():
    rows = []
    if TIMINGS.exists():
        for line in TIMINGS.read_text(encoding="utf-8").splitlines():
            try:
                a, b, text = line.split("|", 2)
                a, b = float(a), float(b)
                text = text.strip().replace("{", "\\{").replace("}", "\\}")
                if b > a and text:
                    rows.append((a, b, text))
            except ValueError:
                continue
    return rows


def make_srt() -> Path:
    rows = []
    for i, (a, b, text) in enumerate(read_timings(), 1):
        rows += [str(i), f"{stamp(a)} --> {stamp(b)}", text.replace("\\{", "{").replace("\\}", "}"), ""]
    SRT.write_text("\n".join(rows), encoding="utf-8")
    return SRT


def make_ass() -> Path:
    # Explicit ASS positioning is used instead of relying on SRT renderer
    # defaults. Alignment 5 = exact horizontal + vertical center.
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Center,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,5,40,40,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for a, b, text in read_timings():
        lines.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Center,,0,0,0,,{text}")
    ASS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ASS


def run(cmd):
    subprocess.run(cmd, check=True)


def finalize_library(source: Path, audio: Path, ass: Path) -> None:
    source_duration = duration(source)
    audio_duration = duration(audio)
    target = min(source_duration, audio_duration)
    if target < 10:
        raise RuntimeError(f"Mode 1 source/audio is too short: {target:.2f}s")

    captioned = OUTPUT / "library-captioned.mp4"
    # Explicit ASS center placement keeps subtitles in the actual middle of
    # the 1080x1920 frame, independent of FFmpeg/SRT defaults.
    subtitle = f"ass={ass.as_posix()}"
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1," + subtitle
    run(["ffmpeg", "-y", "-i", str(source), "-t", f"{target:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(captioned)])

    if MUSIC.exists() and MUSIC.stat().st_size > 0:
        fade_start = max(0.0, target - 2.0)
        # Keep narration at full level and background at roughly 8%.
        # Loudness normalization is part of the same filter graph so FFmpeg
        # does not receive conflicting -filter_complex and -af options.
        music_filter = f"volume=0.08,afade=t=in:st=0:d=1,afade=t=out:st={fade_start:.3f}:d=2[music]"
        filter_complex = f"[1:a]volume=1.0[voice];[2:a]{music_filter};[voice][music]amix=inputs=2:duration=shortest:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(audio), "-stream_loop", "-1", "-i", str(MUSIC), "-t", f"{target:.3f}",
             "-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(FINAL)])
    else:
        run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(audio), "-t", f"{target:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(FINAL)])


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
        finalize_library(source, AUDIO, make_ass())
        make_srt()
        final_duration = duration(FINAL)
        if not 10 <= final_duration <= 61:
            raise RuntimeError(f"Final video duration invalid: {final_duration:.2f}s")
        print(f"Final Mode 1 fixed video: {FINAL} ({final_duration:.2f}s)")
        return

    for p in (VIDEO, AUDIO):
        if not p.exists() or p.stat().st_size == 0: raise RuntimeError(f"Missing cinematic artifact: {p}")
    target = min(45.0, duration(AUDIO), duration(VIDEO))
    ass = make_ass()
    captioned = OUTPUT / "cinematic-captioned.mp4"
    subtitle = f"ass={ass.as_posix()}"
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1," + subtitle
    run(["ffmpeg", "-y", "-i", str(VIDEO), "-t", str(target), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(captioned)])
    run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(AUDIO), "-t", str(target), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(FINAL)])
    final_duration = duration(FINAL)
    if not 10 <= final_duration <= 46: raise RuntimeError(f"Final video duration invalid: {final_duration:.2f}s")
    print(f"Final cinematic normal video: {FINAL} ({final_duration:.2f}s)")


if __name__ == "__main__": main()
