import os
import time
from pathlib import Path
from google import genai
from google.genai import errors

OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

PROMPT = """
Create a short vertical social-media video concept about an interesting fact.
Return a concise narration script only, suitable for a 30-45 second video.
Start with a strong hook and end with a curiosity-driven line.
"""

MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]


def generate_with_retry(client, model, attempts=4):
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=model, contents=PROMPT)
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

    last_error = None
    for model in MODELS:
        try:
            response = generate_with_retry(client, model)
            script = (response.text or "").strip()
            if not script:
                raise RuntimeError(f"Gemini returned an empty response from {model}")
            (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
            print(script)
            print(f"Script generated successfully with {model}.")
            return
        except errors.ServerError as exc:
            last_error = exc
            print(f"{model} unavailable; trying the next model...")

    raise RuntimeError(f"All Gemini models were temporarily unavailable: {last_error}")


if __name__ == "__main__":
    main()
