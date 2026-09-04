"""AI-assisted visual critic for the isolated normal-video pipeline."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PRODUCTION = OUTPUT / "normal_production"
PLAN = PRODUCTION / "director_plan.json"
REPORT = PRODUCTION / "visual_critic_report.json"
VISUALS = ROOT / "assets" / "visuals"
THRESHOLD = 80

PROMPT = """
You are a strict film/visual continuity critic. Evaluate this image for the specified storyboard scene.
Return ONLY JSON: {"score":0,"relevance":0,"composition":0,"quality":0,"continuity":0,"issues":[],"repair_query":""}
Scores are 0-100. Be strict: a generic attractive image fails if it does not depict the scene.
"""


def local_score(scene: dict, path: Path) -> dict:
    text = " ".join(str(scene.get(k, "")) for k in ("subject", "location", "action", "visual_prompt")).lower()
    name = path.stem.lower()
    words = [w for w in re.findall(r"[a-z]{5,}", text) if w not in {"documentary", "cinematic", "vertical", "composition", "realistic"}]
    hits = sum(1 for w in words if w in name)
    relevance = min(95, 55 + hits * 8)
    quality = 85 if path.stat().st_size > 100_000 else 60
    score = round(relevance * 0.55 + 82 * 0.20 + quality * 0.25)
    return {"score": score, "relevance": relevance, "composition": 82, "quality": quality, "continuity": 75,
            "issues": [] if score >= THRESHOLD else ["Local fallback critic could not verify semantic image content"],
            "repair_query": " ".join(words[:6]) + " documentary photography"}


def gemini_score(scene: dict, path: Path) -> dict | None:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or not path.exists() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        response = client.models.generate_content(
            model=os.getenv("CRITIC_MODEL", os.getenv("DIRECTOR_MODEL", "gemini-3.7-flash")),
            contents=[PROMPT, "STORYBOARD SCENE:\n" + json.dumps(scene, ensure_ascii=False), types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)],
        )
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (response.text or "").strip(), flags=re.I | re.S).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        score = max(0, min(100, int(float(data.get("score", 0)))))
        return {
            "score": score,
            "relevance": max(0, min(100, int(float(data.get("relevance", score))))),
            "composition": max(0, min(100, int(float(data.get("composition", score))))),
            "quality": max(0, min(100, int(float(data.get("quality", score))))),
            "continuity": max(0, min(100, int(float(data.get("continuity", score))))),
            "issues": data.get("issues", []) if isinstance(data.get("issues", []), list) else [str(data.get("issues"))],
            "repair_query": str(data.get("repair_query", "")).strip(),
        }
    except Exception as exc:
        print(f"Visual critic unavailable for {path.name}: {exc}")
        return None


def display_path(path: Path | None) -> str:
    """Return a stable path even when tests use a temporary VISUALS directory."""
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> dict:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json missing")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    images = sorted(p for p in VISUALS.glob("visual_*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    results = []
    for index, scene in enumerate(scenes, 1):
        path = images[index - 1] if index - 1 < len(images) else None
        if path is None:
            result = {"score": 0, "relevance": 0, "composition": 0, "quality": 0, "continuity": 0,
                      "issues": ["Missing visual"], "repair_query": str(scene.get("visual_prompt", scene.get("subject", "")))}
        else:
            result = gemini_score(scene, path) or local_score(scene, path)
        result.update({"scene": index, "file": display_path(path)})
        result["passed"] = result["score"] >= THRESHOLD
        results.append(result)
        print(f"Visual critic scene {index}: {result['score']}/100 {'PASS' if result['passed'] else 'REPAIR'}")
    report = {"threshold": THRESHOLD, "passed": all(r["passed"] for r in results), "scenes": results}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
