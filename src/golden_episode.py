from __future__ import annotations

"""Create a production-ready 90-second golden-episode specification.

This intentionally separates story, acting, dialogue, music and SFX timing so the
renderer can animate a scene instead of simply sliding still images around.
"""

import json
from pathlib import Path

EPISODE = {
    "title": "Milo and the Little Star",
    "duration_seconds": 90,
    "audience": "preschool",
    "visual_style": "bright 2D children's cartoon, rounded shapes, expressive faces, warm cinematic lighting",
    "characters": [
        {"id": "milo", "name": "Milo", "role": "curious puppy", "voice": "warm_childlike_narrator"},
        {"id": "lumi", "name": "Lumi", "role": "tiny glowing firefly", "voice": "soft_high_friendly"},
    ],
    "scenes": [
        {"start":0,"end":12,"location":"bedroom","action":["Milo wakes","opens curtains","sees a tiny light outside","eyes widen"],"dialogue":"Milo: What's that little light?","music":"gentle_morning","sfx":["yawn","curtain_swish","soft_chime"]},
        {"start":12,"end":24,"location":"garden","action":["Milo runs outside","stops beside flowers","Lumi circles his nose","Milo laughs"],"dialogue":"Milo: Hello, little friend!","music":"playful_garden","sfx":["footsteps_grass","flutter","giggle"]},
        {"start":24,"end":36,"location":"garden_path","action":["Lumi flies toward a dark bush","Milo follows","he notices a frightened rabbit","Milo kneels gently"],"dialogue":"Milo: Don't worry. We'll help you.","music":"gentle_curiosity","sfx":["running","leaves","small_rabbit"]},
        {"start":36,"end":48,"location":"stream","action":["rabbit points across stream","Milo places stepping stones","crosses carefully","almost slips","laughs"],"dialogue":"Milo: One step... two steps... we can do it!","music":"light_adventure","sfx":["water","stone_tap","splash","laugh"]},
        {"start":48,"end":60,"location":"meadow","action":["Lumi reveals a tiny lost star-shaped lantern","Milo picks it up","lantern glows","everyone smiles"],"dialogue":"Milo: We found it!","music":"wonder","sfx":["magic_rise","sparkle","happy_gasp"]},
        {"start":60,"end":72,"location":"meadow","action":["Milo carries lantern home","friends follow","lantern lights the path","camera pulls wide"],"dialogue":"Narrator: Kindness can light even the darkest path.","music":"warm_heart","sfx":["soft_steps","sparkles","night_breeze"]},
        {"start":72,"end":84,"location":"garden","action":["Milo hangs lantern on tree","friends dance","Lumi loops through the lights","Milo claps"],"dialogue":"Milo: A little kindness makes a big light!","music":"celebration","sfx":["twinkle","claps","tiny_bells"]},
        {"start":84,"end":90,"location":"garden_night","action":["Milo waves","Lumi blinks","camera rises to stars","fade out"],"dialogue":"Narrator: And tomorrow, another adventure will begin.","music":"goodnight","sfx":["night_crickets","soft_chime"]},
    ],
    "audio_mix": {"voice_db": -3, "music_db": -18, "sfx_db": -10, "duck_music_under_voice_db": -6},
}


def main() -> None:
    out = Path("output/kids_animation/golden_episode.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(EPISODE, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {out}")


if __name__ == "__main__":
    main()
