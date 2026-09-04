"""Reference-driven character asset and continuity manifest for normal videos.

Zero-cost by default: it does not require a paid image API. It turns the
character bible into deterministic reference specifications, discovers any
existing local reference assets, creates stable hashes/metadata, and emits
provider-neutral prompts that optional image/I2V backends can consume.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "output" / "normal_production"
BIBLE = PROD / "character_bible.json"
DIRECTOR = PROD / "director_plan.json"
OUT = PROD / "character_references.json"
ASSET_ROOT = ROOT / "assets" / "character_references"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value).strip()).strip("_")
    return value.lower() or "character"


def image_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reference_prompt(character: dict) -> str:
    identity = character.get("identity_lock", {})
    wardrobe = character.get("wardrobe_lock", {})
    return (
        f"Create a clean canonical character reference sheet for {character.get('name', 'the character')}. "
        f"Age: {identity.get('age', 'consistent').} Face: {identity.get('face', 'stable').} "
        f"Eyes: {identity.get('eyes', 'stable').} Hair: {identity.get('hair', 'stable').} "
        f"Body: {identity.get('body', 'stable proportions').} Signature features: "
        f"{', '.join(map(str, identity.get('signature_features', []))) or 'none'}. "
        f"Wardrobe: {wardrobe.get('primary', 'signature outfit')}; colors: "
        f"{', '.join(map(str, wardrobe.get('colors', []))) or 'unchanged'}; accessories: "
        f"{', '.join(map(str, wardrobe.get('accessories', []))) or 'none'}. "
        "Front/three-quarter/full-body views, neutral pose, uncluttered background, "
        "consistent proportions, no text, no extra people."
    )


def build(bible: dict, plan: dict) -> dict:
    result = {"version": 1, "mode": "reference-first", "characters": []}
    for character in bible.get("characters", []):
        name = str(character.get("name", "Character"))
        directory = ASSET_ROOT / safe_name(name)
        files = image_files(directory) if directory.exists() else []
        refs = []
        for path in files:
            refs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size})
        result["characters"].append({
            "id": character.get("id"),
            "name": name,
            "reference_status": "available" if refs else "not_provided",
            "reference_images": refs,
            "canonical_prompt": reference_prompt(character),
            "immutable_traits": character.get("identity_lock", {}),
            "wardrobe_lock": character.get("wardrobe_lock", {}),
            "negative_identity": character.get("negative_identity", []),
        })

    scene_refs = []
    for scene in plan.get("scenes", []):
        subject = str(scene.get("subject", ""))
        matched = next((c for c in result["characters"] if c["name"].lower() == subject.lower()), None)
        scene_refs.append({
            "scene_id": scene.get("scene_id"),
            "subject": subject,
            "reference_character": matched["name"] if matched else None,
            "reference_images": matched["reference_images"] if matched else [],
            "reference_required": bool(matched),
            "continuity_instruction": "Use the canonical reference whenever the selected generation backend supports image conditioning; otherwise preserve the canonical prompt and mark the scene as prompt-only.",
        })
    result["scenes"] = scene_refs
    return result


def main() -> None:
    if not BIBLE.exists():
        raise RuntimeError("character_bible.json missing")
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    plan = json.loads(DIRECTOR.read_text(encoding="utf-8")) if DIRECTOR.exists() else {"scenes": []}
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = build(bible, plan)
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    available = sum(c["reference_status"] == "available" for c in manifest["characters"])
    print(f"Reference engine ready: {available}/{len(manifest['characters'])} character reference set(s) available")


if __name__ == "__main__":
    main()
