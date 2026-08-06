#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
mkdir -p output assets/visuals

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "ERROR: GEMINI_API_KEY is not set."
  echo "Run: export GEMINI_API_KEY='your-key'"
  exit 1
fi

rm -f output/test-video.mp4 output/video_base.mp4 output/video_captioned.mp4

python src/main.py
python src/fetch_visuals.py
python src/add_voice.py
python src/render_video.py

if [[ ! -s output/test-video.mp4 ]]; then
  echo "ERROR: output/test-video.mp4 was not created."
  exit 1
fi

ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 output/test-video.mp4

echo
echo "DONE: output/test-video.mp4"
