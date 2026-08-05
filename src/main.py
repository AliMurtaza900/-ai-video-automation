import os
from pathlib import Path
from google import genai

OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

PROMPT = """
Create a short vertical social-media video concept about an interesting fact.
Return a concise narration script only, suitable for a 30-45 second video.
Start with a strong hook and end with a curiosity-driven line.
"""


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in GitHub Secrets")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=PROMPT,
    )

    script = response.text.strip()
    (OUTPUT / "script.txt").write_text(script, encoding="utf-8")
    print(script)
    print("Script generated successfully. Video rendering is the next pipeline stage.")


if __name__ == "__main__":
    main()
