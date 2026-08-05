from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 45


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def caption_for_frame(words, frame):
    if not words:
        return ""
    # Show roughly 6 words at a time, with a gentle timing variation.
    chunk_size = 6
    chunk_index = min(len(words) // chunk_size, max(0, frame // (FPS * 2)))
    start = chunk_index * chunk_size
    return " ".join(words[start:start + chunk_size])


def make_frame(index, words):
    # Animated abstract background: no external image API required.
    phase = index / (FPS * 2)
    bg = (
        int(10 + 12 * ((phase % 1))),
        int(14 + 10 * (((phase + 0.33) % 1))),
        int(28 + 18 * (((phase + 0.66) % 1))),
    )
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Moving geometric light panels.
    x = int((W + 500) * ((index % (FPS * 8)) / (FPS * 8))) - 500
    draw.rounded_rectangle((x, 220, x + 650, 700), radius=80, outline=(90, 110, 180), width=8)
    draw.ellipse((W - x - 250, 900, W - x + 350, 1500), outline=(80, 150, 190), width=10)

    title_font = get_font(FONT_BOLD, 58)
    caption_font = get_font(FONT_BOLD, 64)
    small_font = get_font(FONT_REGULAR, 34)

    draw.text((W // 2, 150), "AI FACT", font=title_font, anchor="mm")

    caption = caption_for_frame(words, index)
    if caption:
        wrapped = "\n".join(textwrap.wrap(caption, width=24))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=caption_font, spacing=16, align="center")
        pad = 45
        box = (
            W // 2 - (bbox[2] - bbox[0]) // 2 - pad,
            H // 2 - (bbox[3] - bbox[1]) // 2 - pad,
            W // 2 + (bbox[2] - bbox[0]) // 2 + pad,
            H // 2 + (bbox[3] - bbox[1]) // 2 + pad,
        )
        draw.rounded_rectangle(box, radius=35, fill=(5, 5, 10), outline=(150, 160, 220), width=4)
        draw.multiline_text((W // 2, H // 2), wrapped, font=caption_font, spacing=16, align="center", anchor="mm")

    draw.text((W // 2, H - 120), "Follow for more facts", font=small_font, anchor="mm")
    return img


def main():
    script_file = OUTPUT / "script.txt"
    script = script_file.read_text(encoding="utf-8").strip() if script_file.exists() else ""
    words = script.split()
    if not words:
        raise RuntimeError("Generated script is empty")

    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = FPS * MAX_SECONDS

    for old in frames.glob("frame_*.png"):
        old.unlink()

    for i in range(total):
        make_frame(i, words).save(frames / f"frame_{i:04d}.png")

    output = OUTPUT / "test-video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(frames / "frame_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        str(output)
    ], check=True)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
