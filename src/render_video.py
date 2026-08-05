from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
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


def load_caption_timings():
    timing_file = OUTPUT / "caption_timing.txt"
    if not timing_file.exists():
        return []
    result = []
    for line in timing_file.read_text(encoding="utf-8").splitlines():
        try:
            start, end, text = line.split("|", 2)
            result.append((float(start), float(end), text))
        except ValueError:
            continue
    return result


def caption_for_frame(timings, frame):
    t = frame / FPS
    for start, end, text in timings:
        if start <= t < end:
            return text
    return ""


def load_visuals():
    images = []
    for path in sorted(VISUALS.glob("visual_*")):
        try:
            img = Image.open(path).convert("RGB")
            images.append(img)
        except OSError:
            pass
    return images


def visual_background(images, index):
    if not images:
        phase = index / (FPS * 2)
        return Image.new("RGB", (W, H), (
            int(10 + 12 * (phase % 1)),
            int(14 + 10 * ((phase + 0.33) % 1)),
            int(28 + 18 * ((phase + 0.66) % 1)),
        ))

    # Hold each image for several seconds and apply a gentle zoom/pan so the
    # stills feel like video rather than a slideshow.
    slot = max(1, FPS * 5)
    image = images[(index // slot) % len(images)].copy()
    scale = max(W / image.width, H / image.height) * (1.0 + 0.08 * ((index % slot) / slot))
    nw, nh = int(image.width * scale), int(image.height * scale)
    image = image.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - W) // 2)
    top = max(0, (nh - H) // 2)
    image = image.crop((left, top, left + W, top + H))

    # Darken slightly so white captions remain readable.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 85))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    return image


def make_frame(index, timings, visuals):
    img = visual_background(visuals, index)
    draw = ImageDraw.Draw(img)

    title_font = get_font(FONT_BOLD, 58)
    caption_font = get_font(FONT_BOLD, 64)
    small_font = get_font(FONT_REGULAR, 34)

    draw.text((W // 2, 150), "AI FACT", font=title_font, anchor="mm")

    caption = caption_for_frame(timings, index)
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
        draw.rounded_rectangle(box, radius=35, fill=(5, 5, 10, 185), outline=(255, 255, 255), width=4)
        draw.multiline_text((W // 2, H // 2), wrapped, font=caption_font, spacing=16, align="center", anchor="mm", fill=(255, 255, 255))

    draw.text((W // 2, H - 120), "Follow for more facts", font=small_font, anchor="mm", fill=(255, 255, 255))
    return img


def main():
    script_file = OUTPUT / "script.txt"
    script = script_file.read_text(encoding="utf-8").strip() if script_file.exists() else ""
    if not script:
        raise RuntimeError("Generated script is empty")

    timings = load_caption_timings()
    if not timings:
        raise RuntimeError("Caption timing data is missing; generate the voice before rendering")

    visuals = load_visuals()
    print(f"Using {len(visuals)} downloaded visuals")

    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = FPS * MAX_SECONDS

    for old in frames.glob("frame_*.png"):
        old.unlink()

    for i in range(total):
        make_frame(i, timings, visuals).save(frames / f"frame_{i:04d}.png")

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
