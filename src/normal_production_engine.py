"""Normal-video cinematic production engine.

This module is deliberately isolated from the kids-animation engines. It turns
an existing normal-video script into a structured director plan that later
stages can use for visual discovery, continuity checks and cinematic rendering.

Zero-cost design: no new paid API is required. Gemini is used when its existing
GEMINI_API_KEY is available; otherwise a deterministic local storyboard is
created so the pipeline remains runnable.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PRODUCTION = OUTPUT / "normal_production"
PRODUCTION.mkdir(parents=True, exist_ok=True)

MAX_SCENES = 18

DIRECTOR_PROMPT = """
You are the AI director for a premium vertical educational documentary Short.
Turn the supplied narration into a production-ready JSON storyboard.

Return ONLY valid JSON with this shape:
{
  "title": "short title",
  "visual_style": "cinematic documentary",
  "color_language": "natural cinematic contrast",
  "character_bible": [],
  "scenes": [
    {
      "scene_id": 1,
      "narration": "exact narration covered by this scene",
      "subject": "main subject",
      "location": "specific setting",
      "action": "what is happening",
      "emotion": "emotional intent",
      "shot": "specific camera shot",
      "camera_motion": "specific camera movement",
      "lighting": "specific lighting",
      "visual_prompt": "detailed visual search/generation prompt",
      "negative_prompt": "things to avoid",
      "sfx": [],
      "music_mood": "mood"
    }
  ]
}

Rules:
- Preserve the factual meaning of the narration. Do not add unsupported facts.
- Split the narration into visually meaningful beats, up to 18 scenes.
- Every scene must have a distinct composition and camera intention.
- Prefer cinematic specificity over generic words like "beautiful" or "amazing".
- Keep visual prompts suitable for general audiences and monetized YouTube.
- For real-world facts, favor documentary/photo-real imagery; for abstract ideas,
  use diagrams, macro shots, maps, scientific illustration or tasteful motion graphics.
- If people/characters recur, define stable appearance details in character_bible.
"""


def clean_script(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def split_beats(script: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    beats: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= 12:
            beats.append(sentence)
            continue
        size = max(7, (len(words) + 1) // 2)
        beats.extend(" ".join(words[i:i + size]) for i in range(0, len(words), size))
    return beats[:MAX_SCENES]


def terms(text: str) -> list[str]:
    stop = {"this", "that", "with", "from", "have", "about", "while", "they", "their", "there", "which", "would", "could", "because", "before", "after", "than", "into"}
    found = []
    for word in re.findall(r"[A-Za-z]{4,}", text.lower()):
        if word not in stop and word not in found:
            found.append(word)
    return found[:6] or ["documentary subject"]


def local_storyboard(script: str) -> dict:
    beats = split_beats(script)
    shots = [
        ("wide establishing shot", "slow cinematic push-in", "soft directional light"),
        ("medium documentary shot", "gentle lateral tracking", "natural window light"),
        ("macro detail shot", "slow controlled dolly", "high-detail rim light"),
        ("overhead composition", "subtle top-down drift", "clean even lighting"),
        ("close-up detail", "slow rack-focus simulation", "dramatic side light"),
        ("low-angle hero shot", "slow forward dolly", "backlit cinematic glow"),
    ]
    scenes = []
    for i, beat in enumerate(beats, 1):
        shot, motion, light = shots[(i - 1) % len(shots)]
        subject = ", ".join(terms(beat)[:3])
        scenes.append({
            "scene_id": i,
            "narration": beat,
            "subject": subject,
            "location": "contextually accurate documentary setting",
            "action": "show the subject clearly and naturally",
            "emotion": "curiosity and discovery",
            "shot": shot,
            "camera_motion": motion,
            "lighting": light,
            "visual_prompt": f"cinematic documentary photograph of {subject}, {beat}, realistic texture, natural depth, vertical composition, premium editorial photography",
            "negative_prompt": "text, watermark, logo, distorted anatomy, duplicate objects, oversaturated colors, low resolution",
            "sfx": [],
            "music_mood": "curious cinematic documentary",
        })
    return {
        "title": "Surprising Fact",
        "visual_style": "cinematic documentary",
        "color_language": "natural cinematic contrast",
        "character_bible": [],
        "scenes": scenes,
    }


def generate_with_gemini(script: str) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("DIRECTOR_MODEL", "gemini-3.7-flash"),
            contents=DIRECTOR_PROMPT + "\n\nNARRATION:\n" + script,
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
            return None
        data["scenes"] = data["scenes"][:MAX_SCENES]
        return data
    except Exception as exc:
        print(f"Director AI unavailable; using local storyboard: {exc}")
        return None


def validate(data: dict, script: str) -> dict:
    if not isinstance(data.get("scenes"), list) or not data["scenes"]:
        data = local_storyboard(script)
    for i, scene in enumerate(data["scenes"], 1):
        scene["scene_id"] = i
        for key in ("narration", "subject", "location", "action", "emotion", "shot", "camera_motion", "lighting", "visual_prompt", "negative_prompt", "music_mood"):
            value = scene.get(key)
            if not isinstance(value, str) or not value.strip():
                scene[key] = "documentary visual"
        if not isinstance(scene.get("sfx"), list):
            scene["sfx"] = []
    data.setdefault("title", "Surprising Fact")
    data.setdefault("visual_style", "cinematic documentary")
    data.setdefault("color_language", "natural cinematic contrast")
    data.setdefault("character_bible", [])
    return data


def main() -> dict:
    script_path = OUTPUT / "script.txt"
    if not script_path.exists():
        raise RuntimeError("Generated script is missing")
    script = clean_script(script_path.read_text(encoding="utf-8"))
    if not script:
        raise RuntimeError("Generated script is empty")

    data = generate_with_gemini(script) or local_storyboard(script)
    data = validate(data, script)
    out = PRODUCTION / "director_plan.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Director plan ready: {len(data['scenes'])} scenes -> {out}")
    return data


if __name__ == "__main__":
    main()
