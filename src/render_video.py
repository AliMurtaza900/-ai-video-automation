from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
DEFAULT_SHOT_SECONDS = 3.5
MAX_SECONDS = 45

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".ogv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}


def media_duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def load_caption_timings():
    path = OUTPUT / "caption_timing.txt"
    if not path.exists(): return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            start, end, text = line.split("|", 2); result.append((float(start), float(end), text.strip()))
        except ValueError: pass
    return result


def make_srt(timings):
    path = OUTPUT / "captions.srt"
    def stamp(seconds):
        seconds = max(0, seconds); h=int(seconds//3600); m=int((seconds%3600)//60); s=int(seconds%60); ms=int(round((seconds-int(seconds))*1000))
        if ms >= 1000: s += 1; ms = 0
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    lines=[]
    for i,(start,end,text) in enumerate(timings,1):
        if end > start and text: lines += [str(i),f"{stamp(start)} --> {stamp(end)}",text,""]
    path.write_text("\n".join(lines),encoding="utf-8"); return path


def visual_files():
    return [p for p in sorted(VISUALS.glob("visual_*")) if p.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS]


def ffmpeg_filter_for(path_count, shot_seconds):
    parts=[]; labels=[]
    for i in range(path_count):
        label=f"v{i}"; parts.append(f"[{i}:v]trim=duration={shot_seconds},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}[{label}]"); labels.append(f"[{label}]")
    duration=min(MAX_SECONDS,path_count*shot_seconds); parts.append("".join(labels)+f"concat=n={path_count}:v=1:a=0,trim=duration={duration},setpts=PTS-STARTPTS[base]")
    return ";".join(parts),duration


def main():
    script_path=OUTPUT/"script.txt"; script=script_path.read_text(encoding="utf-8").strip() if script_path.exists() else ""
    if not script: raise RuntimeError("Generated script is empty")
    timings=load_caption_timings()
    if not timings: raise RuntimeError("Caption timing data is missing; generate the voice before rendering")
    audio=OUTPUT/"voice.mp3"
    if not audio.exists() or audio.stat().st_size < 10000: raise RuntimeError("Voice audio is missing or too small")
    audio_duration=min(MAX_SECONDS,media_duration(audio))
    if audio_duration <= 0: raise RuntimeError("Voice audio has no usable duration")
    files=visual_files()
    if not files: raise RuntimeError("No visuals found in assets/visuals")

    files=files[:max(1,int(audio_duration/DEFAULT_SHOT_SECONDS)+1)]; shot_seconds=audio_duration/len(files)
    video_count=sum(p.suffix.lower() in VIDEO_EXTS for p in files)
    print(f"Using {len(files)} visuals ({video_count} video clips, {len(files)-video_count} images) for {audio_duration:.1f}s narration")
    srt=make_srt(timings); filter_graph,duration=ffmpeg_filter_for(len(files),shot_seconds)
    base=OUTPUT/"video_base.mp4"; output=OUTPUT/"test-video.mp4"

    cmd=["ffmpeg","-y"]
    for path in files:
        if path.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop","1","-t",str(shot_seconds),"-i",str(path)]
        else:
            cmd += ["-stream_loop","-1","-t",str(shot_seconds),"-i",str(path)]
    cmd += ["-filter_complex",filter_graph,"-map","[base]","-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(base)]
    subprocess.run(cmd,check=True)

    subtitle_filter=f"subtitles={srt.as_posix()}:force_style='FontName=DejaVu Sans,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=180'"
    captioned=OUTPUT/"video_captioned.mp4"
    subprocess.run(["ffmpeg","-y","-i",str(base),"-vf",subtitle_filter,"-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-an",str(captioned)],check=True)
    subprocess.run(["ffmpeg","-y","-i",str(captioned),"-i",str(audio),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","128k","-shortest","-movflags","+faststart",str(output)],check=True)
    final_duration=media_duration(output); print(f"Created {output} ({final_duration:.1f}s) with narration audio and captions")

if __name__ == "__main__": main()
