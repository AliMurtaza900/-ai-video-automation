import json
import os
import time
from pathlib import Path
from google import genai

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
HISTORY_FILE = DATA / "topic_history.json"
OUTPUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

MODELS = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
BASE_PROMPT = """
Create one original short-form video narration about ONE specific, genuinely interesting fact.

PRIMARY GOAL:
{goal}

RULES:
- Return narration only: no title, labels, bullets, markdown, emojis, or stage directions.
- Aim for 75-105 words.
- Open with a curiosity hook and finish with a memorable payoff.
- Do not invent statistics, names, dates, quotes, or uncertain claims.
- Keep it safe for general audiences and monetized YouTube Shorts.
- Make every sentence visually describable.
- Do not repeat recent topics below.

Recent topics:
{recent}
"""

FALLBACK_SCRIPTS = [
"A day on Venus is longer than a year on Venus. Venus spins so slowly that one full rotation takes about 243 Earth days, while it completes one trip around the Sun in about 225 Earth days. That means your calendar year would finish before your day did. Venus has another strange twist: it rotates in the opposite direction from most planets. So the planet next door to Earth is basically running on a completely different clock.",
"Octopuses have three hearts, but that is not even the strangest part. Two hearts pump blood toward the gills, while the third sends it around the rest of the body. Even stranger, when an octopus swims, the main heart temporarily stops beating. That is one reason octopuses often prefer crawling instead of swimming when they can. Every time one takes off through the water, its body is doing something remarkably different from when it walks.",
"Bananas are berries, but strawberries are not botanical berries. In botany, a berry develops from one flower with one ovary and usually contains several seeds inside its flesh. A banana fits that definition surprisingly well. A strawberry does not, because the little dots on its surface are actually individual fruits. So the fruit aisle at a supermarket is quietly breaking the rules you learned from everyday language."
]

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
    if fingerprint not in history:
        history.append(fingerprint)
    HISTORY_FILE.write_text(json.dumps({"topics": history[-40:]}, indent=2), encoding="utf-8")

def error_code(exc):
    return getattr(exc, "code", None) or getattr(getattr(exc, "response", None), "status_code", None)

def generate(client, model, prompt):
    for attempt in range(3):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except Exception as exc:
            code = error_code(exc)
            if code == 429 or code not in {500, 502, 503, 504} or attempt == 2:
                raise
            delay = min(30, 3 * (2 ** attempt))
            print(f"Gemini {model} temporary error {code}; retrying in {delay}s...")
            time.sleep(delay)

def validate_script(script):
    words = script.split()
    if not 60 <= len(words) <= 125:
        raise RuntimeError(f"Invalid narration length: {len(words)} words")
    if any(token in script for token in ("```", "**", "#")):
        raise RuntimeError("Narration contains formatting")
    if script.count("!") > 3:
        raise RuntimeError("Narration is excessively punctuated")

def fallback_script(history):
    used = set(history)
    for script in FALLBACK_SCRIPTS:
        if " ".join(script.lower().split())[:180] not in used:
            return script
    return FALLBACK_SCRIPTS[len(history) % len(FALLBACK_SCRIPTS)]

def main():
    history = load_history()
    recent = "\n".join(f"- {item}" for item in history[-20:]) or "- none yet"
    goal = os.environ.get("VIDEO_GOAL", "Create a high-retention, monetization-safe YouTube Short about a genuinely surprising fact").strip() or "Create a surprising educational YouTube Short"
    prompt = BASE_PROMPT.format(goal=goal, recent=recent)
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        for model in MODELS:
            for attempt in range(2):
                try:
                    response = generate(client, model, prompt)
                    script = (response.text or "").strip()
                    if not script:
                        raise RuntimeError("Gemini returned empty text")
                    validate_script(script)
                    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
                    save_history(script)
                    print(f"Generated with {model}: {len(script.split())} words")
                    return
                except Exception as exc:
                    code = error_code(exc)
                    print(f"{model} attempt {attempt + 1} failed ({code or type(exc).__name__}): {exc}")
                    if code in {401, 403}:
                        break
                    if attempt == 0:
                        prompt += "\nRegenerate and strictly obey every rule."
    script = fallback_script(history)
    validate_script(script)
    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
    save_history(script)
    print(f"Using local fallback narration: {len(script.split())} words")

if __name__ == "__main__":
    main()
