# Run the video generator in Codespaces

## 1. Create a Codespace

Open the repository in GitHub and choose **Code → Codespaces → Create codespace on main**.

The repository's `.devcontainer/devcontainer.json` installs Python dependencies and FFmpeg automatically.

## 2. Set the Gemini key

In the Codespaces terminal:

```bash
export GEMINI_API_KEY='YOUR_GEMINI_API_KEY'
```

For a persistent Codespaces secret, add `GEMINI_API_KEY` in your GitHub Codespaces secrets and restart/rebuild the Codespace.

## 3. Run everything

```bash
bash run_video.sh
```

That single command runs:

1. Gemini script generation
2. Public real-footage visual matching
3. Voice generation
4. FFmpeg rendering
5. Audio/caption muxing
6. Output verification

The finished file is:

`output/test-video.mp4`

## Important

This script **does not upload to YouTube**. It is for testing the video locally inside the Codespace first.
