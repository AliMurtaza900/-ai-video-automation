"""Bridge the AI director plan into the existing visual collector.

The collector remains responsible for downloading media and preserving source
metadata. This file only supplies richer per-scene search queries/prompts.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "output" / "normal_production" / "director_plan.json"
QUERIES = ROOT / "output" / "normal_production" / "visual_queries.json"


def main() -> None:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json is missing; run normal_production_engine.py first")
    data = json.loads(PLAN.read_text(encoding="utf-8"))
    result = []
    for scene in data.get("scenes", []):
        subject = scene.get("subject", "")
        prompt = scene.get("visual_prompt", "")
        queries = [
            subject,
            f"{subject} documentary photography",
            f"{subject} close up detail",
            f"{subject} wide shot landscape",
        ]
        result.append({
            "scene_id": scene.get("scene_id"),
            "narration": scene.get("narration", ""),
            "queries": list(dict.fromkeys(q.strip() for q in queries if q.strip())),
            "visual_prompt": prompt,
            "negative_prompt": scene.get("negative_prompt", ""),
            "shot": scene.get("shot", ""),
            "camera_motion": scene.get("camera_motion", ""),
            "lighting": scene.get("lighting", ""),
        })
    QUERIES.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Visual plan ready: {len(result)} scenes -> {QUERIES}")


if __name__ == "__main__":
    main()
