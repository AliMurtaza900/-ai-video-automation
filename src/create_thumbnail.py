import html
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
THUMBNAIL = OUTPUT / "thumbnail.jpg"

W, H = 1280, 720


def font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def extract_frame(video):
    frame = OUTPUT / "thumbnail_frame.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-ss", "2", "-i", str(video), "-frames:v", "1",
        "-vf", """scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,gblur=sigma=0.35""",
        str(frame),
    ], check=True, capture_output=True)
    return frame


def create(video, title):
    frame = extract_frame(video)
    image = Image.open(frame).convert("RGB").resize((W, H))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Cinematic dark gradient bands keep text readable without turning the
    # thumbnail into a plain-text screen.
    for y in range(H):
        alpha = int(190 * max(0, 1 - y / H))
        draw.line((0, y, W, y), fill=(0, 0, 0, alpha))
    draw.rounded_rectangle((48, 48, 310, 112), radius=18, fill=(220, 38, 38, 235))
    draw.text((78, 62), "DID YOU KNOW?", font=font(28), fill="white")

    title = " ".join(title.split())[:72]
    title_font = font(58)
    # Wrap into at most three lines based on rendered width.
    words, lines, current = title.split(), [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=title_font)[2] <= 1120:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == 2:
            break
    if current and len(lines) < 3:
        lines.append(current)
    if not lines:
        lines = ["Amazing Fact"]

    y = 390 - (len(lines) - 1) * 34
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=3)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=title_font, fill="white", stroke_width=5, stroke_fill=(0, 0, 0, 220))
        y += 70

    draw.rounded_rectangle((430, 620, 850, 676), radius=16, fill=(255, 255, 255, 225))
    badge_font = font(25)
    badge = "NEW FACT • WATCH NOW"
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, 635), badge, font=badge_font, fill=(20, 20, 20))

    final = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    final.save(THUMBNAIL, "JPEG", quality=94, optimize=True)
    print(f"Created thumbnail: {THUMBNAIL}")
    return THUMBNAIL


if __name__ == "__main__":
    video = OUTPUT / "final-video.mp4"
    if not video.exists():
        raise RuntimeError("final-video.mp4 not found")
    title = (OUTPUT / "script.txt").read_text(encoding="utf-8").splitlines()[0] if (OUTPUT / "script.txt").exists() else "Amazing Fact"
    create(video, title)
