"""Shot-level acting and cinematic direction for normal videos.

Turns each storyboard scene into a small sequence of purposeful shots while
keeping continuity deterministic when Gemini is unavailable. This layer is
provider-neutral and does not alter any kids-animation engine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "output" / "normal_production"
DIRECTOR = PROD / "director_plan.json"
BIBLE = PROD / "character_bible.json"
REFERENCES = PROD / "character_references.json"
OUT = PROD / "scene_shot_plan.json"

SHOT_TYPES = ("establishing", "wide", "medium", "close_up", "reaction", "action", "insert", "POV")
MOVES = ("static", "push_in", "pull_out", "track_left", "track_right", "tilt_up", "tilt_down", "orbit")
TRANSITIONS = ("cut", "match_cut", "dissolve", "whip_pan")


def clamp_duration(value: object, low: float = 0.8, high: float = 3.5) -> float:
    try:
        return round(max(low, min(high, float(value))), 2)
    except (TypeError, ValueError):
        return 1.5


def character_for(scene: dict, bible: dict, refs: dict) -> dict | None:
    subject = str(scene.get("subject", "")).lower()
    cid = str(scene.get("character_id", "")).lower()
    for c in bible.get("characters", []):
        if str(c.get("id", "")).lower() == cid or str(c.get("name", "")).lower() == subject:
            return c
    for c in refs.get("characters", []):
        if str(c.get("name", "")).lower() == subject:
            return c
    return None


def make_shots(scene: dict, previous_end: dict | None, character: dict | None, scene_index: int) -> list[dict]:
    action = str(scene.get("action") or "perform the described action")
    emotion = str(scene.get("emotion") or "focused")
    location = str(scene.get("location") or "the scene location")
    camera = str(scene.get("camera_motion") or "subtle cinematic movement")
    lighting = str(scene.get("lighting") or "cinematic natural light")
    subject = str(scene.get("subject") or "subject")
    narration = str(scene.get("narration") or "")
    style = str(scene.get("visual_prompt") or "cinematic, detailed, realistic motion")
    immutable = character.get("identity_lock", {}) if character else {}
    wardrobe = character.get("wardrobe_lock", {}) if character else {}
    identity = (
        f"Preserve face={immutable.get('face','unchanged')}; eyes={immutable.get('eyes','unchanged')}; "
        f"hair={immutable.get('hair','unchanged')}; body={immutable.get('body','unchanged')}; "
        f"wardrobe={wardrobe.get('primary','unchanged')}."
    )

    if scene_index == 1:
        sequence = [
            ("establishing", 1.2, "static", "reveal the location and spatial context"),
            ("medium", 1.5, camera, f"show {subject} beginning to {action}"),
            ("close_up", 1.2, "push_in", f"capture {subject}'s {emotion} expression and eye-line"),
        ]
    else:
        sequence = [
            ("wide", 1.0, camera, f"continue {subject}'s movement with clear screen direction"),
            ("medium", 1.5, camera, f"show the main action: {action}"),
            ("reaction", 1.1, "push_in", f"show {subject}'s {emotion} reaction"),
            ("close_up", 1.0, "static", f"hold the emotional beat on {subject}"),
        ]

    shots: list[dict] = []
    for n, (shot_type, duration, move, beat) in enumerate(sequence, 1):
        start_state = previous_end if n == 1 and previous_end else {
            "position": "natural screen position",
            "facing": "toward action",
            "gaze": "scene focal point",
            "emotion": emotion,
            "pose": "natural continuous pose",
        }
        end_state = {
            "position": "maintain screen direction unless action requires a motivated change",
            "facing": "toward the active focal point",
            "gaze": "follow the active subject or object",
            "emotion": emotion,
            "pose": f"pose consistent with beat: {beat}",
        }
        negative = "identity drift, age change, face change, hair change, wardrobe change, extra limbs, duplicate subject, deformed hands, broken anatomy, random text, watermark"
        shots.append({
            "shot_id": f"scene_{scene_index:02d}_shot_{n:02d}",
            "shot_type": shot_type,
            "duration": clamp_duration(duration),
            "framing": {"shot_type": shot_type, "subject_position": "center or rule-of-thirds as motivated by action", "headroom": "natural"},
            "camera_movement": move,
            "screen_direction": "preserve established left/right direction across cuts",
            "location": location,
            "character_action": beat,
            "facial_expression": emotion,
            "gaze_eye_line": "look toward the object/person driving the beat; avoid wandering gaze",
            "body_gesture": "natural weight shift and gesture supporting the action",
            "dialogue_emotional_beat": narration,
            "start_state": start_state,
            "end_state": end_state,
            "transition": "cut" if n < len(sequence) else "match_cut",
            "lighting": lighting,
            "sound_sfx": scene.get("sfx") or "subtle environmental sound matching the location",
            "music_mood": scene.get("music_mood") or "cinematic and emotionally aligned",
            "motion_prompt": f"{style}. Shot: {shot_type}. {beat}. Smooth motivated {move}. {identity} Natural facial acting, eye-line, body mechanics, cinematic lighting, believable depth and motion.",
            "negative_prompt": negative,
        })
    return shots


def fallback_plan(plan: dict, bible: dict, refs: dict) -> dict:
    scenes_out = []
    previous_end = None
    for i, scene in enumerate(plan.get("scenes", []), 1):
        character = character_for(scene, bible, refs)
        shots = make_shots(scene, previous_end, character, i)
        previous_end = shots[-1]["end_state"] if shots else previous_end
        scenes_out.append({
            "scene_id": scene.get("scene_id", i),
            "subject": scene.get("subject", ""),
            "shots": shots,
            "scene_continuity": "Start from the previous scene's final state; preserve identity, wardrobe, screen direction and emotional progression.",
        })
    return {
        "version": 1,
        "mode": "deterministic-shot-director",
        "shot_types": list(SHOT_TYPES),
        "scenes": scenes_out,
    }


def try_gemini(plan: dict, bible: dict, refs: dict) -> dict | None:
    """Optional AI pass; structural fallback remains the source of truth."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        prompt = (
            "You are a cinematic animation director. Return ONLY valid JSON. "
            "Create a shot plan for the supplied scenes. Every shot must contain: "
            "shot_id, shot_type, duration, framing, camera_movement, screen_direction, "
            "character_action, facial_expression, gaze_eye_line, body_gesture, dialogue_emotional_beat, "
            "start_state, end_state, transition, lighting, sound_sfx, music_mood, motion_prompt, negative_prompt. "
            "Keep shots simple and physically continuous. Never alter locked character identity or wardrobe. "
            f"SCENES={json.dumps(plan.get('scenes', []), ensure_ascii=False)} "
            f"CHARACTERS={json.dumps(bible.get('characters', []), ensure_ascii=False)} "
            f"REFERENCES={json.dumps(refs.get('scenes', []), ensure_ascii=False)}"
        )
        model = os.getenv("SCENE_DIRECTOR_MODEL", os.getenv("DIRECTOR_MODEL", "gemini-3.7-flash"))
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", "") or ""
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(text[start:end + 1])
        if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
            return None
        return data
    except Exception as exc:
        print(f"Scene-director AI pass unavailable: {exc}; using deterministic plan")
        return None


def main() -> None:
    if not DIRECTOR.exists():
        raise RuntimeError("director_plan.json missing")
    plan = json.loads(DIRECTOR.read_text(encoding="utf-8"))
    bible = json.loads(BIBLE.read_text(encoding="utf-8")) if BIBLE.exists() else {"characters": []}
    refs = json.loads(REFERENCES.read_text(encoding="utf-8")) if REFERENCES.exists() else {"characters": [], "scenes": []}
    data = try_gemini(plan, bible, refs) or fallback_plan(plan, bible, refs)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Shot director ready: {sum(len(s.get('shots', [])) for s in data.get('scenes', []))} shots")


if __name__ == "__main__":
    main()
