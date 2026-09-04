"""Deterministic quality gate for normal-video production artifacts."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PLAN = OUTPUT / "normal_production" / "director_plan.json"
REPORT = OUTPUT / "normal_production" / "quality_report.json"


def main() -> None:
    if not PLAN.exists():
        raise RuntimeError("director_plan.json missing")
    data = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if not scenes:
        raise RuntimeError("Director produced no scenes")
    checks = {
        "scene_count": len(scenes),
        "scene_limit_ok": len(scenes) <= 18,
        "all_have_narration": all(bool(s.get("narration")) for s in scenes),
        "all_have_visual_prompt": all(bool(s.get("visual_prompt")) for s in scenes),
        "all_have_camera": all(bool(s.get("camera_motion") or s.get("shot")) for s in scenes),
        "all_have_lighting": all(bool(s.get("lighting")) for s in scenes),
        "character_bible_present": isinstance(data.get("character_bible"), list),
    }
    score = round(100 * sum(bool(v) for k, v in checks.items() if k != "scene_count") / (len(checks) - 1))
    report = {"score": score, "passed": score >= 80, "checks": checks}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Normal production quality score: {score}/100")
    if score < 80:
        raise RuntimeError("Normal production quality gate failed")


if __name__ == "__main__":
    main()
