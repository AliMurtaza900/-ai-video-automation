"""Replace failed normal-video visuals with better free-source candidates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Support both `python -m src.normal_visual_repair` and direct execution.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fetch_visuals import download, make_local_fallback, search_candidates

OUTPUT = ROOT / "output"
PRODUCTION = OUTPUT / "normal_production"
PLAN = PRODUCTION / "director_plan.json"
REPORT = PRODUCTION / "visual_critic_report.json"
VISUALS = ROOT / "assets" / "visuals"
MAX_REPAIRS = 2


def main() -> None:
    if not PLAN.exists() or not REPORT.exists():
        raise RuntimeError("Director plan or visual critic report missing")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    repairs = 0
    for item in report.get("scenes", []):
        if item.get("passed") or repairs >= MAX_REPAIRS:
            continue
        number = int(item.get("scene", 0))
        if not 1 <= number <= len(scenes):
            continue
        scene = scenes[number - 1]
        query = item.get("repair_query") or scene.get("visual_prompt") or scene.get("subject", "documentary")
        terms = str(query).split()[:8]
        candidates = search_candidates(str(scene.get("narration", "")), terms, False)
        target = VISUALS / f"visual_{number - 1:02d}.jpg"
        for candidate in candidates:
            try:
                path = download(candidate, number - 1)
                if path != target:
                    path.replace(target)
                print(f"Repaired scene {number}: {candidate.get('source')} -> {target.name}")
                repairs += 1
                break
            except Exception as exc:
                print(f"Repair candidate failed for scene {number}: {exc}")
        else:
            # Keep the pipeline deterministic if every remote candidate fails.
            make_local_fallback(number - 1, str(scene.get("narration", "documentary scene")))
            print(f"Scene {number}: no repair candidate downloaded; retained local fallback")
    print(f"Visual repair pass complete: {repairs} scene(s) replaced")


if __name__ == "__main__":
    main()
