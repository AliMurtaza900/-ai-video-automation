# AI Video Automation

Fully automated AI video creation and publishing system for YouTube Shorts.

## What it does

1. Generates a high-retention fact narration with Gemini
2. Fetches free/open-license visuals (Openverse + Wikimedia Commons)
3. Creates natural TTS voice + caption timings (edge-tts)
4. Renders a vertical 1080x1920 Short with motion, captions, and loudness normalization
5. Uploads to YouTube (with thumbnail)

## Required GitHub Secrets

- `GEMINI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

## Dependencies

See `requirements.txt`. Key packages:

- `google-genai` (Gemini API)
- `edge-tts` (voice)
- `Pillow`, `requests`, Google API client libraries

System: `ffmpeg` (installed by the workflow).

## Workflows

- **Generate AI Video** (`.github/workflows/generate-video.yml`) – scheduled + manual fact Shorts pipeline
- **Kids Animation Studio** – separate cartoon/poem pipeline
- **Test AI Video** – end-to-end dry run

## Recent fixes (Aug 2026)

- Added missing `google-genai` and `edge-tts` packages (was causing ImportError)
- Updated model preference to `gemini-3.7-flash` with 3.5 fallbacks
- Fixed YouTube upload defaults (no longer hard-coded kids content)
- Workflow now sets proper title/description/category/madeForKids flags
