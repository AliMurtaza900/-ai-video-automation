"""Character consistency layer for the isolated normal-video pipeline."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PROD = OUTPUT / "normal_production"
PLAN = PROD / "director_plan.json"
BIBLE = PROD / "character_bible.json"
PROMPTS = PROD / "character_scene_prompts.json"
MAX_CHARACTERS = 8


def clean(v, default=""):
    if v is None: return default
    if isinstance(v, (str, int, float, bool)): return v
    return str(v)


def normalize_character(raw, index):
    wardrobe = raw.get("wardrobe_lock", {})
    if not isinstance(wardrobe, dict): wardrobe = {}
    return {
        "id": clean(raw.get("id"), f"char_{index:02d}"),
        "name": clean(raw.get("name"), f"Character {index}"),
        "role": clean(raw.get("role"), "supporting character"),
        "identity_lock": {
            "age": clean(raw.get("age"), "consistent with story"),
            "face": clean(raw.get("face"), "stable facial structure and distinctive features"),
            "eyes": clean(raw.get("eyes"), "consistent eye shape and color"),
            "hair": clean(raw.get("hair"), "consistent hairstyle, length and color"),
            "skin_or_surface": clean(raw.get("skin_or_surface"), "consistent"),
            "body": clean(raw.get("body"), "consistent proportions and silhouette"),
            "signature_features": raw.get("signature_features", []),
        },
        "wardrobe_lock": {
            "primary": clean(wardrobe.get("primary"), "consistent signature outfit"),
            "colors": wardrobe.get("colors", []),
            "accessories": wardrobe.get("accessories", []),
        },
        "personality": clean(raw.get("personality"), "consistent personality"),
        "expressions": raw.get("expressions", ["neutral", "happy", "surprised", "concerned"]),
        "references": raw.get("references", []),
        "negative_identity": ["different face", "different age", "different hairstyle", "different hair color", "different body proportions", "different outfit colors", "unrequested accessories", "identity drift", "duplicate character", "deformed face"],
    }


def characters_from_plan(plan):
    raw = plan.get("character_bible") or []
    if isinstance(raw, dict):
        raw = [dict(v, name=k) if isinstance(v, dict) else {"name": k} for k, v in raw.items()]
    if not raw:
        names = []
        for scene in plan.get("scenes", []):
            name = clean(scene.get("subject"))
            if name and name.lower() not in {x.lower() for x in names}: names.append(name)
        raw = [{"name": n, "role": "scene subject"} for n in names[:MAX_CHARACTERS]]
    return [normalize_character(c if isinstance(c, dict) else {"name": c}, i) for i, c in enumerate(raw[:MAX_CHARACTERS], 1)]


def identity_block(c):
    x, w = c["identity_lock"], c["wardrobe_lock"]
    sig = ", ".join(map(str, x["signature_features"])) or "none"
    acc = ", ".join(map(str, w["accessories"])) or "none"
    colors = ", ".join(map(str, w["colors"])) or "unchanged"
    return (f"IDENTITY LOCK — {c['name']}: age={x['age']}; face={x['face']}; eyes={x['eyes']}; hair={x['hair']}; surface={x['skin_or_surface']}; body={x['body']}; signature={sig}; wardrobe={w['primary']}; wardrobe colors={colors}; accessories={acc}. Preserve this identity exactly; change only pose, expression, action, camera and environment required by the shot.")


def build(plan):
    chars = characters_from_plan(plan)
    by_name = {c["name"].lower(): c for c in chars}
    scenes = []
    for scene in plan.get("scenes", []):
        subject = clean(scene.get("subject"))
        matched = by_name.get(subject.lower())
        blocks = [identity_block(matched)] if matched else [identity_block(c) for c in chars if c["name"].lower() in subject.lower()]
        prompt = "\n".join(blocks + ["CONTINUITY LOCK — Preserve identity, wardrobe, props, style and screen direction from the previous approved shot. Do not redesign the character.", clean(scene.get("visual_prompt"), clean(scene.get("action"), "cinematic scene"))])
        negatives = list(dict.fromkeys(sum((c["negative_identity"] for c in chars), [])))
        scenes.append({"scene_id": scene.get("scene_id"), "prompt": prompt, "negative_prompt": ", ".join(negatives)})
    return {"version": 1, "policy": "Reference-first identity; immutable traits stay fixed unless the storyboard explicitly records a story-driven change.", "characters": chars}, {"scenes": scenes}


def main():
    if not PLAN.exists(): raise RuntimeError("director_plan.json is missing")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    bible, prompts = build(plan)
    PROD.mkdir(parents=True, exist_ok=True)
    BIBLE.write_text(json.dumps(bible, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PROMPTS.write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Character consistency ready: {len(bible['characters'])} locked character(s)")

if __name__ == "__main__": main()
