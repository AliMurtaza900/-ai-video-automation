from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
SHOT_SECONDS = 3.5
MAX_SECONDS = 45

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".ogv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def load_caption_timings():
    path = OUTPUT / "caption_timing.txt"
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            start, end, text = line.split("|", 2)
            result.append((float(start), float(end), text.strip()))
        except ValueError:
            pass
    return result


def make_srt(timings):
    path = OUTPUT / "captions.srt"

    def stamp(seconds):
        seconds = max(0, seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            s += 1
            ms = 0
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, (start, end, text) in enumerate(timings, 1):
        if end <= start or not text:
            continue
        lines += [str(i), f"{stamp(start)} --> {stamp(end)}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def visual_files():
    files = []
    for path in sorted(VISUALS.glob("visual_*")):
        if path.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS:
            files.append(path)
    return files


def ffmpeg_filter_for(path_count):
    parts = []
    labels = []
    for i in range(path_count):
        label = f"v{i}"
        parts.append(
            f"[{i}:v]trim=duration={SHOT_SECONDS},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS}[{label}]"
        )
        labels.append(f"[{label}]")
    duration = min(MAX_SECONDS, path_count * SHOT_SECONDS)
    parts.append("".join(labels) + f"concat=n={path_count}:v=1:a=0,trim=duration={duration},setpts=PTS-STARTPTS[base]")
    return ";".join(parts), duration


def main():
    script_path = OUTPUT / "script.txt"
    script = script_path.read_text(encoding="utf-8").strip() if script_path.exists() else ""
    if not script:
        raise RuntimeError("Generated script is empty")

    timings = load_caption_timings()
    if not timings:
        raise RuntimeError("Caption timing data is missing; generate the voice before rendering")

    files = visual_files()
    if not files:
        raise RuntimeError("No visuals found in assets/visuals")

    # Prefer real video clips. Images are retained as a fallback and get a
    # gentle motion-like treatment from the same crop pipeline.
    files = files[:max(1, int(MAX_SECONDS / SHOT_SECONDS) + 1)]
    video_count = sum(p.suffix.lower() in VIDEO_EXTS for p in files)
    print(f"Using {len(files)} visuals ({video_count} video clips, {len(files) - video_count} images)")

    srt = make_srt(timings)
    filter_graph, duration = ffmpeg_filter_for(len(files))
    base = OUTPUT / "video_base.mp4"
    output = OUTPUT / "test-video.mp4"

    cmd = ["ffmpeg", "-y"]
    for path in files:
        if path.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop", "1", "-t", str(SHOT_SECONDS), "-i", str(path)]
        else:
            cmd += ["-stream_loop", "-1", "-t", str(SHOT_SECONDS), "-i", str(path)]

    cmd += [
        "-filter_complex", filter_graph,
        "-map", "[base]",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(base),
    ]
    subprocess.run(cmd, check=True)

    # Add readable, bottom-safe captions in one FFmpeg pass instead of
    # generating thousands of intermediate PNG frames.
    subtitle_filter = (
        f"subtitles={srt.as_posix()}:"
        "force_style='FontName=DejaVu Sans,FontSize=20,"
        "Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=180'"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(base), "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-an", str(output)
    ], check=True)

    print(f"Created {output} ({duration:.1f}s) without frame-by-frame PNG rendering")


if __name__ == "__main__":
    main()
