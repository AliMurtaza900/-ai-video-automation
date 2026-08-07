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

MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
BASE_PROMPT = """
Create a short vertical social-media video concept about ONE specific interesting fact.
Return a concise narration script only, suitable for a 30-45 second video.
Start with a strong hook and end with a curiosity-driven line.
Do not repeat any recent topic/concept listed below. Pick a clearly different subject,
not merely a different wording of the same fact.

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
    # Store a compact fingerprint of the generated concept. This avoids
    # repository growth while giving Gemini useful recent context.
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


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in GitHub Secrets")

    client = genai.Client(api_key=api_key)
    history = load_history()
    recent = "\n".join(f"- {item}" for item in history[-20:]) or "- none yet"
    prompt = BASE_PROMPT.format(recent=recent)

    last_error = None
    for model in MODELS:
        try:
            response = generate_with_retry(client, model, prompt)
            script = (response.text or "").strip()
            if not script:
                raise RuntimeError(f"Gemini returned an empty response from {model}")
            (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
            save_history(script)
            print(script)
            print(f"Script generated successfully with {model}.")
            return
        except errors.ServerError as exc:
            last_error = exc
            print(f"{model} unavailable; trying the next model...")

    raise RuntimeError(f"All Gemini models were temporarily unavailable: {last_error}")


if __name__ == "__main__":
    main()
