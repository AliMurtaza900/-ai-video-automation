from __future__ import annotations

# Keep the existing renderer intact; this patch replaces only the fragile audio mix.
# The implementation below is intentionally self-contained so the workflow cannot
# fail because ffmpeg's loudnorm/amix filter graph rejects a generated WAV.

import os
import math
import wave
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "kids_animation"
SCENES = OUT / "scenes"
FPS = 30
DURATION = 6

# The remainder of the production implementation is imported from the stable
# scene renderer when available. This keeps this file backward-compatible with
# existing workflow imports.
try:
    from vector_animation_engine import *  # noqa: F401,F403
except ImportError:
    pass


def ffmpeg(args):
    proc = subprocess.run(["ffmpeg", *args], cwd=ROOT, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        tail = "\n".join(proc.stderr.splitlines()[-30:])
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{tail}")


def _wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def mix(video, voice_file, music, out, index):
    """Robust narration/music mix.

    The previous filter graph could exit 222 on GitHub's ffmpeg build. In
    particular, combining loudnorm + amix + limiter in one graph made failures
    difficult to diagnose. We normalize the narration first, explicitly loop
    the music to the narration duration, duck music, and encode the final audio
    in a second simple graph.
    """
    voice_len = max(0.1, _wav_duration(voice_file))
    # Normalize speech as a standalone stream. Two-pass loudnorm is unnecessary
    # for this short-form content and the one-pass compressor is deterministic.
    normalized = Path(out).with_suffix(".voice-normalized.wav")
    ffmpeg([
        "-y", "-i", str(voice_file),
        "-af", "highpass=f=75,lowpass=f=14500,acompressor=threshold=-24dB:ratio=3:attack=8:release=100:makeup=5,volume=2.5,aresample=48000",
        "-ac", "1", "-c:a", "pcm_s16le", str(normalized)
    ])

    # Mix using the shortest real program stream. Music is deliberately quiet,
    # while narration is already normalized and boosted above.
    ffmpeg([
        "-y", "-i", str(video), "-i", str(normalized), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        "[1:a]aresample=48000,volume=1.0[v];[2:a]aresample=48000,volume=0.10,afade=t=in:st=0:d=0.4[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0.2,alimiter=limit=0.95[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{voice_len:.3f}", "-movflags", "+faststart", str(out)
    ])
    try:
        normalized.unlink()
    except FileNotFoundError:
        pass


def main():
    # Delegate to the maintained vector renderer. This compatibility entry point
    # exists because older workflow commits call premium_cartoon_engine.py.
    from vector_animation_engine import main as vector_main
    return vector_main()


if __name__ == "__main__":
    raise SystemExit(main())
