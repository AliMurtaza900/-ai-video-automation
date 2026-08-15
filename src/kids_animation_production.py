from __future__ import annotations

import json, math, os, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "kids_animation"
ASSETS = OUTPUT / "assets"
SCENES = OUTPUT / "scenes"
FPS, WIDTH, HEIGHT, SCENE_SECONDS = 24, 1280, 720, 6

# A complete 12-scene mini episode. Each scene has its own action beat rather than
# simply moving the same still image across the screen.
SCENES_DATA = [
    ("bedroom", "Milo wakes up, rubs his sleepy eyes, and hears a tiny bird singing outside."),
    ("garden", "He opens the door and skips into the garden. A blue butterfly circles around his head."),
    ("path", "The butterfly leads Milo down a winding path, past dancing leaves and three cheerful birds."),
    ("stream", "Milo reaches a little stream. He hops across the stepping stones, splash, splash, splash!"),
    ("meadow", "In the meadow, Milo hears a soft cry and discovers a little flower with its petals closed."),
    ("flower", "The flower whispers, I am thirsty. Milo smiles and promises to help."),
    ("water", "Milo carries a blue watering can and gently gives the flower a drink."),
    ("magic", "The flower stretches toward the sun, opens wide, and sends tiny golden sparkles into the air."),
    ("friends", "The birds, butterfly, and a little rabbit arrive. Everyone cheers for Milo and the flower."),
    ("dance", "Music starts, and Milo dances with his new friends around the bright flower."),
    ("sunset", "As the sun goes down, Milo learns that one small act of kindness can make a big difference."),
    ("goodbye", "Milo waves goodnight to his friends. Tomorrow, there will be another adventure."),
]

POEM_LINES = [
    "Good morning, Milo, up you go! Stretch your paws and say hello!",
    "Skip through the garden, bright and green. Chase the butterfly, blue and clean!",
    "Follow the path, one, two, three. Sing with the birds in the old oak tree!",
    "Splash at the stream, hop on the stones. Careful little paws, no wet toes!",
    "In the meadow, what do we see? A tiny flower waiting patiently.",
    "The little flower whispers low, I need some water so I can grow.",
    "Tip the can and water slow. Kind little hearts help flowers grow.",
    "Open, open, petals bright! Sparkle, sparkle, what a sight!",
    "Friends come flying, hopping too. There is room for every friend with you.",
    "Clap your paws and dance around. Kindness makes a happy sound!",
    "When the golden sun sinks low, Milo knows what kindness can grow.",
    "Goodnight, friends, the stars shine through. Tomorrow brings a dream for you!",
]

STORY_LINES = [
    "Milo woke up with a yawn. From outside came a tiny bird song, cheerful and bright.",
    "He opened the door and skipped into the garden, where a blue butterfly danced around him.",
    "The butterfly flew along the path. Milo followed, while three little birds hopped beside him.",
    "Soon Milo reached a sparkling stream. He crossed the stones carefully, one hop at a time.",
    "On the other side he heard a tiny sound. In the meadow sat a little flower with closed petals.",
    "The flower whispered that it was thirsty. Milo looked around and knew exactly what to do.",
    "He carried a small blue watering can and gave the flower a gentle drink.",
    "The flower lifted its head, opened its petals, and filled the meadow with golden sparkles.",
    "The birds, butterfly, and a little rabbit came running. Everyone wanted to celebrate.",
    "They danced around the flower together. Milo laughed because kindness had brought everyone closer.",
    "At sunset, Milo rested beside the flower. He learned that even a small kindness can brighten a whole day.",
    "Milo waved goodnight to his friends and walked home smiling, ready for tomorrow's adventure.",
]


def run(cmd: list[str]) -> None:
    if not cmd:
        raise ValueError("empty command")
    if cmd[0].startswith("-"):
        cmd.insert(0, "ffmpeg")
    if shutil.which(cmd[0]) is None:
        raise RuntimeError(f"Required executable not found: {cmd[0]}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def make_background(kind: str, path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), (145, 205, 245))
    d = ImageDraw.Draw(img)
    if kind == "bedroom":
        img.paste((246, 226, 190), [0, 0, WIDTH, HEIGHT])
        d.rectangle([0, 500, WIDTH, HEIGHT], fill=(211, 178, 135))
        d.rectangle([115, 275, 525, 500], fill=(105, 150, 205), outline=(70, 95, 135), width=8)
        d.rectangle([760, 110, 1030, 330], fill=(165, 210, 245), outline=(120, 155, 190), width=6)
        d.ellipse([835, 145, 955, 265], fill=(255, 215, 85))
        d.rectangle([750, 330, 1040, 500], fill=(238, 230, 212))
        return

    # Consistent colorful cartoon landscape.
    d.rectangle([0, 0, WIDTH, 420], fill=(150, 210, 250))
    d.ellipse([930, 55, 1080, 205], fill=(255, 220, 92))
    for cx, cy in [(180, 110), (430, 150), (720, 85)]:
        d.ellipse([cx-75, cy-25, cx+75, cy+25], fill=(245, 250, 255))
        d.ellipse([cx-25, cy-45, cx+70, cy+25], fill=(245, 250, 255))
    d.polygon([(0, 430), (250, 295), (490, 430), (740, 285), (1280, 430), (1280, 720), (0, 720)], fill=(135, 190, 105))
    d.rectangle([0, 510, WIDTH, HEIGHT], fill=(105, 180, 100))
    # Trees
    for x, y, scale in [(80, 290, 1.0), (1130, 300, 1.15), (380, 350, .75)]:
        d.rectangle([x-15, y, x+15, y+160], fill=(105, 72, 42))
        d.ellipse([x-80*scale, y-75*scale, x+80*scale, y+45*scale], fill=(70, 145, 78))
        d.ellipse([x-45*scale, y-115*scale, x+70*scale, y+15*scale], fill=(82, 160, 82))

    if kind in {"garden", "flower", "water", "friends", "dance", "meadow"}:
        for x in range(80, 1230, 105):
            y = 500 + (x * 7 % 70)
            d.line([x, y, x, y+45], fill=(45, 125, 55), width=5)
            d.ellipse([x-14, y-14, x+14, y+14], fill=(245, 120, 170))
            d.ellipse([x-5, y-5, x+5, y+5], fill=(255, 215, 75))
    if kind == "stream":
        d.polygon([(500, 720), (625, 390), (775, 390), (940, 720)], fill=(75, 175, 225))
        for x in range(565, 900, 85):
            d.ellipse([x, 555, x+75, 595], fill=(185, 180, 170))
    if kind == "path":
        d.polygon([(560, 720), (625, 470), (700, 470), (850, 720)], fill=(205, 170, 120))
    if kind == "sunset":
        d.rectangle([0, 0, WIDTH, 420], fill=(235, 150, 115))
        d.ellipse([960, 260, 1110, 410], fill=(255, 205, 105))
    if kind == "goodbye":
        d.rectangle([0, 0, WIDTH, 430], fill=(48, 60, 115))
        for x, y in [(100, 100), (240, 170), (410, 80), (610, 145), (800, 75), (1110, 130), (1000, 220)]:
            d.ellipse([x, y, x+8, y+8], fill=(255, 242, 180))

    # Scene-specific prop.
    if kind in {"flower", "water", "magic", "friends", "dance", "sunset"}:
        d.line([1030, 470, 1030, 585], fill=(45, 130, 60), width=10)
        petals = (245, 105, 175) if kind != "magic" else (255, 180, 90)
        for a in range(0, 360, 72):
            r = math.radians(a)
            cx, cy = 1030 + int(math.cos(r)*55), 450 + int(math.sin(r)*55)
            d.ellipse([cx-28, cy-28, cx+28, cy+28], fill=petals)
        d.ellipse([1000, 420, 1060, 480], fill=(255, 205, 70))
    img.save(path)


def make_character(path: Path) -> None:
    img = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Milo: deliberately simple 2D mascot with readable silhouette.
    d.ellipse([35, 80, 145, 245], fill=(145, 92, 48), outline=(95, 60, 35), width=6)
    d.ellipse([275, 80, 385, 245], fill=(145, 92, 48), outline=(95, 60, 35), width=6)
    d.ellipse([100, 230, 320, 405], fill=(185, 125, 65), outline=(105, 70, 40), width=7)
    d.ellipse([75, 55, 345, 310], fill=(205, 145, 78), outline=(105, 70, 40), width=7)
    d.ellipse([145, 175, 275, 265], fill=(238, 190, 125))
    d.ellipse([196, 178, 225, 205], fill=(45, 35, 30))
    for x in (145, 250):
        d.ellipse([x, 125, x+45, 170], fill=(65, 40, 25))
        d.ellipse([x+10, 133, x+22, 145], fill=(255, 255, 255))
    d.arc([175, 195, 250, 245], 0, 180, fill=(75, 45, 35), width=6)
    d.polygon([(100, 265), (320, 265), (300, 315), (120, 315)], fill=(55, 120, 210))
    d.polygon([(260, 305), (325, 305), (300, 390), (255, 350)], fill=(45, 100, 190))
    img.save(path)


def assets(kind: str):
    ASSETS.mkdir(parents=True, exist_ok=True)
    bg = ASSETS / f"bg_{kind}.png"
    char = ASSETS / "milo.png"
    if not bg.exists(): make_background(kind, bg)
    if not char.exists(): make_character(char)
    return bg, char


def voice(text: str, out: Path, index: int) -> None:
    if not shutil.which("espeak-ng"):
        raise RuntimeError("espeak-ng is required for the zero-cost local voice")
    # Vary pacing and pitch by scene so the narration does not sound like one flat block.
    speeds = [138, 145, 150, 142]
    pitches = [58, 52, 62, 55]
    run(["espeak-ng", "-v", "en-us", "-s", str(speeds[index % 4]), "-p", str(pitches[index % 4]), "-a", "175", "-w", str(out), text])


def scene(index: int, kind: str, line: str) -> Path:
    bg, char = assets(kind)
    sd = SCENES / f"scene_{index:03d}"
    sd.mkdir(parents=True, exist_ok=True)
    wav = sd / "voice.wav"
    voice(line, wav, index)
    silent = sd / "silent.mp4"
    out = sd / "scene.mp4"
    sx, ex = ((-100, 900) if index % 2 else (900, -100))
    inputs = ["-loop", "1", "-i", str(bg), "-loop", "1", "-i", str(char)]
    # Add subtle sparkle particles for the magic scene using FFmpeg's drawbox overlay.
    filt = (
        f"[0:v]zoompan=z='min(zoom+0.0012,1.08)':d={FPS*SCENE_SECONDS}:s={WIDTH}x{HEIGHT}:fps={FPS}[bg];"
        f"[1:v]format=rgba,scale=360:-1[m];"
        f"[bg][m]overlay=x='{sx}+({ex}-{sx})*(t/{SCENE_SECONDS})':y='360+18*sin(t*2.2)':eval=frame[base];"
        f"[base]drawbox=x='1080+25*sin(t*2)':y='180+35*cos(t*2.7)':w=9:h=9:color=white@0.65:t=fill[video]"
    )
    run(inputs + [
        "-filter_complex", filt, "-map", "[video]", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={SCENE_SECONDS}",
        "-t", str(SCENE_SECONDS), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-y", str(silent)
    ])
    # Add a quiet, scene-dependent musical bed beneath the narration.
    freq = 261 + (index % 5) * 55
    run([
        "-i", str(silent), "-i", str(wav), "-f", "lavfi", "-t", str(SCENE_SECONDS), "-i",
        f"sine=frequency={freq}:sample_rate=48000:duration={SCENE_SECONDS}",
        "-filter_complex",
        "[2:a]volume=0.012[music];[1:a]apad=pad_dur=6,volume=1[narr];[narr][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-y", str(out)
    ])
    return out


def main() -> int:
    content = os.getenv("CONTENT_TYPE", "poem").strip().lower()
    topic = os.getenv("TOPIC", "Milo and the Little Flower").strip()
    duration = float(os.getenv("DURATION", "1"))
    if content not in {"poem", "story"}: raise RuntimeError("CONTENT_TYPE must be poem or story")
    if not topic: raise RuntimeError("TOPIC must not be empty")
    if not 1 <= duration <= 10: raise RuntimeError("DURATION must be between 1 and 10 minutes")
    OUTPUT.mkdir(parents=True, exist_ok=True); SCENES.mkdir(parents=True, exist_ok=True)
    count = max(1, math.ceil(duration * 60 / SCENE_SECONDS))
    lines = POEM_LINES if content == "poem" else STORY_LINES
    clips = [scene(i + 1, SCENES_DATA[i % len(SCENES_DATA)][0], lines[i % len(lines)]) for i in range(count)]
    concat = OUTPUT / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'" for p in clips) + "\n", encoding="utf-8")
    final = OUTPUT / "kids-animation.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(final)])
    if not final.is_file() or final.stat().st_size < 100_000: raise RuntimeError("Final animation was not created or is unexpectedly small")
    production = {"topic": topic, "content_type": content, "duration_minutes": duration, "duration_seconds": duration * 60, "video": "kids-animation.mp4", "size_bytes": final.stat().st_size, "production_mode": "zero_cost_local", "voice": "espeak-ng", "renderer": "ffmpeg", "scene_count": count, "episode": "Milo and the Little Flower"}
    (OUTPUT / "production.json").write_text(json.dumps(production, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created {final} ({final.stat().st_size} bytes)")
    return 0

if __name__ == "__main__": raise SystemExit(main())
