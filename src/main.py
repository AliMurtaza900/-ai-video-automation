import json
import os
import time
from pathlib import Path
from google import genai
from google.genai import errors

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
HISTORY_FILE = DATA / "topic_history.json"
OUTPUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

# Prefer the newest capable Flash model first, then fall back to stable 3.5 variants.
MODELS = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
BASE_PROMPT = """
Create one original short-form video narration about ONE specific, genuinely interesting fact.
The finished narration will be voiced and edited automatically for a vertical YouTube Short.

PRIMARY GOAL:
{goal}

STRICT OUTPUT RULES:
- Return narration only. No title, labels, bullets, markdown, emojis, stage directions, or quotation marks.
- Aim for 75-105 words so the finished narration naturally lands around 30-45 seconds.
- Open with a punchy curiosity hook in the first sentence.
- Use short, natural sentences with varied rhythm. Avoid filler and repeated phrases.
- Explain the fact clearly enough that a viewer understands why it is surprising.
- End with a memorable curiosity/payoff line rather than "like and subscribe."
- Do not invent statistics, names, dates, quotes, or claims. If a detail is uncertain, leave it out.
- Keep the topic safe for general audiences and suitable for monetized YouTube Shorts.
- Make every sentence visually describable so the video can find useful public-domain/open-license imagery.
- Do not repeat any recent topic/concept below. Choose a clearly different subject, not a rewording.

Recent topics/scripts to avoid:
{recent}
"""


def load_history():
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        topics = data.get("topics", [])
        return topics if isinstance(topics, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_history(script):
    history = load_history()
    fingerprint = " ".join(script.lower().split())[:180]
    if fingerprint in history:
        return
    history.append(fingerprint)
    history = history[-40:]
    HISTORY_FILE.write_text(json.dumps({"topics": history}, indent=2), encoding="utf-8")


def generate_with_retry(client, model, prompt, attempts=4):
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except errors.ServerError as exc:
            if getattr(exc, "code", None) != 503 or attempt == attempts - 1:
                raise
            delay = 5 * (2 ** attempt)
            print(f"Gemini {model} is temporarily unavailable (503). Retrying in {delay}s...")
            time.sleep(delay)


def validate_script(script):
    words = script.split()
    if not 60 <= len(words) <= 125:
        raise RuntimeError(f"Generated narration length is {len(words)} words; expected 60-125")
    if any(token in script for token in ("```", "**", "#")):
        raise RuntimeError("Generated narration contains formatting instead of narration-only output")
    if script.count("!") > 3:
        raise RuntimeError("Generated narration is excessively punctuated")


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in GitHub Secrets")

    client = genai.Client(api_key=api_key)
    history = load_history()
    recent = "\n".join(f"- {item}" for item in history[-20:]) or "- none yet"
    goal = os.environ.get("VIDEO_GOAL", "Create the best current AI automation YouTube Short").strip()
    if not goal:
        goal = "Create the best current AI automation YouTube Short"
    prompt = BASE_PROMPT.format(goal=goal, recent=recent)

    last_error = None
    for model in MODELS:
        for generation_attempt in range(2):
            try:
                response = generate_with_retry(client, model, prompt)
                script = (response.text or "").strip()
                if not script:
                    raise RuntimeError(f"Gemini returned an empty response from {model}")
                validate_script(script)
                (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
                save_history(script)
                print(script)
                print(f"Script generated successfully with {model} ({len(script.split())} words).")
                return
            except errors.ServerError as exc:
                last_error = exc
                print(f"{model} unavailable; trying again or the next model...")
            except RuntimeError as exc:
                last_error = exc
                print(f"{model} produced an invalid narration: {exc}")
                if generation_attempt == 0:
                    prompt += "\nIMPORTANT: The previous output failed validation. Regenerate it within all rules."

    raise RuntimeError(f"No valid narration was generated: {last_error}")


if __name__ == "__main__":
    main()
